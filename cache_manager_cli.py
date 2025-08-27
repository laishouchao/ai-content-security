#!/usr/bin/env python3
"""
缓存管理命令行工具

提供快速的缓存清理和诊断功能
"""

import asyncio
import argparse
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.cache_manager import cache_manager
from app.core.logging import logger


async def show_status():
    """显示缓存状态"""
    print("🔍 检查缓存状态...")
    
    try:
        await cache_manager.initialize()
        status = await cache_manager.get_cache_status()
        
        print(f"\n📊 缓存状态报告 ({status['timestamp']})")
        print("=" * 50)
        
        # Redis连接状态
        redis_status = "✅ 已连接" if status['redis_connected'] else "❌ 断开"
        print(f"Redis连接: {redis_status}")
        
        if status['redis_connected']:
            redis_info = status.get('redis_info', {})
            print(f"  - 内存使用: {redis_info.get('used_memory_human', 'N/A')}")
            print(f"  - 客户端连接: {redis_info.get('connected_clients', 0)}")
        
        # 任务统计
        print(f"\n📋 任务统计:")
        print(f"  - Redis中的Celery任务: {status['celery_tasks_count']}")
        print(f"  - 孤立任务: {status['orphaned_tasks_count']}")
        print(f"  - 数据库中的任务: {status['database_tasks_count']}")
        
        if status['orphaned_tasks_count'] > 0:
            print(f"\n⚠️  发现 {status['orphaned_tasks_count']} 个孤立任务，建议清理")
        
    except Exception as e:
        print(f"❌ 获取缓存状态失败: {e}")
    finally:
        await cache_manager.close()


async def show_celery_tasks(orphaned_only=False):
    """显示Celery任务"""
    task_type = "孤立任务" if orphaned_only else "所有Celery任务"
    print(f"🔍 获取{task_type}...")
    
    try:
        await cache_manager.initialize()
        
        if orphaned_only:
            tasks = await cache_manager.get_orphaned_celery_tasks()
        else:
            tasks = await cache_manager.get_celery_tasks_from_redis()
        
        print(f"\n📋 {task_type} ({len(tasks)} 个)")
        print("=" * 60)
        
        if not tasks:
            print("✨ 没有找到任务")
            return
        
        for i, task in enumerate(tasks, 1):
            print(f"\n{i}. 键: {task['key']}")
            print(f"   类型: {task['type']}")
            print(f"   TTL: {task.get('ttl', 'N/A')} 秒")
            
            if 'task_id' in task:
                print(f"   任务ID: {task['task_id']}")
            
            if 'task_data' in task:
                task_data = task['task_data']
                if 'status' in task_data:
                    print(f"   状态: {task_data['status']}")
                if 'result' in task_data:
                    print(f"   结果: {task_data['result']}")
            
            if orphaned_only and 'reason' in task:
                print(f"   原因: {task['reason']}")
    
    except Exception as e:
        print(f"❌ 获取任务失败: {e}")
    finally:
        await cache_manager.close()


async def cleanup_orphaned_tasks():
    """清理孤立任务"""
    print("🧹 清理孤立的Celery任务...")
    
    try:
        await cache_manager.initialize()
        
        # 先获取孤立任务信息
        orphaned_tasks = await cache_manager.get_orphaned_celery_tasks()
        if not orphaned_tasks:
            print("✨ 没有发现孤立任务")
            return
        
        print(f"发现 {len(orphaned_tasks)} 个孤立任务:")
        for task in orphaned_tasks:
            print(f"  - {task['key']} (任务ID: {task.get('task_id', 'N/A')})")
        
        # 确认清理
        confirm = input("\n是否继续清理这些孤立任务? (y/N): ")
        if confirm.lower() != 'y':
            print("取消清理操作")
            return
        
        # 执行清理
        cleaned_count = await cache_manager.cleanup_orphaned_celery_tasks()
        print(f"✅ 成功清理 {cleaned_count} 个孤立任务")
    
    except Exception as e:
        print(f"❌ 清理孤立任务失败: {e}")
    finally:
        await cache_manager.close()


async def cleanup_expired_results(max_age_hours=24):
    """清理过期任务结果"""
    print(f"🧹 清理超过 {max_age_hours} 小时的任务结果...")
    
    try:
        await cache_manager.initialize()
        
        cleaned_count = await cache_manager.cleanup_expired_task_results(max_age_hours)
        print(f"✅ 成功清理 {cleaned_count} 个过期任务结果")
    
    except Exception as e:
        print(f"❌ 清理过期任务结果失败: {e}")
    finally:
        await cache_manager.close()


async def cleanup_database_orphans():
    """清理数据库孤立记录"""
    print("🧹 清理数据库孤立记录...")
    
    try:
        cleanup_stats = await cache_manager.cleanup_database_orphaned_records()
        
        total_cleaned = sum(cleanup_stats.values())
        if total_cleaned == 0:
            print("✨ 没有发现孤立记录")
            return
        
        print(f"✅ 成功清理 {total_cleaned} 条孤立记录:")
        for table, count in cleanup_stats.items():
            if count > 0:
                print(f"  - {table}: {count} 条")
    
    except Exception as e:
        print(f"❌ 清理数据库孤立记录失败: {e}")


async def purge_all_queues():
    """清空所有Celery队列"""
    print("🚨 清空所有Celery队列...")
    print("⚠️  警告: 这将删除所有等待执行的任务!")
    
    confirm = input("是否确认清空所有队列? (y/N): ")
    if confirm.lower() != 'y':
        print("取消清空操作")
        return
    
    try:
        await cache_manager.initialize()
        
        cleaned_count = await cache_manager.purge_all_celery_queues()
        print(f"✅ 成功清空队列，删除 {cleaned_count} 个Redis键")
    
    except Exception as e:
        print(f"❌ 清空队列失败: {e}")
    finally:
        await cache_manager.close()


async def full_cleanup():
    """执行完整清理"""
    print("🧹 执行完整缓存清理...")
    
    try:
        await cache_manager.initialize()
        
        results = await cache_manager.perform_full_cleanup()
        
        print(f"\n📊 清理完成报告 ({results['timestamp']})")
        print("=" * 50)
        print(f"Redis连接: {'✅' if results['redis_connected'] else '❌'}")
        print(f"Celery任务清理: {results['celery_tasks_cleaned']} 个")
        print(f"过期结果清理: {results['task_results_cleaned']} 个")
        
        if 'locks_cleaned' in results:
            print(f"Redis锁清理: {results['locks_cleaned']} 个")
        
        db_stats = results['database_records_cleaned']
        total_db_cleaned = sum(db_stats.values())
        print(f"数据库记录清理: {total_db_cleaned} 条")
        
        if total_db_cleaned > 0:
            for table, count in db_stats.items():
                if count > 0:
                    print(f"  - {table}: {count} 条")
        
        print(f"总操作数: {results['total_operations']}")
        
        if results['errors']:
            print(f"\n❌ 错误 ({len(results['errors'])}):")
            for error in results['errors']:
                print(f"  - {error}")
        else:
            print("\n✅ 所有操作成功完成")
    
    except Exception as e:
        print(f"❌ 执行完整清理失败: {e}")
    finally:
        await cache_manager.close()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="缓存管理工具")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 状态查看
    subparsers.add_parser('status', help='显示缓存状态')
    
    # 任务查看
    tasks_parser = subparsers.add_parser('tasks', help='显示Celery任务')
    tasks_parser.add_argument('--orphaned', action='store_true', help='只显示孤立任务')
    
    # 清理操作
    subparsers.add_parser('cleanup-orphaned', help='清理孤立的Celery任务')
    
    expired_parser = subparsers.add_parser('cleanup-expired', help='清理过期任务结果')
    expired_parser.add_argument('--hours', type=int, default=24, help='最大保留时间（小时）')
    
    subparsers.add_parser('cleanup-database', help='清理数据库孤立记录')
    subparsers.add_parser('purge-queues', help='清空所有Celery队列')
    subparsers.add_parser('full-cleanup', help='执行完整清理')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 执行命令
    try:
        if args.command == 'status':
            asyncio.run(show_status())
        elif args.command == 'tasks':
            asyncio.run(show_celery_tasks(args.orphaned))
        elif args.command == 'cleanup-orphaned':
            asyncio.run(cleanup_orphaned_tasks())
        elif args.command == 'cleanup-expired':
            asyncio.run(cleanup_expired_results(args.hours))
        elif args.command == 'cleanup-database':
            asyncio.run(cleanup_database_orphans())
        elif args.command == 'purge-queues':
            asyncio.run(purge_all_queues())
        elif args.command == 'full-cleanup':
            asyncio.run(full_cleanup())
    except KeyboardInterrupt:
        print("\n\n操作已取消")
    except Exception as e:
        print(f"\n❌ 执行命令失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()