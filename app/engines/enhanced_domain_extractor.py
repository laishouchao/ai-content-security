"""
增强的域名和链接提取引擎
基于CSDN文章思路实现，支持从HTML内容中智能提取域名和链接

核心功能：
1. 从HTML内容中提取所有类型的链接（href、src等）
2. 智能域名分类（目标子域名、第三方域名）
3. 支持多种编码和文本解析
4. 域名验证和过滤
5. 高性能异步处理

参考CSDN文章2的Python实现思路
"""

import asyncio
import aiohttp
import re
import time
import chardet
from typing import Dict, List, Set, Tuple, Optional, Any
from urllib.parse import urlparse, urljoin, urlunparse
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import ssl

from bs4 import BeautifulSoup, Comment
from app.core.logging import TaskLogger


@dataclass
class ExtractedLink:
    """提取的链接信息"""
    url: str
    link_type: str  # 'href', 'src', 'action', 'text'
    source_tag: str  # 'a', 'img', 'script', 'link', 'form', etc
    source_url: str
    text_content: Optional[str] = None
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExtractedDomain:
    """提取的域名信息"""
    domain: str
    domain_type: str  # 'target_subdomain', 'third_party', 'internal'
    source_links: List[str] = field(default_factory=list)
    discovery_count: int = 1
    first_seen: datetime = field(default_factory=datetime.utcnow)
    extraction_methods: Set[str] = field(default_factory=set)
    confidence_score: float = 1.0


@dataclass
class PageExtractionResult:
    """页面提取结果"""
    source_url: str
    extracted_links: List[ExtractedLink]
    extracted_domains: List[ExtractedDomain]
    page_title: Optional[str] = None
    meta_description: Optional[str] = None
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    extraction_time: float = 0.0
    error_message: Optional[str] = None


class EnhancedDomainExtractor:
    """增强的域名提取引擎"""
    
    def __init__(self, task_id: str, user_id: str, target_domain: str):
        self.task_id = task_id
        self.user_id = user_id
        self.target_domain = target_domain.lower()
        self.logger = TaskLogger(task_id, user_id)
        
        # 编译正则表达式提高性能
        self.domain_pattern = re.compile(
            r'[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)+',
            re.IGNORECASE
        )
        
        # URL提取模式
        self.url_patterns = [
            re.compile(r'https?://[^\s<>"\'`]+', re.IGNORECASE),
            re.compile(r'www\.[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9]*\.[a-zA-Z]{2,}[^\s<>"\'`]*', re.IGNORECASE),
            re.compile(r'[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9]*\.[a-zA-Z]{2,}/[^\s<>"\'`]*', re.IGNORECASE)
        ]
        
        # 需要过滤的文件扩展名（基于CSDN文章）
        self.filtered_extensions = {
            # 文档文件
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf',
            # 图片文件
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico',
            # 压缩文件
            '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',
            # 音频文件
            '.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac',
            # 视频文件
            '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm',
            # 程序文件
            '.exe', '.dll', '.so', '.dylib', '.class', '.jar', '.war',
            # 样式和脚本
            '.css', '.js', '.json', '.xml', '.rss', '.atom'
        }
        
        # 常见的第三方域名模式
        self.third_party_patterns = [
            r'.*\.googleapis\.com$',
            r'.*\.google\.com$',
            r'.*\.facebook\.com$',
            r'.*\.twitter\.com$',
            r'.*\.linkedin\.com$',
            r'.*\.amazon\.com$',
            r'.*\.cloudflare\.com$',
            r'.*\.jsdelivr\.net$',
            r'.*\.cdnjs\.cloudflare\.com$',
            r'.*\.bootstrapcdn\.com$'
        ]
        
        # 域名缓存
        self.domain_cache: Dict[str, ExtractedDomain] = {}
        self.validation_cache: Dict[str, bool] = {}
    
    async def extract_from_url(self, url: str, session: aiohttp.ClientSession) -> PageExtractionResult:
        """从URL提取域名和链接"""
        start_time = time.time()
        
        try:
            # 获取页面内容
            html_content, status_code, content_type = await self._fetch_page_content(url, session)
            
            if not html_content:
                return PageExtractionResult(
                    source_url=url,
                    extracted_links=[],
                    extracted_domains=[],
                    status_code=status_code,
                    content_type=content_type,
                    extraction_time=time.time() - start_time,
                    error_message="无法获取页面内容"
                )
            
            # 解析HTML内容
            extraction_result = await self._extract_from_html(url, html_content)
            extraction_result.status_code = status_code
            extraction_result.content_type = content_type
            extraction_result.extraction_time = time.time() - start_time
            
            return extraction_result
            
        except Exception as e:
            self.logger.error(f"URL {url} 提取失败: {e}")
            return PageExtractionResult(
                source_url=url,
                extracted_links=[],
                extracted_domains=[],
                extraction_time=time.time() - start_time,
                error_message=str(e)
            )
    
    async def extract_from_html(self, source_url: str, html_content: str) -> PageExtractionResult:
        """从HTML内容提取域名和链接"""
        return await self._extract_from_html(source_url, html_content)
    
    async def _fetch_page_content(
        self, 
        url: str, 
        session: aiohttp.ClientSession
    ) -> Tuple[Optional[str], Optional[int], Optional[str]]:
        """获取页面内容"""
        try:
            # 首先尝试HTTPS
            https_url = self._convert_to_https(url)
            
            async with session.get(https_url, allow_redirects=True) as response:
                status_code = response.status
                content_type = response.headers.get('Content-Type', '')
                
                if not self._is_html_content(content_type):
                    return None, status_code, content_type
                
                if response.status == 200:
                    content = await response.read()
                    html_content = await self._decode_content(content, content_type)
                    return html_content, status_code, content_type
                
        except Exception as e:
            self.logger.debug(f"HTTPS请求失败 {url}: {e}")
            
            # 如果HTTPS失败，尝试HTTP
            try:
                async with session.get(url, allow_redirects=True) as response:
                    status_code = response.status
                    content_type = response.headers.get('Content-Type', '')
                    
                    if not self._is_html_content(content_type):
                        return None, status_code, content_type
                    
                    if response.status == 200:
                        content = await response.read()
                        html_content = await self._decode_content(content, content_type)
                        return html_content, status_code, content_type
                        
            except Exception as e2:
                self.logger.debug(f"HTTP请求失败 {url}: {e2}")
        
        return None, None, None
    
    async def _decode_content(self, content: bytes, content_type: str) -> str:
        """解码内容"""
        # 尝试从Content-Type头获取编码
        encoding = None
        if 'charset=' in content_type:
            try:
                encoding = content_type.split('charset=')[-1].strip().split(';')[0]
            except:
                pass
        
        # 如果没有找到编码，使用chardet检测
        if not encoding:
            detected = chardet.detect(content)
            encoding = detected.get('encoding', 'utf-8')
        
        # 尝试解码
        for enc in [encoding, 'utf-8', 'gbk', 'gb2312', 'gb18030', 'big5']:
            try:
                return content.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        
        # 如果所有编码都失败，使用utf-8并忽略错误
        return content.decode('utf-8', errors='ignore')
    
    async def _extract_from_html(self, source_url: str, html_content: str) -> PageExtractionResult:
        """从HTML内容提取信息"""
        start_time = time.time()
        
        try:
            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 移除注释和脚本内容（可选）
            for element in soup(["script", "style", "noscript"]):
                element.decompose()
            
            for comment in soup.findAll(text=lambda text: isinstance(text, Comment)):
                comment.extract()
            
            # 提取页面元信息
            page_title = None
            title_tag = soup.find('title')
            if title_tag:
                page_title = title_tag.get_text().strip()
            
            meta_description = None
            meta_tag = soup.find('meta', attrs={'name': 'description'})
            if meta_tag and hasattr(meta_tag, 'get'):
                content = meta_tag.get('content')
                if content:
                    meta_description = content.strip()
            
            # 提取所有链接
            extracted_links = []
            
            # 提取各种类型的链接
            link_extractors = [
                ('a', 'href', 'href'),
                ('link', 'href', 'href'),
                ('img', 'src', 'src'),
                ('script', 'src', 'src'),
                ('iframe', 'src', 'src'),
                ('form', 'action', 'action'),
                ('area', 'href', 'href'),
                ('embed', 'src', 'src'),
                ('object', 'data', 'src'),
                ('source', 'src', 'src'),
                ('video', 'src', 'src'),
                ('audio', 'src', 'src')
            ]
            
            for tag_name, attr_name, link_type in link_extractors:
                tags = soup.find_all(tag_name, {attr_name: True})
                for tag in tags:
                    href = tag.get(attr_name)
                    if href and not href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                        # 将相对链接转换为绝对链接
                        absolute_url = urljoin(source_url, href)
                        
                        extracted_link = ExtractedLink(
                            url=absolute_url,
                            link_type=link_type,
                            source_tag=tag_name,
                            source_url=source_url,
                            text_content=tag.get_text().strip() if tag_name == 'a' else None,
                            attributes=dict(tag.attrs)
                        )
                        extracted_links.append(extracted_link)
            
            # 从页面文本中提取URL
            page_text = soup.get_text()
            text_urls = self._extract_urls_from_text(page_text)
            
            for text_url in text_urls:
                absolute_url = urljoin(source_url, text_url)
                extracted_link = ExtractedLink(
                    url=absolute_url,
                    link_type='text',
                    source_tag='text',
                    source_url=source_url
                )
                extracted_links.append(extracted_link)
            
            # 从链接中提取域名
            extracted_domains = self._extract_domains_from_links(extracted_links)
            
            return PageExtractionResult(
                source_url=source_url,
                extracted_links=extracted_links,
                extracted_domains=extracted_domains,
                page_title=page_title,
                meta_description=meta_description,
                extraction_time=time.time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"HTML解析失败 {source_url}: {e}")
            return PageExtractionResult(
                source_url=source_url,
                extracted_links=[],
                extracted_domains=[],
                extraction_time=time.time() - start_time,
                error_message=str(e)
            )
    
    def _extract_urls_from_text(self, text: str) -> List[str]:
        """从文本中提取URL"""
        urls = []
        
        for pattern in self.url_patterns:
            matches = pattern.findall(text)
            urls.extend(matches)
        
        # 去重并过滤
        unique_urls = list(set(urls))
        filtered_urls = []
        
        for url in unique_urls:
            if self._is_valid_url(url):
                filtered_urls.append(url)
        
        return filtered_urls
    
    def _extract_domains_from_links(self, links: List[ExtractedLink]) -> List[ExtractedDomain]:
        """从链接中提取域名"""
        domain_data = defaultdict(lambda: {
            'source_links': [],
            'extraction_methods': set(),
            'count': 0
        })
        
        for link in links:
            domain = self._extract_domain_from_url(link.url)
            if domain and self._is_valid_domain(domain):
                domain_data[domain]['source_links'].append(link.url)
                domain_data[domain]['extraction_methods'].add(link.link_type)
                domain_data[domain]['count'] += 1
        
        # 转换为ExtractedDomain对象
        extracted_domains = []
        for domain, data in domain_data.items():
            domain_type = self._classify_domain(domain)
            confidence_score = self._calculate_confidence_score(domain, data)
            
            extracted_domain = ExtractedDomain(
                domain=domain,
                domain_type=domain_type,
                source_links=data['source_links'][:10],  # 限制源链接数量
                discovery_count=data['count'],
                extraction_methods=data['extraction_methods'],
                confidence_score=confidence_score
            )
            
            extracted_domains.append(extracted_domain)
        
        return extracted_domains
    
    def _extract_domain_from_url(self, url: str) -> Optional[str]:
        """从URL中提取域名"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # 移除端口号
            if ':' in domain:
                domain = domain.split(':')[0]
            
            # 移除用户信息
            if '@' in domain:
                domain = domain.split('@')[-1]
            
            return domain if domain else None
            
        except Exception:
            return None
    
    def _classify_domain(self, domain: str) -> str:
        """分类域名类型"""
        if not domain:
            return 'invalid'
        
        # 检查是否是目标域名
        if domain == self.target_domain:
            return 'target_subdomain'
        
        # 检查是否是目标子域名
        if domain.endswith(f'.{self.target_domain}'):
            return 'target_subdomain'
        
        # 检查是否是知名第三方服务
        for pattern in self.third_party_patterns:
            if re.match(pattern, domain):
                return 'third_party'
        
        # 其他域名归类为第三方
        return 'third_party'
    
    def _calculate_confidence_score(self, domain: str, data: Dict[str, Any]) -> float:
        """计算域名可信度评分"""
        score = 0.5  # 基础分数
        
        # 根据发现次数加分
        count = data.get('count', 0)
        if count >= 10:
            score += 0.3
        elif count >= 5:
            score += 0.2
        elif count >= 2:
            score += 0.1
        
        # 根据提取方法数量加分
        methods = data.get('extraction_methods', set())
        if len(methods) >= 3:
            score += 0.2
        elif len(methods) >= 2:
            score += 0.1
        
        # 域名格式验证加分
        if self._is_valid_domain(domain):
            score += 0.1
        
        return min(score, 1.0)  # 最高1.0分
    
    def _is_valid_domain(self, domain: str) -> bool:
        """验证域名是否有效"""
        if not domain or len(domain) > 253:
            return False
        
        # 检查是否在验证缓存中
        if domain in self.validation_cache:
            return self.validation_cache[domain]
        
        # 基本格式验证
        is_valid = bool(self.domain_pattern.match(domain))
        
        if is_valid:
            # 检查是否是IP地址
            if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', domain):
                is_valid = False
            
            # 检查是否是本地域名
            elif domain in ('localhost', '127.0.0.1', '0.0.0.0'):
                is_valid = False
            
            # 检查是否包含文件扩展名
            elif any(domain.lower().endswith(ext) for ext in self.filtered_extensions):
                is_valid = False
        
        # 缓存结果
        self.validation_cache[domain] = is_valid
        return is_valid
    
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
            
            # 检查是否是文件扩展名
            path = parsed.path.lower()
            if any(path.endswith(ext) for ext in self.filtered_extensions):
                return False
            
            return True
            
        except Exception:
            return False
    
    def _is_html_content(self, content_type: str) -> bool:
        """检查内容类型是否为HTML"""
        if not content_type:
            return True  # 默认假设是HTML
        
        html_types = ['text/html', 'application/xhtml+xml', 'application/xml']
        return any(html_type in content_type.lower() for html_type in html_types)
    
    def _convert_to_https(self, url: str) -> str:
        """将HTTP URL转换为HTTPS"""
        if url.startswith('http://'):
            return url.replace('http://', 'https://', 1)
        return url
    
    async def batch_extract_from_urls(
        self, 
        urls: List[str], 
        max_concurrent: int = 20
    ) -> List[PageExtractionResult]:
        """批量从URL提取域名和链接"""
        self.logger.info(f"开始批量提取: {len(urls)} 个URL")
        
        # 创建SSL上下文
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # 创建连接器
        connector = aiohttp.TCPConnector(
            ssl=ssl_context,
            limit=max_concurrent,
            limit_per_host=10,
            enable_cleanup_closed=True
        )
        
        # 创建会话
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        }
        
        results = []
        
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers=headers,
            connector=connector
        ) as session:
            
            # 创建信号量控制并发
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def extract_with_semaphore(url: str) -> PageExtractionResult:
                async with semaphore:
                    return await self.extract_from_url(url, session)
            
            # 并发执行提取任务
            tasks = [extract_with_semaphore(url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 过滤异常结果
            valid_results = []
            for i, result in enumerate(results):
                if isinstance(result, PageExtractionResult):
                    valid_results.append(result)
                elif isinstance(result, Exception):
                    self.logger.warning(f"URL {urls[i]} 提取异常: {result}")
                    # 创建错误结果
                    error_result = PageExtractionResult(
                        source_url=urls[i],
                        extracted_links=[],
                        extracted_domains=[],
                        error_message=str(result)
                    )
                    valid_results.append(error_result)
        
        self.logger.info(f"批量提取完成: {len(valid_results)} 个结果")
        return valid_results
    
    def get_extraction_statistics(self) -> Dict[str, Any]:
        """获取提取统计信息"""
        total_domains = len(self.domain_cache)
        target_subdomains = len([d for d in self.domain_cache.values() if d.domain_type == 'target_subdomain'])
        third_party_domains = len([d for d in self.domain_cache.values() if d.domain_type == 'third_party'])
        
        return {
            'total_domains_cached': total_domains,
            'target_subdomains': target_subdomains,
            'third_party_domains': third_party_domains,
            'validation_cache_size': len(self.validation_cache),
            'cache_hit_rate': len(self.validation_cache) / max(total_domains, 1)
        }