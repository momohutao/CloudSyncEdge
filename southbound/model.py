from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ECUAdminLog(Base):
    """设备管理日志表 - 成员B的职责"""
    __tablename__ = 'ecu_admin_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ecu_id = Column(String(100), nullable=False, index=True)  # 设备ID
    action_type = Column(String(50), nullable=False)  # 操作类型: connect/disconnect/command/status_update
    action_data = Column(JSON, nullable=False)  # 操作详情（JSON格式）
    result = Column(JSON)  # 操作结果（JSON格式）
    admin_user = Column(String(50), default='system')  # 操作用户
    created_at = Column(DateTime, default=datetime.utcnow)  # 创建时间

    def __repr__(self):
        return f"<ECUAdminLog(id={self.id}, ecu_id={self.ecu_id}, action_type={self.action_type})>"