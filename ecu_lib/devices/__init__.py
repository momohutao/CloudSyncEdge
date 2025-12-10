"""
设备模块
"""

# 修正：使用正确的文件名
from .shared_bike_ecu import SharedBikeECU
from .door_access import DoorAccessECU
from .device_registry import DeviceRegistry, get_device_registry

__all__ = [
    'SharedBikeECU',
    'DoorAccessECU',
    'DeviceRegistry',
    'get_device_registry'
]