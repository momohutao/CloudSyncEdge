"""
设备管理器接口 - 定义与南向接口的交互规范
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable, Awaitable
from datetime import datetime

from protocol.jsonrpc import JSONRPCRequest, JSONRPCResponse

logger = logging.getLogger(__name__)


class DeviceManagerInterface(ABC):
    """设备管理器接口 - 提供给ECU库的南向接口"""
    
    @abstractmethod
    async def register_ecu(self, ecu_id: str, ws_connection) -> bool:
        """
        注册ECU设备连接
        
        Args:
            ecu_id: 设备ID
            ws_connection: WebSocket连接对象
            
        Returns:
            是否注册成功
        """
        pass
    
    @abstractmethod
    async def unregister_ecu(self, ecu_id: str) -> bool:
        """
        注销ECU设备连接
        
        Args:
            ecu_id: 设备ID
            
        Returns:
            是否注销成功
        """
        pass
    
    @abstractmethod
    async def send_to_cloud(self, ecu_id: str, message: Dict) -> bool:
        """
        发送消息到云端
        
        Args:
            ecu_id: 设备ID
            message: 消息内容
            
        Returns:
            是否发送成功
        """
        pass
    
    @abstractmethod
    async def broadcast_to_cloud(self, messages: List[Dict]) -> bool:
        """
        批量发送消息到云端
        
        Args:
            messages: 消息列表
            
        Returns:
            是否发送成功
        """
        pass
    
    @abstractmethod
    async def send_command_to_device(self, ecu_id: str, command: Dict) -> Dict:
        """
        发送命令到设备
        
        Args:
            ecu_id: 设备ID
            command: 命令数据
            
        Returns:
            命令执行结果
        """
        pass
    
    @abstractmethod
    async def get_device_connection_status(self, ecu_id: str) -> Optional[Dict]:
        """
        获取设备连接状态
        
        Args:
            ecu_id: 设备ID
            
        Returns:
            连接状态信息
        """
        pass
    
    @abstractmethod
    async def list_connected_devices(self) -> List[Dict]:
        """
        列出所有已连接的设备
        
        Returns:
            已连接设备列表
        """
        pass
    
    @abstractmethod
    async def subscribe_to_device_events(self, ecu_id: str, 
                                        callback: Callable[[Dict], Awaitable[None]]) -> bool:
        """
        订阅设备事件
        
        Args:
            ecu_id: 设备ID
            callback: 事件回调函数
            
        Returns:
            是否订阅成功
        """
        pass
    
    @abstractmethod
    async def unsubscribe_from_device_events(self, ecu_id: str) -> bool:
        """
        取消订阅设备事件
        
        Args:
            ecu_id: 设备ID
            
        Returns:
            是否取消成功
        """
        pass


class SouthboundInterfaceProxy:
    """南向接口代理 - 用于与成员B的南向接口通信"""
    
    def __init__(self, interface: DeviceManagerInterface):
        """
        初始化南向接口代理
        
        Args:
            interface: 南向接口实例
        """
        self.interface = interface
        self._event_subscribers = {}
        
        logger.info("南向接口代理初始化完成")
    
    async def register_device(self, ecu_id: str, connection_info: Dict) -> bool:
        """
        注册设备
        
        Args:
            ecu_id: 设备ID
            connection_info: 连接信息
            
        Returns:
            是否注册成功
        """
        try:
            # 模拟WebSocket连接
            class MockConnection:
                def __init__(self, info):
                    self.info = info
                    self.id = info.get("connection_id", f"conn_{ecu_id}")
                
                async def send(self, message):
                    logger.debug(f"模拟发送消息到 {ecu_id}: {message[:100]}...")
                    return True
            
            ws_connection = MockConnection(connection_info)
            
            # 注册设备
            success = await self.interface.register_ecu(ecu_id, ws_connection)
            
            if success:
                logger.info(f"设备注册成功: {ecu_id}")
            else:
                logger.error(f"设备注册失败: {ecu_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"注册设备失败: {ecu_id}: {e}")
            return False
    
    async def unregister_device(self, ecu_id: str) -> bool:
        """
        注销设备
        
        Args:
            ecu_id: 设备ID
            
        Returns:
            是否注销成功
        """
        try:
            success = await self.interface.unregister_ecu(ecu_id)
            
            if success:
                logger.info(f"设备注销成功: {ecu_id}")
            else:
                logger.warning(f"设备注销失败或设备未注册: {ecu_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"注销设备失败: {ecu_id}: {e}")
            return False
    
    async def send_device_status(self, ecu_id: str, status_data: Dict) -> bool:
        """
        发送设备状态到云端
        
        Args:
            ecu_id: 设备ID
            status_data: 状态数据
            
        Returns:
            是否发送成功
        """
        try:
            message = {
                "type": "device_status",
                "ecu_id": ecu_id,
                "data": status_data,
                "timestamp": datetime.now().isoformat(),
                "source": "ecu_library"
            }
            
            success = await self.interface.send_to_cloud(ecu_id, message)
            
            if success:
                logger.debug(f"设备状态发送成功: {ecu_id}")
            else:
                logger.warning(f"设备状态发送失败: {ecu_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"发送设备状态失败: {ecu_id}: {e}")
            return False
    
    async def send_device_event(self, ecu_id: str, event_type: str, event_data: Dict) -> bool:
        """
        发送设备事件到云端
        
        Args:
            ecu_id: 设备ID
            event_type: 事件类型
            event_data: 事件数据
            
        Returns:
            是否发送成功
        """
        try:
            message = {
                "type": "device_event",
                "ecu_id": ecu_id,
                "event_type": event_type,
                "data": event_data,
                "timestamp": datetime.now().isoformat(),
                "source": "ecu_library"
            }
            
            success = await self.interface.send_to_cloud(ecu_id, message)
            
            if success:
                logger.info(f"设备事件发送成功: {ecu_id} -> {event_type}")
            else:
                logger.warning(f"设备事件发送失败: {ecu_id} -> {event_type}")
            
            return success
            
        except Exception as e:
            logger.error(f"发送设备事件失败: {ecu_id}: {e}")
            return False
    
    async def send_device_alert(self, ecu_id: str, alert_data: Dict) -> bool:
        """
        发送设备告警到云端
        
        Args:
            ecu_id: 设备ID
            alert_data: 告警数据
            
        Returns:
            是否发送成功
        """
        try:
            message = {
                "type": "device_alert",
                "ecu_id": ecu_id,
                "severity": alert_data.get("severity", "warning"),
                "data": alert_data,
                "timestamp": datetime.now().isoformat(),
                "source": "ecu_library"
            }
            
            success = await self.interface.send_to_cloud(ecu_id, message)
            
            if success:
                logger.warning(f"设备告警发送成功: {ecu_id} -> {alert_data.get('severity')}")
            else:
                logger.error(f"设备告警发送失败: {ecu_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"发送设备告警失败: {ecu_id}: {e}")
            return False
    
    async def execute_device_command(self, ecu_id: str, command: str, params: Dict) -> Dict:
        """
        执行设备命令
        
        Args:
            ecu_id: 设备ID
            command: 命令类型
            params: 命令参数
            
        Returns:
            命令执行结果
        """
        try:
            command_data = {
                "method": command,
                "params": params,
                "timestamp": datetime.now().isoformat(),
                "source": "ecu_library"
            }
            
            result = await self.interface.send_command_to_device(ecu_id, command_data)
            
            logger.info(f"设备命令执行完成: {ecu_id} -> {command}")
            
            return result
            
        except Exception as e:
            logger.error(f"执行设备命令失败: {ecu_id} -> {command}: {e}")
            
            return {
                "success": False,
                "error_code": -1,
                "error_message": f"Command execution failed: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    async def batch_send_status(self, status_list: List[Dict]) -> bool:
        """
        批量发送状态
        
        Args:
            status_list: 状态列表
            
        Returns:
            是否发送成功
        """
        try:
            messages = []
            
            for status in status_list:
                ecu_id = status.get("ecu_id")
                status_data = status.get("status_data", {})
                
                if ecu_id and status_data:
                    message = {
                        "type": "device_status",
                        "ecu_id": ecu_id,
                        "data": status_data,
                        "timestamp": datetime.now().isoformat(),
                        "source": "ecu_library"
                    }
                    messages.append(message)
            
            if messages:
                success = await self.interface.broadcast_to_cloud(messages)
                
                if success:
                    logger.info(f"批量状态发送成功: {len(messages)} 条")
                else:
                    logger.warning(f"批量状态发送失败: {len(messages)} 条")
                
                return success
            
            return True
            
        except Exception as e:
            logger.error(f"批量发送状态失败: {e}")
            return False
    
    async def get_connection_info(self, ecu_id: str) -> Optional[Dict]:
        """
        获取连接信息
        
        Args:
            ecu_id: 设备ID
            
        Returns:
            连接信息
        """
        try:
            status = await self.interface.get_device_connection_status(ecu_id)
            
            if status:
                return {
                    "ecu_id": ecu_id,
                    "connected": status.get("connected", False),
                    "connection_id": status.get("connection_id"),
                    "last_activity": status.get("last_activity"),
                    "message_count": status.get("message_count", 0),
                    "status": "online" if status.get("connected") else "offline"
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"获取连接信息失败: {ecu_id}: {e}")
            return None
    
    async def list_all_connections(self) -> List[Dict]:
        """
        列出所有连接
        
        Returns:
            连接列表
        """
        try:
            devices = await self.interface.list_connected_devices()
            
            connections = []
            for device in devices:
                connection_info = {
                    "ecu_id": device.get("ecu_id"),
                    "device_type": device.get("device_type"),
                    "connected": True,
                    "connection_id": device.get("connection_id"),
                    "connected_at": device.get("connected_at"),
                    "last_activity": device.get("last_activity"),
                    "status": device.get("status", "online")
                }
                connections.append(connection_info)
            
            return connections
            
        except Exception as e:
            logger.error(f"列出所有连接失败: {e}")
            return []
    
    async def subscribe_device_updates(self, ecu_id: str, 
                                       callback: Callable[[Dict], Awaitable[None]]) -> bool:
        """
        订阅设备更新
        
        Args:
            ecu_id: 设备ID
            callback: 更新回调函数
            
        Returns:
            是否订阅成功
        """
        try:
            if ecu_id not in self._event_subscribers:
                self._event_subscribers[ecu_id] = []
            
            self._event_subscribers[ecu_id].append(callback)
            
            # 注册到南向接口
            success = await self.interface.subscribe_to_device_events(ecu_id, self._forward_event)
            
            if success:
                logger.info(f"设备更新订阅成功: {ecu_id}")
            else:
                logger.warning(f"设备更新订阅失败: {ecu_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"订阅设备更新失败: {ecu_id}: {e}")
            return False
    
    async def unsubscribe_device_updates(self, ecu_id: str) -> bool:
        """
        取消订阅设备更新
        
        Args:
            ecu_id: 设备ID
            
        Returns:
            是否取消成功
        """
        try:
            if ecu_id in self._event_subscribers:
                del self._event_subscribers[ecu_id]
            
            success = await self.interface.unsubscribe_from_device_events(ecu_id)
            
            if success:
                logger.info(f"设备更新取消订阅成功: {ecu_id}")
            else:
                logger.warning(f"设备更新取消订阅失败: {ecu_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"取消订阅设备更新失败: {ecu_id}: {e}")
            return False
    
    async def _forward_event(self, event_data: Dict):
        """转发事件到所有订阅者"""
        try:
            ecu_id = event_data.get("ecu_id")
            if ecu_id in self._event_subscribers:
                for callback in self._event_subscribers[ecu_id]:
                    try:
                        await callback(event_data)
                    except Exception as e:
                        logger.error(f"事件回调执行失败: {e}")
                        
        except Exception as e:
            logger.error(f"转发事件失败: {e}")
    
    async def health_check(self) -> Dict:
        """健康检查"""
        try:
            # 获取连接设备列表
            connections = await self.list_all_connections()
            
            # 统计信息
            total_devices = len(connections)
            online_devices = len([c for c in connections if c.get("connected")])
            
            return {
                "status": "healthy" if total_devices > 0 else "degraded",
                "timestamp": datetime.now().isoformat(),
                "statistics": {
                    "total_devices": total_devices,
                    "online_devices": online_devices,
                    "offline_devices": total_devices - online_devices,
                    "online_rate": (online_devices / total_devices * 100) if total_devices > 0 else 0,
                    "event_subscribers": len(self._event_subscribers)
                },
                "connections": connections[:10]  # 只返回前10个连接
            }
            
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# =============== 适配器模式 ===============

class MockToRealAdapter(DeviceManagerInterface):
    """Mock到真实接口的适配器"""
    
    def __init__(self, mock_manager, real_interface=None):
        """
        初始化适配器
        
        Args:
            mock_manager: Mock设备管理器
            real_interface: 真实南向接口（可选）
        """
        self.mock_manager = mock_manager
        self.real_interface = real_interface
        self.use_real_interface = real_interface is not None
        
        logger.info(f"接口适配器初始化，使用{'真实' if self.use_real_interface else 'Mock'}接口")
    
    async def register_ecu(self, ecu_id: str, ws_connection) -> bool:
        """注册ECU设备连接"""
        if self.use_real_interface and self.real_interface:
            return await self.real_interface.register_ecu(ecu_id, ws_connection)
        else:
            # 使用Mock管理器
            from ..mock.mock_manager import MockWebSocketConnection
            mock_conn = MockWebSocketConnection(f"conn_{ecu_id}")
            return await self.mock_manager.register_ecu(ecu_id, None)  # 简化处理
    
    async def unregister_ecu(self, ecu_id: str) -> bool:
        """注销ECU设备连接"""
        if self.use_real_interface and self.real_interface:
            return await self.real_interface.unregister_ecu(ecu_id)
        else:
            return await self.mock_manager.unregister_ecu(ecu_id)
    
    async def send_to_cloud(self, ecu_id: str, message: Dict) -> bool:
        """发送消息到云端"""
        if self.use_real_interface and self.real_interface:
            return await self.real_interface.send_to_cloud(ecu_id, message)
        else:
            # Mock实现：记录日志
            logger.info(f"[Mock] 发送消息到云端: {ecu_id} -> {message.get('type')}")
            return True
    
    async def broadcast_to_cloud(self, messages: List[Dict]) -> bool:
        """批量发送消息到云端"""
        if self.use_real_interface and self.real_interface:
            return await self.real_interface.broadcast_to_cloud(messages)
        else:
            # Mock实现
            for message in messages:
                ecu_id = message.get("ecu_id")
                logger.debug(f"[Mock] 批量发送消息: {ecu_id}")
            return True
    
    async def send_command_to_device(self, ecu_id: str, command: Dict) -> Dict:
        """发送命令到设备"""
        if self.use_real_interface and self.real_interface:
            return await self.real_interface.send_command_to_device(ecu_id, command)
        else:
            # 使用Mock管理器发送命令
            return await self.mock_manager.send_command(ecu_id, command)
    
    async def get_device_connection_status(self, ecu_id: str) -> Optional[Dict]:
        """获取设备连接状态"""
        if self.use_real_interface and self.real_interface:
            return await self.real_interface.get_device_connection_status(ecu_id)
        else:
            return await self.mock_manager.get_connection_status(ecu_id)
    
    async def list_connected_devices(self) -> List[Dict]:
        """列出所有已连接的设备"""
        if self.use_real_interface and self.real_interface:
            return await self.real_interface.list_connected_devices()
        else:
            return await self.mock_manager.get_connected_devices()
    
    async def subscribe_to_device_events(self, ecu_id: str, 
                                        callback: Callable[[Dict], Awaitable[None]]) -> bool:
        """订阅设备事件"""
        if self.use_real_interface and self.real_interface:
            return await self.real_interface.subscribe_to_device_events(ecu_id, callback)
        else:
            # Mock实现：直接调用回调
            logger.info(f"[Mock] 订阅设备事件: {ecu_id}")
            return True
    
    async def unsubscribe_from_device_events(self, ecu_id: str) -> bool:
        """取消订阅设备事件"""
        if self.use_real_interface and self.real_interface:
            return await self.real_interface.unsubscribe_from_device_events(ecu_id)
        else:
            logger.info(f"[Mock] 取消订阅设备事件: {ecu_id}")
            return True


# =============== 工厂函数 ===============

def create_ecu_interface(device_registry, db_client=None) -> ECUInterface:
    """
    创建ECU接口实例
    
    Args:
        device_registry: 设备注册表
        db_client: 数据库客户端
        
    Returns:
        ECU接口实例
    """
    return DefaultECUInterface(device_registry, db_client)


def create_southbound_proxy(interface: DeviceManagerInterface) -> SouthboundInterfaceProxy:
    """
    创建南向接口代理
    
    Args:
        interface: 南向接口实例
        
    Returns:
        南向接口代理
    """
    return SouthboundInterfaceProxy(interface)


def create_adapter_interface(mock_manager, real_interface=None) -> DeviceManagerInterface:
    """
    创建适配器接口
    
    Args:
        mock_manager: Mock设备管理器
        real_interface: 真实南向接口
        
    Returns:
        适配器接口
    """
    return MockToRealAdapter(mock_manager, real_interface)


# =============== 使用示例 ===============

async def demo_ecu_interface():
    """演示ECU接口使用"""
    print("🚀 演示ECU接口使用...")
    
    try:
        # 创建设备注册表
        from ..devices.device_registry import DeviceRegistry
        registry = DeviceRegistry()
        
        # 创建数据库客户端
        from ..database.client import DatabaseClient
        db_client = DatabaseClient("sqlite+aiosqlite:///./data/ecu.db")
        await db_client.initialize()
        
        # 创建ECU接口
        ecu_interface = create_ecu_interface(registry, db_client)
        
        # 注册设备
        device_data = {
            "ecu_id": "demo_bike_001",
            "device_type": "shared_bike",
            "firmware_version": "2.0.0"
        }
        
        result = await ecu_interface.register_ecu(device_data)
        print(f"✅ 设备注册: {result.get('success')}")
        
        # 获取设备状态
        status = await ecu_interface.get_ecu_status("demo_bike_001")
        print(f"✅ 设备状态: {status.get('success')}")
        
        # 执行命令
        command_result = await ecu_interface.execute_command(
            "demo_bike_001",
            "get_status",
            {"detailed": True}
        )
        print(f"✅ 执行命令: {command_result.get('success')}")
        
        # 获取所有设备
        all_devices = await ecu_interface.get_all_ecus()
        print(f"✅ 所有设备: {len(all_devices)}")
        
        # 健康检查
        health = await ecu_interface.health_check()
        print(f"✅ 健康检查: {health.get('status')}")
        
        # 清理
        await ecu_interface.unregister_ecu("demo_bike_001")
        await db_client.close()
        
        print("🎉 ECU接口演示完成")
        
    except Exception as e:
        print(f"❌ 演示失败: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_ecu_interface())