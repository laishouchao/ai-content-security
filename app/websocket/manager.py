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
        self.last_ping = time.time()  # 最后一次接收到ping的时间
        self.last_pong = time.time()  # 最后一次发送pong的时间
        self.last_heartbeat_send = time.time()  # 最后一次发送心跳的时间
        self.subscriptions: Set[str] = set()  # 订阅的任务ID
        self.ping_count = 0  # ping计数
        self.is_alive = True  # 连接是否活跃


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
        
        # 心跳配置
        self.heartbeat_interval = 30  # 心跳间隔（30秒）
        self.heartbeat_timeout = 90   # 心跳超时（90秒）
        self.ping_interval = 25       # 主动ping间隔（25秒）
        self.max_missed_pings = 3     # 最大未响应ping数
        
        # 统计信息
        self.heartbeat_stats = {
            'total_pings_sent': 0,
            'total_pongs_received': 0,
            'timeout_disconnections': 0,
            'last_cleanup_time': time.time()
        }
    
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
                connection_info.ping_count += 1
                self.heartbeat_stats['total_pongs_received'] += 1
                
                # 响应pong消息
                await self._send_to_connection(connection_info, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat(),
                    "ping_count": connection_info.ping_count,
                    "server_time": time.time()
                })
                
                logger.debug(f"接收到心跳ping: {connection_id}, 计数: {connection_info.ping_count}")
            
            elif message_type == "pong":
                # 客户端响应服务器的ping
                connection_info.last_pong = time.time()
                connection_info.ping_count += 1
                logger.debug(f"接收到心跳pong: {connection_id}, 计数: {connection_info.ping_count}")
            
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
        logger.info(f"心跳检查循环已启动，间隔: {self.heartbeat_interval}秒")
        
        while self.is_running:
            try:
                current_time = time.time()
                connections_to_check = list(self.all_connections.values())
                timeout_connections = []
                ping_connections = []
                
                # 检查所有连接
                for connection_info in connections_to_check:
                    if not connection_info.is_alive:
                        continue
                    
                    # 检查是否需要发送ping
                    time_since_last_heartbeat = current_time - connection_info.last_heartbeat_send
                    if time_since_last_heartbeat >= self.ping_interval:
                        ping_connections.append(connection_info)
                    
                    # 检查是否超时
                    time_since_last_response = current_time - max(
                        connection_info.last_ping, 
                        connection_info.last_pong
                    )
                    
                    if time_since_last_response > self.heartbeat_timeout:
                        timeout_connections.append(connection_info)
                        logger.warning(
                            f"连接超时: {connection_info.connection_id}, "
                            f"最后响应: {time_since_last_response:.1f}秒前"
                        )
                
                # 发送主动ping
                for connection_info in ping_connections:
                    await self._send_heartbeat_ping(connection_info)
                
                # 断开超时连接
                for connection_info in timeout_connections:
                    connection_info.is_alive = False
                    self.heartbeat_stats['timeout_disconnections'] += 1
                    logger.info(f"WebSocket连接超时，断开连接: {connection_info.connection_id}")
                    await self._disconnect_internal(connection_info)
                
                # 更新统计信息
                self.heartbeat_stats['last_cleanup_time'] = current_time
                
                # 记录详细的心跳统计
                if len(connections_to_check) > 0:
                    logger.debug(
                        f"心跳检查完成: 连接数={len(connections_to_check)}, "
                        f"ping数={len(ping_connections)}, 超时数={len(timeout_connections)}"
                    )
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except asyncio.CancelledError:
                logger.info("心跳循环被取消")
                break
            except Exception as e:
                logger.error(f"心跳检查异常: {e}")
                await asyncio.sleep(self.heartbeat_interval)
    
    async def _send_heartbeat_ping(self, connection_info: ConnectionInfo):
        """发送主动心跳ping"""
        try:
            current_time = time.time()
            connection_info.last_heartbeat_send = current_time
            self.heartbeat_stats['total_pings_sent'] += 1
            
            ping_message = {
                "type": "ping",
                "timestamp": datetime.utcnow().isoformat(),
                "server_time": current_time,
                "sequence": self.heartbeat_stats['total_pings_sent']
            }
            
            success = await self._send_to_connection(connection_info, ping_message)
            
            if success:
                logger.debug(f"发送心跳ping: {connection_info.connection_id}")
            else:
                logger.warning(f"发送心跳ping失败: {connection_info.connection_id}")
                connection_info.is_alive = False
                
        except Exception as e:
            logger.error(f"发送心跳ping异常: {e}")
            connection_info.is_alive = False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取连接统计信息"""
        current_time = time.time()
        
        # 计算活跃连接
        active_connections = sum(
            1 for conn in self.all_connections.values() 
            if conn.is_alive and (current_time - conn.last_ping) < self.heartbeat_timeout
        )
        
        return {
            "total_connections": len(self.all_connections),
            "active_connections": active_connections,
            "active_users": len(self.user_connections),
            "task_subscriptions": len(self.task_subscribers),
            "connections_by_user": {
                user_id: len(connections) 
                for user_id, connections in self.user_connections.items()
            },
            "heartbeat_stats": {
                **self.heartbeat_stats,
                "heartbeat_interval": self.heartbeat_interval,
                "heartbeat_timeout": self.heartbeat_timeout,
                "ping_interval": self.ping_interval,
                "max_missed_pings": self.max_missed_pings,
                "uptime_seconds": current_time - self.heartbeat_stats['last_cleanup_time'] if self.is_running else 0
            },
            "connection_details": [
                {
                    "connection_id": conn.connection_id,
                    "user_id": conn.user_id,
                    "connected_at": conn.connected_at.isoformat(),
                    "last_ping": conn.last_ping,
                    "last_pong": conn.last_pong,
                    "ping_count": conn.ping_count,
                    "is_alive": conn.is_alive,
                    "subscriptions_count": len(conn.subscriptions)
                }
                for conn in self.all_connections.values()
            ]
        }


# 全局WebSocket管理器实例
websocket_manager = WebSocketManager()