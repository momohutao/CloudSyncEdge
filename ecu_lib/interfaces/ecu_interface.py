"""
ECUInterface类 - 简化版本
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod

from ..core.base_ecu import BaseECU, ECUConfig, ECUStatus
from ..devices.device_registry import DeviceRegistry
from ..database.client import DatabaseClient

logger = logging.getLogger(__name__)


class ECUInterface(ABC):
    """ECU接口基类"""
    
    @abstractmethod
    async def execute_command(self, ecu_id: str, command: str, params: Dict) -> Dict:
        """执行ECU命令"""
        pass
    
    @abstractmethod
    async def get_ecu_status(self, ecu_id: str) -> Dict:
        """获取ECU状态"""
        pass
    
    @abstractmethod
    async def get_all_ecus(self) -> List[Dict]:
        """获取所有ECU设备"""
        pass
    
    @abstractmethod
    async def register_ecu(self, ecu_data: Dict) -> Dict:
        """注册ECU设备"""
        pass
    
    @abstractmethod
    async def unregister_ecu(self, ecu_id: str) -> bool:
        """注销ECU设备"""
        pass
    
    @abstractmethod
    async def start_ecu(self, ecu_id: str) -> bool:
        """启动ECU设备"""
        pass
    
    @abstractmethod
    async def stop_ecu(self, ecu_id: str) -> bool:
        """停止ECU设备"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict:
        """健康检查"""
        pass


class DefaultECUInterface(ECUInterface):
    """默认ECU接口实现"""
    
    def __init__(self, device_registry: DeviceRegistry, db_client: Optional[DatabaseClient] = None):
        self.device_registry = device_registry
        self.db_client = db_client
        logger.info("ECU接口初始化完成")
    
    async def execute_command(self, ecu_id: str, command: str, params: Dict) -> Dict:
        """执行ECU命令"""
        try:
            logger.info(f"执行命令: {ecu_id} -> {command}")
            
            # 获取设备
            ecu = await self.device_registry.get_device(ecu_id)
            if not ecu:
                return {
                    "success": False,
                    "error_code": 1001,
                    "error_message": f"Device {ecu_id} not found"
                }
            
            # 执行命令
            result = await ecu.execute_command(command, params)
            return result
            
        except Exception as e:
            logger.error(f"执行命令失败: {e}")
            return {
                "success": False,
                "error_code": 1004,
                "error_message": f"Command execution failed: {str(e)}"
            }
    
    async def get_ecu_status(self, ecu_id: str) -> Dict:
        """获取ECU状态"""
        try:
            ecu = await self.device_registry.get_device(ecu_id)
            if not ecu:
                return {
                    "success": False,
                    "error_code": 1001,
                    "error_message": f"Device {ecu_id} not found"
                }
            
            status = ecu.get_status_dict()
            
            return {
                "success": True,
                "ecu_id": ecu_id,
                "status": status,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取设备状态失败: {e}")
            return {
                "success": False,
                "error_code": 1004,
                "error_message": f"Failed to get device status: {str(e)}"
            }
    
    async def get_all_ecus(self) -> List[Dict]:
        """获取所有ECU设备"""
        try:
            devices = await self.device_registry.list_devices()
            return devices
        except Exception as e:
            logger.error(f"获取所有设备失败: {e}")
            return []
    
    async def register_ecu(self, ecu_data: Dict) -> Dict:
        """注册ECU设备"""
        try:
            ecu_id = ecu_data.get("ecu_id")
            device_type = ecu_data.get("device_type")
            
            if not ecu_id or not device_type:
                return {
                    "success": False,
                    "error_code": 1005,
                    "error_message": "ecu_id and device_type are required"
                }
            
            # 创建设备配置
            config = ECUConfig(
                ecu_id=ecu_id,
                device_type=device_type,
                firmware_version=ecu_data.get("firmware_version", "1.0.0"),
                heartbeat_interval=ecu_data.get("heartbeat_interval", 30)
            )
            
            # 创建设备实例
            ecu = await self.device_registry.create_device(config, self.db_client)
            if not ecu:
                return {
                    "success": False,
                    "error_code": 1004,
                    "error_message": f"Failed to create device {ecu_id}"
                }
            
            logger.info(f"ECU设备注册成功: {ecu_id} ({device_type})")
            
            return {
                "success": True,
                "ecu_id": ecu_id,
                "device_type": device_type,
                "status": ecu.status.value,
                "message": f"Device {ecu_id} registered successfully"
            }
            
        except Exception as e:
            logger.error(f"注册ECU设备失败: {e}")
            return {
                "success": False,
                "error_code": 1004,
                "error_message": f"Failed to register device: {str(e)}"
            }
    
    async def unregister_ecu(self, ecu_id: str) -> bool:
        """注销ECU设备"""
        try:
            # 停止设备
            await self.stop_ecu(ecu_id)
            
            # 从注册表中移除
            success = await self.device_registry.remove_device(ecu_id)
            
            logger.info(f"ECU设备注销: {ecu_id} - {'成功' if success else '失败'}")
            return success
            
        except Exception as e:
            logger.error(f"注销ECU设备失败: {ecu_id}: {e}")
            return False
    
    async def start_ecu(self, ecu_id: str) -> bool:
        """启动ECU设备"""
        try:
            ecu = await self.device_registry.get_device(ecu_id)
            if not ecu:
                logger.error(f"无法启动不存在的设备: {ecu_id}")
                return False
            
            if ecu.status == ECUStatus.ONLINE:
                return True
            
            await ecu.start()
            logger.info(f"ECU设备启动: {ecu_id}")
            return True
            
        except Exception as e:
            logger.error(f"启动ECU设备失败: {ecu_id}: {e}")
            return False
    
    async def stop_ecu(self, ecu_id: str) -> bool:
        """停止ECU设备"""
        try:
            ecu = await self.device_registry.get_device(ecu_id)
            if not ecu:
                return False
            
            if ecu.status == ECUStatus.OFFLINE:
                return True
            
            await ecu.stop()
            logger.info(f"ECU设备停止: {ecu_id}")
            return True
            
        except Exception as e:
            logger.error(f"停止ECU设备失败: {ecu_id}: {e}")
            return False
    
    async def health_check(self) -> Dict:
        """健康检查"""
        try:
            # 检查设备注册表
            device_count = await self.device_registry.count_devices()
            
            # 检查数据库连接
            db_health = True
            if self.db_client:
                try:
                    db_status = await self.db_client.health_check()
                    db_health = db_status.get("status") == "healthy"
                except Exception as e:
                    logger.warning(f"数据库健康检查失败: {e}")
                    db_health = False
            
            # 检查所有设备状态
            devices = await self.device_registry.list_devices()
            online_count = 0
            device_statuses = []
            
            for device_info in devices:
                ecu_id = device_info["ecu_id"]
                ecu = await self.device_registry.get_device(ecu_id)
                
                if ecu:
                    status_info = {
                        "ecu_id": ecu_id,
                        "status": ecu.status.value,
                        "online": ecu.status == ECUStatus.ONLINE
                    }
                    device_statuses.append(status_info)
                    
                    if ecu.status == ECUStatus.ONLINE:
                        online_count += 1
            
            overall_health = device_count >= 0 and db_health
            
            return {
                "status": "healthy" if overall_health else "degraded",
                "timestamp": datetime.now().isoformat(),
                "components": {
                    "device_registry": "ok",
                    "database": "ok" if db_health else "error"
                },
                "statistics": {
                    "total_devices": device_count,
                    "online_devices": online_count,
                    "offline_devices": device_count - online_count
                }
            }
            
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }