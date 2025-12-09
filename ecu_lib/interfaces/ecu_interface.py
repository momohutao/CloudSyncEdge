"""
ECUInterface类 - 提供给成员B的统一接口
"""
import asyncio
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Callable, Awaitable
from abc import ABC, abstractmethod

from protocol.jsonrpc import JSONRPCRequest, JSONRPCResponse
from protocol.message_types import MessageTypes, ErrorCodes, DeviceStatus
from protocol.mock_codec import MockCodec

from ..core.base_ecu import BaseECU, ECUConfig, ECUStatus
from ..devices.device_registry import DeviceRegistry
from ..database.client import DatabaseClient

logger = logging.getLogger(__name__)


class ECUInterface(ABC):
    """ECU接口基类 - 定义ECU库对外提供的统一接口"""
    
    @abstractmethod
    async def execute_command(self, ecu_id: str, command: str, params: Dict) -> Dict:
        """
        执行ECU命令
        
        Args:
            ecu_id: 设备ID
            command: 命令类型
            params: 命令参数
            
        Returns:
            命令执行结果
        """
        pass
    
    @abstractmethod
    async def get_ecu_status(self, ecu_id: str) -> Dict:
        """
        获取ECU状态
        
        Args:
            ecu_id: 设备ID
            
        Returns:
            设备状态信息
        """
        pass
    
    @abstractmethod
    async def get_all_ecus(self) -> List[Dict]:
        """
        获取所有ECU设备
        
        Returns:
            设备列表
        """
        pass
    
    @abstractmethod
    async def register_ecu(self, ecu_data: Dict) -> Dict:
        """
        注册ECU设备
        
        Args:
            ecu_data: 设备数据
            
        Returns:
            注册结果
        """
        pass
    
    @abstractmethod
    async def unregister_ecu(self, ecu_id: str) -> bool:
        """
        注销ECU设备
        
        Args:
            ecu_id: 设备ID
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    async def start_ecu(self, ecu_id: str) -> bool:
        """
        启动ECU设备
        
        Args:
            ecu_id: 设备ID
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    async def stop_ecu(self, ecu_id: str) -> bool:
        """
        停止ECU设备
        
        Args:
            ecu_id: 设备ID
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    async def get_ecu_history(self, ecu_id: str, 
                              start_time: Optional[datetime] = None,
                              end_time: Optional[datetime] = None,
                              limit: int = 100) -> List[Dict]:
        """
        获取ECU历史记录
        
        Args:
            ecu_id: 设备ID
            start_time: 开始时间
            end_time: 结束时间
            limit: 限制条数
            
        Returns:
            历史记录列表
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict:
        """
        健康检查
        
        Returns:
            健康状态
        """
        pass


class DefaultECUInterface(ECUInterface):
    """默认ECU接口实现"""
    
    def __init__(self, device_registry: DeviceRegistry, db_client: Optional[DatabaseClient] = None):
        """
        初始化ECU接口
        
        Args:
            device_registry: 设备注册表
            db_client: 数据库客户端（可选）
        """
        self.device_registry = device_registry
        self.db_client = db_client
        self._command_executors = self._init_command_executors()
        
        logger.info("ECU接口初始化完成")
    
    def _init_command_executors(self) -> Dict[str, Callable]:
        """初始化命令执行器映射"""
        return {
            MessageTypes.STATUS_UPDATE: self._execute_status_update,
            MessageTypes.HEARTBEAT: self._execute_heartbeat,
            MessageTypes.GET_STATUS: self._execute_get_status,
            MessageTypes.LOCK: self._execute_lock,
            MessageTypes.UNLOCK: self._execute_unlock,
            MessageTypes.GET_CONFIG: self._execute_get_config,
            MessageTypes.UPDATE_CONFIG: self._execute_update_config,
            MessageTypes.REBOOT: self._execute_reboot,
            MessageTypes.FIRMWARE_UPDATE: self._execute_firmware_update,
            MessageTypes.DIAGNOSTIC: self._execute_diagnostic,
            MessageTypes.RESET: self._execute_reset,
            MessageTypes.UPLOAD_DATA: self._execute_upload_data,
            MessageTypes.DOWNLOAD_DATA: self._execute_download_data
        }
    
    # =============== 核心接口方法 ===============
    
    async def execute_command(self, ecu_id: str, command: str, params: Dict) -> Dict:
        """执行ECU命令"""
        try:
            logger.info(f"执行命令: {ecu_id} -> {command}")
            
            # 获取设备
            ecu = await self.device_registry.get_device(ecu_id)
            if not ecu:
                return self._create_error_response(
                    ErrorCodes.DEVICE_NOT_FOUND,
                    f"Device {ecu_id} not found"
                )
            
            # 检查设备状态
            if ecu.status == ECUStatus.OFFLINE:
                return self._create_error_response(
                    ErrorCodes.DEVICE_OFFLINE,
                    f"Device {ecu_id} is offline"
                )
            
            if ecu.status == ECUStatus.BUSY:
                return self._create_error_response(
                    ErrorCodes.DEVICE_BUSY,
                    f"Device {ecu_id} is busy"
                )
            
            # 查找命令执行器
            executor = self._command_executors.get(command)
            if not executor:
                # 使用设备的自定义命令处理
                return await ecu._execute_custom_command(command, params)
            
            # 执行命令
            result = await executor(ecu, params)
            
            # 记录命令执行
            if self.db_client:
                await self._log_command_execution(ecu_id, command, params, result)
            
            return result
            
        except Exception as e:
            logger.error(f"执行命令失败: {ecu_id} -> {command}: {e}")
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Command execution failed: {str(e)}"
            )
    
    async def get_ecu_status(self, ecu_id: str) -> Dict:
        """获取ECU状态"""
        try:
            ecu = await self.device_registry.get_device(ecu_id)
            if not ecu:
                return self._create_error_response(
                    ErrorCodes.DEVICE_NOT_FOUND,
                    f"Device {ecu_id} not found"
                )
            
            # 获取设备状态
            status = ecu.get_status_dict()
            
            # 从数据库获取额外信息
            if self.db_client:
                try:
                    # 获取最新状态历史
                    latest_status = await self.db_client.get_latest_ecu_status(ecu_id)
                    if latest_status:
                        status["db_status"] = latest_status
                    
                    # 获取心跳历史
                    heartbeats = await self.db_client.get_heartbeat_history(ecu_id, hours=1, limit=5)
                    status["recent_heartbeats"] = heartbeats
                    
                    # 获取命令统计
                    stats = await self.db_client.get_command_statistics(ecu_id)
                    status["command_stats"] = stats
                    
                except Exception as db_error:
                    logger.warning(f"获取数据库信息失败: {db_error}")
            
            return {
                "success": True,
                "ecu_id": ecu_id,
                "status": status,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取设备状态失败: {ecu_id}: {e}")
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Failed to get device status: {str(e)}"
            )
    
    async def get_all_ecus(self) -> List[Dict]:
        """获取所有ECU设备"""
        try:
            devices = await self.device_registry.list_devices()
            result = []
            
            for device_info in devices:
                ecu_id = device_info["ecu_id"]
                ecu = await self.device_registry.get_device(ecu_id)
                
                if ecu:
                    device_summary = {
                        "ecu_id": ecu_id,
                        "device_type": ecu.device_type,
                        "status": ecu.status.value,
                        "firmware_version": ecu.firmware_version,
                        "last_heartbeat": ecu._last_heartbeat.isoformat() if ecu._last_heartbeat else None,
                        "last_command": ecu._last_command.isoformat() if ecu._last_command else None,
                        "error_count": ecu._error_count,
                        "connected": device_info.get("connected", False),
                        "stats": ecu._stats.copy()
                    }
                    result.append(device_summary)
            
            return result
            
        except Exception as e:
            logger.error(f"获取所有设备失败: {e}")
            return []
    
    async def register_ecu(self, ecu_data: Dict) -> Dict:
        """注册ECU设备"""
        try:
            ecu_id = ecu_data.get("ecu_id")
            device_type = ecu_data.get("device_type")
            
            if not ecu_id or not device_type:
                return {
                    "success": False,
                    "error_code": ErrorCodes.INVALID_PARAMS,
                    "error_message": "ecu_id and device_type are required"
                }
            
            # 创建设备配置
            config = ECUConfig(
                ecu_id=ecu_id,
                device_type=device_type,
                firmware_version=ecu_data.get("firmware_version", "1.0.0"),
                heartbeat_interval=ecu_data.get("heartbeat_interval", 30),
                command_timeout=ecu_data.get("command_timeout", 10)
            )
            
            # 创建设备实例
            ecu = await self.device_registry.create_device(config, self.db_client)
            if not ecu:
                return {
                    "success": False,
                    "error_code": ErrorCodes.INTERNAL_ERROR,
                    "error_message": f"Failed to create device {ecu_id}"
                }
            
            # 启动设备
            await ecu.start()
            
            # 保存到数据库
            if self.db_client:
                await self.db_client.save_ecu_device({
                    "ecu_id": ecu_id,
                    "device_type": device_type,
                    "firmware_version": ecu.firmware_version,
                    "status": ecu.status.value,
                    "config": ecu.config.__dict__,
                    "created_at": datetime.now()
                })
            
            logger.info(f"ECU设备注册成功: {ecu_id} ({device_type})")
            
            return {
                "success": True,
                "ecu_id": ecu_id,
                "device_type": device_type,
                "status": ecu.status.value,
                "message": f"Device {ecu_id} registered successfully"
            }
            
        except Exception as e:
            logger.error(f"注册ECU设备失败: {e}")
            return {
                "success": False,
                "error_code": ErrorCodes.INTERNAL_ERROR,
                "error_message": f"Failed to register device: {str(e)}"
            }
    
    async def unregister_ecu(self, ecu_id: str) -> bool:
        """注销ECU设备"""
        try:
            # 停止设备
            await self.stop_ecu(ecu_id)
            
            # 从注册表中移除
            success = await self.device_registry.remove_device(ecu_id)
            
            if success and self.db_client:
                # 标记设备为已删除
                await self.db_client.delete_ecu_device(ecu_id)
            
            logger.info(f"ECU设备注销: {ecu_id} - {'成功' if success else '失败'}")
            return success
            
        except Exception as e:
            logger.error(f"注销ECU设备失败: {ecu_id}: {e}")
            return False
    
    async def start_ecu(self, ecu_id: str) -> bool:
        """启动ECU设备"""
        try:
            ecu = await self.device_registry.get_device(ecu_id)
            if not ecu:
                logger.error(f"无法启动不存在的设备: {ecu_id}")
                return False
            
            if ecu.status == ECUStatus.ONLINE:
                logger.warning(f"设备 {ecu_id} 已在线")
                return True
            
            await ecu.start()
            logger.info(f"ECU设备启动: {ecu_id}")
            return True
            
        except Exception as e:
            logger.error(f"启动ECU设备失败: {ecu_id}: {e}")
            return False
    
    async def stop_ecu(self, ecu_id: str) -> bool:
        """停止ECU设备"""
        try:
            ecu = await self.device_registry.get_device(ecu_id)
            if not ecu:
                logger.warning(f"无法停止不存在的设备: {ecu_id}")
                return False
            
            if ecu.status == ECUStatus.OFFLINE:
                logger.warning(f"设备 {ecu_id} 已离线")
                return True
            
            await ecu.stop()
            logger.info(f"ECU设备停止: {ecu_id}")
            return True
            
        except Exception as e:
            logger.error(f"停止ECU设备失败: {ecu_id}: {e}")
            return False
    
    async def get_ecu_history(self, ecu_id: str, 
                              start_time: Optional[datetime] = None,
                              end_time: Optional[datetime] = None,
                              limit: int = 100) -> List[Dict]:
        """获取ECU历史记录"""
        try:
            if not self.db_client:
                return []
            
            # 获取状态历史
            status_history = await self.db_client.get_ecu_status_history(
                ecu_id, start_time, end_time, limit
            )
            
            # 获取命令历史
            command_history = await self.db_client.get_command_history(
                ecu_id, start_time=start_time, end_time=end_time, limit=limit
            )
            
            # 获取事件日志
            event_logs = await self.db_client.get_event_logs(
                ecu_id, start_time=start_time, end_time=end_time, limit=limit
            )
            
            # 合并历史记录
            history = []
            
            # 添加状态记录
            for status in status_history:
                history.append({
                    "type": "status",
                    "timestamp": status["timestamp"],
                    "data": status["status_data"]
                })
            
            # 添加命令记录
            for command in command_history:
                history.append({
                    "type": "command",
                    "timestamp": command["execution_time"],
                    "data": {
                        "command": command["command"],
                        "success": command["success"],
                        "result": command["result"]
                    }
                })
            
            # 添加事件记录
            for event in event_logs:
                history.append({
                    "type": "event",
                    "timestamp": event["timestamp"],
                    "data": {
                        "event_type": event["event_type"],
                        "severity": event["severity"],
                        "event_data": event["event_data"]
                    }
                })
            
            # 按时间排序
            history.sort(key=lambda x: x["timestamp"], reverse=True)
            
            # 限制返回数量
            return history[:limit]
            
        except Exception as e:
            logger.error(f"获取设备历史失败: {ecu_id}: {e}")
            return []
    
    async def health_check(self) -> Dict:
        """健康检查"""
        try:
            # 检查设备注册表
            device_count = await self.device_registry.count_devices()
            devices_health = device_count >= 0
            
            # 检查数据库连接
            db_health = True
            if self.db_client:
                try:
                    db_status = await self.db_client.health_check()
                    db_health = db_status.get("status") == "healthy"
                except Exception as e:
                    logger.warning(f"数据库健康检查失败: {e}")
                    db_health = False
            
            # 检查所有设备状态
            devices = await self.device_registry.list_devices()
            online_count = 0
            device_statuses = []
            
            for device_info in devices:
                ecu_id = device_info["ecu_id"]
                ecu = await self.device_registry.get_device(ecu_id)
                
                if ecu:
                    status_info = {
                        "ecu_id": ecu_id,
                        "status": ecu.status.value,
                        "online": ecu.status == ECUStatus.ONLINE,
                        "error_count": ecu._error_count
                    }
                    device_statuses.append(status_info)
                    
                    if ecu.status == ECUStatus.ONLINE:
                        online_count += 1
            
            overall_health = devices_health and db_health
            
            return {
                "status": "healthy" if overall_health else "degraded",
                "timestamp": datetime.now().isoformat(),
                "components": {
                    "device_registry": "ok" if devices_health else "error",
                    "database": "ok" if db_health else "error"
                },
                "statistics": {
                    "total_devices": device_count,
                    "online_devices": online_count,
                    "offline_devices": device_count - online_count,
                    "online_rate": (online_count / device_count * 100) if device_count > 0 else 0
                },
                "device_statuses": device_statuses
            }
            
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    # =============== 命令执行器 ===============
    
    async def _execute_status_update(self, ecu: BaseECU, params: Dict) -> Dict:
        """执行状态更新命令"""
        try:
            # 获取当前状态
            status = ecu.get_status_dict()
            
            # 更新参数
            update_params = params.get("status", {})
            if update_params:
                for key, value in update_params.items():
                    ecu.set_attribute(key, value)
            
            # 保存状态到数据库
            if self.db_client:
                await self.db_client.save_ecu_status(ecu.ecu_id, status)
            
            return {
                "success": True,
                "message": "Status updated",
                "status": status,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"状态更新失败: {ecu.ecu_id}: {e}")
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Status update failed: {str(e)}"
            )
    
    async def _execute_heartbeat(self, ecu: BaseECU, params: Dict) -> Dict:
        """执行心跳命令"""
        try:
            # 更新最后心跳时间
            ecu._last_heartbeat = datetime.now()
            ecu._stats["heartbeats_sent"] += 1
            
            # 保存心跳记录
            heartbeat_data = {
                "ecu_id": ecu.ecu_id,
                "timestamp": ecu._last_heartbeat.isoformat(),
                "status": ecu.status.value,
                "uptime": (datetime.now() - ecu._stats["uptime_start"]).total_seconds()
            }
            
            if self.db_client:
                await self.db_client.save_heartbeat(ecu.ecu_id, heartbeat_data)
            
            return {
                "success": True,
                "message": "Heartbeat received",
                "heartbeat": heartbeat_data
            }
            
        except Exception as e:
            logger.error(f"心跳处理失败: {ecu.ecu_id}: {e}")
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Heartbeat processing failed: {str(e)}"
            )
    
    async def _execute_get_status(self, ecu: BaseECU, params: Dict) -> Dict:
        """执行获取状态命令"""
        try:
            detailed = params.get("detailed", False)
            include_history = params.get("include_history", False)
            
            # 获取设备状态
            result = await ecu._execute_get_status(params)
            
            # 添加额外信息
            if result.get("success"):
                status_data = result.get("status", {})
                
                # 添加数据库信息
                if self.db_client and include_history:
                    try:
                        history = await self.db_client.get_ecu_status_history(
                            ecu.ecu_id, limit=10
                        )
                        status_data["recent_history"] = history
                    except Exception as e:
                        logger.warning(f"获取历史记录失败: {e}")
                
                # 添加统计信息
                if detailed:
                    status_data["stats"] = ecu._stats.copy()
                    status_data["errors"] = list(ecu._errors)[-10:] if ecu._errors else []
            
            return result
            
        except Exception as e:
            logger.error(f"获取状态失败: {ecu.ecu_id}: {e}")
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Get status failed: {str(e)}"
            )
    
    async def _execute_lock(self, ecu: BaseECU, params: Dict) -> Dict:
        """执行锁定命令"""
        try:
            # 调用设备特定的锁定方法
            result = await ecu._execute_lock(params)
            
            # 记录锁定事件
            if result.get("success") and self.db_client:
                event_data = {
                    "ecu_id": ecu.ecu_id,
                    "command": "lock",
                    "params": params,
                    "result": result,
                    "timestamp": datetime.now()
                }
                await self.db_client.save_event(ecu.ecu_id, "lock", event_data)
            
            return result
            
        except Exception as e:
            logger.error(f"锁定失败: {ecu.ecu_id}: {e}")
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Lock failed: {str(e)}"
            )
    
    async def _execute_unlock(self, ecu: BaseECU, params: Dict) -> Dict:
        """执行解锁命令"""
        try:
            # 调用设备特定的解锁方法
            result = await ecu._execute_unlock(params)
            
            # 记录解锁事件
            if result.get("success") and self.db_client:
                event_data = {
                    "ecu_id": ecu.ecu_id,
                    "command": "unlock",
                    "params": params,
                    "result": result,
                    "timestamp": datetime.now()
                }
                await self.db_client.save_event(ecu.ecu_id, "unlock", event_data)
            
            return result
            
        except Exception as e:
            logger.error(f"解锁失败: {ecu.ecu_id}: {e}")
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Unlock failed: {str(e)}"
            )
    
    async def _execute_get_config(self, ecu: BaseECU, params: Dict) -> Dict:
        """执行获取配置命令"""
        try:
            config_keys = params.get("config_keys", [])
            
            config_data = {}
            
            if not config_keys or "general" in config_keys:
                config_data["general"] = {
                    "device_type": ecu.device_type,
                    "firmware_version": ecu.firmware_version,
                    "heartbeat_interval": ecu.config.heartbeat_interval,
                    "command_timeout": ecu.config.command_timeout
                }
            
            if not config_keys or "attributes" in config_keys:
                config_data["attributes"] = ecu._attributes.copy()
            
            return {
                "success": True,
                "config": config_data,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取配置失败: {ecu.ecu_id}: {e}")
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Get config failed: {str(e)}"
            )
    
    async def _execute_update_config(self, ecu: BaseECU, params: Dict) -> Dict:
        """执行更新配置命令"""
        try:
            config = params.get("config", {})
            
            # 更新配置
            for key, value in config.items():
                if hasattr(ecu.config, key):
                    setattr(ecu.config, key, value)
                else:
                    ecu.set_attribute(key, value)
            
            # 如果是心跳间隔更新，需要重启心跳任务
            if "heartbeat_interval" in config:
                ecu.config.heartbeat_interval = config["heartbeat_interval"]
            
            return {
                "success": True,
                "message": "Configuration updated",
                "updated_config": config,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"更新配置失败: {ecu.ecu_id}: {e}")
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Update config failed: {str(e)}"
            )
    
    async def _execute_reboot(self, ecu: BaseECU, params: Dict) -> Dict:
        """执行重启命令"""
        try:
            result = await ecu._execute_reboot(params)
            
            # 记录重启事件
            if result.get("success") and self.db_client:
                event_data = {
                    "ecu_id": ecu.ecu_id,
                    "command": "reboot",
                    "params": params,
                    "result": result,
                    "timestamp": datetime.now()
                }
                await self.db_client.save_event(ecu.ecu_id, "reboot", event_data)
            
            return result
            
        except Exception as e:
            logger.error(f"重启失败: {ecu.ecu_id}: {e}")
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Reboot failed: {str(e)}"
            )
    
    async def _execute_firmware_update(self, ecu: BaseECU, params: Dict) -> Dict:
        """执行固件更新命令"""
        try:
            result = await ecu._execute_firmware_update(params)
            
            # 记录固件更新事件
            if result.get("success") and self.db_client:
                event_data = {
                    "ecu_id": ecu.ecu_id,
                    "command": "firmware_update",
                    "params": params,
                    "result": result,
                    "timestamp": datetime.now()
                }
                await self.db_client.save_event(ecu.ecu_id, "firmware_update", event_data)
            
            return result
            
        except Exception as e:
            logger.error(f"固件更新失败: {ecu.ecu_id}: {e}")
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Firmware update failed: {str(e)}"
            )
    
    async def _execute_diagnostic(self, ecu: BaseECU, params: Dict) -> Dict:
        """执行诊断命令"""
        try:
            diagnostics = await ecu.get_diagnostics()
            
            # 添加数据库诊断信息
            if self.db_client:
                try:
                    db_stats = await self.db_client.get_device_statistics()
                    diagnostics["database_stats"] = db_stats
                except Exception as e:
                    diagnostics["database_stats_error"] = str(e)
            
            return {
                "success": True,
                "diagnostics": diagnostics,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"诊断失败: {ecu.ecu_id}: {e}")
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Diagnostic failed: {str(e)}"
            )
    
    async def _execute_reset(self, ecu: BaseECU, params: Dict) -> Dict:
        """执行重置命令"""
        try:
            reset_type = params.get("type", "soft")
            
            if reset_type == "soft":
                # 软重置：重启设备
                return await self._execute_reboot(ecu, params)
            elif reset_type == "hard":
                # 硬重置：恢复出厂设置
                ecu._attributes.clear()
                ecu._error_count = 0
                ecu._errors.clear()
                
                # 重置统计信息
                ecu._stats = {
                    "commands_received": 0,
                    "commands_executed": 0,
                    "commands_failed": 0,
                    "heartbeats_sent": 0,
                    "errors": 0,
                    "uptime_start": datetime.now(),
                    "total_uptime": 0.0,
                    "last_reset": datetime.now()
                }
                
                return {
                    "success": True,
                    "message": "Factory reset completed",
                    "reset_type": "hard",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return self._create_error_response(
                    ErrorCodes.INVALID_PARAMS,
                    f"Invalid reset type: {reset_type}"
                )
                
        except Exception as e:
            logger.error(f"重置失败: {ecu.ecu_id}: {e}")
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Reset failed: {str(e)}"
            )
    
    async def _execute_upload_data(self, ecu: BaseECU, params: Dict) -> Dict:
        """执行上传数据命令"""
        try:
            data_type = params.get("data_type")
            data = params.get("data", {})
            
            if not data_type:
                return self._create_error_response(
                    ErrorCodes.INVALID_PARAMS,
                    "data_type is required"
                )
            
            # 保存数据到数据库
            if self.db_client:
                event_data = {
                    "data_type": data_type,
                    "data": data,
                    "size_bytes": len(str(data)),
                    "uploaded_at": datetime.now()
                }
                
                await self.db_client.save_event(ecu.ecu_id, f"upload_{data_type}", event_data)
            
            return {
                "success": True,
                "message": f"Data uploaded successfully",
                "data_type": data_type,
                "data_size": len(str(data)),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"上传数据失败: {ecu.ecu_id}: {e}")
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Upload data failed: {str(e)}"
            )
    
    async def _execute_download_data(self, ecu: BaseECU, params: Dict) -> Dict:
        """执行下载数据命令"""
        try:
            data_type = params.get("data_type")
            
            if not data_type:
                return self._create_error_response(
                    ErrorCodes.INVALID_PARAMS,
                    "data_type is required"
                )
            
            # 从数据库获取数据
            if self.db_client:
                try:
                    # 获取相关事件日志
                    events = await self.db_client.get_event_logs(
                        ecu.ecu_id, 
                        event_type=f"upload_{data_type}",
                        limit=50
                    )
                    
                    data = [event["event_data"] for event in events]
                    
                    return {
                        "success": True,
                        "data_type": data_type,
                        "data": data,
                        "count": len(data),
                        "timestamp": datetime.now().isoformat()
                    }
                    
                except Exception as db_error:
                    return self._create_error_response(
                        ErrorCodes.INTERNAL_ERROR,
                        f"Failed to retrieve data: {str(db_error)}"
                    )
            else:
                return self._create_error_response(
                    ErrorCodes.RESOURCE_UNAVAILABLE,
                    "Database not available for data retrieval"
                )
                
        except Exception as e:
            logger.error(f"下载数据失败: {ecu.ecu_id}: {e}")
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Download data failed: {str(e)}"
            )
    
    # =============== 辅助方法 ===============
    
    def _create_error_response(self, error_code: int, error_message: str) -> Dict:
        """创建错误响应"""
        return {
            "success": False,
            "error_code": error_code,
            "error_message": error_message,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _log_command_execution(self, ecu_id: str, command: str, params: Dict, result: Dict):
        """记录命令执行"""
        try:
            if self.db_client:
                execution_data = {
                    "ecu_id": ecu_id,
                    "command": command,
                    "params": params,
                    "result": result,
                    "execution_time": datetime.now(),
                    "success": result.get("success", False),
                    "error_message": result.get("error_message"),
                    "error_code": result.get("error_code"),
                    "execution_duration_ms": 0  # 可以添加计时逻辑
                }
                
                await self.db_client.save_command_execution(execution_data)
                
        except Exception as e:
            logger.error(f"记录命令执行失败: {e}")
    
    # =============== 批量操作 ===============
    
    async def batch_execute_commands(self, commands: List[Dict]) -> List[Dict]:
        """批量执行命令"""
        try:
            results = []
            
            for command in commands:
                ecu_id = command.get("ecu_id")
                cmd = command.get("command")
                params = command.get("params", {})
                
                if not ecu_id or not cmd:
                    results.append({
                        "success": False,
                        "error_code": ErrorCodes.INVALID_PARAMS,
                        "error_message": "ecu_id and command are required"
                    })
                    continue
                
                # 执行单个命令
                result = await self.execute_command(ecu_id, cmd, params)
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"批量执行命令失败: {e}")
            return [self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Batch command execution failed: {str(e)}"
            )]
    
    async def batch_get_status(self, ecu_ids: List[str]) -> Dict[str, Dict]:
        """批量获取状态"""
        try:
            status_map = {}
            
            for ecu_id in ecu_ids:
                status = await self.get_ecu_status(ecu_id)
                status_map[ecu_id] = status
            
            return status_map
            
        except Exception as e:
            logger.error(f"批量获取状态失败: {e}")
            return {}