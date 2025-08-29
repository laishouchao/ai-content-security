"""
无限迭代控制器
实现真正的无限迭代循环逻辑，直至全部发现

核心特性：
1. 智能停止条件判断
2. 动态队列管理
3. 迭代深度控制
4. 性能监控和优化
5. 错误恢复机制

确保系统能够：
- 持续发现新域名直到没有新的发现
- 智能管理内存和资源使用
- 提供实时进度监控
- 处理各种异常情况
"""

import asyncio
import time
from typing import Dict, List, Set, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque, defaultdict
from enum import Enum
import gc

# 安全导入psutil
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

from app.core.logging import TaskLogger


class IterationPhase(Enum):
    """迭代阶段枚举"""
    INITIALIZING = "initializing"
    SUBDOMAIN_DISCOVERY = "subdomain_discovery"
    CONTENT_CRAWLING = "content_crawling"
    DOMAIN_EXTRACTION = "domain_extraction"
    AI_ANALYSIS = "ai_analysis"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class IterationMetrics:
    """迭代指标"""
    iteration_number: int
    phase: IterationPhase
    start_time: datetime
    end_time: Optional[datetime] = None
    domains_discovered: int = 0
    pages_crawled: int = 0
    links_extracted: int = 0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    queue_sizes: Dict[str, int] = field(default_factory=dict)
    error_count: int = 0
    warnings_count: int = 0


@dataclass
class StoppingCondition:
    """停止条件配置"""
    max_iterations: int = 100  # 最大迭代次数
    max_total_domains: int = 50000  # 最大域名总数
    max_runtime_hours: int = 24  # 最大运行时间（小时）
    consecutive_empty_iterations: int = 3  # 连续空迭代次数
    memory_limit_mb: int = 8192  # 内存限制（MB）
    cpu_limit_percent: int = 90  # CPU使用率限制
    min_discovery_rate: float = 0.01  # 最小发现率（新域名/总域名）


class InfiniteIterationController:
    """无限迭代控制器"""
    
    def __init__(self, task_id: str, user_id: str, target_domain: str):
        self.task_id = task_id
        self.user_id = user_id
        self.target_domain = target_domain
        self.logger = TaskLogger(task_id, user_id)
        
        # 迭代状态
        self.current_iteration = 0
        self.start_time = datetime.utcnow()
        self.current_phase = IterationPhase.INITIALIZING
        self.iteration_metrics: List[IterationMetrics] = []
        
        # 停止条件
        self.stopping_condition = StoppingCondition()
        self.consecutive_empty_count = 0
        self.last_discovery_rate = 1.0
        
        # 队列状态监控
        self.queue_status_history: List[Dict[str, int]] = []
        self.discovery_rate_history: List[float] = []
        self.performance_history: List[Dict[str, float]] = []
        
        # 动态调整参数
        self.adaptive_batch_size = 50
        self.adaptive_concurrent_limit = 20
        self.adaptive_delay = 1.0
        
        # 错误统计
        self.total_errors = 0
        self.total_warnings = 0
        self.error_patterns: Dict[str, int] = defaultdict(int)
    
    def configure_stopping_conditions(self, config: Dict[str, Any]):
        """配置停止条件"""
        if 'max_iterations' in config:
            self.stopping_condition.max_iterations = config['max_iterations']
        if 'max_total_domains' in config:
            self.stopping_condition.max_total_domains = config['max_total_domains']
        if 'max_runtime_hours' in config:
            self.stopping_condition.max_runtime_hours = config['max_runtime_hours']
        if 'consecutive_empty_iterations' in config:
            self.stopping_condition.consecutive_empty_iterations = config['consecutive_empty_iterations']
        if 'memory_limit_mb' in config:
            self.stopping_condition.memory_limit_mb = config['memory_limit_mb']
        if 'min_discovery_rate' in config:
            self.stopping_condition.min_discovery_rate = config['min_discovery_rate']
        
        self.logger.info(f"停止条件已配置: {self.stopping_condition}")
    
    def start_iteration(self, iteration_number: int) -> IterationMetrics:
        """开始新的迭代"""
        self.current_iteration = iteration_number
        self.current_phase = IterationPhase.SUBDOMAIN_DISCOVERY
        
        metrics = IterationMetrics(
            iteration_number=iteration_number,
            phase=self.current_phase,
            start_time=datetime.utcnow()
        )
        
        self.iteration_metrics.append(metrics)
        self.logger.info(f"开始第 {iteration_number} 次迭代")
        
        return metrics
    
    def update_phase(self, phase: IterationPhase):
        """更新当前阶段"""
        self.current_phase = phase
        if self.iteration_metrics:
            self.iteration_metrics[-1].phase = phase
        
        self.logger.debug(f"迭代阶段切换到: {phase.value}")
    
    def record_discovery(self, domains_count: int, pages_count: int = 0, links_count: int = 0):
        """记录发现结果"""
        if self.iteration_metrics:
            metrics = self.iteration_metrics[-1]
            metrics.domains_discovered += domains_count
            metrics.pages_crawled += pages_count
            metrics.links_extracted += links_count
    
    def record_queue_status(self, queue_sizes: Dict[str, int]):
        """记录队列状态"""
        self.queue_status_history.append(queue_sizes.copy())
        
        if self.iteration_metrics:
            self.iteration_metrics[-1].queue_sizes = queue_sizes.copy()
        
        # 保持历史记录在合理范围内
        if len(self.queue_status_history) > 1000:
            self.queue_status_history = self.queue_status_history[-500:]
    
    def record_performance_metrics(self):
        """记录性能指标"""
        try:
            if PSUTIL_AVAILABLE and psutil is not None:
                # 获取系统性能指标
                memory_info = psutil.virtual_memory()
                memory_usage_mb = memory_info.used / 1024 / 1024
                cpu_usage = psutil.cpu_percent(interval=0.1)
                memory_percent = memory_info.percent
            else:
                # 使用基本的内存监控
                import sys
                memory_usage_mb = sys.getsizeof(self) / 1024 / 1024  # 粗略估计
                cpu_usage = 0.0  # 无法获取CPU使用率
                memory_percent = memory_usage_mb / 1024  # 粗略估计
            
            performance_data = {
                'memory_usage_mb': memory_usage_mb,
                'cpu_usage_percent': cpu_usage,
                'memory_percent': memory_percent
            }
            
            self.performance_history.append(performance_data)
            
            if self.iteration_metrics:
                metrics = self.iteration_metrics[-1]
                metrics.memory_usage_mb = memory_usage_mb
                metrics.cpu_usage_percent = cpu_usage
            
            # 保持历史记录在合理范围内
            if len(self.performance_history) > 1000:
                self.performance_history = self.performance_history[-500:]
            
        except Exception as e:
            self.logger.warning(f"无法获取性能指标: {e}")
    
    def record_error(self, error_type: str, error_message: str):
        """记录错误"""
        self.total_errors += 1
        self.error_patterns[error_type] += 1
        
        if self.iteration_metrics:
            self.iteration_metrics[-1].error_count += 1
        
        self.logger.debug(f"记录错误: {error_type} - {error_message}")
    
    def record_warning(self, warning_message: str):
        """记录警告"""
        self.total_warnings += 1
        
        if self.iteration_metrics:
            self.iteration_metrics[-1].warnings_count += 1
    
    def end_iteration(self, new_domains_found: int, total_domains: int) -> bool:
        """结束当前迭代，返回是否应该继续"""
        if self.iteration_metrics:
            metrics = self.iteration_metrics[-1]
            metrics.end_time = datetime.utcnow()
            metrics.phase = IterationPhase.COMPLETED
        
        # 计算发现率
        discovery_rate = new_domains_found / max(total_domains, 1)
        self.discovery_rate_history.append(discovery_rate)
        self.last_discovery_rate = discovery_rate
        
        # 更新连续空迭代计数
        if new_domains_found == 0:
            self.consecutive_empty_count += 1
        else:
            self.consecutive_empty_count = 0
        
        # 记录性能指标
        self.record_performance_metrics()
        
        # 自适应调整参数
        self._adaptive_parameter_adjustment(new_domains_found, total_domains)
        
        # 判断是否应该继续迭代
        should_continue = self._should_continue_iteration(new_domains_found, total_domains)
        
        duration = (datetime.utcnow() - self.start_time).total_seconds()
        self.logger.info(f"第 {self.current_iteration} 次迭代完成: "
                        f"新发现 {new_domains_found} 个域名，"
                        f"总计 {total_domains} 个域名，"
                        f"发现率 {discovery_rate:.4f}，"
                        f"是否继续: {should_continue}")
        
        return should_continue
    
    def _should_continue_iteration(self, new_domains_found: int, total_domains: int) -> bool:
        """判断是否应该继续迭代"""
        # 检查各种停止条件
        
        # 1. 最大迭代次数
        if self.current_iteration >= self.stopping_condition.max_iterations:
            self.logger.info(f"达到最大迭代次数限制: {self.stopping_condition.max_iterations}")
            return False
        
        # 2. 最大域名数量
        if total_domains >= self.stopping_condition.max_total_domains:
            self.logger.info(f"达到最大域名数量限制: {self.stopping_condition.max_total_domains}")
            return False
        
        # 3. 最大运行时间
        runtime_hours = (datetime.utcnow() - self.start_time).total_seconds() / 3600
        if runtime_hours >= self.stopping_condition.max_runtime_hours:
            self.logger.info(f"达到最大运行时间限制: {runtime_hours:.2f} 小时")
            return False
        
        # 4. 连续空迭代
        if self.consecutive_empty_count >= self.stopping_condition.consecutive_empty_iterations:
            self.logger.info(f"连续 {self.consecutive_empty_count} 次空迭代，停止发现")
            return False
        
        # 5. 内存限制
        if PSUTIL_AVAILABLE and psutil is not None and self.iteration_metrics and self.iteration_metrics[-1].memory_usage_mb > self.stopping_condition.memory_limit_mb:
            self.logger.warning(f"内存使用超出限制: {self.iteration_metrics[-1].memory_usage_mb:.2f} MB")
            # 尝试垃圾回收
            gc.collect()
            # 如果仍然超出限制，停止迭代
            if PSUTIL_AVAILABLE and psutil is not None:
                current_memory = psutil.virtual_memory().used / 1024 / 1024
                if current_memory > self.stopping_condition.memory_limit_mb:
                    return False
        
        # 6. CPU限制
        if self.iteration_metrics and self.iteration_metrics[-1].cpu_usage_percent > self.stopping_condition.cpu_limit_percent:
            self.logger.warning(f"CPU使用率过高: {self.iteration_metrics[-1].cpu_usage_percent:.2f}%")
            # 增加延迟
            self.adaptive_delay = min(self.adaptive_delay * 1.5, 10.0)
        
        # 7. 发现率过低
        if len(self.discovery_rate_history) >= 5:
            recent_avg_rate = sum(self.discovery_rate_history[-5:]) / 5
            if recent_avg_rate < self.stopping_condition.min_discovery_rate:
                self.logger.info(f"最近发现率过低: {recent_avg_rate:.4f} < {self.stopping_condition.min_discovery_rate}")
                return False
        
        # 8. 队列状态检查
        if not self._has_pending_work():
            self.logger.info("所有工作队列为空，无待处理任务")
            return False
        
        return True
    
    def _has_pending_work(self) -> bool:
        """检查是否还有待处理的工作"""
        if not self.queue_status_history:
            return True  # 如果没有队列信息，假设有工作要做
        
        latest_status = self.queue_status_history[-1]
        total_pending = sum(latest_status.values())
        
        return total_pending > 0
    
    def _adaptive_parameter_adjustment(self, new_domains_found: int, total_domains: int):
        """自适应参数调整"""
        # 根据发现效率调整批处理大小
        if new_domains_found > 0:
            efficiency = new_domains_found / max(self.adaptive_batch_size, 1)
            if efficiency > 0.5:  # 高效率，增加批处理大小
                self.adaptive_batch_size = min(self.adaptive_batch_size * 1.2, 200)
            elif efficiency < 0.1:  # 低效率，减少批处理大小
                self.adaptive_batch_size = max(self.adaptive_batch_size * 0.8, 10)
        
        # 根据性能调整并发限制
        if self.iteration_metrics:
            latest_metrics = self.iteration_metrics[-1]
            if latest_metrics.cpu_usage_percent > 80:
                self.adaptive_concurrent_limit = max(self.adaptive_concurrent_limit - 2, 5)
            elif latest_metrics.cpu_usage_percent < 50:
                self.adaptive_concurrent_limit = min(self.adaptive_concurrent_limit + 2, 50)
        
        # 根据错误率调整延迟
        if self.iteration_metrics:
            latest_metrics = self.iteration_metrics[-1]
            if latest_metrics.error_count > 10:
                self.adaptive_delay = min(self.adaptive_delay * 1.3, 5.0)
            elif latest_metrics.error_count == 0:
                self.adaptive_delay = max(self.adaptive_delay * 0.9, 0.1)
        
        self.logger.debug(f"参数自适应调整: batch_size={self.adaptive_batch_size:.0f}, "
                         f"concurrent_limit={self.adaptive_concurrent_limit}, "
                         f"delay={self.adaptive_delay:.2f}")
    
    def get_adaptive_parameters(self) -> Dict[str, Any]:
        """获取自适应参数"""
        return {
            'batch_size': int(self.adaptive_batch_size),
            'concurrent_limit': self.adaptive_concurrent_limit,
            'delay': self.adaptive_delay
        }
    
    def get_iteration_summary(self) -> Dict[str, Any]:
        """获取迭代总结"""
        total_domains_discovered = sum(m.domains_discovered for m in self.iteration_metrics)
        total_pages_crawled = sum(m.pages_crawled for m in self.iteration_metrics)
        total_links_extracted = sum(m.links_extracted for m in self.iteration_metrics)
        
        runtime = (datetime.utcnow() - self.start_time).total_seconds()
        
        avg_memory_usage = 0
        avg_cpu_usage = 0
        if self.performance_history:
            avg_memory_usage = sum(p['memory_usage_mb'] for p in self.performance_history) / len(self.performance_history)
            avg_cpu_usage = sum(p['cpu_usage_percent'] for p in self.performance_history) / len(self.performance_history)
        
        return {
            'total_iterations': len(self.iteration_metrics),
            'total_runtime_seconds': runtime,
            'total_domains_discovered': total_domains_discovered,
            'total_pages_crawled': total_pages_crawled,
            'total_links_extracted': total_links_extracted,
            'consecutive_empty_iterations': self.consecutive_empty_count,
            'last_discovery_rate': self.last_discovery_rate,
            'average_discovery_rate': sum(self.discovery_rate_history) / max(len(self.discovery_rate_history), 1),
            'total_errors': self.total_errors,
            'total_warnings': self.total_warnings,
            'error_patterns': dict(self.error_patterns),
            'performance_metrics': {
                'average_memory_usage_mb': avg_memory_usage,
                'average_cpu_usage_percent': avg_cpu_usage,
                'peak_memory_usage_mb': max((p['memory_usage_mb'] for p in self.performance_history), default=0),
                'peak_cpu_usage_percent': max((p['cpu_usage_percent'] for p in self.performance_history), default=0)
            },
            'adaptive_parameters': self.get_adaptive_parameters(),
            'stopping_condition': {
                'max_iterations': self.stopping_condition.max_iterations,
                'max_total_domains': self.stopping_condition.max_total_domains,
                'max_runtime_hours': self.stopping_condition.max_runtime_hours,
                'consecutive_empty_iterations': self.stopping_condition.consecutive_empty_iterations,
                'min_discovery_rate': self.stopping_condition.min_discovery_rate
            }
        }
    
    def save_iteration_report(self, output_file: str):
        """保存迭代报告"""
        try:
            import json
            
            report = {
                'task_id': self.task_id,
                'target_domain': self.target_domain,
                'start_time': self.start_time.isoformat(),
                'end_time': datetime.utcnow().isoformat(),
                'summary': self.get_iteration_summary(),
                'iteration_details': [
                    {
                        'iteration': m.iteration_number,
                        'phase': m.phase.value,
                        'start_time': m.start_time.isoformat(),
                        'end_time': m.end_time.isoformat() if m.end_time else None,
                        'domains_discovered': m.domains_discovered,
                        'pages_crawled': m.pages_crawled,
                        'links_extracted': m.links_extracted,
                        'memory_usage_mb': m.memory_usage_mb,
                        'cpu_usage_percent': m.cpu_usage_percent,
                        'queue_sizes': m.queue_sizes,
                        'error_count': m.error_count,
                        'warnings_count': m.warnings_count
                    }
                    for m in self.iteration_metrics
                ],
                'discovery_rate_history': self.discovery_rate_history,
                'performance_history': self.performance_history
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"迭代报告已保存到: {output_file}")
            
        except Exception as e:
            self.logger.error(f"保存迭代报告失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        # 强制垃圾回收
        gc.collect()
        
        # 清理历史数据
        if len(self.queue_status_history) > 100:
            self.queue_status_history = self.queue_status_history[-50:]
        
        if len(self.performance_history) > 100:
            self.performance_history = self.performance_history[-50:]
        
        if len(self.discovery_rate_history) > 100:
            self.discovery_rate_history = self.discovery_rate_history[-50:]
        
        self.logger.debug("迭代控制器资源清理完成")