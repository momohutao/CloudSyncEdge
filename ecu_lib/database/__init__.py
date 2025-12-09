"""
数据库模块
"""

from .client import DatabaseClient
from .models import (
    Base,
    ECUDeviceModel,
    ECUStatusHistory,
    CommandExecutionLog,
    HeartbeatLog,
    AccessEventLog,
    RideRecord
)
from .batch_writer import BatchWriter, PriorityBatchWriter

__version__ = "1.0.0"
__author__ = "Team A - Database Module"

__all__ = [
    'DatabaseClient',
    'Base',
    'ECUDeviceModel',
    'ECUStatusHistory',
    'CommandExecutionLog',
    'HeartbeatLog',
    'AccessEventLog',
    'RideRecord',
    'BatchWriter',
    'PriorityBatchWriter'
]