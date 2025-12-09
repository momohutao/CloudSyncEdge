"""
南向接口配置管理
"""
import os
from typing import Dict,Any
class SouthboundConfig:
    """南向接口配置"""
    DEV_MODE = "development"  # development | production
    USE_MOCK_PROTOCOL = True  # 是否使用Mock协议
    # WebSocket服务器配置
    WS_HOST = "0.0.0.0"
    WS_PORT = 8081
    WS_PATH = "/ws/ecu"
    # 连接配置
    MAX_CONNECTIONS = 1000
    HEARTBEAT_INTERVAL = 30
    CONNECTION_TIMEOUT = 60

    # 协议配置
    PROTOCOL_VERSION = "1.0"

    @classmethod
    def load_from_env(cls):
        """从环境变量加载配置"""
        # 1. 加载WebSocket服务器地址配置,没有参数中设置，默认从类本身获取
        cls.WS_HOST = os.getenv("SB_WS_HOST", cls.WS_HOST)
        # 2. 加载WebSocket服务器端口配置（转成整数）
        cls.WS_PORT = int(os.getenv("SB_WS_PORT", cls.WS_PORT))
        # 3. 加载开发模式配置
        cls.DEV_MODE = os.getenv("SB_DEV_MODE", cls.DEV_MODE)
    @classmethod
    def get_protocol_modules(cls):
        """获取协议模块（动态导入）"""
        try:
            from protocol import MockCodec,JSONRPCRequest, JSONRPCResponse
            return MockCodec, JSONRPCRequest, JSONRPCResponse
        except ImportError:
            raise ImportError("Protocol module not found. Please install protocol package first.")