"""
设备注册表 - 管理所有ECU设备实例
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime

from ..core.base_ecu import BaseECU, ECUConfig

logger = logging.getLogger(__name__)


class DeviceRegistry:
    """设备注册表"""
    
    def __init__(self):
        self._devices: Dict[str, BaseECU] = {}
        logger.info("设备注册表初始化")
    
    async def create_device(self, config: ECUConfig, db_client=None) -> Optional[BaseECU]:
        """创建设备"""
        try:
            from ..core.ecu_factory import get_ecu_factory
            
            factory = get_ecu_factory()
            ecu = factory.create_ecu(config, db_client)
            
            if ecu:
                self._devices[config.ecu_id] = ecu
                logger.info(f"设备创建并注册: {config.ecu_id}")
            
            return ecu
            
        except Exception as e:
            logger.error(f"创建设备失败: {e}")
            return None
    
    async def get_device(self, ecu_id: str) -> Optional[BaseECU]:
        """获取设备"""
        return self._devices.get(ecu_id)
    
    async def remove_device(self, ecu_id: str) -> bool:
        """移除设备"""
        if ecu_id in self._devices:
            del self._devices[ecu_id]
            logger.info(f"设备移除: {ecu_id}")
            return True
        return False
    
    async def list_devices(self) -> List[Dict]:
        """列出所有设备"""
        devices_info = []
        
        for ecu_id, ecu in self._devices.items():
            devices_info.append({
                "ecu_id": ecu_id,
                "device_type": ecu.device_type,
                "status": ecu.status.value,
                "firmware_version": ecu.firmware_version,
                "connected": ecu.status.value == "online"
            })
        
        return devices_info
    
    async def count_devices(self) -> int:
        """设备计数"""
        return len(self._devices)
    
    def get_all_devices(self) -> Dict[str, BaseECU]:
        """获取所有设备实例"""
        return self._devices.copy()


# 全局设备注册表实例
_global_registry = None

def get_device_registry() -> DeviceRegistry:
    """获取全局设备注册表实例"""
    global _global_registry
    if _global_registry is None:
        _global_registry = DeviceRegistry()
    return _global_registry