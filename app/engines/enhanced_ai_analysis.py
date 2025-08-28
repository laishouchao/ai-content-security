import asyncio
import time
import json
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path

from app.core.logging import TaskLogger
from app.engines.ai_analysis import AIAnalysisEngine, AIAnalysisResult
from app.engines.smart_ai_prefilter import SmartAIPrefilter
from app.engines.content_capture import ContentResult
from app.models.task import ViolationRecord, RiskLevel
from app.models.user import UserAIConfig


class EnhancedAIAnalysisEngine:
    """增强的AI分析引擎（集成智能预筛选）"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        # 核心组件
        self.prefilter = SmartAIPrefilter(task_id, user_id)
        self.ai_engine = None  # 延迟初始化
        
        # 性能统计
        self.performance_stats = {
            'total_processed': 0,
            'ai_calls_made': 0,
            'ai_calls_skipped': 0,
            'total_violations_found': 0,
            'avg_processing_time': 0.0,
            'cost_saved_estimate': 0.0,
            'cache_hit_rate': 0.0
        }
        
        # 批处理配置
        self.batch_size = 10
        self.max_concurrent_ai_calls = 3
    
    async def analyze_content_batch(self, content_results: List[ContentResult], config: Dict[str, Any]) -> List[ViolationRecord]:
        """批量分析内容（主要入口点）"""
        start_time = time.time()
        self.logger.info(f"开始批量AI分析: {len(content_results)} 个内容")
        
        all_violations = []
        
        # 分批处理以控制内存和并发
        for i in range(0, len(content_results), self.batch_size):
            batch = content_results[i:i + self.batch_size]
            
            try:
                batch_violations = await self._process_batch(batch, config)
                all_violations.extend(batch_violations)
                
                # 批次间短暂休息，避免API限制
                if i + self.batch_size < len(content_results):
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                self.logger.error(f"批次 {i//self.batch_size + 1} 处理失败: {e}")
                continue
        
        # 更新统计信息
        duration = time.time() - start_time
        self._update_performance_stats(len(content_results), len(all_violations), duration)
        
        self.logger.info(f"批量AI分析完成: 发现 {len(all_violations)} 个违规，耗时 {duration:.2f}秒")
        return all_violations
    
    async def _process_batch(self, batch: List[ContentResult], config: Dict[str, Any]) -> List[ViolationRecord]:
        """处理单个批次"""
        violations = []
        
        # 第一阶段：智能预筛选
        analysis_tasks = []
        for content_result in batch:
            analysis_tasks.append(self._analyze_single_content_smart(content_result, config))
        
        # 限制并发AI调用数量
        semaphore = asyncio.Semaphore(self.max_concurrent_ai_calls)
        
        async def _limited_analysis(task):
            async with semaphore:
                return await task
        
        # 执行分析
        results = await asyncio.gather(
            *[_limited_analysis(task) for task in analysis_tasks],
            return_exceptions=True
        )
        
        # 收集结果
        for result in results:
            if isinstance(result, list):
                violations.extend(result)
            elif isinstance(result, Exception):
                self.logger.warning(f"内容分析异常: {result}")
        
        return violations
    
    async def _analyze_single_content_smart(self, content_result: ContentResult, config: Dict[str, Any]) -> List[ViolationRecord]:
        """智能分析单个内容"""
        violations = []
        
        try:
            # 步骤1：智能预筛选
            needs_ai, reason, analysis_details = await self.prefilter.should_analyze_with_ai(content_result)
            
            self.performance_stats['total_processed'] += 1
            
            if not needs_ai:
                # 跳过AI分析，记录原因
                self.performance_stats['ai_calls_skipped'] += 1
                self.logger.debug(f"跳过AI分析 {content_result.url}: {reason}")
                
                # 如果预筛选发现明显的低风险特征，创建一个低风险记录
                if self._should_create_low_risk_record(reason, analysis_details):
                    violation = self._create_low_risk_violation_record(content_result, reason, analysis_details)
                    violations.append(violation)
                
                return violations
            
            # 步骤2：执行完整AI分析
            self.performance_stats['ai_calls_made'] += 1
            ai_violations = await self._perform_full_ai_analysis(content_result, config, reason, analysis_details)
            violations.extend(ai_violations)
            
            return violations
            
        except Exception as e:
            self.logger.error(f"智能内容分析失败 {content_result.url}: {e}")
            return []
    
    async def _perform_full_ai_analysis(self, content_result: ContentResult, config: Dict[str, Any], trigger_reason: str, prefilter_details: Dict[str, Any]) -> List[ViolationRecord]:
        """执行完整的AI分析"""
        violations = []
        
        try:
            # 初始化AI引擎（如果需要）
            if not self.ai_engine:
                await self._initialize_ai_engine()
            
            if not self.ai_engine:
                self.logger.warning("AI引擎初始化失败，无法进行分析")
                return violations
            
            # 由于 AIAnalysisEngine 没有 analyze_single_content 方法，
            # 我们需要创建一个适配器方法来处理 ContentResult
            ai_violations = await self._adapt_content_to_ai_analysis(content_result)
            
            # 增强违规记录信息
            for violation in ai_violations:
                # 添加预筛选信息到违规记录
                if hasattr(violation, 'metadata') and violation.metadata:
                    metadata = json.loads(violation.metadata)
                else:
                    metadata = {}
                
                metadata.update({
                    'prefilter_trigger': trigger_reason,
                    'prefilter_details': prefilter_details,
                    'analysis_method': 'full_ai_with_prefilter',
                    'processing_timestamp': datetime.utcnow().isoformat()
                })
                
                violation.metadata = json.dumps(metadata)
                violations.append(violation)
            
            self.performance_stats['total_violations_found'] += len(violations)
            
        except Exception as e:
            self.logger.error(f"完整AI分析失败: {e}")
        
        return violations
    
    async def _adapt_content_to_ai_analysis(self, content_result: ContentResult) -> List[ViolationRecord]:
        """适配 ContentResult 到 AIAnalysisEngine 的分析流程"""
        violations = []
        
        try:
            # 由于 AIAnalysisEngine 主要针对 ThirdPartyDomain 设计，
            # 我们需要创建一个模拟的 domain 对象或者直接使用其内部方法
            from app.models.task import ThirdPartyDomain
            
            # 创建一个模拟的 ThirdPartyDomain 对象
            mock_domain = ThirdPartyDomain()
            setattr(mock_domain, 'domain', content_result.domain)
            setattr(mock_domain, 'screenshot_path', content_result.screenshot_path)
            setattr(mock_domain, 'page_title', getattr(content_result, 'title', ''))
            setattr(mock_domain, 'page_description', getattr(content_result, 'description', ''))
            setattr(mock_domain, 'found_on_url', content_result.url)
            setattr(mock_domain, 'domain_type', 'content_analysis')
            setattr(mock_domain, 'is_analyzed', False)
            
            # 使用 AIAnalysisEngine 的内部方法进行分析
            if not self.ai_engine:
                raise ValueError("AI引擎未初始化")
            
            result = await self.ai_engine._analyze_single_domain(mock_domain)
            
            # 如果发现违规，创建违规记录
            if result.has_violation:
                violation = await self._create_content_violation_record(content_result, result)
                violations.append(violation)
                
        except Exception as e:
            self.logger.error(f"适配器分析失败: {e}")
        
        return violations
    
    async def _create_content_violation_record(self, content_result: ContentResult, ai_result) -> ViolationRecord:
        """为 ContentResult 创建违规记录"""
        violation = ViolationRecord()
        setattr(violation, 'task_id', self.task_id)
        setattr(violation, 'url', content_result.url)
        setattr(violation, 'domain', content_result.domain)
        setattr(violation, 'violation_type', ', '.join(ai_result.violation_types))
        setattr(violation, 'risk_level', ai_result.risk_level)
        setattr(violation, 'confidence_score', ai_result.confidence_score)
        setattr(violation, 'title', ai_result.title)
        setattr(violation, 'description', ai_result.description)
        setattr(violation, 'evidence', json.dumps(ai_result.evidence) if ai_result.evidence else None)
        setattr(violation, 'ai_model_used', self.ai_engine.ai_config.ai_model_name if self.ai_engine else "unknown")
        setattr(violation, 'screenshot_path', content_result.screenshot_path)
        setattr(violation, 'detected_at', datetime.utcnow())
        
        # 添加元数据
        metadata = {
            'analysis_method': 'full_ai_with_prefilter',
            'ai_analysis_duration': getattr(ai_result, 'analysis_duration', 0),
            'content_type': getattr(content_result, 'content_type', 'unknown'),
            'processing_timestamp': datetime.utcnow().isoformat()
        }
        violation.metadata = json.dumps(metadata)
        
        return violation
    
    def _should_create_low_risk_record(self, reason: str, analysis_details: Dict[str, Any]) -> bool:
        """判断是否应该创建低风险记录"""
        # 对于某些特定的跳过原因，我们仍然创建一个记录以便追踪
        create_record_reasons = [
            'low_score',
            'below_threshold',
            'random_skip'
        ]
        
        return any(create_reason in reason for create_reason in create_record_reasons)
    
    def _create_low_risk_violation_record(self, content_result: ContentResult, reason: str, analysis_details: Dict[str, Any]) -> ViolationRecord:
        """创建低风险违规记录"""
        violation = ViolationRecord()
        setattr(violation, 'task_id', self.task_id)
        setattr(violation, 'url', content_result.url)
        setattr(violation, 'domain', content_result.domain)
        setattr(violation, 'violation_type', "low_risk_content")
        setattr(violation, 'risk_level', RiskLevel.LOW)
        setattr(violation, 'confidence_score', 0.1)  # 低置信度
        setattr(violation, 'title', "低风险内容")
        setattr(violation, 'description', f"通过智能预筛选识别为低风险内容: {reason}")
        setattr(violation, 'evidence', json.dumps(analysis_details))
        setattr(violation, 'ai_model_used', "prefilter_only")
        setattr(violation, 'screenshot_path', content_result.screenshot_path)
        setattr(violation, 'detected_at', datetime.utcnow())
        
        # 添加元数据
        metadata = {
            'analysis_method': 'prefilter_only',
            'skip_reason': reason,
            'prefilter_details': analysis_details,
            'cost_saved': True
        }
        violation.metadata = json.dumps(metadata)
        
        return violation
    
    async def _initialize_ai_engine(self):
        """初始化AI引擎"""
        try:
            from app.core.database import AsyncSessionLocal
            
            async with AsyncSessionLocal() as db:
                ai_config = await db.get(UserAIConfig, self.user_id)
                if ai_config:
                    self.ai_engine = AIAnalysisEngine(self.task_id, ai_config)
                    self.logger.info("AI引擎初始化成功")
                else:
                    self.logger.warning("未找到用户AI配置")
                    
        except Exception as e:
            self.logger.error(f"AI引擎初始化失败: {e}")
    
    def _update_performance_stats(self, total_processed: int, violations_found: int, duration: float):
        """更新性能统计"""
        self.performance_stats['avg_processing_time'] = (
            self.performance_stats['avg_processing_time'] + duration
        ) / 2 if self.performance_stats['avg_processing_time'] > 0 else duration
        
        # 估算节省的成本（基于跳过的AI调用）
        # 假设每次GPT-4V调用成本约$0.01
        cost_per_call = 0.01
        self.performance_stats['cost_saved_estimate'] += (
            self.performance_stats['ai_calls_skipped'] * cost_per_call
        )
        
        # 获取预筛选器的缓存命中率
        prefilter_stats = self.prefilter.get_efficiency_stats()
        if 'cache_hit_rate' in prefilter_stats:
            self.performance_stats['cache_hit_rate'] = float(
                prefilter_stats['cache_hit_rate'].replace('%', '')
            ) / 100
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        prefilter_stats = self.prefilter.get_efficiency_stats()
        
        return {
            'analysis_performance': self.performance_stats.copy(),
            'prefilter_efficiency': prefilter_stats,
            'optimization_metrics': {
                'ai_skip_rate': f"{(self.performance_stats['ai_calls_skipped'] / max(self.performance_stats['total_processed'], 1) * 100):.1f}%",
                'violations_per_ai_call': self.performance_stats['total_violations_found'] / max(self.performance_stats['ai_calls_made'], 1),
                'estimated_cost_savings': f"${self.performance_stats['cost_saved_estimate']:.3f}",
                'avg_processing_time': f"{self.performance_stats['avg_processing_time']:.2f}s"
            }
        }
    
    async def analyze_single_content(self, content_result: ContentResult) -> List[ViolationRecord]:
        """分析单个内容（兼容性方法）"""
        return await self._analyze_single_content_smart(content_result, {})
    
    async def cleanup(self):
        """清理资源"""
        try:
            await self.prefilter.clear_cache()
            # AIAnalysisEngine 没有 cleanup 方法，只清理预筛选器
            self.logger.info("增强AI分析引擎清理完成")
        except Exception as e:
            self.logger.warning(f"清理过程中出现异常: {e}")


class AIAnalysisOptimizer:
    """AI分析优化器"""
    
    def __init__(self):
        self.optimization_rules = {
            'batch_size_optimization': True,
            'concurrent_limit_adjustment': True,
            'cache_management': True,
            'cost_optimization': True
        }
    
    def optimize_batch_size(self, total_items: int, avg_processing_time: float) -> int:
        """优化批处理大小"""
        if avg_processing_time < 1.0:
            return min(20, total_items)  # 快速处理，增加批大小
        elif avg_processing_time < 5.0:
            return min(10, total_items)  # 中等速度
        else:
            return min(5, total_items)   # 慢速处理，减少批大小
    
    def optimize_concurrent_limit(self, ai_skip_rate: float) -> int:
        """根据AI跳过率优化并发限制"""
        if ai_skip_rate > 0.8:  # 高跳过率，可以增加并发
            return 5
        elif ai_skip_rate > 0.5:  # 中等跳过率
            return 3
        else:  # 低跳过率，减少并发避免API限制
            return 2
    
    def should_enable_aggressive_caching(self, cache_hit_rate: float) -> bool:
        """判断是否启用激进缓存策略"""
        return cache_hit_rate > 0.3  # 缓存命中率高于30%时启用