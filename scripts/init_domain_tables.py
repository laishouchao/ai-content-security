#!/usr/bin/env python3
"""
简化的数据库初始化脚本
直接创建新的域名表结构，暂时不删除旧表以保持兼容性
"""

import asyncio
import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy import text
from app.core.database import AsyncSessionLocal, engine


async def init_domain_tables():
    """初始化新的域名表结构"""
    print("🚀 初始化新的域名表结构...")
    
    try:
        # 创建新的域名表的SQL
        create_domain_table_sql = """
        CREATE TABLE IF NOT EXISTS domain_records (
            id VARCHAR(36) PRIMARY KEY,
            task_id VARCHAR(36) NOT NULL,
            domain VARCHAR(255) NOT NULL,
            category VARCHAR(50) DEFAULT 'unknown' NOT NULL,
            status VARCHAR(50) DEFAULT 'discovered' NOT NULL,
            discovery_method VARCHAR(50) NOT NULL,
            ip_address VARCHAR(45),
            is_accessible BOOLEAN DEFAULT FALSE NOT NULL,
            response_code INTEGER,
            response_time FLOAT,
            server_header VARCHAR(255),
            content_type VARCHAR(100),
            page_title VARCHAR(500),
            page_description TEXT,
            content_hash VARCHAR(64),
            found_on_urls JSON,
            parent_domain VARCHAR(255),
            depth_level INTEGER DEFAULT 0 NOT NULL,
            risk_level VARCHAR(20) DEFAULT 'low' NOT NULL,
            confidence_score FLOAT DEFAULT 0.0 NOT NULL,
            screenshot_path VARCHAR(500),
            html_content_path VARCHAR(500),
            is_analyzed BOOLEAN DEFAULT FALSE NOT NULL,
            analysis_error TEXT,
            ai_analysis_result JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            first_discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            last_accessed_at TIMESTAMP,
            analyzed_at TIMESTAMP,
            extra_data JSON,
            tags JSON,
            
            -- 外键约束
            FOREIGN KEY (task_id) REFERENCES scan_tasks(id) ON DELETE CASCADE
        );
        """
        
        # 创建索引的SQL
        create_indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_domain_records_task_id ON domain_records(task_id);",
            "CREATE INDEX IF NOT EXISTS idx_domain_records_domain ON domain_records(domain);",
            "CREATE INDEX IF NOT EXISTS idx_domain_records_category ON domain_records(category);",
            "CREATE INDEX IF NOT EXISTS idx_domain_records_status ON domain_records(status);",
            "CREATE INDEX IF NOT EXISTS idx_domain_records_discovery_method ON domain_records(discovery_method);",
            "CREATE INDEX IF NOT EXISTS idx_domain_records_is_accessible ON domain_records(is_accessible);",
            "CREATE INDEX IF NOT EXISTS idx_domain_records_risk_level ON domain_records(risk_level);",
            "CREATE INDEX IF NOT EXISTS idx_domain_records_is_analyzed ON domain_records(is_analyzed);",
            "CREATE INDEX IF NOT EXISTS idx_domain_records_created_at ON domain_records(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_domain_records_parent_domain ON domain_records(parent_domain);"
        ]
        
        # 更新ViolationRecord表，添加对新域名表的关联
        update_violation_table_sql = """
        ALTER TABLE violation_records 
        ADD COLUMN IF NOT EXISTS domain_record_id VARCHAR(36);
        """
        
        # 创建外键约束（如果不存在）
        add_foreign_key_sql = """
        -- 这里可以添加外键约束，但由于SQLite的限制，我们跳过这一步
        -- ALTER TABLE violation_records 
        -- ADD CONSTRAINT fk_violation_domain_record 
        -- FOREIGN KEY (domain_record_id) REFERENCES domain_records(id) ON DELETE CASCADE;
        """
        
        async with engine.begin() as conn:
            # 创建主表
            print("   📋 创建 domain_records 表...")
            await conn.execute(text(create_domain_table_sql))
            
            # 创建索引
            print("   🔍 创建索引...")
            for index_sql in create_indexes_sql:
                await conn.execute(text(index_sql))
            
            # 更新违规记录表
            print("   🔄 更新 violation_records 表...")
            await conn.execute(text(update_violation_table_sql))
            
            print("   ✅ 数据库表结构初始化完成")
        
        print("🎉 新的域名表结构创建成功！")
        
    except Exception as e:
        print(f"❌ 创建表结构失败: {e}")
        raise


async def main():
    """主函数"""
    print("🔧 数据库初始化工具")
    print("=" * 60)
    
    try:
        await init_domain_tables()
        print("\n🎉 初始化成功完成！")
        
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())