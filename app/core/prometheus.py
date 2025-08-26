from prometheus_client import Counter, Histogram, Gauge, Info
from typing import Dict, Any


# 应用信息
APP_INFO = Info("app_info", "Application information")

# 请求指标
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"]
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"]
)

# 业务指标
SCAN_TASKS_TOTAL = Counter(
    "scan_tasks_total",
    "Total scan tasks created",
    ["status", "user_role"]
)

SCAN_TASK_DURATION = Histogram(
    "scan_task_duration_seconds",
    "Scan task execution duration in seconds",
    ["status"]
)

SUBDOMAINS_DISCOVERED = Counter(
    "subdomains_discovered_total",
    "Total subdomains discovered",
    ["discovery_method"]
)

PAGES_CRAWLED = Counter(
    "pages_crawled_total",
    "Total pages crawled",
    ["domain_type"]
)

VIOLATIONS_DETECTED = Counter(
    "violations_detected_total",
    "Total violations detected",
    ["violation_type", "risk_level"]
)

AI_ANALYSIS_REQUESTS = Counter(
    "ai_analysis_requests_total",
    "Total AI analysis requests",
    ["model", "status"]
)

AI_ANALYSIS_DURATION = Histogram(
    "ai_analysis_duration_seconds",
    "AI analysis request duration in seconds",
    ["model"]
)

# 系统指标
ACTIVE_USERS = Gauge(
    "active_users_count",
    "Number of currently active users"
)

CONCURRENT_TASKS = Gauge(
    "concurrent_tasks_count",
    "Number of currently running tasks"
)

TASK_QUEUE_SIZE = Gauge(
    "task_queue_size",
    "Current task queue size",
    ["queue_name"]
)

DATABASE_CONNECTIONS = Gauge(
    "database_connections_active",
    "Number of active database connections"
)

REDIS_CONNECTIONS = Gauge(
    "redis_connections_active", 
    "Number of active Redis connections"
)

# 错误指标
ERROR_COUNT = Counter(
    "errors_total",
    "Total errors by type",
    ["error_type", "module"]
)

FAILED_TASKS = Counter(
    "failed_tasks_total",
    "Total failed tasks by reason",
    ["failure_reason"]
)


def setup_metrics():
    """初始化监控指标"""
    APP_INFO.info({
        "version": "1.0.0",
        "name": "Domain Compliance Scanner"
    })


def record_task_started(user_role: str = "user"):
    """记录任务开始"""
    SCAN_TASKS_TOTAL.labels(status="started", user_role=user_role).inc()


def record_task_completed(duration: float, status: str = "completed"):
    """记录任务完成"""
    SCAN_TASK_DURATION.labels(status=status).observe(duration)
    SCAN_TASKS_TOTAL.labels(status=status, user_role="user").inc()


def record_subdomain_discovery(count: int, method: str):
    """记录子域名发现"""
    SUBDOMAINS_DISCOVERED.labels(discovery_method=method).inc(count)


def record_page_crawled(domain_type: str = "unknown"):
    """记录页面爬取"""
    PAGES_CRAWLED.labels(domain_type=domain_type).inc()


def record_violation_detected(violation_type: str, risk_level: str):
    """记录违规检测"""
    VIOLATIONS_DETECTED.labels(
        violation_type=violation_type,
        risk_level=risk_level
    ).inc()


def record_ai_analysis(model: str, duration: float, status: str = "success"):
    """记录AI分析"""
    AI_ANALYSIS_REQUESTS.labels(model=model, status=status).inc()
    AI_ANALYSIS_DURATION.labels(model=model).observe(duration)


def record_error(error_type: str, module: str):
    """记录错误"""
    ERROR_COUNT.labels(error_type=error_type, module=module).inc()


def record_task_failure(failure_reason: str):
    """记录任务失败"""
    FAILED_TASKS.labels(failure_reason=failure_reason).inc()


def update_active_users(count: int):
    """更新活跃用户数"""
    ACTIVE_USERS.set(count)


def update_concurrent_tasks(count: int):
    """更新并发任务数"""
    CONCURRENT_TASKS.set(count)


def update_queue_size(queue_name: str, size: int):
    """更新队列大小"""
    TASK_QUEUE_SIZE.labels(queue_name=queue_name).set(size)