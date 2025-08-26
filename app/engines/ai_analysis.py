import asyncio
import json
import time
import base64
import aiohttp
import aiofiles
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path

from app.core.logging import TaskLogger
from app.core.config import settings
from app.core.security import data_encryption
from app.models.user import UserAIConfig
from app.models.task import ThirdPartyDomain, ViolationRecord, RiskLevel
from app.core.prometheus import record_ai_analysis, record_violation_detected, record_error


class AIAnalysisResult:
    """AI分析结果数据结构"""
    
    def __init__(self):
        self.has_violation = False
        self.violation_types: List[str] = []
        self.confidence_score = 0.0
        self.risk_level = RiskLevel.LOW
        self.title = ""
        self.description = ""
        self.content_snippet = ""
        self.evidence: List[str] = []
        self.recommendations: List[str] = []
        self.ai_raw_response = ""
        self.analysis_duration = 0.0
        self.error_message = ""


class OpenAIClient:
    """OpenAI API客户端"""
    
    def __init__(self, ai_config: UserAIConfig, logger: TaskLogger):
        self.ai_config = ai_config
        self.logger = logger
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        timeout = aiohttp.ClientTimeout(total=self.ai_config.request_timeout_int)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def analyze_content(
        self, 
        prompt: str, 
        image_data: str, 
        retry_count: int = None
    ) -> Dict[str, Any]:
        """调用OpenAI API进行内容分析"""
        if not self.session:
            raise RuntimeError("OpenAI客户端未初始化")
        
        # 获取解密的API密钥
        try:
            api_key = data_encryption.decrypt_data(self.ai_config.openai_api_key)
        except Exception as e:
            raise ValueError(f"无法解密API密钥: {e}")
        
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        if self.ai_config.openai_organization:
            headers["OpenAI-Organization"] = self.ai_config.openai_organization
        
        # 构建请求数据
        request_data = {
            "model": self.ai_config.ai_model_name,
            "messages": [
                {
                    "role": "system",
                    "content": self._get_system_prompt()
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}",
                                "detail": "auto"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": self.ai_config.max_tokens_int,
            "temperature": self.ai_config.temperature_float
        }
        
        retry_count = retry_count or self.ai_config.retry_count_int
        last_error = None
        
        for attempt in range(retry_count + 1):
            try:
                start_time = time.time()
                
                async with self.session.post(
                    f"{self.ai_config.openai_base_url}/chat/completions",
                    headers=headers,
                    json=request_data
                ) as response:
                    duration = time.time() - start_time
                    
                    if response.status == 200:
                        result = await response.json()
                        record_ai_analysis(self.ai_config.ai_model_name, duration, "success")
                        return result
                    else:
                        error_text = await response.text()
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status,
                            message=f"OpenAI API错误: {error_text}"
                        )
            
            except Exception as e:
                last_error = e
                duration = time.time() - start_time
                record_ai_analysis(self.ai_config.ai_model_name, duration, "error")
                
                if attempt < retry_count:
                    wait_time = 2 ** attempt  # 指数退避
                    self.logger.warning(f"AI分析请求失败 (尝试 {attempt + 1}/{retry_count + 1}): {e}, {wait_time}秒后重试")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"AI分析请求最终失败: {e}")
                    record_error("ai_api_failure", "ai_analysis")
                    raise
        
        raise last_error or Exception("AI分析请求失败")
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        if self.ai_config.system_prompt:
            return self.ai_config.system_prompt
        
        return """你是一个专业的内容安全分析专家。请分析提供的网页内容和截图，识别是否存在以下违规情况：

1. 色情内容 (NSFW)
2. 暴力内容
3. 赌博相关
4. 诈骗信息
5. 恶意软件
6. 仇恨言论
7. 侵权内容
8. 其他违法违规内容

请按照以下JSON格式返回分析结果：

{
  "has_violation": boolean,
  "violation_types": ["类型1", "类型2"],
  "confidence_score": 0.0-1.0,
  "risk_level": "low|medium|high|critical", 
  "title": "违规标题",
  "description": "详细描述",
  "content_snippet": "关键内容片段",
  "evidence": ["证据1", "证据2"],
  "recommendations": ["建议1", "建议2"]
}

分析要客观准确，避免误报。对于正常内容，has_violation应为false。"""


class AIAnalysisEngine:
    """AI分析引擎"""
    
    def __init__(self, task_id: str, ai_config: UserAIConfig):
        self.task_id = task_id
        self.ai_config = ai_config
        self.logger = TaskLogger(task_id, "ai_analysis")
        
        # 配置验证
        if not self.ai_config or not self.ai_config.has_valid_config:
            raise ValueError("用户AI配置无效或缺失")
    
    async def analyze_domains(self, domains: List[ThirdPartyDomain]) -> List[ViolationRecord]:
        """批量分析第三方域名"""
        self.logger.info(f"开始AI分析 {len(domains)} 个第三方域名")
        
        violations = []
        analyzed_count = 0
        
        for i, domain in enumerate(domains):
            try:
                # 跳过已分析的域名
                if domain.is_analyzed:
                    self.logger.debug(f"跳过已分析的域名: {domain.domain}")
                    continue
                
                # 检查必要文件是否存在
                if not domain.screenshot_path or not Path(domain.screenshot_path).exists():
                    self.logger.warning(f"域名 {domain.domain} 缺少截图文件，跳过AI分析")
                    domain.is_analyzed = True
                    domain.analysis_error = "缺少截图文件"
                    continue
                
                self.logger.info(f"分析域名 ({i+1}/{len(domains)}): {domain.domain}")
                
                # 执行AI分析
                result = await self._analyze_single_domain(domain)
                
                # 如果发现违规，创建违规记录
                if result.has_violation:
                    violation = await self._create_violation_record(domain, result)
                    violations.append(violation)
                    
                    # 记录监控指标
                    for violation_type in result.violation_types:
                        record_violation_detected(violation_type, result.risk_level)
                
                # 更新域名分析状态
                domain.is_analyzed = True
                domain.analyzed_at = datetime.utcnow()
                domain.risk_level = result.risk_level
                
                analyzed_count += 1
                self.logger.info(f"完成分析: {domain.domain} (违规: {result.has_violation})")
                
                # 防止过快请求
                if i < len(domains) - 1:
                    await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"分析域名 {domain.domain} 失败: {e}")
                domain.is_analyzed = True
                domain.analysis_error = str(e)
                record_error("domain_analysis_failure", "ai_analysis")
        
        self.logger.info(f"AI分析完成，共分析 {analyzed_count} 个域名，发现 {len(violations)} 个违规")
        return violations
    
    async def _analyze_single_domain(self, domain: ThirdPartyDomain) -> AIAnalysisResult:
        """分析单个域名"""
        result = AIAnalysisResult()
        
        try:
            start_time = time.time()
            
            # 构建分析提示词
            prompt = await self._build_analysis_prompt(domain)
            
            # 读取截图数据
            image_data = await self._read_image_as_base64(domain.screenshot_path)
            
            # 调用AI API
            async with OpenAIClient(self.ai_config, self.logger) as client:
                ai_response = await client.analyze_content(prompt, image_data)
            
            # 解析AI响应
            result = await self._parse_ai_response(ai_response, result)
            result.analysis_duration = time.time() - start_time
            
        except Exception as e:
            result.error_message = str(e)
            result.has_violation = False
            self.logger.error(f"AI分析失败: {e}")
        
        return result
    
    async def _build_analysis_prompt(self, domain: ThirdPartyDomain) -> str:
        """构建AI分析提示词"""
        template = self.ai_config.custom_prompt_template or """
分析域名：{domain}
发现页面：{found_on_url}
域名类型：{domain_type}
页面标题：{page_title}

请仔细分析该域名的页面截图和以下信息，判断是否存在违规内容。

域名描述：{page_description}

注意事项：
1. 这是一个第三方域名，需要特别关注是否存在恶意内容
2. 请结合页面截图进行综合判断
3. 对于CDN、广告、分析等正常技术服务，除非明确存在违规内容，否则不应标记为违规
4. 重点关注页面的实际内容，而非技术实现
"""
        
        return template.format(
            domain=domain.domain,
            found_on_url=domain.found_on_url[:200],  # 限制长度
            domain_type=domain.domain_type,
            page_title=domain.page_title or "无标题",
            page_description=domain.page_description or "无描述"
        )
    
    async def _read_image_as_base64(self, image_path: str) -> str:
        """读取图片并转换为Base64"""
        try:
            async with aiofiles.open(image_path, 'rb') as f:
                image_data = await f.read()
            return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            raise ValueError(f"读取截图文件失败: {e}")
    
    async def _parse_ai_response(self, ai_response: Dict[str, Any], result: AIAnalysisResult) -> AIAnalysisResult:
        """解析AI响应"""
        try:
            # 保存原始响应
            result.ai_raw_response = json.dumps(ai_response, ensure_ascii=False)
            
            # 提取响应内容
            if 'choices' not in ai_response or not ai_response['choices']:
                raise ValueError("AI响应格式错误：缺少choices字段")
            
            content = ai_response['choices'][0]['message']['content']
            
            # 尝试解析JSON响应
            try:
                analysis_result = json.loads(content)
            except json.JSONDecodeError:
                # 如果不是标准JSON，尝试提取JSON部分
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    analysis_result = json.loads(json_match.group())
                else:
                    raise ValueError("无法从AI响应中提取JSON格式结果")
            
            # 映射结果字段
            result.has_violation = analysis_result.get('has_violation', False)
            result.violation_types = analysis_result.get('violation_types', [])
            result.confidence_score = float(analysis_result.get('confidence_score', 0.0))
            result.title = analysis_result.get('title', 'AI分析结果')
            result.description = analysis_result.get('description', '')
            result.content_snippet = analysis_result.get('content_snippet', '')
            result.evidence = analysis_result.get('evidence', [])
            result.recommendations = analysis_result.get('recommendations', [])
            
            # 映射风险等级
            risk_level_str = analysis_result.get('risk_level', 'low').lower()
            result.risk_level = self._map_risk_level(risk_level_str)
            
            # 验证数据有效性
            if result.has_violation:
                if not result.violation_types:
                    result.violation_types = ['未知违规']
                if not result.description:
                    result.description = 'AI检测到潜在违规内容'
                if result.confidence_score < 0.1:
                    result.confidence_score = 0.5  # 设置默认置信度
                if not result.title:
                    result.title = f"{result.violation_types[0]} - {result.risk_level}"
            
        except Exception as e:
            self.logger.error(f"解析AI响应失败: {e}")
            # 设置默认值
            result.has_violation = False
            result.error_message = f"解析AI响应失败: {e}"
        
        return result
    
    def _map_risk_level(self, risk_level_str: str) -> str:
        """映射风险等级"""
        risk_mapping = {
            'low': RiskLevel.LOW,
            'medium': RiskLevel.MEDIUM,
            'high': RiskLevel.HIGH,
            'critical': RiskLevel.CRITICAL
        }
        return risk_mapping.get(risk_level_str.lower(), RiskLevel.LOW)
    
    async def _create_violation_record(self, domain: ThirdPartyDomain, result: AIAnalysisResult) -> ViolationRecord:
        """创建违规记录"""
        violation = ViolationRecord(
            task_id=self.task_id,
            domain_id=domain.id,
            violation_type=', '.join(result.violation_types),
            confidence_score=result.confidence_score,
            risk_level=result.risk_level,
            title=result.title,
            description=result.description,
            content_snippet=result.content_snippet,
            ai_analysis_result={
                "has_violation": result.has_violation,
                "violation_types": result.violation_types,
                "confidence_score": result.confidence_score,
                "risk_level": result.risk_level,
                "evidence": result.evidence,
                "recommendations": result.recommendations,
                "analysis_duration": result.analysis_duration,
                "raw_response": result.ai_raw_response
            },
            ai_model_used=self.ai_config.ai_model_name,
            evidence=result.evidence,
            recommendations=result.recommendations,
            detected_at=datetime.utcnow()
        )
        
        return violation
    
    async def test_configuration(self) -> Dict[str, Any]:
        """测试AI配置是否有效"""
        try:
            test_prompt = "请回答：这是一个连接测试，请回复'连接成功'。"
            test_image = self._create_test_image_base64()
            
            async with OpenAIClient(self.ai_config, self.logger) as client:
                response = await client.analyze_content(test_prompt, test_image)
            
            return {
                "success": True,
                "message": "AI配置测试成功",
                "model": self.ai_config.ai_model_name,
                "response_preview": response.get('choices', [{}])[0].get('message', {}).get('content', '')[:100]
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"AI配置测试失败: {e}",
                "model": self.ai_config.ai_model_name
            }
    
    def _create_test_image_base64(self) -> str:
        """创建测试用的Base64图片数据"""
        # 创建一个简单的1x1像素PNG图片的Base64数据
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x18\xdd\x8d\xb4\x1c\x00\x00\x00\x00IEND\xaeB`\x82'
        return base64.b64encode(png_data).decode('utf-8')