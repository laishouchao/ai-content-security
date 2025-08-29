"""
第三方域名分析引擎
实现访问测试、内容抓取和AI分类
"""

import asyncio
import aiohttp
import json
import time
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict, field
from urllib.parse import urlparse
from pathlib import Path
import tempfile
import base64

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from app.core.logging import TaskLogger
from app.core.config import settings
from app.engines.ai_analysis import AIAnalysisEngine
from app.engines.screenshot_engine import UniversalScreenshotEngine, ScreenshotConfig


@dataclass
class ThirdPartyDomainResult:
    """第三方域名分析结果"""
    domain: str
    source_urls: List[str]
    discovered_at: datetime
    
    # 访问测试结果
    is_accessible: bool = False
    response_code: Optional[int] = None
    response_time: float = 0.0
    final_url: Optional[str] = None
    server_info: Optional[str] = None
    
    # 内容抓取结果
    page_title: Optional[str] = None
    page_description: Optional[str] = None
    page_content: Optional[str] = None
    screenshot_path: Optional[str] = None
    content_hash: Optional[str] = None
    
    # AI分析结果
    domain_type: Optional[str] = None
    risk_level: Optional[str] = None
    confidence_score: float = 0.0
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    ai_analysis_result: Optional[Dict[str, Any]] = None
    
    # 错误信息
    error_message: Optional[str] = None
    analysis_error: Optional[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class DomainAccessTester:
    """域名访问测试器"""
    
    def __init__(self):
        self.timeout = 30
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    
    async def test_domain_access(self, domain: str) -> Dict[str, Any]:
        """测试域名可访问性"""
        start_time = time.time()
        
        # 尝试 HTTPS 和 HTTP
        for protocol in ['https', 'http']:
            url = f"{protocol}://{domain}"
            try:
                result = await self._test_url_access(url)
                if result['accessible']:
                    result['response_time'] = time.time() - start_time
                    result['protocol_used'] = protocol
                    return result
            except Exception as e:
                continue
        
        return {
            'accessible': False,
            'status_code': None,
            'response_time': time.time() - start_time,
            'error': '无法访问域名',
            'protocol_used': None
        }
    
    async def _test_url_access(self, url: str) -> Dict[str, Any]:
        """测试单个URL访问"""
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        connector = aiohttp.TCPConnector(ssl=False, limit=10)
        
        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={'User-Agent': self.user_agent}
        ) as session:
            
            async with session.get(url, allow_redirects=True) as response:
                return {
                    'accessible': True,
                    'status_code': response.status,
                    'final_url': str(response.url),
                    'server_info': response.headers.get('Server', ''),
                    'content_type': response.headers.get('Content-Type', ''),
                    'content_length': response.headers.get('Content-Length', '0')
                }


class EnhancedDomainContentCapturer:
    """增强的域名内容抓取器，使用统一截图引擎"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.screenshot_dir = Path(f"screenshots/{task_id}")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化截图引擎
        self.screenshot_engine = UniversalScreenshotEngine(task_id, user_id)
        self.screenshot_config = ScreenshotConfig(
            width=1280,
            height=720,
            full_page=False,
            quality=90,
            timeout=30,
            wait_time=3.0,
            retry_count=2
        )
        
        self._engine_initialized = False
        
    async def _ensure_engine_initialized(self):
        """确保截图引擎已初始化"""
        if not self._engine_initialized:
            await self.screenshot_engine.initialize(self.screenshot_config)
            self._engine_initialized = True
    
    async def capture_domain_content(self, domain: str, protocol: str = 'https') -> Dict[str, Any]:
        """使用增强截图引擎抓取域名内容和截图"""
        url = f"{protocol}://{domain}"
        
        try:
            # 确保截图引擎已初始化
            await self._ensure_engine_initialized()
            
            # 生成截图文件名
            screenshot_filename = f"{domain.replace('.', '_')}_{int(time.time())}.png"
            screenshot_path = self.screenshot_dir / screenshot_filename
            
            # 使用统一截图引擎进行截图
            screenshot_result = await self.screenshot_engine.capture_screenshot(
                url, 
                self.screenshot_config, 
                str(screenshot_path)
            )
            
            if screenshot_result.success:
                # 提取页面内容信息
                page_title = screenshot_result.page_title or ''
                page_content = await self._extract_page_content(url)
                
                # 计算内容哈希
                content_hash = hashlib.md5(page_content.encode('utf-8')).hexdigest()
                
                return {
                    'title': page_title,
                    'description': page_content[:200] if page_content else '',  # 前200字符作为描述
                    'content': page_content,
                    'screenshot_path': str(screenshot_path),
                    'content_hash': content_hash,
                    'success': True,
                    'file_size': screenshot_result.file_size,
                    'response_time': screenshot_result.response_time,
                    'final_url': screenshot_result.page_url
                }
            else:
                return {
                    'success': False, 
                    'error': f'截图失败: {screenshot_result.error_message}'
                }
                
        except Exception as e:
            return {'success': False, 'error': f'抓取失败: {str(e)}'}
    
    async def _extract_page_content(self, url: str) -> str:
        """使用HTTP请求提取页面文本内容"""
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            connector = aiohttp.TCPConnector(ssl=False, limit=10)
            
            async with aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={'User-Agent': self.screenshot_config.user_agent}
            ) as session:
                
                async with session.get(url, allow_redirects=True) as response:
                    if response.status == 200 and 'text/html' in response.headers.get('Content-Type', ''):
                        html_content = await response.text()
                        
                        # 简单的HTML文本提取
                        import re
                        # 移除script和style标签
                        clean_html = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
                        clean_html = re.sub(r'<style[^>]*>.*?</style>', '', clean_html, flags=re.DOTALL | re.IGNORECASE)
                        # 移除HTML标签
                        text_content = re.sub(r'<[^>]+>', '', clean_html)
                        # 清理多余空白
                        text_content = re.sub(r'\s+', ' ', text_content).strip()
                        
                        return text_content[:2000]  # 限制在2000字符内
                    else:
                        return ''
        except Exception as e:
            return f'内容提取失败: {str(e)}'
    
    async def cleanup(self):
        """清理资源"""
        try:
            await self.screenshot_engine.cleanup()
        except Exception as e:
            pass  # 忽略清理错误


class ThirdPartyDomainClassifier:
    """第三方域名AI分类器"""
    
    def __init__(self, ai_engine: AIAnalysisEngine):
        self.ai_engine = ai_engine
        self.classification_prompt = self._build_classification_prompt()
    
    def _build_classification_prompt(self) -> str:
        """构建AI分类提示词"""
        return """你是一个专业的网络安全分析师，需要对第三方域名进行分类和风险评估。

请根据提供的域名信息（包括域名、页面标题、页面描述、页面内容截图），对域名进行分析并返回JSON格式的结果。

分类类型 (domain_type)：
- cdn: 内容分发网络
- analytics: 分析统计服务
- advertising: 广告服务
- social: 社交媒体
- api: API服务
- payment: 支付服务
- security: 安全服务
- maps: 地图位置服务
- email: 邮件服务
- cloud: 云服务
- unknown: 未知类型

风险等级 (risk_level)：
- low: 低风险 - 正常的第三方服务
- medium: 中风险 - 需要关注的服务
- high: 高风险 - 可能存在安全风险
- critical: 严重风险 - 明确的恶意或违规内容

请返回以下JSON格式：
{
    "domain_type": "分类类型",
    "risk_level": "风险等级", 
    "confidence": 0.85,
    "description": "详细描述该域名的用途和特征",
    "tags": ["标签1", "标签2"],
    "reasoning": "分析推理过程"
}

请确保返回的是有效的JSON格式，confidence为0-1之间的浮点数。"""

    async def classify_domain(self, domain: str, content_info: Dict[str, Any], screenshot_path: Optional[str] = None) -> Dict[str, Any]:
        """使用AI对域名进行分类"""
        try:
            # 构建分析内容
            analysis_content = f"""域名: {domain}
页面标题: {content_info.get('title', 'N/A')}
页面描述: {content_info.get('description', 'N/A')}
页面内容摘要: {content_info.get('content', 'N/A')[:500]}...
"""
            
            # 准备图片（如果有截图）
            image_data = ""
            if screenshot_path and Path(screenshot_path).exists():
                with open(screenshot_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
            
            # 调用AI分析
            from app.engines.ai_analysis import OpenAIClient
            async with OpenAIClient(self.ai_engine.ai_config, self.ai_engine.logger) as client:
                ai_result = await client.analyze_content(
                    prompt=f"{self.classification_prompt}\n\n{analysis_content}",
                    image_data=image_data
                )
            
            if ai_result and 'choices' in ai_result and ai_result['choices']:
                # 提取AI响应内容
                content = ai_result['choices'][0]['message']['content']
                try:
                    classification_result = json.loads(content)
                except json.JSONDecodeError:
                    # 如果不是标准JSON，尝试提取JSON部分
                    import re
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        try:
                            classification_result = json.loads(json_match.group())
                        except json.JSONDecodeError as e:
                            return {
                                'success': False,
                                'error': f'AI返回格式解析失败: {e}',
                                'ai_raw_result': ai_result
                            }
                    else:
                        return {
                            'success': False,
                            'error': 'AI返回中未找到有效JSON格式',
                            'ai_raw_result': ai_result
                        }
                
                # 验证结果格式
                required_fields = ['domain_type', 'risk_level', 'confidence', 'description']
                for field in required_fields:
                    if field not in classification_result:
                        classification_result[field] = 'unknown' if field != 'confidence' else 0.0
                
                # 确保confidence在有效范围内
                confidence = classification_result.get('confidence', 0.0)
                if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
                    classification_result['confidence'] = 0.5
                
                return {
                    'success': True,
                    'classification': classification_result,
                    'ai_raw_result': ai_result
                }
            else:
                return {
                    'success': False,
                    'error': 'AI分析失败：无有效响应',
                    'ai_raw_result': ai_result
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'域名分类异常: {str(e)}'
            }


class ThirdPartyDomainAnalyzer:
    """第三方域名分析引擎主类"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        # 初始化组件
        self.access_tester = DomainAccessTester()
        self.content_capturer = EnhancedDomainContentCapturer(task_id, user_id)
        
        # AI分析引擎（延迟初始化）
        self.ai_classifier: Optional[ThirdPartyDomainClassifier] = None
        
    async def analyze_domain(self, domain: str, source_urls: List[str]) -> ThirdPartyDomainResult:
        """对第三方域名进行全面分析"""
        result = ThirdPartyDomainResult(
            domain=domain,
            source_urls=source_urls,
            discovered_at=datetime.utcnow()
        )
        
        try:
            self.logger.info(f"开始分析第三方域名: {domain}")
            
            # 步骤1: 访问测试
            access_result = await self.access_tester.test_domain_access(domain)
            result.is_accessible = access_result['accessible']
            result.response_code = access_result.get('status_code')
            result.response_time = access_result.get('response_time', 0.0)
            result.final_url = access_result.get('final_url')
            result.server_info = access_result.get('server_info')
            
            if not result.is_accessible:
                result.error_message = access_result.get('error', '域名无法访问')
                self.logger.warning(f"域名 {domain} 无法访问: {result.error_message}")
                return result
            
            # 步骤2: 内容抓取
            protocol = access_result.get('protocol_used', 'https')
            content_result = await self.content_capturer.capture_domain_content(domain, protocol)
            
            if content_result.get('success'):
                result.page_title = content_result.get('title')
                result.page_description = content_result.get('description')
                result.page_content = content_result.get('content')
                result.screenshot_path = content_result.get('screenshot_path')
                result.content_hash = content_result.get('content_hash')
            else:
                result.error_message = content_result.get('error', '内容抓取失败')
                self.logger.warning(f"域名 {domain} 内容抓取失败: {result.error_message}")
                return result
            
            # 步骤3: AI分类（如果有AI引擎）
            if await self._ensure_ai_classifier() and self.ai_classifier is not None:
                classification_result = await self.ai_classifier.classify_domain(
                    domain, content_result, result.screenshot_path
                )
                
                if classification_result.get('success'):
                    classification = classification_result['classification']
                    result.domain_type = classification.get('domain_type', 'unknown')
                    result.risk_level = classification.get('risk_level', 'low')
                    result.confidence_score = classification.get('confidence', 0.0)
                    result.description = classification.get('description', '')
                    result.tags = classification.get('tags', [])
                    result.ai_analysis_result = classification_result.get('ai_raw_result')
                else:
                    result.analysis_error = classification_result.get('error', 'AI分析失败')
                    self.logger.warning(f"域名 {domain} AI分析失败: {result.analysis_error}")
            
            self.logger.info(f"域名 {domain} 分析完成")
            return result
            
        except Exception as e:
            result.error_message = f"分析异常: {str(e)}"
            self.logger.error(f"域名 {domain} 分析异常: {e}")
            return result
    
    async def batch_analyze_domains(self, domain_info_list: List[Dict[str, Any]], batch_size: int = 10) -> List[ThirdPartyDomainResult]:
        """批量分析第三方域名"""
        results = []
        
        # 分批处理
        for i in range(0, len(domain_info_list), batch_size):
            batch = domain_info_list[i:i + batch_size]
            self.logger.info(f"处理第 {i//batch_size + 1} 批域名，共 {len(batch)} 个")
            
            # 并发分析当前批次
            tasks = []
            for domain_info in batch:
                domain = domain_info['domain']
                source_urls = domain_info.get('source_urls', [])
                tasks.append(self.analyze_domain(domain, source_urls))
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    self.logger.error(f"域名分析异常: {result}")
                    # 创建错误结果
                    domain_info = batch[j]
                    error_result = ThirdPartyDomainResult(
                        domain=domain_info['domain'],
                        source_urls=domain_info.get('source_urls', []),
                        discovered_at=datetime.utcnow(),
                        error_message=str(result)
                    )
                    results.append(error_result)
                else:
                    results.append(result)
        
        self.logger.info(f"批量分析完成，共处理 {len(results)} 个域名")
        return results
    
    async def _ensure_ai_classifier(self) -> bool:
        """确保AI分类器已初始化"""
        if self.ai_classifier is None:
            try:
                # 使用简单的AI配置
                from app.core.config import settings
                from app.models.user import UserAIConfig
                
                # 创建默认AI配置
                default_config = getattr(settings, 'DEFAULT_AI_CONFIG', {})
                ai_config = UserAIConfig(
                    openai_api_key=default_config.get('openai_api_key', ''),
                    openai_base_url=default_config.get('openai_base_url', ''),
                    ai_model_name=default_config.get('ai_model_name', 'gpt-4'),
                    has_valid_config=True
                )
                
                ai_engine = AIAnalysisEngine(self.task_id, ai_config)
                self.ai_classifier = ThirdPartyDomainClassifier(ai_engine)
                return True
            except Exception as e:
                self.logger.warning(f"AI分类器初始化失败: {e}")
                return False
        return True
    
    async def cleanup(self):
        """清理所有资源"""
        try:
            await self.content_capturer.cleanup()
            self.logger.info("第三方域名分析器资源清理完成")
        except Exception as e:
            self.logger.warning(f"清理第三方域名分析器资源失败: {e}")