#!/usr/bin/env python3
"""
Redis 连接测试脚本
用于诊断和测试 Redis 连接问题
"""

import sys
import os
import time
import traceback
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import redis
    from app.core.config import settings
    
    def test_redis_connection():
        """测试 Redis 连接"""
        print("🔍 Redis 连接测试")
        print("=" * 50)
        
        redis_url = settings.CELERY_BROKER_URL
        print(f"📡 连接URL: {redis_url}")
        
        try:
            # 创建Redis连接
            r = redis.from_url(redis_url, decode_responses=True)
            
            # 测试基本连接
            print("🔗 测试基本连接...")
            result = r.ping()
            print(f"✅ PING 结果: {result}")
            
            # 测试基本操作
            print("📝 测试基本操作...")
            test_key = "celery_test_key"
            test_value = "test_value"
            
            # 设置键值
            r.set(test_key, test_value, ex=60)  # 60秒过期
            print(f"✅ SET {test_key} = {test_value}")
            
            # 获取键值
            retrieved_value = r.get(test_key)
            print(f"✅ GET {test_key} = {retrieved_value}")
            
            # 删除测试键
            r.delete(test_key)
            print(f"✅ DEL {test_key}")
            
            # 检查 Celery 相关键
            print("🔍 检查 Celery 相关键...")
            celery_keys = r.keys("celery*")
            print(f"📊 Celery 键数量: {len(celery_keys)}")
            
            if celery_keys:
                print("📋 前10个 Celery 键:")
                for i, key in enumerate(celery_keys[:10]):
                    print(f"   {i+1}. {key}")
            
            # 检查任务元数据
            task_meta_keys = r.keys("celery-task-meta-*")
            print(f"📋 任务元数据键数量: {len(task_meta_keys)}")
            
            # Redis 信息
            print("💾 Redis 服务器信息:")
            info = r.info()
            print(f"   版本: {info.get('redis_version', 'Unknown')}")
            print(f"   内存使用: {info.get('used_memory_human', 'Unknown')}")
            print(f"   连接客户端: {info.get('connected_clients', 'Unknown')}")
            print(f"   正常运行时间: {info.get('uptime_in_seconds', 'Unknown')} 秒")
            
            return True
            
        except redis.ConnectionError as e:
            print(f"❌ 连接错误: {e}")
            return False
        except redis.TimeoutError as e:
            print(f"❌ 连接超时: {e}")
            return False
        except Exception as e:
            print(f"❌ 其他错误: {e}")
            print(f"📍 错误详情:\n{traceback.format_exc()}")
            return False
    
    def test_celery_broker():
        """测试 Celery broker 配置"""
        print("\n🚀 Celery Broker 测试")
        print("=" * 50)
        
        try:
            from celery import Celery
            
            # 创建临时 Celery 应用
            test_app = Celery('test_app', broker=settings.CELERY_BROKER_URL)
            
            # 配置基础设置
            test_app.conf.update(
                broker_connection_retry_on_startup=True,
                broker_connection_retry=True,
                broker_connection_max_retries=3,
                broker_heartbeat=30,
                task_serializer='json',
                result_serializer='json',
                accept_content=['json'],
                broker_transport_options={
                    'visibility_timeout': 3600,
                    'fanout_prefix': True,
                    'fanout_patterns': True,
                },
                result_backend_transport_options={
                    'visibility_timeout': 3600,
                }
            )
            
            print("✅ Celery 应用创建成功")
            
            # 测试连接
            with test_app.connection() as conn:
                conn.connect()
                print("✅ Celery broker 连接成功")
                
            return True
            
        except Exception as e:
            print(f"❌ Celery broker 测试失败: {e}")
            print(f"📍 错误详情:\n{traceback.format_exc()}")
            return False
    
    def cleanup_orphaned_tasks():
        """清理孤立任务"""
        print("\n🧹 清理孤立任务")
        print("=" * 50)
        
        try:
            r = redis.from_url(settings.CELERY_BROKER_URL)
            
            # 获取所有任务元数据键
            task_keys = r.keys("celery-task-meta-*")
            print(f"📊 发现 {len(task_keys)} 个任务元数据键")
            
            if not task_keys:
                print("✅ 没有需要清理的任务")
                return True
            
            cleaned_count = 0
            current_time = time.time()
            
            for key in task_keys:
                try:
                    # 检查 TTL
                    ttl = r.ttl(key)
                    
                    if ttl == -1:  # 没有过期时间
                        r.expire(key, 3600)  # 设置1小时过期
                        cleaned_count += 1
                        print(f"   ✅ 设置过期时间: {key}")
                    elif ttl > 7200:  # TTL 大于2小时
                        r.expire(key, 3600)  # 重置为1小时
                        cleaned_count += 1
                        print(f"   ✅ 重置过期时间: {key}")
                        
                except Exception as e:
                    print(f"   ❌ 处理键 {key} 失败: {e}")
            
            print(f"✅ 清理完成，处理了 {cleaned_count} 个任务")
            return True
            
        except Exception as e:
            print(f"❌ 清理失败: {e}")
            return False
    
    def main():
        """主函数"""
        print("🎯 AI内容安全监控系统 - Redis 诊断工具")
        print(f"📅 测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        success_count = 0
        total_tests = 3
        
        # 测试 Redis 连接
        if test_redis_connection():
            success_count += 1
        
        # 测试 Celery broker
        if test_celery_broker():
            success_count += 1
        
        # 清理孤立任务
        if cleanup_orphaned_tasks():
            success_count += 1
        
        print("\n📊 测试结果汇总")
        print("=" * 50)
        print(f"✅ 成功: {success_count}/{total_tests}")
        print(f"❌ 失败: {total_tests - success_count}/{total_tests}")
        
        if success_count == total_tests:
            print("\n🎉 所有测试通过！Redis 连接正常。")
            return 0
        else:
            print("\n⚠️  部分测试失败，请检查 Redis 配置和网络连接。")
            return 1

except ImportError as e:
    print(f"❌ 导入模块失败: {e}")
    print("请确保已安装所需依赖: pip install redis")
    sys.exit(1)

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)