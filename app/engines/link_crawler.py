import asyncio
import aiohttp
import re
import time
from typing import List, Dict, Set, Optional, Any, Tuple
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from datetime import datetime
import hashlib

from app.core.logging import TaskLogger
from app.core.config import settings


class CrawlResult:
    """爬取结果"""
    
    def __init__(self, url: str, domain: str):
        self.url: str = url
        self.domain: str = domain
        self.status_code: Optional[int] = None
        self.content_type: Optional[str] = None
        self.page_title: Optional[str] = None
        self.content_length: int = 0
        self.response_time: float = 0.0
        self.links: List[str] = []
        self.resources: List[str] = []
        self.forms: List[str] = []
        self.error_message: Optional[str] = None
        self.crawled_at: datetime = datetime.utcnow()
        self.content_hash: Optional[str] = None
    
    def set_content_hash(self, content: str):
        """设置内容哈希"""
        self.content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()


class LinkExtractor:
    """链接提取器"""
    
    def __init__(self):
        # 链接提取正则表达式
        self.link_patterns = [
            r'href=["\']([^"\']+)["\']',  # href链接
            r'src=["\']([^"\']+)["\']',   # src资源
            r'action=["\']([^"\']+)["\']', # 表单action
            r'url\(["\']?([^"\'()]+)["\']?\)',  # CSS url()
            r'@import\s+["\']([^"\']+)["\']',   # CSS @import
        ]
        
        # 资源文件扩展名
        self.resource_extensions = {
            'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico'],
            'styles': ['.css'],
            'scripts': ['.js'],
            'documents': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'],
            'media': ['.mp4', '.mp3', '.avi', '.mov', '.wmv', '.flv', '.wav'],
            'archives': ['.zip', '.rar', '.tar', '.gz', '.7z']
        }
    
    def extract_links_from_html(self, html: str, base_url: str) -> Tuple[List[str], List[str], List[str]]:
        """从HTML中提取链接"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            links = []
            resources = []
            forms = []
            
            # 提取页面链接
            for tag in soup.find_all(['a', 'link']):
                href = tag.get('href')
                if href:
                    absolute_url = urljoin(base_url, href)
                    if self._is_valid_url(absolute_url):
                        if self._is_resource_url(absolute_url):
                            resources.append(absolute_url)
                        else:
                            links.append(absolute_url)
            
            # 提取资源链接
            for tag in soup.find_all(['img', 'script', 'iframe', 'embed', 'object']):
                src = tag.get('src')
                if src:
                    absolute_url = urljoin(base_url, src)
                    if self._is_valid_url(absolute_url):
                        resources.append(absolute_url)
            
            # 提取表单链接
            for form in soup.find_all('form'):
                action = form.get('action')
                if action:
                    absolute_url = urljoin(base_url, action)
                    if self._is_valid_url(absolute_url):
                        forms.append(absolute_url)
            
            # 使用正则表达式提取更多链接
            regex_links = self._extract_links_with_regex(html, base_url)
            resources.extend(regex_links)
            
            return list(set(links)), list(set(resources)), list(set(forms))
            
        except Exception as e:
            return [], [], []
    
    def _extract_links_with_regex(self, content: str, base_url: str) -> List[str]:
        """使用正则表达式提取链接"""
        links = []
        
        for pattern in self.link_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                absolute_url = urljoin(base_url, match)
                if self._is_valid_url(absolute_url):
                    links.append(absolute_url)
        
        return links
    
    def _is_valid_url(self, url: str) -> bool:
        """验证URL是否有效"""
        try:
            parsed = urlparse(url)
            return bool(parsed.netloc and parsed.scheme in ['http', 'https'])
        except:
            return False
    
    def _is_resource_url(self, url: str) -> bool:
        """判断是否为资源URL"""
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            
            for category, extensions in self.resource_extensions.items():
                for ext in extensions:
                    if path.endswith(ext):
                        return True
            
            return False
        except:
            return False


class RobotsChecker:
    """robots.txt检查器"""
    
    def __init__(self):
        self.robots_cache = {}
    
    async def can_fetch(self, url: str, user_agent: str = '*') -> bool:
        """检查是否允许抓取URL"""
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            
            # 检查缓存
            if robots_url not in self.robots_cache:
                await self._load_robots_txt(robots_url)
            
            robots = self.robots_cache.get(robots_url)
            if robots:
                return robots.can_fetch(user_agent, url)
            
            # 如果无法获取robots.txt，默认允许
            return True
            
        except Exception:
            return True
    
    async def _load_robots_txt(self, robots_url: str):
        """加载robots.txt文件"""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            ) as session:
                async with session.get(robots_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        # 解析robots.txt
                        rp = RobotFileParser()
                        rp.parse(content.splitlines())
                        self.robots_cache[robots_url] = rp
                    else:
                        self.robots_cache[robots_url] = None
                        
        except Exception:
            self.robots_cache[robots_url] = None


class LinkCrawlerEngine:
    """链接爬取引擎"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        self.link_extractor = LinkExtractor()
        self.robots_checker = RobotsChecker()
        
        # 爬取状态
        self.crawled_urls = set()
        self.failed_urls = set()
        self.discovered_links = set()
        self.discovered_resources = set()
        self.third_party_crawled_depth = {}  # 记录第三方域名的爬取深度
        self.all_crawled_links = []  # 全量存储所有爬取到的链接
        self.found_subdomains = set()  # 记录发现的子域名
    
    async def crawl_domain(
        self, 
        domain: str, 
        start_urls: List[str], 
        config: Dict[str, Any]
    ) -> List[CrawlResult]:
        """爬取域名下的所有链接"""
        start_time = time.time()
        self.logger.info(f"开始爬取域名: {domain}")
        
        # 获取配置
        max_depth = config.get('crawl_depth', 3)
        max_pages = config.get('max_pages_per_domain', 100)
        respect_robots = config.get('respect_robots_txt', True)
        timeout_per_page = config.get('timeout_per_page', 30)
        
        results = []
        urls_to_crawl = set(start_urls)
        current_depth = 0
        
        # 清空全量链接存储和发现的子域名
        self.all_crawled_links = []
        self.found_subdomains = set()
        
        # 创建HTTP会话
        connector = aiohttp.TCPConnector(
            limit=20,
            limit_per_host=5,
            ssl=False
        )
        
        timeout = aiohttp.ClientTimeout(total=timeout_per_page)
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'DomainScanner/1.0'}
        ) as session:
            
            while current_depth <= max_depth and urls_to_crawl and len(results) < max_pages:
                self.logger.info(f"爬取深度 {current_depth}: {len(urls_to_crawl)} 个URL待处理")
                
                # 当前深度的URL
                current_urls = list(urls_to_crawl)
                urls_to_crawl.clear()
                
                # 并发爬取当前深度的URL
                semaphore = asyncio.Semaphore(10)  # 限制并发数
                
                async def crawl_single_url(url: str):
                    async with semaphore:
                        return await self._crawl_single_page(
                            session, url, domain, respect_robots
                        )
                
                # 批量爬取
                tasks = [crawl_single_url(url) for url in current_urls[:max_pages - len(results)]]
                crawl_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 处理爬取结果
                for result in crawl_results:
                    if isinstance(result, CrawlResult) and result.status_code:
                        results.append(result)
                        
                        # 将爬取到的链接添加到全量存储中
                        self.all_crawled_links.append(result.url)
                        
                        # 将发现的新链接分类处理
                        for link in result.links:
                            if link not in self.crawled_urls and link not in self.failed_urls:
                                if self._is_same_domain(link, domain):
                                    # 同域链接，可以继续深入爬取
                                    urls_to_crawl.add(link)
                                    
                                    # 从同域链接中提取子域名
                                    subdomain = self._extract_subdomain(link, domain)
                                    if subdomain and subdomain not in self.found_subdomains:
                                        self.found_subdomains.add(subdomain)
                                        # 将新发现的子域名也添加到爬取队列中
                                        subdomain_urls = [f"https://{subdomain}", f"http://{subdomain}"]
                                        for sub_url in subdomain_urls:
                                            if sub_url not in self.crawled_urls and sub_url not in self.failed_urls:
                                                urls_to_crawl.add(sub_url)
                                # 不再对第三方域名进行深度爬取
                                # 第三方域名将在扫描执行器中直接处理
                        
                        # 记录发现的资源
                        self.discovered_resources.update(result.resources)
                        
                        # 添加资源链接到全量存储
                        self.all_crawled_links.extend(result.resources)
                        self.all_crawled_links.extend(result.forms)
                    
                    elif isinstance(result, Exception):
                        self.logger.debug(f"爬取异常: {result}")
                
                current_depth += 1
        
        duration = time.time() - start_time
        self.logger.info(f"域名爬取完成: 爬取 {len(results)} 个页面，发现 {len(self.discovered_resources)} 个资源，耗时 {duration:.2f} 秒")
        
        return results
    
    def _extract_domain(self, url: str) -> str:
        """从URL中提取域名"""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except:
            return ""
    
    def _extract_subdomain(self, url: str, target_domain: str) -> Optional[str]:
        """从URL中提取子域名"""
        try:
            parsed = urlparse(url)
            url_domain = parsed.netloc.lower()
            
            # 移除端口号
            if ':' in url_domain:
                url_domain = url_domain.split(':')[0]
            
            # 检查是否为目标域名的子域名
            if url_domain != target_domain.lower() and url_domain.endswith(f'.{target_domain.lower()}'):
                return url_domain
            
            return None
        except:
            return None
    
    async def _crawl_single_page(
        self, 
        session: aiohttp.ClientSession, 
        url: str, 
        domain: str, 
        respect_robots: bool
    ) -> Optional[CrawlResult]:
        """爬取单个页面"""
        
        # 检查是否已经爬取过
        if url in self.crawled_urls or url in self.failed_urls:
            return None
        
        # 检查robots.txt
        if respect_robots and not await self.robots_checker.can_fetch(url):
            self.logger.debug(f"robots.txt禁止访问: {url}")
            self.failed_urls.add(url)
            return None
        
        start_time = time.time()
        result = CrawlResult(url, domain)
        
        try:
            async with session.get(url, allow_redirects=True) as response:
                result.status_code = response.status
                result.content_type = response.headers.get('Content-Type', '')
                result.response_time = time.time() - start_time
                
                # 只处理HTML内容
                if 'text/html' in result.content_type.lower():
                    content = await response.text()
                    result.content_length = len(content)
                    result.set_content_hash(content)
                    
                    # 提取页面标题
                    title_match = re.search(r'<title[^>]*>([^<]+)</title>', content, re.IGNORECASE)
                    if title_match:
                        result.page_title = title_match.group(1).strip()
                    
                    # 提取链接
                    links, resources, forms = self.link_extractor.extract_links_from_html(content, url)
                    result.links = links
                    result.resources = resources
                    result.forms = forms
                    
                    self.logger.debug(f"页面爬取成功: {url} ({response.status}) - {len(links)} 链接, {len(resources)} 资源")
                
                self.crawled_urls.add(url)
                return result
                
        except asyncio.TimeoutError:
            result.error_message = "请求超时"
            self.logger.debug(f"页面爬取超时: {url}")
        except aiohttp.ClientError as e:
            result.error_message = f"网络错误: {str(e)}"
            self.logger.debug(f"页面爬取网络错误: {url} - {e}")
        except Exception as e:
            result.error_message = f"未知错误: {str(e)}"
            self.logger.debug(f"页面爬取异常: {url} - {e}")
        
        self.failed_urls.add(url)
        return result
    
    def _is_same_domain(self, url: str, domain: str) -> bool:
        """检查URL是否属于同一个域名"""
        try:
            parsed = urlparse(url)
            url_domain = parsed.netloc.lower()
            
            # 移除端口号
            if ':' in url_domain:
                url_domain = url_domain.split(':')[0]
            
            # 检查是否为相同域名或子域名
            return url_domain == domain.lower() or url_domain.endswith(f'.{domain.lower()}')
            
        except:
            return False
    
    async def get_crawl_statistics(self) -> Dict[str, Any]:
        """获取爬取统计信息"""
        return {
            'total_crawled': len(self.crawled_urls),
            'total_failed': len(self.failed_urls),
            'total_resources': len(self.discovered_resources),
            'total_links': len(self.discovered_links),
            'crawl_success_rate': len(self.crawled_urls) / (len(self.crawled_urls) + len(self.failed_urls)) if (self.crawled_urls or self.failed_urls) else 0,
            'all_crawled_links_count': len(self.all_crawled_links)  # 添加全量链接统计
        }
