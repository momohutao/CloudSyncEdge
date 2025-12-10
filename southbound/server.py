# southbound/server.py
import asyncio
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import websockets
    from websockets.server import WebSocketServerProtocol

    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    print("⚠️ 未安装websockets库，WebSocket功能不可用")

from protocol.message_types import MessageTypes, DeviceTypes, ErrorCodes
from ecu_lib.interface.ecu_interface import ECUInterface
from .database import init_database, get_database_client
from .interface_impl import SouthboundInterfaceImpl


class SouthboundWebSocketServer:
    """南向WebSocket服务器"""

    def __init__(self, host: str = "0.0.0.0", port: int = 8081):
        self.host = host
        self.port = port
        self.server = None

        # 依赖成员A的接口
        self.ecu_interface = ECUInterface()

        # 南向接口实现（供成员C调用）
        self.southbound_interface = SouthboundInterfaceImpl(self)

        # 数据库客户端
        self.db_client = None

        # 活跃连接
        self.active_connections: Dict[str, WebSocketServerProtocol] = {}
        self.device_info: Dict[str, Dict[str, Any]] = {}

        # 设备认证令牌（简化）
        self.device_tokens = {
            "bike_001": "bike_token_001",
            "gate_001": "gate_token_001",
            "sensor_001": "sensor_token_001"
        }

        print(f"🚀 南向WebSocket服务器初始化: {host}:{port}")

    async def initialize(self):
        """初始化服务器"""
        # 初始化数据库
        await init_database()
        self.db_client = get_database_client()

        print("✅ 南向服务器初始化完成")

    async def authenticate_device(self, ecu_id: str, token: str) -> bool:
        """设备认证"""
        valid_token = self.device_tokens.get(ecu_id)
        if valid_token != token:
            print(f"❌ 设备认证失败: {ecu_id}")
            return False

        # 调用成员A的接口注册设备
        try:
            success = await self.ecu_interface.register_device(
                ecu_id=ecu_id,
                device_info={
                    "type": DeviceTypes.BIKE,  # 可以从消息中获取实际类型
                    "status": "online",
                    "last_seen": datetime.now().isoformat()
                }
            )
            return success
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
                await self.db_client.log_connection(ecu_id, client_ip)

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
                        # 处理心跳
                        await self.handle_heartbeat(ecu_id, data.get("params", {}))

                    elif method == MessageTypes.DEVICE_DATA:
                        # 处理设备数据
                        await self.handle_device_data(ecu_id, data.get("params", {}))

                    elif method == MessageTypes.COMMAND_RESPONSE:
                        # 处理命令响应
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
            await self.db_client.update_heartbeat(ecu_id)

        # 更新设备最后在线时间（通过成员A的接口）
        try:
            await self.ecu_interface.update_device_last_seen(ecu_id)
        except Exception as e:
            print(f"⚠️ 更新设备最后在线时间失败: {e}")

    async def handle_device_data(self, ecu_id: str, params: Dict[str, Any]):
        """处理设备数据"""
        print(f"📊 设备数据: {ecu_id} - {params.get('data_type', 'unknown')}")

        # 记录数据日志
        if self.db_client:
            await self.db_client.log_status_update(ecu_id, params)

    async def handle_command_response(self, ecu_id: str, params: Dict[str, Any]):
        """处理命令响应"""
        print(f"📨 命令响应: {ecu_id} - {params.get('command', 'unknown')}")

        # 记录命令响应日志
        if self.db_client:
            await self.db_client.log_command_response(ecu_id, params)

    async def cleanup_connection(self, ecu_id: str, websocket: WebSocketServerProtocol):
        """清理连接"""
        if ecu_id in self.active_connections:
            del self.active_connections[ecu_id]

        if ecu_id in self.device_info:
            # 记录断开日志
            if self.db_client:
                await self.db_client.log_disconnection(ecu_id, "connection_closed")

            # 更新设备状态（通过成员A的接口）
            try:
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
        print(f"   活跃连接: {len(self.active_connections)}")
        print(f"   设备数量: {len(self.device_info)}")

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
    server = SouthboundWebSocketServer("0.0.0.0", 8081)

    try:
        await server.start()
    except KeyboardInterrupt:
        print("\n🛑 接收到中断信号，正在停止服务器...")
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())