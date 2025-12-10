"""
数据库日志服务基类
"""
import json
import uuid
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timedelta  # 修复：添加timedelta导入
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class LogDirection(Enum):
    """日志方向"""
    INBOUND = "inbound"     # 入站消息
    OUTBOUND = "outbound"   # 出站消息


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DatabaseLogger(ABC):
    """数据库日志服务基类"""
    
    @abstractmethod
    async def log_protocol_message(self, direction: LogDirection, method: str, 
                                   data: Dict, ecu_id: Optional[str] = None,
                                   request_id: Optional[str] = None) -> str:
        """
        记录协议消息日志
        
        Args:
            direction: 消息方向（入站/出站）
            method: 方法名
            data: 消息数据
            ecu_id: 设备ID（可选）
            request_id: 请求ID（可选）
            
        Returns:
            日志ID
        """
        pass
    
    @abstractmethod
    async def log_error(self, error_code: int, error_message: str, 
                       context: Optional[Dict] = None,
                       ecu_id: Optional[str] = None) -> str:
        """
        记录错误日志
        
        Args:
            error_code: 错误代码
            error_message: 错误信息
            context: 上下文信息（可选）
            ecu_id: 设备ID（可选）
            
        Returns:
            错误日志ID
        """
        pass
    
    @abstractmethod
    async def log_heartbeat(self, ecu_id: str, status: Dict) -> str:
        """
        记录心跳日志
        
        Args:
            ecu_id: 设备ID
            status: 设备状态
            
        Returns:
            心跳日志ID
        """
        pass
    
    @abstractmethod
    async def batch_log_messages(self, messages: List[Dict]) -> bool:
        """
        批量记录消息日志
        
        Args:
            messages: 消息列表
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    async def get_protocol_stats(self, start_time: datetime, end_time: datetime) -> Dict:
        """
        获取协议统计信息
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            统计信息字典
        """
        pass
    
    @abstractmethod
    async def get_device_message_history(self, ecu_id: str, 
                                        limit: int = 100,
                                        start_time: Optional[datetime] = None,
                                        end_time: Optional[datetime] = None) -> List[Dict]:
        """
        获取设备消息历史
        
        Args:
            ecu_id: 设备ID
            limit: 限制条数
            start_time: 开始时间（可选）
            end_time: 结束时间（可选）
            
        Returns:
            消息历史列表
        """
        pass
    
    @abstractmethod
    async def cleanup_old_logs(self, days_to_keep: int = 30) -> int:
        """
        清理旧日志
        
        Args:
            days_to_keep: 保留天数
            
        Returns:
            删除的记录数
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """
        测试数据库连接
        
        Returns:
            连接是否成功
        """
        pass


class MockDatabaseLogger(DatabaseLogger):
    """Mock数据库日志服务（供开发使用）"""
    
    def __init__(self):
        self._logs: List[Dict] = []
        self._error_logs: List[Dict] = []
        self._heartbeat_logs: List[Dict] = []
        logger.info("Mock数据库日志服务已初始化")
    
    async def log_protocol_message(self, direction: LogDirection, method: str, 
                                   data: Dict, ecu_id: Optional[str] = None,
                                   request_id: Optional[str] = None) -> str:
        """记录协议消息日志（Mock实现）"""
        log_id = str(uuid.uuid4())
        log_entry = {
            "log_id": log_id,
            "timestamp": datetime.now(),
            "direction": direction.value,
            "method": method,
            "ecu_id": ecu_id,
            "request_id": request_id,
            "data": data,
            "message_size": len(json.dumps(data)) if data else 0,
            "status": "logged"
        }
        
        self._logs.append(log_entry)
        logger.debug(f"记录协议消息日志: {log_id} - {method} - {direction.value}")
        return log_id
    
    async def log_error(self, error_code: int, error_message: str, 
                       context: Optional[Dict] = None,
                       ecu_id: Optional[str] = None) -> str:
        """记录错误日志（Mock实现）"""
        error_id = str(uuid.uuid4())
        error_entry = {
            "error_id": error_id,
            "timestamp": datetime.now(),
            "error_code": error_code,
            "error_message": error_message,
            "context": context,
            "ecu_id": ecu_id,
            "stack_trace": None
        }
        
        self._error_logs.append(error_entry)
        logger.warning(f"记录错误日志: {error_id} - {error_code}: {error_message}")
        return error_id
    
    async def log_heartbeat(self, ecu_id: str, status: Dict) -> str:
        """记录心跳日志（Mock实现）"""
        heartbeat_id = str(uuid.uuid4())
        heartbeat_entry = {
            "heartbeat_id": heartbeat_id,
            "timestamp": datetime.now(),
            "ecu_id": ecu_id,
            "status": status,
            "latency": 0.05  # Mock延迟
        }
        
        self._heartbeat_logs.append(heartbeat_entry)
        logger.debug(f"记录心跳日志: {heartbeat_id} - {ecu_id}")
        return heartbeat_id
    
    async def batch_log_messages(self, messages: List[Dict]) -> bool:
        """批量记录消息日志（Mock实现）"""
        try:
            for message in messages:
                log_entry = {
                    "log_id": str(uuid.uuid4()),
                    "timestamp": datetime.now(),
                    **message
                }
                self._logs.append(log_entry)
            
            logger.info(f"批量记录 {len(messages)} 条消息日志")
            return True
        except Exception as e:
            logger.error(f"批量记录失败: {e}")
            return False
    
    async def get_protocol_stats(self, start_time: datetime, end_time: datetime) -> Dict:
        """获取协议统计信息（Mock实现）"""
        # 模拟统计计算
        inbound_count = sum(1 for log in self._logs 
                          if log["direction"] == "inbound" 
                          and start_time <= log["timestamp"] <= end_time)
        
        outbound_count = sum(1 for log in self._logs 
                           if log["direction"] == "outbound" 
                           and start_time <= log["timestamp"] <= end_time)
        
        error_count = len([error for error in self._error_logs 
                          if start_time <= error["timestamp"] <= end_time])
        
        total_messages = inbound_count + outbound_count
        success_rate = 1.0 if total_messages == 0 else 1.0 - (error_count / total_messages)
        
        # 计算平均消息大小
        message_sizes = [log.get("message_size", 0) for log in self._logs 
                        if start_time <= log["timestamp"] <= end_time]
        avg_message_size = sum(message_sizes) / len(message_sizes) if message_sizes else 0
        
        return {
            "total_messages": total_messages,
            "inbound_count": inbound_count,
            "outbound_count": outbound_count,
            "error_count": error_count,
            "avg_message_size": avg_message_size,
            "success_rate": success_rate,
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            },
            "generated_at": datetime.now().isoformat()
        }
    
    async def get_device_message_history(self, ecu_id: str, 
                                        limit: int = 100,
                                        start_time: Optional[datetime] = None,
                                        end_time: Optional[datetime] = None) -> List[Dict]:
        """获取设备消息历史（Mock实现）"""
        filtered_logs = [
            log for log in self._logs 
            if log.get("ecu_id") == ecu_id
        ]
        
        if start_time:
            filtered_logs = [log for log in filtered_logs if log["timestamp"] >= start_time]
        
        if end_time:
            filtered_logs = [log for log in filtered_logs if log["timestamp"] <= end_time]
        
        # 按时间倒序排序
        filtered_logs.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # 限制返回数量
        return filtered_logs[:limit]
    
    async def cleanup_old_logs(self, days_to_keep: int = 30) -> int:
        """清理旧日志（Mock实现）"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        old_logs_count = sum(1 for log in self._logs if log["timestamp"] < cutoff_date)
        old_errors_count = sum(1 for error in self._error_logs if error["timestamp"] < cutoff_date)
        
        # 模拟清理
        self._logs = [log for log in self._logs if log["timestamp"] >= cutoff_date]
        self._error_logs = [error for error in self._error_logs if error["timestamp"] >= cutoff_date]
        
        total_cleaned = old_logs_count + old_errors_count
        logger.info(f"清理旧日志: {total_cleaned} 条记录")
        return total_cleaned
    
    async def test_connection(self) -> bool:
        """测试连接（Mock实现）"""
        await asyncio.sleep(0.01)  # 模拟网络延迟
        return True


# 其他数据库实现类的导入占位（避免导入错误）
class SQLiteDatabaseLogger(MockDatabaseLogger):
    """SQLite数据库日志服务（占位实现）"""
    def __init__(self, **kwargs):
        super().__init__()
        logger.warning("使用SQLite的Mock实现，需要安装SQLAlchemy和aiosqlite")


class MySQLDatabaseLogger(MockDatabaseLogger):
    """MySQL数据库日志服务（占位实现）"""
    def __init__(self, **kwargs):
        super().__init__()
        logger.warning("使用MySQL的Mock实现，需要安装SQLAlchemy和aiomysql")


class PostgreSQLDatabaseLogger(MockDatabaseLogger):
    """PostgreSQL数据库日志服务（占位实现）"""
    def __init__(self, **kwargs):
        super().__init__()
        logger.warning("使用PostgreSQL的Mock实现，需要安装SQLAlchemy和asyncpg")


# 使用示例
def get_database_logger(db_type: str = "mock", **kwargs) -> DatabaseLogger:
    """
    获取数据库日志服务实例
    
    Args:
        db_type: 数据库类型 ("mock", "sqlite", "mysql", "postgres")
        **kwargs: 数据库连接参数
        
    Returns:
        数据库日志服务实例
    """
    if db_type == "mock":
        return MockDatabaseLogger()
    elif db_type == "sqlite":
        # SQLite实现
        try:
            from .sqlite_logger import SQLiteDatabaseLogger
            return SQLiteDatabaseLogger(**kwargs)
        except ImportError:
            logger.warning("SQLiteLogger未实现，使用Mock数据库")
            return SQLiteDatabaseLogger(**kwargs)
    elif db_type == "mysql":
        # MySQL实现
        try:
            from .mysql_logger import MySQLDatabaseLogger
            return MySQLDatabaseLogger(**kwargs)
        except ImportError:
            logger.warning("MySQLLogger未实现，使用Mock数据库")
            return MySQLDatabaseLogger(**kwargs)
    elif db_type == "postgres":
        # PostgreSQL实现
        try:
            from .postgres_logger import PostgreSQLDatabaseLogger
            return PostgreSQLDatabaseLogger(**kwargs)
        except ImportError:
            logger.warning("PostgreSQLLogger未实现，使用Mock数据库")
            return PostgreSQLDatabaseLogger(**kwargs)
    else:
        logger.warning(f"未知的数据库类型: {db_type}, 使用Mock数据库")
        return MockDatabaseLogger()


# 同步版本的包装器（用于非异步环境）
class SyncDatabaseLogger:
    """同步版本的数据库日志服务"""
    
    def __init__(self, db_type: str = "mock", **kwargs):
        self._async_logger = get_database_logger(db_type, **kwargs)
    
    def log_protocol_message(self, *args, **kwargs) -> str:
        """同步版本的log_protocol_message"""
        import asyncio
        return asyncio.run(self._async_logger.log_protocol_message(*args, **kwargs))
    
    def log_error(self, *args, **kwargs) -> str:
        """同步版本的log_error"""
        import asyncio
        return asyncio.run(self._async_logger.log_error(*args, **kwargs))
    
    def log_heartbeat(self, *args, **kwargs) -> str:
        """同步版本的log_heartbeat"""
        import asyncio
        return asyncio.run(self._async_logger.log_heartbeat(*args, **kwargs))
    
    def get_protocol_stats(self, *args, **kwargs) -> Dict:
        """同步版本的get_protocol_stats"""
        import asyncio
        return asyncio.run(self._async_logger.get_protocol_stats(*args, **kwargs))