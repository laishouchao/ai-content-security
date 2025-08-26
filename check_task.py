import asyncio
from app.core.database import AsyncSessionLocal
from app.models.task import ScanTask
from sqlalchemy import select

async def check_task_status():
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(ScanTask).where(ScanTask.id == '7ba9a117-90e7-459e-8285-be15047ab548')
            result = await db.execute(stmt)
            task = result.scalar_one_or_none()
            
            if task:
                print(f'Task ID: {task.id}')
                print(f'Status: {task.status}')
                print(f'Progress: {task.progress}%')
                print(f'Total subdomains: {task.total_subdomains}')
                print(f'Total third party domains: {task.total_third_party_domains}')
                print(f'Error message: {task.error_message}')
                print(f'Started at: {task.started_at}')
                print(f'Completed at: {task.completed_at}')
            else:
                print('Task not found')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    asyncio.run(check_task_status())