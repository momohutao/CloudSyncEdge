"""
南向接口启动脚本
"""
import sys
import os
# 添加协议模块路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from southbound.server import SouthboundServer
from southbound.config import SouthboundConfig

if __name__ == "__main__":
    # 加载配置
    SouthboundConfig.load_from_env()

    # 创建并启动服务器
    server = SouthboundServer()
    print("=" * 50)
    print("ECU Southbound Server")
    print(f"Mode: {SouthboundConfig.DEV_MODE}")
    print(f"Host: {SouthboundConfig.WS_HOST}")
    print(f"Port: {SouthboundConfig.WS_PORT}")
    print(f"Mock Protocol: {SouthboundConfig.USE_MOCK_PROTOCOL}")
    print("=" * 50)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Server error: {e}")