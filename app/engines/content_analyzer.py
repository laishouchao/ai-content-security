"""
网页内容分析器
从网页内容中提取文本、链接、脚本等信息用于AI分析

核心功能：
1. HTML结构解析和清理
2. 文本内容提取和处理
3. 元数据提取（标题、描述、关键词）
4. 链接和媒体资源分析
5. 脚本和样式内容提取
6. 表单和交互元素分析
7. SEO相关信息提取
8. 内容特征和统计信息
"""

import re
import hashlib
import asyncio
from typing import Dict, List, Set, Optional, Tuple, Any, Union
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter
import html
import json

from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from app.core.logging import TaskLogger
from app.engines.enhanced_link_extractor import EnhancedLinkExtractor, LinkExtractionResult


@dataclass
class ContentMetadata:
    """内容元数据"""
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    author: Optional[str] = None
    language: Optional[str] = None
    charset: Optional[str] = None
    
    # SEO相关
    h1_tags: List[str] = field(default_factory=list)
    h2_tags: List[str] = field(default_factory=list)
    alt_texts: List[str] = field(default_factory=list)
    
    # 社交媒体标签
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None


@dataclass
class TextContent:
    """文本内容"""
    raw_text: str = ""
    cleaned_text: str = ""
    main_content: str = ""
    
    # 文本统计
    word_count: int = 0
    char_count: int = 0
    paragraph_count: int = 0
    sentence_count: int = 0
    
    # 文本特征
    language_detected: Optional[str] = None
    reading_level: Optional[str] = None
    text_quality_score: float = 0.0


@dataclass
class ScriptContent:
    """脚本内容"""
    inline_scripts: List[str] = field(default_factory=list)
    external_scripts: List[str] = field(default_factory=list)
    script_analysis: Dict[str, Any] = field(default_factory=dict)
    
    # 安全相关
    suspicious_scripts: List[str] = field(default_factory=list)
    tracking_scripts: List[str] = field(default_factory=list)


@dataclass
class FormAnalysis:
    """表单分析"""
    form_count: int = 0
    input_types: List[str] = field(default_factory=list)
    form_actions: List[str] = field(default_factory=list)
    form_methods: List[str] = field(default_factory=list)
    
    # 敏感表单检测
    has_login_form: bool = False
    has_payment_form: bool = False
    has_personal_info_form: bool = False


@dataclass
class MediaAnalysis:
    """媒体资源分析"""
    image_count: int = 0
    video_count: int = 0
    audio_count: int = 0
    
    image_urls: List[str] = field(default_factory=list)
    video_urls: List[str] = field(default_factory=list)
    audio_urls: List[str] = field(default_factory=list)
    
    # 媒体特征
    has_adult_content_indicators: bool = False
    suspicious_media: List[str] = field(default_factory=list)


@dataclass
class ContentAnalysisResult:
    """内容分析结果"""
    url: str
    analysis_time: datetime = field(default_factory=datetime.now)
    
    # 核心内容
    metadata: ContentMetadata = field(default_factory=ContentMetadata)
    text_content: TextContent = field(default_factory=TextContent)
    script_content: ScriptContent = field(default_factory=ScriptContent)
    form_analysis: FormAnalysis = field(default_factory=FormAnalysis)
    media_analysis: MediaAnalysis = field(default_factory=MediaAnalysis)
    
    # 链接分析（来自增强链接提取器）
    link_extraction_result: Optional[LinkExtractionResult] = None
    
    # 内容特征
    content_hash: str = ""
    content_type: str = "html"
    content_size: int = 0
    
    # 风险指标
    suspicious_indicators: List[str] = field(default_factory=list)
    content_risk_score: float = 0.0
    
    # 分析状态
    analysis_success: bool = True
    error_message: Optional[str] = None


class ContentAnalyzer:
    """网页内容分析器"""
    
    def __init__(self, task_id: str, user_id: str, target_domain: str):
        self.task_id = task_id
        self.user_id = user_id
        self.target_domain = target_domain
        self.logger = TaskLogger(task_id, user_id)
        
        # 集成链接提取器
        self.link_extractor = EnhancedLinkExtractor(task_id, user_id, target_domain)
        
        # 初始化分析规则
        self._init_analysis_patterns()
    
    def _init_analysis_patterns(self):
        """初始化分析模式"""
        # 可疑脚本模式
        self.suspicious_script_patterns = [
            r'eval\s*\(',
            r'document\.write\s*\(',
            r'window\.open\s*\(',
            r'location\.href\s*=',
            r'bitcoin|crypto|mining',
            r'keylogger|malware|virus',
        ]
        
        # 追踪脚本模式
        self.tracking_script_patterns = [
            r'google-analytics\.com',
            r'googletagmanager\.com',
            r'facebook\.net/tr',
            r'doubleclick\.net',
            r'analytics|tracking|gtag',
        ]
        
        # 成人内容指标
        self.adult_content_indicators = [
            r'xxx|porn|adult|sex|nude',
            r'casino|betting|gambling',
            r'escort|massage|hookup',
        ]
        
        # 敏感表单字段
        self.sensitive_form_fields = {
            'login': ['username', 'password', 'email', 'login'],
            'payment': ['credit', 'card', 'payment', 'billing', 'cvv'],
            'personal': ['ssn', 'social', 'passport', 'id_number', 'phone']
        }
        
        # 编译正则表达式
        self.suspicious_script_regexes = [re.compile(p, re.IGNORECASE) for p in self.suspicious_script_patterns]
        self.tracking_script_regexes = [re.compile(p, re.IGNORECASE) for p in self.tracking_script_patterns]
        self.adult_content_regexes = [re.compile(p, re.IGNORECASE) for p in self.adult_content_indicators]
    
    async def analyze_content(
        self, 
        html_content: str, 
        url: str,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> ContentAnalysisResult:
        """分析网页内容"""
        try:
            start_time = datetime.now()
            
            # 创建结果对象
            result = ContentAnalysisResult(url=url)
            result.content_size = len(html_content)
            result.content_hash = hashlib.md5(html_content.encode('utf-8')).hexdigest()
            
            # 解析HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 1. 提取元数据
            result.metadata = await self._extract_metadata(soup, url)
            
            # 2. 分析文本内容
            result.text_content = await self._analyze_text_content(soup)
            
            # 3. 分析脚本内容
            result.script_content = await self._analyze_script_content(soup)
            
            # 4. 分析表单
            result.form_analysis = await self._analyze_forms(soup)
            
            # 5. 分析媒体资源
            result.media_analysis = await self._analyze_media(soup, url)
            
            # 6. 提取链接
            result.link_extraction_result = await self.link_extractor.extract_from_html(
                html_content, url
            )
            
            # 7. 风险评估
            result.suspicious_indicators = await self._detect_suspicious_content(result)
            result.content_risk_score = self._calculate_risk_score(result)
            
            result.analysis_time = datetime.now()
            
            self.logger.debug(f"内容分析完成: {url} -> 风险评分: {result.content_risk_score:.2f}")
            return result
            
        except Exception as e:
            self.logger.error(f"内容分析失败 {url}: {e}")
            return ContentAnalysisResult(
                url=url,
                analysis_success=False,
                error_message=str(e)
            )
    
    async def _extract_metadata(self, soup: BeautifulSoup, url: str) -> ContentMetadata:
        """提取页面元数据"""
        metadata = ContentMetadata()
        
        # 基本元数据
        title_tag = soup.find('title')
        metadata.title = title_tag.get_text().strip() if title_tag else None
        
        # Meta标签
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            name = meta.get('name', '').lower()
            property_attr = meta.get('property', '').lower()
            content = meta.get('content', '')
            
            if name == 'description':
                metadata.description = content
            elif name == 'keywords':
                metadata.keywords = [k.strip() for k in content.split(',')]
            elif name == 'author':
                metadata.author = content
            elif name == 'language':
                metadata.language = content
            elif property_attr == 'og:title':
                metadata.og_title = content
            elif property_attr == 'og:description':
                metadata.og_description = content
            elif property_attr == 'og:image':
                metadata.og_image = content
            elif name == 'twitter:title':
                metadata.twitter_title = content
            elif name == 'twitter:description':
                metadata.twitter_description = content
        
        # HTML lang属性
        html_tag = soup.find('html')
        if html_tag and not metadata.language and isinstance(html_tag, Tag):
            lang_attr = html_tag.get('lang')
            # 确保lang属性是字符串类型
            if isinstance(lang_attr, str):
                metadata.language = lang_attr
            elif isinstance(lang_attr, list) and lang_attr:
                # 如果返回列表，取第一个元素
                metadata.language = str(lang_attr[0])
        
        # 标题标签
        metadata.h1_tags = [h.get_text().strip() for h in soup.find_all('h1')]
        metadata.h2_tags = [h.get_text().strip() for h in soup.find_all('h2')]
        
        # Alt文本
        metadata.alt_texts = [
            img.get('alt', '').strip() for img in soup.find_all('img') 
            if img.get('alt')
        ]
        
        return metadata
    
    async def _analyze_text_content(self, soup: BeautifulSoup) -> TextContent:
        """分析文本内容"""
        text_content = TextContent()
        
        # 获取原始文本
        text_content.raw_text = soup.get_text()
        
        # 清理文本
        cleaned = re.sub(r'\s+', ' ', text_content.raw_text)
        cleaned = re.sub(r'\n+', '\n', cleaned)
        text_content.cleaned_text = cleaned.strip()
        
        # 尝试提取主要内容
        main_content_tags = soup.find_all(['article', 'main', 'div'], 
                                        class_=re.compile(r'content|main|article', re.I))
        if main_content_tags:
            main_texts = [tag.get_text() for tag in main_content_tags]
            text_content.main_content = ' '.join(main_texts)
        else:
            # 如果没有找到主要内容标签，使用body
            body = soup.find('body')
            if body:
                text_content.main_content = body.get_text()
        
        # 统计信息
        text_content.char_count = len(text_content.cleaned_text)
        text_content.word_count = len(text_content.cleaned_text.split())
        text_content.paragraph_count = len([p for p in soup.find_all('p') if p.get_text().strip()])
        text_content.sentence_count = len(re.findall(r'[.!?]+', text_content.cleaned_text))
        
        # 简单的文本质量评分
        if text_content.word_count > 0:
            avg_word_length = text_content.char_count / text_content.word_count
            text_content.text_quality_score = min(1.0, avg_word_length / 10.0)
        
        return text_content
    
    async def _analyze_script_content(self, soup: BeautifulSoup) -> ScriptContent:
        """分析脚本内容"""
        script_content = ScriptContent()
        
        script_tags = soup.find_all('script')
        
        for script in script_tags:
            # 外部脚本
            src = script.get('src')
            if src:
                script_content.external_scripts.append(src)
            
            # 内联脚本
            if script.string:
                script_text = script.string.strip()
                if script_text:
                    script_content.inline_scripts.append(script_text)
                    
                    # 检查可疑脚本
                    for pattern in self.suspicious_script_regexes:
                        if pattern.search(script_text):
                            script_content.suspicious_scripts.append(script_text[:200] + "...")
                            break
                    
                    # 检查追踪脚本
                    for pattern in self.tracking_script_regexes:
                        if pattern.search(script_text):
                            script_content.tracking_scripts.append(script_text[:100] + "...")
                            break
        
        # 脚本分析统计
        script_content.script_analysis = {
            'total_scripts': len(script_tags),
            'external_count': len(script_content.external_scripts),
            'inline_count': len(script_content.inline_scripts),
            'suspicious_count': len(script_content.suspicious_scripts),
            'tracking_count': len(script_content.tracking_scripts)
        }
        
        return script_content
    
    async def _analyze_forms(self, soup: BeautifulSoup) -> FormAnalysis:
        """分析表单"""
        form_analysis = FormAnalysis()
        
        forms = soup.find_all('form')
        form_analysis.form_count = len(forms)
        
        for form in forms:
            # 表单属性
            action = form.get('action', '')
            method = form.get('method', 'get').lower()
            
            if action:
                form_analysis.form_actions.append(action)
            form_analysis.form_methods.append(method)
            
            # 输入字段分析
            inputs = form.find_all(['input', 'textarea', 'select'])
            for input_elem in inputs:
                input_type = input_elem.get('type', 'text').lower()
                input_name = input_elem.get('name', '').lower()
                input_id = input_elem.get('id', '').lower()
                
                form_analysis.input_types.append(input_type)
                
                # 检查敏感字段
                field_text = f"{input_name} {input_id}".lower()
                
                if any(keyword in field_text for keyword in self.sensitive_form_fields['login']):
                    form_analysis.has_login_form = True
                elif any(keyword in field_text for keyword in self.sensitive_form_fields['payment']):
                    form_analysis.has_payment_form = True
                elif any(keyword in field_text for keyword in self.sensitive_form_fields['personal']):
                    form_analysis.has_personal_info_form = True
        
        return form_analysis
    
    async def _analyze_media(self, soup: BeautifulSoup, base_url: str) -> MediaAnalysis:
        """分析媒体资源"""
        media_analysis = MediaAnalysis()
        
        # 图片
        images = soup.find_all('img')
        media_analysis.image_count = len(images)
        for img in images:
            src = img.get('src')
            if src:
                full_url = urljoin(base_url, src)
                media_analysis.image_urls.append(full_url)
                
                # 检查可疑图片
                alt_text = img.get('alt', '').lower()
                src_lower = src.lower()
                if any(pattern.search(f"{alt_text} {src_lower}") for pattern in self.adult_content_regexes):
                    media_analysis.has_adult_content_indicators = True
                    media_analysis.suspicious_media.append(full_url)
        
        # 视频
        videos = soup.find_all(['video', 'source'])
        for video in videos:
            src = video.get('src')
            if src:
                full_url = urljoin(base_url, src)
                media_analysis.video_urls.append(full_url)
                media_analysis.video_count += 1
        
        # 音频
        audios = soup.find_all(['audio', 'source'])
        for audio in audios:
            src = audio.get('src')
            if src and src not in media_analysis.video_urls:  # 避免重复
                full_url = urljoin(base_url, src)
                media_analysis.audio_urls.append(full_url)
                media_analysis.audio_count += 1
        
        return media_analysis
    
    async def _detect_suspicious_content(self, result: ContentAnalysisResult) -> List[str]:
        """检测可疑内容"""
        indicators = []
        
        # 文本内容检查
        content_text = f"{result.text_content.cleaned_text} {result.metadata.title or ''} {result.metadata.description or ''}"
        for pattern in self.adult_content_regexes:
            if pattern.search(content_text):
                indicators.append(f"可疑文本内容: {pattern.pattern}")
        
        # 脚本检查
        if result.script_content.suspicious_scripts:
            indicators.append(f"发现{len(result.script_content.suspicious_scripts)}个可疑脚本")
        
        # 表单检查
        if result.form_analysis.has_payment_form and not self._is_trusted_domain(result.url):
            indicators.append("非信任域名包含支付表单")
        
        # 媒体检查
        if result.media_analysis.has_adult_content_indicators:
            indicators.append("媒体内容包含成人内容指标")
        
        # 链接检查
        if result.link_extraction_result:
            external_links = len(result.link_extraction_result.external_links)
            total_links = result.link_extraction_result.total_links
            if total_links > 0 and external_links / total_links > 0.8:
                indicators.append("外部链接比例过高")
        
        return indicators
    
    def _calculate_risk_score(self, result: ContentAnalysisResult) -> float:
        """计算内容风险评分"""
        score = 0.0
        
        # 基于可疑指标（增加权重）
        score += len(result.suspicious_indicators) * 0.25
        
        # 基于脚本分析（增加权重）
        if result.script_content.suspicious_scripts:
            score += len(result.script_content.suspicious_scripts) * 0.4
        
        # 基于表单分析
        if result.form_analysis.has_payment_form:
            score += 0.25
        if result.form_analysis.has_personal_info_form:
            score += 0.15
        
        # 基于媒体内容（增加权重）
        if result.media_analysis.has_adult_content_indicators:
            score += 0.5
        
        # 基于文本质量
        if result.text_content.text_quality_score < 0.3:
            score += 0.1
        
        return min(score, 1.0)
    
    def _is_trusted_domain(self, url: str) -> bool:
        """检查是否为信任域名"""
        trusted_domains = [
            'paypal.com', 'stripe.com', 'amazon.com', 'google.com',
            'microsoft.com', 'apple.com', 'shopify.com'
        ]
        
        domain = urlparse(url).netloc.lower()
        return any(trusted in domain for trusted in trusted_domains)
    
    async def analyze_batch_content(
        self, 
        content_list: List[Tuple[str, str]], 
        max_concurrent: int = 10
    ) -> List[ContentAnalysisResult]:
        """批量分析内容"""
        self.logger.info(f"开始批量内容分析: {len(content_list)} 个页面")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def analyze_with_semaphore(content_data: Tuple[str, str]) -> ContentAnalysisResult:
            url, html_content = content_data
            async with semaphore:
                return await self.analyze_content(html_content, url)
        
        tasks = [analyze_with_semaphore(content) for content in content_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, ContentAnalysisResult):
                valid_results.append(result)
            else:
                self.logger.warning(f"内容分析失败 {content_list[i][0]}: {result}")
        
        self.logger.info(f"批量内容分析完成: {len(valid_results)} 个有效结果")
        return valid_results


# 便捷函数
async def analyze_web_content(
    html_content: str,
    url: str,
    target_domain: str,
    task_id: str = "default",
    user_id: str = "default"
) -> ContentAnalysisResult:
    """便捷的网页内容分析函数"""
    analyzer = ContentAnalyzer(task_id, user_id, target_domain)
    return await analyzer.analyze_content(html_content, url)


def extract_ai_analysis_data(result: ContentAnalysisResult) -> Dict[str, Any]:
    """从分析结果中提取AI分析所需的数据"""
    return {
        'url': result.url,
        'title': result.metadata.title,
        'description': result.metadata.description,
        'main_content': result.text_content.main_content[:5000],  # 限制长度
        'keywords': result.metadata.keywords,
        'h1_tags': result.metadata.h1_tags,
        'suspicious_indicators': result.suspicious_indicators,
        'content_risk_score': result.content_risk_score,
        'has_forms': result.form_analysis.form_count > 0,
        'has_payment_form': result.form_analysis.has_payment_form,
        'media_count': {
            'images': result.media_analysis.image_count,
            'videos': result.media_analysis.video_count
        },
        'external_links_count': len(result.link_extraction_result.external_links) if result.link_extraction_result else 0
    }