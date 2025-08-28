"""
AI分析结果处理器
处理AI识别结果，解析风险等级，更新域名库和任务详情

核心功能：
1. AI分析结果验证和清洗
2. 风险等级评估和分类
3. 违规内容识别和处理
4. 域名库更新和同步
5. 结果导出和报告生成
"""

import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re

from app.core.logging import TaskLogger
from app.engines.infinite_crawler_ai_engine import AIAnalysisResult


class RiskLevel(Enum):
    """风险等级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ViolationType(Enum):
    """违规类型枚举"""
    MALWARE = "malware"
    PHISHING = "phishing"
    FRAUD = "fraud"
    ADULT_CONTENT = "adult_content"
    GAMBLING = "gambling"
    ILLEGAL_CONTENT = "illegal_content"
    SPAM = "spam"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


@dataclass
class ProcessedDomainResult:
    """处理后的域名结果"""
    domain: str
    original_analysis: AIAnalysisResult
    
    # 处理后的分类信息
    category: str
    risk_level: RiskLevel
    confidence_score: float
    
    # 违规信息
    has_violations: bool
    violation_types: List[str]
    violation_details: str
    violation_severity: float  # 0-1
    
    # 评分
    security_score: float      # 0-1
    trustworthiness: float     # 0-1
    
    # 处理信息
    processed_at: datetime = field(default_factory=datetime.utcnow)
    requires_manual_review: bool = False
    
    # 推荐动作
    recommended_action: str = "allow"  # allow, monitor, block, investigate
    monitoring_frequency: str = "monthly"
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DomainDatabaseEntry:
    """域名数据库条目"""
    domain: str
    category: str
    risk_level: str
    last_analyzed: datetime
    analysis_count: int
    first_discovered: datetime
    
    # 统计信息
    violation_count: int = 0
    high_risk_detections: int = 0
    reputation_score: float = 0.5
    
    # 状态
    current_status: str = "active"
    source_tasks: List[str] = field(default_factory=list)


class AIResultValidator:
    """AI结果验证器"""
    
    def __init__(self):
        self.valid_categories = {
            'cdn', 'analytics', 'advertising', 'social', 'api', 
            'payment', 'security', 'maps', 'email', 'cloud', 'unknown'
        }
        self.valid_risk_levels = {'low', 'medium', 'high', 'critical'}
        self.valid_violation_types = {e.value for e in ViolationType}
    
    def validate_analysis_result(self, result: AIAnalysisResult) -> Tuple[bool, List[str]]:
        """验证AI分析结果"""
        issues = []
        
        if not result.analysis_success:
            issues.append("分析未成功完成")
            return False, issues
        
        # 验证域名格式
        if not self._is_valid_domain(result.domain):
            issues.append(f"无效的域名格式: {result.domain}")
        
        # 验证域名分类
        if result.domain_category not in self.valid_categories:
            issues.append(f"无效的域名分类: {result.domain_category}")
        
        # 验证风险等级
        if result.risk_level not in self.valid_risk_levels:
            issues.append(f"无效的风险等级: {result.risk_level}")
        
        # 验证置信度分数
        if not (0 <= result.confidence_score <= 1):
            issues.append(f"置信度分数超出范围: {result.confidence_score}")
        
        # 检查逻辑一致性
        if result.has_violations and not result.violation_types:
            issues.append("标记有违规但未提供违规类型")
        
        return len(issues) == 0, issues
    
    def _is_valid_domain(self, domain: str) -> bool:
        """验证域名格式"""
        if not domain or len(domain) > 253:
            return False
        
        domain_pattern = re.compile(
            r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        )
        return bool(domain_pattern.match(domain))


class RiskAssessmentEngine:
    """风险评估引擎"""
    
    def __init__(self):
        # 违规类型严重度评分
        self.violation_severity_scores = {
            ViolationType.MALWARE: 1.0,
            ViolationType.PHISHING: 0.9,
            ViolationType.FRAUD: 0.8,
            ViolationType.ADULT_CONTENT: 0.6,
            ViolationType.GAMBLING: 0.5,
            ViolationType.ILLEGAL_CONTENT: 0.9,
            ViolationType.SPAM: 0.3,
            ViolationType.SUSPICIOUS_ACTIVITY: 0.5
        }
        
        # 类别风险评分
        self.category_risk_scores = {
            'cdn': 0.1, 'analytics': 0.2, 'advertising': 0.4,
            'social': 0.3, 'api': 0.2, 'payment': 0.1,
            'security': 0.1, 'maps': 0.1, 'email': 0.3,
            'cloud': 0.1, 'unknown': 0.5
        }
    
    def assess_comprehensive_risk(
        self, 
        result: AIAnalysisResult,
        historical_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[RiskLevel, float]:
        """综合风险评估"""
        
        # 计算违规严重度
        violation_score = self._calculate_violation_severity(result)
        
        # 类别风险
        category_risk = self.category_risk_scores.get(result.domain_category, 0.5)
        
        # 置信度调整
        confidence_factor = min(result.confidence_score, 1.0)
        
        # 历史风险 (如果有历史数据)
        historical_risk = 0.5
        if historical_data:
            violation_history = historical_data.get('violation_count', 0)
            total_analyses = historical_data.get('analysis_count', 1)
            historical_risk = violation_history / max(total_analyses, 1)
        
        # 计算加权风险分数
        weighted_score = (
            violation_score * 0.4 +
            category_risk * 0.2 +
            (1 - confidence_factor) * 0.2 +
            historical_risk * 0.2
        )
        
        # 确定风险等级
        if weighted_score >= 0.8:
            risk_level = RiskLevel.CRITICAL
        elif weighted_score >= 0.6:
            risk_level = RiskLevel.HIGH
        elif weighted_score >= 0.4:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW
        
        return risk_level, weighted_score
    
    def _calculate_violation_severity(self, result: AIAnalysisResult) -> float:
        """计算违规严重度"""
        if not result.has_violations or not result.violation_types:
            return 0.0
        
        max_severity = 0.0
        for violation_type_str in result.violation_types:
            try:
                violation_type = ViolationType(violation_type_str)
                severity = self.violation_severity_scores.get(violation_type, 0.5)
                max_severity = max(max_severity, severity)
            except ValueError:
                max_severity = max(max_severity, 0.5)
        
        return max_severity


class AIResultProcessor:
    """AI结果处理器主类"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        # 核心组件
        self.validator = AIResultValidator()
        self.risk_assessor = RiskAssessmentEngine()
        
        # 域名数据库 (内存存储)
        self.domain_database: Dict[str, DomainDatabaseEntry] = {}
        
        # 处理统计
        self.processing_stats = {
            'total_processed': 0,
            'successful_processes': 0,
            'validation_failures': 0,
            'high_risk_found': 0,
            'violations_detected': 0,
            'database_updates': 0
        }
    
    async def process_ai_results(
        self, 
        ai_results: List[AIAnalysisResult],
        update_database: bool = True
    ) -> List[ProcessedDomainResult]:
        """处理AI分析结果列表"""
        self.logger.info(f"开始处理 {len(ai_results)} 个AI分析结果")
        
        processed_results = []
        
        for ai_result in ai_results:
            try:
                processed_result = await self._process_single_result(ai_result, update_database)
                if processed_result:
                    processed_results.append(processed_result)
                    self.processing_stats['successful_processes'] += 1
                    
                    # 统计高风险和违规
                    if processed_result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                        self.processing_stats['high_risk_found'] += 1
                    
                    if processed_result.has_violations:
                        self.processing_stats['violations_detected'] += 1
                
                self.processing_stats['total_processed'] += 1
                
            except Exception as e:
                self.logger.error(f"处理域名 {ai_result.domain} 结果失败: {e}")
                continue
        
        self.logger.info(f"AI结果处理完成: 成功 {len(processed_results)}/{len(ai_results)}")
        return processed_results
    
    async def _process_single_result(
        self, 
        ai_result: AIAnalysisResult,
        update_database: bool = True
    ) -> Optional[ProcessedDomainResult]:
        """处理单个AI分析结果"""
        
        # 1. 验证AI结果
        is_valid, validation_issues = self.validator.validate_analysis_result(ai_result)
        if not is_valid:
            self.logger.warning(f"AI结果验证失败 {ai_result.domain}: {validation_issues}")
            self.processing_stats['validation_failures'] += 1
            return None
        
        # 2. 获取历史数据
        historical_data = self._get_historical_data(ai_result.domain)
        
        # 3. 综合风险评估
        assessed_risk, risk_score = self.risk_assessor.assess_comprehensive_risk(
            ai_result, historical_data
        )
        
        # 4. 计算评分
        security_score = self._calculate_security_score(ai_result)
        trustworthiness = self._calculate_trustworthiness(ai_result, risk_score)
        violation_severity = self._calculate_violation_severity(ai_result)
        
        # 5. 确定推荐动作
        recommended_action, monitoring_freq = self._determine_recommended_action(
            assessed_risk, ai_result.has_violations
        )
        
        # 6. 创建处理结果
        processed_result = ProcessedDomainResult(
            domain=ai_result.domain,
            original_analysis=ai_result,
            category=ai_result.domain_category,
            risk_level=assessed_risk,
            confidence_score=ai_result.confidence_score,
            has_violations=ai_result.has_violations,
            violation_types=ai_result.violation_types,
            violation_details=ai_result.violation_details,
            violation_severity=violation_severity,
            security_score=security_score,
            trustworthiness=trustworthiness,
            requires_manual_review=self._requires_manual_review(assessed_risk, ai_result),
            recommended_action=recommended_action,
            monitoring_frequency=monitoring_freq,
            metadata={
                'risk_score': risk_score,
                'validation_issues': validation_issues
            }
        )
        
        # 7. 更新域名数据库
        if update_database:
            await self._update_domain_database(processed_result)
        
        return processed_result
    
    def _get_historical_data(self, domain: str) -> Optional[Dict[str, Any]]:
        """获取域名历史数据"""
        if domain in self.domain_database:
            entry = self.domain_database[domain]
            return {
                'analysis_count': entry.analysis_count,
                'violation_count': entry.violation_count,
                'reputation_score': entry.reputation_score
            }
        return None
    
    def _calculate_security_score(self, ai_result: AIAnalysisResult) -> float:
        """计算安全评分"""
        base_score = 1.0
        
        if ai_result.has_violations:
            # 安全相关违规类型
            security_violations = {'malware', 'phishing', 'fraud', 'suspicious_activity'}
            if any(vt in security_violations for vt in ai_result.violation_types):
                base_score = 0.2
            else:
                base_score = 0.6
        
        return base_score
    
    def _calculate_trustworthiness(self, ai_result: AIAnalysisResult, risk_score: float) -> float:
        """计算可信度"""
        base_trustworthiness = 1.0 - risk_score
        confidence_weight = ai_result.confidence_score
        return base_trustworthiness * confidence_weight
    
    def _calculate_violation_severity(self, ai_result: AIAnalysisResult) -> float:
        """计算违规严重度"""
        if not ai_result.has_violations:
            return 0.0
        
        max_severity = 0.0
        for violation_type_str in ai_result.violation_types:
            try:
                violation_type = ViolationType(violation_type_str)
                severity = self.risk_assessor.violation_severity_scores.get(violation_type, 0.5)
                max_severity = max(max_severity, severity)
            except ValueError:
                max_severity = max(max_severity, 0.5)
        
        return max_severity
    
    def _determine_recommended_action(self, risk_level: RiskLevel, has_violations: bool) -> Tuple[str, str]:
        """确定推荐动作和监控频率"""
        if risk_level == RiskLevel.CRITICAL:
            return "block", "daily"
        elif risk_level == RiskLevel.HIGH:
            return "investigate", "weekly"
        elif risk_level == RiskLevel.MEDIUM:
            return "monitor", "weekly" if has_violations else "monthly"
        else:
            return "allow", "monthly"
    
    def _requires_manual_review(self, risk_level: RiskLevel, ai_result: AIAnalysisResult) -> bool:
        """判断是否需要人工审查"""
        return (
            risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] or
            ai_result.confidence_score < 0.7 or
            ai_result.has_violations
        )
    
    async def _update_domain_database(self, processed_result: ProcessedDomainResult):
        """更新域名数据库"""
        domain = processed_result.domain
        
        if domain in self.domain_database:
            # 更新现有条目
            entry = self.domain_database[domain]
            entry.last_analyzed = processed_result.processed_at
            entry.analysis_count += 1
            
            if processed_result.has_violations:
                entry.violation_count += 1
            
            if processed_result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                entry.high_risk_detections += 1
            
            entry.reputation_score = processed_result.trustworthiness
        
        else:
            # 创建新条目
            entry = DomainDatabaseEntry(
                domain=domain,
                category=processed_result.category,
                risk_level=processed_result.risk_level.value,
                last_analyzed=processed_result.processed_at,
                analysis_count=1,
                first_discovered=processed_result.processed_at,
                violation_count=1 if processed_result.has_violations else 0,
                high_risk_detections=1 if processed_result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] else 0,
                reputation_score=processed_result.trustworthiness,
                source_tasks=[self.task_id]
            )
            
            self.domain_database[domain] = entry
        
        self.processing_stats['database_updates'] += 1
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        total = self.processing_stats['total_processed']
        success_rate = self.processing_stats['successful_processes'] / max(total, 1)
        
        return {
            **self.processing_stats,
            'success_rate': success_rate,
            'database_size': len(self.domain_database),
            'validation_failure_rate': self.processing_stats['validation_failures'] / max(total, 1),
            'high_risk_rate': self.processing_stats['high_risk_found'] / max(total, 1),
            'violation_rate': self.processing_stats['violations_detected'] / max(total, 1)
        }
    
    def get_high_risk_domains(self) -> List[Dict[str, Any]]:
        """获取高风险域名列表"""
        high_risk_domains = []
        
        for domain, entry in self.domain_database.items():
            if entry.risk_level in ['high', 'critical']:
                high_risk_domains.append({
                    'domain': domain,
                    'risk_level': entry.risk_level,
                    'category': entry.category,
                    'violation_count': entry.violation_count,
                    'last_analyzed': entry.last_analyzed.isoformat(),
                    'reputation_score': entry.reputation_score
                })
        
        # 按风险等级排序
        high_risk_domains.sort(
            key=lambda x: (0 if x['risk_level'] == 'critical' else 1, x['reputation_score'])
        )
        
        return high_risk_domains
    
    async def export_results(self, output_file: str):
        """导出处理结果"""
        try:
            export_data = {
                'export_timestamp': datetime.utcnow().isoformat(),
                'task_id': self.task_id,
                'statistics': self.get_processing_statistics(),
                'high_risk_domains': self.get_high_risk_domains(),
                'domain_database': [
                    {
                        'domain': entry.domain,
                        'category': entry.category,
                        'risk_level': entry.risk_level,
                        'reputation_score': entry.reputation_score,
                        'analysis_count': entry.analysis_count,
                        'violation_count': entry.violation_count,
                        'first_discovered': entry.first_discovered.isoformat(),
                        'last_analyzed': entry.last_analyzed.isoformat()
                    }
                    for entry in self.domain_database.values()
                ]
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"处理结果已导出到: {output_file}")
            
        except Exception as e:
            self.logger.error(f"导出结果失败: {e}")


# 便捷函数
def create_mock_ai_result(
    domain: str, 
    category: str = "unknown", 
    risk: str = "low",
    has_violations: bool = False,
    violation_types: Optional[List[str]] = None
) -> AIAnalysisResult:
    """创建模拟AI分析结果"""
    from datetime import datetime
    
    return AIAnalysisResult(
        domain=domain,
        analysis_success=True,
        analysis_timestamp=datetime.utcnow(),
        processing_time=2.0,
        domain_category=category,
        risk_level=risk,
        confidence_score=0.85,
        content_type="service",
        has_violations=has_violations,
        violation_types=violation_types or [],
        violation_details="检测到可疑内容" if has_violations else "",
        ai_raw_response=f'{{"domain_category": "{category}", "risk_level": "{risk}"}}'
    )