"""
ECU工厂类 - 负责创建和管理ECU设备实例
"""
import logging
from typing import Dict, List, Optional, Type
from enum import Enum
import importlib

from CloudSyncEdge.src.protocol.message_types import DeviceTypes, MessageTypes

from .base_ecu import BaseECU, ECUConfig
from ..devices.shared_bike import SharedBikeECU
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
            device_class=SharedBikeECU,
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
        
        logger.debug(f"注册设备类型: {device_type} -> {device_class.__name__ if device_class else 'GenericECU'}")
    
    @classmethod
    def unregister_device_type(cls, device_type: str) -> bool:
        """注销设备类型"""
        if device_type in cls._device_registry:
            del cls._device_registry[device_type]
            del cls._device_categories[device_type]
            del cls._device_config_templates[device_type]
            
            logger.info(f"注销设备类型: {device_type}")
            return True
        return False
    
    @classmethod
    def register_custom_device_type(cls, device_type: str, module_path: str, class_name: str,
                                   category: DeviceCategory, config_template: Dict) -> bool:
        """注册自定义设备类型"""
        try:
            # 动态导入模块
            module = importlib.import_module(module_path)
            device_class = getattr(module, class_name)
            
            if not issubclass(device_class, BaseECU):
                logger.error(f"类 {class_name} 不是 BaseECU 的子类")
                return False
            
            cls.register_device_type(device_type, device_class, category, config_template)
            logger.info(f"注册自定义设备类型: {device_type} -> {class_name}")
            return True
            
        except ImportError as e:
            logger.error(f"导入模块失败: {module_path}: {e}")
            return False
        except AttributeError as e:
            logger.error(f"找不到类: {class_name} in {module_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"注册自定义设备类型失败: {e}")
            return False
    
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
                from .base_ecu import BaseECU
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
    def batch_create_ecus(cls, ecu_list: List[Dict], db_client: Optional[DatabaseClient] = None) -> List[BaseECU]:
        """批量创建ECU设备"""
        ecus = []
        
        for ecu_data in ecu_list:
            ecu = cls.create_ecu_from_dict(ecu_data, db_client)
            if ecu:
                ecus.append(ecu)
        
        logger.info(f"批量创建 {len(ecus)}/{len(ecu_list)} 个ECU设备")
        return ecus
    
    @classmethod
    def get_device_class(cls, device_type: str) -> Optional[Type[BaseECU]]:
        """获取设备类"""
        return cls._device_registry.get(device_type)
    
    @classmethod
    def get_device_category(cls, device_type: str) -> Optional[DeviceCategory]:
        """获取设备分类"""
        return cls._device_categories.get(device_type)
    
    @classmethod
    def get_config_template(cls, device_type: str) -> Dict:
        """获取配置模板"""
        return cls._device_config_templates.get(device_type, {}).copy()
    
    @classmethod
    def update_config_template(cls, device_type: str, template_updates: Dict) -> bool:
        """更新配置模板"""
        if device_type in cls._device_config_templates:
            cls._device_config_templates[device_type].update(template_updates)
            logger.info(f"更新配置模板: {device_type}")
            return True
        return False
    
    @classmethod
    def list_device_types(cls, category: Optional[DeviceCategory] = None) -> List[str]:
        """列出设备类型"""
        if category:
            return [
                device_type for device_type, device_category in cls._device_categories.items()
                if device_category == category
            ]
        return list(cls._device_registry.keys())
    
    @classmethod
    def list_device_categories(cls) -> Dict[DeviceCategory, List[str]]:
        """列出设备分类及其类型"""
        categories = {}
        
        for device_type, category in cls._device_categories.items():
            if category not in categories:
                categories[category] = []
            categories[category].append(device_type)
        
        return categories
    
    @classmethod
    def validate_device_config(cls, ecu_id: str, device_type: str, config: Dict) -> Dict:
        """验证设备配置"""
        errors = []
        warnings = []
        
        # 基本验证
        if not ecu_id or len(ecu_id) > 64:
            errors.append("ecu_id不能为空且长度不能超过64字符")
        
        if device_type not in cls._device_registry:
            errors.append(f"未知的设备类型: {device_type}")
        else:
            # 获取配置模板
            template = cls.get_config_template(device_type)
            
            # 验证必填字段
            required_fields = ["heartbeat_interval", "command_timeout"]
            for field in required_fields:
                if field not in config:
                    config[field] = template.get(field)
            
            # 验证数值范围
            if "heartbeat_interval" in config:
                interval = config["heartbeat_interval"]
                if interval < 10 or interval > 300:
                    warnings.append(f"心跳间隔{interval}秒可能不合适，建议10-300秒")
            
            if "command_timeout" in config:
                timeout = config["command_timeout"]
                if timeout < 1 or timeout > 60:
                    warnings.append(f"命令超时{timeout}秒可能不合适，建议1-60秒")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "suggested_config": config
        }
    
    @classmethod
    async def create_and_start_ecu(cls, ecu_data: Dict, db_client: Optional[DatabaseClient] = None) -> Optional[BaseECU]:
        """创建并启动ECU设备"""
        try:
            ecu = cls.create_ecu_from_dict(ecu_data, db_client)
            if not ecu:
                return None
            
            await ecu.start()
            logger.info(f"ECU设备创建并启动: {ecu.ecu_id}")
            return ecu
            
        except Exception as e:
            logger.error(f"创建并启动ECU失败: {e}")
            return None
    
    @classmethod
    def get_statistics(cls) -> Dict:
        """获取工厂统计信息"""
        total_types = len(cls._device_registry)
        categories = cls.list_device_categories()
        
        category_counts = {cat.value: len(types) for cat, types in categories.items()}
        
        return {
            "total_device_types": total_types,
            "category_distribution": category_counts,
            "registered_types": cls.list_device_types(),
            "config_templates_available": len(cls._device_config_templates)
        }


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
            
            ecu = await self.factory.create_and_start_ecu(ecu_data, db_client)
            if ecu:
                self.created_devices.append(ecu)
            
            return ecu
            
        except Exception as e:
            logger.error(f"创建设备失败: {ecu_id}: {e}")
            return None
    
    async def create_multiple_devices(self, device_specs: List[Dict], 
                                     db_client: Optional[DatabaseClient] = None) -> List[BaseECU]:
        """创建多个设备"""
        tasks = []
        
        for spec in device_specs:
            ecu_id = spec.get("ecu_id")
            device_type = spec.get("device_type")
            config = spec.get("config", {})
            
            if ecu_id and device_type:
                task = self.create_device(ecu_id, device_type, config, db_client)
                tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_devices = []
        for result in results:
            if isinstance(result, BaseECU):
                successful_devices.append(result)
            elif isinstance(result, Exception):
                logger.error(f"创建设备失败: {result}")
        
        return successful_devices
    
    async def cleanup(self):
        """清理所有创建的设备"""
        cleanup_tasks = []
        
        for ecu in self.created_devices:
            if ecu.status.value != "offline":
                cleanup_tasks.append(ecu.stop())
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        self.created_devices.clear()
        logger.info(f"清理了 {len(cleanup_tasks)} 个设备")


# =============== 使用示例 ===============

async def demo_ecu_factory():
    """演示ECU工厂使用"""
    print("🚀 演示ECU工厂使用...")
    
    try:
        # 获取工厂实例
        factory = get_ecu_factory()
        
        # 列出所有设备类型
        device_types = factory.list_device_types()
        print(f"✅ 可用设备类型: {len(device_types)} 种")
        for dtype in device_types:
            print(f"  - {dtype}")
        
        # 按分类列出
        categories = factory.list_device_categories()
        print(f"\n✅ 设备分类:")
        for category, types in categories.items():
            print(f"  {category.value}: {len(types)} 种类型")
        
        # 创建设备
        creator = DeviceCreator(factory)
        
        # 创建共享单车
        bike = await creator.create_device(
            ecu_id="demo_bike_001",
            device_type=DeviceTypes.SHARED_BIKE,
            config_overrides={"heartbeat_interval": 25}
        )
        
        if bike:
            print(f"✅ 创建共享单车: {bike.ecu_id}")
            
            # 获取设备状态
            status = bike.get_status_dict()
            print(f"✅ 设备状态: {status['status']}")
            
            # 执行命令
            result = await bike.execute_command(MessageTypes.GET_STATUS, {})
            print(f"✅ 执行命令: {result.get('success')}")
        
        # 创建门禁设备
        door = await creator.create_device(
            ecu_id="demo_door_001",
            device_type=DeviceTypes.ACCESS_CONTROL,
            config_overrides={"command_timeout": 5}
        )
        
        if door:
            print(f"✅ 创建门禁设备: {door.ecu_id}")
        
        # 批量创建设备
        device_specs = [
            {"ecu_id": "demo_bike_002", "device_type": DeviceTypes.SHARED_BIKE},
            {"ecu_id": "demo_door_002", "device_type": DeviceTypes.ACCESS_CONTROL},
        ]
        
        devices = await creator.create_multiple_devices(device_specs)
        print(f"✅ 批量创建: {len(devices)} 个设备")
        
        # 获取工厂统计
        stats = factory.get_statistics()
        print(f"✅ 工厂统计: {stats}")
        
        # 清理
        await creator.cleanup()
        print("🎉 ECU工厂演示完成")
        
    except Exception as e:
        print(f"❌ 演示失败: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_ecu_factory())