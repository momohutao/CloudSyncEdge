# southbound/interface.py
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod


class SouthboundInterface(ABC):
    """南向通信接口（供成员C调用）"""

    @abstractmethod
    async def send_command(self, ecu_id: str, command: str, params: dict) -> dict:
        """发送命令到设备"""
        pass

    @abstractmethod
    def get_connected_devices(self) -> List[str]:
        """获取已连接设备列表"""
        pass

    @abstractmethod
    def is_device_online(self, ecu_id: str) -> bool:
        """检查设备是否在线"""
        pass