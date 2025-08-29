"""
错误处理系统
为无限迭代爬虫提供全面的错误处理和容错机制

核心功能：
1. 智能重试机制
2. 异常分类和恢复
3. 超时控制
4. 熔断器模式
5. 错误统计和分析
6. 自动降级策略
7. 状态持久化和恢复
"""

import asyncio
import time
import random
from typing import Dict, List, Any, Optional, Callable, Union, Type
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum
import functools
import traceback
import pickle
import json

from app.core.logging import TaskLogger


class ErrorType(Enum):
    """错误类型"""
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    AUTH_ERROR = "auth_error"
    PARSING_ERROR = "parsing_error"
    DATABASE_ERROR = "database_error"
    AI_ERROR = "ai_error"
    VALIDATION_ERROR = "validation_error"
    RESOURCE_ERROR = "resource_error"
    UNKNOWN_ERROR = "unknown_error"


class RetryStrategy(Enum):
    """重试策略"""
    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    RANDOM_JITTER = "random_jitter"
    CUSTOM = "custom"


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True
    
    # 条件重试
    retry_on_exceptions: List[Type[Exception]] = field(default_factory=list)
    retry_on_status_codes: List[int] = field(default_factory=list)
    
    # 自定义重试判断
    should_retry: Optional[Callable[[Exception], bool]] = None


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5       # 失败次数阈值
    recovery_timeout: float = 30.0   # 恢复时间窗口
    success_threshold: int = 3       # 恢复成功次数阈值
    half_open_max_calls: int = 5     # 半开状态最大调用数


class CircuitBreakerState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 关闭：正常工作
    OPEN = "open"          # 开启：拒绝调用
    HALF_OPEN = "half_open"  # 半开：尝试恢复


@dataclass
class ErrorRecord:
    """错误记录"""
    timestamp: datetime
    error_type: ErrorType
    exception: Exception
    function_name: str
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    
    # 上下文信息
    domain: Optional[str] = None
    url: Optional[str] = None
    retry_count: int = 0
    
    # 错误详情
    error_message: str = ""
    stack_trace: str = ""
    
    def __post_init__(self):
        if not self.error_message:
            self.error_message = str(self.exception)
        if not self.stack_trace:
            self.stack_trace = traceback.format_exc()


class CircuitBreaker:
    """熔断器"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0
        
        self.call_count = 0
        self.success_rate = 1.0
    
    def can_execute(self) -> bool:
        """判断是否可以执行"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return self.half_open_calls < self.config.half_open_max_calls
        
        return False
    
    def record_success(self):
        """记录成功"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            self.half_open_calls += 1
            
            if self.success_count >= self.config.success_threshold:
                self._reset()
        else:
            self.failure_count = 0
        
        self.call_count += 1
        self._update_success_rate()
    
    def record_failure(self):
        """记录失败"""
        self.failure_count += 1
        self.success_count = 0
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_calls += 1
            self.state = CircuitBreakerState.OPEN
        elif self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN
        
        self.call_count += 1
        self._update_success_rate()
    
    def _should_attempt_reset(self) -> bool:
        """判断是否应该尝试重置"""
        if not self.last_failure_time:
            return True
        
        return (datetime.now() - self.last_failure_time).total_seconds() >= self.config.recovery_timeout
    
    def _reset(self):
        """重置熔断器"""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
    
    def _update_success_rate(self):
        """更新成功率"""
        if self.call_count > 0:
            success_calls = self.call_count - self.failure_count
            self.success_rate = success_calls / self.call_count


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = TaskLogger(task_id, user_id)
        
        # 错误记录
        self.error_history: deque = deque(maxlen=1000)
        self.error_stats: Dict[str, int] = defaultdict(int)
        
        # 熔断器管理
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # 重试配置
        self.default_retry_config = RetryConfig()
        self.function_retry_configs: Dict[str, RetryConfig] = {}
        
        # 错误分类映射
        self.error_type_mapping = self._init_error_mapping()
        
        # 状态持久化
        self.state_file = f"error_state_{task_id}.json"
        
        # 降级策略
        self.degradation_handlers: Dict[str, Callable] = {}
    
    def _init_error_mapping(self) -> Dict[Type[Exception], ErrorType]:
        """初始化错误类型映射"""
        return {
            asyncio.TimeoutError: ErrorType.TIMEOUT_ERROR,
            ConnectionError: ErrorType.NETWORK_ERROR,
            OSError: ErrorType.NETWORK_ERROR,
            ValueError: ErrorType.VALIDATION_ERROR,
            TypeError: ErrorType.VALIDATION_ERROR,
            KeyError: ErrorType.PARSING_ERROR,
            AttributeError: ErrorType.PARSING_ERROR,
            PermissionError: ErrorType.AUTH_ERROR,
            MemoryError: ErrorType.RESOURCE_ERROR,
        }
    
    def retry(
        self, 
        config: Optional[RetryConfig] = None,
        circuit_breaker: Optional[str] = None
    ):
        """重试装饰器"""
        def decorator(func: Callable):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                retry_config = config or self.function_retry_configs.get(func.__name__, self.default_retry_config)
                
                # 检查熔断器
                if circuit_breaker and not self._can_execute_with_circuit_breaker(circuit_breaker):
                    raise Exception(f"熔断器 {circuit_breaker} 已开启，拒绝执行")
                
                last_exception: Optional[Exception] = None
                
                # 确保至少尝试一次
                max_attempts = max(1, retry_config.max_attempts)
                
                for attempt in range(max_attempts):
                    try:
                        result = await func(*args, **kwargs)
                        
                        # 记录成功
                        if circuit_breaker:
                            self.circuit_breakers[circuit_breaker].record_success()
                        
                        return result
                        
                    except Exception as e:
                        last_exception = e
                        
                        # 记录错误
                        error_record = self._create_error_record(e, func.__name__, args, kwargs)
                        error_record.retry_count = attempt + 1
                        self.error_history.append(error_record)
                        
                        # 记录熔断器失败
                        if circuit_breaker:
                            self.circuit_breakers[circuit_breaker].record_failure()
                        
                        # 检查是否应该重试
                        if not self._should_retry(e, retry_config, attempt + 1):
                            break
                        
                        # 计算延迟时间
                        delay = self._calculate_retry_delay(retry_config, attempt + 1)
                        self.logger.warning(f"函数 {func.__name__} 第 {attempt + 1} 次重试失败，{delay:.2f}秒后重试: {e}")
                        
                        await asyncio.sleep(delay)
                
                # 所有重试都失败了
                if last_exception is not None:
                    self.logger.error(f"函数 {func.__name__} 重试 {max_attempts} 次后仍然失败: {last_exception}")
                    
                    # 尝试降级处理
                    if func.__name__ in self.degradation_handlers:
                        self.logger.info(f"执行降级处理: {func.__name__}")
                        return await self.degradation_handlers[func.__name__](*args, **kwargs)
                    
                    raise last_exception
                else:
                    # 这种情况理论上不应该发生，但为了类型安全
                    raise RuntimeError(f"函数 {func.__name__} 执行失败，但没有捕获到具体异常")
            
            return wrapper
        return decorator
    
    def timeout(self, seconds: float):
        """超时装饰器"""
        def decorator(func: Callable):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
                except asyncio.TimeoutError as e:
                    self.logger.warning(f"函数 {func.__name__} 执行超时 ({seconds}秒)")
                    error_record = self._create_error_record(e, func.__name__, args, kwargs)
                    self.error_history.append(error_record)
                    raise
            return wrapper
        return decorator
    
    def register_circuit_breaker(self, name: str, config: CircuitBreakerConfig):
        """注册熔断器"""
        self.circuit_breakers[name] = CircuitBreaker(name, config)
        self.logger.info(f"注册熔断器: {name}")
    
    def register_retry_config(self, function_name: str, config: RetryConfig):
        """注册重试配置"""
        self.function_retry_configs[function_name] = config
        self.logger.debug(f"注册重试配置: {function_name}")
    
    def register_degradation_handler(self, function_name: str, handler: Callable):
        """注册降级处理器"""
        self.degradation_handlers[function_name] = handler
        self.logger.debug(f"注册降级处理器: {function_name}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计"""
        if not self.error_history:
            return {}
        
        # 错误类型统计
        error_type_counts = defaultdict(int)
        function_error_counts = defaultdict(int)
        hourly_errors = defaultdict(int)
        
        for record in self.error_history:
            error_type_counts[record.error_type.value] += 1
            function_error_counts[record.function_name] += 1
            hour_key = record.timestamp.strftime('%Y-%m-%d %H:00')
            hourly_errors[hour_key] += 1
        
        # 熔断器状态
        circuit_breaker_status = {}
        for name, cb in self.circuit_breakers.items():
            circuit_breaker_status[name] = {
                'state': cb.state.value,
                'failure_count': cb.failure_count,
                'success_rate': cb.success_rate,
                'call_count': cb.call_count
            }
        
        return {
            'total_errors': len(self.error_history),
            'error_types': dict(error_type_counts),
            'function_errors': dict(function_error_counts),
            'hourly_errors': dict(hourly_errors),
            'circuit_breakers': circuit_breaker_status,
            'recent_errors': [
                {
                    'timestamp': record.timestamp.isoformat(),
                    'type': record.error_type.value,
                    'function': record.function_name,
                    'message': record.error_message[:200],
                    'retry_count': record.retry_count
                }
                for record in list(self.error_history)[-10:]  # 最近10个错误
            ]
        }
    
    async def save_state(self):
        """保存错误处理状态"""
        try:
            state = {
                'error_stats': dict(self.error_stats),
                'circuit_breaker_states': {
                    name: {
                        'state': cb.state.value,
                        'failure_count': cb.failure_count,
                        'success_count': cb.success_count,
                        'last_failure_time': cb.last_failure_time.isoformat() if cb.last_failure_time else None
                    }
                    for name, cb in self.circuit_breakers.items()
                }
            }
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            
            self.logger.debug("错误处理状态已保存")
        except Exception as e:
            self.logger.warning(f"保存错误处理状态失败: {e}")
    
    async def load_state(self):
        """加载错误处理状态"""
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            # 恢复错误统计
            if 'error_stats' in state:
                self.error_stats.update(state['error_stats'])
            
            # 恢复熔断器状态
            if 'circuit_breaker_states' in state:
                for name, cb_state in state['circuit_breaker_states'].items():
                    if name in self.circuit_breakers:
                        cb = self.circuit_breakers[name]
                        cb.state = CircuitBreakerState(cb_state['state'])
                        cb.failure_count = cb_state['failure_count']
                        cb.success_count = cb_state['success_count']
                        if cb_state['last_failure_time']:
                            cb.last_failure_time = datetime.fromisoformat(cb_state['last_failure_time'])
            
            self.logger.debug("错误处理状态已恢复")
        except FileNotFoundError:
            self.logger.debug("错误处理状态文件不存在，使用默认状态")
        except Exception as e:
            self.logger.warning(f"加载错误处理状态失败: {e}")
    
    def _classify_error(self, exception: Exception) -> ErrorType:
        """分类错误类型"""
        for exc_type, error_type in self.error_type_mapping.items():
            if isinstance(exception, exc_type):
                return error_type
        
        # 检查错误消息中的关键词
        error_msg = str(exception).lower()
        if any(keyword in error_msg for keyword in ['timeout', 'timed out']):
            return ErrorType.TIMEOUT_ERROR
        elif any(keyword in error_msg for keyword in ['rate limit', 'too many requests']):
            return ErrorType.RATE_LIMIT_ERROR
        elif any(keyword in error_msg for keyword in ['connection', 'network']):
            return ErrorType.NETWORK_ERROR
        elif any(keyword in error_msg for keyword in ['authentication', 'unauthorized']):
            return ErrorType.AUTH_ERROR
        
        return ErrorType.UNKNOWN_ERROR
    
    def _create_error_record(
        self, 
        exception: Exception, 
        function_name: str, 
        args: tuple, 
        kwargs: dict
    ) -> ErrorRecord:
        """创建错误记录"""
        error_type = self._classify_error(exception)
        
        # 从参数中提取上下文信息
        domain = None
        url = None
        
        if args:
            for arg in args:
                if isinstance(arg, str):
                    if '.' in arg and not arg.startswith('http'):
                        domain = arg
                    elif arg.startswith(('http://', 'https://')):
                        url = arg
        
        if kwargs:
            domain = domain or kwargs.get('domain')
            url = url or kwargs.get('url')
        
        return ErrorRecord(
            timestamp=datetime.now(),
            error_type=error_type,
            exception=exception,
            function_name=function_name,
            args=args,
            kwargs=kwargs,
            domain=domain,
            url=url
        )
    
    def _should_retry(self, exception: Exception, config: RetryConfig, attempt: int) -> bool:
        """判断是否应该重试"""
        if attempt >= config.max_attempts:
            return False
        
        # 自定义重试判断
        if config.should_retry:
            return config.should_retry(exception)
        
        # 检查异常类型
        if config.retry_on_exceptions:
            return any(isinstance(exception, exc_type) for exc_type in config.retry_on_exceptions)
        
        # 默认重试策略
        error_type = self._classify_error(exception)
        non_retryable_errors = [ErrorType.AUTH_ERROR, ErrorType.VALIDATION_ERROR]
        
        return error_type not in non_retryable_errors
    
    def _calculate_retry_delay(self, config: RetryConfig, attempt: int) -> float:
        """计算重试延迟"""
        if config.strategy == RetryStrategy.FIXED_DELAY:
            delay = config.base_delay
        elif config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = config.base_delay * (config.backoff_factor ** (attempt - 1))
        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = config.base_delay * attempt
        else:  # RANDOM_JITTER
            delay = config.base_delay * (2 ** (attempt - 1))
        
        # 添加随机抖动
        if config.jitter:
            jitter = delay * 0.1 * random.random()
            delay += jitter
        
        return min(delay, config.max_delay)
    
    def _can_execute_with_circuit_breaker(self, name: str) -> bool:
        """检查熔断器是否允许执行"""
        if name not in self.circuit_breakers:
            return True
        
        return self.circuit_breakers[name].can_execute()


# 全局错误处理器实例
_global_error_handlers: Dict[str, ErrorHandler] = {}


def get_error_handler(task_id: str, user_id: str) -> ErrorHandler:
    """获取错误处理器实例"""
    key = f"{task_id}_{user_id}"
    if key not in _global_error_handlers:
        _global_error_handlers[key] = ErrorHandler(task_id, user_id)
    return _global_error_handlers[key]


def retry_with_config(config: RetryConfig, circuit_breaker: Optional[str] = None):
    """便捷的重试装饰器"""
    def decorator(func):
        handler = get_error_handler("default", "default")
        return handler.retry(config, circuit_breaker)(func)
    return decorator


def timeout_after(seconds: float):
    """便捷的超时装饰器"""
    def decorator(func):
        handler = get_error_handler("default", "default")
        return handler.timeout(seconds)(func)
    return decorator