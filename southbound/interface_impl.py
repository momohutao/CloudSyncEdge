# southbound/interface_impl.py
import sys
import os
from typing import Dict, List, Any

from  .interface import SouthboundInterface
from  ..ecu_lib.interfaces.ecu_interface import ECUInterface
from ..src.protocol.message_types import *
class SouthboundInterfaceImpl(SouthboundInterface):
    def __init__(self,server_instance=None):
        #依赖成员A的接口
        from ..ecu_lib.interfaces.ecu_interface import DefaultECUInterface
        from ..ecu_lib.devices.device_registry import DeviceRegistry
        device_registry = DeviceRegistry()  # 或者从其他地方获取
        self.ecu_interface = DefaultECUInterface(device_registry)
        #WebSocket服务器管理实例
        self.server=server_instance
        #本地设备管理
        self.active_devices={}
        print("南向接口初始化完成")
    async def send_command(self, ecu_id: str, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """发送命令到设备"""
        # 1. 检查设备是否在线
        if ecu_id not in self.active_devices:
            return {
                "success": False,
                "error": f"设备 {ecu_id} 离线",
                "error_code":  ErrorCodes.DEVICE_OFFLINE
            }

        try:
            # 2. 调用成员A的接口执行命令
            result = await self.ecu_interface.execute_command(ecu_id, command, params)
            # 3. 记录日志（南向自己的职责）
            if self.server and hasattr(self.server, 'db_client'):
                await self.server.db_client.log_command(
                    ecu_id=ecu_id,
                    command=command,
                    params=params,
                    result=result
                )
            return result
        except Exception as e:
            return{
                "success":False,
                "error":str(e),
                "error_code":ErrorCodes.COMMAND_TIMEOUT
            }

    def get_connected_devices(self) -> List[str]:
        """获取已连接设备列表"""
        return list(self.active_devices.keys())

    def is_device_online(self, ecu_id: str) -> bool:
        """检查设备是否在线"""
        return ecu_id in self.active_devices

    async def get_device_logs(self, ecu_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取设备日志"""
        if self.server and hasattr(self.server, 'db_client'):#db_client 是「数据库客户端实例」的缩写
            return await self.server.db_client.get_device_logs(ecu_id, limit)
        return []

    async def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if self.server and hasattr(self.server, 'db_client'):
            return await self.server.db_client.get_statistics()
        return {"active_devices": len(self.active_devices)}
