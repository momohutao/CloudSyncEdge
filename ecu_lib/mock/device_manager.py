"""
本地Mock设备管理器 - 在集成成员B的真实接口前使用
"""
import asyncio
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Awaitable
from collections import defaultdict
import random

from protocol.jsonrpc import JSONRPCRequest, JSONRPCResponse, JSONRPCNotification
from protocol.message_types import MessageTypes, ErrorCodes, DeviceTypes, DeviceStatus
from protocol.mock_codec import MockCodec

from ..core.base_ecu import BaseECU, ECUConfig, ECUStatus
from ..devices.shared_bike import SharedBikeECU
from ..devices.door_access import DoorAccessECU
from ..interface.device_manager import DeviceManagerInterface

logger = logging.getLogger(__name__)


class MockWebSocketConnection:
    """Mock WebSocket连接模拟"""
    
    def __init__(self, connection_id: str):
        self.connection_id = connection_id
        self.connected = True
        self.messages_sent = []
        self.messages_received = []
        self.connected_at = datetime.now()
        self.last_activity = datetime.now()
        
    async def send(self, message: str):
        """发送消息"""
        if self.connected:
            self.messages_sent.append({
                "timestamp": datetime.now(),
                "message": message,
                "direction": "outbound"
            })
            self.last_activity = datetime.now()
            logger.debug(f"Mock WebSocket [{self.connection_id}] 发送消息: {message[:100]}...")
            return True
        return False
    
    async def receive(self) -> Optional[str]:
        """接收消息"""
        if self.connected and self.messages_received:
            message = self.messages_received.pop(0)
            self.last_activity = datetime.now()
            return message
        return None
    
    def disconnect(self):
        """断开连接"""
        self.connected = False
        logger.info(f"Mock WebSocket [{self.connection_id}] 已断开连接")


class MockDeviceManager(DeviceManagerInterface):
    """本地Mock设备管理器 - 模拟南向接口功能"""
    
    def __init__(self):
        # 设备注册表
        self._registered_devices: Dict[str, BaseECU] = {}
        self._device_connections: Dict[str, MockWebSocketConnection] = {}
        self._connection_devices: Dict[str, str] = {}  # connection_id -> ecu_id
        
        # 消息队列
        self._message_queue = asyncio.Queue(maxsize=1000)
        self._response_handlers: Dict[str, Callable[[JSONRPCResponse], Awaitable[None]]] = {}
        
        # 统计信息
        self._stats = {
            "devices_registered": 0,
            "connections_active": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "commands_executed": 0,
            "errors_occurred": 0,
            "start_time": datetime.now()
        }
        
        # 心跳管理
        self._heartbeat_intervals = defaultdict(int)
        self._heartbeat_tasks = {}
        
        # 启动消息处理器
        self._processing_task = asyncio.create_task(self._process_messages())
        
        logger.info("Mock设备管理器初始化完成")
    
    # =============== 设备注册和管理 ===============
    
    async def register_ecu(self, ecu_id: str, ecu_instance: BaseECU) -> bool:
        """注册ECU设备"""
        try:
            if ecu_id in self._registered_devices:
                logger.warning(f"ECU设备 {ecu_id} 已注册")
                return True
            
            self._registered_devices[ecu_id] = ecu_instance
            self._stats["devices_registered"] += 1
            
            # 设置心跳间隔
            self._heartbeat_intervals[ecu_id] = ecu_instance.config.heartbeat_interval
            
            # 启动心跳任务
            self._heartbeat_tasks[ecu_id] = asyncio.create_task(
                self._start_heartbeat_for_device(ecu_id)
            )
            
            logger.info(f"ECU设备注册成功: {ecu_id} ({ecu_instance.device_type})")
            return True
            
        except Exception as e:
            logger.error(f"注册ECU设备失败: {e}")
            self._stats["errors_occurred"] += 1
            return False
    
    async def unregister_ecu(self, ecu_id: str) -> bool:
        """注销ECU设备"""
        try:
            if ecu_id not in self._registered_devices:
                logger.warning(f"ECU设备 {ecu_id} 未注册")
                return False
            
            # 停止心跳任务
            if ecu_id in self._heartbeat_tasks:
                self._heartbeat_tasks[ecu_id].cancel()
                del self._heartbeat_tasks[ecu_id]
            
            # 断开相关连接
            connection_ids = [
                conn_id for conn_id, e_id in self._connection_devices.items()
                if e_id == ecu_id
            ]
            
            for conn_id in connection_ids:
                await self._disconnect_device(conn_id)
            
            # 移除设备
            del self._registered_devices[ecu_id]
            if ecu_id in self._heartbeat_intervals:
                del self._heartbeat_intervals[ecu_id]
            
            self._stats["devices_registered"] -= 1
            
            logger.info(f"ECU设备注销成功: {ecu_id}")
            return True
            
        except Exception as e:
            logger.error(f"注销ECU设备失败: {e}")
            return False
    
    async def get_registered_ecu(self, ecu_id: str) -> Optional[BaseECU]:
        """获取注册的ECU设备"""
        return self._registered_devices.get(ecu_id)
    
    async def list_registered_devices(self) -> List[Dict]:
        """列出所有注册的设备"""
        devices = []
        
        for ecu_id, ecu in self._registered_devices.items():
            device_info = {
                "ecu_id": ecu_id,
                "device_type": ecu.device_type,
                "status": ecu.status.value,
                "firmware_version": ecu.firmware_version,
                "connected": ecu_id in self._device_connections,
                "connection_id": next(
                    (conn_id for conn_id, e_id in self._connection_devices.items() 
                     if e_id == ecu_id), None
                ),
                "last_heartbeat": ecu._last_heartbeat.isoformat() if ecu._last_heartbeat else None,
                "stats": ecu._stats.copy()
            }
            devices.append(device_info)
        
        return devices
    
    # =============== 连接管理 ===============
    
    async def connect_device(self, ecu_id: str) -> Optional[str]:
        """连接设备（模拟WebSocket连接）"""
        try:
            if ecu_id not in self._registered_devices:
                logger.error(f"无法连接未注册的设备: {ecu_id}")
                return None
            
            if ecu_id in self._device_connections:
                logger.warning(f"设备 {ecu_id} 已连接")
                return self._device_connections[ecu_id].connection_id
            
            # 创建Mock WebSocket连接
            connection_id = f"conn_{uuid.uuid4().hex[:8]}"
            connection = MockWebSocketConnection(connection_id)
            
            self._device_connections[ecu_id] = connection
            self._connection_devices[connection_id] = ecu_id
            self._stats["connections_active"] += 1
            
            # 发送连接成功通知
            connection_message = {
                "type": "connection_established",
                "ecu_id": ecu_id,
                "connection_id": connection_id,
                "timestamp": datetime.now().isoformat(),
                "server_info": {
                    "version": "1.0.0",
                    "protocol": "JSON-RPC 2.0"
                }
            }
            
            await connection.send(json.dumps(connection_message))
            
            # 更新设备状态为在线
            ecu = self._registered_devices[ecu_id]
            if ecu.status != ECUStatus.ONLINE:
                await ecu.start()
            
            logger.info(f"设备连接成功: {ecu_id} -> {connection_id}")
            return connection_id
            
        except Exception as e:
            logger.error(f"连接设备失败: {e}")
            self._stats["errors_occurred"] += 1
            return None
    
    async def disconnect_device(self, ecu_id: str) -> bool:
        """断开设备连接"""
        try:
            if ecu_id not in self._device_connections:
                logger.warning(f"设备 {ecu_id} 未连接")
                return True
            
            connection = self._device_connections[ecu_id]
            await self._disconnect_device(connection.connection_id)
            
            logger.info(f"设备断开连接: {ecu_id}")
            return True
            
        except Exception as e:
            logger.error(f"断开设备连接失败: {e}")
            return False
    
    async def _disconnect_device(self, connection_id: str):
        """内部断开连接方法"""
        if connection_id in self._connection_devices:
            ecu_id = self._connection_devices[connection_id]
            
            # 断开WebSocket连接
            if ecu_id in self._device_connections:
                connection = self._device_connections[ecu_id]
                connection.disconnect()
                del self._device_connections[ecu_id]
            
            # 更新设备状态
            if ecu_id in self._registered_devices:
                ecu = self._registered_devices[ecu_id]
                ecu.status = ECUStatus.OFFLINE
            
            # 清理映射
            del self._connection_devices[connection_id]
            self._stats["connections_active"] -= 1
            
            # 发送断开连接通知
            disconnect_message = {
                "type": "connection_closed",
                "ecu_id": ecu_id,
                "connection_id": connection_id,
                "timestamp": datetime.now().isoformat(),
                "reason": "client_disconnect"
            }
            
            # 记录断开事件
            logger.debug(f"连接断开: {connection_id} -> {ecu_id}")
    
    async def get_connected_devices(self) -> List[Dict]:
        """获取已连接的设备列表"""
        connected_devices = []
        
        for ecu_id, connection in self._device_connections.items():
            if connection.connected:
                ecu = self._registered_devices.get(ecu_id)
                if ecu:
                    device_info = {
                        "ecu_id": ecu_id,
                        "device_type": ecu.device_type,
                        "connection_id": connection.connection_id,
                        "connected_at": connection.connected_at.isoformat(),
                        "last_activity": connection.last_activity.isoformat(),
                        "messages_sent": len(connection.messages_sent),
                        "messages_received": len(connection.messages_received),
                        "status": ecu.status.value
                    }
                    connected_devices.append(device_info)
        
        return connected_devices
    
    async def get_connection_status(self, ecu_id: str) -> Optional[Dict]:
        """获取连接状态"""
        if ecu_id not in self._device_connections:
            return None
        
        connection = self._device_connections[ecu_id]
        ecu = self._registered_devices.get(ecu_id)
        
        if not ecu:
            return None
        
        return {
            "ecu_id": ecu_id,
            "connected": connection.connected,
            "connection_id": connection.connection_id,
            "connected_at": connection.connected_at.isoformat(),
            "last_activity": connection.last_activity.isoformat(),
            "inactive_seconds": (datetime.now() - connection.last_activity).total_seconds(),
            "messages_sent": len(connection.messages_sent),
            "messages_received": len(connection.messages_received),
            "device_status": ecu.status.value,
            "heartbeat_interval": self._heartbeat_intervals.get(ecu_id, 30)
        }
    
    # =============== 消息处理 ===============
    
    async def send_command(self, ecu_id: str, command_data: Dict) -> Dict:
        """发送命令到设备"""
        try:
            self._stats["messages_sent"] += 1
            
            if ecu_id not in self._registered_devices:
                return {
                    "success": False,
                    "error_code": ErrorCodes.DEVICE_NOT_FOUND,
                    "error_message": f"Device {ecu_id} not found"
                }
            
            ecu = self._registered_devices[ecu_id]
            
            # 检查设备是否连接
            if ecu_id not in self._device_connections:
                return {
                    "success": False,
                    "error_code": ErrorCodes.DEVICE_OFFLINE,
                    "error_message": f"Device {ecu_id} is offline"
                }
            
            # 检查连接状态
            connection = self._device_connections[ecu_id]
            if not connection.connected:
                return {
                    "success": False,
                    "error_code": ErrorCodes.NETWORK_ERROR,
                    "error_message": f"Connection to {ecu_id} is closed"
                }
            
            # 创建JSON-RPC请求
            method = command_data.get("method")
            params = command_data.get("params", {})
            request_id = command_data.get("request_id", f"req_{uuid.uuid4().hex[:8]}")
            
            if not method:
                return {
                    "success": False,
                    "error_code": ErrorCodes.INVALID_REQUEST,
                    "error_message": "Method is required"
                }
            
            # 创建请求对象
            request = JSONRPCRequest(
                method=method,
                params=params,
                request_id=request_id
            )
            
            # 编码请求
            request_json = MockCodec.encode_message(request)
            
            # 发送请求
            sent = await connection.send(request_json)
            if not sent:
                return {
                    "success": False,
                    "error_code": ErrorCodes.NETWORK_ERROR,
                    "error_message": "Failed to send message"
                }
            
            # 创建响应处理器
            response_future = asyncio.Future()
            self._response_handlers[request_id] = lambda resp: response_future.set_result(resp)
            
            # 等待响应（带超时）
            try:
                timeout = command_data.get("timeout", 10)
                response = await asyncio.wait_for(response_future, timeout=timeout)
                
                self._stats["commands_executed"] += 1
                
                return {
                    "success": True,
                    "request_id": request_id,
                    "response": response.to_dict() if hasattr(response, 'to_dict') else response,
                    "sent_time": datetime.now().isoformat()
                }
                
            except asyncio.TimeoutError:
                # 清理处理器
                if request_id in self._response_handlers:
                    del self._response_handlers[request_id]
                
                return {
                    "success": False,
                    "error_code": ErrorCodes.COMMAND_TIMEOUT,
                    "error_message": f"Command timeout after {timeout}s"
                }
                
        except Exception as e:
            logger.error(f"发送命令失败: {e}")
            self._stats["errors_occurred"] += 1
            
            return {
                "success": False,
                "error_code": ErrorCodes.INTERNAL_ERROR,
                "error_message": f"Failed to send command: {str(e)}"
            }
    
    async def send_notification(self, ecu_id: str, notification_data: Dict) -> bool:
        """发送通知到设备（无响应）"""
        try:
            if ecu_id not in self._device_connections:
                logger.warning(f"无法发送通知，设备未连接: {ecu_id}")
                return False
            
            connection = self._device_connections[ecu_id]
            if not connection.connected:
                return False
            
            # 创建JSON-RPC通知
            method = notification_data.get("method")
            params = notification_data.get("params", {})
            
            if not method:
                logger.error("通知缺少method参数")
                return False
            
            notification = JSONRPCNotification(
                method=method,
                params=params
            )
            
            # 编码通知
            notification_json = MockCodec.encode_message(notification)
            
            # 发送通知
            sent = await connection.send(notification_json)
            
            if sent:
                self._stats["messages_sent"] += 1
                logger.debug(f"发送通知到 {ecu_id}: {method}")
            
            return sent
            
        except Exception as e:
            logger.error(f"发送通知失败: {e}")
            return False
    
    async def _process_messages(self):
        """处理消息队列"""
        logger.info("Mock消息处理器启动")
        
        try:
            while True:
                try:
                    # 从队列获取消息
                    message = await asyncio.wait_for(
                        self._message_queue.get(),
                        timeout=1.0
                    )
                    
                    await self._handle_message(message)
                    
                    # 标记任务完成
                    self._message_queue.task_done()
                    
                except asyncio.TimeoutError:
                    # 超时继续循环
                    continue
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"处理消息失败: {e}")
                    continue
                    
        except asyncio.CancelledError:
            logger.info("Mock消息处理器停止")
        except Exception as e:
            logger.error(f"消息处理器异常退出: {e}")
    
    async def _handle_message(self, message: Dict):
        """处理单个消息"""
        try:
            message_type = message.get("type")
            ecu_id = message.get("ecu_id")
            data = message.get("data", {})
            
            if not ecu_id or ecu_id not in self._registered_devices:
                logger.warning(f"收到未知设备的消息: {ecu_id}")
                return
            
            ecu = self._registered_devices[ecu_id]
            
            if message_type == "status_update":
                # 处理状态更新
                await self._handle_status_update(ecu, data)
                
            elif message_type == "command_response":
                # 处理命令响应
                await self._handle_command_response(ecu_id, data)
                
            elif message_type == "heartbeat":
                # 处理心跳
                await self._handle_heartbeat(ecu, data)
                
            elif message_type == "error":
                # 处理错误
                await self._handle_error(ecu_id, data)
                
            else:
                logger.warning(f"未知消息类型: {message_type}")
                
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
    
    async def _handle_status_update(self, ecu: BaseECU, data: Dict):
        """处理状态更新"""
        try:
            # 更新设备状态
            status_info = ecu.get_status_dict()
            
            # 模拟发送到云端
            cloud_message = {
                "type": "device_status",
                "ecu_id": ecu.ecu_id,
                "device_type": ecu.device_type,
                "status": status_info,
                "timestamp": datetime.now().isoformat(),
                "source": "mock_manager"
            }
            
            logger.debug(f"设备状态更新: {ecu.ecu_id} -> {ecu.status.value}")
            
            # 保存状态历史
            if ecu.db_client:
                try:
                    await ecu.db_client.save_ecu_status(ecu.ecu_id, status_info)
                except Exception as e:
                    logger.error(f"保存状态到数据库失败: {e}")
            
        except Exception as e:
            logger.error(f"处理状态更新失败: {e}")
    
    async def _handle_command_response(self, ecu_id: str, data: Dict):
        """处理命令响应"""
        try:
            request_id = data.get("request_id")
            response_data = data.get("response", {})
            
            if request_id and request_id in self._response_handlers:
                handler = self._response_handlers[request_id]
                
                # 创建响应对象
                if response_data.get("error"):
                    response = JSONRPCResponse.error_response(
                        response_data["error"].get("code", ErrorCodes.INTERNAL_ERROR),
                        response_data["error"].get("message", "Unknown error"),
                        response_data.get("data"),
                        request_id
                    )
                else:
                    response = JSONRPCResponse.success(
                        response_data.get("result", {}),
                        request_id
                    )
                
                # 调用处理器
                await handler(response)
                
                # 清理处理器
                del self._response_handlers[request_id]
                
                logger.debug(f"命令响应处理完成: {ecu_id} -> {request_id}")
            
        except Exception as e:
            logger.error(f"处理命令响应失败: {e}")
    
    async def _handle_heartbeat(self, ecu: BaseECU, data: Dict):
        """处理心跳"""
        try:
            ecu._last_heartbeat = datetime.now()
            ecu._stats["heartbeats_sent"] += 1
            
            # 更新连接最后活动时间
            if ecu.ecu_id in self._device_connections:
                connection = self._device_connections[ecu.ecu_id]
                connection.last_activity = datetime.now()
            
            # 保存心跳记录
            if ecu.db_client:
                try:
                    heartbeat_data = {
                        "ecu_id": ecu.ecu_id,
                        "timestamp": ecu._last_heartbeat.isoformat(),
                        "status": ecu.status.value,
                        "uptime": (datetime.now() - ecu._stats["uptime_start"]).total_seconds()
                    }
                    await ecu.db_client.save_heartbeat(ecu.ecu_id, heartbeat_data)
                except Exception as e:
                    logger.error(f"保存心跳记录失败: {e}")
            
            logger.debug(f"心跳处理: {ecu.ecu_id}")
            
        except Exception as e:
            logger.error(f"处理心跳失败: {e}")
    
    async def _handle_error(self, ecu_id: str, data: Dict):
        """处理错误"""
        try:
            error_code = data.get("error_code", ErrorCodes.INTERNAL_ERROR)
            error_message = data.get("error_message", "Unknown error")
            
            logger.error(f"设备错误: {ecu_id} -> {error_code}: {error_message}")
            
            self._stats["errors_occurred"] += 1
            
            # 记录错误日志
            error_data = {
                "ecu_id": ecu_id,
                "error_code": error_code,
                "error_message": error_message,
                "context": data.get("context", {}),
                "timestamp": datetime.now().isoformat()
            }
            
            # 保存错误记录
            ecu = self._registered_devices.get(ecu_id)
            if ecu and ecu.db_client:
                try:
                    await ecu.db_client.save_event(ecu_id, "device_error", error_data)
                except Exception as e:
                    logger.error(f"保存错误记录失败: {e}")
            
        except Exception as e:
            logger.error(f"处理错误失败: {e}")
    
    # =============== 心跳管理 ===============
    
    async def _start_heartbeat_for_device(self, ecu_id: str):
        """为设备启动心跳任务"""
        try:
            ecu = self._registered_devices.get(ecu_id)
            if not ecu:
                return
            
            interval = self._heartbeat_intervals.get(ecu_id, 30)
            
            while ecu_id in self._registered_devices:
                await asyncio.sleep(interval)
                
                if ecu_id in self._device_connections:
                    # 发送心跳
                    heartbeat_data = {
                        "ecu_id": ecu_id,
                        "timestamp": datetime.now().isoformat(),
                        "uptime": (datetime.now() - ecu._stats["uptime_start"]).total_seconds(),
                        "status": ecu.status.value
                    }
                    
                    await self._message_queue.put({
                        "type": "heartbeat",
                        "ecu_id": ecu_id,
                        "data": heartbeat_data
                    })
                    
                    # 模拟网络延迟
                    await asyncio.sleep(random.uniform(0.05, 0.2))
                    
        except asyncio.CancelledError:
            logger.debug(f"心跳任务取消: {ecu_id}")
        except Exception as e:
            logger.error(f"心跳任务异常: {ecu_id} -> {e}")
    
    async def update_heartbeat_interval(self, ecu_id: str, interval: int) -> bool:
        """更新心跳间隔"""
        try:
            if ecu_id not in self._registered_devices:
                return False
            
            self._heartbeat_intervals[ecu_id] = interval
            
            # 重启心跳任务
            if ecu_id in self._heartbeat_tasks:
                self._heartbeat_tasks[ecu_id].cancel()
                self._heartbeat_tasks[ecu_id] = asyncio.create_task(
                    self._start_heartbeat_for_device(ecu_id)
                )
            
            logger.info(f"更新心跳间隔: {ecu_id} -> {interval}s")
            return True
            
        except Exception as e:
            logger.error(f"更新心跳间隔失败: {e}")
            return False
    
    # =============== 设备模拟 ===============
    
    async def simulate_device_connection(self, ecu_id: str, duration: int = 300):
        """模拟设备连接"""
        try:
            if ecu_id not in self._registered_devices:
                logger.error(f"无法模拟未注册的设备: {ecu_id}")
                return False
            
            # 连接设备
            connection_id = await self.connect_device(ecu_id)
            if not connection_id:
                return False
            
            logger.info(f"开始模拟设备连接: {ecu_id} ({duration}s)")
            
            # 模拟期间发送状态更新
            ecu = self._registered_devices[ecu_id]
            start_time = datetime.now()
            
            while (datetime.now() - start_time).total_seconds() < duration:
                if ecu.ecu_id not in self._device_connections:
                    break
                
                # 发送状态更新
                status_update = {
                    "type": "status_update",
                    "ecu_id": ecu_id,
                    "data": ecu.get_status_dict()
                }
                
                await self._message_queue.put(status_update)
                
                # 随机发送命令（模拟）
                if random.random() < 0.1:  # 10%概率
                    await self._simulate_random_command(ecu_id)
                
                # 等待一段时间
                await asyncio.sleep(random.uniform(5, 15))
            
            # 断开连接
            await self.disconnect_device(ecu_id)
            
            logger.info(f"设备模拟完成: {ecu_id}")
            return True
            
        except Exception as e:
            logger.error(f"模拟设备连接失败: {e}")
            return False
    
    async def _simulate_random_command(self, ecu_id: str):
        """模拟随机命令"""
        try:
            ecu = self._registered_devices.get(ecu_id)
            if not ecu:
                return
            
            # 根据设备类型选择命令
            if ecu.device_type == DeviceTypes.SHARED_BIKE:
                commands = [
                    MessageTypes.GET_STATUS,
                    MessageTypes.LOCK,
                    MessageTypes.UNLOCK
                ]
            elif ecu.device_type == DeviceTypes.ACCESS_CONTROL:
                commands = [
                    MessageTypes.GET_STATUS,
                    MessageTypes.LOCK,
                    MessageTypes.UNLOCK
                ]
            else:
                commands = [MessageTypes.GET_STATUS]
            
            command = random.choice(commands)
            
            # 构建命令数据
            command_data = {
                "method": command,
                "params": {
                    "ecu_id": ecu_id,
                    "timestamp": datetime.now().isoformat()
                },
                "request_id": f"sim_{uuid.uuid4().hex[:8]}",
                "timeout": 5
            }
            
            # 发送命令
            await self.send_command(ecu_id, command_data)
            
            logger.debug(f"模拟命令发送: {ecu_id} -> {command}")
            
        except Exception as e:
            logger.error(f"模拟随机命令失败: {e}")
    
    # =============== 统计和监控 ===============
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = (datetime.now() - self._stats["start_time"]).total_seconds()
        
        return {
            "uptime_seconds": uptime,
            "devices_registered": self._stats["devices_registered"],
            "connections_active": self._stats["connections_active"],
            "messages_sent": self._stats["messages_sent"],
            "messages_received": self._stats["messages_received"],
            "commands_executed": self._stats["commands_executed"],
            "errors_occurred": self._stats["errors_occurred"],
            "message_queue_size": self._message_queue.qsize(),
            "response_handlers": len(self._response_handlers),
            "heartbeat_tasks": len(self._heartbeat_tasks),
            "last_updated": datetime.now().isoformat()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            # 检查消息处理器
            processing_ok = not self._processing_task.done()
            
            # 检查队列状态
            queue_ok = self._message_queue.qsize() < 500
            
            # 检查连接
            connections_ok = True
            for ecu_id, connection in self._device_connections.items():
                if not connection.connected:
                    connections_ok = False
                    break
            
            return {
                "status": "healthy" if all([processing_ok, queue_ok, connections_ok]) else "degraded",
                "components": {
                    "message_processor": "ok" if processing_ok else "failed",
                    "message_queue": "ok" if queue_ok else "congested",
                    "connections": "ok" if connections_ok else "issues"
                },
                "details": {
                    "processing_task_running": processing_ok,
                    "queue_size": self._message_queue.qsize(),
                    "active_connections": len([c for c in self._device_connections.values() if c.connected]),
                    "total_connections": len(self._device_connections)
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def reset_statistics(self):
        """重置统计信息"""
        self._stats.update({
            "messages_sent": 0,
            "messages_received": 0,
            "commands_executed": 0,
            "errors_occurred": 0
        })
        logger.info("统计信息已重置")
    
    # =============== 生命周期管理 ===============
    
    async def start(self):
        """启动Mock管理器"""
        # 已经通过__init__启动
        logger.info("Mock设备管理器已启动")
    
    async def stop(self):
        """停止Mock管理器"""
        try:
            # 停止消息处理器
            if self._processing_task:
                self._processing_task.cancel()
                try:
                    await self._processing_task
                except asyncio.CancelledError:
                    pass
            
            # 停止所有心跳任务
            for ecu_id, task in self._heartbeat_tasks.items():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # 断开所有连接
            for ecu_id in list(self._device_connections.keys()):
                await self.disconnect_device(ecu_id)
            
            # 停止所有设备
            for ecu in self._registered_devices.values():
                await ecu.stop()
            
            logger.info("Mock设备管理器已停止")
            
        except Exception as e:
            logger.error(f"停止Mock管理器失败: {e}")
    
    def __del__(self):
        """析构函数"""
        try:
            if self._processing_task and not self._processing_task.done():
                self._processing_task.cancel()
        except:
            pass


# =============== 使用示例和工厂函数 ===============

def create_mock_device_manager() -> MockDeviceManager:
    """创建Mock设备管理器实例"""
    return MockDeviceManager()


async def setup_mock_environment(db_url: str = None) -> Dict[str, Any]:
    """设置Mock环境（用于测试和演示）"""
    try:
        logger.info("开始设置Mock环境...")
        
        # 创建Mock设备管理器
        mock_manager = create_mock_device_manager()
        
        # 创建DatabaseClient（如果提供了数据库URL）
        db_client = None
        if db_url:
            from ..database.client import DatabaseClient
            db_client = DatabaseClient(db_url)
            await db_client.initialize()
            logger.info("数据库客户端初始化完成")
        
        # 创建示例设备
        devices = []
        
        # 共享单车设备
        bike_config = ECUConfig(
            ecu_id="bike_001",
            device_type=DeviceTypes.SHARED_BIKE,
            firmware_version="2.1.0",
            heartbeat_interval=20
        )
        
        from ..devices.shared_bike import SharedBikeECU
        bike_ecu = SharedBikeECU(bike_config, db_client)
        await mock_manager.register_ecu("bike_001", bike_ecu)
        devices.append({"ecu_id": "bike_001", "type": "shared_bike"})
        
        # 门禁设备
        door_config = ECUConfig(
            ecu_id="door_001",
            device_type=DeviceTypes.ACCESS_CONTROL,
            firmware_version="1.5.0",
            heartbeat_interval=15
        )
        
        from ..devices.door_access import DoorAccessECU
        door_ecu = DoorAccessECU(door_config, db_client)
        await mock_manager.register_ecu("door_001", door_ecu)
        devices.append({"ecu_id": "door_001", "type": "access_control"})
        
        # 自动连接设备
        await mock_manager.connect_device("bike_001")
        await mock_manager.connect_device("door_001")
        
        logger.info(f"Mock环境设置完成，创建了 {len(devices)} 个设备")
        
        return {
            "mock_manager": mock_manager,
            "db_client": db_client,
            "devices": devices,
            "status": "ready"
        }
        
    except Exception as e:
        logger.error(f"设置Mock环境失败: {e}")
        raise


if __name__ == "__main__":
    """测试Mock管理器"""
    import asyncio
    
    async def test_mock_manager():
        print("🧪 测试Mock设备管理器...")
        
        # 创建Mock管理器
        mock_manager = MockDeviceManager()
        
        # 测试设备注册
        config = ECUConfig(
            ecu_id="test_ecu_001",
            device_type=DeviceTypes.SHARED_BIKE,
            firmware_version="1.0.0"
        )
        
        bike_ecu = SharedBikeECU(config)
        registered = await mock_manager.register_ecu("test_ecu_001", bike_ecu)
        print(f"✅ 设备注册: {registered}")
        
        # 测试设备连接
        connection_id = await mock_manager.connect_device("test_ecu_001")
        print(f"✅ 设备连接: {connection_id}")
        
        # 测试获取连接设备
        connected_devices = await mock_manager.get_connected_devices()
        print(f"✅ 已连接设备: {len(connected_devices)}")
        
        # 测试发送命令
        command_data = {
            "method": MessageTypes.GET_STATUS,
            "params": {"detailed": True},
            "request_id": "test_001"
        }
        
        result = await mock_manager.send_command("test_ecu_001", command_data)
        print(f"✅ 发送命令结果: {result.get('success')}")
        
        # 测试统计信息
        stats = await mock_manager.get_statistics()
        print(f"✅ 统计信息: {stats}")
        
        # 测试健康检查
        health = await mock_manager.health_check()
        print(f"✅ 健康检查: {health['status']}")
        
        # 清理
        await mock_manager.stop()
        print("🎉 Mock管理器测试完成")
    
    asyncio.run(test_mock_manager())