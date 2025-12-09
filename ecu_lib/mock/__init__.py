"""
Mock模块
"""

from .mock_manager import (
    MockDeviceManager,
    MockWebSocketConnection,
    create_mock_device_manager,
    setup_mock_environment
)

__version__ = "1.0.0"
__author__ = "Team A - Mock Module"

__all__ = [
    'MockDeviceManager',
    'MockWebSocketConnection',
    'create_mock_device_manager',
    'setup_mock_environment'
]