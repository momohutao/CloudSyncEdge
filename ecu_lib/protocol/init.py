"""
协议模块
"""

from .jsonrpc import JSONRPCRequest, JSONRPCResponse, JSONRPCNotification
from .message_types import MessageTypes, ErrorCodes, DeviceTypes, DeviceStatus, CommandStatus
from .mock_codec import MockCodec, encode_message, decode_message

__version__ = "1.0.0"
__author__ = "Team D - Protocol Design"

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
    'decode_message'
]