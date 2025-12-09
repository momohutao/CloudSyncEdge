"""
南向接口Sanic服务器
"""
from sanic import Sanic, Websocket
from sanic.response import text, json as sanic_json
import asyncio
import json
import logging

from .config import SouthboundConfig

logger = logging.getLogger(__name__)#创建 / 获取一个与当前模块名绑定的日志器实例，后续通过这个 logger 输出的日志，会自带模块名标识southbound.server

class SouthboundServer:
    """南向接口WebSocket服务器"""
    def __init__(self):
        self.app=Sanic("SouthboundServer")
        self.active_connections={}#ecu_id->websocket
        # 导入协议模块
        MockCodec, JSONRPCRequest, JSONRPCResponse = SouthboundConfig.get_protocol_module()
        self.MockCodec = MockCodec
        self.JSONRPCRequest = JSONRPCRequest
        self.JSONRPCResponse = JSONRPCResponse

        self.setup_routes()
    def setup_routes(self):
        """设置服务器路由"""
        @self.app.websocket(SouthboundConfig.WS_PATH)#当客户端发起 ws://服务器IP:端口/ws/ecu 的 WebSocket 连接请求时，会触发下面的 ecu_websocket 函数。
        async def ecu_websocket(request, ws: Websocket):
            """WebSocket连接处理"""
            await self.handle_ecu_connection(request, ws)
        @self.app.get("/")
        async def index(request):
            """首页 - 服务器状态"""
            return sanic_json({
                "service": "ECU Southbound Server",
                "version": "1.0.0",
                "status": "running",
                "mode": SouthboundConfig.DEV_MODE,
                "connected_devices": len(self.active_connections)
            })

        @self.app.get("/health")
        async def health_check(request):
            """健康检查"""
            return sanic_json({"status": "healthy"})#sanic_json()：Sanic 提供的工具函数，将 Python 字典转换成 JSON 格式的 HTTP 响应（自动设置 Content-Type: application/json 响应头）；

        async def handle_ecu_connection(self, request, ws: Websocket):
            """处理ECU连接"""
            ecu_id = None
            try:
                # 1. 接收认证消息
                message = await ws.recv()
                data = json.loads(message)
                # 2. 验证消息格式
                if not self.validate_connection_request(data):
                    await self.send_error(ws, -400, "Invalid connection request")
                    return
                # 3. 提取设备ID
                ecu_id = data.get("ecu_id", "unknown")# "unknown"：默认值
                # 4. 注册连接
                """把当前认证通过的ECU设备连接信息，以ecu_id为键存入注册表：如果该 ecu_id已存在（比如设备重连），会覆盖旧的连接信息（保证始终指向最新的
                WebSocket  连接）"""


                self.active_connections[ecu_id]={
                    "websocket":ws,
                    "ip":request.ip,
                    "connected_at":asyncio.get_event_loop().time()#存储设备的连接时间戳
                }
                logger.info(f"Device connected: {ecu_id}")
                # 5. 发送连接成功响应
                await self.send_success(ws, {
                    "status": "connected",
                    "ecu_id": ecu_id,
                    "server_time": asyncio.get_event_loop().time()
                })
                # 6. 进入消息循环
                await self.message_loop(ecu_id, ws)
            except Exception as e:
                logger.error(f"Connection error: {str(e)}")
            finally:
                # 7. 清理连接
                if ecu_id and ecu_id in self.active_connections:
                    del self.active_connections[ecu_id]
                    logger.info(f"Device disconnected: {ecu_id}")

        async def message_loop(self, ecu_id: str, ws: Websocket):
            """消息处理循环"""
            while True:
                try:
                    #接受消息
                    message=await ws.recv()
                    logger.debug(f"Received from {ecu_id}:{message[:100]}...")#截取消息的前 100 个字符（[:100] 是字符串切片）；
                    # 截取消息的前 100 个字符（[:100] 是字符串切片）；...表示后面还有内容
                    # 处理消息
                    response = await self.process_message(ecu_id, message)
                    # 发送响应
                    if response:
                        await ws.send(response)
                except Exception as e:
                    logger.error(f"Message loop error for {ecu_id}: {str(e)}")
                    break

        async def process_message(self, ecu_id: str, message: str) -> str:
            """处理设备消息"""
            try:
                decoded = self.MockCodec.decode_message(message)
                if isinstance(decoded, self.JSONRPCRequest):
                    return await self.handle_request(ecu_id, decoded)
                elif isinstance(decoded,self.JSONRPCResponse):
                    return await self.handle_response(ecu_id, decoded)
                else:
                    return self.create_error_response(
                        -32600, "Invalid message type", request_id=None
                    )
            except Exception as e:
                logger.error(f"Message processing error: {str(e)}")
                return self.create_error_response(
                    -32603, f"Internal error: {str(e)}", request_id=None
                )

        async def handle_request(self, ecu_id: str, request) -> str:
            """处理请求消息"""
            # 第一阶段：只实现基本响应
            logger.info(f"Request from {ecu_id}: {request.method}")

            # 创建Mock响应
            response = self.MockCodec.create_mock_response(request, success=True)
            return self.MockCodec.encode_message(response)#返回JSON格式

        async def handle_response(self, ecu_id: str, response) -> str:
            """处理响应消息"""
            logger.info(f"Response from {ecu_id}: {'success' if response.is_success() else 'error'}")
            return None  # 不需要发送响应

        def validate_connection_request(self, data: dict) -> bool:
            """验证连接请求"""
            return bool(data.get("ecu_id"))

        async def send_error(self, ws: Websocket, code: int, message: str):
            """发送错误消息"""
            error_msg = self.create_error_response(code, message, None)
            await ws.send(error_msg)

        async def send_success(self, ws: Websocket, data: dict):
            """发送成功消息"""
            success_msg = json.dumps({
                "jsonrpc": "2.0",
                "result": data,
                "id": None
            })
            await ws.send(success_msg)

        def create_error_response(self, code: int, message: str, request_id: str) -> str:
            """创建错误响应"""
            error_response = self.JSONRPCResponse.error_response(code, message, request_id=request_id)
            return self.MockCodec.encode_message(error_response)

        def start(self):
            """启动服务器"""
            logger.info(f"Starting Southbound Server on {SouthboundConfig.WS_HOST}:{SouthboundConfig.WS_PORT}")
            self.app.run(
                host=SouthboundConfig.WS_HOST,
                port=SouthboundConfig.WS_PORT,
                debug=(SouthboundConfig.DEV_MODE == "development"),
                access_log=True
            )
