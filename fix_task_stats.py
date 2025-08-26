import asyncio
from app.core.database import AsyncSessionLocal
from app.models.task import ScanTask, SubdomainRecord, ThirdPartyDomain, ViolationRecord
from sqlalchemy import select, func

async def fix_task_statistics():
    """修复任务统计数据"""
    try:
        async with AsyncSessionLocal() as db:
            # 获取指定任务
            task_id = '7ba9a117-90e7-459e-8285-be15047ab548'
            stmt = select(ScanTask).where(ScanTask.id == task_id)
            result = await db.execute(stmt)
            task = result.scalar_one_or_none()
            
            if not task:
                print(f'Task {task_id} not found')
                return
            
            print(f'Current task statistics:')
            print(f'  Total subdomains: {task.total_subdomains}')
            print(f'  Total third party domains: {task.total_third_party_domains}')
            print(f'  Total violations: {task.total_violations}')
            
            # 计算实际的统计数据
            # 子域名数量
            subdomain_count_stmt = select(func.count(SubdomainRecord.id)).where(
                SubdomainRecord.task_id == task_id
            )
            subdomain_result = await db.execute(subdomain_count_stmt)
            actual_subdomains = subdomain_result.scalar() or 0
            
            # 第三方域名数量
            third_party_count_stmt = select(func.count(ThirdPartyDomain.id)).where(
                ThirdPartyDomain.task_id == task_id
            )
            third_party_result = await db.execute(third_party_count_stmt)
            actual_third_party = third_party_result.scalar() or 0
            
            # 违规记录数量
            violation_count_stmt = select(func.count(ViolationRecord.id)).where(
                ViolationRecord.task_id == task_id
            )
            violation_result = await db.execute(violation_count_stmt)
            actual_violations = violation_result.scalar() or 0
            
            print(f'Actual statistics:')
            print(f'  Subdomains: {actual_subdomains}')
            print(f'  Third party domains: {actual_third_party}')
            print(f'  Violations: {actual_violations}')
            
            # 更新任务统计数据
            task.total_subdomains = actual_subdomains
            task.total_third_party_domains = actual_third_party
            task.total_violations = actual_violations
            
            # 更新风险等级统计
            if actual_violations > 0:
                # 查询各风险等级的违规数量
                critical_stmt = select(func.count(ViolationRecord.id)).where(
                    ViolationRecord.task_id == task_id,
                    ViolationRecord.risk_level == 'critical'
                )
                critical_result = await db.execute(critical_stmt)
                task.critical_violations = critical_result.scalar() or 0
                
                high_stmt = select(func.count(ViolationRecord.id)).where(
                    ViolationRecord.task_id == task_id,
                    ViolationRecord.risk_level == 'high'
                )
                high_result = await db.execute(high_stmt)
                task.high_violations = high_result.scalar() or 0
                
                medium_stmt = select(func.count(ViolationRecord.id)).where(
                    ViolationRecord.task_id == task_id,
                    ViolationRecord.risk_level == 'medium'
                )
                medium_result = await db.execute(medium_stmt)
                task.medium_violations = medium_result.scalar() or 0
                
                low_stmt = select(func.count(ViolationRecord.id)).where(
                    ViolationRecord.task_id == task_id,
                    ViolationRecord.risk_level == 'low'
                )
                low_result = await db.execute(low_stmt)
                task.low_violations = low_result.scalar() or 0
            
            await db.commit()
            print('Task statistics updated successfully')
            
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_task_statistics())