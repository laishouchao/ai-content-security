import asyncio
from app.core.database import AsyncSessionLocal
from app.models.task import TaskLog
from sqlalchemy import select

async def check_task_logs():
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(TaskLog).where(
                TaskLog.task_id == '7ba9a117-90e7-459e-8285-be15047ab548'
            ).order_by(TaskLog.created_at.desc())
            
            result = await db.execute(stmt)
            logs = result.scalars().all()
            
            print(f'Found {len(logs)} log entries for task:')
            for log in logs[:20]:  # 显示最近20条日志
                print(f'{log.created_at} [{log.level}] {log.module}: {log.message}')
                if log.extra_data:
                    print(f'  Extra data: {log.extra_data}')
                print()
                
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    asyncio.run(check_task_logs())