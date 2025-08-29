"""
WebSocket实时推送管理器
用于向前端推送任务状态、域名发现等实时更新
"""

import json
import asyncio
from typing import Dict, Set, Optional, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.database import AsyncSessionLocal


class WebSocketManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        # 存储活跃连接：{task_id: {user_id: set(websockets)}}
        self.active_connections: Dict[str, Dict[str, Set[WebSocket]]] = {}
        # 存储用户连接：{user_id: {task_id: set(websockets)}}
        self.user_connections: Dict[str, Dict[str, Set[WebSocket]]] = {}
        
    async def connect(self, websocket: WebSocket, task_id: str, user_id: str):
        """建立WebSocket连接"""
        await websocket.accept()
        
        # 初始化数据结构
        if task_id not in self.active_connections:
            self.active_connections[task_id] = {}
        if user_id not in self.active_connections[task_id]:
            self.active_connections[task_id][user_id] = set()
        
        if user_id not in self.user_connections:
            self.user_connections[user_id] = {}
        if task_id not in self.user_connections[user_id]:
            self.user_connections[user_id][task_id] = set()
        
        # 添加连接
        self.active_connections[task_id][user_id].add(websocket)
        self.user_connections[user_id][task_id].add(websocket)
        
        logger.info(f"WebSocket连接已建立: task_id={task_id}, user_id={user_id}")
        
        # 发送连接成功消息
        await self.send_personal_message({
            "type": "connection_established",
            "task_id": task_id,
            "message": "实时连接已建立",
            "timestamp": datetime.utcnow().isoformat()
        }, websocket)
    
    def disconnect(self, websocket: WebSocket, task_id: str, user_id: str):
        """断开WebSocket连接"""
        try:
            # 从active_connections中移除
            if (task_id in self.active_connections and 
                user_id in self.active_connections[task_id]):
                self.active_connections[task_id][user_id].discard(websocket)
                
                # 如果该用户没有其他连接，删除用户记录
                if not self.active_connections[task_id][user_id]:
                    del self.active_connections[task_id][user_id]
                
                # 如果该任务没有其他连接，删除任务记录
                if not self.active_connections[task_id]:
                    del self.active_connections[task_id]
            
            # 从user_connections中移除
            if (user_id in self.user_connections and 
                task_id in self.user_connections[user_id]):
                self.user_connections[user_id][task_id].discard(websocket)
                
                # 如果该任务没有其他连接，删除任务记录
                if not self.user_connections[user_id][task_id]:
                    del self.user_connections[user_id][task_id]
                
                # 如果该用户没有其他连接，删除用户记录
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            
            logger.info(f"WebSocket连接已断开: task_id={task_id}, user_id={user_id}")
            
        except Exception as e:
            logger.error(f"断开WebSocket连接时出错: {e}")
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """发送个人消息"""
        try:
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"发送个人消息失败: {e}")
    
    async def send_task_update(self, task_id: str, message: Dict[str, Any]):
        """向指定任务的所有连接发送更新"""
        if task_id not in self.active_connections:
            return
        
        # 添加时间戳
        message["timestamp"] = datetime.utcnow().isoformat()
        
        dead_connections = []
        
        for user_id, websockets in self.active_connections[task_id].items():
            for websocket in websockets.copy():
                try:
                    await websocket.send_text(json.dumps(message, ensure_ascii=False))
                except Exception as e:
                    logger.warning(f"发送任务更新失败: {e}")
                    dead_connections.append((task_id, user_id, websocket))
        
        # 清理失效连接
        for task_id, user_id, websocket in dead_connections:
            self.disconnect(websocket, task_id, user_id)
    
    async def send_user_update(self, user_id: str, message: Dict[str, Any]):
        """向指定用户的所有连接发送更新"""
        if user_id not in self.user_connections:
            return
        
        # 添加时间戳
        message["timestamp"] = datetime.utcnow().isoformat()
        
        dead_connections = []
        
        for task_id, websockets in self.user_connections[user_id].items():
            for websocket in websockets.copy():
                try:
                    await websocket.send_text(json.dumps(message, ensure_ascii=False))
                except Exception as e:
                    logger.warning(f"发送用户更新失败: {e}")
                    dead_connections.append((task_id, user_id, websocket))
        
        # 清理失效连接
        for task_id, user_id, websocket in dead_connections:
            self.disconnect(websocket, task_id, user_id)
    
    def get_connection_count(self, task_id: Optional[str] = None) -> int:
        """获取连接数量"""
        if task_id:
            if task_id in self.active_connections:
                return sum(len(websockets) for websockets in self.active_connections[task_id].values())
            return 0
        else:
            total = 0
            for task_connections in self.active_connections.values():
                total += sum(len(websockets) for websockets in task_connections.values())
            return total


# 全局WebSocket管理器实例
websocket_manager = WebSocketManager()


class TaskProgressNotifier:
    """任务进度通知器"""
    
    def __init__(self, manager: WebSocketManager):
        self.manager = manager
    
    async def notify_task_started(self, task_id: str, target_domain: str):
        """通知任务开始"""
        message = {
            "type": "task_started",
            "task_id": task_id,
            "target_domain": target_domain,
            "message": f"任务已开始执行: {target_domain}"
        }
        await self.manager.send_task_update(task_id, message)
    
    async def notify_task_progress(self, task_id: str, progress: int, status: str, message: str):
        """通知任务进度更新"""
        update_message = {
            "type": "task_progress",
            "task_id": task_id,
            "progress": progress,
            "status": status,
            "message": message
        }
        await self.manager.send_task_update(task_id, update_message)
    
    async def notify_task_completed(self, task_id: str, stats: Dict[str, Any]):
        """通知任务完成"""
        message = {
            "type": "task_completed",
            "task_id": task_id,
            "stats": stats,
            "message": "任务执行完成"
        }
        await self.manager.send_task_update(task_id, message)
    
    async def notify_task_failed(self, task_id: str, error: str):
        """通知任务失败"""
        message = {
            "type": "task_failed",
            "task_id": task_id,
            "error": error,
            "message": f"任务执行失败: {error}"
        }
        await self.manager.send_task_update(task_id, message)
    
    async def notify_domain_discovered(self, task_id: str, domains: list, discovery_round: int):
        """通知发现新域名"""
        message = {
            "type": "domains_discovered",
            "task_id": task_id,
            "domains": domains,
            "discovery_round": discovery_round,
            "count": len(domains),
            "message": f"第{discovery_round}轮发现了{len(domains)}个新域名"
        }
        await self.manager.send_task_update(task_id, message)
    
    async def notify_domain_analyzed(self, task_id: str, domain: str, analysis_result: Dict[str, Any]):
        """通知域名分析完成"""
        message = {
            "type": "domain_analyzed",
            "task_id": task_id,
            "domain": domain,
            "analysis_result": analysis_result,
            "message": f"域名分析完成: {domain}"
        }
        await self.manager.send_task_update(task_id, message)
    
    async def notify_violation_detected(self, task_id: str, domain: str, violation: Dict[str, Any]):
        """通知检测到违规内容"""
        message = {
            "type": "violation_detected",
            "task_id": task_id,
            "domain": domain,
            "violation": violation,
            "message": f"检测到违规内容: {domain} - {violation.get('title', '未知违规')}"
        }
        await self.manager.send_task_update(task_id, message)
    
    async def notify_continuous_discovery_round(self, task_id: str, round_info: Dict[str, Any]):
        """通知循环发现轮次完成"""
        message = {
            "type": "discovery_round_complete",
            "task_id": task_id,
            "round_info": round_info,
            "message": f"第{round_info['round_number']}轮发现完成，新发现{round_info['new_domains_found']}个域名"
        }
        await self.manager.send_task_update(task_id, message)


# 全局任务进度通知器实例
task_notifier = TaskProgressNotifier(websocket_manager)


async def notify_domain_stats_update(task_id: str):
    """通知域名统计数据更新"""
    try:
        async with AsyncSessionLocal() as db:
            from app.models.domain import DomainRecord, DomainCategory
            
            # 查询最新统计数据
            from sqlalchemy import select, func
            query = select(DomainRecord).where(DomainRecord.task_id == task_id)
            result = await db.execute(query)
            domains = result.scalars().all()
            
            # 计算统计信息 - 使用数据库查询避免类型错误
            from sqlalchemy import and_
            
            # 查询各种类型的域名数量
            accessible_query = select(func.count()).where(
                and_(
                    DomainRecord.task_id == task_id,
                    DomainRecord.is_accessible == True
                )
            )
            accessible_result = await db.execute(accessible_query)
            accessible_count = accessible_result.scalar() or 0
            
            target_related_query = select(func.count()).where(
                and_(
                    DomainRecord.task_id == task_id,
                    DomainRecord.category.in_([DomainCategory.TARGET_MAIN, DomainCategory.TARGET_SUBDOMAIN])
                )
            )
            target_related_result = await db.execute(target_related_query)
            target_related = target_related_result.scalar() or 0
            
            third_party_query = select(func.count()).where(
                and_(
                    DomainRecord.task_id == task_id,
                    DomainRecord.category == DomainCategory.THIRD_PARTY
                )
            )
            third_party_result = await db.execute(third_party_query)
            third_party = third_party_result.scalar() or 0
            
            stats = {
                "total_domains": len(domains),
                "accessible_count": accessible_count,
                "violation_count": 0,  # TODO: 计算违规数量
                "target_related": target_related,
                "third_party": third_party,
            }
            
            message = {
                "type": "domain_stats_update",
                "task_id": task_id,
                "stats": stats
            }
            
            await websocket_manager.send_task_update(task_id, message)
            
    except Exception as e:
        logger.error(f"发送域名统计更新失败: {e}")