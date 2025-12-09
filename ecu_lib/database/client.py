"""
DatabaseClient类 - 设备状态CRUD和数据库操作
"""
import asyncio
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.exc import SQLAlchemyError

from .models import (
    Base, 
    ECUDeviceModel, 
    ECUStatusHistory, 
    CommandExecutionLog,
    HeartbeatLog,
    AccessEventLog,
    RideRecord
)

logger = logging.getLogger(__name__)


class DatabaseClient:
    """数据库客户端 - 提供设备状态CRUD操作"""
    
    def __init__(self, db_url: str, pool_size: int = 10, pool_recycle: int = 3600):
        """
        初始化数据库客户端
        
        Args:
            db_url: 数据库连接URL (sqlite+aiosqlite:///./data/ecu.db)
            pool_size: 连接池大小
            pool_recycle: 连接回收时间（秒）
        """
        self.db_url = db_url
        
        # 创建异步引擎
        self.engine = create_async_engine(
            db_url,
            echo=False,  # 设置为True可查看SQL日志
            pool_size=pool_size,
            max_overflow=10,
            pool_recycle=pool_recycle,
            pool_pre_ping=True  # 连接前ping数据库
        )
        
        # 创建会话工厂
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # 批量写入器
        self.batch_writer = BatchWriter(self.session_factory)
        
        logger.info(f"DatabaseClient初始化完成，连接URL: {db_url}")
    
    async def initialize(self):
        """初始化数据库表"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("数据库表创建成功")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
    
    @asynccontextmanager
    async def get_session(self):
        """获取数据库会话上下文管理器"""
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"数据库会话异常: {e}")
            raise
        finally:
            await session.close()
    
    # =============== ECU设备操作 ===============
    
    async def save_ecu_device(self, device_data: Dict) -> str:
        """保存ECU设备信息"""
        try:
            async with self.get_session() as session:
                # 检查设备是否已存在
                query = select(ECUDeviceModel).where(
                    ECUDeviceModel.ecu_id == device_data["ecu_id"]
                )
                result = await session.execute(query)
                existing_device = result.scalar_one_or_none()
                
                if existing_device:
                    # 更新现有设备
                    for key, value in device_data.items():
                        if hasattr(existing_device, key):
                            setattr(existing_device, key, value)
                    existing_device.updated_at = datetime.now()
                    device_id = existing_device.id
                else:
                    # 创建新设备
                    device = ECUDeviceModel(**device_data)
                    session.add(device)
                    await session.flush()
                    device_id = device.id
                
                logger.debug(f"保存ECU设备: {device_data['ecu_id']}")
                return device_id
                
        except SQLAlchemyError as e:
            logger.error(f"保存ECU设备失败: {e}")
            raise
    
    async def get_ecu_device(self, ecu_id: str) -> Optional[Dict]:
        """获取ECU设备信息"""
        try:
            async with self.get_session() as session:
                query = select(ECUDeviceModel).where(
                    ECUDeviceModel.ecu_id == ecu_id
                )
                result = await session.execute(query)
                device = result.scalar_one_or_none()
                
                if device:
                    return self._model_to_dict(device)
                return None
                
        except SQLAlchemyError as e:
            logger.error(f"获取ECU设备失败: {e}")
            raise
    
    async def update_ecu_device(self, ecu_id: str, update_data: Dict) -> bool:
        """更新ECU设备信息"""
        try:
            async with self.get_session() as session:
                query = select(ECUDeviceModel).where(
                    ECUDeviceModel.ecu_id == ecu_id
                )
                result = await session.execute(query)
                device = result.scalar_one_or_none()
                
                if device:
                    for key, value in update_data.items():
                        if hasattr(device, key):
                            setattr(device, key, value)
                    device.updated_at = datetime.now()
                    
                    logger.debug(f"更新ECU设备: {ecu_id}")
                    return True
                return False
                
        except SQLAlchemyError as e:
            logger.error(f"更新ECU设备失败: {e}")
            raise
    
    async def delete_ecu_device(self, ecu_id: str) -> bool:
        """删除ECU设备（软删除）"""
        try:
            async with self.get_session() as session:
                query = select(ECUDeviceModel).where(
                    ECUDeviceModel.ecu_id == ecu_id
                )
                result = await session.execute(query)
                device = result.scalar_one_or_none()
                
                if device:
                    device.is_active = False
                    device.deleted_at = datetime.now()
                    
                    logger.info(f"删除ECU设备: {ecu_id}")
                    return True
                return False
                
        except SQLAlchemyError as e:
            logger.error(f"删除ECU设备失败: {e}")
            raise
    
    async def list_ecu_devices(self, device_type: Optional[str] = None, 
                               active_only: bool = True, 
                               limit: int = 100, 
                               offset: int = 0) -> List[Dict]:
        """列出ECU设备"""
        try:
            async with self.get_session() as session:
                query = select(ECUDeviceModel)
                
                # 过滤条件
                if device_type:
                    query = query.where(ECUDeviceModel.device_type == device_type)
                
                if active_only:
                    query = query.where(ECUDeviceModel.is_active == True)
                
                # 排序和分页
                query = query.order_by(ECUDeviceModel.created_at.desc())
                query = query.offset(offset).limit(limit)
                
                result = await session.execute(query)
                devices = result.scalars().all()
                
                return [self._model_to_dict(device) for device in devices]
                
        except SQLAlchemyError as e:
            logger.error(f"列出ECU设备失败: {e}")
            raise
    
    # =============== 设备状态操作 ===============
    
    async def save_ecu_status(self, ecu_id: str, status_data: Dict) -> str:
        """保存设备状态"""
        try:
            status_entry = {
                "id": str(uuid.uuid4()),
                "ecu_id": ecu_id,
                "status_data": status_data,
                "timestamp": datetime.now()
            }
            
            # 使用批量写入器
            await self.batch_writer.add_status(status_entry)
            
            logger.debug(f"保存设备状态: {ecu_id}")
            return status_entry["id"]
            
        except Exception as e:
            logger.error(f"保存设备状态失败: {e}")
            raise
    
    async def batch_save_statuses(self, statuses: List[Dict]) -> bool:
        """批量保存设备状态"""
        try:
            status_entries = []
            for status in statuses:
                status_entry = {
                    "id": str(uuid.uuid4()),
                    "ecu_id": status["ecu_id"],
                    "status_data": status,
                    "timestamp": datetime.now()
                }
                status_entries.append(status_entry)
            
            # 批量写入
            await self.batch_writer.batch_save_statuses(status_entries)
            
            logger.info(f"批量保存 {len(statuses)} 个设备状态")
            return True
            
        except Exception as e:
            logger.error(f"批量保存设备状态失败: {e}")
            raise
    
    async def get_ecu_status_history(self, ecu_id: str, 
                                     start_time: Optional[datetime] = None,
                                     end_time: Optional[datetime] = None,
                                     limit: int = 100) -> List[Dict]:
        """获取设备状态历史"""
        try:
            async with self.get_session() as session:
                query = select(ECUStatusHistory).where(
                    ECUStatusHistory.ecu_id == ecu_id
                )
                
                # 时间范围过滤
                if start_time:
                    query = query.where(ECUStatusHistory.timestamp >= start_time)
                if end_time:
                    query = query.where(ECUStatusHistory.timestamp <= end_time)
                
                # 排序和分页
                query = query.order_by(ECUStatusHistory.timestamp.desc())
                query = query.limit(limit)
                
                result = await session.execute(query)
                statuses = result.scalars().all()
                
                return [
                    {
                        "id": status.id,
                        "ecu_id": status.ecu_id,
                        "status_data": status.status_data,
                        "timestamp": status.timestamp.isoformat()
                    }
                    for status in statuses
                ]
                
        except SQLAlchemyError as e:
            logger.error(f"获取设备状态历史失败: {e}")
            raise
    
    async def get_latest_ecu_status(self, ecu_id: str) -> Optional[Dict]:
        """获取最新设备状态"""
        try:
            async with self.get_session() as session:
                subquery = select(
                    ECUStatusHistory.ecu_id,
                    func.max(ECUStatusHistory.timestamp).label('max_timestamp')
                ).where(
                    ECUStatusHistory.ecu_id == ecu_id
                ).group_by(
                    ECUStatusHistory.ecu_id
                ).subquery()
                
                query = select(ECUStatusHistory).join(
                    subquery,
                    and_(
                        ECUStatusHistory.ecu_id == subquery.c.ecu_id,
                        ECUStatusHistory.timestamp == subquery.c.max_timestamp
                    )
                )
                
                result = await session.execute(query)
                status = result.scalar_one_or_none()
                
                if status:
                    return {
                        "id": status.id,
                        "ecu_id": status.ecu_id,
                        "status_data": status.status_data,
                        "timestamp": status.timestamp.isoformat()
                    }
                return None
                
        except SQLAlchemyError as e:
            logger.error(f"获取最新设备状态失败: {e}")
            raise
    
    # =============== 心跳记录 ===============
    
    async def save_heartbeat(self, ecu_id: str, heartbeat_data: Dict) -> str:
        """保存心跳记录"""
        try:
            heartbeat_entry = {
                "id": str(uuid.uuid4()),
                "ecu_id": ecu_id,
                "heartbeat_data": heartbeat_data,
                "timestamp": datetime.now(),
                "latency_ms": heartbeat_data.get("latency_ms", 0),
                "network_quality": heartbeat_data.get("network_quality", 5)
            }
            
            # 使用批量写入器
            await self.batch_writer.add_heartbeat(heartbeat_entry)
            
            logger.debug(f"保存心跳记录: {ecu_id}")
            return heartbeat_entry["id"]
            
        except Exception as e:
            logger.error(f"保存心跳记录失败: {e}")
            raise
    
    async def get_heartbeat_history(self, ecu_id: str, 
                                    hours: int = 24,
                                    limit: int = 100) -> List[Dict]:
        """获取心跳历史"""
        try:
            start_time = datetime.now() - timedelta(hours=hours)
            
            async with self.get_session() as session:
                query = select(HeartbeatLog).where(
                    HeartbeatLog.ecu_id == ecu_id,
                    HeartbeatLog.timestamp >= start_time
                ).order_by(
                    HeartbeatLog.timestamp.desc()
                ).limit(limit)
                
                result = await session.execute(query)
                heartbeats = result.scalars().all()
                
                return [
                    {
                        "id": hb.id,
                        "ecu_id": hb.ecu_id,
                        "heartbeat_data": hb.heartbeat_data,
                        "timestamp": hb.timestamp.isoformat(),
                        "latency_ms": hb.latency_ms,
                        "network_quality": hb.network_quality
                    }
                    for hb in heartbeats
                ]
                
        except SQLAlchemyError as e:
            logger.error(f"获取心跳历史失败: {e}")
            raise
    
    # =============== 命令执行日志 ===============
    
    async def save_command_execution(self, execution_data: Dict) -> str:
        """保存命令执行日志"""
        try:
            command_log = {
                "id": str(uuid.uuid4()),
                "ecu_id": execution_data["ecu_id"],
                "command_id": execution_data.get("command_id", ""),
                "command": execution_data["command"],
                "params": execution_data.get("params", {}),
                "result": execution_data["result"],
                "execution_time": execution_data.get("execution_time", datetime.now()),
                "success": execution_data.get("success", False),
                "error_message": execution_data.get("error_message"),
                "execution_duration_ms": execution_data.get("execution_duration_ms", 0)
            }
            
            # 使用批量写入器
            await self.batch_writer.add_command_log(command_log)
            
            logger.debug(f"保存命令执行日志: {execution_data['ecu_id']} - {execution_data['command']}")
            return command_log["id"]
            
        except Exception as e:
            logger.error(f"保存命令执行日志失败: {e}")
            raise
    
    async def get_command_history(self, ecu_id: str,
                                  command: Optional[str] = None,
                                  start_time: Optional[datetime] = None,
                                  end_time: Optional[datetime] = None,
                                  limit: int = 100) -> List[Dict]:
        """获取命令历史"""
        try:
            async with self.get_session() as session:
                query = select(CommandExecutionLog).where(
                    CommandExecutionLog.ecu_id == ecu_id
                )
                
                # 过滤条件
                if command:
                    query = query.where(CommandExecutionLog.command == command)
                if start_time:
                    query = query.where(CommandExecutionLog.execution_time >= start_time)
                if end_time:
                    query = query.where(CommandExecutionLog.execution_time <= end_time)
                
                # 排序和分页
                query = query.order_by(CommandExecutionLog.execution_time.desc())
                query = query.limit(limit)
                
                result = await session.execute(query)
                commands = result.scalars().all()
                
                return [
                    {
                        "id": cmd.id,
                        "ecu_id": cmd.ecu_id,
                        "command_id": cmd.command_id,
                        "command": cmd.command,
                        "params": cmd.params,
                        "result": cmd.result,
                        "execution_time": cmd.execution_time.isoformat(),
                        "success": cmd.success,
                        "error_message": cmd.error_message,
                        "execution_duration_ms": cmd.execution_duration_ms
                    }
                    for cmd in commands
                ]
                
        except SQLAlchemyError as e:
            logger.error(f"获取命令历史失败: {e}")
            raise
    
    # =============== 访问事件日志 ===============
    
    async def save_event(self, ecu_id: str, event_type: str, event_data: Dict) -> str:
        """保存事件日志"""
        try:
            event_log = {
                "id": str(uuid.uuid4()),
                "ecu_id": ecu_id,
                "event_type": event_type,
                "event_data": event_data,
                "timestamp": datetime.now(),
                "severity": event_data.get("severity", "info"),
                "location": event_data.get("location", "unknown")
            }
            
            # 使用批量写入器
            await self.batch_writer.add_event_log(event_log)
            
            logger.debug(f"保存事件日志: {ecu_id} - {event_type}")
            return event_log["id"]
            
        except Exception as e:
            logger.error(f"保存事件日志失败: {e}")
            raise
    
    async def get_event_logs(self, ecu_id: str,
                             event_type: Optional[str] = None,
                             start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None,
                             severity: Optional[str] = None,
                             limit: int = 100) -> List[Dict]:
        """获取事件日志"""
        try:
            async with self.get_session() as session:
                query = select(AccessEventLog).where(
                    AccessEventLog.ecu_id == ecu_id
                )
                
                # 过滤条件
                if event_type:
                    query = query.where(AccessEventLog.event_type == event_type)
                if start_time:
                    query = query.where(AccessEventLog.timestamp >= start_time)
                if end_time:
                    query = query.where(AccessEventLog.timestamp <= end_time)
                if severity:
                    query = query.where(AccessEventLog.severity == severity)
                
                # 排序和分页
                query = query.order_by(AccessEventLog.timestamp.desc())
                query = query.limit(limit)
                
                result = await session.execute(query)
                events = result.scalars().all()
                
                return [
                    {
                        "id": event.id,
                        "ecu_id": event.ecu_id,
                        "event_type": event.event_type,
                        "event_data": event.event_data,
                        "timestamp": event.timestamp.isoformat(),
                        "severity": event.severity,
                        "location": event.location
                    }
                    for event in events
                ]
                
        except SQLAlchemyError as e:
            logger.error(f"获取事件日志失败: {e}")
            raise
    
    # =============== 骑行记录（共享单车专用） ===============
    
    async def save_ride_record(self, ride_data: Dict) -> str:
        """保存骑行记录"""
        try:
            ride_record = {
                "id": str(uuid.uuid4()),
                "ride_id": ride_data.get("ride_id", f"ride_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
                "ecu_id": ride_data["ecu_id"],
                "user_id": ride_data["user_id"],
                "start_time": ride_data.get("start_time", datetime.now()),
                "end_time": ride_data.get("end_time", datetime.now()),
                "duration_seconds": ride_data.get("duration", 0),
                "distance_km": ride_data.get("distance", 0.0),
                "start_location": ride_data.get("start_location", {}),
                "end_location": ride_data.get("end_location", {}),
                "average_speed_kmh": ride_data.get("average_speed", 0.0),
                "calories_burned": ride_data.get("calories_burned", 0),
                "cost_amount": ride_data.get("cost", 0.0),
                "payment_status": ride_data.get("payment_status", "pending"),
                "battery_usage": ride_data.get("battery_usage", 0.0),
                "created_at": datetime.now()
            }
            
            # 使用批量写入器
            await self.batch_writer.add_ride_record(ride_record)
            
            logger.info(f"保存骑行记录: {ride_record['ride_id']}")
            return ride_record["id"]
            
        except Exception as e:
            logger.error(f"保存骑行记录失败: {e}")
            raise
    
    async def get_ride_history(self, ecu_id: str,
                               user_id: Optional[str] = None,
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None,
                               limit: int = 50) -> List[Dict]:
        """获取骑行历史"""
        try:
            async with self.get_session() as session:
                query = select(RideRecord).where(
                    RideRecord.ecu_id == ecu_id
                )
                
                # 过滤条件
                if user_id:
                    query = query.where(RideRecord.user_id == user_id)
                if start_date:
                    query = query.where(RideRecord.start_time >= start_date)
                if end_date:
                    query = query.where(RideRecord.start_time <= end_date)
                
                # 排序和分页
                query = query.order_by(RideRecord.start_time.desc())
                query = query.limit(limit)
                
                result = await session.execute(query)
                rides = result.scalars().all()
                
                return [
                    {
                        "id": ride.id,
                        "ride_id": ride.ride_id,
                        "ecu_id": ride.ecu_id,
                        "user_id": ride.user_id,
                        "start_time": ride.start_time.isoformat(),
                        "end_time": ride.end_time.isoformat() if ride.end_time else None,
                        "duration_seconds": ride.duration_seconds,
                        "distance_km": ride.distance_km,
                        "start_location": ride.start_location,
                        "end_location": ride.end_location,
                        "average_speed_kmh": ride.average_speed_kmh,
                        "calories_burned": ride.calories_burned,
                        "cost_amount": ride.cost_amount,
                        "payment_status": ride.payment_status,
                        "battery_usage": ride.battery_usage,
                        "created_at": ride.created_at.isoformat()
                    }
                    for ride in rides
                ]
                
        except SQLAlchemyError as e:
            logger.error(f"获取骑行历史失败: {e}")
            raise
    
    # =============== 统计和聚合 ===============
    
    async def get_device_statistics(self, device_type: Optional[str] = None) -> Dict:
        """获取设备统计信息"""
        try:
            async with self.get_session() as session:
                # 总设备数
                query_total = select(func.count(ECUDeviceModel.id)).where(
                    ECUDeviceModel.is_active == True
                )
                if device_type:
                    query_total = query_total.where(ECUDeviceModel.device_type == device_type)
                
                total_devices = await session.scalar(query_total)
                
                # 在线设备数
                one_minute_ago = datetime.now() - timedelta(minutes=1)
                query_online = select(func.count(HeartbeatLog.ecu_id.distinct())).where(
                    HeartbeatLog.timestamp >= one_minute_ago
                )
                online_devices = await session.scalar(query_online)
                
                # 设备类型分布
                query_distribution = select(
                    ECUDeviceModel.device_type,
                    func.count(ECUDeviceModel.id).label('count')
                ).where(
                    ECUDeviceModel.is_active == True
                ).group_by(
                    ECUDeviceModel.device_type
                )
                
                result = await session.execute(query_distribution)
                distribution = {row.device_type: row.count for row in result}
                
                return {
                    "total_devices": total_devices or 0,
                    "online_devices": online_devices or 0,
                    "offline_devices": (total_devices or 0) - (online_devices or 0),
                    "online_rate": (online_devices / total_devices * 100) if total_devices > 0 else 0,
                    "device_distribution": distribution,
                    "last_updated": datetime.now().isoformat()
                }
                
        except SQLAlchemyError as e:
            logger.error(f"获取设备统计失败: {e}")
            raise
    
    async def get_command_statistics(self, ecu_id: str, 
                                     start_time: Optional[datetime] = None,
                                     end_time: Optional[datetime] = None) -> Dict:
        """获取命令统计信息"""
        try:
            if not start_time:
                start_time = datetime.now() - timedelta(days=1)
            if not end_time:
                end_time = datetime.now()
            
            async with self.get_session() as session:
                # 命令总数
                query_total = select(func.count(CommandExecutionLog.id)).where(
                    CommandExecutionLog.ecu_id == ecu_id,
                    CommandExecutionLog.execution_time.between(start_time, end_time)
                )
                total_commands = await session.scalar(query_total) or 0
                
                # 成功命令数
                query_success = select(func.count(CommandExecutionLog.id)).where(
                    CommandExecutionLog.ecu_id == ecu_id,
                    CommandExecutionLog.success == True,
                    CommandExecutionLog.execution_time.between(start_time, end_time)
                )
                success_commands = await session.scalar(query_success) or 0
                
                # 命令类型分布
                query_distribution = select(
                    CommandExecutionLog.command,
                    func.count(CommandExecutionLog.id).label('count'),
                    func.avg(CommandExecutionLog.execution_duration_ms).label('avg_duration')
                ).where(
                    CommandExecutionLog.ecu_id == ecu_id,
                    CommandExecutionLog.execution_time.between(start_time, end_time)
                ).group_by(
                    CommandExecutionLog.command
                )
                
                result = await session.execute(query_distribution)
                command_distribution = {
                    row.command: {
                        "count": row.count,
                        "avg_duration_ms": float(row.avg_duration or 0)
                    }
                    for row in result
                }
                
                # 错误统计
                query_errors = select(
                    CommandExecutionLog.error_message,
                    func.count(CommandExecutionLog.id).label('count')
                ).where(
                    CommandExecutionLog.ecu_id == ecu_id,
                    CommandExecutionLog.success == False,
                    CommandExecutionLog.execution_time.between(start_time, end_time),
                    CommandExecutionLog.error_message.isnot(None)
                ).group_by(
                    CommandExecutionLog.error_message
                ).order_by(
                    func.count(CommandExecutionLog.id).desc()
                ).limit(10)
                
                error_result = await session.execute(query_errors)
                error_distribution = [
                    {"error_message": row.error_message, "count": row.count}
                    for row in error_result
                ]
                
                return {
                    "total_commands": total_commands,
                    "success_commands": success_commands,
                    "failed_commands": total_commands - success_commands,
                    "success_rate": (success_commands / total_commands * 100) if total_commands > 0 else 0,
                    "command_distribution": command_distribution,
                    "top_errors": error_distribution,
                    "period": {
                        "start": start_time.isoformat(),
                        "end": end_time.isoformat()
                    }
                }
                
        except SQLAlchemyError as e:
            logger.error(f"获取命令统计失败: {e}")
            raise
    
    # =============== 清理和维护 ===============
    
    async def cleanup_old_data(self, days_to_keep: int = 30) -> Dict[str, int]:
        """清理旧数据"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            async with self.get_session() as session:
                # 清理状态历史
                query_status = delete(ECUStatusHistory).where(
                    ECUStatusHistory.timestamp < cutoff_date
                )
                status_deleted = await session.execute(query_status)
                
                # 清理心跳日志
                query_heartbeat = delete(HeartbeatLog).where(
                    HeartbeatLog.timestamp < cutoff_date
                )
                heartbeat_deleted = await session.execute(query_heartbeat)
                
                # 清理命令日志
                query_command = delete(CommandExecutionLog).where(
                    CommandExecutionLog.execution_time < cutoff_date
                )
                command_deleted = await session.execute(query_command)
                
                # 清理事件日志（保留重要事件）
                query_event = delete(AccessEventLog).where(
                    AccessEventLog.timestamp < cutoff_date,
                    AccessEventLog.severity != "critical"
                )
                event_deleted = await session.execute(query_event)
                
                await session.commit()
                
                deleted_counts = {
                    "status_history": status_deleted.rowcount,
                    "heartbeat_logs": heartbeat_deleted.rowcount,
                    "command_logs": command_deleted.rowcount,
                    "event_logs": event_deleted.rowcount,
                    "total": (status_deleted.rowcount + heartbeat_deleted.rowcount + 
                             command_deleted.rowcount + event_deleted.rowcount)
                }
                
                logger.info(f"数据清理完成，删除记录: {deleted_counts}")
                return deleted_counts
                
        except SQLAlchemyError as e:
            logger.error(f"数据清理失败: {e}")
            raise
    
    async def close(self):
        """关闭数据库连接"""
        try:
            # 先刷新批量写入器
            await self.batch_writer.flush_all()
            
            # 关闭引擎
            await self.engine.dispose()
            logger.info("数据库连接已关闭")
        except Exception as e:
            logger.error(f"关闭数据库连接失败: {e}")
    
    # =============== 辅助方法 ===============
    
    def _model_to_dict(self, model) -> Dict:
        """将SQLAlchemy模型转换为字典"""
        result = {}
        for column in model.__table__.columns:
            value = getattr(model, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result
    
    async def health_check(self) -> Dict:
        """数据库健康检查"""
        try:
            async with self.get_session() as session:
                # 执行简单查询检查连接
                result = await session.execute(select(1))
                test_value = result.scalar()
                
                # 获取数据库统计
                device_count = await session.scalar(
                    select(func.count(ECUDeviceModel.id))
                ) or 0
                
                status_count = await session.scalar(
                    select(func.count(ECUStatusHistory.id))
                ) or 0
                
                return {
                    "status": "healthy",
                    "connected": True,
                    "test_query": test_value == 1,
                    "database_stats": {
                        "device_count": device_count,
                        "status_count": status_count,
                        "batch_queue_size": self.batch_writer.get_queue_sizes()
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"数据库健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }