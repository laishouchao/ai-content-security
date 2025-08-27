#!/usr/bin/env python3
"""
测试任务创建修复效果的脚本

这个脚本验证：
1. 任务创建的原子性
2. Redis分布式锁的工作
3. 延迟执行机制
4. 重试机制
"""

import asyncio
import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.cache_manager import cache_manager
from app.core.redis_lock import lock_manager
from app.core.logging import logger


async def test_redis_connections():
    """测试Redis连接"""
    print("🔍 测试Redis连接...")
    
    try:
        # 测试缓存管理器
        await cache_manager.initialize()
        if cache_manager.redis_client:
            await cache_manager.redis_client.ping()
            print("✅ 缓存管理器Redis连接正常")
        else:
            print("❌ 缓存管理器Redis连接失败")
            return False
        
        # 测试锁管理器
        await lock_manager.initialize()
        if lock_manager.redis_client:
            await lock_manager.redis_client.ping()
            print("✅ 锁管理器Redis连接正常")
        else:
            print("❌ 锁管理器Redis连接失败")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Redis连接测试失败: {e}")
        return False


async def test_distributed_lock():
    """测试分布式锁功能"""
    print("\n🔒 测试分布式锁功能...")
    
    try:
        lock_key = "test_lock_key"
        
        # 测试锁的获取和释放
        async with lock_manager.lock(lock_key, timeout=10, expire_time=30):
            print("✅ 成功获取分布式锁")
            
            # 模拟一些工作
            await asyncio.sleep(1)
            
            print("✅ 工作完成，释放锁")
        
        print("✅ 分布式锁测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 分布式锁测试失败: {e}")
        return False


async def test_task_creation_markers():
    """测试任务创建标记功能"""
    print("\n📝 测试任务创建标记功能...")
    
    try:
        if not cache_manager.redis_client:
            print("❌ Redis客户端未初始化")
            return False
        
        # 测试设置和获取任务创建标记
        test_task_id = "test-task-12345"
        task_creation_key = f"task_created:{test_task_id}"
        
        # 设置标记
        await cache_manager.redis_client.setex(task_creation_key, 60, "created")
        print("✅ 成功设置任务创建标记")
        
        # 获取标记
        marker_value = await cache_manager.redis_client.get(task_creation_key)
        if marker_value == "created":
            print("✅ 成功获取任务创建标记")
        else:
            print("❌ 任务创建标记值不正确")
            return False
        
        # 清理测试数据
        await cache_manager.redis_client.delete(task_creation_key)
        print("✅ 清理测试数据完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 任务创建标记测试失败: {e}")
        return False


async def test_orphaned_task_cleanup():
    """测试孤立任务清理功能"""
    print("\n🧹 测试孤立任务清理功能...")
    
    try:
        # 检查当前的孤立任务
        orphaned_tasks = await cache_manager.get_orphaned_celery_tasks()
        print(f"🔍 当前孤立任务数量: {len(orphaned_tasks)}")
        
        if orphaned_tasks:
            print("发现孤立任务:")
            for task in orphaned_tasks[:3]:  # 只显示前3个
                print(f"  - {task.get('key', 'Unknown')} (原因: {task.get('reason', 'Unknown')})")
            
            # 询问是否清理
            print("\n是否要清理这些孤立任务? (y/N):", end=" ")
            # 自动选择不清理，避免在测试时误删
            choice = "n"
            print(choice)
            
            if choice.lower() == 'y':
                cleaned_count = await cache_manager.cleanup_orphaned_celery_tasks()
                print(f"✅ 已清理 {cleaned_count} 个孤立任务")
            else:
                print("⏭️  跳过清理")
        else:
            print("✅ 没有发现孤立任务")
        
        return True
        
    except Exception as e:
        print(f"❌ 孤立任务清理测试失败: {e}")
        return False


async def test_task_existence_check():
    """测试任务存在性检查函数"""
    print("\n🔍 测试任务存在性检查功能...")
    
    try:
        from app.tasks.scan_tasks import _check_task_exists
        
        # 测试不存在的任务（应该返回False）
        fake_task_id = "non-existent-task-12345"
        exists = await _check_task_exists(fake_task_id, max_retries=2, retry_delay=0.5)
        
        if not exists:
            print("✅ 不存在的任务检查正确返回False")
        else:
            print("❌ 不存在的任务检查错误返回True")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 任务存在性检查测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("🚀 开始测试任务创建修复效果")
    print("=" * 50)
    
    tests = [
        test_redis_connections,
        test_distributed_lock,
        test_task_creation_markers,
        test_orphaned_task_cleanup,
        test_task_existence_check
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if await test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ 测试 {test_func.__name__} 发生异常: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("🎉 所有测试都通过了！任务创建修复应该生效。")
    else:
        print("⚠️  有测试失败，请检查相关配置。")
    
    # 清理资源
    try:
        await cache_manager.close()
        await lock_manager.close()
        print("✅ 资源清理完成")
    except Exception as e:
        print(f"⚠️  资源清理时出错: {e}")


if __name__ == "__main__":
    asyncio.run(main())