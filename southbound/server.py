import asyncio
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import websockets
    from websockets.server import WebSocketServerProtocol

    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    print("⚠️ 未安装websockets库，WebSocket功能不可用")

# 注意：这里可能需要修复导入路径
try:
    from src.protocol.message_types import MessageTypes, DeviceTypes, ErrorCodes
except ImportError:
    print("⚠️ 无法从src.protocol导入，尝试其他路径...")
    from ..src.protocol.message_types import MessageTypes, DeviceTypes, ErrorCodes

from .database import init_database, get_database_client
from .interface_impl import SouthboundInterfaceImpl


class SouthboundWebSocketServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8082):
        self.host = host
        self.port = port
        self.server = None

        # 先设置为None，在initialize中初始化
        self.db_client = None
        self.ecu_interface = None
        self.southbound_interface = None
        self.active_connections = {}
        self.device_info = {}

        # 设备认证令牌 - 与ecu_management中的设备ID匹配
        self.device_tokens = {
            "BIKE001": "bike_token_001",
            "BIKE002": "bike_token_001",
            "DOOR001": "gate_token_001",
            "DOOR002": "gate_token_001"
        }

        print(f"🚀 南向WebSocket服务器初始化: {host}:{port}")

    async def initialize(self):
        """初始化服务器"""
        # 1. 初始化数据库（南向模块自己的数据库）
        await init_database()
        self.db_client = get_database_client()

        # 2. 初始化ecu_lib的接口
        try:
            from ecu_lib.devices.device_registry import DeviceRegistry
            from ecu_lib.interfaces.ecu_interface import DefaultECUInterface

            # 注意：DefaultECUInterface可能需要正确的参数
            device_registry = DeviceRegistry()

            # 尝试不同的初始化方式
            try:
                self.ecu_interface = DefaultECUInterface(device_registry, self.db_client)
            except TypeError:
                # 如果构造函数参数不匹配，尝试其他方式
                self.ecu_interface = DefaultECUInterface(device_registry)

        except ImportError as e:
            print(f"⚠️ 导入ecu_lib失败: {e}")
            print("将在模拟模式下运行...")

            # 创建一个模拟的ecu_interface
            class MockECUInterface:
                async def register_device(self, ecu_id, device_info):
                    print(f"模拟注册设备: {ecu_id}")
                    return True

                async def update_device_last_seen(self, ecu_id):
                    print(f"模拟更新设备最后在线时间: {ecu_id}")
                    return True

                async def update_device_status(self, ecu_id, status):
                    print(f"模拟更新设备状态: {ecu_id} -> {status}")
                    return True

            self.ecu_interface = MockECUInterface()

        # 3. 初始化南向接口
        self.southbound_interface = SouthboundInterfaceImpl(self)

        print("✅ 南向服务器初始化完成")

    async def authenticate_device(self, ecu_id: str, token: str) -> bool:
        """设备认证"""
        valid_token = self.device_tokens.get(ecu_id)
        if valid_token != token:
            print(f"❌ 设备认证失败: {ecu_id}")
            return False

        # 调用成员A的接口注册设备
        try:
            if hasattr(self.ecu_interface, 'register_device'):
                success = await self.ecu_interface.register_device(
                    ecu_id=ecu_id,
                    device_info={
                        "type": DeviceTypes.BIKE,
                        "status": "online",
                        "last_seen": datetime.now().isoformat()
                    }
                )
                return success
            else:
                print(f"⚠️ ecu_interface没有register_device方法")
                return True  # 模拟成功
        except Exception as e:
            print(f"❌ 设备注册失败: {e}")
            return False

    async def handle_connection(self, websocket: WebSocketServerProtocol, path: str):
        """处理WebSocket连接"""
        client_ip = websocket.remote_address[0]
        print(f"📡 新的WebSocket连接: {client_ip}")

        try:
            # 1. 接收认证消息
            message = await websocket.recv()
            data = json.loads(message)

            # 2. 验证消息格式
            if data.get("method") != MessageTypes.DEVICE_AUTH:
                await websocket.send(json.dumps({
                    "error": "Invalid message type",
                    "error_code": ErrorCodes.INVALID_MESSAGE_FORMAT
                }))
                return

            # 3. 设备认证
            ecu_id = data.get("params", {}).get("ecu_id")
            token = data.get("params", {}).get("token")

            if not ecu_id or not token:
                await websocket.send(json.dumps({
                    "error": "Missing ecu_id or token",
                    "error_code": ErrorCodes.INVALID_PARAMETERS
                }))
                return

            if not await self.authenticate_device(ecu_id, token):
                await websocket.send(json.dumps({
                    "error": "Authentication failed",
                    "error_code": ErrorCodes.AUTH_FAILED
                }))
                return

            # 4. 记录连接
            self.active_connections[ecu_id] = websocket
            self.device_info[ecu_id] = {
                "ip": client_ip,
                "connected_at": datetime.now(),
                "protocol": "websocket"
            }

            # 5. 记录连接日志
            if self.db_client:
                # 注意：db_client可能有不同的方法名
                try:
                    from .database.client import ConnectionInfo
                    conn_info = ConnectionInfo(
                        ecu_id=ecu_id,
                        ip_address=client_ip,
                        protocol="websocket"
                    )
                    await self.db_client.add_connection(conn_info)
                except Exception as e:
                    print(f"记录连接日志失败: {e}")

            # 6. 发送认证成功响应
            await websocket.send(json.dumps({
                "method": MessageTypes.DEVICE_AUTH_RESPONSE,
                "params": {
                    "success": True,
                    "ecu_id": ecu_id,
                    "message": "Authentication successful",
                    "server_time": datetime.now().isoformat()
                }
            }))

            print(f"✅ 设备认证成功: {ecu_id}")

            # 7. 保持连接，处理后续消息
            await self.handle_device_messages(ecu_id, websocket)

        except json.JSONDecodeError:
            await websocket.send(json.dumps({
                "error": "Invalid JSON format",
                "error_code": ErrorCodes.INVALID_JSON
            }))
        except Exception as e:
            print(f"❌ 处理连接时出错: {e}")
        finally:
            # 8. 清理连接
            await self.cleanup_connection(ecu_id, websocket)

    async def handle_device_messages(self, ecu_id: str, websocket: WebSocketServerProtocol):
        """处理设备消息"""
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    method = data.get("method")

                    if method == MessageTypes.DEVICE_HEARTBEAT:
                        await self.handle_heartbeat(ecu_id, data.get("params", {}))

                    elif method == MessageTypes.DEVICE_DATA:
                        await self.handle_device_data(ecu_id, data.get("params", {}))

                    elif method == MessageTypes.COMMAND_RESPONSE:
                        await self.handle_command_response(ecu_id, data.get("params", {}))

                    else:
                        print(f"⚠️ 未知消息类型: {method}")

                except json.JSONDecodeError:
                    print(f"❌ 无效的JSON消息: {message}")

        except websockets.exceptions.ConnectionClosed:
            print(f"📴 连接关闭: {ecu_id}")
        except Exception as e:
            print(f"❌ 处理消息时出错: {e}")

    async def handle_heartbeat(self, ecu_id: str, params: Dict[str, Any]):
        """处理心跳"""
        print(f"❤️  心跳: {ecu_id}")

        # 更新心跳时间
        if self.db_client:
            try:
                await self.db_client.update_heartbeat(ecu_id)
            except Exception as e:
                print(f"更新心跳失败: {e}")

        # 更新设备最后在线时间
        try:
            if hasattr(self.ecu_interface, 'update_device_last_seen'):
                await self.ecu_interface.update_device_last_seen(ecu_id)
        except Exception as e:
            print(f"⚠️ 更新设备最后在线时间失败: {e}")

    async def handle_device_data(self, ecu_id: str, params: Dict[str, Any]):
        """处理设备数据"""
        print(f"📊 设备数据: {ecu_id} - {params.get('data_type', 'unknown')}")

        # 记录数据日志
        if self.db_client:
            try:
                # 记录到南向数据库
                from .database.client import DeviceLog
                log = DeviceLog(
                    ecu_id=ecu_id,
                    action_type="status_update",
                    action_data=params,
                    ip_address=self.device_info.get(ecu_id, {}).get("ip")
                )
                await self.db_client.add_log(log)
            except Exception as e:
                print(f"记录设备数据失败: {e}")

    async def handle_command_response(self, ecu_id: str, params: Dict[str, Any]):
        """处理命令响应"""
        print(f"📨 命令响应: {ecu_id} - {params.get('command', 'unknown')}")

    async def cleanup_connection(self, ecu_id: str, websocket: WebSocketServerProtocol):
        """清理连接"""
        if ecu_id in self.active_connections:
            del self.active_connections[ecu_id]

        if ecu_id in self.device_info:
            # 记录断开日志
            if self.db_client:
                try:
                    await self.db_client.remove_connection(ecu_id, "connection_closed")
                except Exception as e:
                    print(f"记录断开日志失败: {e}")

            # 更新设备状态
            try:
                if hasattr(self.ecu_interface, 'update_device_status'):
                    await self.ecu_interface.update_device_status(ecu_id, "offline")
            except Exception as e:
                print(f"⚠️ 更新设备状态失败: {e}")

            del self.device_info[ecu_id]

        print(f"🗑️  清理连接: {ecu_id}")

    async def start(self):
        """启动服务器"""
        if not HAS_WEBSOCKETS:
            print("❌ 无法启动WebSocket服务器，未安装websockets库")
            return

        # 初始化
        await self.initialize()

        # 启动WebSocket服务器
        self.server = await websockets.serve(
            self.handle_connection,
            self.host,
            self.port
        )

        print(f"✅ 南向WebSocket服务器启动成功: ws://{self.host}:{self.port}")
        print("按 Ctrl+C 停止服务器")

        # 保持运行
        await self.server.wait_closed()

    async def stop(self):
        """停止服务器"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            print("✅ 南向WebSocket服务器已停止")


async def main():
    """主函数"""
    server = SouthboundWebSocketServer("0.0.0.0", 8082)

    try:
        await server.start()
    except KeyboardInterrupt:
        print("\n🛑 接收到中断信号，正在停止服务器...")
    except Exception as e:
        print(f"\n❌ 服务器运行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())