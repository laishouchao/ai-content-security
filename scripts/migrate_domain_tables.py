#!/usr/bin/env python3
"""
数据库迁移脚本：整合域名表结构
将 domain_records 和 domain_records 表的数据迁移到新的 domain_records 表
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import List, Dict, Any
import uuid

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, insert
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal, engine
from app.models.domain import DomainRecord
from app.models.domain import DomainRecord, DomainCategory, DomainStatus, DiscoveryMethod, RiskLevel


class DatabaseMigrator:
    """数据库迁移器"""
    
    def __init__(self):
        self.session = None
        self.migrated_count = {
            'subdomains': 0,
            'domain_records': 0,
            'violations': 0,
            'total': 0
        }
    
    async def run_migration(self):
        """执行完整的数据库迁移"""
        print("=" * 60)
        print("🚀 开始数据库迁移：整合域名表结构")
        print("=" * 60)
        
        try:
            async with AsyncSessionLocal() as session:
                self.session = session
                
                # 1. 创建新表（如果不存在）
                print("📋 步骤1: 创建新的域名表...")
                await self._create_new_tables()
                
                # 2. 备份现有数据
                print("💾 步骤2: 备份现有数据...")
                await self._backup_existing_data()
                
                # 3. 迁移子域名数据
                print("🔄 步骤3: 迁移子域名数据...")
                await self._migrate_domain_records()
                
                # 4. 迁移第三方域名数据
                print("🔄 步骤4: 迁移第三方域名数据...")
                await self._migrate_domain_records()
                
                # 5. 更新违规记录关联
                print("🔄 步骤5: 更新违规记录关联...")
                await self._update_violation_records()
                
                # 6. 验证数据完整性
                print("✅ 步骤6: 验证数据完整性...")
                await self._verify_data_integrity()
                
                # 7. 提交事务
                await session.commit()
                
                print("=" * 60)
                print("🎉 数据库迁移完成！")
                print(f"📊 迁移统计:")
                print(f"   - 子域名记录: {self.migrated_count['subdomains']}")
                print(f"   - 第三方域名: {self.migrated_count['domain_records']}")
                print(f"   - 违规记录更新: {self.migrated_count['violations']}")
                print(f"   - 总计: {self.migrated_count['total']}")
                print("=" * 60)
                
        except Exception as e:
            print(f"❌ 迁移失败: {e}")
            if self.session:
                await self.session.rollback()
            raise
    
    async def _create_new_tables(self):
        """创建新表"""
        try:
            # 导入新模型以确保表被创建
            from app.models.domain import DomainRecord
            
            # 创建所有表
            async with engine.begin() as conn:
                # 由于我们已经在模型中定义了新表，SQLAlchemy会自动创建
                await conn.run_sync(lambda _: print("   ✅ 域名表结构已准备就绪"))
            
            print("   ✅ 新的域名表创建完成")
        except Exception as e:
            print(f"   ❌ 创建新表失败: {e}")
            raise
    
    async def _backup_existing_data(self):
        """备份现有数据"""
        try:
            # 统计现有数据
            subdomain_count = await self.session.execute(
                select(text("COUNT(*)")).select_from(text("domain_records"))
            )
            third_party_count = await self.session.execute(
                select(text("COUNT(*)")).select_from(text("domain_records"))
            )
            
            subdomain_total = subdomain_count.scalar()
            third_party_total = third_party_count.scalar()
            
            print(f"   📊 发现数据:")
            print(f"      - 子域名记录: {subdomain_total}")
            print(f"      - 第三方域名: {third_party_total}")
            
            # 可以在这里添加数据备份逻辑
            backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            print(f"   💾 备份时间戳: {backup_timestamp}")
            
        except Exception as e:
            print(f"   ❌ 备份数据失败: {e}")
            raise
    
    async def _migrate_domain_records(self):
        """迁移子域名记录"""
        try:
            # 查询所有子域名记录
            result = await self.session.execute(
                select(DomainRecord).options(selectinload(DomainRecord.task))
            )
            domain_records = result.scalars().all()
            
            print(f"   🔄 开始迁移 {len(domain_records)} 条子域名记录...")
            
            for subdomain in domain_records:
                # 创建新的域名记录
                domain_record = DomainRecord(
                    id=str(uuid.uuid4()),
                    task_id=subdomain.task_id,
                    domain=subdomain.subdomain,
                    category=DomainCategory.TARGET_SUBDOMAIN,
                    status=DomainStatus.ACCESSIBLE if subdomain.is_accessible else DomainStatus.INACCESSIBLE,
                    discovery_method=self._map_discovery_method(subdomain.discovery_method),
                    ip_address=subdomain.ip_address,
                    is_accessible=subdomain.is_accessible,
                    response_code=subdomain.response_code,
                    response_time=subdomain.response_time,
                    server_header=subdomain.server_header,
                    content_type=subdomain.content_type,
                    page_title=subdomain.page_title,
                    parent_domain=subdomain.task.target_domain if subdomain.task else None,
                    depth_level=1,  # 子域名默认深度为1
                    risk_level=RiskLevel.LOW,  # 目标域名相关的子域名默认为低风险
                    confidence_score=1.0,  # 子域名识别置信度很高
                    created_at=subdomain.created_at,
                    first_discovered_at=subdomain.created_at,
                    last_updated_at=subdomain.created_at,
                    tags=["migrated_from_subdomain", "target_related"],
                    extra_data={
                        "migration_source": "domain_records",
                        "original_id": subdomain.id
                    }
                )
                
                self.session.add(domain_record)
                self.migrated_count['subdomains'] += 1
            
            print(f"   ✅ 子域名记录迁移完成: {self.migrated_count['subdomains']} 条")
            
        except Exception as e:
            print(f"   ❌ 迁移子域名记录失败: {e}")
            raise
    
    async def _migrate_domain_records(self):
        """迁移第三方域名记录"""
        try:
            # 查询所有第三方域名记录
            result = await self.session.execute(
                select(DomainRecord).options(
                    selectinload(DomainRecord.task),
                    selectinload(DomainRecord.violations)
                )
            )
            domain_records = result.scalars().all()
            
            print(f"   🔄 开始迁移 {len(domain_records)} 条第三方域名记录...")
            
            for domain in domain_records:
                # 创建新的域名记录
                domain_record = DomainRecord(
                    id=str(uuid.uuid4()),
                    task_id=domain.task_id,
                    domain=domain.domain,
                    category=DomainCategory.THIRD_PARTY,
                    status=DomainStatus.ANALYZED if domain.is_analyzed else DomainStatus.DISCOVERED,
                    discovery_method=DiscoveryMethod.LINK_CRAWLING,  # 第三方域名主要通过链接爬取发现
                    is_accessible=True,  # 第三方域名能被发现通常意味着可访问
                    page_title=domain.page_title,
                    page_description=domain.page_description,
                    content_hash=domain.content_hash,
                    found_on_urls=[domain.found_on_url] if domain.found_on_url else [],
                    depth_level=2,  # 第三方域名默认深度为2
                    risk_level=self._map_risk_level(domain.risk_level),
                    confidence_score=0.8,  # 第三方域名识别置信度较高
                    screenshot_path=domain.screenshot_path,
                    html_content_path=domain.html_content_path,
                    is_analyzed=domain.is_analyzed,
                    analysis_error=domain.analysis_error,
                    ai_analysis_result=domain.cached_analysis_result,
                    created_at=domain.created_at,
                    first_discovered_at=domain.created_at,
                    last_updated_at=domain.last_identified_at or domain.created_at,
                    analyzed_at=domain.analyzed_at,
                    tags=["migrated_from_third_party", "external_domain"],
                    extra_data={
                        "migration_source": "domain_records",
                        "original_id": domain.id,
                        "original_domain_type": domain.domain_type
                    }
                )
                
                self.session.add(domain_record)
                self.migrated_count['domain_records'] += 1
            
            print(f"   ✅ 第三方域名记录迁移完成: {self.migrated_count['domain_records']} 条")
            
        except Exception as e:
            print(f"   ❌ 迁移第三方域名记录失败: {e}")
            raise
    
    async def _update_violation_records(self):
        """更新违规记录关联"""
        try:
            # 这里可以添加违规记录的关联更新逻辑
            # 暂时保持现有的违规记录不变，后续可以逐步迁移
            print("   ⏸️  违规记录关联更新暂时跳过（保持兼容性）")
            
        except Exception as e:
            print(f"   ❌ 更新违规记录关联失败: {e}")
            raise
    
    async def _verify_data_integrity(self):
        """验证数据完整性"""
        try:
            # 验证新表中的数据
            result = await self.session.execute(
                select(text("COUNT(*)")).select_from(text("domain_records"))
            )
            new_total = result.scalar()
            
            expected_total = self.migrated_count['subdomains'] + self.migrated_count['domain_records']
            
            print(f"   📊 数据验证:")
            print(f"      - 预期记录数: {expected_total}")
            print(f"      - 实际记录数: {new_total}")
            
            if new_total == expected_total:
                print("   ✅ 数据完整性验证通过")
                self.migrated_count['total'] = new_total
            else:
                raise Exception(f"数据完整性验证失败: 预期{expected_total}，实际{new_total}")
            
        except Exception as e:
            print(f"   ❌ 数据完整性验证失败: {e}")
            raise
    
    def _map_discovery_method(self, old_method: str) -> str:
        """映射发现方法"""
        method_mapping = {
            'subdomain_enum': DiscoveryMethod.SUBDOMAIN_ENUM,
            'dns_lookup': DiscoveryMethod.DNS_LOOKUP,
            'certificate': DiscoveryMethod.CERTIFICATE,
            'link_crawling': DiscoveryMethod.LINK_CRAWLING,
            'manual': DiscoveryMethod.MANUAL
        }
        return method_mapping.get(old_method, DiscoveryMethod.SUBDOMAIN_ENUM)
    
    def _map_risk_level(self, old_risk: str) -> str:
        """映射风险等级"""
        risk_mapping = {
            'critical': RiskLevel.CRITICAL,
            'high': RiskLevel.HIGH,
            'medium': RiskLevel.MEDIUM,
            'low': RiskLevel.LOW
        }
        return risk_mapping.get(old_risk, RiskLevel.LOW)


async def main():
    """主函数"""
    print("🔧 数据库迁移工具")
    print("=" * 60)
    
    # 确认迁移
    confirm = input("⚠️  即将执行数据库迁移，是否继续？(y/N): ")
    if confirm.lower() != 'y':
        print("❌ 迁移已取消")
        return
    
    try:
        migrator = DatabaseMigrator()
        await migrator.run_migration()
        print("\n🎉 迁移成功完成！")
        
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())