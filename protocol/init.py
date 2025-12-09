"""
协议模块
"""
import sys

# 版本检查
if sys.version_info < (3, 7):
    raise RuntimeError("需要Python 3.7或更高版本")

from .jsonrpc import JSONRPCRequest, JSONRPCResponse, JSONRPCNotification
from .message_types import MessageTypes, ErrorCodes, DeviceTypes, DeviceStatus, CommandStatus
from .mock_codec import MockCodec, encode_message, decode_message
from .base_logger import (
    DatabaseLogger, 
    MockDatabaseLogger, 
    LogDirection, 
    LogLevel,
    get_database_logger,
    SyncDatabaseLogger
)
from .models import (
    ProtocolLogBase,
    ErrorLogBase,
    HeartbeatLogBase,
    ProtocolStats,
    create_protocol_log_model
)

__version__ = "1.0.0"
__author__ = "Team D - Protocol Design"
__python_version__ = f"{sys.version_info.major}.{sys.version_info.minor}"

__all__ = [
    # 基础类
    'JSONRPCRequest',
    'JSONRPCResponse',
    'JSONRPCNotification',
    
    # 常量
    'MessageTypes',
    'ErrorCodes',
    'DeviceTypes',
    'DeviceStatus',
    'CommandStatus',
    
    # 编解码
    'MockCodec',
    'encode_message',
    'decode_message',
    
    # 日志服务
    'DatabaseLogger',
    'MockDatabaseLogger',
    'LogDirection',
    'LogLevel',
    'get_database_logger',
    'SyncDatabaseLogger',
    
    # 数据模型
    'ProtocolLogBase',
    'ErrorLogBase',
    'HeartbeatLogBase',
    'ProtocolStats',
    'create_protocol_log_model'
]

# 模块初始化信息
print(f"[Protocol Module] v{__version__} loaded (Python {__python_version__})")