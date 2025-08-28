"""
无限迭代爬虫AI分析引擎
专门为无限迭代爬虫设计的AI内容分析引擎

核心功能：
1. 集成OpenAI API进行域名内容分析
2. 支持预设提示词和回复格式
3. 批量域名内容分析和风险识别
4. 智能缓存和结果处理
5. 性能优化和错误处理

基于CSDN文章3的AI识别需求实现
"""

import asyncio
import aiohttp
import json
import time
import base64
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import ssl
import re

from app.core.logging import TaskLogger
from app.engines.advanced_prompt_system import (
    EnhancedPromptManager,
    AnalysisType,
    PromptContext,
    create_prompt_context
)


@dataclass
class AIAnalysisConfig:
    """AI分析配置"""
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4-vision-preview"
    max_tokens: int = 1500
    temperature: float = 0.3
    timeout: int = 60
    max_retries: int = 3
    max_concurrent: int = 5
    
    # 启用功能
    enable_screenshot_analysis: bool = True
    enable_content_analysis: bool = True
    enable_risk_assessment: bool = True
    enable_caching: bool = True


@dataclass
class DomainAnalysisRequest:
    """域名分析请求"""
    domain: str
    page_title: Optional[str] = None
    page_description: Optional[str] = None
    page_content: Optional[str] = None
    screenshot_path: Optional[str] = None
    source_urls: List[str] = field(default_factory=list)
    discovery_method: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIAnalysisResult:
    """AI分析结果"""
    domain: str
    analysis_success: bool
    analysis_timestamp: datetime
    processing_time: float
    
    # 域名分类结果
    domain_category: str = "unknown"  # 'cdn', 'analytics', 'advertising', 'social', 'api', etc.
    risk_level: str = "low"  # 'low', 'medium', 'high', 'critical'
    confidence_score: float = 0.0
    
    # 内容分析结果
    content_type: str = "unknown"
    has_violations: bool = False
    violation_types: List[str] = field(default_factory=list)
    violation_details: str = ""
    
    # AI原始响应
    ai_raw_response: str = ""
    analysis_prompt_used: str = ""
    
    # 错误信息
    error_message: Optional[str] = None
    retry_count: int = 0


class DomainAIPromptBuilder:
    """域名AI分析提示词构建器"""
    
    def __init__(self):
        self.system_prompt = self._build_system_prompt()
        self.analysis_template = self._build_analysis_template()
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专业的网络安全和域名分析专家。你需要分析第三方域名的内容、功能和风险等级。

请根据提供的域名信息（包括域名名称、页面标题、页面描述、页面内容、截图），对域名进行全面分析。

分析重点：
1. 域名功能分类和用途识别
2. 内容安全性和合规性评估
3. 潜在风险和威胁识别
4. 业务类型和服务性质判断

请保持客观、准确的分析，避免误报和漏报。"""
    
    def _build_analysis_template(self) -> str:
        """构建分析模板"""
        return """请分析以下第三方域名：

域名: {domain}
页面标题: {title}
页面描述: {description}
发现来源: {source_urls}
发现方法: {discovery_method}

页面内容摘要:
{content_snippet}

请按照以下JSON格式返回分析结果：

{{
    "domain_category": "域名类型（选择一个）: cdn, analytics, advertising, social, api, payment, security, maps, email, cloud, media, ecommerce, government, education, news, blog, forum, unknown",
    "risk_level": "风险等级: low, medium, high, critical",
    "confidence_score": 0.85,
    "content_type": "内容类型: business, personal, service, platform, resource, malicious, unknown",
    "has_violations": false,
    "violation_types": ["如果有违规，列出类型"],
    "violation_details": "违规详细说明（如果有）",
    "functional_analysis": {{
        "primary_purpose": "主要功能描述",
        "service_type": "服务类型",
        "target_audience": "目标用户群",
        "business_model": "商业模式（如适用）"
    }},
    "security_assessment": {{
        "data_collection": "是否收集用户数据",
        "privacy_concern": "隐私关注点",
        "security_features": ["安全特性列表"],
        "potential_risks": ["潜在风险列表"]
    }},
    "recommendations": {{
        "action_required": "建议采取的行动: allow, monitor, block, investigate",
        "monitoring_frequency": "建议监控频率: daily, weekly, monthly, none",
        "specific_concerns": ["具体关注点"],
        "mitigation_steps": ["缓解措施建议"]
    }},
    "reasoning": "详细分析推理过程和判断依据"
}}

请确保返回的是有效的JSON格式，所有字段都要填写。confidence_score为0-1之间的浮点数。"""
    
    def build_domain_analysis_prompt(self, request: DomainAnalysisRequest) -> str:
        """构建域名分析提示词"""
        # 准备内容摘要
        content_snippet = ""
        if request.page_content:
            # 截取前1000个字符作为摘要
            content_snippet = request.page_content[:1000]
            if len(request.page_content) > 1000:
                content_snippet += "..."
        else:
            content_snippet = "（无页面内容）"
        
        # 格式化提示词
        prompt = self.analysis_template.format(
            domain=request.domain,
            title=request.page_title or "（无标题）",
            description=request.page_description or "（无描述）",
            source_urls=", ".join(request.source_urls[:5]) if request.source_urls else "（未知）",
            discovery_method=request.discovery_method,
            content_snippet=content_snippet
        )
        
        return prompt


class InfiniteCrawlerAIEngine:
    """无限迭代爬虫AI分析引擎"""
    
    def __init__(self, task_id: str, user_id: str, config: AIAnalysisConfig):
        self.task_id = task_id
        self.user_id = user_id
        self.config = config
        self.logger = TaskLogger(task_id, user_id)
        
        # 初始化组件
        self.prompt_builder = DomainAIPromptBuilder()
        self.enhanced_prompt_manager = EnhancedPromptManager(task_id, user_id)
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 缓存管理
        self.analysis_cache: Dict[str, AIAnalysisResult] = {}
        self.cache_expiry: Dict[str, datetime] = {}
        self.cache_ttl = timedelta(hours=24)  # 缓存24小时
        
        # 性能统计
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'total_processing_time': 0.0,
            'average_processing_time': 0.0,
            'api_calls_made': 0,
            'tokens_used': 0
        }
        
        # 并发控制
        self.semaphore = asyncio.Semaphore(config.max_concurrent)
        self.rate_limiter = asyncio.Semaphore(config.max_concurrent)
        
        self._session_initialized = False
    
    async def initialize(self):
        """初始化AI引擎"""
        if self._session_initialized:
            return
        
        # 创建HTTP会话
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        connector = aiohttp.TCPConnector(
            ssl=ssl.create_default_context(),
            limit=self.config.max_concurrent,
            enable_cleanup_closed=True
        )
        
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={
                'Authorization': f'Bearer {self.config.api_key}',
                'Content-Type': 'application/json'
            }
        )
        
        self._session_initialized = True
        self.logger.info("AI分析引擎初始化完成")
    
    async def analyze_domains_batch(
        self, 
        requests: List[DomainAnalysisRequest]
    ) -> List[AIAnalysisResult]:
        """批量分析域名"""
        if not self._session_initialized:
            await self.initialize()
        
        self.logger.info(f"开始批量AI分析: {len(requests)} 个域名")
        start_time = time.time()
        
        # 过滤已缓存的结果
        uncached_requests = []
        cached_results = []
        
        for request in requests:
            cache_key = self._generate_cache_key(request)
            cached_result = self._get_cached_result(cache_key)
            
            if cached_result:
                self.stats['cache_hits'] += 1
                cached_results.append(cached_result)
                self.logger.debug(f"使用缓存结果: {request.domain}")
            else:
                self.stats['cache_misses'] += 1
                uncached_requests.append(request)
        
        # 并发分析未缓存的请求
        analysis_results = []
        if uncached_requests:
            tasks = []
            for request in uncached_requests:
                task = self._analyze_single_domain(request)
                tasks.append(task)
            
            # 执行分析任务
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, AIAnalysisResult):
                    analysis_results.append(result)
                    # 缓存结果
                    if self.config.enable_caching:
                        cache_key = self._generate_cache_key_from_result(result)
                        self._cache_result(cache_key, result)
                elif isinstance(result, Exception):
                    self.logger.error(f"域名分析异常: {result}")
                    self.stats['failed_requests'] += 1
        
        # 合并结果
        all_results = cached_results + analysis_results
        
        # 更新统计
        total_time = time.time() - start_time
        self.stats['total_processing_time'] += total_time
        self.stats['total_requests'] += len(requests)
        if self.stats['total_requests'] > 0:
            self.stats['average_processing_time'] = (
                self.stats['total_processing_time'] / self.stats['total_requests']
            )
        
        self.logger.info(f"批量AI分析完成: {len(all_results)} 个结果，耗时 {total_time:.2f}秒")
        return all_results
    
    async def _analyze_single_domain(self, request: DomainAnalysisRequest) -> AIAnalysisResult:
        """分析单个域名"""
        async with self.semaphore:
            start_time = time.time()
            result = AIAnalysisResult(
                domain=request.domain,
                analysis_success=False,
                analysis_timestamp=datetime.utcnow(),
                processing_time=0.0
            )
            
            try:
                # 使用增强的提示词系统构建分析提示词
                prompt_context = create_prompt_context(
                    domain=request.domain,
                    page_title=request.page_title,
                    page_content=request.page_content,
                    screenshot_path=request.screenshot_path,
                    source_urls=request.source_urls,
                    discovery_method=request.discovery_method
                )
                
                # 生成优化的提示词
                prompt_result = await self.enhanced_prompt_manager.generate_analysis_prompt(
                    prompt_context,
                    AnalysisType.COMPREHENSIVE
                )
                
                result.analysis_prompt_used = prompt_result.user_prompt
                
                # 准备API请求
                api_response = await self._call_openai_api_enhanced(
                    prompt_result.system_prompt,
                    prompt_result.user_prompt,
                    request.screenshot_path
                )
                
                if api_response:
                    # 解析AI响应
                    parsed_result = self._parse_ai_response(api_response, result)
                    if parsed_result:
                        result = parsed_result
                        result.analysis_success = True
                        self.stats['successful_requests'] += 1
                    else:
                        result.error_message = "AI响应解析失败"
                        self.stats['failed_requests'] += 1
                else:
                    result.error_message = "API调用失败"
                    self.stats['failed_requests'] += 1
            
            except Exception as e:
                result.error_message = str(e)
                self.stats['failed_requests'] += 1
                self.logger.error(f"域名 {request.domain} 分析失败: {e}")
            
            finally:
                result.processing_time = time.time() - start_time
            
            return result
    
    async def _call_openai_api(
        self, 
        prompt: str, 
        screenshot_path: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """调用OpenAI API"""
        if not self.session:
            raise RuntimeError("会话未初始化")
        
        # 构建消息
        messages = [
            {
                "role": "system",
                "content": self.prompt_builder.system_prompt
            },
            {
                "role": "user",
                "content": []
            }
        ]
        
        # 添加文本内容
        messages[1]["content"].append({
            "type": "text",
            "text": prompt
        })
        
        # 添加截图（如果有）
        if screenshot_path and Path(screenshot_path).exists():
            try:
                with open(screenshot_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                
                messages[1]["content"].append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_data}",
                        "detail": "low"  # 使用低细节以节省token
                    }
                })
            except Exception as e:
                self.logger.warning(f"读取截图失败: {e}")
        
        # 构建请求数据
        request_data = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature
        }
        
        # 重试机制
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                async with self.rate_limiter:
                    async with self.session.post(
                        f"{self.config.base_url}/chat/completions",
                        json=request_data
                    ) as response:
                        
                        if response.status == 200:
                            api_response = await response.json()
                            self.stats['api_calls_made'] += 1
                            
                            # 记录token使用量
                            if 'usage' in api_response:
                                self.stats['tokens_used'] += api_response['usage'].get('total_tokens', 0)
                            
                            return api_response
                        else:
                            error_text = await response.text()
                            raise aiohttp.ClientResponseError(
                                request_info=response.request_info,
                                history=response.history,
                                status=response.status,
                                message=f"API错误: {error_text}"
                            )
            
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries:
                    wait_time = (2 ** attempt) + 1  # 指数退避
                    self.logger.warning(f"API调用失败 (尝试 {attempt + 1}/{self.config.max_retries + 1}): {e}, {wait_time}秒后重试")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"API调用最终失败: {e}")
        
        return None
    
    async def _call_openai_api_enhanced(
        self, 
        system_prompt: str,
        user_prompt: str,
        screenshot_path: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """增强的OpenAI API调用，支持系统提示词和用户提示词分离"""
        if not self.session:
            raise RuntimeError("会话未初始化")
        
        # 构建消息
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": []
            }
        ]
        
        # 添加文本内容
        messages[1]["content"].append({
            "type": "text",
            "text": user_prompt
        })
        
        # 添加截图（如果有）
        if screenshot_path and Path(screenshot_path).exists():
            try:
                with open(screenshot_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                
                messages[1]["content"].append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_data}",
                        "detail": "low"  # 使用低细节以节省token
                    }
                })
            except Exception as e:
                self.logger.warning(f"读取截图失败: {e}")
        
        # 构建请求数据
        request_data = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature
        }
        
        # 重试机制
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                async with self.rate_limiter:
                    async with self.session.post(
                        f"{self.config.base_url}/chat/completions",
                        json=request_data
                    ) as response:
                        
                        if response.status == 200:
                            api_response = await response.json()
                            self.stats['api_calls_made'] += 1
                            
                            # 记录token使用量
                            if 'usage' in api_response:
                                self.stats['tokens_used'] += api_response['usage'].get('total_tokens', 0)
                            
                            return api_response
                        else:
                            error_text = await response.text()
                            raise aiohttp.ClientResponseError(
                                request_info=response.request_info,
                                history=response.history,
                                status=response.status,
                                message=f"API错误: {error_text}"
                            )
            
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries:
                    wait_time = (2 ** attempt) + 1  # 指数退避
                    self.logger.warning(f"API调用失败 (尝试 {attempt + 1}/{self.config.max_retries + 1}): {e}, {wait_time}秒后重试")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"API调用最终失败: {e}")
        
        return None
    
    def _parse_ai_response(
        self, 
        api_response: Dict[str, Any], 
        result: AIAnalysisResult
    ) -> Optional[AIAnalysisResult]:
        """解析AI响应"""
        try:
            # 提取AI回复内容
            content = api_response['choices'][0]['message']['content']
            result.ai_raw_response = content
            
            # 提取JSON部分
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if not json_match:
                result.error_message = "AI响应中未找到JSON格式"
                return None
            
            # 解析JSON
            analysis_data = json.loads(json_match.group(0))
            
            # 填充结果
            result.domain_category = analysis_data.get('domain_category', 'unknown')
            result.risk_level = analysis_data.get('risk_level', 'low')
            result.confidence_score = float(analysis_data.get('confidence_score', 0.0))
            result.content_type = analysis_data.get('content_type', 'unknown')
            result.has_violations = bool(analysis_data.get('has_violations', False))
            result.violation_types = analysis_data.get('violation_types', [])
            result.violation_details = analysis_data.get('violation_details', '')
            
            return result
            
        except json.JSONDecodeError as e:
            result.error_message = f"JSON解析失败: {e}"
            return None
        except Exception as e:
            result.error_message = f"响应解析异常: {e}"
            return None
    
    def _generate_cache_key(self, request: DomainAnalysisRequest) -> str:
        """生成缓存键"""
        # 使用域名和内容哈希作为缓存键
        content_hash = ""
        if request.page_content:
            content_hash = hashlib.md5(request.page_content.encode('utf-8')).hexdigest()[:8]
        
        cache_key = f"{request.domain}_{content_hash}"
        return cache_key
    
    def _generate_cache_key_from_result(self, result: AIAnalysisResult) -> str:
        """从结果生成缓存键"""
        return f"{result.domain}_{result.analysis_timestamp.strftime('%Y%m%d')}"
    
    def _get_cached_result(self, cache_key: str) -> Optional[AIAnalysisResult]:
        """获取缓存结果"""
        if not self.config.enable_caching:
            return None
        
        if cache_key in self.analysis_cache:
            # 检查缓存是否过期
            if cache_key in self.cache_expiry:
                if datetime.utcnow() > self.cache_expiry[cache_key]:
                    # 缓存过期，删除
                    del self.analysis_cache[cache_key]
                    del self.cache_expiry[cache_key]
                    return None
            
            return self.analysis_cache[cache_key]
        
        return None
    
    def _cache_result(self, cache_key: str, result: AIAnalysisResult):
        """缓存结果"""
        if self.config.enable_caching:
            self.analysis_cache[cache_key] = result
            self.cache_expiry[cache_key] = datetime.utcnow() + self.cache_ttl
    
    def get_analysis_statistics(self) -> Dict[str, Any]:
        """获取分析统计信息"""
        cache_hit_rate = 0.0
        if self.stats['cache_hits'] + self.stats['cache_misses'] > 0:
            cache_hit_rate = self.stats['cache_hits'] / (self.stats['cache_hits'] + self.stats['cache_misses'])
        
        return {
            **self.stats,
            'cache_hit_rate': cache_hit_rate,
            'cache_size': len(self.analysis_cache),
            'success_rate': self.stats['successful_requests'] / max(self.stats['total_requests'], 1)
        }
    
    async def cleanup(self):
        """清理资源"""
        if self.session:
            await self.session.close()
            self.session = None
        
        # 清理提示词管理器缓存
        if hasattr(self, 'enhanced_prompt_manager'):
            self.enhanced_prompt_manager.clear_cache()
        
        self._session_initialized = False
        self.logger.info("AI分析引擎资源清理完成")


# 便捷函数
async def create_ai_analysis_config_from_database(user_id: str) -> Optional[AIAnalysisConfig]:
    """从数据库中创建AI配置"""
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.user import UserAIConfig
        from sqlalchemy import select
        
        async with AsyncSessionLocal() as db:
            # 查询用户AI配置
            stmt = select(UserAIConfig).where(UserAIConfig.user_id == user_id)
            result = await db.execute(stmt)
            user_ai_config = result.scalar_one_or_none()
            
            if not user_ai_config or not user_ai_config.has_valid_config:
                # 如果没有配置或配置无效，尝试使用系统默认配置
                from app.models.setting import Setting
                
                # 查询系统默认AI配置
                ai_settings = {}
                default_settings = [
                    'openai_api_key', 'openai_base_url', 'ai_model_name',
                    'openai_max_tokens', 'openai_temperature', 'openai_timeout'
                ]
                
                for setting_key in default_settings:
                    setting_stmt = select(Setting).where(Setting.key == setting_key)
                    setting_result = await db.execute(setting_stmt)
                    setting = setting_result.scalar_one_or_none()
                    if setting and setting.value:
                        ai_settings[setting_key] = setting.value
                
                # 检查必要的配置项
                if not ai_settings.get('openai_api_key') or not ai_settings.get('openai_base_url'):
                    return None
                
                config = AIAnalysisConfig(
                    api_key=ai_settings['openai_api_key'],
                    base_url=ai_settings.get('openai_base_url', 'https://api.openai.com/v1'),
                    model=ai_settings.get('ai_model_name', 'gpt-4-vision-preview'),
                    max_tokens=int(ai_settings.get('openai_max_tokens', '1500')),
                    temperature=float(ai_settings.get('openai_temperature', '0.3')),
                    timeout=int(ai_settings.get('openai_timeout', '60'))
                )
            else:
                # 使用用户自定义配置
                config = AIAnalysisConfig(
                    api_key=str(user_ai_config.openai_api_key),
                    base_url=str(user_ai_config.openai_base_url or 'https://api.openai.com/v1'),
                    model=str(user_ai_config.ai_model_name or 'gpt-4-vision-preview'),
                    max_tokens=int(user_ai_config.openai_max_tokens or 1500),
                    temperature=float(user_ai_config.openai_temperature or 0.3),
                    timeout=60
                )
            
            return config
            
    except Exception as e:
        print(f"从数据库加载AI配置失败: {e}")
        return None


async def create_ai_analysis_config_from_env() -> Optional[AIAnalysisConfig]:
    """从环境变量创建AI配置（保留作为备用）"""
    import os
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        return None
    
    config = AIAnalysisConfig(
        api_key=api_key,
        base_url=os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
        model=os.getenv('OPENAI_MODEL', 'gpt-4-vision-preview'),
        max_tokens=int(os.getenv('OPENAI_MAX_TOKENS', '1500')),
        temperature=float(os.getenv('OPENAI_TEMPERATURE', '0.3')),
        timeout=int(os.getenv('OPENAI_TIMEOUT', '60')),
        max_concurrent=int(os.getenv('AI_MAX_CONCURRENT', '5'))
    )
    
    return config


def create_domain_analysis_request(
    domain: str,
    page_title: Optional[str] = None,
    page_content: Optional[str] = None,
    screenshot_path: Optional[str] = None,
    source_urls: Optional[List[str]] = None
) -> DomainAnalysisRequest:
    """创建域名分析请求的便捷函数"""
    return DomainAnalysisRequest(
        domain=domain,
        page_title=page_title,
        page_content=page_content,
        screenshot_path=screenshot_path,
        source_urls=source_urls or []
    )