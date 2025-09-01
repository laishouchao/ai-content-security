"""
性能监控数据模型

用于存储系统性能日志和监控数据
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, BigInteger, Float, DateTime, JSON, Text, Index
from sqlalchemy.ext.declarative import declarative_base

from app.core.database import Base


class PerformanceLog(Base):
    """性能日志模型"""
    __tablename__ = "performance_logs"
    
    # 基础信息
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 时间戳（重要索引）
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # 系统指标
    cpu_percent = Column(Float, nullable=True)                    # CPU使用率 (%)
    memory_percent = Column(Float, nullable=True)                 # 内存使用率 (%)
    memory_available_mb = Column(Float, nullable=True)            # 可用内存 (MB)
    memory_total_mb = Column(Float, nullable=True)               # 总内存 (MB)
    disk_percent = Column(Float, nullable=True)                  # 磁盘使用率 (%)
    disk_free_gb = Column(Float, nullable=True)                  # 可用磁盘空间 (GB)
    disk_total_gb = Column(Float, nullable=True)                 # 总磁盘空间 (GB)
    
    # 网络指标
    network_bytes_sent = Column(BigInteger, nullable=True)          # 网络发送字节数
    network_bytes_recv = Column(BigInteger, nullable=True)          # 网络接收字节数
    network_packets_sent = Column(BigInteger, nullable=True)        # 网络发送包数
    network_packets_recv = Column(BigInteger, nullable=True)        # 网络接收包数
    
    # 进程指标
    process_count = Column(Integer, nullable=True)               # 进程数量
    thread_count = Column(Integer, nullable=True)                # 线程数量
    
    # 数据库指标
    db_active_connections = Column(Integer, nullable=True)       # 活跃数据库连接数
    db_total_connections = Column(Integer, nullable=True)        # 总数据库连接数
    db_query_count = Column(Integer, nullable=True)              # 查询次数
    db_avg_query_time = Column(Float, nullable=True)             # 平均查询时间 (ms)
    
    # Redis指标
    redis_connected = Column(Integer, nullable=True)             # Redis连接状态 (1=连接, 0=断开)
    redis_memory_usage_mb = Column(Float, nullable=True)         # Redis内存使用 (MB)
    redis_keys_count = Column(Integer, nullable=True)            # Redis键数量
    
    # Celery指标
    celery_active_tasks = Column(Integer, nullable=True)         # 活跃任务数
    celery_pending_tasks = Column(Integer, nullable=True)        # 等待任务数
    celery_failed_tasks = Column(Integer, nullable=True)         # 失败任务数
    celery_completed_tasks = Column(Integer, nullable=True)      # 完成任务数
    
    # 应用指标
    active_users = Column(Integer, nullable=True)                # 活跃用户数
    running_scan_tasks = Column(Integer, nullable=True)          # 运行中的扫描任务数
    total_violations = Column(Integer, nullable=True)            # 总违规数
    
    # 性能指标
    avg_response_time = Column(Float, nullable=True)             # 平均响应时间 (ms)
    error_rate = Column(Float, nullable=True)                    # 错误率 (%)
    request_count = Column(Integer, nullable=True)               # 请求数
    
    # 扩展数据
    extra_metrics = Column(JSON, nullable=True)                  # 额外性能指标
    error_details = Column(Text, nullable=True)                  # 错误详情
    
    # 索引优化
    __table_args__ = (
        Index('idx_performance_timestamp_hour', 'timestamp'),     # 按小时查询优化
        Index('idx_performance_cpu_memory', 'cpu_percent', 'memory_percent'),  # 资源使用查询优化
    )
    
    def __repr__(self):
        return f"<PerformanceLog(timestamp={self.timestamp}, cpu={self.cpu_percent}%, memory={self.memory_percent}%)>"
    
    @property
    def health_score(self) -> float:
        """计算健康分数 (0-100)"""
        score = 100.0
        
        # 获取实际的属性值
        cpu_val = getattr(self, 'cpu_percent', None)
        memory_val = getattr(self, 'memory_percent', None)
        disk_val = getattr(self, 'disk_percent', None)
        error_val = getattr(self, 'error_rate', None)
        
        # CPU权重 30%
        if cpu_val is not None:
            if cpu_val > 90:
                score -= 30
            elif cpu_val > 70:
                score -= 20
            elif cpu_val > 50:
                score -= 10
        
        # 内存权重 30%
        if memory_val is not None:
            if memory_val > 90:
                score -= 30
            elif memory_val > 80:
                score -= 20
            elif memory_val > 60:
                score -= 10
        
        # 磁盘权重 20%
        if disk_val is not None:
            if disk_val > 95:
                score -= 20
            elif disk_val > 85:
                score -= 15
            elif disk_val > 75:
                score -= 10
        
        # 错误率权重 20%
        if error_val is not None:
            if error_val > 10:
                score -= 20
            elif error_val > 5:
                score -= 15
            elif error_val > 1:
                score -= 10
        
        return max(0.0, score)
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        timestamp_val = getattr(self, 'timestamp', None)
        redis_connected_val = getattr(self, 'redis_connected', None)
        
        return {
            'id': self.id,
            'timestamp': timestamp_val.isoformat() if timestamp_val else None,
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'memory_available_mb': self.memory_available_mb,
            'memory_total_mb': self.memory_total_mb,
            'disk_percent': self.disk_percent,
            'disk_free_gb': self.disk_free_gb,
            'disk_total_gb': self.disk_total_gb,
            'network_bytes_sent': self.network_bytes_sent,
            'network_bytes_recv': self.network_bytes_recv,
            'db_active_connections': self.db_active_connections,
            'db_total_connections': self.db_total_connections,
            'redis_connected': bool(redis_connected_val) if redis_connected_val is not None else None,
            'redis_memory_usage_mb': self.redis_memory_usage_mb,
            'celery_active_tasks': self.celery_active_tasks,
            'celery_pending_tasks': self.celery_pending_tasks,
            'active_users': self.active_users,
            'running_scan_tasks': self.running_scan_tasks,
            'avg_response_time': self.avg_response_time,
            'error_rate': self.error_rate,
            'request_count': self.request_count,
            'health_score': self.health_score,
            'extra_metrics': self.extra_metrics,
        }


class PerformanceAlert(Base):
    """性能告警模型"""
    __tablename__ = "performance_alerts"
    
    # 基础信息
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 告警信息
    alert_type = Column(String(50), nullable=False, index=True)   # 告警类型 (cpu, memory, disk, etc.)
    severity = Column(String(20), nullable=False, index=True)     # 严重程度 (critical, warning, info)
    title = Column(String(200), nullable=False)                   # 告警标题
    message = Column(Text, nullable=False)                        # 告警消息
    
    # 指标值
    current_value = Column(Float, nullable=True)                  # 当前值
    threshold_value = Column(Float, nullable=True)                # 阈值
    
    # 状态管理
    is_active = Column(Integer, default=1, nullable=False, index=True)  # 是否活跃 (1=活跃, 0=已解决)
    resolved_at = Column(DateTime, nullable=True)                 # 解决时间
    
    # 时间戳
    triggered_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # 扩展信息
    extra_metadata = Column(JSON, nullable=True)                        # 元数据
    
    def __repr__(self):
        return f"<PerformanceAlert(type={self.alert_type}, severity={self.severity}, active={self.is_active})>"
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        triggered_at_val = getattr(self, 'triggered_at', None)
        resolved_at_val = getattr(self, 'resolved_at', None)
        
        return {
            'id': self.id,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'title': self.title,
            'message': self.message,
            'current_value': self.current_value,
            'threshold_value': self.threshold_value,
            'is_active': bool(self.is_active),
            'triggered_at': triggered_at_val.isoformat() if triggered_at_val else None,
            'resolved_at': resolved_at_val.isoformat() if resolved_at_val else None,
            'extra_metadata': self.extra_metadata,
        }