"""
ECU库主模块 - 成员A
简化版本，只包含必要的导出
"""

# 核心模块
from .core.base_ecu import BaseECU, ECUConfig, ECUStatus, ECUCommand, CommandResult
from .core.ecu_factory import ECUFactory, get_ecu_factory

# 接口模块
from .interfaces.ecu_interface import ECUInterface, DefaultECUInterface

# 数据库模块
from .database.client import DatabaseClient
from .database.ecu_device_dao import ECUDeviceDAO

# 设备模块
from .devices.device_registry import DeviceRegistry, get_device_registry

# 共享工具
from .shared.database import SimpleDB

__all__ = [
    # 核心
    'BaseECU',
    'ECUConfig', 
    'ECUStatus',
    'ECUCommand',
    'CommandResult',
    'ECUFactory',
    'get_ecu_factory',
    
    # 接口
    'ECUInterface',
    'DefaultECUInterface',
    
    # 数据库
    'DatabaseClient',
    'ECUDeviceDAO',
    
    # 设备
    'DeviceRegistry',
    'get_device_registry',
    
    # 工具
    'SimpleDB'
]