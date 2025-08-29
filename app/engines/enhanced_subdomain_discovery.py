"""
增强的子域名发现引擎
支持迭代式发现和动态添加子域名
"""

import asyncio
import aiohttp
import dns.resolver
import dns.exception
import re
import json
import ssl
import socket
from typing import List, Dict, Set, Optional, Any, Tuple, Union
from urllib.parse import urlparse, urljoin
from datetime import datetime
import time
from dataclasses import dataclass
from collections import defaultdict

from app.core.logging import TaskLogger
from app.core.config import settings
from app.engines.subdomain_discovery import SubdomainResult, DNSQueryMethod, CertificateTransparencyMethod


@dataclass
class DomainSource:
    """域名来源记录"""
    domain: str
    source_url: str
    discovered_at: datetime
    discovery_method: str


class EnhancedSubdomainDiscovery:
    """增强的子域名发现引擎"""
    
    def __init__(self, task_id: str, user_id: str, target_domain: str):
        self.task_id = task_id
        self.user_id = user_id
        self.target_domain = target_domain.lower().strip()
        self.logger = TaskLogger(task_id, user_id)
        
        # 发现的子域名集合
        self.discovered_subdomains: Set[str] = set()
        # 第三方域名集合
        self.third_party_domains: Set[str] = set()
        # 域名来源记录
        self.domain_sources: Dict[str, List[DomainSource]] = defaultdict(list)
        # 待爬取的子域名队列
        self.subdomain_queue: Set[str] = set()
        # 已爬取的子域名
        self.crawled_subdomains: Set[str] = set()
        
        # 初始化发现方法
        self.dns_method = DNSQueryMethod()
        self.ct_method = CertificateTransparencyMethod()
        
        # 配置参数
        self.max_crawl_depth = getattr(settings, 'MAX_CRAWL_DEPTH', 3)
        self.max_subdomains_per_task = getattr(settings, 'MAX_SUBDOMAINS_PER_TASK', 1000)
        
    async def discover_subdomains(self) -> Tuple[List[SubdomainResult], List[Dict[str, Any]]]:
        """
        执行完整的子域名发现流程
        返回: (子域名列表, 第三方域名列表)
        """
        try:
            self.logger.info(f"开始子域名发现: {self.target_domain}")
            
            # 阶段1: 初始子域名发现
            initial_subdomains = await self._initial_subdomain_discovery()
            self.logger.info(f"初始发现 {len(initial_subdomains)} 个子域名")
            
            # 阶段2: 迭代式网页爬取和动态发现
            additional_subdomains, third_party_domains = await self._iterative_discovery()
            self.logger.info(f"迭代发现 {len(additional_subdomains)} 个子域名，{len(third_party_domains)} 个第三方域名")
            
            # 合并结果
            all_subdomains = initial_subdomains + additional_subdomains
            
            # 记录统计信息
            self.logger.info(f"子域名发现完成: 总共 {len(all_subdomains)} 个子域名，{len(third_party_domains)} 个第三方域名")
            
            return all_subdomains, third_party_domains
            
        except Exception as e:
            self.logger.error(f"子域名发现异常: {e}")
            raise e
    
    async def _initial_subdomain_discovery(self) -> List[SubdomainResult]:
        """初始子域名发现阶段"""
        all_subdomains = []
        
        # DNS查询发现
        try:
            dns_results = await self.dns_method.discover(self.target_domain, self.logger)
            all_subdomains.extend(dns_results)
            for result in dns_results:
                self.discovered_subdomains.add(result.subdomain)
                self.subdomain_queue.add(result.subdomain)
                self._record_domain_source(result.subdomain, "初始DNS查询", "dns_discovery")
        except Exception as e:
            self.logger.warning(f"DNS查询失败: {e}")
        
        # 证书透明度查询发现
        try:
            ct_results = await self.ct_method.discover(self.target_domain, self.logger)
            all_subdomains.extend(ct_results)
            for result in ct_results:
                if result.subdomain not in self.discovered_subdomains:
                    self.discovered_subdomains.add(result.subdomain)
                    self.subdomain_queue.add(result.subdomain)
                    self._record_domain_source(result.subdomain, "证书透明日志", "certificate_transparency")
        except Exception as e:
            self.logger.warning(f"证书透明度查询失败: {e}")
        
        self.logger.info(f"初始发现完成，待爬取队列: {len(self.subdomain_queue)} 个子域名")
        
        return all_subdomains
    
    async def _iterative_discovery(self) -> Tuple[List[SubdomainResult], List[Dict[str, Any]]]:
        """迭代式发现阶段"""
        new_subdomains = []
        third_party_domains = []
        current_depth = 0
        
        while (self.subdomain_queue and 
               current_depth < self.max_crawl_depth and 
               len(self.discovered_subdomains) < self.max_subdomains_per_task):
            
            current_depth += 1
            self.logger.info(f"开始第 {current_depth} 层迭代爬取，队列中有 {len(self.subdomain_queue)} 个子域名")
            
            # 获取当前批次要爬取的子域名
            batch_subdomains = list(self.subdomain_queue)[:50]  # 每批最多处理50个
            self.subdomain_queue.clear()
            
            # 并发爬取子域名
            crawl_tasks = []
            for subdomain in batch_subdomains:
                if subdomain not in self.crawled_subdomains:
                    crawl_tasks.append(self._crawl_subdomain_for_links(subdomain))
                    
            if crawl_tasks:
                crawl_results = await asyncio.gather(*crawl_tasks, return_exceptions=True)
                
                # 处理爬取结果
                for i, result in enumerate(crawl_results):
                    subdomain = batch_subdomains[i]
                    self.crawled_subdomains.add(subdomain)
                    
                    if isinstance(result, Exception):
                        self.logger.warning(f"爬取 {subdomain} 失败: {result}")
                        continue
                    
                    if result and isinstance(result, tuple) and len(result) == 2:
                        discovered_domains, third_party_found = result
                        
                        # 处理新发现的子域名
                        for new_subdomain in discovered_domains:
                            if new_subdomain not in self.discovered_subdomains:
                                self.discovered_subdomains.add(new_subdomain)
                                self.subdomain_queue.add(new_subdomain)
                                # 创建SubdomainResult对象
                                subdomain_result = SubdomainResult(new_subdomain, "iterative_crawling")
                                new_subdomains.append(subdomain_result)
                                self._record_domain_source(new_subdomain, f"https://{subdomain}", "iterative_crawling")
                        
                        # 处理第三方域名
                        third_party_domains.extend(third_party_found)
            
            self.logger.info(f"第 {current_depth} 层完成，新发现 {len(new_subdomains)} 个子域名")
        
        return new_subdomains, third_party_domains
    
    async def _crawl_subdomain_for_links(self, subdomain: str) -> Optional[Tuple[List[str], List[Dict[str, Any]]]]:
        """爬取子域名页面提取链接"""
        try:
            url = f"https://{subdomain}"
            
            # 创建HTTP会话
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(ssl=False, limit=10)
            
            async with aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            ) as session:
                
                # 尝试访问HTTPS，失败则尝试HTTP
                test_url = f"https://{subdomain}"  # 默认URL
                for protocol in ['https', 'http']:
                    try:
                        test_url = f"{protocol}://{subdomain}"
                        async with session.get(test_url, allow_redirects=True) as response:
                            if response.status == 200:
                                content = await response.text()
                                content_type = response.headers.get('content-type', '').lower()
                                
                                # 只处理HTML内容
                                if 'html' in content_type:
                                    return await self._extract_domains_from_content(content, test_url)
                                
                        break  # 成功访问则跳出循环
                        
                    except Exception as e:
                        self.logger.debug(f"访问 {test_url} 失败: {e}")
                        continue
                
        except Exception as e:
            self.logger.debug(f"爬取 {subdomain} 异常: {e}")
        
        return None
    
    async def _extract_domains_from_content(self, content: str, source_url: str) -> Tuple[List[str], List[Dict[str, Any]]]:
        """从网页内容中提取域名"""
        discovered_subdomains = []
        third_party_domains = []
        
        # 提取所有URL
        url_patterns = [
            r'https?://([^/\s<>"\']+)',  # 完整URL中的域名
            r'//([^/\s<>"\']+)',         # 协议相对URL
            r'href=["\']https?://([^/\s<>"\']+)["\']',  # href属性
            r'src=["\']https?://([^/\s<>"\']+)["\']',   # src属性
        ]
        
        all_domains = set()
        for pattern in url_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                domain = match.lower().strip()
                # 清理域名（移除端口号、路径等）
                domain = self._clean_domain(domain)
                if domain and self._is_valid_domain(domain):
                    all_domains.add(domain)
        
        # 分类域名
        for domain in all_domains:
            if self._is_target_subdomain(domain):
                # 是目标域名的子域名
                if domain not in self.discovered_subdomains:
                    discovered_subdomains.append(domain)
                    self._record_domain_source(domain, source_url, "link_extraction")
            else:
                # 第三方域名
                if domain not in self.third_party_domains:
                    self.third_party_domains.add(domain)
                    third_party_info = {
                        'domain': domain,
                        'source_url': source_url,
                        'discovered_at': datetime.utcnow().isoformat(),
                        'discovery_method': 'link_extraction'
                    }
                    third_party_domains.append(third_party_info)
                    self._record_domain_source(domain, source_url, "third_party_extraction")
        
        return discovered_subdomains, third_party_domains
    
    def _clean_domain(self, domain: str) -> str:
        """清理域名"""
        try:
            # 移除端口号
            if ':' in domain:
                domain = domain.split(':')[0]
            
            # 移除路径
            if '/' in domain:
                domain = domain.split('/')[0]
            
            # 移除查询参数
            if '?' in domain:
                domain = domain.split('?')[0]
            
            return domain.lower().strip()
        except:
            return ""
    
    def _is_valid_domain(self, domain: str) -> bool:
        """验证域名格式是否有效"""
        try:
            if not domain or len(domain) > 253:
                return False
            
            # 基本格式检查
            if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$', domain):
                return False
            
            # 检查是否包含有效的TLD
            parts = domain.split('.')
            if len(parts) < 2:
                return False
            
            # 过滤明显无效的域名
            invalid_patterns = [
                r'^localhost$',
                r'^127\.0\.0\.1$',
                r'^0\.0\.0\.0$',
                r'^\d+\.\d+\.\d+\.\d+$',  # IP地址
            ]
            
            for pattern in invalid_patterns:
                if re.match(pattern, domain):
                    return False
            
            return True
        except:
            return False
    
    def _is_target_subdomain(self, domain: str) -> bool:
        """检查是否为目标域名的子域名"""
        if domain == self.target_domain:
            return True
        if domain.endswith(f'.{self.target_domain}'):
            return True
        return False
    
    def _record_domain_source(self, domain: str, source_url: str, method: str):
        """记录域名来源"""
        source = DomainSource(
            domain=domain,
            source_url=source_url,
            discovered_at=datetime.utcnow(),
            discovery_method=method
        )
        self.domain_sources[domain].append(source)
    
    def get_domain_sources(self, domain: str) -> List[DomainSource]:
        """获取域名的所有来源记录"""
        return self.domain_sources.get(domain, [])
    
    def get_discovery_stats(self) -> Dict[str, Any]:
        """获取发现统计信息"""
        return {
            'total_subdomains': len(self.discovered_subdomains),
            'total_third_party_domains': len(self.third_party_domains),
            'crawled_subdomains': len(self.crawled_subdomains),
            'discovery_methods': self._get_method_stats()
        }
    
    def _get_method_stats(self) -> Dict[str, int]:
        """获取发现方法统计"""
        method_stats = defaultdict(int)
        for sources in self.domain_sources.values():
            for source in sources:
                method_stats[source.discovery_method] += 1
        return dict(method_stats)