"""
共享单车ECU设备实现
"""
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
import logging

from ..core.base_ecu import BaseECU, ECUConfig, CommandResult
from protocol.message_types import MessageTypes, ErrorCodes, DeviceTypes

logger = logging.getLogger(__name__)


class SharedBikeECU(BaseECU):
    """共享单车ECU设备"""
    
    def __init__(self, config: ECUConfig, db_client=None):
        # 设置设备类型为共享单车
        config.device_type = DeviceTypes.SHARED_BIKE
        super().__init__(config, db_client)
        
        # 共享单车特定属性
        self._battery_level = 85.0  # 电量百分比
        self._is_locked = True  # 是否锁定
        self._mileage = 1256.3  # 总里程（公里）
        self._current_speed = 0.0  # 当前速度（km/h）
        self._location = {
            "latitude": 31.2304,  # 纬度
            "longitude": 121.4737,  # 经度
            "accuracy": 10.0  # 精度（米）
        }
        self._temperature = 25.5  # 温度（摄氏度）
        self._signal_strength = 4  # 信号强度（1-5）
        self._last_ride_info = None  # 最后一次骑行信息
        
        # 硬件状态
        self._hardware_errors = []
        self._lock_status = "normal"  # normal, stuck, broken
        
        # 更新属性
        self._attributes.update({
            "battery_level": self._battery_level,
            "is_locked": self._is_locked,
            "mileage": self._mileage,
            "location": self._location.copy(),
            "temperature": self._temperature
        })
        
        logger.info(f"共享单车ECU {self.ecu_id} 初始化完成")
    
    async def _execute_lock(self, params: Dict) -> Dict:
        """执行锁定命令"""
        try:
            force = params.get("force", False)
            user_id = params.get("user_id", "system")
            reason = params.get("reason", "normal_lock")
            
            # 检查当前状态
            if self._is_locked:
                return {
                    "success": True,
                    "message": "Device is already locked",
                    "already_locked": True,
                    "lock_status": self._lock_status
                }
            
            # 检查速度
            if self._current_speed > 1.0 and not force:
                return {
                    "success": False,
                    "error_code": ErrorCodes.INVALID_STATE,
                    "error_message": "Cannot lock while bike is moving"
                }
            
            # 模拟锁定过程
            logger.info(f"锁定单车 {self.ecu_id}，用户: {user_id}")
            
            # 检查锁状态
            if self._lock_status == "stuck":
                # 锁卡住，需要重试
                await asyncio.sleep(2)
                self._lock_status = "normal"
            elif self._lock_status == "broken":
                return {
                    "success": False,
                    "error_code": ErrorCodes.RESOURCE_UNAVAILABLE,
                    "error_message": "Lock mechanism is broken"
                }
            
            # 执行锁定
            await asyncio.sleep(1.5)  # 模拟锁定时间
            
            self._is_locked = True
            self._current_speed = 0.0
            
            # 更新属性
            self._attributes["is_locked"] = True
            
            # 如果是骑行结束，记录骑行数据
            if self._last_ride_info and not self._last_ride_info.get("ended"):
                await self._record_ride_completion(user_id)
            
            # 记录锁定事件
            lock_event = {
                "event_type": "lock",
                "ecu_id": self.ecu_id,
                "user_id": user_id,
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
                "location": self._location.copy(),
                "force_mode": force,
                "lock_status": self._lock_status
            }
            
            # 保存到数据库
            if self.db_client:
                try:
                    await self.db_client.save_event(self.ecu_id, "lock", lock_event)
                except Exception as e:
                    logger.error(f"保存锁定事件失败: {e}")
            
            return {
                "success": True,
                "message": "Bike locked successfully",
                "lock_status": self._lock_status,
                "event": lock_event
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
            user_id = params.get("user_id", "unknown")
            auth_code = params.get("auth_code", "")
            duration = params.get("duration", 3600)  # 默认1小时
            
            # 验证授权码（简化验证）
            if not auth_code:
                return {
                    "success": False,
                    "error_code": ErrorCodes.PERMISSION_DENIED,
                    "error_message": "Authorization code required"
                }
            
            # 检查当前状态
            if not self._is_locked:
                return {
                    "success": True,
                    "message": "Device is already unlocked",
                    "already_unlocked": True
                }
            
            # 检查电量
            if self._battery_level < 10.0:
                return {
                    "success": False,
                    "error_code": ErrorCodes.RESOURCE_UNAVAILABLE,
                    "error_message": "Battery level too low"
                }
            
            # 检查锁状态
            if self._lock_status == "broken":
                return {
                    "success": False,
                    "error_code": ErrorCodes.RESOURCE_UNAVAILABLE,
                    "error_message": "Lock mechanism is broken"
                }
            
            # 模拟解锁过程
            logger.info(f"解锁单车 {self.ecu_id}，用户: {user_id}")
            
            # 检查锁状态
            if self._lock_status == "stuck":
                # 锁卡住，需要重试
                await asyncio.sleep(3)
                self._lock_status = "normal"
            
            # 执行解锁
            await asyncio.sleep(2.0)  # 模拟解锁时间
            
            self._is_locked = False
            self._lock_status = "normal"
            
            # 更新属性
            self._attributes["is_locked"] = False
            
            # 记录骑行开始
            ride_start_time = datetime.now()
            self._last_ride_info = {
                "user_id": user_id,
                "start_time": ride_start_time,
                "start_location": self._location.copy(),
                "start_mileage": self._mileage,
                "auth_code": auth_code,
                "duration_limit": duration,
                "ended": False
            }
            
            # 记录解锁事件
            unlock_event = {
                "event_type": "unlock",
                "ecu_id": self.ecu_id,
                "user_id": user_id,
                "timestamp": ride_start_time.isoformat(),
                "location": self._location.copy(),
                "auth_code": auth_code[:8],  # 只存储部分用于追踪
                "duration_limit": duration,
                "battery_level": self._battery_level
            }
            
            # 保存到数据库
            if self.db_client:
                try:
                    await self.db_client.save_event(self.ecu_id, "unlock", unlock_event)
                except Exception as e:
                    logger.error(f"保存解锁事件失败: {e}")
            
            return {
                "success": True,
                "message": "Bike unlocked successfully",
                "unlock_time": ride_start_time.isoformat(),
                "expires_at": (ride_start_time + timedelta(seconds=duration)).isoformat(),
                "auth_code": auth_code[:8],
                "event": unlock_event
            }
            
        except Exception as e:
            logger.error(f"解锁失败: {e}")
            return {
                "success": False,
                "error_code": ErrorCodes.INTERNAL_ERROR,
                "error_message": f"Unlock failed: {str(e)}"
            }
    
    async def _execute_get_status(self, params: Dict) -> Dict:
        """执行获取状态命令"""
        try:
            detailed = params.get("detailed", False)
            include_history = params.get("include_history", False)
            
            # 模拟传感器数据更新
            await self._update_sensor_data()
            
            # 基础状态
            status = {
                "ecu_id": self.ecu_id,
                "device_type": self.device_type,
                "online": self.status.value == "online",
                "status": self.status.value,
                "is_locked": self._is_locked,
                "battery_level": self._battery_level,
                "battery_voltage": 3.8,  # 模拟电压
                "mileage": self._mileage,
                "current_speed": self._current_speed,
                "location": self._location.copy(),
                "temperature": self._temperature,
                "humidity": 60.2,  # 模拟湿度
                "signal_strength": self._signal_strength,
                "lock_status": self._lock_status,
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
                    "storage_info": self._get_storage_info(),
                    "power_info": self._get_power_info(),
                    "stats": self._stats.copy(),
                    "error_count": self._error_count
                })
            
            # 骑行历史
            if include_history and self.db_client:
                try:
                    ride_history = await self.db_client.get_ride_history(
                        self.ecu_id, 
                        limit=10
                    )
                    status["recent_rides"] = ride_history
                except Exception as e:
                    logger.error(f"获取骑行历史失败: {e}")
                    status["recent_rides"] = []
            
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
            # 模拟电量消耗
            if not self._is_locked:
                # 骑行中消耗更快
                self._battery_level -= random.uniform(0.01, 0.05)
            else:
                # 锁定时消耗较慢
                self._battery_level -= random.uniform(0.001, 0.005)
            
            # 确保电量在合理范围
            self._battery_level = max(0.0, min(100.0, self._battery_level))
            
            # 模拟位置变化（如果正在骑行）
            if not self._is_locked and self._last_ride_info:
                # 模拟速度和里程增加
                self._current_speed = random.uniform(5.0, 25.0)
                distance = self._current_speed * 0.00027778  # km/s (假设1秒间隔)
                self._mileage += distance
                
                # 模拟位置移动（小范围随机）
                self._location["latitude"] += random.uniform(-0.0001, 0.0001)
                self._location["longitude"] += random.uniform(-0.0001, 0.0001)
            
            # 模拟温度变化
            self._temperature += random.uniform(-0.5, 0.5)
            self._temperature = max(-10.0, min(50.0, self._temperature))
            
            # 模拟信号强度变化
            self._signal_strength = random.randint(2, 5)
            
            # 随机锁故障
            if random.random() < 0.001:  # 0.1%概率
                self._lock_status = random.choice(["stuck", "normal"])
                if self._lock_status == "stuck":
                    self._hardware_errors.append({
                        "timestamp": datetime.now(),
                        "component": "lock",
                        "error": "lock_stuck",
                        "severity": "warning"
                    })
            
            # 更新属性
            self._attributes.update({
                "battery_level": round(self._battery_level, 2),
                "mileage": round(self._mileage, 2),
                "current_speed": round(self._current_speed, 2),
                "location": self._location.copy(),
                "temperature": round(self._temperature, 2),
                "signal_strength": self._signal_strength,
                "lock_status": self._lock_status
            })
            
        except Exception as e:
            logger.error(f"更新传感器数据失败: {e}")
    
    def _get_hardware_status(self) -> Dict:
        """获取硬件状态"""
        return {
            "lock": self._lock_status,
            "motor": "normal",
            "battery": "normal" if self._battery_level > 20.0 else "low",
            "gps": "normal",
            "bluetooth": "normal",
            "accelerometer": "normal",
            "temperature_sensor": "normal",
            "hardware_errors": self._hardware_errors[-5:] if self._hardware_errors else []
        }
    
    def _get_network_info(self) -> Dict:
        """获取网络信息"""
        return {
            "signal_strength": self._signal_strength,
            "network_type": "4G",
            "operator": "China Mobile",
            "ip_address": "192.168.1." + str(random.randint(100, 200)),
            "connected_since": (datetime.now() - timedelta(minutes=random.randint(1, 60))).isoformat()
        }
    
    def _get_storage_info(self) -> Dict:
        """获取存储信息"""
        return {
            "total_memory": 1024 * 1024,  # 1MB
            "used_memory": random.randint(100000, 500000),
            "free_memory": 1024 * 1024 - random.randint(100000, 500000),
            "log_count": random.randint(100, 1000)
        }
    
    def _get_power_info(self) -> Dict:
        """获取电源信息"""
        return {
            "battery_level": self._battery_level,
            "battery_health": "good" if self._battery_level > 70.0 else "fair",
            "voltage": 3.8,
            "current": 0.5,
            "power_mode": "normal",
            "estimated_remaining_time": self._battery_level * 0.5  # 小时
        }
    
    async def _record_ride_completion(self, user_id: str):
        """记录骑行完成"""
        try:
            if not self._last_ride_info:
                return
            
            ride_info = self._last_ride_info
            end_time = datetime.now()
            start_time = ride_info["start_time"]
            duration = (end_time - start_time).total_seconds()
            
            # 计算骑行距离
            distance = self._mileage - ride_info["start_mileage"]
            
            # 计算费用（示例：每分钟0.5元）
            cost = (duration / 60) * 0.5
            
            # 创建骑行记录
            ride_record = {
                "ride_id": f"ride_{start_time.strftime('%Y%m%d_%H%M%S')}_{self.ecu_id}",
                "ecu_id": self.ecu_id,
                "user_id": user_id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration": duration,
                "distance": distance,
                "start_location": ride_info["start_location"],
                "end_location": self._location.copy(),
                "average_speed": (distance / (duration / 3600)) if duration > 0 else 0,
                "calories_burned": distance * 50,  # 模拟卡路里计算
                "cost": round(cost, 2),
                "payment_status": "pending",
                "battery_usage": ride_info.get("start_battery", 100) - self._battery_level
            }
            
            # 保存到数据库
            if self.db_client:
                try:
                    await self.db_client.save_ride_record(ride_record)
                except Exception as e:
                    logger.error(f"保存骑行记录失败: {e}")
            
            # 标记骑行结束
            self._last_ride_info["ended"] = True
            self._last_ride_info["end_time"] = end_time
            self._last_ride_info["distance"] = distance
            self._last_ride_info["cost"] = cost
            
            logger.info(f"骑行记录完成: {ride_record['ride_id']}, 距离: {distance:.2f}km, 时长: {duration:.0f}s")
            
        except Exception as e:
            logger.error(f"记录骑行完成失败: {e}")
    
    async def charge_battery(self, amount: float):
        """充电"""
        self._battery_level = min(100.0, self._battery_level + amount)
        logger.info(f"单车 {self.ecu_id} 充电 {amount}%，当前电量: {self._battery_level}%")
    
    async def simulate_movement(self, speed_kmh: float, duration_minutes: float):
        """模拟移动"""
        if self._is_locked:
            logger.warning(f"单车 {self.ecu_id} 已锁定，无法移动")
            return
        
        logger.info(f"单车 {self.ecu_id} 开始移动: {speed_kmh} km/h, {duration_minutes} 分钟")
        
        self._current_speed = speed_kmh
        await asyncio.sleep(duration_minutes * 60)
        
        # 更新里程
        distance = speed_kmh * (duration_minutes / 60)
        self._mileage += distance
        
        logger.info(f"单车 {self.ecu_id} 移动完成，新增里程: {distance:.2f} km")