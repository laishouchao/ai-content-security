#!/usr/bin/env python3
"""
简化的系统集成测试脚本
专注测试核心重构功能，避免复杂模块的导入问题
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
from sqlalchemy import select, text, func


class SimplifiedIntegrationTester:
    """简化的集成测试器"""
    
    def __init__(self):
        self.test_task_id = "simple_test_001"
        self.test_user_id = "test_user"
        self.test_domain = "example.com"
        self.test_results = []
    
    async def run_core_tests(self):
        """运行核心重构功能测试"""
        print("🧪 开始简化集成测试")
        print("=" * 60)
        
        tests = [
            ("数据库和域名表测试", self.test_database_basic),
            ("统一域名模型测试", self.test_domain_model),
            ("域名分类逻辑测试", self.test_domain_classification),
            ("数据库查询测试", self.test_database_queries),
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
    
    async def test_database_basic(self) -> bool:
        """测试基本数据库连接和表存在性"""
        try:
            async with AsyncSessionLocal() as db:
                # 检查表是否存在（兼容PostgreSQL）
                result = await db.execute(text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = 'domain_records'
                """))
                table_exists = result.fetchone() is not None
                
                if not table_exists:
                    print("   ⚠️  domain_records表不存在")
                    return False
                
                print(f"   ✅ domain_records表存在")
                
                # 检查旧表是否已删除
                old_tables = ['subdomain_records', 'third_party_domains']
                for table_name in old_tables:
                    result = await db.execute(text(f"""
                        SELECT table_name FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = '{table_name}'
                    """))
                    if result.fetchone():
                        print(f"   ⚠️  旧表 {table_name} 仍存在")
                        return False
                    else:
                        print(f"   ✅ 旧表 {table_name} 已删除")
                
                return True
                
        except Exception as e:
            print(f"   ❌ 数据库测试失败: {e}")
            return False
    
    async def test_domain_model(self) -> bool:
        """测试统一域名模型"""
        try:
            async with AsyncSessionLocal() as db:
                # 创建测试用户（如果不存在）
                from app.models.user import User
                user_query = select(User).where(User.id == self.test_user_id)
                user_result = await db.execute(user_query)
                existing_user = user_result.scalar_one_or_none()
                
                if not existing_user:
                    test_user = User(
                        id=self.test_user_id,
                        username="test_user",
                        email="test@example.com",
                        password_hash="test_hash",
                        is_active=True
                    )
                    db.add(test_user)
                    await db.commit()
                    print(f"   ✅ 创建了测试用户: {self.test_user_id}")
                # 创建测试任务
                task_query = select(ScanTask).where(ScanTask.id == self.test_task_id)
                task_result = await db.execute(task_query)
                existing_task = task_result.scalar_one_or_none()
                
                if not existing_task:
                    test_task = ScanTask(
                        id=self.test_task_id,
                        target_domain=self.test_domain,
                        user_id=self.test_user_id,
                        status=TaskStatus.PENDING,
                        description="简化集成测试任务",
                        config={}
                    )
                    db.add(test_task)
                    await db.commit()
                    print(f"   ✅ 创建了测试任务: {self.test_task_id}")
                
                # 测试插入域名记录
                test_domain = DomainRecord(
                    task_id=self.test_task_id,
                    domain="test.example.com",
                    category=DomainCategory.TARGET_SUBDOMAIN,
                    status=DomainStatus.DISCOVERED,
                    discovery_method=DiscoveryMethod.MANUAL,
                    is_accessible=True,
                    risk_level=RiskLevel.LOW,
                    confidence_score=0.8,
                    tags=["test"],
                    extra_data={"test": True}
                )
                
                db.add(test_domain)
                await db.commit()
                print(f"   ✅ 成功插入域名记录")
                
                # 测试查询
                query = select(DomainRecord).where(DomainRecord.task_id == self.test_task_id)
                result = await db.execute(query)
                domains = result.scalars().all()
                
                print(f"   📊 查询到 {len(domains)} 条域名记录")
                
                # 验证字段值
                domain = domains[0]
                assert domain.category == DomainCategory.TARGET_SUBDOMAIN
                assert domain.status == DomainStatus.DISCOVERED
                assert domain.is_accessible == True
                print(f"   ✅ 域名模型字段验证通过")
                
                # 清理测试数据
                for domain in domains:
                    await db.delete(domain)
                await db.commit()
                print(f"   🧹 测试数据已清理")
                
                return True
                
        except Exception as e:
            print(f"   ❌ 域名模型测试失败: {e}")
            return False
    
    async def test_domain_classification(self) -> bool:
        """测试域名分类逻辑"""
        try:
            from app.engines.domain_discovery_engine import ContinuousDomainDiscoveryEngine
            
            # 创建引擎实例（不初始化数据库）
            engine = ContinuousDomainDiscoveryEngine(
                task_id=self.test_task_id,
                user_id=self.test_user_id,
                target_domain=self.test_domain
            )
            
            # 测试域名分类功能
            test_cases = [
                ("example.com", DomainCategory.TARGET_MAIN),
                ("www.example.com", DomainCategory.TARGET_SUBDOMAIN), 
                ("api.example.com", DomainCategory.TARGET_SUBDOMAIN),
                ("google.com", DomainCategory.THIRD_PARTY),
                ("cdn.cloudflare.com", DomainCategory.THIRD_PARTY)
            ]
            
            for domain, expected_category in test_cases:
                actual_category = engine._classify_domain(domain)
                if actual_category == expected_category:
                    print(f"   ✅ {domain} -> {actual_category}")
                else:
                    print(f"   ❌ {domain} -> {actual_category} (期望: {expected_category})")
                    return False
            
            print("   ✅ 域名分类逻辑正常")
            return True
            
        except Exception as e:
            print(f"   ❌ 域名分类测试失败: {e}")
            return False
    
    async def test_database_queries(self) -> bool:
        """测试数据库查询功能"""
        try:
            async with AsyncSessionLocal() as db:
                # 测试统计查询
                count_query = select(func.count(DomainRecord.id))
                count_result = await db.execute(count_query)
                total_domains = count_result.scalar()
                print(f"   📊 当前域名记录总数: {total_domains}")
                
                # 测试按分类查询
                main_query = select(func.count(DomainRecord.id)).where(
                    DomainRecord.category == DomainCategory.TARGET_MAIN
                )
                main_result = await db.execute(main_query)
                main_count = main_result.scalar()
                print(f"   📊 主域名数量: {main_count}")
                
                # 测试按任务查询
                task_query = select(func.count(DomainRecord.id)).where(
                    DomainRecord.task_id == self.test_task_id
                )
                task_result = await db.execute(task_query)
                task_count = task_result.scalar()
                print(f"   📊 测试任务域名数量: {task_count}")
                
                print("   ✅ 数据库查询功能正常")
                return True
                
        except Exception as e:
            print(f"   ❌ 数据库查询测试失败: {e}")
            return False
    
    async def print_test_summary(self):
        """打印测试总结"""
        print("\n" + "=" * 60)
        print("📋 简化集成测试总结")
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
            print("\n🎉 所有核心测试通过！重构基础功能正常。")
        else:
            print(f"\n⚠️  有 {total - passed} 个测试失败，需要进一步修复。")
        
        print("=" * 60)


async def main():
    """主函数"""
    print("🔧 简化系统集成测试工具")
    print("=" * 60)
    
    tester = SimplifiedIntegrationTester()
    
    try:
        await tester.run_core_tests()
        
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试执行异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())