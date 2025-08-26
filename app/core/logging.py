import logging
import logging.config
import json
import sys
from datetime import datetime
from typing import Any, Dict
from pathlib import Path

from app.core.config import settings


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # 添加自定义字段
        if hasattr(record, '__dict__'):
            if 'user_id' in record.__dict__:
                log_entry["user_id"] = record.__dict__['user_id']
            if 'task_id' in record.__dict__:
                log_entry["task_id"] = record.__dict__['task_id']
            if 'request_id' in record.__dict__:
                log_entry["request_id"] = record.__dict__['request_id']
            if 'extra' in record.__dict__:
                log_entry["extra"] = record.__dict__['extra']
            
        # 添加异常信息
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Unknown",
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
            
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging():
    """设置日志配置"""
    
    # 确保日志目录存在
    Path(settings.LOGS_PATH).mkdir(parents=True, exist_ok=True)
    
    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "structured": {
                "()": StructuredFormatter,
            },
        },
        "handlers": {
            "console": {
                "level": "INFO",
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": sys.stdout,
            },
            "file": {
                "level": "INFO",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": f"{settings.LOGS_PATH}/app.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "formatter": "structured",
                "encoding": "utf-8",
            },
            "error_file": {
                "level": "ERROR",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": f"{settings.LOGS_PATH}/error.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "formatter": "structured",
                "encoding": "utf-8",
            },
            "task_file": {
                "level": "INFO",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": f"{settings.LOGS_PATH}/tasks.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10,
                "formatter": "structured",
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "": {  # root logger
                "level": settings.LOG_LEVEL,
                "handlers": ["console", "file", "error_file"],
                "propagate": False,
            },
            "app": {
                "level": settings.LOG_LEVEL,
                "handlers": ["console", "file", "error_file"],
                "propagate": False,
            },
            "app.tasks": {
                "level": "INFO",
                "handlers": ["task_file", "console"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["console", "error_file"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
        },
    }
    
    logging.config.dictConfig(LOGGING_CONFIG)


# 创建logger实例
logger = logging.getLogger("app")


class TaskLogger:
    """任务专用日志记录器"""
    
    def __init__(self, task_id: str, user_id: str | None = None):
        self.task_id = task_id
        self.user_id = user_id
        self.logger = logging.getLogger("app.tasks")
    
    def _log(self, level: str, message: str, extra: Dict[str, Any] | None = None):
        """记录日志"""
        log_extra = {
            "task_id": self.task_id,
            "user_id": self.user_id,
            "extra": extra or {}
        }
        
        getattr(self.logger, level.lower())(message, extra=log_extra)
    
    def info(self, message: str, extra: Dict[str, Any] | None = None):
        """记录信息日志"""
        self._log("INFO", message, extra)
    
    def warning(self, message: str, extra: Dict[str, Any] | None = None):
        """记录警告日志"""
        self._log("WARNING", message, extra)
    
    def error(self, message: str, extra: Dict[str, Any] | None = None):
        """记录错误日志"""
        self._log("ERROR", message, extra)
    
    def debug(self, message: str, extra: Dict[str, Any] | None = None):
        """记录调试日志"""
        self._log("DEBUG", message, extra)
