import asyncio
from app.core.database import AsyncSessionLocal
from app.models.task import ScanTask, SubdomainRecord, ThirdPartyDomain, ViolationRecord
from sqlalchemy import select, func

async def fix_all_task_statistics():
    """修复所有任务的统计数据"""
    try:
        async with AsyncSessionLocal() as db:
            # 获取所有任务
            stmt = select(ScanTask)
            result = await db.execute(stmt)
            tasks = result.scalars().all()
            
            print(f'Found {len(tasks)} tasks to process')
            
            for task in tasks:
                print(f'\nProcessing task {task.id} ({task.target_domain})')
                print(f'  Current status: {task.status}')
                print(f'  Current statistics: subdomains={task.total_subdomains}, third_party={task.total_third_party_domains}, violations={task.total_violations}')
                
                # 计算实际的统计数据
                # 子域名数量
                subdomain_count_stmt = select(func.count(SubdomainRecord.id)).where(
                    SubdomainRecord.task_id == task.id
                )
                subdomain_result = await db.execute(subdomain_count_stmt)
                actual_subdomains = subdomain_result.scalar() or 0
                
                # 第三方域名数量
                third_party_count_stmt = select(func.count(ThirdPartyDomain.id)).where(
                    ThirdPartyDomain.task_id == task.id
                )
                third_party_result = await db.execute(third_party_count_stmt)
                actual_third_party = third_party_result.scalar() or 0
                
                # 违规记录数量
                violation_count_stmt = select(func.count(ViolationRecord.id)).where(
                    ViolationRecord.task_id == task.id
                )
                violation_result = await db.execute(violation_count_stmt)
                actual_violations = violation_result.scalar() or 0
                
                print(f'  Actual statistics: subdomains={actual_subdomains}, third_party={actual_third_party}, violations={actual_violations}')
                
                # 检查是否需要更新
                needs_update = (
                    task.total_subdomains != actual_subdomains or
                    task.total_third_party_domains != actual_third_party or
                    task.total_violations != actual_violations
                )
                
                if needs_update:
                    print(f'  Updating statistics...')
                    # 更新任务统计数据
                    task.total_subdomains = actual_subdomains
                    task.total_third_party_domains = actual_third_party
                    task.total_violations = actual_violations
                    
                    # 更新风险等级统计
                    if actual_violations > 0:
                        # 查询各风险等级的违规数量
                        critical_stmt = select(func.count(ViolationRecord.id)).where(
                            ViolationRecord.task_id == task.id,
                            ViolationRecord.risk_level == 'critical'
                        )
                        critical_result = await db.execute(critical_stmt)
                        task.critical_violations = critical_result.scalar() or 0
                        
                        high_stmt = select(func.count(ViolationRecord.id)).where(
                            ViolationRecord.task_id == task.id,
                            ViolationRecord.risk_level == 'high'
                        )
                        high_result = await db.execute(high_stmt)
                        task.high_violations = high_result.scalar() or 0
                        
                        medium_stmt = select(func.count(ViolationRecord.id)).where(
                            ViolationRecord.task_id == task.id,
                            ViolationRecord.risk_level == 'medium'
                        )
                        medium_result = await db.execute(medium_stmt)
                        task.medium_violations = medium_result.scalar() or 0
                        
                        low_stmt = select(func.count(ViolationRecord.id)).where(
                            ViolationRecord.task_id == task.id,
                            ViolationRecord.risk_level == 'low'
                        )
                        low_result = await db.execute(low_stmt)
                        task.low_violations = low_result.scalar() or 0
                    else:
                        # 重置风险等级统计
                        task.critical_violations = 0
                        task.high_violations = 0
                        task.medium_violations = 0
                        task.low_violations = 0
                    
                    print(f'  Statistics updated successfully')
                else:
                    print(f'  No update needed')
            
            # 提交所有更改
            await db.commit()
            print(f'\nAll task statistics processed successfully')
            
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_all_task_statistics())