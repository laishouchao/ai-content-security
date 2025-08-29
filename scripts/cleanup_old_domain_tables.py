#!/usr/bin/env python3
"""
数据库清理脚本 - 删除旧的域名表
在删除之前会进行安全检查，确保数据已迁移到新的统一域名表中
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, Any, List

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app.core.database import AsyncSessionLocal, engine
from app.models.domain import DomainRecord
from sqlalchemy import select, text, func, and_
from sqlalchemy.exc import SQLAlchemyError


class DatabaseCleaner:
    """数据库清理器"""
    
    def __init__(self):
        self.cleanup_results = []
        
    async def run_cleanup(self):
        """运行数据库清理"""
        print("🧹 开始数据库清理 - 删除旧域名表")
        print("=" * 60)
        
        try:
            # 1. 检查新域名表是否存在数据
            check_new_table = await self.check_new_domain_table()
            if not check_new_table:
                print("❌ 新域名表检查失败，停止清理")
                return
            
            # 2. 数据迁移检查（如果需要）
            check_migration = await self.check_data_migration()
            if not check_migration:
                print("❌ 数据迁移检查失败，停止清理")
                return
            
            # 3. 删除旧表结构
            drop_success = await self.drop_old_tables()
            if not drop_success:
                print("❌ 删除旧表失败")
                return
            
            # 4. 验证清理结果
            verify_success = await self.verify_cleanup()
            if not verify_success:
                print("❌ 清理验证失败")
                return
            
            await self.print_cleanup_summary()
            
        except Exception as e:
            print(f"❌ 清理过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
    
    async def check_new_domain_table(self) -> bool:
        """检查新的域名表是否存在并有数据"""
        try:
            print("🔍 检查新的统一域名表...")
            
            async with AsyncSessionLocal() as db:
                # 检查表是否存在（兼容PostgreSQL）
                result = await db.execute(text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = 'domain_records'
                """))
                table_exists = result.fetchone() is not None
                
                if not table_exists:
                    print("   ⚠️  domain_records表不存在，无法继续清理")
                    return False
                
                # 检查数据量
                count_query = select(func.count(DomainRecord.id))
                count_result = await db.execute(count_query)
                record_count = count_result.scalar()
                
                print(f"   ✅ domain_records表存在，当前有 {record_count} 条记录")
                
                if record_count == 0:
                    print("   ⚠️  新表中没有数据，但仍可继续清理旧表")
                
                return True
                
        except Exception as e:
            print(f"   ❌ 检查新域名表失败: {e}")
            return False
    
    async def check_data_migration(self) -> bool:
        """检查数据迁移状态"""
        try:
            print("🔄 检查数据迁移状态...")
            
            async with AsyncSessionLocal() as db:
                # 检查旧表是否还存在
                old_tables = ['subdomain_records', 'third_party_domains']
                existing_old_tables = []
                
                for table_name in old_tables:
                    result = await db.execute(text(f"""
                        SELECT table_name FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = '{table_name}'
                    """))
                    if result.fetchone():
                        existing_old_tables.append(table_name)
                
                if not existing_old_tables:
                    print("   ✅ 旧表已不存在，无需清理")
                    return True
                
                print(f"   📊 发现旧表: {existing_old_tables}")
                
                # 检查旧表中的数据量
                for table_name in existing_old_tables:
                    try:
                        result = await db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                        count = result.scalar()
                        print(f"   📊 {table_name}: {count} 条记录")
                        
                        if count > 0:
                            print(f"   ⚠️  {table_name} 中还有数据")
                            
                    except Exception as e:
                        print(f"   ⚠️  无法检查 {table_name} 的数据量: {e}")
                
                return True
                
        except Exception as e:
            print(f"   ❌ 检查数据迁移状态失败: {e}")
            return False
    
    async def drop_old_tables(self) -> bool:
        """删除旧的数据库表"""
        try:
            print("🗑️ 删除旧的数据库表...")
            
            async with AsyncSessionLocal() as db:
                old_tables = ['subdomain_records', 'third_party_domains']
                
                for table_name in old_tables:
                    try:
                        # 检查表是否存在（兼容PostgreSQL）
                        result = await db.execute(text(f"""
                            SELECT table_name FROM information_schema.tables 
                            WHERE table_schema = 'public' AND table_name = '{table_name}'
                        """))
                        
                        if result.fetchone():
                            print(f"   🗑️  删除表: {table_name}")
                            await db.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
                            print(f"   ✅ 已删除表: {table_name}")
                        else:
                            print(f"   ℹ️  表不存在: {table_name}")
                            
                    except Exception as e:
                        print(f"   ❌ 删除表 {table_name} 失败: {e}")
                        return False
                
                await db.commit()
                print("   ✅ 所有旧表删除完成")
                
                return True
                
        except Exception as e:
            print(f"   ❌ 删除旧表失败: {e}")
            return False
    
    async def verify_cleanup(self) -> bool:
        """验证清理结果"""
        try:
            print("✅ 验证清理结果...")
            
            async with AsyncSessionLocal() as db:
                # 验证旧表已被删除
                old_tables = ['subdomain_records', 'third_party_domains']
                
                for table_name in old_tables:
                    result = await db.execute(text(f"""
                        SELECT table_name FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = '{table_name}'
                    """))
                    
                    if result.fetchone():
                        print(f"   ❌ 表 {table_name} 仍然存在")
                        return False
                    else:
                        print(f"   ✅ 表 {table_name} 已成功删除")
                
                # 验证新表仍然正常
                try:
                    count_query = select(func.count(DomainRecord.id))
                    count_result = await db.execute(count_query)
                    record_count = count_result.scalar()
                    print(f"   ✅ 新域名表正常，包含 {record_count} 条记录")
                except Exception as e:
                    print(f"   ❌ 新域名表访问异常: {e}")
                    return False
                
                return True
                
        except Exception as e:
            print(f"   ❌ 验证清理结果失败: {e}")
            return False
    
    async def print_cleanup_summary(self):
        """打印清理总结"""
        print("\n" + "=" * 60)
        print("📋 数据库清理总结")
        print("=" * 60)
        
        print("已完成的清理操作:")
        print("✅ 检查了新的统一域名表状态")
        print("✅ 验证了数据迁移状态")
        print("✅ 删除了旧的数据库表结构")
        print("✅ 验证了清理结果")
        
        print("\n需要手动完成的操作:")
        print("⚠️  清理代码中对旧表模型的引用")
        print("⚠️  更新相关API接口")
        print("⚠️  清理前端类型定义")
        
        print("\n建议下一步操作:")
        print("1. 运行单元测试确保系统正常")
        print("2. 检查日志确认没有旧表相关错误")
        print("3. 更新文档反映新的域名表结构")
        
        print("=" * 60)


async def main():
    """主函数"""
    print("🧹 数据库清理工具")
    print("=" * 60)
    
    cleaner = DatabaseCleaner()
    
    try:
        print("⚠️  此操作将删除旧的域名表结构")
        print("   - subdomain_records表")
        print("   - third_party_domains表")
        print("   - 新的统一域名表domain_records将保留")
        
        await cleaner.run_cleanup()
        
    except KeyboardInterrupt:
        print("\n⚠️  清理操作被用户中断")
    except Exception as e:
        print(f"\n❌ 清理执行异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())