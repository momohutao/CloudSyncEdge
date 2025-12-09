"""
设备模块
"""

from .shared_bike import SharedBikeECU
from .door_access import DoorAccessECU
from .device_registry import DeviceRegistry, get_device_registry

__version__ = "1.0.0"
__author__ = "Team A - Devices Module"

__all__ = [
    'SharedBikeECU',
    'DoorAccessECU',
    'DeviceRegistry',
    'get_device_registry'
]