import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.logging import logger
from app.core.database import get_db
from app.models.task import ScanTask, TaskLog, TaskStatus
from app.websocket.manager import websocket_manager
from app.core.prometheus import update_concurrent_tasks


class TaskMonitorHandler:
    """任务监控处理器"""
    
    def __init__(self):
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.is_running = False
    
    async def start(self):
        """启动任务监控"""
        if not self.is_running:
            self.is_running = True
            # 启动任务状态监控循环
            asyncio.create_task(self._monitor_tasks_loop())
            logger.info("任务监控处理器已启动")
    
    async def stop(self):
        """停止任务监控"""
        self.is_running = False
        
        # 取消所有监控任务
        for task in self.monitoring_tasks.values():
            task.cancel()
        
        # 等待所有任务完成
        if self.monitoring_tasks:
            await asyncio.gather(*self.monitoring_tasks.values(), return_exceptions=True)
        
        self.monitoring_tasks.clear()
        logger.info("任务监控处理器已停止")
    
    async def notify_task_created(self, task_id: str, user_id: str, target_domain: str):
        """通知任务创建"""
        message = {
            "type": "task_created",
            "task_id": task_id,
            "target_domain": target_domain,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"扫描任务已创建: {target_domain}"
        }
        
        await websocket_manager.broadcast_to_user(user_id, message)
        logger.info(f"任务创建通知已发送: {task_id}")
    
    async def notify_task_started(self, task_id: str, user_id: str):
        """通知任务开始"""
        message = {
            "type": "task_started",
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "扫描任务开始执行"
        }
        
        await websocket_manager.broadcast_to_user(user_id, message)
        await websocket_manager.broadcast_to_task_subscribers(task_id, message)
        logger.info(f"任务开始通知已发送: {task_id}")
    
    async def notify_task_progress(self, task_id: str, progress: int, stage: str, message: str = ""):
        """通知任务进度更新"""
        notification = {
            "type": "task_progress",
            "task_id": task_id,
            "progress": progress,
            "stage": stage,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await websocket_manager.broadcast_to_task_subscribers(task_id, notification)
        logger.debug(f"任务进度通知: {task_id} - {progress}% - {stage}")
    
    async def notify_task_completed(self, task_id: str, user_id: str, status: str, statistics: Dict[str, Any] = None):  # type: ignore
        """通知任务完成"""
        message = {
            "type": "task_completed",
            "task_id": task_id,
            "status": status,
            "statistics": statistics or {},
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"扫描任务已{self._get_status_text(status)}"
        }
        
        await websocket_manager.broadcast_to_user(user_id, message)
        await websocket_manager.broadcast_to_task_subscribers(task_id, message)
        logger.info(f"任务完成通知已发送: {task_id} - {status}")
    
    async def notify_task_error(self, task_id: str, user_id: str, error_message: str):
        """通知任务错误"""
        message = {
            "type": "task_error",
            "task_id": task_id,
            "error": error_message,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"任务执行出错: {error_message}"
        }
        
        await websocket_manager.broadcast_to_user(user_id, message)
        await websocket_manager.broadcast_to_task_subscribers(task_id, message)
        logger.error(f"任务错误通知已发送: {task_id} - {error_message}")
    
    async def notify_violation_detected(self, task_id: str, violation_data: Dict[str, Any]):
        """通知检测到违规"""
        # 验证违规数据的有效性
        if not violation_data or not violation_data.get('domain'):
            logger.warning(f"违规通知数据无效，跳过发送: {violation_data}")
            return
        
        # 确保必要的字段存在
        domain = violation_data.get('domain', 'unknown')
        violation_type = violation_data.get('violation_type', '未知违规')
        risk_level = violation_data.get('risk_level', 'low')
        confidence_score = violation_data.get('confidence_score', 0)
        description = violation_data.get('description', '检测到潜在违规内容')
        
        # 只有在置信度足够高时才发送通知 (至少50%)
        if confidence_score < 0.5:
            logger.info(f"违规检测置信度过低 ({confidence_score*100:.1f}%)，跳过通知: {domain}")
            return
        
        message = {
            "type": "violation_detected",
            "task_id": task_id,
            "violation": {
                "domain": domain,
                "violation_type": violation_type,
                "risk_level": risk_level,
                "confidence_score": confidence_score * 100,  # 转换为百分比
                "description": description
            },
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"在域名 {domain} 检测到{risk_level}风险{violation_type}（置信度: {confidence_score*100:.1f}%）"
        }
        
        # 获取任务所属用户，发送给用户和任务订阅者
        try:
            async for db in get_db():
                stmt = select(ScanTask).where(ScanTask.id == task_id)
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()
                
                if task:
                    # 发送给任务所属用户
                    await websocket_manager.broadcast_to_user(str(task.user_id), message)
                    
                # 发送给任务订阅者
                await websocket_manager.broadcast_to_task_subscribers(task_id, message)
                
                logger.info(f"违规检测通知已发送: {task_id} - {domain} ({violation_type}, {risk_level}风险, {confidence_score*100:.1f}%置信度)")
                
        except Exception as e:
            logger.error(f"发送违规检测通知失败: {e}")
            # 即使获取用户失败，也尝试发送给任务订阅者
            await websocket_manager.broadcast_to_task_subscribers(task_id, message)
    
    async def notify_task_event(self, task_id: str, user_id: str, event_data: Dict[str, Any]):
        """通知任务事件（用于并行执行器）"""
        # 验证事件数据
        if not event_data:
            logger.warning(f"任务事件数据为空，跳过发送: {task_id}")
            return
        
        # 构建通知消息
        message = {
            "type": "task_event",
            "task_id": task_id,
            "event": event_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # 根据事件类型添加描述性消息
        event_type = event_data.get('event_type', '')
        stage = event_data.get('stage', '')
        data = event_data.get('data', {})
        
        if event_type == 'scan_started':
            message["message"] = f"开始扫描: {data.get('target_domain', '未知域名')}"
        elif event_type == 'stage_started':
            stage_name = data.get('stage', stage)
            message["message"] = f"开始{stage_name}阶段"
        elif event_type == 'subdomains_discovered':
            count = data.get('count', 0)
            message["message"] = f"发现 {count} 个子域名"
        elif event_type == 'subdomain_crawled':
            subdomain = data.get('subdomain', '')
            pages = data.get('pages', 0)
            message["message"] = f"已爬取 {subdomain}，获得 {pages} 个页面"
        elif event_type == 'domain_analyzed':
            domain = data.get('domain', '')
            violations = data.get('violations_found', 0)
            message["message"] = f"已分析 {domain}，发现 {violations} 个潜在违规"
        elif event_type == 'scan_completed':
            duration = data.get('duration', 0)
            message["message"] = f"扫描完成，耗时 {duration:.1f} 秒"
        elif event_type == 'scan_failed':
            error = data.get('error', '未知错误')
            message["message"] = f"扫描失败: {error}"
        else:
            message["message"] = f"{stage}阶段事件: {event_type}"
        
        # 发送给用户和任务订阅者
        await websocket_manager.broadcast_to_user(user_id, message)
        await websocket_manager.broadcast_to_task_subscribers(task_id, message)
        
        logger.debug(f"任务事件通知已发送: {task_id} - {event_type}")
    
    async def send_task_logs(self, task_id: str, logs: List[Dict[str, Any]]):
        """发送任务日志"""
        message = {
            "type": "task_logs",
            "task_id": task_id,
            "logs": logs,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await websocket_manager.broadcast_to_task_subscribers(task_id, message)
        logger.debug(f"任务日志已发送: {task_id} - {len(logs)} 条记录")
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        try:
            async for db in get_db():
                stmt = select(ScanTask).where(ScanTask.id == task_id)
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()
                
                if not task:
                    return None
                
                return {
                    "task_id": task_id,
                    "status": task.status,
                    "progress": task.progress,
                    "target_domain": task.target_domain,
                    "created_at": task.created_at.isoformat() if task.created_at else None, # type: ignore
                    "started_at": task.started_at.isoformat() if task.started_at else None, # type: ignore
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,   # type: ignore
                    "statistics": {
                        "total_subdomains": task.total_subdomains,
                        "total_pages_crawled": task.total_pages_crawled,
                        "total_third_party_domains": task.total_third_party_domains,
                        "total_violations": task.total_violations,
                        "critical_violations": task.critical_violations,
                        "high_violations": task.high_violations,
                        "medium_violations": task.medium_violations,
                        "low_violations": task.low_violations
                    },
                    "error_message": task.error_message
                }
        except Exception as e:
            logger.error(f"获取任务状态失败: {e}")
            return None
    
    async def get_task_logs(self, task_id: str, limit: int = 50) -> List[Dict[str, Any]]:   # type: ignore
        """获取任务日志"""
        try:
            async for db in get_db():
                stmt = select(TaskLog).where(
                    TaskLog.task_id == task_id
                ).order_by(TaskLog.created_at.desc()).limit(limit)
                
                result = await db.execute(stmt)
                logs = result.scalars().all()
                
                return [
                    {
                        "id": log.id,
                        "level": log.level,
                        "module": log.module,
                        "message": log.message,
                        "extra_data": log.extra_data,
                        "created_at": log.created_at.isoformat()
                    }
                    for log in logs
                ]
        except Exception as e:
            logger.error(f"获取任务日志失败: {e}")
            return []
    
    async def _monitor_tasks_loop(self):
        """任务监控循环"""
        while self.is_running:
            try:
                await self._check_running_tasks()
                await asyncio.sleep(10)  # 每10秒检查一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"任务监控循环异常: {e}")
                await asyncio.sleep(10)
    
    async def _check_running_tasks(self):
        """检查运行中的任务"""
        try:
            async for db in get_db():
                # 查询运行中的任务
                stmt = select(ScanTask).where(ScanTask.status == TaskStatus.RUNNING)
                result = await db.execute(stmt)
                running_tasks = result.scalars().all()
                
                # 更新并发任务数监控指标
                update_concurrent_tasks(len(running_tasks))
                
                # 检查长时间运行的任务
                current_time = datetime.utcnow()
                for task in running_tasks:
                    if task.started_at: # type: ignore
                        duration = (current_time - task.started_at).total_seconds()
                        
                        # 如果任务运行超过6小时，发送警告
                        if duration > 6 * 3600:  # 6小时
                            await self._notify_long_running_task(task, duration)
                        
                        # 如果任务运行超过12小时，标记为超时
                        elif duration > 12 * 3600:  # 12小时
                            await self._handle_timeout_task(task, db)
                
        except Exception as e:
            logger.error(f"检查运行中任务失败: {e}")
    
    async def _notify_long_running_task(self, task: ScanTask, duration: float):
        """通知长时间运行的任务"""
        hours = int(duration // 3600)
        message = {
            "type": "task_warning",
            "task_id": task.id,
            "message": f"任务已运行 {hours} 小时，请检查是否存在问题",
            "duration_hours": hours,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await websocket_manager.broadcast_to_user(task.user_id, message)    # type: ignore
        await websocket_manager.broadcast_to_task_subscribers(task.id, message) # type: ignore
    
    async def _handle_timeout_task(self, task: ScanTask, db: AsyncSession):
        """处理超时任务"""
        try:
            task.status = TaskStatus.FAILED  # type: ignore
            task.error_message = "任务执行超时（超过12小时）"  # type: ignore
            task.completed_at = datetime.utcnow()  # type: ignore
            
            await db.commit()
            
            # 发送超时通知
            await self.notify_task_completed(
                task.id,  # type: ignore
                task.user_id,  # type: ignore
                TaskStatus.FAILED,
                {"error": "任务执行超时"}
            )
            
            logger.warning(f"任务 {task.id} 因超时被标记为失败")  # type: ignore
            
        except Exception as e:
            logger.error(f"处理超时任务失败: {e}")
    
    def _get_status_text(self, status: str) -> str:
        """获取状态文本"""
        status_map = {
            TaskStatus.COMPLETED: "完成",
            TaskStatus.FAILED: "失败",
            TaskStatus.CANCELLED: "取消"
        }
        return status_map.get(status, status)   # type: ignore


# 全局任务监控处理器实例
task_monitor = TaskMonitorHandler()