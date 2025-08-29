"""
Redis分布式锁管理器
用于防止并发任务冲突，确保资源访问的原子性
"""

import asyncio
import time
import uuid
from typing import Optional, Any, AsyncGenerator
from contextlib import asynccontextmanager
import redis.asyncio as redis
from redis.asyncio import Redis
import logging

from app.core.config import settings
from app.core.logging import logger


class RedisLockError(Exception):
    """Redis锁异常"""
    pass


class RedisLockTimeout(RedisLockError):
    """Redis锁超时异常"""
    pass


class RedisDistributedLock:
    """Redis分布式锁"""
    
    def __init__(
        self,
        redis_client: Redis,
        key: str,
        timeout: float = 30.0,
        retry_interval: float = 0.1,
        expire_time: Optional[float] = None
    ):
        """
        初始化分布式锁
        
        Args:
            redis_client: Redis客户端
            key: 锁的键名
            timeout: 获取锁的超时时间（秒）
            retry_interval: 重试间隔（秒）
            expire_time: 锁的过期时间（秒），防止死锁
        """
        self.redis = redis_client
        self.key = f"lock:{key}"
        self.timeout = timeout
        self.retry_interval = retry_interval
        self.expire_time = expire_time or timeout * 2
        self.token = str(uuid.uuid4())
        self._acquired = False
    
    async def acquire(self) -> bool:
        """
        获取锁
        
        Returns:
            是否成功获取锁
        """
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            # 尝试设置锁，使用SET命令的NX和EX选项
            result = await self.redis.set(
                self.key,
                self.token,
                nx=True,  # 只在键不存在时设置
                ex=int(self.expire_time)  # 设置过期时间
            )
            
            if result:
                self._acquired = True
                logger.debug(f"成功获取Redis锁: {self.key}")
                return True
            
            # 锁被占用，等待重试
            await asyncio.sleep(self.retry_interval)
        
        logger.warning(f"获取Redis锁超时: {self.key}")
        raise RedisLockTimeout(f"无法在 {self.timeout} 秒内获取锁: {self.key}")
    
    async def release(self) -> bool:
        """
        释放锁
        
        Returns:
            是否成功释放锁
        """
        if not self._acquired:
            return False
        
        # 使用Lua脚本确保原子性：只有持有锁的客户端才能释放锁
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        try:
            # 使用正确的参数顺序：script, numkeys, key1, key2, ..., arg1, arg2, ...
            result = await self.redis.eval(lua_script, 1, self.key, self.token)  # type: ignore
            if result:
                self._acquired = False
                logger.debug(f"成功释放Redis锁: {self.key}")
                return True
            else:
                logger.warning(f"锁已被其他客户端持有或已过期: {self.key}")
                return False
        except Exception as e:
            logger.error(f"释放Redis锁失败: {self.key}, 错误: {e}")
            return False
    
    async def extend(self, extend_time: float) -> bool:
        """
        延长锁的过期时间
        
        Args:
            extend_time: 延长时间（秒）
        
        Returns:
            是否成功延长
        """
        if not self._acquired:
            return False
        
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        
        try:
            # 使用正确的参数顺序：script, numkeys, key1, key2, ..., arg1, arg2, ...
            result = await self.redis.eval(lua_script, 1, self.key, self.token, str(extend_time))  # type: ignore
            if result:
                logger.debug(f"成功延长Redis锁过期时间: {self.key}")
                return True
            return False
        except Exception as e:
            logger.error(f"延长Redis锁过期时间失败: {self.key}, 错误: {e}")
            return False
    
    async def is_locked(self) -> bool:
        """检查锁是否被持有"""
        try:
            value = await self.redis.get(self.key)
            return value is not None
        except Exception:
            return False
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.release()


class RedisLockManager:
    """Redis锁管理器"""
    
    def __init__(self):
        self.redis_client: Optional[Redis] = None
        self._locks: dict = {}
    
    async def initialize(self):
        """初始化Redis连接"""
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # 测试连接
            await self.redis_client.ping()
            logger.info("Redis锁管理器初始化成功")
            
        except Exception as e:
            logger.error(f"Redis锁管理器初始化失败: {e}")
            raise e
    
    async def close(self):
        """关闭Redis连接"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis锁管理器已关闭")
    
    @asynccontextmanager
    async def lock(
        self,
        key: str,
        timeout: float = 30.0,
        retry_interval: float = 0.1,
        expire_time: Optional[float] = None
    ) -> AsyncGenerator[RedisDistributedLock, None]:
        """
        获取分布式锁的上下文管理器
        
        Args:
            key: 锁的键名
            timeout: 获取锁的超时时间
            retry_interval: 重试间隔
            expire_time: 锁的过期时间
        
        Usage:
            async with lock_manager.lock("task:scan:domain.com") as lock:
                # 执行需要锁保护的代码
                pass
        """
        if not self.redis_client:
            raise RedisLockError("Redis客户端未初始化")
        
        lock = RedisDistributedLock(
            self.redis_client,
            key,
            timeout,
            retry_interval,
            expire_time
        )
        
        try:
            await lock.acquire()
            yield lock
        finally:
            await lock.release()
    
    async def is_locked(self, key: str) -> bool:
        """检查指定键是否被锁定"""
        if not self.redis_client:
            return False
        
        try:
            value = await self.redis_client.get(f"lock:{key}")
            return value is not None
        except Exception:
            return False
    
    async def force_release_lock(self, key: str) -> bool:
        """强制释放锁（慎用）"""
        if not self.redis_client:
            return False
        
        try:
            result = await self.redis_client.delete(f"lock:{key}")
            if result:
                logger.warning(f"强制释放锁: {key}")
            return bool(result)
        except Exception as e:
            logger.error(f"强制释放锁失败: {key}, 错误: {e}")
            return False
    
    async def get_lock_info(self, key: str) -> Optional[dict]:
        """获取锁信息"""
        if not self.redis_client:
            return None
        
        try:
            lock_key = f"lock:{key}"
            value = await self.redis_client.get(lock_key)
            ttl = await self.redis_client.ttl(lock_key)
            
            if value:
                return {
                    'key': key,
                    'token': value,
                    'ttl': ttl,
                    'locked': True
                }
            else:
                return {
                    'key': key,
                    'locked': False
                }
        except Exception as e:
            logger.error(f"获取锁信息失败: {key}, 错误: {e}")
            return None
    
    async def cleanup_expired_locks(self) -> int:
        """清理过期的锁"""
        if not self.redis_client:
            return 0
        
        try:
            # 获取所有锁键
            lock_keys = await self.redis_client.keys("lock:*")
            expired_count = 0
            
            for key in lock_keys:
                ttl = await self.redis_client.ttl(key)
                if ttl == -1:  # 没有设置过期时间的锁
                    await self.redis_client.delete(key)
                    expired_count += 1
                    logger.info(f"清理无过期时间的锁: {key}")
            
            if expired_count > 0:
                logger.info(f"清理过期锁完成，共清理 {expired_count} 个锁")
            
            return expired_count
            
        except Exception as e:
            logger.error(f"清理过期锁失败: {e}")
            return 0


# 全局锁管理器实例
lock_manager = RedisLockManager()


# 装饰器：为函数添加分布式锁
def with_redis_lock(key_template: str, timeout: float = 30.0):
    """
    分布式锁装饰器
    
    Args:
        key_template: 锁键名模板，可以使用函数参数进行格式化
        timeout: 锁超时时间
    
    Usage:
        @with_redis_lock("scan:domain:{domain}")
        async def scan_domain(domain: str):
            pass
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 生成锁键名
            try:
                # 获取函数参数
                import inspect
                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()
                
                # 格式化锁键名
                lock_key = key_template.format(**bound_args.arguments)
            except Exception as e:
                logger.error(f"生成锁键名失败: {e}")
                lock_key = key_template
            
            # 使用锁执行函数
            async with lock_manager.lock(lock_key, timeout=timeout):
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator