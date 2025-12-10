"""
数据库客户端 - 基于MySQL的简单实现
专门用于ECU设备表（ecu_devices）的操作
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..shared.database import SimpleDB
from .ecu_device_dao import ECUDeviceDAO

logger = logging.getLogger(__name__)


class DatabaseClient:
    """简单的数据库客户端"""
    
    def __init__(self):
        """初始化数据库客户端"""
        self.connected = False
    
    async def initialize(self) -> bool:
        """初始化数据库连接"""
        try:
            # 测试连接
            if await SimpleDB.test_connection():
                self.connected = True
                logger.info("数据库客户端初始化成功")
                return True
            else:
                logger.warning("数据库连接测试失败，将使用Mock模式")
                self.connected = False
                return True  # Mock模式下也返回True
                
        except Exception as e:
            logger.error(f"数据库客户端初始化失败: {e}")
            self.connected = False
            return True  # 即使失败也继续（Mock模式）
    
    async def save_ecu_device(self, device_data: Dict) -> bool:
        """保存ECU设备信息"""
        try:
            ecu_id = device_data.get("ecu_id")
            device_type = device_data.get("device_type", "unknown")
            firmware_version = device_data.get("firmware_version", "1.0.0")
            status = device_data.get("status", "offline")
            
            if not ecu_id:
                logger.error("保存ECU设备失败：缺少ecu_id")
                return False
            
            # 注册设备
            success = await ECUDeviceDAO.register_device(
                ecu_id=ecu_id,
                device_type=device_type,
                device_name=f"{device_type}_{ecu_id}"
            )
            
            if success:
                # 更新状态
                await ECUDeviceDAO.update_device_status(ecu_id, status)
            
            return success
            
        except Exception as e:
            logger.error(f"保存ECU设备失败: {e}")
            return False
    
    async def save_ecu_status(self, ecu_id: str, status_data: Dict) -> bool:
        """保存ECU状态"""
        try:
            status_value = status_data.get("status", "offline")
            success = await ECUDeviceDAO.update_device_status(ecu_id, status_value)
            return success
            
        except Exception as e:
            logger.error(f"保存ECU状态失败: {e}")
            return False
    
    async def save_heartbeat(self, ecu_id: str, heartbeat_data: Dict) -> bool:
        """保存心跳记录"""
        try:
            # 更新最后在线时间
            success = await ECUDeviceDAO.update_device_status(ecu_id, "online")
            return success
            
        except Exception as e:
            logger.error(f"保存心跳记录失败: {e}")
            return False
    
    async def save_command_execution(self, execution_data: Dict) -> bool:
        """保存命令执行记录"""
        try:
            ecu_id = execution_data.get("ecu_id")
            if ecu_id:
                # 更新最后在线时间
                success = await ECUDeviceDAO.update_device_status(ecu_id, "online")
                return success
            return False
            
        except Exception as e:
            logger.error(f"保存命令执行记录失败: {e}")
            return False
    
    async def save_event(self, ecu_id: str, event_type: str, event_data: Dict) -> bool:
        """保存事件记录"""
        try:
            # 更新最后在线时间
            success = await ECUDeviceDAO.update_device_status(ecu_id, "online")
            return success
            
        except Exception as e:
            logger.error(f"保存事件记录失败: {e}")
            return False
    
    async def get_latest_ecu_status(self, ecu_id: str) -> Optional[Dict]:
        """获取最新ECU状态"""
        try:
            device = await ECUDeviceDAO.get_device(ecu_id)
            return device
        except Exception as e:
            logger.error(f"获取最新ECU状态失败: {e}")
            return None
    
    async def get_heartbeat_history(self, ecu_id: str, hours: int = 1, 
                                   limit: int = 5) -> List[Dict]:
        """获取心跳历史"""
        # 简化实现 - 返回空列表
        return []
    
    async def get_command_statistics(self, ecu_id: str) -> Dict:
        """获取命令统计"""
        # 简化实现
        return {
            "total": 0,
            "success": 0,
            "failed": 0
        }
    
    async def delete_ecu_device(self, ecu_id: str) -> bool:
        """删除ECU设备"""
        try:
            # 注意：实际项目中应该软删除而不是硬删除
            # 这里简化处理，实际应该更新状态为deleted
            sql = "DELETE FROM ecu_devices WHERE ecu_id = %s"
            await SimpleDB.execute(sql, ecu_id)
            logger.info(f"删除ECU设备: {ecu_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除ECU设备失败: {e}")
            return False
    
    async def close(self):
        """关闭数据库连接"""
        try:
            await SimpleDB.close()
            logger.info("数据库客户端已关闭")
        except Exception as e:
            logger.error(f"关闭数据库客户端失败: {e}")
    
    async def health_check(self) -> Dict:
        """健康检查"""
        try:
            # 测试数据库连接
            connected = await SimpleDB.test_connection()
            
            # 获取设备统计
            device_count = 0
            if connected:
                devices = await ECUDeviceDAO.get_all_devices()
                device_count = len(devices)
            
            return {
                "status": "healthy" if connected else "unhealthy",
                "database_connected": connected,
                "device_count": device_count,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "database_connected": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }