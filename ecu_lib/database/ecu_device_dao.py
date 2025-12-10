"""
ECU设备数据访问对象 - 支持Mock模式
"""
from ..shared.database import SimpleDB
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ECUDeviceDAO:
    """ecu_devices表的数据访问对象"""
    
    @staticmethod
    async def register_device(ecu_id: str, device_type: str = 'bike', 
                            device_name: str = None) -> bool:
        """注册新设备"""
        try:
            if SimpleDB.is_mock_mode():
                logger.info(f"Mock注册设备: {ecu_id} ({device_type})")
            
            await SimpleDB.execute("""
                INSERT INTO ecu_devices 
                (ecu_id, device_type, device_name, status, created_at, last_seen)
                VALUES (%s, %s, %s, 'offline', NOW(), NOW())
                ON DUPLICATE KEY UPDATE 
                device_type = VALUES(device_type),
                device_name = VALUES(device_name)
            """, ecu_id, device_type, device_name or ecu_id)
            return True
        except Exception as e:
            logger.error(f"注册设备失败: {e}")
            return False
    
    @staticmethod
    async def update_device_status(ecu_id: str, status: str, 
                                 ip_address: str = None) -> bool:
        """更新设备状态"""
        try:
            sql = """
                UPDATE ecu_devices 
                SET status = %s, last_seen = NOW()
            """
            params = [status]
            
            if ip_address:
                sql += ", ip_address = %s"
                params.append(ip_address)
            
            sql += " WHERE ecu_id = %s"
            params.append(ecu_id)
            
            await SimpleDB.execute(sql, *params)
            return True
        except Exception as e:
            logger.error(f"更新设备状态失败: {e}")
            return False
    
    @staticmethod
    async def get_device(ecu_id: str) -> dict:
        """获取单个设备信息"""
        try:
            rows = await SimpleDB.execute("""
                SELECT ecu_id, device_type, device_name, status, 
                       ip_address, created_at, last_seen
                FROM ecu_devices
                WHERE ecu_id = %s
            """, ecu_id)
            return rows[0] if rows else None
        except Exception as e:
            logger.error(f"获取设备信息失败: {e}")
            return None
    
    @staticmethod
    async def get_all_devices() -> list:
        """获取所有设备"""
        try:
            return await SimpleDB.execute("""
                SELECT ecu_id, device_type, device_name, status, 
                       ip_address, created_at, last_seen
                FROM ecu_devices
                ORDER BY last_seen DESC
            """)
        except Exception as e:
            logger.error(f"获取所有设备失败: {e}")
            return []
    
    @staticmethod
    def is_mock_mode() -> bool:
        """是否在Mock模式"""
        return SimpleDB.is_mock_mode()