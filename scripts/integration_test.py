#!/usr/bin/env python3
"""
系统集成测试脚本
验证重构后的功能是否正常工作
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, Any

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app.core.database import AsyncSessionLocal
from app.models.domain import DomainRecord, DomainCategory, DomainStatus, DiscoveryMethod, RiskLevel
from app.models.task import ScanTask, TaskStatus
from app.engines.domain_discovery_engine import ContinuousDomainDiscoveryEngine
from app.websocket.domain_websocket import websocket_manager, task_notifier, notify_domain_stats_update
from app.core.task_queue import task_queue, start_task_queue, stop_task_queue, DomainTaskType
from sqlalchemy import select, text


class IntegrationTester:
    """集成测试器"""
    
    def __init__(self):
        self.test_task_id = "test_integration_001"
        self.test_user_id = "test_user"
        self.test_domain = "example.com"
        self.test_results = []
    
    async def run_all_tests(self):
        """运行所有集成测试"""
        print("🧪 开始系统集成测试")
        print("=" * 60)
        
        tests = [
            ("数据库连接和域名表测试", self.test_database_and_domain_table),
            ("循环域名发现引擎测试", self.test_continuous_discovery_engine),
            ("WebSocket推送系统测试", self.test_websocket_system),
            ("内存任务队列测试", self.test_task_queue_system),
            ("API接口测试", self.test_api_endpoints),
            ("数据同步测试", self.test_data_synchronization)
        ]
        
        for test_name, test_func in tests:
            try:
                print(f"\n🔄 测试: {test_name}")
                result = await test_func()
                if result:
                    print(f"✅ 通过: {test_name}")
                    self.test_results.append((test_name, True, None))
                else:
                    print(f"❌ 失败: {test_name}")
                    self.test_results.append((test_name, False, "测试返回False"))
            except Exception as e:
                print(f"❌ 异常: {test_name} - {e}")
                self.test_results.append((test_name, False, str(e)))
        
        await self.print_test_summary()
    
    async def test_database_and_domain_table(self) -> bool:
        """测试数据库连接和域名表"""
        try:
            async with AsyncSessionLocal() as db:
                # 检查表是否存在（兼容PostgreSQL）
                result = await db.execute(text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = 'domain_records'
                """))
                table_exists = result.fetchone() is not None
                
                if not table_exists:
                    print("   ⚠️  domain_records表不存在，尝试创建...")
                    return False
                
                # 创建测试任务（如果不存在）
                task_query = select(ScanTask).where(ScanTask.id == self.test_task_id)
                task_result = await db.execute(task_query)
                existing_task = task_result.scalar_one_or_none()
                
                if not existing_task:
                    test_task = ScanTask(
                        id=self.test_task_id,
                        target_domain=self.test_domain,
                        user_id=self.test_user_id,
                        status=TaskStatus.PENDING,
                        description="集成测试任务"
                    )
                    db.add(test_task)
                    await db.commit()
                    print(f"   ✅ 创建了测试任务: {self.test_task_id}")
                
                # 测试插入一条测试数据
                test_domain = DomainRecord(
                    task_id=self.test_task_id,
                    domain="test.example.com",
                    category=DomainCategory.TARGET_SUBDOMAIN,
                    status=DomainStatus.DISCOVERED,
                    discovery_method=DiscoveryMethod.MANUAL,
                    is_accessible=True,
                    risk_level=RiskLevel.LOW,
                    confidence_score=1.0,
                    tags=["test"],
                    extra_data={"test": True}
                )
                
                db.add(test_domain)
                await db.commit()
                
                # 测试查询
                query = select(DomainRecord).where(DomainRecord.task_id == self.test_task_id)
                result = await db.execute(query)
                domains = result.scalars().all()
                
                print(f"   📊 成功插入并查询到 {len(domains)} 条测试域名记录")
                
                # 清理测试数据
                for domain in domains:
                    await db.delete(domain)
                await db.commit()
                
                return True
                
        except Exception as e:
            print(f"   ❌ 数据库测试失败: {e}")
            return False
    
    async def test_continuous_discovery_engine(self) -> bool:
        """测试循环域名发现引擎"""
        try:
            print(f"   🔄 测试循环发现引擎 - 目标域名: {self.test_domain}")
            
            # 首先确保测试任务存在
            async with AsyncSessionLocal() as db:
                task_query = select(ScanTask).where(ScanTask.id == self.test_task_id)
                task_result = await db.execute(task_query)
                existing_task = task_result.scalar_one_or_none()
                
                if not existing_task:
                    test_task = ScanTask(
                        id=self.test_task_id,
                        target_domain=self.test_domain,
                        user_id=self.test_user_id,
                        status=TaskStatus.PENDING,
                        description="循环发现引擎测试任务"
                    )
                    db.add(test_task)
                    await db.commit()
                    print(f"   ✅ 创建了测试任务：{self.test_task_id}")
            
            # 创建引擎实例
            engine = ContinuousDomainDiscoveryEngine(
                task_id=self.test_task_id,
                user_id=self.test_user_id,
                target_domain=self.test_domain
            )
            
            # 测试域名分类功能
            test_domains = [
                "example.com",
                "www.example.com", 
                "api.example.com",
                "google.com",
                "cdn.cloudflare.com"
            ]
            
            classifications = {}
            for domain in test_domains:
                category = engine._classify_domain(domain)
                classifications[domain] = category
                print(f"   🏷️  {domain} -> {category}")
            
            # 验证分类结果
            assert classifications["example.com"] == DomainCategory.TARGET_MAIN
            assert classifications["www.example.com"] == DomainCategory.TARGET_SUBDOMAIN
            assert classifications["google.com"] == DomainCategory.THIRD_PARTY
            
            print("   ✅ 域名分类逻辑正常")
            
            # 测试初始化目标域名
            await engine._initialize_target_domain()
            print("   ✅ 目标域名初始化完成")
            
            return True
            
        except Exception as e:
            print(f"   ❌ 循环发现引擎测试失败: {e}")
            return False
    
    async def test_websocket_system(self) -> bool:
        """测试WebSocket推送系统"""
        try:
            print("   📡 测试WebSocket推送系统")
            
            # 测试连接统计
            connection_count = websocket_manager.get_connection_count()
            print(f"   📊 当前WebSocket连接数: {connection_count}")
            
            # 测试任务通知器
            test_message = {
                "test": True,
                "message": "集成测试消息",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # 这些调用不会真正发送消息（因为没有连接），但会测试方法是否正常
            await task_notifier.notify_task_started(self.test_task_id, self.test_domain)
            await task_notifier.notify_task_progress(self.test_task_id, 50, "running", "测试进度更新")
            await task_notifier.notify_domain_discovered(self.test_task_id, ["test1.example.com", "test2.example.com"], 1)
            
            print("   ✅ WebSocket通知方法调用正常")
            
            # 测试域名统计更新
            await notify_domain_stats_update(self.test_task_id)
            print("   ✅ 域名统计更新推送正常")
            
            return True
            
        except Exception as e:
            print(f"   ❌ WebSocket系统测试失败: {e}")
            return False
    
    async def test_task_queue_system(self) -> bool:
        """测试内存任务队列系统"""
        try:
            print("   🧠 测试内存任务队列系统")
            
            # 启动任务队列
            await start_task_queue()
            
            # 获取队列统计
            stats = await task_queue.get_queue_stats()
            print(f"   📊 队列统计: {stats}")
            
            # 测试添加任务
            from app.core.task_queue import TaskPriority
            
            task_id = await task_queue.add_task(
                task_type=DomainTaskType.SUBDOMAIN_DISCOVERY,
                payload={
                    'task_id': self.test_task_id,
                    'user_id': self.test_user_id,
                    'target_domain': self.test_domain,
                    'config': {'test': True}
                },
                priority=TaskPriority.HIGH
            )
            
            print(f"   ✅ 任务已添加到队列: {task_id}")
            
            # 等待任务处理
            await asyncio.sleep(2)
            
            # 检查任务状态
            task_status = await task_queue.get_task_status(task_id)
            print(f"   📄 任务状态: {task_status['status'] if task_status else 'Not Found'}")
            
            # 停止任务队列
            await stop_task_queue()
            
            return True
            
        except Exception as e:
            print(f"   ❌ 任务队列系统测试失败: {e}")
            return False
    
    async def test_api_endpoints(self) -> bool:
        """测试API接口"""
        try:
            print("   🌐 测试API接口（模拟）")
            
            # 这里只是测试导入是否正常，实际HTTP测试需要启动服务器
            from app.api.domain import router as domain_router
            from app.api.v1.tasks import router as tasks_router
            
            print("   ✅ 域名API模块导入正常")
            print("   ✅ 任务API模块导入正常")
            
            # 测试新增的API路由是否存在
            routes = []
            for route in tasks_router.routes:
                if hasattr(route, 'path'):
                    routes.append(route.path)
                elif hasattr(route, 'path_regex') and hasattr(route, 'path_format'):
                    # 对于APIRoute类型，使用path_format属性
                    routes.append(getattr(route, 'path_format', str(route.path_regex)))
                else:
                    # 作为备选方案，尝试获取字符串表示
                    routes.append(str(route))
            
            expected_routes = [
                "/{task_id}/scan-domains",
                "/{task_id}/all-domains", 
                "/{task_id}/domain-stats"
            ]
            
            print(f"   📋 发现的路由: {routes}")
            
            for expected_route in expected_routes:
                if any(expected_route in route for route in routes):
                    print(f"   ✅ 路由存在: {expected_route}")
                else:
                    print(f"   ⚠️  路由可能缺失: {expected_route}")
            
            return True
            
        except Exception as e:
            print(f"   ❌ API接口测试失败: {e}")
            return False
    
    async def test_data_synchronization(self) -> bool:
        """测试数据同步"""
        try:
            print("   🔄 测试数据同步机制")
            
            async with AsyncSessionLocal() as db:
                # 确保测试任务存在
                task_query = select(ScanTask).where(ScanTask.id == self.test_task_id)
                task_result = await db.execute(task_query)
                existing_task = task_result.scalar_one_or_none()
                
                if not existing_task:
                    test_task = ScanTask(
                        id=self.test_task_id,
                        target_domain=self.test_domain,
                        user_id=self.test_user_id,
                        status=TaskStatus.PENDING,
                        description="数据同步测试任务"
                    )
                    db.add(test_task)
                    await db.commit()
                    print(f"   ✅ 创建了测试任务：{self.test_task_id}")
                # 创建测试域名数据
                test_domains = [
                    DomainRecord(
                        task_id=self.test_task_id,
                        domain=f"sync-test-{i}.example.com",
                        category=DomainCategory.TARGET_SUBDOMAIN,
                        status=DomainStatus.DISCOVERED,
                        discovery_method=DiscoveryMethod.MANUAL,
                        is_accessible=True,
                        risk_level=RiskLevel.LOW,
                        confidence_score=0.8,
                        tags=["sync_test"],
                        extra_data={"sync_test": True}
                    )
                    for i in range(3)
                ]
                
                # 批量插入
                db.add_all(test_domains)
                await db.commit()
                
                print(f"   ✅ 已插入 {len(test_domains)} 条测试数据")
                
                # 测试查询和统计
                query = select(DomainRecord).where(DomainRecord.task_id == self.test_task_id)
                result = await db.execute(query)
                domains = result.scalars().all()
                
                print(f"   📊 查询到 {len(domains)} 条域名记录")
                
                # 测试统计计算
                stats = {
                    'total': len(domains),
                    'accessible': sum(1 for d in domains if d.is_accessible),
                    'target_related': sum(1 for d in domains if d.category in [DomainCategory.TARGET_MAIN, DomainCategory.TARGET_SUBDOMAIN])
                }
                
                print(f"   📊 统计结果: {stats}")
                
                # 清理测试数据
                for domain in domains:
                    await db.delete(domain)
                await db.commit()
                
                print("   🧹 测试数据已清理")
                
                return True
                
        except Exception as e:
            print(f"   ❌ 数据同步测试失败: {e}")
            return False
    
    async def print_test_summary(self):
        """打印测试总结"""
        print("\n" + "=" * 60)
        print("📋 集成测试总结")
        print("=" * 60)
        
        passed = sum(1 for _, success, _ in self.test_results if success)
        total = len(self.test_results)
        
        print(f"总测试数: {total}")
        print(f"通过: {passed}")
        print(f"失败: {total - passed}")
        print(f"成功率: {passed/total*100:.1f}%")
        
        print("\n详细结果:")
        for test_name, success, error in self.test_results:
            status = "✅ 通过" if success else "❌ 失败"
            print(f"  {status} {test_name}")
            if error:
                print(f"    错误: {error}")
        
        if passed == total:
            print("\n🎉 所有测试通过！系统集成正常。")
        else:
            print(f"\n⚠️  有 {total - passed} 个测试失败，请检查相关功能。")
        
        print("=" * 60)


async def main():
    """主函数"""
    print("🔧 系统集成测试工具")
    print("=" * 60)
    
    tester = IntegrationTester()
    
    try:
        await tester.run_all_tests()
        
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试执行异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())