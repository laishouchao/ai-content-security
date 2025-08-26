import asyncio
from app.core.database import AsyncSessionLocal
from app.models.task import TaskLog, ScanTask
from sqlalchemy import select, or_, and_

async def check_detailed_logs():
    try:
        async with AsyncSessionLocal() as db:
            task_id = '7ba9a117-90e7-459e-8285-be15047ab548'
            
            # 检查任务状态
            task_stmt = select(ScanTask).where(ScanTask.id == task_id)
            task_result = await db.execute(task_stmt)
            task = task_result.scalar_one_or_none()
            
            if task:
                print(f"Task Status: {task.status}")
                print(f"Progress: {task.progress}%")
                print(f"Error Message: {task.error_message}")
                print(f"Error Code: {task.error_code}")
                print()
            
            # 检查所有相关的日志，包括错误和警告
            stmt = select(TaskLog).where(
                and_(
                    TaskLog.task_id == task_id,
                    or_(
                        TaskLog.level.in_(['ERROR', 'WARNING', 'INFO']),
                        TaskLog.message.like('%第三方域名%'),
                        TaskLog.message.like('%保存%'),
                        TaskLog.message.like('%失败%'),
                        TaskLog.message.like('%异常%')
                    )
                )
            ).order_by(TaskLog.created_at.desc()).limit(50)
            
            result = await db.execute(stmt)
            logs = result.scalars().all()
            
            print(f'Found {len(logs)} relevant log entries:')
            for log in logs:
                print(f'{log.created_at} [{log.level}] {log.module}: {log.message}')
                if log.extra_data:
                    print(f'  Extra: {log.extra_data}')
                print()
                
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_detailed_logs())