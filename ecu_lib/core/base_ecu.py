"""
ECU基类 - 所有ECU设备的抽象基类
"""
import asyncio
import uuid
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable
from collections import deque

# 导入D成员的协议
from protocol.jsonrpc import JSONRPCRequest, JSONRPCResponse
from protocol.message_types import MessageTypes, ErrorCodes, DeviceStatus as ProtocolDeviceStatus

logger = logging.getLogger(__name__)


class ECUStatus(Enum):
    """ECU状态枚举"""
    OFFLINE = "offline"
    ONLINE = "online"
    ERROR = "error"
    UPDATING = "updating"
    MAINTENANCE = "maintenance"
    BUSY = "busy"


class ECUCommand(Enum):
    """ECU命令枚举"""
    STATUS_REPORT = "status_report"
    LOCK = "lock"
    UNLOCK = "unlock"
    REBOOT = "reboot"
    UPDATE = "update"
    DIAGNOSTIC = "diagnostic"
    CONFIG_UPDATE = "config_update"


@dataclass
class ECUConfig:
    """ECU配置"""
    ecu_id: str
    device_type: str
    firmware_version: str = "1.0.0"
    heartbeat_interval: int = 30
    reconnect_attempts: int = 3
    reconnect_delay: float = 1.0
    command_timeout: int = 10
    max_command_queue: int = 100
    enable_logging: bool = True


class CommandResult:
    """命令执行结果"""
    
    def __init__(self, success: bool, data: Optional[Dict] = None, 
                 error_code: Optional[int] = None, error_message: Optional[str] = None):
        self.success = success
        self.data = data or {}
        self.error_code = error_code
        self.error_message = error_message
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "data": self.data,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat()
        }


class BaseECU(ABC):
    """ECU基类 - 所有ECU设备必须继承此类"""
    
    def __init__(self, config: ECUConfig, db_client = None):
        self.config = config
        self.ecu_id = config.ecu_id
        self.device_type = config.device_type
        self.firmware_version = config.firmware_version
        
        # 数据库客户端
        self.db_client = db_client
        
        # 状态管理
        self._status = ECUStatus.OFFLINE
        self._last_heartbeat: Optional[datetime] = None
        self._last_command: Optional[datetime] = None
        self._last_status_update: Optional[datetime] = None
        self._error_count = 0
        self._errors = deque(maxlen=100)  # 保存最近100个错误
        
        # 命令队列
        self._command_queue = asyncio.Queue(maxsize=config.max_command_queue)
        self._processing_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        # 回调函数
        self._status_callbacks: List[Callable[[Dict], Awaitable[None]]] = []
        # status_callbacks 是一个列表，存放所有状态回调函数
        # 每个回调函数必须：
        # 1. 接受一个字典参数
        # 2. 是异步函数（async def）
        # 3. 不返回值（返回 None）

        self._command_callbacks: List[Callable[[Dict], Awaitable[None]]] = []
        
        # 统计信息
        self._stats = {
            "commands_received": 0,
            "commands_executed": 0,
            "commands_failed": 0,
            "heartbeats_sent": 0,
            "errors": 0,
            "uptime_start": datetime.now(),
            "total_uptime": 0.0,
            "last_reset": datetime.now()
        }
        
        # 设备属性
        self._attributes: Dict[str, Any] = {}
        
        logger.info(f"ECU {self.ecu_id} ({self.device_type}) initialized")
    
    @property
    def status(self) -> ECUStatus:
        """获取当前状态"""
        return self._status
    
    @status.setter
    def status(self, value: ECUStatus):
        """设置状态并触发回调"""
        old_status = self._status
        self._status = value
        
        if old_status != value:
            logger.info(f"ECU {self.ecu_id} status changed: {old_status.value} -> {value.value}")
            self._notify_status_change()
    
    async def _notify_status_change(self):
        """通知状态变更"""
        status_info = self.get_status_dict()
        
        # 保存到数据库
        if self.db_client and self.config.enable_logging:
            try:
                await self.db_client.save_ecu_status(self.ecu_id, status_info)
            except Exception as e:
                logger.error(f"保存状态到数据库失败: {e}")
        
        # 调用回调函数
        for callback in self._status_callbacks:
            try:
                await callback(status_info)
            except Exception as e:
                logger.error(f"状态回调执行失败: {e}")
    
    def get_status_dict(self) -> Dict[str, Any]:
        """获取状态字典"""
        uptime = (datetime.now() - self._stats["uptime_start"]).total_seconds()
        
        return {
            "ecu_id": self.ecu_id,
            "device_type": self.device_type,
            "status": self.status.value,
            "firmware_version": self.firmware_version,
            "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
            "last_command": self._last_command.isoformat() if self._last_command else None,
            "last_status_update": self._last_status_update.isoformat() if self._last_status_update else None,
            "error_count": self._error_count,
            "uptime": uptime,
            "attributes": self._attributes.copy(),
            "timestamp": datetime.now().isoformat()
        }
    
    def add_status_callback(self, callback: Callable[[Dict], Awaitable[None]]):
        """添加状态回调"""
        self._status_callbacks.append(callback)
    
    def add_command_callback(self, callback: Callable[[Dict], Awaitable[None]]):
        """添加命令回调"""
        self._command_callbacks.append(callback)
    
    async def start(self):
        """启动ECU"""
        if self._processing_task is None:
            self.status = ECUStatus.ONLINE
            self._processing_task = asyncio.create_task(self._process_commands())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info(f"ECU {self.ecu_id} started")
    
    async def stop(self):
        """停止ECU"""
        self.status = ECUStatus.OFFLINE
        
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
            self._processing_task = None
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        
        logger.info(f"ECU {self.ecu_id} stopped")
    
    async def execute_command(self, command: str, params: Optional[Dict] = None) -> Dict:
        """执行命令（异步）"""
        self._stats["commands_received"] += 1
        
        try:
            # 检查设备状态
            if self.status == ECUStatus.OFFLINE:
                return self._create_error_response(
                    ErrorCodes.DEVICE_OFFLINE,
                    "Device is offline"
                )
            
            if self.status == ECUStatus.BUSY:
                return self._create_error_response(
                    ErrorCodes.DEVICE_BUSY,
                    "Device is busy"
                )
            
            # 将命令加入队列
            command_id = str(uuid.uuid4())
            command_data = {
                "command_id": command_id,
                "command": command,
                "params": params or {},
                "timestamp": datetime.now(),
                "status": "pending"
            }
            
            await self._command_queue.put(command_data)
            
            # 等待命令执行完成
            timeout = self.config.command_timeout
            try:
                result = await asyncio.wait_for(
                    self._wait_for_command_result(command_id),
                    timeout=timeout
                )
                return result
            except asyncio.TimeoutError:
                return self._create_error_response(
                    ErrorCodes.COMMAND_TIMEOUT,
                    f"Command timeout after {timeout}s"
                )
                
        except Exception as e:
            logger.error(f"执行命令失败: {e}")
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Command execution failed: {str(e)}"
            )
    
    async def _wait_for_command_result(self, command_id: str) -> Dict:
        """等待命令结果"""
        # 这里可以扩展为使用事件或回调机制
        # 简化实现：直接执行命令
        try:
            # 从队列中获取命令
            command_data = await self._command_queue.get()
            
            # 执行命令
            result = await self._execute_single_command(command_data)
            
            # 标记任务完成
            self._command_queue.task_done()
            
            return result
        except Exception as e:
            logger.error(f"等待命令结果失败: {e}")
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Failed to wait for command result: {str(e)}"
            )
    
    async def _execute_single_command(self, command_data: Dict) -> Dict:
        """执行单个命令"""
        command = command_data["command"]
        params = command_data["params"]
        
        self._last_command = datetime.now()
        
        try:
            # 根据命令类型执行
            if command == MessageTypes.LOCK:
                result = await self._execute_lock(params)
            elif command == MessageTypes.UNLOCK:
                result = await self._execute_unlock(params)
            elif command == MessageTypes.GET_STATUS:
                result = await self._execute_get_status(params)
            elif command == MessageTypes.UPDATE_CONFIG:
                result = await self._execute_update_config(params)
            elif command == MessageTypes.REBOOT:
                result = await self._execute_reboot(params)
            elif command == MessageTypes.FIRMWARE_UPDATE:
                result = await self._execute_firmware_update(params)
            else:
                result = await self._execute_custom_command(command, params)
            
            # 更新统计信息
            if result.get("success", False):
                self._stats["commands_executed"] += 1
            else:
                self._stats["commands_failed"] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"命令执行异常: {e}")
            self._stats["commands_failed"] += 1
            self._error_count += 1
            self._errors.append({
                "timestamp": datetime.now(),
                "command": command,
                "error": str(e)
            })
            
            return self._create_error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Command execution exception: {str(e)}"
            )
    
    @abstractmethod
    async def _execute_lock(self, params: Dict) -> Dict:
        """执行锁定命令"""
        pass
    
    @abstractmethod
    async def _execute_unlock(self, params: Dict) -> Dict:
        """执行解锁命令"""
        pass
    
    @abstractmethod
    async def _execute_get_status(self, params: Dict) -> Dict:
        """执行获取状态命令"""
        pass
    
    async def _execute_update_config(self, params: Dict) -> Dict:
        """执行更新配置命令"""
        try:
            config = params.get("config", {})
            self._attributes.update(config)
            
            return {
                "success": True,
                "message": "Configuration updated",
                "config": self._attributes.copy()
            }
        except Exception as e:
            return {
                "success": False,
                "error_code": ErrorCodes.INVALID_PARAMS,
                "error_message": f"Invalid configuration: {str(e)}"
            }
    
    async def _execute_reboot(self, params: Dict) -> Dict:
        """执行重启命令"""
        try:
            # 停止ECU
            await self.stop()
            
            # 等待重启延迟
            delay = params.get("delay", 3)
            await asyncio.sleep(delay)
            
            # 重新启动ECU
            await self.start()
            
            return {
                "success": True,
                "message": f"Device rebooted after {delay}s delay",
                "new_status": self.status.value
            }
        except Exception as e:
            return {
                "success": False,
                "error_code": ErrorCodes.INTERNAL_ERROR,
                "error_message": f"Reboot failed: {str(e)}"
            }
    
    async def _execute_firmware_update(self, params: Dict) -> Dict:
        """执行固件更新命令"""
        try:
            self.status = ECUStatus.UPDATING
            
            # 模拟固件更新过程
            version = params.get("version", "")
            logger.info(f"Starting firmware update to version {version}")
            
            # 模拟更新过程
            await asyncio.sleep(5)  # 模拟下载
            await asyncio.sleep(3)  # 模拟安装
            
            self.firmware_version = version
            self.status = ECUStatus.ONLINE
            
            return {
                "success": True,
                "message": f"Firmware updated to {version}",
                "new_version": version
            }
        except Exception as e:
            self.status = ECUStatus.ERROR
            return {
                "success": False,
                "error_code": ErrorCodes.FIRMWARE_ERROR,
                "error_message": f"Firmware update failed: {str(e)}"
            }
    
    async def _execute_custom_command(self, command: str, params: Dict) -> Dict:
        """执行自定义命令"""
        # 子类可以重写此方法以支持更多命令
        return {
            "success": False,
            "error_code": ErrorCodes.METHOD_NOT_FOUND,
            "error_message": f"Command '{command}' not supported"
        }
    
    async def _process_commands(self):
        """处理命令队列"""
        logger.info(f"ECU {self.ecu_id} command processor started")
        
        try:
            while self.status != ECUStatus.OFFLINE:
                try:
                    # 非阻塞获取命令
                    command_data = await asyncio.wait_for(
                        self._command_queue.get(),
                        timeout=0.5
                    )
                    
                    # 执行命令
                    result = await self._execute_single_command(command_data)
                    
                    # 记录命令执行结果
                    self._record_command_execution(command_data, result)
                    
                    # 标记任务完成
                    self._command_queue.task_done()
                    
                except asyncio.TimeoutError:
                    # 超时继续循环
                    continue
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"处理命令失败: {e}")
                    continue
                    
        except asyncio.CancelledError:
            logger.info(f"ECU {self.ecu_id} command processor cancelled")
        except Exception as e:
            logger.error(f"命令处理器异常退出: {e}")
        finally:
            logger.info(f"ECU {self.ecu_id} command processor stopped")
    
    async def _heartbeat_loop(self):
        """心跳循环"""
        logger.info(f"ECU {self.ecu_id} heartbeat loop started")
        
        interval = self.config.heartbeat_interval
        
        try:
            while self.status != ECUStatus.OFFLINE:
                await asyncio.sleep(interval)
                
                if self.status == ECUStatus.ONLINE:
                    await self._send_heartbeat()
                    
        except asyncio.CancelledError:
            logger.info(f"ECU {self.ecu_id} heartbeat loop cancelled")
        except Exception as e:
            logger.error(f"心跳循环异常: {e}")
        finally:
            logger.info(f"ECU {self.ecu_id} heartbeat loop stopped")
    
    async def _send_heartbeat(self):
        """发送心跳"""
        try:
            self._last_heartbeat = datetime.now()
            self._stats["heartbeats_sent"] += 1
            
            # 更新总运行时间
            uptime = (datetime.now() - self._stats["uptime_start"]).total_seconds()
            self._stats["total_uptime"] = uptime
            
            # 创建心跳数据
            heartbeat_data = {
                "ecu_id": self.ecu_id,
                "timestamp": self._last_heartbeat.isoformat(),
                "status": self.status.value,
                "uptime": uptime,
                "stats": self._stats.copy()
            }
            
            # 保存到数据库
            if self.db_client and self.config.enable_logging:
                try:
                    await self.db_client.save_heartbeat(self.ecu_id, heartbeat_data)
                except Exception as e:
                    logger.error(f"保存心跳到数据库失败: {e}")
            
            # 发送心跳通知（如果有回调）
            for callback in self._command_callbacks:
                try:
                    await callback({
                        "type": "heartbeat",
                        "data": heartbeat_data
                    })
                except Exception as e:
                    logger.error(f"心跳回调执行失败: {e}")
            
            logger.debug(f"ECU {self.ecu_id} heartbeat sent")
            
        except Exception as e:
            logger.error(f"发送心跳失败: {e}")
            self._error_count += 1
    
    def _create_error_response(self, error_code: int, error_message: str) -> Dict:
        """创建错误响应"""
        self._stats["errors"] += 1
        self._error_count += 1
        
        return {
            "success": False,
            "error_code": error_code,
            "error_message": error_message,
            "timestamp": datetime.now().isoformat()
        }
    
    def _record_command_execution(self, command_data: Dict, result: Dict):
        """记录命令执行"""
        # 可以扩展为保存到数据库或日志
        if self.db_client and self.config.enable_logging:
            execution_record = {
                "command_id": command_data.get("command_id"),
                "ecu_id": self.ecu_id,
                "command": command_data.get("command"),
                "params": command_data.get("params", {}),
                "result": result,
                "execution_time": datetime.now(),
                "success": result.get("success", False)
            }
            
            # 异步保存执行记录
            asyncio.create_task(
                self.db_client.save_command_execution(execution_record)
            )
    
    async def get_diagnostics(self) -> Dict:
        """获取诊断信息"""
        return {
            "ecu_id": self.ecu_id,
            "device_type": self.device_type,
            "status": self.status.value,
            "firmware_version": self.firmware_version,
            "stats": self._stats.copy(),
            "error_count": self._error_count,
            "recent_errors": list(self._errors),
            "command_queue_size": self._command_queue.qsize(),
            "attributes": self._attributes.copy(),
            "timestamp": datetime.now().isoformat()
        }
    
    def set_attribute(self, key: str, value: Any):
        """设置设备属性"""
        self._attributes[key] = value
    
    def get_attribute(self, key: str, default: Any = None) -> Any:
        """获取设备属性"""
        return self._attributes.get(key, default)
    
    def __del__(self):
        """析构函数"""
        try:
            if self._processing_task and not self._processing_task.done():
                self._processing_task.cancel()
            if self._heartbeat_task and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
        except:
            pass