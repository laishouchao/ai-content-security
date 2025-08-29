"""
进度监控系统
为无限迭代爬虫提供实时进度显示、统计信息和性能监控

核心功能：
1. 实时进度跟踪和显示
2. 性能指标监控
3. 资源使用监控
4. 错误和警告统计
5. 阶段性报告生成
6. WebSocket实时推送
7. 历史数据记录
"""

import asyncio
import time
import psutil
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque, defaultdict
from enum import Enum
import json
import threading
from concurrent.futures import ThreadPoolExecutor

from app.core.logging import TaskLogger


class MonitoringPhase(Enum):
    """监控阶段"""
    INITIALIZING = "initializing"
    SUBDOMAIN_DISCOVERY = "subdomain_discovery"
    CONTENT_CRAWLING = "content_crawling"
    DOMAIN_EXTRACTION = "domain_extraction"
    AI_ANALYSIS = "ai_analysis"
    DATA_PROCESSING = "data_processing"
    COMPLETED = "completed"
    ERROR = "error"
    PAUSED = "paused"


@dataclass
class ProgressSnapshot:
    """进度快照"""
    timestamp: datetime
    phase: MonitoringPhase
    
    # 基础进度
    total_domains: int = 0
    processed_domains: int = 0
    pending_domains: int = 0
    
    # 队列状态
    subdomain_queue_size: int = 0
    crawl_queue_size: int = 0
    analysis_queue_size: int = 0
    
    # 统计数据
    domains_per_minute: float = 0.0
    pages_crawled: int = 0
    links_extracted: int = 0
    violations_found: int = 0
    
    # 性能指标
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    network_requests: int = 0
    
    # 错误统计
    error_count: int = 0
    warning_count: int = 0
    
    # 估算信息
    estimated_completion: Optional[datetime] = None
    estimated_remaining_time: Optional[timedelta] = None


@dataclass 
class PerformanceMetrics:
    """性能指标"""
    # 处理速度
    domains_per_second: float = 0.0
    pages_per_second: float = 0.0
    analysis_per_second: float = 0.0
    
    # 响应时间
    avg_response_time: float = 0.0
    max_response_time: float = 0.0
    min_response_time: float = 0.0
    
    # 成功率
    success_rate: float = 0.0
    ai_success_rate: float = 0.0
    
    # 资源使用
    peak_memory_usage: float = 0.0
    avg_cpu_usage: float = 0.0
    
    # 网络统计
    total_requests: int = 0
    failed_requests: int = 0
    timeout_requests: int = 0


class ProgressMonitor:
    """进度监控器"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        # 监控状态
        self.current_phase = MonitoringPhase.INITIALIZING
        self.start_time = datetime.now()
        self.is_running = False
        self.is_paused = False
        
        # 进度数据
        self.progress_history: deque = deque(maxlen=1000)  # 保留最近1000个快照
        self.current_snapshot = ProgressSnapshot(
            timestamp=datetime.now(),
            phase=self.current_phase
        )
        
        # 性能指标
        self.performance_metrics = PerformanceMetrics()
        self.response_times: deque = deque(maxlen=100)  # 最近100个响应时间
        
        # 计数器
        self.counters = defaultdict(int)
        self.rates = defaultdict(float)
        
        # 回调函数
        self.progress_callbacks: List[Callable] = []
        self.phase_callbacks: Dict[MonitoringPhase, List[Callable]] = defaultdict(list)
        
        # 监控线程
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # 历史记录
        self.phase_durations: Dict[str, timedelta] = {}
        self.phase_start_times: Dict[str, datetime] = {}
    
    async def start_monitoring(self):
        """开始监控"""
        if self.is_running:
            return
        
        self.is_running = True
        self.start_time = datetime.now()
        self.current_phase = MonitoringPhase.INITIALIZING
        
        # 启动监控线程
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        self.logger.info("进度监控已启动")
    
    async def stop_monitoring(self):
        """停止监控"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.stop_event.set()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        await self._generate_final_report()
        self.logger.info("进度监控已停止")
    
    def update_phase(self, new_phase: MonitoringPhase):
        """更新当前阶段"""
        if new_phase == self.current_phase:
            return
        
        # 记录上一阶段的持续时间
        if self.current_phase.value in self.phase_start_times:
            duration = datetime.now() - self.phase_start_times[self.current_phase.value]
            self.phase_durations[self.current_phase.value] = duration
        
        old_phase = self.current_phase
        self.current_phase = new_phase
        self.phase_start_times[new_phase.value] = datetime.now()
        
        # 触发阶段回调
        for callback in self.phase_callbacks[new_phase]:
            try:
                asyncio.create_task(callback(old_phase, new_phase))
            except Exception as e:
                self.logger.error(f"阶段回调执行失败: {e}")
        
        self.logger.info(f"阶段切换: {old_phase.value} -> {new_phase.value}")
    
    def update_progress(self, **kwargs):
        """更新进度数据"""
        for key, value in kwargs.items():
            if hasattr(self.current_snapshot, key):
                setattr(self.current_snapshot, key, value)
            else:
                self.counters[key] = value
        
        self.current_snapshot.timestamp = datetime.now()
        
        # 计算速率
        self._update_rates()
        
        # 估算完成时间
        self._estimate_completion_time()
    
    def record_response_time(self, response_time: float):
        """记录响应时间"""
        self.response_times.append(response_time)
        
        # 更新性能指标
        if self.response_times:
            self.performance_metrics.avg_response_time = sum(self.response_times) / len(self.response_times)
            self.performance_metrics.max_response_time = max(self.response_times)
            self.performance_metrics.min_response_time = min(self.response_times)
    
    def increment_counter(self, counter_name: str, amount: int = 1):
        """增加计数器"""
        self.counters[counter_name] += amount
        
        # 更新对应的快照字段
        if counter_name == "domains_processed":
            self.current_snapshot.processed_domains = self.counters[counter_name]
        elif counter_name == "pages_crawled":
            self.current_snapshot.pages_crawled = self.counters[counter_name]
        elif counter_name == "links_extracted":
            self.current_snapshot.links_extracted = self.counters[counter_name]
        elif counter_name == "violations_found":
            self.current_snapshot.violations_found = self.counters[counter_name]
        elif counter_name == "errors":
            self.current_snapshot.error_count = self.counters[counter_name]
        elif counter_name == "warnings":
            self.current_snapshot.warning_count = self.counters[counter_name]
    
    def get_current_progress(self) -> Dict[str, Any]:
        """获取当前进度"""
        total_time = datetime.now() - self.start_time
        
        return {
            'task_id': self.task_id,
            'phase': self.current_phase.value,
            'is_running': self.is_running,
            'is_paused': self.is_paused,
            'start_time': self.start_time.isoformat(),
            'elapsed_time': str(total_time),
            'progress_snapshot': {
                'timestamp': self.current_snapshot.timestamp.isoformat(),
                'total_domains': self.current_snapshot.total_domains,
                'processed_domains': self.current_snapshot.processed_domains,
                'pending_domains': self.current_snapshot.pending_domains,
                'progress_percentage': self._calculate_progress_percentage(),
                'queue_sizes': {
                    'subdomain_queue': self.current_snapshot.subdomain_queue_size,
                    'crawl_queue': self.current_snapshot.crawl_queue_size,
                    'analysis_queue': self.current_snapshot.analysis_queue_size
                },
                'statistics': {
                    'domains_per_minute': self.current_snapshot.domains_per_minute,
                    'pages_crawled': self.current_snapshot.pages_crawled,
                    'links_extracted': self.current_snapshot.links_extracted,
                    'violations_found': self.current_snapshot.violations_found
                },
                'performance': {
                    'cpu_usage': self.current_snapshot.cpu_usage,
                    'memory_usage': self.current_snapshot.memory_usage,
                    'avg_response_time': self.performance_metrics.avg_response_time
                },
                'errors': {
                    'error_count': self.current_snapshot.error_count,
                    'warning_count': self.current_snapshot.warning_count
                },
                'estimation': {
                    'estimated_completion': self.current_snapshot.estimated_completion.isoformat() if self.current_snapshot.estimated_completion else None,
                    'estimated_remaining_time': str(self.current_snapshot.estimated_remaining_time) if self.current_snapshot.estimated_remaining_time else None
                }
            },
            'performance_metrics': {
                'domains_per_second': self.performance_metrics.domains_per_second,
                'success_rate': self.performance_metrics.success_rate,
                'peak_memory_usage': self.performance_metrics.peak_memory_usage,
                'total_requests': self.performance_metrics.total_requests
            }
        }
    
    def get_phase_summary(self) -> Dict[str, Any]:
        """获取阶段总结"""
        return {
            'current_phase': self.current_phase.value,
            'phase_durations': {k: str(v) for k, v in self.phase_durations.items()},
            'total_phases': len(MonitoringPhase),
            'completed_phases': len(self.phase_durations)
        }
    
    def add_progress_callback(self, callback: Callable):
        """添加进度回调"""
        self.progress_callbacks.append(callback)
    
    def add_phase_callback(self, phase: MonitoringPhase, callback: Callable):
        """添加阶段回调"""
        self.phase_callbacks[phase].append(callback)
    
    def _monitoring_loop(self):
        """监控循环（在单独线程中运行）"""
        while not self.stop_event.is_set() and self.is_running:
            try:
                # 更新系统资源使用情况
                self._update_system_metrics()
                
                # 保存快照
                self._save_snapshot()
                
                # 触发进度回调
                self._trigger_progress_callbacks()
                
                # 等待1秒
                self.stop_event.wait(1.0)
                
            except Exception as e:
                self.logger.error(f"监控循环异常: {e}")
                time.sleep(1)
    
    def _update_system_metrics(self):
        """更新系统指标"""
        try:
            # CPU使用率
            self.current_snapshot.cpu_usage = psutil.cpu_percent(interval=0.1)
            
            # 内存使用率
            memory = psutil.virtual_memory()
            self.current_snapshot.memory_usage = memory.percent
            
            # 更新峰值内存使用
            if memory.percent > self.performance_metrics.peak_memory_usage:
                self.performance_metrics.peak_memory_usage = memory.percent
            
        except Exception as e:
            self.logger.debug(f"系统指标更新失败: {e}")
    
    def _update_rates(self):
        """更新速率计算"""
        if len(self.progress_history) < 2:
            return
        
        current = self.current_snapshot
        previous = self.progress_history[-1]
        
        time_diff = (current.timestamp - previous.timestamp).total_seconds()
        if time_diff > 0:
            # 计算域名处理速率
            domain_diff = current.processed_domains - previous.processed_domains
            self.current_snapshot.domains_per_minute = (domain_diff / time_diff) * 60
            
            # 更新性能指标
            self.performance_metrics.domains_per_second = domain_diff / time_diff
    
    def _calculate_progress_percentage(self) -> float:
        """计算进度百分比"""
        if self.current_snapshot.total_domains == 0:
            return 0.0
        
        return (self.current_snapshot.processed_domains / self.current_snapshot.total_domains) * 100
    
    def _estimate_completion_time(self):
        """估算完成时间"""
        if (self.current_snapshot.domains_per_minute <= 0 or 
            self.current_snapshot.pending_domains <= 0):
            return
        
        remaining_minutes = self.current_snapshot.pending_domains / self.current_snapshot.domains_per_minute
        self.current_snapshot.estimated_remaining_time = timedelta(minutes=remaining_minutes)
        self.current_snapshot.estimated_completion = datetime.now() + self.current_snapshot.estimated_remaining_time
    
    def _save_snapshot(self):
        """保存进度快照"""
        snapshot_copy = ProgressSnapshot(
            timestamp=self.current_snapshot.timestamp,
            phase=self.current_snapshot.phase,
            total_domains=self.current_snapshot.total_domains,
            processed_domains=self.current_snapshot.processed_domains,
            pending_domains=self.current_snapshot.pending_domains,
            subdomain_queue_size=self.current_snapshot.subdomain_queue_size,
            crawl_queue_size=self.current_snapshot.crawl_queue_size,
            analysis_queue_size=self.current_snapshot.analysis_queue_size,
            domains_per_minute=self.current_snapshot.domains_per_minute,
            pages_crawled=self.current_snapshot.pages_crawled,
            links_extracted=self.current_snapshot.links_extracted,
            violations_found=self.current_snapshot.violations_found,
            cpu_usage=self.current_snapshot.cpu_usage,
            memory_usage=self.current_snapshot.memory_usage,
            error_count=self.current_snapshot.error_count,
            warning_count=self.current_snapshot.warning_count
        )
        
        self.progress_history.append(snapshot_copy)
    
    def _trigger_progress_callbacks(self):
        """触发进度回调"""
        for callback in self.progress_callbacks:
            try:
                # 在新的事件循环中执行异步回调
                asyncio.run_coroutine_threadsafe(
                    callback(self.get_current_progress()),
                    asyncio.get_event_loop()
                )
            except Exception as e:
                self.logger.error(f"进度回调执行失败: {e}")
    
    async def _generate_final_report(self):
        """生成最终报告"""
        total_time = datetime.now() - self.start_time
        
        report = {
            'task_id': self.task_id,
            'start_time': self.start_time.isoformat(),
            'end_time': datetime.now().isoformat(),
            'total_duration': str(total_time),
            'final_phase': self.current_phase.value,
            'phase_durations': {k: str(v) for k, v in self.phase_durations.items()},
            'final_statistics': {
                'total_domains': self.current_snapshot.total_domains,
                'processed_domains': self.current_snapshot.processed_domains,
                'pages_crawled': self.current_snapshot.pages_crawled,
                'links_extracted': self.current_snapshot.links_extracted,
                'violations_found': self.current_snapshot.violations_found,
                'error_count': self.current_snapshot.error_count,
                'warning_count': self.current_snapshot.warning_count
            },
            'performance_summary': {
                'avg_domains_per_second': self.performance_metrics.domains_per_second,
                'avg_response_time': self.performance_metrics.avg_response_time,
                'peak_memory_usage': self.performance_metrics.peak_memory_usage,
                'success_rate': self.performance_metrics.success_rate
            }
        }
        
        self.logger.info(f"爬虫任务完成报告: {json.dumps(report, ensure_ascii=False, indent=2)}")


# 便捷函数
async def create_progress_monitor(task_id: str, user_id: str) -> ProgressMonitor:
    """创建并启动进度监控器"""
    monitor = ProgressMonitor(task_id, user_id)
    await monitor.start_monitoring()
    return monitor


def format_progress_display(progress: Dict[str, Any]) -> str:
    """格式化进度显示"""
    snapshot = progress['progress_snapshot']
    
    return f"""
📊 任务进度 [{progress['task_id']}]
🔄 当前阶段: {progress['phase']}
⏱️ 运行时间: {progress['elapsed_time']}
📈 总进度: {snapshot['progress_percentage']:.1f}% ({snapshot['processed_domains']}/{snapshot['total_domains']})

📋 队列状态:
   子域名发现: {snapshot['queue_sizes']['subdomain_queue']}
   内容爬取: {snapshot['queue_sizes']['crawl_queue']} 
   AI分析: {snapshot['queue_sizes']['analysis_queue']}

📊 统计信息:
   处理速度: {snapshot['statistics']['domains_per_minute']:.1f} 域名/分钟
   页面爬取: {snapshot['statistics']['pages_crawled']}
   链接提取: {snapshot['statistics']['links_extracted']}
   违规发现: {snapshot['statistics']['violations_found']}

💻 系统性能:
   CPU使用: {snapshot['performance']['cpu_usage']:.1f}%
   内存使用: {snapshot['performance']['memory_usage']:.1f}%
   响应时间: {snapshot['performance']['avg_response_time']:.3f}s

⚠️ 错误统计:
   错误: {snapshot['errors']['error_count']}
   警告: {snapshot['errors']['warning_count']}

⏰ 预估完成: {snapshot['estimation']['estimated_remaining_time'] or '计算中...'}
    """.strip()