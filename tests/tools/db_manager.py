#!/usr/bin/env python3
"""
数据库管理工具

用于初始化数据库、创建迁移、应用迁移等操作
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from alembic.config import Config
from alembic import command
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings
from app.core.database import Base
from app.models import *  # 导入所有模型


async def init_db():
    """初始化数据库"""
    print("正在初始化数据库...")
    
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✓ 数据库初始化成功")
    except Exception as e:
        print(f"✗ 数据库初始化失败: {e}")
        raise
    finally:
        await engine.dispose()


async def drop_all_tables():
    """删除所有表"""
    print("警告: 正在删除所有数据库表...")
    response = input("确认删除所有表? (yes/no): ")
    if response.lower() != 'yes':
        print("操作已取消")
        return
    
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        print("✓ 所有表已删除")
    except Exception as e:
        print(f"✗ 删除表失败: {e}")
        raise
    finally:
        await engine.dispose()


def create_migration(message: str):
    """创建新的迁移文件"""
    print(f"正在创建迁移: {message}")
    
    alembic_cfg = Config("alembic.ini")
    
    try:
        command.revision(alembic_cfg, message=message, autogenerate=True)
        print("✓ 迁移文件创建成功")
    except Exception as e:
        print(f"✗ 创建迁移失败: {e}")
        raise


def upgrade_db(revision: str = "head"):
    """应用数据库迁移"""
    print(f"正在应用迁移到版本: {revision}")
    
    alembic_cfg = Config("alembic.ini")
    
    try:
        command.upgrade(alembic_cfg, revision)
        print("✓ 数据库迁移成功")
    except Exception as e:
        print(f"✗ 数据库迁移失败: {e}")
        raise


def downgrade_db(revision: str):
    """回滚数据库迁移"""
    print(f"正在回滚到版本: {revision}")
    
    alembic_cfg = Config("alembic.ini")
    
    try:
        command.downgrade(alembic_cfg, revision)
        print("✓ 数据库回滚成功")
    except Exception as e:
        print(f"✗ 数据库回滚失败: {e}")
        raise


def show_current_revision():
    """显示当前数据库版本"""
    alembic_cfg = Config("alembic.ini")
    
    try:
        command.current(alembic_cfg)
    except Exception as e:
        print(f"✗ 获取当前版本失败: {e}")
        raise


def show_migration_history():
    """显示迁移历史"""
    alembic_cfg = Config("alembic.ini")
    
    try:
        command.history(alembic_cfg)
    except Exception as e:
        print(f"✗ 获取迁移历史失败: {e}")
        raise


async def create_admin_user():
    """创建管理员用户"""
    from app.models.user import User, UserRole
    from app.core.database import AsyncSessionLocal
    from passlib.context import CryptContext
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    print("创建管理员用户...")
    username = input("用户名: ")
    email = input("邮箱: ")
    password = input("密码: ")
    
    if not all([username, email, password]):
        print("✗ 所有字段都是必填的")
        return
    
    async with AsyncSessionLocal() as session:
        try:
            # 检查用户是否已存在
            from sqlalchemy import select
            stmt = select(User).where(
                (User.username == username) | (User.email == email)
            )
            result = await session.execute(stmt)
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print("✗ 用户名或邮箱已存在")
                return
            
            # 创建管理员用户
            admin_user = User(
                username=username,
                email=email,
                password_hash=pwd_context.hash(password),
                role=UserRole.ADMIN,
                is_active=True
            )
            
            session.add(admin_user)
            await session.commit()
            
            print(f"✓ 管理员用户 '{username}' 创建成功")
            
        except Exception as e:
            await session.rollback()
            print(f"✗ 创建管理员用户失败: {e}")
            raise


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  python db_manager.py init                 # 初始化数据库")
        print("  python db_manager.py drop                 # 删除所有表")
        print("  python db_manager.py migrate <message>    # 创建迁移")
        print("  python db_manager.py upgrade [revision]   # 应用迁移")
        print("  python db_manager.py downgrade <revision> # 回滚迁移")
        print("  python db_manager.py current              # 显示当前版本")
        print("  python db_manager.py history              # 显示迁移历史")
        print("  python db_manager.py create-admin         # 创建管理员用户")
        return
    
    command_name = sys.argv[1]
    
    try:
        if command_name == "init":
            asyncio.run(init_db())
        elif command_name == "drop":
            asyncio.run(drop_all_tables())
        elif command_name == "migrate":
            if len(sys.argv) < 3:
                print("错误: 请提供迁移消息")
                return
            message = sys.argv[2]
            create_migration(message)
        elif command_name == "upgrade":
            revision = sys.argv[2] if len(sys.argv) > 2 else "head"
            upgrade_db(revision)
        elif command_name == "downgrade":
            if len(sys.argv) < 3:
                print("错误: 请提供回滚版本")
                return
            revision = sys.argv[2]
            downgrade_db(revision)
        elif command_name == "current":
            show_current_revision()
        elif command_name == "history":
            show_migration_history()
        elif command_name == "create-admin":
            asyncio.run(create_admin_user())
        else:
            print(f"错误: 未知命令 '{command_name}'")
            
    except KeyboardInterrupt:
        print("\n操作已取消")
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()