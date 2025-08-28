"""
智能链接爬取器
基于CSDN文章1的思路，实现高性能的网站链接抓取功能

核心功能：
1. 从给定域名抓取所有可访问的URL页面
2. 递归抓取页面中的所有内部链接
3. 智能去重和访问控制
4. 支持多域名并发抓取
5. 集成域名提取功能

参考CSDN文章1的Go实现思路，用Python重新实现
"""

import asyncio
import aiohttp
import time
from typing import Dict, List, Set, Optional, Any, Tuple
from urllib.parse import urlparse, urljoin, urlunparse
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
import ssl
import re
from pathlib import Path

from app.core.logging import TaskLogger
from app.engines.enhanced_domain_extractor import EnhancedDomainExtractor, PageExtractionResult


@dataclass
class CrawledPage:
    """爬取的页面信息"""
    url: str
    status_code: int
    title: Optional[str] = None
    meta_description: Optional[str] = None
    content_length: int = 0
    content_type: Optional[str] = None
    response_time: float = 0.0
    crawled_at: datetime = field(default_factory=datetime.utcnow)
    found_links: List[str] = field(default_factory=list)
    found_domains: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


@dataclass
class CrawlingResult:
    """爬取结果"""
    target_domain: str
    start_urls: List[str]
    total_pages_crawled: int
    total_links_found: int
    total_domains_found: int
    crawling_duration: float
    pages: List[CrawledPage] = field(default_factory=list)
    domain_statistics: Dict[str, int] = field(default_factory=dict)
    error_count: int = 0


class SmartLinkCrawler:
    """智能链接爬取器"""
    
    def __init__(self, task_id: str, user_id: str, target_domain: str):
        self.task_id = task_id
        self.user_id = user_id
        self.target_domain = target_domain.lower()
        self.logger = TaskLogger(task_id, user_id)
        
        # 初始化域名提取器
        self.domain_extractor = EnhancedDomainExtractor(task_id, user_id, target_domain)
        
        # 爬取状态管理
        self.visited_urls: Set[str] = set()
        self.urls_to_visit: deque = deque()
        self.crawled_pages: List[CrawledPage] = []
        
        # 域名统计
        self.all_found_domains: Set[str] = set()
        self.domain_counts: Dict[str, int] = {}
        
        # 配置参数
        self.max_pages = 1000  # 最大页面数
        self.max_concurrent = 20  # 最大并发数
        self.timeout = 30  # 请求超时时间
        self.delay_between_requests = 0.1  # 请求间延迟
        
        # 过滤规则（基于CSDN文章）
        self.filtered_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico',
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.zip', '.rar', '.7z', '.tar', '.gz',
            '.mp3', '.wav', '.mp4', '.avi', '.mov'
        }
        
        # URL规范化缓存
        self.normalized_url_cache: Dict[str, str] = {}
    
    async def crawl_domain(
        self, 
        domain: str, 
        start_urls: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> CrawlingResult:
        """爬取指定域名的所有页面"""
        start_time = time.time()
        self.logger.info(f"开始爬取域名: {domain}")
        
        # 应用配置
        if config:
            self.max_pages = config.get('max_pages_per_domain', self.max_pages)
            self.max_concurrent = config.get('max_concurrent', self.max_concurrent)
            self.timeout = config.get('timeout_per_page', self.timeout)
        
        # 准备起始URL
        if not start_urls:
            start_urls = [f"https://{domain}", f"http://{domain}"]
        
        # 初始化爬取状态
        self._reset_crawling_state()
        
        # 添加起始URL到队列
        for url in start_urls:
            normalized_url = self._normalize_url(url)
            if normalized_url and self._is_target_domain_url(normalized_url, domain):
                self.urls_to_visit.append(normalized_url)
        
        # 创建HTTP会话
        await self._crawl_with_session(domain)
        
        # 生成结果
        crawling_duration = time.time() - start_time
        result = CrawlingResult(
            target_domain=domain,
            start_urls=start_urls,
            total_pages_crawled=len(self.crawled_pages),
            total_links_found=sum(len(page.found_links) for page in self.crawled_pages),
            total_domains_found=len(self.all_found_domains),
            crawling_duration=crawling_duration,
            pages=self.crawled_pages.copy(),
            domain_statistics=self.domain_counts.copy(),
            error_count=len([p for p in self.crawled_pages if p.error_message])
        )
        
        self.logger.info(f"域名 {domain} 爬取完成: "
                        f"页面 {result.total_pages_crawled}, "
                        f"链接 {result.total_links_found}, "
                        f"域名 {result.total_domains_found}, "
                        f"耗时 {crawling_duration:.2f}秒")
        
        return result
    
    async def _crawl_with_session(self, target_domain: str):
        """使用HTTP会话进行爬取"""
        # 创建SSL上下文
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # 创建连接器
        connector = aiohttp.TCPConnector(
            ssl=ssl_context,
            limit=self.max_concurrent,
            limit_per_host=10,
            enable_cleanup_closed=True
        )
        
        # 设置请求头（基于CSDN文章）
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0'
        }
        
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers=headers,
            connector=connector
        ) as session:
            
            # 创建信号量控制并发
            semaphore = asyncio.Semaphore(self.max_concurrent)
            
            # 主爬取循环
            while self.urls_to_visit and len(self.crawled_pages) < self.max_pages:
                # 获取下一批URL
                batch_urls = []
                batch_size = min(self.max_concurrent, len(self.urls_to_visit))
                
                for _ in range(batch_size):
                    if self.urls_to_visit:
                        url = self.urls_to_visit.popleft()
                        if url not in self.visited_urls:
                            batch_urls.append(url)
                            self.visited_urls.add(url)
                
                if not batch_urls:
                    break
                
                # 并发处理URL批次
                tasks = []
                for url in batch_urls:
                    if len(self.crawled_pages) >= self.max_pages:
                        break
                    task = self._crawl_single_url(url, target_domain, session, semaphore)
                    tasks.append(task)
                
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # 处理结果
                    for i, result in enumerate(results):
                        if isinstance(result, CrawledPage):
                            self.crawled_pages.append(result)
                            
                            # 添加新发现的链接到队列
                            for link in result.found_links:
                                normalized_link = self._normalize_url(link)
                                if (normalized_link and 
                                    normalized_link not in self.visited_urls and
                                    self._is_target_domain_url(normalized_link, target_domain) and
                                    len(self.urls_to_visit) < self.max_pages * 2):  # 限制队列大小
                                    self.urls_to_visit.append(normalized_link)
                            
                            # 统计域名
                            for domain in result.found_domains:
                                self.all_found_domains.add(domain)
                                self.domain_counts[domain] = self.domain_counts.get(domain, 0) + 1
                        
                        elif isinstance(result, Exception):
                            self.logger.warning(f"爬取异常: {result}")
                
                # 添加延迟避免过快请求
                if self.delay_between_requests > 0:
                    await asyncio.sleep(self.delay_between_requests)
    
    async def _crawl_single_url(
        self, 
        url: str, 
        target_domain: str, 
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore
    ) -> CrawledPage:
        """爬取单个URL"""
        async with semaphore:
            start_time = time.time()
            
            try:
                # 使用域名提取器获取页面内容和链接
                extraction_result = await self.domain_extractor.extract_from_url(url, session)
                
                response_time = time.time() - start_time
                
                # 提取链接URL
                found_links = [link.url for link in extraction_result.extracted_links]
                
                # 提取域名
                found_domains = [domain.domain for domain in extraction_result.extracted_domains]
                
                # 创建爬取页面结果
                crawled_page = CrawledPage(
                    url=url,
                    status_code=extraction_result.status_code or 0,
                    title=extraction_result.page_title,
                    meta_description=extraction_result.meta_description,
                    content_type=extraction_result.content_type,
                    response_time=response_time,
                    found_links=found_links,
                    found_domains=found_domains,
                    error_message=extraction_result.error_message
                )
                
                self.logger.debug(f"爬取成功: {url} -> {len(found_links)} 链接, {len(found_domains)} 域名")
                return crawled_page
                
            except Exception as e:
                self.logger.warning(f"爬取失败 {url}: {e}")
                return CrawledPage(
                    url=url,
                    status_code=0,
                    response_time=time.time() - start_time,
                    error_message=str(e)
                )
    
    def _reset_crawling_state(self):
        """重置爬取状态"""
        self.visited_urls.clear()
        self.urls_to_visit.clear()
        self.crawled_pages.clear()
        self.all_found_domains.clear()
        self.domain_counts.clear()
    
    def _normalize_url(self, url: str) -> Optional[str]:
        """规范化URL"""
        if not url:
            return None
        
        # 检查缓存
        if url in self.normalized_url_cache:
            return self.normalized_url_cache[url]
        
        try:
            # 处理相对URL和协议相对URL
            if url.startswith('//'):
                url = 'https:' + url
            elif not url.startswith(('http://', 'https://')):
                url = 'https://' + url.lstrip('/')
            
            parsed = urlparse(url)
            
            # 检查是否有效
            if not parsed.netloc:
                return None
            
            # 移除fragment和一些查询参数
            normalized = urlunparse((
                parsed.scheme,
                parsed.netloc.lower(),
                parsed.path,
                parsed.params,
                parsed.query,
                ''  # 移除fragment
            ))
            
            # 检查文件扩展名
            path = parsed.path.lower()
            if any(path.endswith(ext) for ext in self.filtered_extensions):
                return None
            
            # 缓存结果
            self.normalized_url_cache[url] = normalized
            return normalized
            
        except Exception:
            return None
    
    def _is_target_domain_url(self, url: str, target_domain: str) -> bool:
        """检查URL是否属于目标域名"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # 移除端口号
            if ':' in domain:
                domain = domain.split(':')[0]
            
            return domain == target_domain or domain.endswith(f'.{target_domain}')
            
        except Exception:
            return False
    
    def _is_valid_url(self, url: str) -> bool:
        """验证URL是否有效"""
        try:
            parsed = urlparse(url)
            
            # 必须有scheme和netloc
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # 检查scheme
            if parsed.scheme not in ('http', 'https'):
                return False
            
            # 检查路径
            path = parsed.path.lower()
            
            # 过滤文件扩展名
            if any(path.endswith(ext) for ext in self.filtered_extensions):
                return False
            
            # 过滤特殊路径
            if any(keyword in path for keyword in ['logout', 'login', 'register', 'admin']):
                return False
            
            return True
            
        except Exception:
            return False
    
    async def crawl_multiple_domains(
        self, 
        domains: List[str], 
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, CrawlingResult]:
        """爬取多个域名"""
        self.logger.info(f"开始爬取多个域名: {len(domains)} 个")
        
        results = {}
        
        # 并发爬取所有域名
        tasks = []
        for domain in domains:
            task = self.crawl_domain(domain, config=config)
            tasks.append((domain, task))
        
        # 执行所有任务
        for domain, task in tasks:
            try:
                result = await task
                results[domain] = result
            except Exception as e:
                self.logger.error(f"域名 {domain} 爬取失败: {e}")
                results[domain] = CrawlingResult(
                    target_domain=domain,
                    start_urls=[],
                    total_pages_crawled=0,
                    total_links_found=0,
                    total_domains_found=0,
                    crawling_duration=0.0,
                    error_count=1
                )
        
        return results
    
    def get_crawling_statistics(self) -> Dict[str, Any]:
        """获取爬取统计信息"""
        total_pages = len(self.crawled_pages)
        successful_pages = len([p for p in self.crawled_pages if not p.error_message])
        total_response_time = sum(p.response_time for p in self.crawled_pages)
        avg_response_time = total_response_time / max(total_pages, 1)
        
        return {
            'total_pages': total_pages,
            'successful_pages': successful_pages,
            'error_pages': total_pages - successful_pages,
            'success_rate': successful_pages / max(total_pages, 1),
            'average_response_time': avg_response_time,
            'total_domains_found': len(self.all_found_domains),
            'cache_size': len(self.normalized_url_cache)
        }
    
    def save_results_to_file(self, filepath: str):
        """保存结果到文件（类似CSDN文章的功能）"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # 写入统计信息
                stats = self.get_crawling_statistics()
                f.write(f"# 爬取统计信息\n")
                f.write(f"总页面数: {stats['total_pages']}\n")
                f.write(f"成功页面数: {stats['successful_pages']}\n")
                f.write(f"平均响应时间: {stats['average_response_time']:.2f}秒\n")
                f.write(f"发现域名数: {stats['total_domains_found']}\n\n")
                
                # 写入所有访问的URL
                f.write("# 所有访问的URL\n")
                for page in self.crawled_pages:
                    status = f"[{page.status_code}]" if page.status_code else "[ERROR]"
                    f.write(f"{status} {page.url}\n")
                
                # 写入发现的域名
                f.write(f"\n# 发现的域名 ({len(self.all_found_domains)} 个)\n")
                for domain in sorted(self.all_found_domains):
                    count = self.domain_counts.get(domain, 0)
                    f.write(f"{domain} (出现{count}次)\n")
            
            self.logger.info(f"结果已保存到: {filepath}")
            
        except Exception as e:
            self.logger.error(f"保存结果失败: {e}")