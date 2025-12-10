# southbound/interface.py
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod


class SouthboundInterface(ABC):
    """南向通信接口（供成员C调用）"""

    @abstractmethod
    async def send_command(self, ecu_id: str, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """发送命令到设备"""
        pass

    @abstractmethod
    def is_device_online(self, ecu_id: str) -> bool:
        """检查设备是否在线"""
        pass

    @abstractmethod
    async def get_device_logs(self, ecu_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取设备日志"""
        pass

    @abstractmethod
    async def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        pass