"""
ECU工厂类 - 负责创建和管理ECU设备实例
简化版本
"""
import asyncio
import logging
from typing import Dict, List, Optional, Type
from enum import Enum

from .base_ecu import BaseECU, ECUConfig
from ..devices.shared_bike_ecu import SharedBikeECU  # 修正：使用正确的文件名
from ..devices.door_access import DoorAccessECU
from ..database.client import DatabaseClient

logger = logging.getLogger(__name__)


class DeviceCategory(Enum):
    """设备分类"""
    TRANSPORTATION = "transportation"  # 交通设备
    SECURITY = "security"              # 安防设备
    UTILITY = "utility"                # 公用设备
    INDUSTRIAL = "industrial"          # 工业设备
    CONSUMER = "consumer"              # 消费设备


# 设备类型常量
class DeviceTypes:
    SHARED_BIKE = "shared_bike"
    ACCESS_CONTROL = "door_access"
    SMART_METER = "smart_meter"
    IOT_GATEWAY = "iot_gateway"
    VEHICLE_ECU = "vehicle_ecu"
    SMART_LOCK = "smart_lock"
    ENVIRONMENT_SENSOR = "environment_sensor"


class ECUFactory:
    """ECU工厂 - 负责创建和管理ECU设备实例"""
    
    # 设备类型到设备类的映射
    _device_registry: Dict[str, Type[BaseECU]] = {}
    
    # 设备类型到设备分类的映射
    _device_categories: Dict[str, DeviceCategory] = {}
    
    # 设备配置模板
    _device_config_templates: Dict[str, Dict] = {}
    
    @classmethod
    def initialize(cls):
        """初始化工厂"""
        # 注册内置设备类型
        cls.register_device_type(
            device_type=DeviceTypes.SHARED_BIKE,
            device_class=SharedBikeECU,  # 这里使用正确的类名
            category=DeviceCategory.TRANSPORTATION,
            config_template={
                "heartbeat_interval": 30,
                "command_timeout": 10,
                "reconnect_attempts": 3,
                "max_command_queue": 50,
                "enable_logging": True
            }
        )
        
        cls.register_device_type(
            device_type=DeviceTypes.ACCESS_CONTROL,
            device_class=DoorAccessECU,
            category=DeviceCategory.SECURITY,
            config_template={
                "heartbeat_interval": 20,
                "command_timeout": 8,
                "reconnect_attempts": 5,
                "max_command_queue": 30,
                "enable_logging": True,
                "security_level": "medium"
            }
        )
        
        # 注册其他设备类型（占位符）
        cls._register_placeholder_types()
        
        logger.info(f"ECU工厂初始化完成，已注册 {len(cls._device_registry)} 种设备类型")
    
    @classmethod
    def _register_placeholder_types(cls):
        """注册占位符设备类型"""
        placeholder_config = {
            "heartbeat_interval": 60,
            "command_timeout": 15,
            "reconnect_attempts": 3,
            "max_command_queue": 100,
            "enable_logging": True
        }
        
        placeholder_types = [
            (DeviceTypes.SMART_METER, DeviceCategory.UTILITY),
            (DeviceTypes.IOT_GATEWAY, DeviceCategory.INDUSTRIAL),
            (DeviceTypes.VEHICLE_ECU, DeviceCategory.TRANSPORTATION),
            (DeviceTypes.SMART_LOCK, DeviceCategory.SECURITY),
            (DeviceTypes.ENVIRONMENT_SENSOR, DeviceCategory.UTILITY)
        ]
        
        for device_type, category in placeholder_types:
            cls.register_device_type(
                device_type=device_type,
                device_class=None,  # 使用通用ECU
                category=category,
                config_template=placeholder_config.copy()
            )
    
    @classmethod
    def register_device_type(cls, device_type: str, device_class: Type[BaseECU], 
                            category: DeviceCategory, config_template: Dict):
        """注册设备类型"""
        cls._device_registry[device_type] = device_class
        cls._device_categories[device_type] = category
        cls._device_config_templates[device_type] = config_template
        
        logger.debug(f"注册设备类型: {device_type}")
    
    @classmethod
    def create_ecu(cls, config: ECUConfig, db_client: Optional[DatabaseClient] = None) -> Optional[BaseECU]:
        """
        创建ECU设备实例
        
        Args:
            config: ECU配置
            db_client: 数据库客户端
            
        Returns:
            ECU设备实例，失败时返回None
        """
        try:
            device_type = config.device_type
            
            if device_type not in cls._device_registry:
                logger.error(f"未知的设备类型: {device_type}")
                return None
            
            device_class = cls._device_registry[device_type]
            
            if device_class is None:
                # 使用通用ECU
                device_class = BaseECU
            
            # 创建设备实例
            ecu = device_class(config, db_client)
            
            logger.info(f"创建ECU设备: {config.ecu_id} ({device_type})")
            return ecu
            
        except Exception as e:
            logger.error(f"创建ECU设备失败: {config.ecu_id}: {e}")
            return None
    
    @classmethod
    def create_ecu_from_dict(cls, ecu_data: Dict, db_client: Optional[DatabaseClient] = None) -> Optional[BaseECU]:
        """
        从字典数据创建ECU设备
        
        Args:
            ecu_data: 设备数据字典
            db_client: 数据库客户端
            
        Returns:
            ECU设备实例
        """
        try:
            # 提取必要字段
            ecu_id = ecu_data.get("ecu_id")
            device_type = ecu_data.get("device_type")
            
            if not ecu_id or not device_type:
                logger.error(f"缺少必要字段: ecu_id={ecu_id}, device_type={device_type}")
                return None
            
            # 获取配置模板
            config_template = cls._device_config_templates.get(device_type, {})
            
            # 合并配置
            config_dict = config_template.copy()
            config_dict.update(ecu_data.get("config", {}))
            
            # 创建配置对象
            config = ECUConfig(
                ecu_id=ecu_id,
                device_type=device_type,
                firmware_version=ecu_data.get("firmware_version", "1.0.0"),
                heartbeat_interval=config_dict.get("heartbeat_interval", 30),
                command_timeout=config_dict.get("command_timeout", 10),
                reconnect_attempts=config_dict.get("reconnect_attempts", 3),
                reconnect_delay=config_dict.get("reconnect_delay", 1.0),
                max_command_queue=config_dict.get("max_command_queue", 100),
                enable_logging=config_dict.get("enable_logging", True)
            )
            
            # 创建设备
            return cls.create_ecu(config, db_client)
            
        except Exception as e:
            logger.error(f"从字典创建ECU失败: {e}")
            return None
    
    @classmethod
    def get_device_class(cls, device_type: str) -> Optional[Type[BaseECU]]:
        """获取设备类"""
        return cls._device_registry.get(device_type)
    
    @classmethod
    def list_device_types(cls, category: Optional[DeviceCategory] = None) -> List[str]:
        """列出设备类型"""
        if category:
            return [
                device_type for device_type, device_category in cls._device_categories.items()
                if device_category == category
            ]
        return list(cls._device_registry.keys())


# 创建工厂实例
_global_factory = None

def get_ecu_factory() -> ECUFactory:
    """获取全局ECU工厂实例"""
    global _global_factory
    if _global_factory is None:
        ECUFactory.initialize()
        _global_factory = ECUFactory()
    return _global_factory


class DeviceCreator:
    """设备创建器 - 简化设备创建过程"""
    
    def __init__(self, factory: ECUFactory = None):
        self.factory = factory or get_ecu_factory()
        self.created_devices = []
    
    async def create_device(self, ecu_id: str, device_type: str, 
                           config_overrides: Dict = None, 
                           db_client: Optional[DatabaseClient] = None) -> Optional[BaseECU]:
        """创建设备"""
        try:
            ecu_data = {
                "ecu_id": ecu_id,
                "device_type": device_type,
                "config": config_overrides or {}
            }
            
            ecu = self.factory.create_ecu_from_dict(ecu_data, db_client)
            if ecu:
                self.created_devices.append(ecu)
            
            return ecu
            
        except Exception as e:
            logger.error(f"创建设备失败: {ecu_id}: {e}")
            return None