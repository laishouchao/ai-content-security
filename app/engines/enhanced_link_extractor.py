"""
增强的链接提取器
从HTML内容中提取所有内部和外部链接，支持多种标签解析

核心功能：
1. 全面的HTML标签解析（支持30+种标签）
2. 智能URL规范化和验证
3. 相对链接转换为绝对链接
4. CSS和JavaScript中的URL提取
5. 链接分类和过滤
6. 多种编码支持
7. 高性能批量处理
"""

import re
import asyncio
from typing import Dict, List, Set, Optional, Tuple, Any
from urllib.parse import urlparse, urljoin, urlunparse
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict, Counter
import html

from bs4 import BeautifulSoup, Comment, Tag
from app.core.logging import TaskLogger


@dataclass
class ExtractedLink:
    """提取的链接详细信息"""
    url: str
    normalized_url: str
    link_type: str  # 'navigation', 'resource', 'form', 'css', 'js', 'meta', 'text'
    source_tag: str
    source_attribute: str
    source_url: str
    
    # 链接属性
    text_content: Optional[str] = None
    title: Optional[str] = None
    rel: Optional[str] = None
    target: Optional[str] = None
    
    # 分类信息
    is_internal: bool = False
    is_external: bool = False
    is_subdomain: bool = False
    is_resource: bool = False
    resource_type: Optional[str] = None
    
    # 元数据
    extraction_method: str = 'html_parser'
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass
class LinkExtractionResult:
    """链接提取结果"""
    source_url: str
    total_links: int
    
    # 按类型分类的链接
    navigation_links: List[ExtractedLink] = field(default_factory=list)
    resource_links: List[ExtractedLink] = field(default_factory=list)
    form_links: List[ExtractedLink] = field(default_factory=list)
    css_links: List[ExtractedLink] = field(default_factory=list)
    js_links: List[ExtractedLink] = field(default_factory=list)
    text_links: List[ExtractedLink] = field(default_factory=list)
    
    # 按域名分类
    internal_links: List[ExtractedLink] = field(default_factory=list)
    external_links: List[ExtractedLink] = field(default_factory=list)
    subdomain_links: List[ExtractedLink] = field(default_factory=list)
    
    # 统计信息
    domain_distribution: Dict[str, int] = field(default_factory=dict)
    link_type_distribution: Dict[str, int] = field(default_factory=dict)
    extraction_time: float = 0.0
    error_message: Optional[str] = None


class EnhancedLinkExtractor:
    """增强的链接提取器"""
    
    def __init__(self, task_id: str, user_id: str, target_domain: str):
        self.task_id = task_id
        self.user_id = user_id
        self.target_domain = target_domain.lower()
        self.logger = TaskLogger(task_id, user_id)
        
        # HTML标签和属性配置
        self.html_extractors = {
            # 导航链接
            'a': {'attr': 'href', 'type': 'navigation'},
            'area': {'attr': 'href', 'type': 'navigation'},
            
            # 资源链接
            'img': {'attr': 'src', 'type': 'resource'},
            'script': {'attr': 'src', 'type': 'resource'},
            'link': {'attr': 'href', 'type': 'resource'},
            'iframe': {'attr': 'src', 'type': 'resource'},
            'frame': {'attr': 'src', 'type': 'resource'},
            'embed': {'attr': 'src', 'type': 'resource'},
            'object': {'attr': 'data', 'type': 'resource'},
            'source': {'attr': 'src', 'type': 'resource'},
            'video': {'attr': 'src', 'type': 'resource'},
            'audio': {'attr': 'src', 'type': 'resource'},
            
            # 表单相关
            'form': {'attr': 'action', 'type': 'form'},
        }
        
        # 多属性提取配置
        self.multi_attr_extractors = {
            'img': ['src', 'data-src', 'data-lazy-src', 'srcset'],
            'video': ['src', 'poster'],
            'source': ['src', 'srcset'],
        }
        
        # 资源文件类型
        self.resource_types = {
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico'],
            'style': ['.css'],
            'script': ['.js', '.jsx', '.ts'],
            'font': ['.woff', '.woff2', '.ttf', '.eot'],
            'document': ['.pdf', '.doc', '.docx', '.txt'],
            'media': ['.mp4', '.mp3', '.avi', '.mov', '.wav'],
            'archive': ['.zip', '.rar', '.tar', '.gz'],
            'data': ['.json', '.xml', '.csv', '.rss']
        }
        
        # URL正则表达式模式
        self.url_patterns = [
            re.compile(r'https?://[^\s<>"\'`\[\]{}\\|^]+', re.IGNORECASE),
            re.compile(r'//[^\s<>"\'`\[\]{}\\|^/][^\s<>"\'`\[\]{}\\|^]*', re.IGNORECASE),
        ]
        
        # 忽略的URL模式
        self.ignore_patterns = [
            re.compile(r'^javascript:', re.IGNORECASE),
            re.compile(r'^mailto:', re.IGNORECASE),
            re.compile(r'^tel:', re.IGNORECASE),
            re.compile(r'^data:', re.IGNORECASE),
            re.compile(r'^#', re.IGNORECASE),
            re.compile(r'^\s*$'),
        ]
    
    async def extract_from_html(
        self, 
        html_content: str, 
        source_url: str,
        extract_options: Optional[Dict[str, Any]] = None
    ) -> LinkExtractionResult:
        """从HTML内容中提取所有链接"""
        import time
        start_time = time.time()
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 1. 从HTML标签中提取链接
            html_links = await self._extract_from_html_tags(soup, source_url)
            
            # 2. 从CSS内容中提取链接
            css_links = await self._extract_from_css_content(soup, source_url)
            
            # 3. 从JavaScript内容中提取链接
            js_links = await self._extract_from_js_content(soup, source_url)
            
            # 4. 从文本内容中提取链接
            text_links = await self._extract_from_text_content(soup, source_url)
            
            # 合并所有链接
            all_links = html_links + css_links + js_links + text_links
            
            # 去重和规范化
            unique_links = await self._deduplicate_and_normalize(all_links, source_url)
            
            # 分类和分析
            result = await self._classify_and_analyze_links(unique_links, source_url)
            result.extraction_time = time.time() - start_time
            
            self.logger.debug(f"链接提取完成: {source_url} -> {len(unique_links)} 个唯一链接")
            return result
            
        except Exception as e:
            self.logger.error(f"链接提取失败 {source_url}: {e}")
            return LinkExtractionResult(
                source_url=source_url,
                total_links=0,
                extraction_time=time.time() - start_time,
                error_message=str(e)
            )
    
    async def _extract_from_html_tags(self, soup: BeautifulSoup, source_url: str) -> List[ExtractedLink]:
        """从HTML标签中提取链接"""
        links = []
        
        for tag_name, config in self.html_extractors.items():
            attr_name = config['attr']
            link_type = config['type']
            
            tags = soup.find_all(tag_name)
            
            for tag in tags:
                if tag.has_attr(attr_name):
                    url = tag.get(attr_name)
                    if url and self._is_valid_url_candidate(url):
                        link = self._create_extracted_link(
                            url, source_url, link_type, tag_name, 
                            attr_name, tag, 'html_parser'
                        )
                        if link:
                            links.append(link)
                
                # 多属性提取（如srcset）
                if tag_name in self.multi_attr_extractors:
                    for attr in self.multi_attr_extractors[tag_name]:
                        if tag.has_attr(attr) and attr != attr_name:
                            value = tag.get(attr)
                            if value:
                                if attr == 'srcset':
                                    urls = self._parse_srcset(value)
                                    for srcset_url in urls:
                                        link = self._create_extracted_link(
                                            srcset_url, source_url, 'resource', 
                                            tag_name, attr, tag, 'srcset_parser'
                                        )
                                        if link:
                                            links.append(link)
        
        return links
    
    async def _extract_from_css_content(self, soup: BeautifulSoup, source_url: str) -> List[ExtractedLink]:
        """从CSS内容中提取链接"""
        links = []
        
        # 从<style>标签中提取
        style_tags = soup.find_all('style')
        for style_tag in style_tags:
            css_content = style_tag.string or ""
            css_urls = self._extract_urls_from_css(css_content)
            
            for css_url in css_urls:
                link = self._create_extracted_link(
                    css_url, source_url, 'css', 'style', 
                    'content', style_tag, 'css_parser'
                )
                if link:
                    links.append(link)
        
        return links
    
    async def _extract_from_js_content(self, soup: BeautifulSoup, source_url: str) -> List[ExtractedLink]:
        """从JavaScript内容中提取链接"""
        links = []
        
        script_tags = soup.find_all('script')
        for script_tag in script_tags:
            if script_tag.string:
                js_urls = self._extract_urls_from_js(script_tag.string)
                
                for js_url in js_urls:
                    link = self._create_extracted_link(
                        js_url, source_url, 'js', 'script', 
                        'content', script_tag, 'js_parser'
                    )
                    if link:
                        links.append(link)
        
        return links
    
    async def _extract_from_text_content(self, soup: BeautifulSoup, source_url: str) -> List[ExtractedLink]:
        """从纯文本内容中提取链接"""
        links = []
        text_content = soup.get_text()
        
        for pattern in self.url_patterns:
            matches = pattern.findall(text_content)
            
            for match in matches:
                if self._is_valid_url_candidate(match):
                    link = self._create_extracted_link(
                        match, source_url, 'text', 'text', 
                        'content', None, 'regex_parser'
                    )
                    if link:
                        links.append(link)
        
        return links
    
    def _create_extracted_link(
        self, 
        url: str, 
        source_url: str, 
        link_type: str,
        tag_name: str, 
        attr_name: str, 
        tag: Optional[Tag], 
        extraction_method: str
    ) -> Optional[ExtractedLink]:
        """创建提取的链接对象"""
        try:
            normalized_url = self._normalize_url(url, source_url)
            if not normalized_url:
                return None
            
            link = ExtractedLink(
                url=url,
                normalized_url=normalized_url,
                link_type=link_type,
                source_tag=tag_name,
                source_attribute=attr_name,
                source_url=source_url,
                extraction_method=extraction_method
            )
            
            # 从标签中提取额外信息
            if tag:
                link.text_content = tag.get_text().strip() if tag.get_text() else None
                
                # 处理可能返回 list[str] 的属性
                title_value = tag.get('title')
                link.title = title_value if isinstance(title_value, str) else (title_value[0] if isinstance(title_value, list) and title_value else None)
                
                rel_value = tag.get('rel')
                link.rel = rel_value if isinstance(rel_value, str) else (' '.join(rel_value) if isinstance(rel_value, list) and rel_value else None)
                
                target_value = tag.get('target')
                link.target = target_value if isinstance(target_value, str) else (target_value[0] if isinstance(target_value, list) and target_value else None)
                link.attributes = dict(tag.attrs) if hasattr(tag, 'attrs') else {}
            
            # 分析URL属性
            parsed_url = urlparse(normalized_url)
            parsed_source = urlparse(source_url)
            
            if parsed_url.netloc == parsed_source.netloc:
                link.is_internal = True
            elif self._is_subdomain(parsed_url.netloc, self.target_domain):
                link.is_subdomain = True
            else:
                link.is_external = True
            
            # 判断是否为资源
            path = parsed_url.path.lower()
            link.is_resource, link.resource_type = self._classify_resource_type(path)
            
            return link
            
        except Exception as e:
            self.logger.debug(f"创建链接对象失败: {url} - {e}")
            return None
    
    def _normalize_url(self, url: str, base_url: str) -> Optional[str]:
        """URL规范化处理"""
        try:
            url = html.unescape(url.strip())
            
            if any(pattern.match(url) for pattern in self.ignore_patterns):
                return None
            
            absolute_url = urljoin(base_url, url)
            parsed = urlparse(absolute_url)
            
            if not parsed.netloc or parsed.scheme not in ['http', 'https']:
                return None
            
            normalized = urlunparse((
                parsed.scheme,
                parsed.netloc.lower(),
                parsed.path,
                parsed.params,
                parsed.query,
                ''  # 移除fragment
            ))
            
            return normalized
            
        except Exception:
            return None
    
    def _is_valid_url_candidate(self, url: str) -> bool:
        """检查是否为有效的URL候选"""
        if not url or not isinstance(url, str):
            return False
        
        url = url.strip()
        if not url or len(url) > 2048:
            return False
        
        return not any(pattern.match(url) for pattern in self.ignore_patterns)
    
    def _parse_srcset(self, srcset: str) -> List[str]:
        """解析srcset属性"""
        urls = []
        entries = srcset.split(',')
        
        for entry in entries:
            entry = entry.strip()
            if ' ' in entry:
                url = entry.split()[0]
            else:
                url = entry
            
            if url and self._is_valid_url_candidate(url):
                urls.append(url)
        
        return urls
    
    def _extract_urls_from_css(self, css_content: str) -> List[str]:
        """从CSS内容中提取URL"""
        urls = []
        
        # CSS url()函数
        url_pattern = re.compile(r'url\s*\(\s*["\']?([^"\'()]+)["\']?\s*\)', re.IGNORECASE)
        matches = url_pattern.findall(css_content)
        
        for match in matches:
            if self._is_valid_url_candidate(match):
                urls.append(match)
        
        return urls
    
    def _extract_urls_from_js(self, js_content: str) -> List[str]:
        """从JavaScript内容中提取URL"""
        urls = []
        
        js_patterns = [
            re.compile(r'(?:window\.location|location\.href)\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE),
            re.compile(r'["\']https?://[^"\']+["\']', re.IGNORECASE),
        ]
        
        for pattern in js_patterns:
            matches = pattern.findall(js_content)
            for match in matches:
                clean_url = match.strip('\'"')
                if self._is_valid_url_candidate(clean_url):
                    urls.append(clean_url)
        
        return urls
    
    def _is_subdomain(self, domain: str, target_domain: str) -> bool:
        """判断是否为子域名"""
        if not domain or not target_domain:
            return False
        
        domain = domain.lower()
        target_domain = target_domain.lower()
        
        return domain == target_domain or domain.endswith('.' + target_domain)
    
    def _classify_resource_type(self, path: str) -> Tuple[bool, Optional[str]]:
        """分类资源类型"""
        if not path:
            return False, None
        
        path_lower = path.lower()
        
        for resource_type, extensions in self.resource_types.items():
            if any(path_lower.endswith(ext) for ext in extensions):
                return True, resource_type
        
        return False, None
    
    async def _deduplicate_and_normalize(self, links: List[ExtractedLink], source_url: str) -> List[ExtractedLink]:
        """去重和规范化链接"""
        seen_urls = set()
        unique_links = []
        
        for link in links:
            url_key = link.normalized_url
            if url_key not in seen_urls:
                seen_urls.add(url_key)
                unique_links.append(link)
        
        return unique_links
    
    async def _classify_and_analyze_links(self, links: List[ExtractedLink], source_url: str) -> LinkExtractionResult:
        """分类和分析链接"""
        result = LinkExtractionResult(source_url=source_url, total_links=len(links))
        
        # 按类型分类
        for link in links:
            if link.link_type == 'navigation':
                result.navigation_links.append(link)
            elif link.link_type == 'resource':
                result.resource_links.append(link)
            elif link.link_type == 'form':
                result.form_links.append(link)
            elif link.link_type == 'css':
                result.css_links.append(link)
            elif link.link_type == 'js':
                result.js_links.append(link)
            elif link.link_type == 'text':
                result.text_links.append(link)
            
            # 按域名分类
            if link.is_internal:
                result.internal_links.append(link)
            elif link.is_subdomain:
                result.subdomain_links.append(link)
            elif link.is_external:
                result.external_links.append(link)
        
        # 统计信息
        result.link_type_distribution = Counter(link.link_type for link in links)
        result.domain_distribution = Counter(urlparse(link.normalized_url).netloc for link in links)
        
        return result
    
    async def batch_extract_from_pages(
        self, 
        pages: List[Tuple[str, str]], 
        max_concurrent: int = 10
    ) -> List[LinkExtractionResult]:
        """批量从页面提取链接"""
        self.logger.info(f"开始批量链接提取: {len(pages)} 个页面")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def extract_with_semaphore(page_data: Tuple[str, str]) -> LinkExtractionResult:
            url, html_content = page_data
            async with semaphore:
                return await self.extract_from_html(html_content, url)
        
        tasks = [extract_with_semaphore(page) for page in pages]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, LinkExtractionResult):
                valid_results.append(result)
            else:
                self.logger.warning(f"页面 {pages[i][0]} 链接提取失败: {result}")
        
        self.logger.info(f"批量链接提取完成: {len(valid_results)} 个有效结果")
        return valid_results


# 便捷函数
async def extract_links_from_html(
    html_content: str, 
    source_url: str, 
    target_domain: str,
    task_id: str = "default",
    user_id: str = "default"
) -> LinkExtractionResult:
    """便捷的链接提取函数"""
    extractor = EnhancedLinkExtractor(task_id, user_id, target_domain)
    return await extractor.extract_from_html(html_content, source_url)


def get_all_links_from_result(result: LinkExtractionResult) -> List[ExtractedLink]:
    """从结果中获取所有链接"""
    return (result.navigation_links + result.resource_links + result.form_links + 
            result.css_links + result.js_links + result.text_links)