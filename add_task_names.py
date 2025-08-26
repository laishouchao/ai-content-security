import asyncio
from app.core.database import AsyncSessionLocal
from app.models.task import ScanTask
from sqlalchemy import select, update

async def add_task_names():
    """为现有任务添加任务名称"""
    try:
        async with AsyncSessionLocal() as db:
            # 获取所有任务
            stmt = select(ScanTask)
            result = await db.execute(stmt)
            tasks = result.scalars().all()
            
            print(f'Found {len(tasks)} tasks')
            
            # 为没有任务名称的任务添加默认名称
            updated_count = 0
            for task in tasks:
                if not task.task_name:
                    # 基于目标域名和创建时间生成任务名称
                    domain = task.target_domain
                    created_date = task.created_at.strftime("%Y-%m-%d") if task.created_at else ""
                    task_name = f"{domain} 扫描任务 {created_date}".strip()
                    
                    # 更新任务名称
                    update_stmt = update(ScanTask).where(ScanTask.id == task.id).values(
                        task_name=task_name
                    )
                    await db.execute(update_stmt)
                    updated_count += 1
                    print(f"Updated task {task.id[:8]}... with name: {task_name}")
            
            await db.commit()
            print(f"Successfully updated {updated_count} tasks with task names")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(add_task_names())