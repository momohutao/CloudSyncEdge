"""
数据库模型定义
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

# 导入缺失的SQLAlchemy组件
try:
    from sqlalchemy import Column, String, Integer, DateTime, JSON, Text, Index
    from sqlalchemy.ext.declarative import declarative_base
    SQLALCHEMY_AVAILABLE = True
    Base = declarative_base()
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    # 创建虚拟基类，防止导入错误
    class Base:
        pass

from pydantic import BaseModel, Field


# Pydantic模型（用于数据验证和序列化）
class ProtocolLogBase(BaseModel):
    """协议日志基础模型"""
    direction: str = Field(..., description="消息方向: inbound/outbound")
    method: str = Field(..., description="方法名")
    ecu_id: Optional[str] = Field(None, description="设备ID")
    request_id: Optional[str] = Field(None, description="请求ID")
    data: Dict[str, Any] = Field(default_factory=dict, description="消息数据")
    message_size: int = Field(0, description="消息大小（字节）")
    status: str = Field("logged", description="日志状态")
    
    class Config:
        schema_extra = {
            "example": {
                "direction": "inbound",
                "method": "status_update",
                "ecu_id": "bike_001",
                "request_id": "req_123",
                "data": {"battery": 85},
                "message_size": 128,
                "status": "logged"
            }
        }


class ErrorLogBase(BaseModel):
    """错误日志基础模型"""
    error_code: int = Field(..., description="错误代码")
    error_message: str = Field(..., description="错误信息")
    ecu_id: Optional[str] = Field(None, description="设备ID")
    context: Optional[Dict[str, Any]] = Field(None, description="上下文信息")
    stack_trace: Optional[str] = Field(None, description="堆栈跟踪")
    
    class Config:
        schema_extra = {
            "example": {
                "error_code": -32001,
                "error_message": "Device is offline",
                "ecu_id": "bike_001",
                "context": {"ip": "192.168.1.100"},
                "stack_trace": "Traceback..."
            }
        }


class HeartbeatLogBase(BaseModel):
    """心跳日志基础模型"""
    ecu_id: str = Field(..., description="设备ID")
    status: Dict[str, Any] = Field(..., description="设备状态")
    latency: float = Field(0.0, description="延迟时间（秒）")
    network_quality: Optional[int] = Field(None, description="网络质量（1-5）")
    
    class Config:
        schema_extra = {
            "example": {
                "ecu_id": "bike_001",
                "status": {"battery": 85, "signal": 4},
                "latency": 0.05,
                "network_quality": 4
            }
        }


class ProtocolStats(BaseModel):
    """协议统计信息"""
    total_messages: int = Field(0, description="总消息数")
    inbound_count: int = Field(0, description="入站消息数")
    outbound_count: int = Field(0, description="出站消息数")
    error_count: int = Field(0, description="错误数")
    avg_message_size: float = Field(0.0, description="平均消息大小")
    success_rate: float = Field(0.0, description="成功率")
    period_start: datetime = Field(..., description="统计开始时间")
    period_end: datetime = Field(..., description="统计结束时间")
    generated_at: datetime = Field(default_factory=datetime.now, description="生成时间")
    
    class Config:
        schema_extra = {
            "example": {
                "total_messages": 1000,
                "inbound_count": 600,
                "outbound_count": 400,
                "error_count": 10,
                "avg_message_size": 512.5,
                "success_rate": 0.99,
                "period_start": "2024-01-01T00:00:00",
                "period_end": "2024-01-01T23:59:59",
                "generated_at": "2024-01-01T23:59:59"
            }
        }


# SQLAlchemy模型（如果SQLAlchemy可用）
if SQLALCHEMY_AVAILABLE:
    class ProtocolLog(Base):
        """SQLAlchemy协议日志模型"""
        __tablename__ = "protocol_logs"
        
        # 字段定义
        id = Column(String(36), primary_key=True)
        timestamp = Column(DateTime, default=datetime.utcnow, index=True)
        direction = Column(String(10), nullable=False)
        method = Column(String(50), nullable=False)
        ecu_id = Column(String(64), index=True)
        request_id = Column(String(64), index=True)
        data = Column(JSON)
        message_size = Column(Integer, default=0)
        status = Column(String(20), default="logged")
        created_at = Column(DateTime, default=datetime.utcnow)
        
        # 索引
        __table_args__ = (
            Index('idx_protocol_ecu_timestamp', 'ecu_id', 'timestamp'),
            Index('idx_protocol_method_timestamp', 'method', 'timestamp'),
        )
        
        def to_dict(self) -> Dict[str, Any]:
            """转换为字典"""
            return {
                "id": self.id,
                "timestamp": self.timestamp.isoformat() if self.timestamp else None,
                "direction": self.direction,
                "method": self.method,
                "ecu_id": self.ecu_id,
                "request_id": self.request_id,
                "data": self.data,
                "message_size": self.message_size,
                "status": self.status,
                "created_at": self.created_at.isoformat() if self.created_at else None
            }
    
    class ErrorLog(Base):
        """SQLAlchemy错误日志模型"""
        __tablename__ = "error_logs"
        
        # 字段定义
        id = Column(String(36), primary_key=True)
        timestamp = Column(DateTime, default=datetime.utcnow, index=True)
        error_code = Column(Integer, nullable=False)
        error_message = Column(String(500), nullable=False)
        ecu_id = Column(String(64), index=True)
        context = Column(JSON)
        stack_trace = Column(Text)
        severity = Column(String(20), default="error")
        created_at = Column(DateTime, default=datetime.utcnow)
        
        # 索引
        __table_args__ = (
            Index('idx_error_ecu_timestamp', 'ecu_id', 'timestamp'),
            Index('idx_error_code_timestamp', 'error_code', 'timestamp'),
        )
        
        def to_dict(self) -> Dict[str, Any]:
            """转换为字典"""
            return {
                "id": self.id,
                "timestamp": self.timestamp.isoformat() if self.timestamp else None,
                "error_code": self.error_code,
                "error_message": self.error_message,
                "ecu_id": self.ecu_id,
                "context": self.context,
                "stack_trace": self.stack_trace,
                "severity": self.severity,
                "created_at": self.created_at.isoformat() if self.created_at else None
            }
else:
    # SQLAlchemy不可用时的占位类
    class ProtocolLog:
        pass
    
    class ErrorLog:
        pass


# 便捷函数
def create_protocol_log_model() -> type:
    """动态创建协议日志模型类"""
    if SQLALCHEMY_AVAILABLE:
        return ProtocolLog
    else:
        class MockProtocolLog:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
            
            def to_dict(self) -> Dict[str, Any]:
                return self.__dict__
        
        return MockProtocolLog