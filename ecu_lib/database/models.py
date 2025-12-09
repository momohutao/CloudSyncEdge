"""
数据库模型类 - 映射数据库表
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ECUDeviceModel(Base):
    """ECU设备表模型"""
    __tablename__ = "ecu_devices"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ecu_id = Column(String(64), unique=True, nullable=False, index=True)
    device_type = Column(String(32), nullable=False, index=True)
    firmware_version = Column(String(32), default="1.0.0")
    hardware_version = Column(String(32), default="1.0")
    
    # 状态信息
    status = Column(String(20), default="offline")
    last_seen = Column(DateTime)
    last_heartbeat = Column(DateTime)
    last_command = Column(DateTime)
    
    # 配置信息
    config = Column(JSON, default=dict)
    attributes = Column(JSON, default=dict)
    
    # 位置信息
    location_latitude = Column(Float)
    location_longitude = Column(Float)
    location_accuracy = Column(Float)
    location_address = Column(String(255))
    
    # 网络信息
    ip_address = Column(String(45))
    mac_address = Column(String(17))
    network_type = Column(String(20))
    signal_strength = Column(Integer)
    
    # 元数据
    manufacturer = Column(String(64))
    model = Column(String(64))
    serial_number = Column(String(64))
    production_date = Column(DateTime)
    
    # 管理字段
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    deleted_at = Column(DateTime)
    
    # 索引
    __table_args__ = (
        # 复合索引
        {"extend_existing": True}
    )
    
    def __repr__(self):
        return f"<ECUDevice(ecu_id='{self.ecu_id}', device_type='{self.device_type}', status='{self.status}')>"


class ECUStatusHistory(Base):
    """ECU状态历史表模型"""
    __tablename__ = "ecu_status_history"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ecu_id = Column(String(64), nullable=False, index=True)
    status_data = Column(JSON, nullable=False)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    
    # 索引
    __table_args__ = (
        # 复合索引
        {"extend_existing": True}
    )
    
    def __repr__(self):
        return f"<ECUStatusHistory(ecu_id='{self.ecu_id}', timestamp='{self.timestamp}')>"


class CommandExecutionLog(Base):
    """命令执行日志表模型"""
    __tablename__ = "command_execution_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ecu_id = Column(String(64), nullable=False, index=True)
    command_id = Column(String(64), index=True)
    command = Column(String(64), nullable=False, index=True)
    params = Column(JSON, default=dict)
    result = Column(JSON, nullable=False)
    execution_time = Column(DateTime, default=datetime.now, index=True)
    success = Column(Boolean, default=False)
    error_message = Column(Text)
    error_code = Column(Integer)
    execution_duration_ms = Column(Integer, default=0)
    
    # 索引
    __table_args__ = (
        # 复合索引
        {"extend_existing": True}
    )
    
    def __repr__(self):
        return f"<CommandExecutionLog(ecu_id='{self.ecu_id}', command='{self.command}', success={self.success})>"


class HeartbeatLog(Base):
    """心跳日志表模型"""
    __tablename__ = "heartbeat_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ecu_id = Column(String(64), nullable=False, index=True)
    heartbeat_data = Column(JSON, nullable=False)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    latency_ms = Column(Integer, default=0)
    network_quality = Column(Integer, default=5)
    
    # 索引
    __table_args__ = (
        # 复合索引
        {"extend_existing": True}
    )
    
    def __repr__(self):
        return f"<HeartbeatLog(ecu_id='{self.ecu_id}', timestamp='{self.timestamp}')>"


class AccessEventLog(Base):
    """访问事件日志表模型"""
    __tablename__ = "access_event_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ecu_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    event_data = Column(JSON, nullable=False)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    severity = Column(String(20), default="info", index=True)
    location = Column(String(64))
    
    # 索引
    __table_args__ = (
        # 复合索引
        {"extend_existing": True}
    )
    
    def __repr__(self):
        return f"<AccessEventLog(ecu_id='{self.ecu_id}', event_type='{self.event_type}', timestamp='{self.timestamp}')>"


class RideRecord(Base):
    """骑行记录表模型（共享单车专用）"""
    __tablename__ = "ride_records"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ride_id = Column(String(64), unique=True, index=True)
    ecu_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, index=True)
    duration_seconds = Column(Integer, default=0)
    distance_km = Column(Float, default=0.0)
    start_location = Column(JSON, default=dict)
    end_location = Column(JSON, default=dict)
    average_speed_kmh = Column(Float, default=0.0)
    calories_burned = Column(Integer, default=0)
    cost_amount = Column(Float, default=0.0)
    payment_status = Column(String(20), default="pending")
    battery_usage = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    
    # 索引
    __table_args__ = (
        # 复合索引
        {"extend_existing": True}
    )
    
    def __repr__(self):
        return f"<RideRecord(ride_id='{self.ride_id}', ecu_id='{self.ecu_id}', user_id='{self.user_id}')>"


# Pydantic模型（用于数据验证）
class ECUDeviceCreate(Base):
    """创建ECU设备的Pydantic模型"""
    ecu_id: str
    device_type: str
    firmware_version: str = "1.0.0"
    status: str = "offline"
    config: Dict[str, Any] = {}
    attributes: Dict[str, Any] = {}


class ECUStatusCreate(Base):
    """创建状态记录的Pydantic模型"""
    ecu_id: str
    status_data: Dict[str, Any]
    timestamp: Optional[datetime] = None


class CommandLogCreate(Base):
    """创建命令日志的Pydantic模型"""
    ecu_id: str
    command: str
    params: Dict[str, Any] = {}
    result: Dict[str, Any]
    success: bool
    execution_time: Optional[datetime] = None


# 数据迁移函数
def get_alembic_config():
    """获取Alembic配置"""
    import os
    from alembic.config import Config
    
    alembic_cfg = Config()
    alembic_cfg.set_main_option(
        "script_location", 
        os.path.join(os.path.dirname(__file__), "migrations")
    )
    alembic_cfg.set_main_option(
        "sqlalchemy.url", 
        "sqlite+aiosqlite:///./data/ecu.db"  # 默认URL
    )
    return alembic_cfg