"""
接口模块
"""

from .ecu_interface import ECUInterface, DefaultECUInterface, create_ecu_interface
from .device_manager import (
    DeviceManagerInterface,
    SouthboundInterfaceProxy,
    MockToRealAdapter,
    create_southbound_proxy,
    create_adapter_interface
)

__version__ = "1.0.0"
__author__ = "Team A - Interfaces Module"

__all__ = [
    'ECUInterface',
    'DefaultECUInterface',
    'create_ecu_interface',
    'DeviceManagerInterface',
    'SouthboundInterfaceProxy',
    'MockToRealAdapter',
    'create_southbound_proxy',
    'create_adapter_interface'
]