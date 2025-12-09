"""
ECU设备库
"""

from .core.base_ecu import BaseECU, ECUConfig, ECUStatus, ECUCommand
from .core.ecu_factory import ECUFactory
from .core.ecu_simulator import ECUSimulator

from .devices.shared_bike import SharedBikeECU
from .devices.door_access import DoorAccessECU
from .devices.device_registry import DeviceRegistry

from .database.client import DatabaseClient
from .database.models import ECUDeviceModel, ECUStatusModel
from .database.batch_writer import BatchWriter

from .interface.ecu_interface import ECUInterface
from .interface.device_manager import DeviceManagerInterface

from .mock.mock_manager import MockDeviceManager

__version__ = "1.0.0"
__author__ = "Team A - ECU Library"

__all__ = [
    # 核心类
    'BaseECU',
    'ECUConfig',
    'ECUStatus',
    'ECUCommand',
    'ECUFactory',
    'ECUSimulator',
    
    # 设备实现
    'SharedBikeECU',
    'DoorAccessECU',
    'DeviceRegistry',
    
    # 数据库
    'DatabaseClient',
    'ECUDeviceModel',
    'ECUStatusModel',
    'BatchWriter',
    
    # 接口
    'ECUInterface',
    'DeviceManagerInterface',
    
    # Mock
    'MockDeviceManager',
]