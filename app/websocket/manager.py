import asyncio
import json
import time
from typing import Dict, Set, List, Optional, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
import uuid
import weakref

from app.core.logging import logger
from app.core.prometheus import update_active_users


class ConnectionInfo:
    """连接信息"""
    
    def __init__(self, websocket: WebSocket, user_id: str, connection_id: str):
        self.websocket = websocket
        self.user_id = user_id
        self.connection_id = connection_id
        self.connected_at = datetime.utcnow()
        self.last_ping = time.time()
        self.subscriptions: Set[str] = set()  # 订阅的任务ID


class WebSocketManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        # 用户ID -> 连接信息列表
        self.user_connections: Dict[str, List[ConnectionInfo]] = {}
        # 连接ID -> 连接信息
        self.all_connections: Dict[str, ConnectionInfo] = {}
        # 任务ID -> 订阅用户ID集合
        self.task_subscribers: Dict[str, Set[str]] = {}
        # 心跳检查任务
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.is_running = False
    
    async def start(self):
        """启动WebSocket管理器"""
        if not self.is_running:
            self.is_running = True
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("WebSocket管理器已启动")
    
    async def stop(self):
        """停止WebSocket管理器"""
        self.is_running = False
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有连接
        for connection_info in list(self.all_connections.values()):
            await self._disconnect_internal(connection_info)
        
        logger.info("WebSocket管理器已停止")
    
    async def connect(self, websocket: WebSocket, user_id: str) -> str:
        """建立WebSocket连接"""
        await websocket.accept()
        
        connection_id = str(uuid.uuid4())
        connection_info = ConnectionInfo(websocket, user_id, connection_id)
        
        # 保存连接信息
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        
        self.user_connections[user_id].append(connection_info)
        self.all_connections[connection_id] = connection_info
        
        # 更新活跃用户数
        active_users_count = len(self.user_connections)
        update_active_users(active_users_count)
        
        logger.info(f"用户 {user_id} 建立WebSocket连接: {connection_id}")
        
        # 发送连接确认消息
        await self._send_to_connection(connection_info, {
            "type": "connection_established",
            "connection_id": connection_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "WebSocket连接建立成功"
        })
        
        return connection_id
    
    async def disconnect(self, connection_id: str):
        """断开WebSocket连接"""
        if connection_id in self.all_connections:
            connection_info = self.all_connections[connection_id]
            await self._disconnect_internal(connection_info)
    
    async def _disconnect_internal(self, connection_info: ConnectionInfo):
        """内部断开连接方法"""
        user_id = connection_info.user_id
        connection_id = connection_info.connection_id
        
        # 从订阅中移除
        for task_id in connection_info.subscriptions.copy():
            await self._unsubscribe_from_task(connection_info, task_id)
        
        # 移除连接信息
        if user_id in self.user_connections:
            self.user_connections[user_id] = [
                conn for conn in self.user_connections[user_id] 
                if conn.connection_id != connection_id
            ]
            
            # 如果用户没有其他连接，移除用户
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        if connection_id in self.all_connections:
            del self.all_connections[connection_id]
        
        # 更新活跃用户数
        active_users_count = len(self.user_connections)
        update_active_users(active_users_count)
        
        # 关闭WebSocket连接
        try:
            await connection_info.websocket.close()
        except Exception as e:
            logger.warning(f"关闭WebSocket连接失败: {e}")
        
        logger.info(f"用户 {user_id} 断开WebSocket连接: {connection_id}")
    
    async def subscribe_to_task(self, connection_id: str, task_id: str) -> bool:
        """订阅任务状态更新"""
        if connection_id not in self.all_connections:
            return False
        
        connection_info = self.all_connections[connection_id]
        connection_info.subscriptions.add(task_id)
        
        # 添加到任务订阅者
        if task_id not in self.task_subscribers:
            self.task_subscribers[task_id] = set()
        
        self.task_subscribers[task_id].add(connection_info.user_id)
        
        logger.debug(f"用户 {connection_info.user_id} 订阅任务 {task_id}")
        return True
    
    async def unsubscribe_from_task(self, connection_id: str, task_id: str) -> bool:
        """取消订阅任务状态更新"""
        if connection_id not in self.all_connections:
            return False
        
        connection_info = self.all_connections[connection_id]
        return await self._unsubscribe_from_task(connection_info, task_id)
    
    async def _unsubscribe_from_task(self, connection_info: ConnectionInfo, task_id: str) -> bool:
        """内部取消订阅方法"""
        connection_info.subscriptions.discard(task_id)
        
        if task_id in self.task_subscribers:
            self.task_subscribers[task_id].discard(connection_info.user_id)
            
            # 如果没有订阅者，移除任务
            if not self.task_subscribers[task_id]:
                del self.task_subscribers[task_id]
        
        logger.debug(f"用户 {connection_info.user_id} 取消订阅任务 {task_id}")
        return True
    
    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]) -> int:
        """向指定用户的所有连接广播消息"""
        if user_id not in self.user_connections:
            return 0
        
        sent_count = 0
        connections = self.user_connections[user_id].copy()
        
        for connection_info in connections:
            if await self._send_to_connection(connection_info, message):
                sent_count += 1
        
        return sent_count
    
    async def broadcast_to_task_subscribers(self, task_id: str, message: Dict[str, Any]) -> int:
        """向任务订阅者广播消息"""
        if task_id not in self.task_subscribers:
            return 0
        
        sent_count = 0
        subscribers = self.task_subscribers[task_id].copy()
        
        for user_id in subscribers:
            sent = await self.broadcast_to_user(user_id, message)
            sent_count += sent
        
        return sent_count
    
    async def broadcast_to_all(self, message: Dict[str, Any]) -> int:
        """向所有连接广播消息"""
        sent_count = 0
        
        for connections in self.user_connections.values():
            for connection_info in connections.copy():
                if await self._send_to_connection(connection_info, message):
                    sent_count += 1
        
        return sent_count
    
    async def _send_to_connection(self, connection_info: ConnectionInfo, message: Dict[str, Any]) -> bool:
        """向指定连接发送消息"""
        try:
            message_str = json.dumps(message, ensure_ascii=False, default=str)
            await connection_info.websocket.send_text(message_str)
            return True
        except WebSocketDisconnect:
            # 连接已断开，清理连接
            await self._disconnect_internal(connection_info)
            return False
        except Exception as e:
            logger.warning(f"发送WebSocket消息失败: {e}")
            # 异常情况下也清理连接
            await self._disconnect_internal(connection_info)
            return False
    
    async def handle_client_message(self, connection_id: str, message: str):
        """处理客户端消息"""
        if connection_id not in self.all_connections:
            return
        
        connection_info = self.all_connections[connection_id]
        
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "ping":
                # 心跳包
                connection_info.last_ping = time.time()
                await self._send_to_connection(connection_info, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            elif message_type == "subscribe_task":
                # 订阅任务
                task_id = data.get("task_id")
                if task_id:
                    success = await self.subscribe_to_task(connection_id, task_id)
                    await self._send_to_connection(connection_info, {
                        "type": "subscription_result",
                        "task_id": task_id,
                        "success": success,
                        "action": "subscribe"
                    })
            
            elif message_type == "unsubscribe_task":
                # 取消订阅任务
                task_id = data.get("task_id")
                if task_id:
                    success = await self.unsubscribe_from_task(connection_id, task_id)
                    await self._send_to_connection(connection_info, {
                        "type": "subscription_result",
                        "task_id": task_id,
                        "success": success,
                        "action": "unsubscribe"
                    })
            
            elif message_type == "get_status":
                # 获取连接状态
                await self._send_to_connection(connection_info, {
                    "type": "status",
                    "connection_id": connection_id,
                    "user_id": connection_info.user_id,
                    "connected_at": connection_info.connected_at.isoformat(),
                    "subscriptions": list(connection_info.subscriptions),
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            else:
                logger.warning(f"未知的WebSocket消息类型: {message_type}")
        
        except json.JSONDecodeError:
            logger.warning(f"WebSocket收到无效JSON消息: {message}")
        except Exception as e:
            logger.error(f"处理WebSocket消息异常: {e}")
    
    async def _heartbeat_loop(self):
        """心跳检查循环"""
        while self.is_running:
            try:
                current_time = time.time()
                timeout_connections = []
                
                # 检查超时连接
                for connection_info in self.all_connections.values():
                    if current_time - connection_info.last_ping > 60:  # 60秒超时
                        timeout_connections.append(connection_info)
                
                # 断开超时连接
                for connection_info in timeout_connections:
                    logger.info(f"WebSocket连接超时，断开连接: {connection_info.connection_id}")
                    await self._disconnect_internal(connection_info)
                
                await asyncio.sleep(30)  # 每30秒检查一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳检查异常: {e}")
                await asyncio.sleep(30)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取连接统计信息"""
        return {
            "total_connections": len(self.all_connections),
            "active_users": len(self.user_connections),
            "task_subscriptions": len(self.task_subscribers),
            "connections_by_user": {
                user_id: len(connections) 
                for user_id, connections in self.user_connections.items()
            }
        }


# 全局WebSocket管理器实例
websocket_manager = WebSocketManager()