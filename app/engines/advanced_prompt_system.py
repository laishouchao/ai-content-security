"""
高级AI提示词系统
为无限迭代爬虫设计的专业AI提示词管理引擎

核心功能：
1. 多种预设提示词模板
2. 动态提示词构建
3. 回复格式标准化
4. 提示词性能监控
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import hashlib

from app.core.logging import TaskLogger


class AnalysisType(Enum):
    """分析类型枚举"""
    DOMAIN_CLASSIFICATION = "domain_classification"
    SECURITY_ASSESSMENT = "security_assessment"
    CONTENT_ANALYSIS = "content_analysis"
    COMPREHENSIVE = "comprehensive"


@dataclass
class PromptContext:
    """提示词上下文"""
    domain: str
    page_title: Optional[str] = None
    page_description: Optional[str] = None
    content_snippet: Optional[str] = None
    screenshot_available: bool = False
    source_urls: List[str] = field(default_factory=list)
    discovery_method: str = "unknown"


@dataclass
class PromptResult:
    """提示词生成结果"""
    system_prompt: str
    user_prompt: str
    expected_format: str
    template_used: str
    estimated_tokens: int


class AdvancedPromptBuilder:
    """高级提示词构建器"""
    
    def __init__(self):
        self.system_prompts = self._load_system_prompts()
        self.format_templates = self._load_format_templates()
        self.max_prompt_length = 8000
        
    def _load_system_prompts(self) -> Dict[str, str]:
        """加载系统提示词模板"""
        return {
            "base": """你是一个专业的网络内容安全审核专家，专门负责检测和识别网站内容中的违法违规信息。

你的主要职责：
• 检测黄色、色情内容（成人内容、色情图片、性相关内容）
• 识别赌博内容（线上博彩、赌场、竞猬平台）
• 发现毒品相关内容（毒品交易、吸毒用具、制毒方法）
• 识别其他违法内容（欺诈、洗钱、危险物品、虚假信息）

分析原则：
• 保持客观公正，不过度解读
• 严格按照中国法律法规标准进行判断
• 提供具体可靠的证据和建议
• 区分正常内容和违法内容，避免误报""",

            "domain_classifier": """你是一个专业的网络内容安全审核师，专门负责检测网站中的黄赌毒等违法违规内容。

重点检测内容：

1. **黄色色情内容**：
   - 成人网站、色情视频、性用品销售
   - 性服务广告、招嫦信息
   - 暴露性图片、描述性行为的文字

2. **赌博内容**：
   - 线上赌场、博彩网站、体育博彩
   - 赌博平台推广、赌博技巧分享
   - 竞猬游戏、老虎机等赌博工具

3. **毒品相关内容**：
   - 毒品交易、毒品销售信息
   - 吸毒用具、制毒原料销售
   - 引导吸毒、毒品使用经历分享

4. **其他违法内容**：
   - 电信诈骗、网络诈骗、金融诈骗
   - 洗钱服务、非法集资
   - 危险物品销售、非法武器交易
   - 传销组织、邪教组织宣传

审核标准：严格遵守中国法律法规，准确识别违法内容，对正常内容不要误报。""",

            "security_analyzer": """你是一个专业的网络安全分析师，专门识别网站和域名的安全风险和威胁。

安全评估重点：
• 恶意软件和病毒传播
• 钓鱼攻击和欺诈行为
• 数据泄露和隐私侵犯
• 非法内容和违规服务
• 技术漏洞和安全缺陷

风险等级定义：
• LOW: 正常合法服务，无明显安全风险
• MEDIUM: 存在潜在风险或需要关注的行为
• HIGH: 发现明确的安全威胁或违规行为
• CRITICAL: 严重的安全威胁，需要立即处理""",

            "comprehensive": """你是一个专业的网络内容安全检测专家，能够从多个维度对网站内容进行全面的违法违规检测。

综合分析框架：
• **内容安全检测**: 黄色色情、赌博、毒品等违法内容识别
• **风险等级评估**: 根据内容严重程度进行风险分级
• **法律合规检查**: 检查是否符合中国法律法规要求
• **安全建议提供**: 给出具体的处理建议和防范措施

请提供全面、客观、专业的综合安全检测报告。"""
        }
    
    def _load_format_templates(self) -> Dict[str, str]:
        """加载回复格式模板"""
        return {
            "standard": """请按照以下JSON格式返回违法内容检测结果：

{
    "has_violations": false,
    "violation_types": ["违法类型列表"],
    "risk_level": "风险等级 (low/medium/high/critical)",
    "confidence_score": 0.85,
    "violation_details": "违法内容详细说明",
    "evidence": ["证据1", "证据2"],
    "legal_assessment": {
        "yellow_content": {
            "detected": false,
            "severity": "none",
            "description": ""
        },
        "gambling_content": {
            "detected": false,
            "severity": "none", 
            "description": ""
        },
        "drug_content": {
            "detected": false,
            "severity": "none",
            "description": ""
        },
        "fraud_content": {
            "detected": false,
            "severity": "none",
            "description": ""
        }
    },
    "recommended_action": "建议采取的行动: allow/monitor/block/report",
    "analysis_summary": "分析总结",
    "reasoning": "分析推理过程"
}""",

            "security_focused": """请按照以下JSON格式返回安全分析结果：

{
    "security_level": "安全等级 (safe/warning/danger/critical)",
    "threat_types": ["威胁类型列表"],
    "vulnerability_score": 0.25,
    "risk_factors": {
        "malware_risk": 0.1,
        "phishing_risk": 0.2,
        "privacy_risk": 0.3,
        "content_risk": 0.4
    },
    "security_features": ["安全特性列表"],
    "security_concerns": ["安全关注点"],
    "mitigation_actions": ["缓解措施"],
    "detailed_analysis": "详细安全分析"
}""",

            "comprehensive": """请按照以下JSON格式返回综合违法内容检测结果：

{
    "overall_assessment": {
        "has_violations": false,
        "risk_level": "综合风险等级",
        "confidence_score": 0.85
    },
    "content_analysis": {
        "yellow_content": {
            "detected": false,
            "type": "none",
            "severity": "low",
            "evidence": [],
            "confidence": 0.0
        },
        "gambling_content": {
            "detected": false,
            "type": "none", 
            "severity": "low",
            "evidence": [],
            "confidence": 0.0
        },
        "drug_content": {
            "detected": false,
            "type": "none",
            "severity": "low", 
            "evidence": [],
            "confidence": 0.0
        },
        "other_illegal": {
            "detected": false,
            "types": [],
            "severity": "low",
            "evidence": [],
            "confidence": 0.0
        }
    },
    "legal_compliance": {
        "china_law_compliant": true,
        "violation_categories": [],
        "legal_references": [],
        "severity_assessment": "compliant"
    },
    "recommendations": {
        "immediate_actions": ["立即行动"],
        "monitoring_strategy": "监控策略",
        "risk_mitigation": ["风险缓解措施"],
        "reporting_required": false
    },
    "detailed_reasoning": "详细分析推理和法律依据"
}"""
        }
    
    def build_prompt(
        self, 
        context: PromptContext, 
        analysis_type: AnalysisType = AnalysisType.COMPREHENSIVE,
        custom_instructions: Optional[str] = None
    ) -> PromptResult:
        """构建完整的提示词"""
        
        # 选择系统提示词模板
        template_key = self._select_template(analysis_type)
        system_prompt = self.system_prompts[template_key]
        
        # 构建用户提示词
        user_prompt = self._build_user_prompt(context, analysis_type, custom_instructions)
        
        # 选择回复格式
        format_template = self._select_format_template(analysis_type)
        
        # 估算token数量
        total_prompt = system_prompt + user_prompt + format_template
        estimated_tokens = int(len(total_prompt) * 0.75)
        
        # 优化提示词长度
        if len(total_prompt) > self.max_prompt_length:
            user_prompt = self._optimize_prompt_length(user_prompt, context)
        
        return PromptResult(
            system_prompt=system_prompt,
            user_prompt=user_prompt + "\\n\\n" + format_template,
            expected_format=format_template,
            template_used=template_key,
            estimated_tokens=estimated_tokens
        )
    
    def _select_template(self, analysis_type: AnalysisType) -> str:
        """选择合适的提示词模板"""
        template_mapping = {
            AnalysisType.DOMAIN_CLASSIFICATION: "domain_classifier",
            AnalysisType.SECURITY_ASSESSMENT: "security_analyzer",
            AnalysisType.CONTENT_ANALYSIS: "base",
            AnalysisType.COMPREHENSIVE: "comprehensive"
        }
        return template_mapping.get(analysis_type, "comprehensive")
    
    def _select_format_template(self, analysis_type: AnalysisType) -> str:
        """选择合适的回复格式模板"""
        format_mapping = {
            AnalysisType.SECURITY_ASSESSMENT: "security_focused",
            AnalysisType.COMPREHENSIVE: "comprehensive"
        }
        return self.format_templates.get(format_mapping.get(analysis_type, "standard"), self.format_templates["standard"])
    
    def _build_user_prompt(
        self, 
        context: PromptContext, 
        analysis_type: AnalysisType,
        custom_instructions: Optional[str] = None
    ) -> str:
        """构建用户提示词"""
        
        prompt_parts = []
        
        # 添加任务描述
        task_description = self._get_task_description(analysis_type)
        prompt_parts.append(task_description)
        
        # 添加域名基本信息
        domain_info = f"""域名信息：
• 域名: {context.domain}
• 发现方法: {context.discovery_method}
• 来源URL: {", ".join(context.source_urls[:3]) if context.source_urls else "未知"}"""
        prompt_parts.append(domain_info)
        
        # 添加页面内容信息
        if context.page_title or context.page_description or context.content_snippet:
            content_info = f"""页面内容信息：
• 页面标题: {context.page_title or "无"}
• 页面描述: {context.page_description or "无"}
• 内容摘要: {self._prepare_content_snippet(context.content_snippet)}"""
            prompt_parts.append(content_info)
        
        # 添加截图信息
        if context.screenshot_available:
            prompt_parts.append("• 截图可用: 是（请结合截图进行分析）")
        
        # 添加自定义指令
        if custom_instructions:
            prompt_parts.append(f"\\n特殊要求: {custom_instructions}")
        
        # 添加分析指导
        analysis_guidance = self._get_analysis_guidance(analysis_type)
        prompt_parts.append(analysis_guidance)
        
        return "\\n\\n".join(prompt_parts)
    
    def _get_task_description(self, analysis_type: AnalysisType) -> str:
        """获取任务描述（专门用于违法内容检测）"""
        descriptions = {
            AnalysisType.DOMAIN_CLASSIFICATION: "请对以下域名的内容进行黄赌毒等违法内容检测：",
            AnalysisType.SECURITY_ASSESSMENT: "请对以下域名进行安全风险和违法内容评估：",
            AnalysisType.CONTENT_ANALYSIS: "请对以下域名的内容进行违法违规检测和分析：",
            AnalysisType.COMPREHENSIVE: "请对以下域名进行全面的违法内容安全检测："
        }
        return descriptions.get(analysis_type, "请对以下域名进行违法内容检测：")
    
    def _get_analysis_guidance(self, analysis_type: AnalysisType) -> str:
        """获取分析指导"""
        guidance = {
            AnalysisType.DOMAIN_CLASSIFICATION: """分析重点：
• 重点检测黄色色情内容（成人网站、色情内容、性服务）
• 识别赌博相关内容（线上赌场、博彩网站、竞猬游戏）
• 发现毒品相关信息（毒品交易、吸毒用具、制毒原料）
• 其他违法内容（诈骗、洗钱、危险物品、传销组织）""",

            AnalysisType.SECURITY_ASSESSMENT: """分析重点：
• 检查是否存在违法违规内容
• 识别钓鱼攻击和网络诈骗行为
• 评估内容安全和法律风险
• 分析潜在的社会危害性和影响""",

            AnalysisType.CONTENT_ANALYSIS: """分析重点：
• 全面检测黄赌毒等违法内容
• 识别成人和敏感内容
• 评估内容对未成年人的影响
• 分析潜在的法律风险和社会危害""",

            AnalysisType.COMPREHENSIVE: """分析重点：
• 从内容安全、法律合规、社会影响等多个维度进行分析
• 提供全面客观的违法内容检测结果
• 识别主要风险和法律问题
• 给出具体可操作的处理建议和防范措施"""
        }
        return guidance.get(analysis_type, "请进行全面深入的违法内容检测。")
    
    def _prepare_content_snippet(self, content: Optional[str]) -> str:
        """准备内容摘要"""
        if not content:
            return "无页面内容"
        
        # 清理和截取内容
        cleaned_content = re.sub(r'\\s+', ' ', content.strip())
        max_content_length = 800
        
        if len(cleaned_content) > max_content_length:
            cleaned_content = cleaned_content[:max_content_length] + "..."
        
        return cleaned_content
    
    def _optimize_prompt_length(self, prompt: str, context: PromptContext) -> str:
        """优化提示词长度"""
        if len(prompt) <= self.max_prompt_length:
            return prompt
        
        # 优化策略：缩减内容摘要
        if context.content_snippet and len(context.content_snippet) > 400:
            shorter_content = context.content_snippet[:400] + "..."
            prompt = prompt.replace(context.content_snippet, shorter_content)
        
        # 缩减来源URL列表
        if len(context.source_urls) > 2:
            original_urls_str = ", ".join(context.source_urls)
            reduced_urls_str = ", ".join(context.source_urls[:2]) + "..."
            prompt = prompt.replace(original_urls_str, reduced_urls_str)
        
        return prompt


class PromptPerformanceMonitor:
    """提示词性能监控器"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        # 性能统计
        self.prompt_stats = {
            'total_prompts_generated': 0,
            'average_prompt_length': 0,
            'average_token_count': 0,
            'template_usage': {},
            'cache_hits': 0,
            'generation_time': []
        }
        
        # 提示词缓存
        self.prompt_cache: Dict[str, PromptResult] = {}
    
    def record_prompt_generation(self, prompt_result: PromptResult, generation_time: float, cache_hit: bool = False):
        """记录提示词生成"""
        self.prompt_stats['total_prompts_generated'] += 1
        
        if cache_hit:
            self.prompt_stats['cache_hits'] += 1
        else:
            # 更新统计
            total = self.prompt_stats['total_prompts_generated']
            current_avg_length = self.prompt_stats['average_prompt_length']
            current_avg_tokens = self.prompt_stats['average_token_count']
            
            self.prompt_stats['average_prompt_length'] = (
                (current_avg_length * (total - 1) + len(prompt_result.user_prompt)) / total
            )
            self.prompt_stats['average_token_count'] = (
                (current_avg_tokens * (total - 1) + prompt_result.estimated_tokens) / total
            )
            
            # 更新模板使用统计
            template = prompt_result.template_used
            self.prompt_stats['template_usage'][template] = (
                self.prompt_stats['template_usage'].get(template, 0) + 1
            )
        
        # 记录生成时间
        self.prompt_stats['generation_time'].append(generation_time)
        if len(self.prompt_stats['generation_time']) > 100:
            self.prompt_stats['generation_time'].pop(0)
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        generation_times = self.prompt_stats['generation_time']
        avg_generation_time = sum(generation_times) / max(len(generation_times), 1)
        
        cache_hit_rate = 0
        if self.prompt_stats['total_prompts_generated'] > 0:
            cache_hit_rate = self.prompt_stats['cache_hits'] / self.prompt_stats['total_prompts_generated']
        
        return {
            'total_prompts': self.prompt_stats['total_prompts_generated'],
            'average_prompt_length': self.prompt_stats['average_prompt_length'],
            'average_token_count': self.prompt_stats['average_token_count'],
            'template_usage': self.prompt_stats['template_usage'],
            'cache_hit_rate': cache_hit_rate,
            'average_generation_time': avg_generation_time,
            'performance_score': self._calculate_performance_score()
        }
    
    def _calculate_performance_score(self) -> float:
        """计算性能评分"""
        # 基于缓存命中率、生成时间等计算性能评分
        cache_score = min(self.prompt_stats['cache_hits'] / max(self.prompt_stats['total_prompts_generated'], 1), 1.0)
        
        generation_times = self.prompt_stats['generation_time']
        if generation_times:
            avg_time = sum(generation_times) / len(generation_times)
            time_score = max(0, 1.0 - avg_time / 10.0)  # 假设10秒为最差情况
        else:
            time_score = 1.0
        
        return (cache_score * 0.4 + time_score * 0.6) * 100


class EnhancedPromptManager:
    """增强的提示词管理器"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        self.prompt_builder = AdvancedPromptBuilder()
        self.performance_monitor = PromptPerformanceMonitor(task_id, user_id)
        
        # A/B测试配置
        self.ab_testing_enabled = False
        self.current_variant = "default"
    
    async def generate_analysis_prompt(
        self,
        context: PromptContext,
        analysis_type: AnalysisType = AnalysisType.COMPREHENSIVE,
        custom_instructions: Optional[str] = None
    ) -> PromptResult:
        """生成分析提示词"""
        import time
        start_time = time.time()
        
        try:
            # 生成缓存键
            cache_key = self._generate_cache_key(context, analysis_type, custom_instructions)
            
            # 检查缓存
            if cache_key in self.performance_monitor.prompt_cache:
                cached_result = self.performance_monitor.prompt_cache[cache_key]
                generation_time = time.time() - start_time
                self.performance_monitor.record_prompt_generation(cached_result, generation_time, cache_hit=True)
                return cached_result
            
            # 生成新提示词
            prompt_result = self.prompt_builder.build_prompt(context, analysis_type, custom_instructions)
            
            # 缓存结果
            self.performance_monitor.prompt_cache[cache_key] = prompt_result
            
            # 记录性能
            generation_time = time.time() - start_time
            self.performance_monitor.record_prompt_generation(prompt_result, generation_time)
            
            return prompt_result
            
        except Exception as e:
            self.logger.error(f"提示词生成失败: {e}")
            raise
    
    def _generate_cache_key(
        self, 
        context: PromptContext, 
        analysis_type: AnalysisType,
        custom_instructions: Optional[str]
    ) -> str:
        """生成缓存键"""
        key_components = [
            context.domain,
            analysis_type.value,
            str(context.screenshot_available),
            custom_instructions or "",
            context.discovery_method
        ]
        
        key_string = "|".join(key_components)
        return hashlib.md5(key_string.encode('utf-8')).hexdigest()[:16]
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return self.performance_monitor.get_performance_report()
    
    def clear_cache(self):
        """清理缓存"""
        self.performance_monitor.prompt_cache.clear()
        self.logger.info("提示词缓存已清理")


# 便捷函数
def create_prompt_context(
    domain: str,
    page_title: Optional[str] = None,
    page_content: Optional[str] = None,
    screenshot_path: Optional[str] = None,
    source_urls: Optional[List[str]] = None,
    discovery_method: str = "unknown"
) -> PromptContext:
    """创建提示词上下文的便捷函数"""
    return PromptContext(
        domain=domain,
        page_title=page_title,
        content_snippet=page_content,
        screenshot_available=bool(screenshot_path),
        source_urls=source_urls or [],
        discovery_method=discovery_method
    )