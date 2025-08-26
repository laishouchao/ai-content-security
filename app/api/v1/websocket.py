from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any
from datetime import datetime
import json

from app.core.dependencies import get_current_user_websocket, get_current_user
from app.core.logging import logger
from app.websocket.manager import websocket_manager
from app.websocket.handlers import task_monitor
from app.models.user import User

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    current_user: User = Depends(get_current_user_websocket)
):
    """WebSocket连接端点"""
    connection_id = None
    
    try:
        # 建立连接
        connection_id = await websocket_manager.connect(websocket, current_user.id)
        logger.info(f"WebSocket连接建立: 用户 {current_user.username} ({current_user.id})")
        
        # 处理消息循环
        while True:
            try:
                # 接收客户端消息
                message = await websocket.receive_text()
                
                # 处理消息
                await websocket_manager.handle_client_message(connection_id, message)
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket客户端主动断开: {connection_id}")
                break
            except Exception as e:
                logger.error(f"WebSocket消息处理异常: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"消息处理失败: {str(e)}",
                    "timestamp": str(datetime.utcnow())
                }, ensure_ascii=False))
    
    except Exception as e:
        logger.error(f"WebSocket连接异常: {e}")
    
    finally:
        # 断开连接
        if connection_id:
            await websocket_manager.disconnect(connection_id)


@router.get("/ws/stats")
async def get_websocket_stats(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """获取WebSocket连接统计信息（管理员）"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    stats = websocket_manager.get_stats()
    return {
        "success": True,
        "data": stats,
        "message": "WebSocket统计信息获取成功"
    }


@router.post("/ws/broadcast")
async def broadcast_message(
    message_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """广播消息（管理员）"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    try:
        message = {
            "type": "admin_broadcast",
            "message": message_data.get("message", ""),
            "data": message_data.get("data", {}),
            "sender": current_user.username,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        sent_count = await websocket_manager.broadcast_to_all(message)
        
        return {
            "success": True,
            "sent_count": sent_count,
            "message": f"消息已广播到 {sent_count} 个连接"
        }
    
    except Exception as e:
        logger.error(f"广播消息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="广播消息失败"
        )


@router.get("/tasks/{task_id}/status")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """获取任务状态"""
    try:
        task_status = await task_monitor.get_task_status(task_id)
        
        if not task_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        # 检查用户权限（只能查看自己的任务，除非是管理员）
        if not current_user.is_admin:
            # 这里需要验证任务属于当前用户
            # 由于task_status中没有user_id，我们需要从数据库查询
            from app.core.database import get_async_session
            from app.models.task import ScanTask
            from sqlalchemy import select
            
            async for db in get_async_session():
                stmt = select(ScanTask).where(ScanTask.id == task_id)
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()
                
                if not task or task.user_id != current_user.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="权限不足"
                    )
        
        return {
            "success": True,
            "data": task_status,
            "message": "任务状态获取成功"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取任务状态失败"
        )


@router.get("/tasks/{task_id}/logs")
async def get_task_logs(
    task_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """获取任务日志"""
    try:
        # 检查用户权限
        if not current_user.is_admin:
            from app.core.database import get_async_session
            from app.models.task import ScanTask
            from sqlalchemy import select
            
            async for db in get_async_session():
                stmt = select(ScanTask).where(ScanTask.id == task_id)
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()
                
                if not task or task.user_id != current_user.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="权限不足"
                    )
        
        logs = await task_monitor.get_task_logs(task_id, limit)
        
        return {
            "success": True,
            "data": {
                "task_id": task_id,
                "logs": logs,
                "total": len(logs)
            },
            "message": "任务日志获取成功"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务日志失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取任务日志失败"
        )