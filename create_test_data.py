#!/usr/bin/env python3
"""
测试数据生成脚本
用于生成仪表板功能所需的测试数据
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
import uuid
import random

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal, engine
from app.models.task import (
    ScanTask, TaskStatus, ViolationRecord, ViolationType, 
    RiskLevel, ThirdPartyDomain, DomainType, SubdomainRecord
)
from app.models.user import User


async def create_test_data():
    """创建测试数据"""
    async with AsyncSessionLocal() as db:
        try:
            # 检查是否已有用户，如果没有则创建一个测试用户
            from sqlalchemy import select
            user_query = select(User).limit(1)
            result = await db.execute(user_query)
            user = result.scalar_one_or_none()
            
            if not user:
                # 创建测试用户
                user = User(
                    id=str(uuid.uuid4()),
                    username="testuser",
                    email="test@example.com",
                    hashed_password="dummy_hash",
                    is_active=True,
                    is_superuser=False,
                    created_at=datetime.utcnow()
                )
                db.add(user)
                await db.commit()
                print(f"创建测试用户: {user.username}")
            
            # 清理已存在的测试数据
            await db.execute(select(ScanTask).where(ScanTask.user_id == user.id))
            existing_tasks = (await db.execute(select(ScanTask).where(ScanTask.user_id == user.id))).scalars().all()
            for task in existing_tasks:
                await db.delete(task)
            await db.commit()
            
            # 生成最近30天的测试任务数据
            domains = ['example.com', 'test.org', 'demo.net', 'sample.io', 'mock.dev']
            statuses = [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.RUNNING, TaskStatus.PENDING]
            violation_types = [ViolationType.NSFW, ViolationType.FRAUD, ViolationType.GAMBLING, ViolationType.MALWARE]
            risk_levels = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
            
            tasks_created = 0
            for day_offset in range(30, 0, -1):
                # 每天创建1-3个任务
                task_count = random.randint(1, 3)
                
                for i in range(task_count):
                    created_time = datetime.utcnow() - timedelta(days=day_offset, hours=random.randint(0, 23))
                    status = random.choice(statuses)
                    
                    # 预先生成统计数据和时间
                    total_violations_count = random.randint(0, 10)
                    total_third_party_count = random.randint(1, 20)
                    started_time = created_time + timedelta(minutes=1) if status != TaskStatus.PENDING else None
                    completed_time = created_time + timedelta(hours=random.randint(1, 6)) if status in [TaskStatus.COMPLETED, TaskStatus.FAILED] else None
                    
                    task = ScanTask(
                        id=str(uuid.uuid4()),
                        user_id=user.id,
                        target_domain=random.choice(domains),
                        task_name=f"测试任务 {tasks_created + 1}",
                        description=f"自动生成的测试扫描任务",
                        status=status,
                        progress=100 if status == TaskStatus.COMPLETED else random.randint(0, 90),
                        config={
                            "subdomain_discovery_enabled": True,
                            "ai_analysis_enabled": True,
                            "max_subdomains": 100
                        },
                        total_subdomains=random.randint(5, 50),
                        total_pages_crawled=random.randint(10, 200),
                        total_third_party_domains=total_third_party_count,
                        total_violations=total_violations_count,
                        critical_violations=random.randint(0, 2),
                        high_violations=random.randint(0, 3),
                        medium_violations=random.randint(0, 5),
                        low_violations=random.randint(0, 10),
                        created_at=created_time,
                        started_at=started_time,
                        completed_at=completed_time
                    )
                    
                    db.add(task)
                    tasks_created += 1
                    
                    # 为已完成的任务创建第三方域名和违规记录
                    if status == TaskStatus.COMPLETED and total_violations_count > 0:
                        # 创建第三方域名
                        for j in range(min(total_third_party_count, 5)):
                            third_party = ThirdPartyDomain(
                                id=str(uuid.uuid4()),
                                task_id=task.id,
                                domain=f"third-party-{j+1}.com",
                                found_on_url=f"https://{task.target_domain}/page-{j+1}",
                                domain_type=random.choice(list(DomainType)),
                                risk_level=random.choice(list(RiskLevel)),
                                page_title=f"第三方页面 {j+1}",
                                is_analyzed=True,
                                created_at=started_time,
                                analyzed_at=started_time + timedelta(minutes=30) if started_time else None
                            )
                            db.add(third_party)
                            
                            # 为一些第三方域名创建违规记录
                            if random.random() < 0.3:  # 30%概率有违规
                                violation = ViolationRecord(
                                    id=str(uuid.uuid4()),
                                    task_id=task.id,
                                    domain_id=third_party.id,
                                    violation_type=random.choice(list(ViolationType)),
                                    confidence_score=random.uniform(0.6, 0.9),
                                    risk_level=random.choice(list(RiskLevel)),
                                    title=f"违规内容检测",
                                    description=f"在域名 {third_party.domain} 上检测到可疑内容",
                                    content_snippet="检测到的违规内容片段...",
                                    ai_analysis_result={
                                        "model": "gpt-4-vision-preview",
                                        "confidence": random.uniform(0.6, 0.9),
                                        "analysis": "AI分析结果详情"
                                    },
                                    ai_model_used="gpt-4-vision-preview",
                                    evidence=["截图证据", "文本证据"],
                                    recommendations=["建议立即处理", "加强监控"],
                                    detected_at=started_time + timedelta(minutes=45) if started_time else None
                                )
                                db.add(violation)
            
            await db.commit()
            print(f"成功创建 {tasks_created} 个测试任务")
            
            # 创建一些子域名记录
            tasks = (await db.execute(select(ScanTask).where(ScanTask.user_id == user.id).limit(5))).scalars().all()
            for task in tasks:
                for i in range(random.randint(3, 8)):
                    subdomain = SubdomainRecord(
                        id=str(uuid.uuid4()),
                        task_id=task.id,
                        subdomain=f"sub{i+1}.{task.target_domain}",
                        ip_address=f"192.168.1.{random.randint(1, 254)}",
                        discovery_method="dns_enumeration",
                        is_accessible=random.choice([True, False]),
                        response_code=random.choice([200, 404, 500]) if random.random() < 0.8 else None,
                        response_time=random.uniform(0.1, 2.0),
                        server_header="nginx/1.18",
                        content_type="text/html",
                        page_title=f"子域名页面 {i+1}",
                        created_at=task.created_at
                    )
                    db.add(subdomain)
            
            await db.commit()
            print("测试数据创建完成！")
            
        except Exception as e:
            print(f"创建测试数据时出错: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    print("开始创建测试数据...")
    asyncio.run(create_test_data())
    print("测试数据创建完毕！")