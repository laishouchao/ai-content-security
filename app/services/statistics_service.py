from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, extract, text
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict

from app.models.task import (
    ScanTask, TaskStatus, ViolationRecord, ViolationType, RiskLevel
)
from app.models.domain import DomainRecord
from app.models.user import User
from app.core.logging import logger


class StatisticsService:
    """统计数据服务类"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_dashboard_stats(self, user_id: str) -> Dict[str, Any]:
        """获取仪表板统计数据"""
        try:
            # 基础统计
            basic_stats = await self._get_basic_task_stats(user_id)
            
            # 任务趋势数据（最近30天）
            task_trends = await self._get_task_trends(user_id, days=30)
            
            # 违规类型分布
            violation_distribution = await self._get_violation_distribution(user_id)
            
            # 风险级别分布
            risk_level_distribution = await self._get_risk_level_distribution(user_id)
            
            # 最近任务
            recent_tasks = await self._get_recent_tasks(user_id, limit=5)
            
            # 系统状态
            system_status = await self._get_system_status(user_id)
            
            return {
                **basic_stats,
                "task_trends": task_trends,
                "violation_distribution": violation_distribution,
                "risk_level_distribution": risk_level_distribution,
                "recent_tasks": recent_tasks,
                "system_status": system_status
            }
            
        except Exception as e:
            logger.error(f"获取仪表板统计数据失败: {e}")
            raise e
    
    async def _get_basic_task_stats(self, user_id: str) -> Dict[str, Any]:
        """获取基础任务统计"""
        # 总任务数
        total_tasks_query = select(func.count(ScanTask.id)).where(
            ScanTask.user_id == user_id
        )
        total_result = await self.db.execute(total_tasks_query)
        total_tasks = total_result.scalar() or 0
        
        # 各状态任务统计
        status_counts_query = select(
            ScanTask.status,
            func.count(ScanTask.id)
        ).where(
            ScanTask.user_id == user_id
        ).group_by(ScanTask.status)
        
        status_result = await self.db.execute(status_counts_query)
        status_counts = {status: count for status, count in status_result.all()}
        
        # 违规统计
        violation_stats_query = select(
            func.sum(ScanTask.total_violations),
            func.sum(ScanTask.critical_violations),
            func.sum(ScanTask.high_violations),
            func.sum(ScanTask.medium_violations),
            func.sum(ScanTask.low_violations)
        ).where(
            ScanTask.user_id == user_id
        )
        
        violation_result = await self.db.execute(violation_stats_query)
        violation_stats = violation_result.first()
        
        # 今日任务统计
        today = datetime.utcnow().date()
        today_tasks_query = select(func.count(ScanTask.id)).where(
            and_(
                ScanTask.user_id == user_id,
                func.date(ScanTask.created_at) == today
            )
        )
        today_result = await self.db.execute(today_tasks_query)
        today_tasks = today_result.scalar() or 0
        
        return {
            "total_tasks": total_tasks,
            "completed_tasks": status_counts.get(TaskStatus.COMPLETED, 0),
            "running_tasks": status_counts.get(TaskStatus.RUNNING, 0),
            "failed_tasks": status_counts.get(TaskStatus.FAILED, 0),
            "pending_tasks": status_counts.get(TaskStatus.PENDING, 0),
            "cancelled_tasks": status_counts.get(TaskStatus.CANCELLED, 0),
            "total_violations": violation_stats[0] or 0 if violation_stats else 0,
            "critical_violations": violation_stats[1] or 0 if violation_stats else 0,
            "high_violations": violation_stats[2] or 0 if violation_stats else 0,
            "medium_violations": violation_stats[3] or 0 if violation_stats else 0,
            "low_violations": violation_stats[4] or 0 if violation_stats else 0,
            "today_tasks": today_tasks
        }
    
    async def _get_task_trends(self, user_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """获取任务趋势数据"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # 按天统计任务数量
        from sqlalchemy import case
        
        trends_query = select(
            func.date(ScanTask.created_at).label('date'),
            func.count(ScanTask.id).label('total'),
            func.sum(
                case(
                    (ScanTask.status == TaskStatus.COMPLETED, 1)
                )
            ).label('completed'),
            func.sum(
                case(
                    (ScanTask.status == TaskStatus.FAILED, 1)
                )
            ).label('failed'),
            func.coalesce(func.sum(ScanTask.total_violations), 0).label('violations')
        ).where(
            and_(
                ScanTask.user_id == user_id,
                ScanTask.created_at >= start_date,
                ScanTask.created_at <= end_date
            )
        ).group_by(
            func.date(ScanTask.created_at)
        ).order_by(
            func.date(ScanTask.created_at)
        )
        
        result = await self.db.execute(trends_query)
        trends_data = result.all()
        
        # 填充缺失的日期
        trend_dict = {row.date: row for row in trends_data}
        trends = []
        
        for i in range(days):
            date = (start_date + timedelta(days=i)).date()
            if date in trend_dict:
                row = trend_dict[date]
                trends.append({
                    "date": date.isoformat(),
                    "total": row.total,
                    "completed": row.completed,
                    "failed": row.failed,
                    "violations": row.violations or 0
                })
            else:
                trends.append({
                    "date": date.isoformat(),
                    "total": 0,
                    "completed": 0,
                    "failed": 0,
                    "violations": 0
                })
        
        return trends
    
    async def _get_violation_distribution(self, user_id: str) -> List[Dict[str, Any]]:
        """获取违规类型分布"""
        # 从违规记录表直接统计
        violation_query = select(
            ViolationRecord.violation_type,
            func.count(ViolationRecord.id).label('count')
        ).join(
            ScanTask, ViolationRecord.task_id == ScanTask.id
        ).where(
            ScanTask.user_id == user_id
        ).group_by(
            ViolationRecord.violation_type
        )
        
        result = await self.db.execute(violation_query)
        violations = result.all()
        
        distribution = []
        for violation_type, count in violations:
            distribution.append({
                "type": violation_type,
                "count": count,
                "name": self._get_violation_type_name(violation_type)
            })
        
        return distribution
    
    async def _get_risk_level_distribution(self, user_id: str) -> List[Dict[str, Any]]:
        """获取风险级别分布"""
        # 从违规记录表统计风险级别
        risk_query = select(
            ViolationRecord.risk_level,
            func.count(ViolationRecord.id).label('count')
        ).join(
            ScanTask, ViolationRecord.task_id == ScanTask.id
        ).where(
            ScanTask.user_id == user_id
        ).group_by(
            ViolationRecord.risk_level
        )
        
        result = await self.db.execute(risk_query)
        risks = result.all()
        
        distribution = []
        for risk_level, count in risks:
            distribution.append({
                "level": risk_level,
                "count": count,
                "name": self._get_risk_level_name(risk_level)
            })
        
        return distribution
    
    async def _get_recent_tasks(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """获取最近的任务"""
        query = select(ScanTask).where(
            ScanTask.user_id == user_id
        ).order_by(ScanTask.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        tasks = result.scalars().all()
        
        recent_tasks = []
        for task in tasks:
            recent_tasks.append({
                "id": task.id,
                "target_domain": task.target_domain,
                "status": task.status,
                "progress": task.progress,
                "created_at": task.created_at.isoformat() if task.created_at is not None else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at is not None else None,
                "total_violations": task.total_violations,
                "error_message": task.error_message
            })
        
        return recent_tasks
    
    async def _get_system_status(self, user_id: str) -> Dict[str, Any]:
        """获取系统状态信息"""
        # 正在运行的任务数
        running_query = select(func.count(ScanTask.id)).where(
            and_(
                ScanTask.user_id == user_id,
                ScanTask.status == TaskStatus.RUNNING
            )
        )
        running_result = await self.db.execute(running_query)
        running_tasks = running_result.scalar() or 0
        
        # 今日完成的任务数
        today = datetime.utcnow().date()
        today_completed_query = select(func.count(ScanTask.id)).where(
            and_(
                ScanTask.user_id == user_id,
                ScanTask.status == TaskStatus.COMPLETED,
                func.date(ScanTask.completed_at) == today
            )
        )
        today_completed_result = await self.db.execute(today_completed_query)
        today_completed = today_completed_result.scalar() or 0
        
        # 平均执行时间（最近10个完成的任务）
        avg_duration_query = select(
            func.avg(
                extract('epoch', ScanTask.completed_at) - extract('epoch', ScanTask.started_at)
            ).label('avg_duration')
        ).where(
            and_(
                ScanTask.user_id == user_id,
                ScanTask.status == TaskStatus.COMPLETED,
                ScanTask.started_at.is_not(None),
                ScanTask.completed_at.is_not(None)
            )
        ).limit(10)
        
        avg_result = await self.db.execute(avg_duration_query)
        avg_duration = avg_result.scalar() or 0
        
        return {
            "running_tasks": running_tasks,
            "today_completed": today_completed,
            "avg_execution_time": round(avg_duration, 2) if avg_duration else 0,
            "queue_status": "normal",  # 可以后续集成实际的队列状态
            "api_status": "healthy",
            "database_status": "connected"
        }
    
    def _get_violation_type_name(self, violation_type: str) -> str:
        """获取违规类型的中文名称"""
        type_names = {
            ViolationType.NSFW.value: "不当内容",
            ViolationType.VIOLENCE.value: "暴力内容", 
            ViolationType.GAMBLING.value: "赌博内容",
            ViolationType.FRAUD.value: "欺诈内容",
            ViolationType.MALWARE.value: "恶意软件",
            ViolationType.HATE_SPEECH.value: "仇恨言论",
            ViolationType.COPYRIGHT.value: "版权侵权",
            ViolationType.OTHER.value: "其他"
        }
        return type_names.get(violation_type, violation_type)
    
    def _get_risk_level_name(self, risk_level: str) -> str:
        """获取风险级别的中文名称"""
        level_names = {
            RiskLevel.LOW.value: "低风险",
            RiskLevel.MEDIUM.value: "中等风险",
            RiskLevel.HIGH.value: "高风险",
            RiskLevel.CRITICAL.value: "严重风险"
        }
        return level_names.get(risk_level, risk_level)


async def get_statistics_service(db: AsyncSession) -> StatisticsService:
    """获取统计服务实例"""
    return StatisticsService(db)