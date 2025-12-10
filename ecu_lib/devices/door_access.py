"""
门禁ECU设备实现
"""
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
import logging

from ..core.base_ecu import BaseECU, ECUConfig, CommandResult
from ...src.protocol.message_types import MessageTypes, ErrorCodes, DeviceTypes

logger = logging.getLogger(__name__)


class DoorAccessECU(BaseECU):
    """门禁系统ECU设备"""
    
    def __init__(self, config: ECUConfig, db_client=None):
        # 设置设备类型为门禁
        config.device_type = DeviceTypes.ACCESS_CONTROL
        super().__init__(config, db_client)
        
        # 门禁特定属性
        self._is_locked = True  # 门是否锁定
        self._is_open = False  # 门是否打开
        self._access_mode = "card"  # 访问模式：card, pin, facial, remote
        self._last_access_time = None  # 最后访问时间
        self._access_logs = []  # 访问日志
        
        # 安全设置
        self._security_level = "medium"  # low, medium, high
        self._unauthorized_attempts = 0  # 未授权尝试次数
        self._alarm_triggered = False  # 警报是否触发
        
        # 传感器数据
        self._temperature = 22.5  # 温度
        self._humidity = 45.0  # 湿度
        self._light_level = 75  # 光照强度（0-100）
        self._motion_detected = False  # 是否检测到运动
        
        # 硬件状态
        self._door_sensor_status = "normal"  # 门传感器状态
        self._lock_mechanism_status = "normal"  # 锁机构状态
        self._camera_status = "normal"  # 摄像头状态
        
        # 授权列表
        self._authorized_users = {}
        self._authorized_cards = {}
        
        # 更新属性
        self._attributes.update({
            "is_locked": self._is_locked,
            "is_open": self._is_open,
            "access_mode": self._access_mode,
            "security_level": self._security_level,
            "temperature": self._temperature,
            "humidity": self._humidity
        })
        
        # 初始化默认授权（示例）
        self._initialize_default_authorizations()
        
        logger.info(f"门禁ECU {self.ecu_id} 初始化完成")
    
    def _initialize_default_authorizations(self):
        """初始化默认授权"""
        # 默认管理员
        self._authorized_users["admin"] = {
            "user_id": "admin",
            "name": "Administrator",
            "pin": "123456",  # 实际应用中应该使用哈希
            "permissions": ["unlock", "lock", "add_user", "view_logs"],
            "valid_from": datetime.now(),
            "valid_to": datetime.now() + timedelta(days=365),
            "enabled": True
        }
        
        # 默认卡片
        self._authorized_cards["CARD001"] = {
            "card_id": "CARD001",
            "user_id": "admin",
            "last_used": None,
            "enabled": True
        }
    
    async def _execute_lock(self, params: Dict) -> Dict:
        """执行锁定命令"""
        try:
            user_id = params.get("user_id", "system")
            reason = params.get("reason", "security_lock")
            force = params.get("force", False)
            
            # 检查当前状态
            if self._is_locked:
                return {
                    "success": True,
                    "message": "Door is already locked",
                    "already_locked": True
                }
            
            # 检查门是否开着
            if self._is_open and not force:
                return {
                    "success": False,
                    "error_code": ErrorCodes.INVALID_STATE,
                    "error_message": "Cannot lock while door is open"
                }
            
            # 验证权限
            if not await self._check_permission(user_id, "lock"):
                return {
                    "success": False,
                    "error_code": ErrorCodes.PERMISSION_DENIED,
                    "error_message": "Permission denied for lock operation"
                }
            
            # 模拟锁定过程
            logger.info(f"锁定门禁 {self.ecu_id}，用户: {user_id}")
            
            # 检查锁机构状态
            if self._lock_mechanism_status == "stuck":
                # 尝试恢复
                await asyncio.sleep(2)
                self._lock_mechanism_status = "normal"
            elif self._lock_mechanism_status == "broken":
                return {
                    "success": False,
                    "error_code": ErrorCodes.RESOURCE_UNAVAILABLE,
                    "error_message": "Lock mechanism is broken"
                }
            
            # 执行锁定
            await asyncio.sleep(1.0)  # 模拟锁定时间
            self._is_locked = True
            
            # 记录访问日志
            access_log = {
                "event_type": "lock",
                "ecu_id": self.ecu_id,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
                "reason": reason,
                "success": True,
                "location": "main_entrance"
            }
            
            self._access_logs.append(access_log)
            
            # 保存到数据库
            if self.db_client:
                try:
                    await self.db_client.save_event(self.ecu_id, "door_lock", access_log)
                except Exception as e:
                    logger.error(f"保存锁定事件失败: {e}")
            
            # 触发相关操作
            if self._security_level == "high":
                await self._activate_security_protocols("lock")
            
            return {
                "success": True,
                "message": "Door locked successfully",
                "lock_time": datetime.now().isoformat(),
                "lock_status": self._lock_mechanism_status,
                "log": access_log
            }
            
        except Exception as e:
            logger.error(f"锁定失败: {e}")
            return {
                "success": False,
                "error_code": ErrorCodes.INTERNAL_ERROR,
                "error_message": f"Lock failed: {str(e)}"
            }
    
    async def _execute_unlock(self, params: Dict) -> Dict:
        """执行解锁命令"""
        try:
            user_id = params.get("user_id", "")
            pin_code = params.get("pin_code", "")
            card_id = params.get("card_id", "")
            facial_data = params.get("facial_data", "")
            
            # 检查当前状态
            if not self._is_locked:
                return {
                    "success": True,
                    "message": "Door is already unlocked",
                    "already_unlocked": True
                }
            
            # 验证身份
            auth_result = await self._authenticate_user(user_id, pin_code, card_id, facial_data)
            if not auth_result["authenticated"]:
                self._unauthorized_attempts += 1
                
                # 检查是否触发警报
                if self._unauthorized_attempts >= 3:
                    await self._trigger_alarm("multiple_unauthorized_attempts")
                
                return {
                    "success": False,
                    "error_code": ErrorCodes.PERMISSION_DENIED,
                    "error_message": auth_result.get("message", "Authentication failed"),
                    "unauthorized_attempts": self._unauthorized_attempts
                }
            
            # 验证权限
            if not await self._check_permission(auth_result["user_id"], "unlock"):
                return {
                    "success": False,
                    "error_code": ErrorCodes.PERMISSION_DENIED,
                    "error_message": "Permission denied for unlock operation"
                }
            
            # 重置未授权尝试计数
            self._unauthorized_attempts = 0
            
            # 模拟解锁过程
            logger.info(f"解锁门禁 {self.ecu_id}，用户: {auth_result['user_id']}")
            
            # 检查锁机构状态
            if self._lock_mechanism_status == "stuck":
                # 尝试恢复
                await asyncio.sleep(2)
                self._lock_mechanism_status = "normal"
            elif self._lock_mechanism_status == "broken":
                return {
                    "success": False,
                    "error_code": ErrorCodes.RESOURCE_UNAVAILABLE,
                    "error_message": "Lock mechanism is broken"
                }
            
            # 执行解锁
            await asyncio.sleep(1.5)  # 模拟解锁时间
            self._is_locked = False
            self._is_open = True  # 解锁后自动开门
            
            # 记录最后访问时间
            self._last_access_time = datetime.now()
            
            # 记录访问日志
            access_log = {
                "event_type": "unlock",
                "ecu_id": self.ecu_id,
                "user_id": auth_result["user_id"],
                "auth_method": auth_result["method"],
                "timestamp": self._last_access_time.isoformat(),
                "success": True,
                "location": "main_entrance",
                "access_id": auth_result.get("access_id", "")
            }
            
            self._access_logs.append(access_log)
            
            # 如果是卡片，更新最后使用时间
            if card_id and card_id in self._authorized_cards:
                self._authorized_cards[card_id]["last_used"] = self._last_access_time
            
            # 保存到数据库
            if self.db_client:
                try:
                    await self.db_client.save_event(self.ecu_id, "door_unlock", access_log)
                except Exception as e:
                    logger.error(f"保存解锁事件失败: {e}")
            
            # 触发相关操作
            if self._security_level == "high":
                await self._activate_security_protocols("unlock")
            
            # 设置自动重新锁定定时器
            asyncio.create_task(self._auto_relock())
            
            return {
                "success": True,
                "message": "Door unlocked successfully",
                "unlock_time": self._last_access_time.isoformat(),
                "user_info": {
                    "user_id": auth_result["user_id"],
                    "name": auth_result.get("name", ""),
                    "auth_method": auth_result["method"]
                },
                "log": access_log
            }
            
        except Exception as e:
            logger.error(f"解锁失败: {e}")
            return {
                "success": False,
                "error_code": ErrorCodes.INTERNAL_ERROR,
                "error_message": f"Unlock failed: {str(e)}"
            }
    
    async def _authenticate_user(self, user_id: str, pin_code: str, 
                                card_id: str, facial_data: str) -> Dict:
        """验证用户身份"""
        
        # 优先检查卡片
        if card_id and card_id in self._authorized_cards:
            card_info = self._authorized_cards[card_id]
            if card_info["enabled"]:
                user_id = card_info["user_id"]
                return {
                    "authenticated": True,
                    "user_id": user_id,
                    "method": "card",
                    "access_id": card_id
                }
        
        # 检查PIN码
        if user_id and pin_code:
            if user_id in self._authorized_users:
                user_info = self._authorized_users[user_id]
                if user_info["enabled"] and user_info["pin"] == pin_code:
                    # 检查有效期
                    if user_info["valid_from"] <= datetime.now() <= user_info["valid_to"]:
                        return {
                            "authenticated": True,
                            "user_id": user_id,
                            "name": user_info["name"],
                            "method": "pin"
                        }
        
        # 检查面部识别（简化实现）
        if facial_data:
            # 实际应用中应该有面部识别算法
            # 这里简化为检查预存储的面部数据
            for uid, user_info in self._authorized_users.items():
                if user_info.get("facial_data") == facial_data:
                    return {
                        "authenticated": True,
                        "user_id": uid,
                        "name": user_info["name"],
                        "method": "facial"
                    }
        
        return {
            "authenticated": False,
            "message": "Authentication failed"
        }
    
    async def _check_permission(self, user_id: str, permission: str) -> bool:
        """检查用户权限"""
        if user_id in self._authorized_users:
            user_info = self._authorized_users[user_id]
            return permission in user_info.get("permissions", [])
        return False
    
    async def _execute_get_status(self, params: Dict) -> Dict:
        """执行获取状态命令"""
        try:
            detailed = params.get("detailed", False)
            include_logs = params.get("include_logs", False)
            
            # 模拟传感器数据更新
            await self._update_sensor_data()
            
            # 基础状态
            status = {
                "ecu_id": self.ecu_id,
                "device_type": self.device_type,
                "online": self.status.value == "online",
                "status": self.status.value,
                "is_locked": self._is_locked,
                "is_open": self._is_open,
                "access_mode": self._access_mode,
                "security_level": self._security_level,
                "last_access_time": self._last_access_time.isoformat() if self._last_access_time else None,
                "unauthorized_attempts": self._unauthorized_attempts,
                "alarm_triggered": self._alarm_triggered,
                "temperature": self._temperature,
                "humidity": self._humidity,
                "light_level": self._light_level,
                "motion_detected": self._motion_detected,
                "door_sensor_status": self._door_sensor_status,
                "lock_mechanism_status": self._lock_mechanism_status,
                "camera_status": self._camera_status,
                "firmware_version": self.firmware_version,
                "serial_number": f"SN{self.ecu_id}",
                "last_seen": datetime.now().isoformat(),
                "uptime": (datetime.now() - self._stats["uptime_start"]).total_seconds()
            }
            
            # 详细状态
            if detailed:
                status.update({
                    "hardware_status": self._get_hardware_status(),
                    "network_info": self._get_network_info(),
                    "power_info": self._get_power_info(),
                    "stats": self._stats.copy(),
                    "error_count": self._error_count,
                    "authorized_user_count": len(self._authorized_users),
                    "authorized_card_count": len(self._authorized_cards)
                })
            
            # 访问日志
            if include_logs:
                status["recent_access_logs"] = self._access_logs[-10:]  # 最近10条
            
            # 更新最后状态更新时间
            self._last_status_update = datetime.now()
            
            return {
                "success": True,
                "status": status,
                "timestamp": self._last_status_update.isoformat(),
                "detailed": detailed
            }
            
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            return {
                "success": False,
                "error_code": ErrorCodes.INTERNAL_ERROR,
                "error_message": f"Get status failed: {str(e)}"
            }
    
    async def _update_sensor_data(self):
        """更新传感器数据（模拟）"""
        try:
            # 模拟温度和湿度变化
            self._temperature += random.uniform(-0.2, 0.2)
            self._temperature = max(10.0, min(35.0, self._temperature))
            
            self._humidity += random.uniform(-1.0, 1.0)
            self._humidity = max(20.0, min(80.0, self._humidity))
            
            # 模拟光照强度变化（基于时间）
            hour = datetime.now().hour
            if 6 <= hour < 18:  # 白天
                self._light_level = random.randint(60, 100)
            else:  # 夜晚
                self._light_level = random.randint(10, 40)
            
            # 模拟运动检测（随机）
            if random.random() < 0.05:  # 5%概率
                self._motion_detected = True
                # 记录运动事件
                if self.db_client:
                    try:
                        await self.db_client.save_event(
                            self.ecu_id,
                            "motion_detected",
                            {
                                "timestamp": datetime.now().isoformat(),
                                "location": "main_entrance",
                                "confidence": random.randint(70, 95)
                            }
                        )
                    except Exception as e:
                        logger.error(f"保存运动事件失败: {e}")
                
                # 如果门开着且检测到运动，可能需要警报
                if self._is_open and self._security_level == "high":
                    await self._trigger_alarm("door_open_with_motion")
            else:
                self._motion_detected = False
            
            # 模拟硬件状态变化（随机故障）
            if random.random() < 0.001:  # 0.1%概率
                component = random.choice(["door_sensor", "lock_mechanism", "camera"])
                status = random.choice(["normal", "stuck", "degraded"])
                
                if component == "door_sensor":
                    self._door_sensor_status = status
                elif component == "lock_mechanism":
                    self._lock_mechanism_status = status
                elif component == "camera":
                    self._camera_status = status
            
            # 更新属性
            self._attributes.update({
                "is_locked": self._is_locked,
                "is_open": self._is_open,
                "temperature": round(self._temperature, 1),
                "humidity": round(self._humidity, 1),
                "light_level": self._light_level,
                "motion_detected": self._motion_detected
            })
            
        except Exception as e:
            logger.error(f"更新传感器数据失败: {e}")
    
    def _get_hardware_status(self) -> Dict:
        """获取硬件状态"""
        return {
            "door_sensor": self._door_sensor_status,
            "lock_mechanism": self._lock_mechanism_status,
            "camera": self._camera_status,
            "motion_sensor": "normal",
            "temperature_sensor": "normal",
            "humidity_sensor": "normal",
            "light_sensor": "normal",
            "buzzer": "normal",
            "led_indicator": "normal"
        }
    
    def _get_network_info(self) -> Dict:
        """获取网络信息"""
        return {
            "connection_type": "WiFi",
            "signal_strength": random.randint(3, 5),
            "ip_address": f"192.168.1.{random.randint(50, 100)}",
            "mac_address": f"00:1A:2B:3C:4D:{random.randint(10, 99):02X}",
            "connected_since": (datetime.now() - timedelta(hours=random.randint(1, 24))).isoformat()
        }
    
    def _get_power_info(self) -> Dict:
        """获取电源信息"""
        return {
            "power_source": "main",  # main, battery, backup
            "battery_level": 95.0,  # 如果有备用电池
            "voltage": 12.0,
            "current": 0.8,
            "power_consumption": 9.6,  # 瓦特
            "estimated_backup_time": 24  # 小时
        }
    
    async def _auto_relock(self):
        """自动重新锁定"""
        try:
            # 等待30秒后自动重新锁定
            await asyncio.sleep(30)
            
            if not self._is_locked:
                logger.info(f"门禁 {self.ecu_id} 自动重新锁定")
                self._is_locked = True
                self._is_open = False
                
                # 记录自动锁定事件
                if self.db_client:
                    try:
                        await self.db_client.save_event(
                            self.ecu_id,
                            "auto_relock",
                            {
                                "timestamp": datetime.now().isoformat(),
                                "reason": "timeout"
                            }
                        )
                    except Exception as e:
                        logger.error(f"保存自动锁定事件失败: {e}")
                
                # 更新属性
                self._attributes["is_locked"] = True
                self._attributes["is_open"] = False
        except Exception as e:
            logger.error(f"自动重新锁定失败: {e}")
    
    async def _trigger_alarm(self, reason: str):
        """触发警报"""
        if self._alarm_triggered:
            return
        
        logger.warning(f"门禁 {self.ecu_id} 触发警报: {reason}")
        self._alarm_triggered = True
        
        # 记录警报事件
        alarm_event = {
            "timestamp": datetime.now().isoformat(),
            "ecu_id": self.ecu_id,
            "reason": reason,
            "severity": "high",
            "location": "main_entrance"
        }
        
        if self.db_client:
            try:
                await self.db_client.save_event(self.ecu_id, "alarm_triggered", alarm_event)
            except Exception as e:
                logger.error(f"保存警报事件失败: {e}")
        
        # 模拟警报动作（如蜂鸣器响、LED闪烁等）
        await asyncio.sleep(5)  # 警报持续5秒
        
        # 停止警报
        self._alarm_triggered = False
    
    async def _activate_security_protocols(self, action: str):
        """激活安全协议"""
        logger.info(f"激活安全协议: {action}")
        
        if action == "unlock" and self._security_level == "high":
            # 高级安全解锁：拍照记录
            if self.db_client:
                try:
                    await self.db_client.save_event(
                        self.ecu_id,
                        "security_photo",
                        {
                            "timestamp": datetime.now().isoformat(),
                            "action": "unlock",
                            "photo_id": f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        }
                    )
                except Exception as e:
                    logger.error(f"保存安全照片失败: {e}")
        
        elif action == "lock" and self._security_level == "high":
            # 高级安全锁定：检查门窗状态
            pass
    
    async def add_authorized_user(self, user_info: Dict) -> Dict:
        """添加授权用户"""
        try:
            user_id = user_info.get("user_id")
            if not user_id:
                return {
                    "success": False,
                    "error_code": ErrorCodes.INVALID_PARAMS,
                    "error_message": "User ID is required"
                }
            
            self._authorized_users[user_id] = {
                "user_id": user_id,
                "name": user_info.get("name", ""),
                "pin": user_info.get("pin", ""),
                "permissions": user_info.get("permissions", ["unlock"]),
                "valid_from": user_info.get("valid_from", datetime.now()),
                "valid_to": user_info.get("valid_to", datetime.now() + timedelta(days=365)),
                "enabled": user_info.get("enabled", True)
            }
            
            logger.info(f"添加授权用户: {user_id}")
            
            return {
                "success": True,
                "message": f"User {user_id} added successfully",
                "user_count": len(self._authorized_users)
            }
            
        except Exception as e:
            logger.error(f"添加授权用户失败: {e}")
            return {
                "success": False,
                "error_code": ErrorCodes.INTERNAL_ERROR,
                "error_message": f"Failed to add user: {str(e)}"
            }
    
    async def add_authorized_card(self, card_info: Dict) -> Dict:
        """添加授权卡片"""
        try:
            card_id = card_info.get("card_id")
            if not card_id:
                return {
                    "success": False,
                    "error_code": ErrorCodes.INVALID_PARAMS,
                    "error_message": "Card ID is required"
                }
            
            self._authorized_cards[card_id] = {
                "card_id": card_id,
                "user_id": card_info.get("user_id", ""),
                "last_used": None,
                "enabled": card_info.get("enabled", True)
            }
            
            logger.info(f"添加授权卡片: {card_id}")
            
            return {
                "success": True,
                "message": f"Card {card_id} added successfully",
                "card_count": len(self._authorized_cards)
            }
            
        except Exception as e:
            logger.error(f"添加授权卡片失败: {e}")
            return {
                "success": False,
                "error_code": ErrorCodes.INTERNAL_ERROR,
                "error_message": f"Failed to add card: {str(e)}"
            }