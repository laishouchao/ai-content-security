from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, Response
from contextlib import asynccontextmanager
import time
import uuid
from typing import Dict, Any

from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1 import auth, tasks, config, reports, admin, websocket, domains, domain_whitelist, performance
from app.core.exceptions import CustomException
from app.core.logging import setup_logging, logger
from app.core.prometheus import setup_metrics, REQUEST_COUNT, REQUEST_DURATION
from app.websocket.manager import websocket_manager
from app.websocket.handlers import task_monitor
from app.core.redis_lock import lock_manager
from app.core.memory_manager import memory_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("Starting Domain Compliance Scanner API...")
    
    # 创建数据库表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 设置监控
    setup_metrics()
    
    # 启动WebSocket管理器
    await websocket_manager.start()
    
    # 启动任务监控器
    await task_monitor.start()
    
    # 初始化Redis锁管理器
    try:
        await lock_manager.initialize()
        logger.info("Redis锁管理器初始化成功")
    except Exception as e:
        logger.error(f"Redis锁管理器初始化失败: {e}")
    
    # 启动内存管理器
    try:
        await memory_manager.start()
        logger.info("内存管理器启动成功")
    except Exception as e:
        logger.error(f"内存管理器启动失败: {e}")
    
    yield
    
    # 关闭时执行
    logger.info("Shutting down Domain Compliance Scanner API...")
    
    # 停止WebSocket管理器
    await websocket_manager.stop()
    
    # 停止任务监控器
    await task_monitor.stop()
    
    # 关闭Redis锁管理器
    try:
        await lock_manager.close()
        logger.info("Redis锁管理器已关闭")
    except Exception as e:
        logger.error(f"Redis锁管理器关闭失败: {e}")
    
    # 停止内存管理器
    try:
        await memory_manager.stop()
        logger.info("内存管理器已停止")
    except Exception as e:
        logger.error(f"内存管理器停止失败: {e}")


app = FastAPI(
    title="域名合规扫描系统",
    description="基于AI的智能域名内容安全检测平台",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT == "development" else None,
    lifespan=lifespan
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 可信主机中间件
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """添加请求处理时间和请求ID"""
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    # 添加请求ID到上下文
    request.state.request_id = request_id
    
    response = await call_next(request)
    
    # 计算处理时间
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Request-ID"] = request_id
    
    # 记录指标
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=str(request.url.path),
        status_code=response.status_code
    ).inc()
    
    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=str(request.url.path)
    ).observe(process_time)
    
    return response


@app.exception_handler(CustomException)
async def custom_exception_handler(request: Request, exc: CustomException):
    """自定义异常处理"""
    logger.error(
        f"Custom exception occurred",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "error_code": exc.error_code,
            "detail": exc.detail,
            "path": str(request.url.path)
        }
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "detail": exc.detail,
            "request_id": getattr(request.state, "request_id", None)
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理"""
    logger.warning(
        f"HTTP exception occurred",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": str(request.url.path)
        }
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "request_id": getattr(request.state, "request_id", None)
        }
    )


# 路由注册
app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["任务管理"])
app.include_router(config.router, prefix="/api/v1/config", tags=["配置管理"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["报告管理"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["系统管理"])
app.include_router(websocket.router, prefix="/api/v1/monitor", tags=["实时监控"])
app.include_router(domains.router, prefix="/api/v1/domains", tags=["域名库"])
app.include_router(domain_whitelist.router, prefix="/api/v1/domain-lists", tags=["域名白名单"])
app.include_router(performance.router, prefix="/api/v1/performance", tags=["性能监控"])


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "域名合规扫描系统 API",
        "version": "1.0.0",
        "docs": "/docs" if settings.ENVIRONMENT == "development" else "disabled"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "environment": settings.ENVIRONMENT
    }


@app.get("/metrics")
async def get_metrics():
    """Prometheus指标端点"""
    try:
        from prometheus_client import generate_latest
        return Response(generate_latest(), media_type="text/plain")
    except ImportError:
        return {"message": "Prometheus metrics not available"}


if __name__ == "__main__":
    import uvicorn
    
    setup_logging()
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
        log_config=None  # 使用我们自定义的日志配置
    )