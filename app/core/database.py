from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import StaticPool
from typing import AsyncGenerator
import logging
import asyncio
from contextlib import asynccontextmanager

from app.core.config import settings

logger = logging.getLogger(__name__)

# 为Celery任务创建专用的数据库引擎
_celery_engine = None
_main_engine = None

def get_engine():
    """获取适合当前环境的数据库引擎"""
    global _celery_engine, _main_engine
    
    try:
        # 检查当前是否在Celery任务中（通过事件循环检测）
        current_loop = asyncio.get_running_loop()
        
        # 如果当前循环是新创建的，很可能是Celery任务
        if hasattr(current_loop, '_asyncio_running_loop'):
            # 在Celery任务中使用专用引擎
            if _celery_engine is None:
                _celery_engine = create_async_engine(
                    settings.DATABASE_URL,
                    echo=settings.DATABASE_ECHO,
                    pool_pre_ping=True,
                    pool_recycle=300,
                    pool_size=5,  # 减少连接池大小
                    max_overflow=10,
                    pool_timeout=30,
                    connect_args={
                        "server_settings": {
                            "jit": "off"
                        },
                        "command_timeout": 30
                    }
                )
            return _celery_engine
        else:
            # 在主应用中使用主引擎
            if _main_engine is None:
                _main_engine = create_async_engine(
                    settings.DATABASE_URL,
                    echo=settings.DATABASE_ECHO,
                    pool_pre_ping=True,
                    pool_recycle=300,
                    connect_args={
                        "server_settings": {
                            "jit": "off"
                        }
                    }
                )
            return _main_engine
            
    except RuntimeError:
        # 没有运行的事件循环，使用主引擎
        if _main_engine is None:
            _main_engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DATABASE_ECHO,
                pool_pre_ping=True,
                pool_recycle=300,
                connect_args={
                    "server_settings": {
                        "jit": "off"
                    }
                }
            )
        return _main_engine

# 创建默认引擎（向后兼容）
engine = get_engine()

# 创建会话工厂
def create_session_maker(engine_instance=None):
    """创建会话制造器"""
    if engine_instance is None:
        engine_instance = get_engine()
    
    return async_sessionmaker(
        engine_instance, 
        class_=AsyncSession, 
        expire_on_commit=False,
        autoflush=False,
        autocommit=False
    )

AsyncSessionLocal = create_session_maker()

# 创建基础模型类
Base = declarative_base()


@asynccontextmanager
async def get_db_session():
    """获取数据库会话（上下文管理器）"""
    # 为当前环境创建适合的会话制造器
    session_maker = create_session_maker()
    async with session_maker() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（FastAPI依赖注入）"""
    async with get_db_session() as session:
        yield session


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """获取异步数据库会话（FastAPI依赖注入别名）"""
    async with get_db_session() as session:
        yield session


async def init_db():
    """初始化数据库"""
    try:
        current_engine = get_engine()
        async with current_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_db():
    """关闭数据库连接"""
    global _celery_engine, _main_engine
    
    try:
        if _celery_engine:
            await _celery_engine.dispose()
            _celery_engine = None
            logger.info("Celery database engine disposed")
        
        if _main_engine:
            await _main_engine.dispose()
            _main_engine = None
            logger.info("Main database engine disposed")
            
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")