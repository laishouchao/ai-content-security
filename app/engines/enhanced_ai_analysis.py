import asyncio
import time
import json
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path

from app.core.logging import TaskLogger
from app.engines.ai_analysis import AIAnalysisEngine, AIAnalysisResult
from app.engines.content_capture import ContentResult
from app.models.task import ViolationRecord, RiskLevel
from app.models.user import UserAIConfig


class EnhancedAIAnalysisEngine:
    """增强的AI分析引擎（直接AI分析）"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        # 核心组件
        self.ai_engine = None  # 延迟初始化
        
        # 性能统计
        self.performance_stats = {
            'total_processed': 0,
            'ai_calls_made': 0,
            'total_violations_found': 0,
            'avg_processing_time': 0.0
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
        
        # 直接进行AI分析
        analysis_tasks = []
        for content_result in batch:
            analysis_tasks.append(self._analyze_single_content(content_result, config))
        
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
    
    async def _analyze_single_content(self, content_result: ContentResult, config: Dict[str, Any]) -> List[ViolationRecord]:
        """分析单个内容"""
        violations = []
        
        try:
            # 检查是否有有效的截图文件
            if not content_result.screenshot_path or not Path(content_result.screenshot_path).exists():
                self.logger.debug(f"跳过分析（无截图）: {content_result.url}")
                return violations
            
            # 检查文件大小
            file_size = Path(content_result.screenshot_path).stat().st_size
            if file_size < 1024:  # 小于1KB
                self.logger.debug(f"跳过分析（截图太小）: {content_result.url}")
                return violations
            
            # 直接执行AI分析
            self.performance_stats['total_processed'] += 1
            self.performance_stats['ai_calls_made'] += 1
            
            ai_violations = await self._perform_ai_analysis(content_result, config)
            violations.extend(ai_violations)
            
            return violations
            
        except Exception as e:
            self.logger.error(f"内容分析失败 {content_result.url}: {e}")
            return []
    
    async def _perform_ai_analysis(self, content_result: ContentResult, config: Dict[str, Any]) -> List[ViolationRecord]:
        """执行AI分析"""
        violations = []
        
        try:
            # 初始化AI引擎（如果需要）
            if not self.ai_engine:
                await self._initialize_ai_engine()
            
            if not self.ai_engine:
                self.logger.warning("AI引擎初始化失败，无法进行分析")
                return violations
            
            # 适配 ContentResult 到 AI 分析流程
            ai_violations = await self._adapt_content_to_ai_analysis(content_result)
            
            # 添加元数据到违规记录
            for violation in ai_violations:
                metadata = {
                    'analysis_method': 'direct_ai_analysis',
                    'processing_timestamp': datetime.utcnow().isoformat()
                }
                
                if hasattr(violation, 'metadata') and violation.metadata:
                    existing_metadata = json.loads(violation.metadata)
                    existing_metadata.update(metadata)
                    violation.metadata = json.dumps(existing_metadata)
                else:
                    violation.metadata = json.dumps(metadata)
                
                violations.append(violation)
            
            self.performance_stats['total_violations_found'] += len(violations)
            
        except Exception as e:
            self.logger.error(f"AI分析失败: {e}")
        
        return violations
    
    async def _adapt_content_to_ai_analysis(self, content_result: ContentResult) -> List[ViolationRecord]:
        """适配 ContentResult 到 AIAnalysisEngine 的分析流程"""
        violations = []
        
        try:
            # 由于 AIAnalysisEngine 主要针对 DomainRecord 设计，
            # 我们需要创建一个模拟的 domain 对象或者直接使用其内部方法
            from app.models.domain import DomainRecord
            
            # 创建一个模拟的 DomainRecord 对象
            mock_domain = DomainRecord()
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
            'analysis_method': 'direct_ai_analysis',
            'ai_analysis_duration': getattr(ai_result, 'analysis_duration', 0),
            'content_type': getattr(content_result, 'content_type', 'unknown'),
            'processing_timestamp': datetime.utcnow().isoformat()
        }
        violation.metadata = json.dumps(metadata)
        
        return violation
    
    async def _initialize_ai_engine(self):
        """初始化AI引擎"""
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.user import UserAIConfig
            from sqlalchemy import select
            from app.core.security import data_encryption
            
            async with AsyncSessionLocal() as db:
                stmt = select(UserAIConfig).where(UserAIConfig.user_id == self.user_id)
                result = await db.execute(stmt)
                ai_config = result.scalar_one_or_none()
                
                if ai_config:
                    # 解密API密钥
                    decrypted_api_key = None
                    if ai_config.openai_api_key is not None and str(ai_config.openai_api_key).strip() != '':
                        try:
                            decrypted_api_key = data_encryption.decrypt_data(str(ai_config.openai_api_key))
                        except Exception as e:
                            self.logger.warning(f"解密API密钥失败: {e}")
                            decrypted_api_key = None
                    
                    # 为了避免SQLAlchemy Column对象的类型检查问题，我们使用临时属性的方法
                    if decrypted_api_key:
                        # 临时替换加密的API密钥
                        original_api_key = ai_config.openai_api_key
                        
                        # 使用setattr来避免类型检查问题
                        setattr(ai_config, 'openai_api_key', decrypted_api_key)
                        
                        try:
                            self.ai_engine = AIAnalysisEngine(self.task_id, ai_config)
                            self.logger.info("AI引擎初始化成功")
                        finally:
                            # 恢复原始的加密密钥
                            setattr(ai_config, 'openai_api_key', original_api_key)
                    else:
                        self.logger.warning("无有效的API密钥，无法初始化AI引擎")
                else:
                    self.logger.warning("未找到用户AI配置")
                    
        except Exception as e:
            self.logger.error(f"AI引擎初始化失败: {e}")
    
    def _update_performance_stats(self, total_processed: int, violations_found: int, duration: float):
        """更新性能统计"""
        self.performance_stats['avg_processing_time'] = (
            self.performance_stats['avg_processing_time'] + duration
        ) / 2 if self.performance_stats['avg_processing_time'] > 0 else duration
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        return {
            'analysis_performance': self.performance_stats.copy(),
            'optimization_metrics': {
                'violations_per_ai_call': self.performance_stats['total_violations_found'] / max(self.performance_stats['ai_calls_made'], 1),
                'avg_processing_time': f"{self.performance_stats['avg_processing_time']:.2f}s"
            }
        }
    
    async def analyze_single_content(self, content_result: ContentResult) -> List[ViolationRecord]:
        """分析单个内容（兼容性方法）"""
        return await self._analyze_single_content(content_result, {})
    
    async def cleanup(self):
        """清理资源"""
        try:
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