"""
Mock编解码器 - 提供假数据供开发使用
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Union, Dict, Any
from jsonrpc import JSONRPCRequest, JSONRPCResponse, JSONRPCNotification
from message_types import MessageTypes, ErrorCodes, DeviceTypes, DeviceStatus


class MockCodec:
    """Mock编解码器"""

    @staticmethod
    def encode_message(message: Union[JSONRPCRequest, JSONRPCResponse, JSONRPCNotification]) -> str:
        """
        编码消息为JSON字符串（Mock版本）

        Args:
            message: JSON-RPC消息对象

        Returns:
            JSON格式的字符串
        """
        try:
            message_dict = message.to_dict()
            return json.dumps(message_dict, ensure_ascii=False, indent=2)
        except Exception as e:
            # 编码失败时返回错误响应
            error_response = JSONRPCResponse.error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Encode failed: {str(e)}"
            )
            return json.dumps(error_response.to_dict(), ensure_ascii=False)

    @staticmethod
    def decode_message(json_str: str) -> Union[JSONRPCRequest, JSONRPCResponse, JSONRPCNotification]:
        """
        解码JSON字符串为消息对象

        Args:
            json_str: JSON格式的字符串

        Returns:
            JSON-RPC消息对象
        """
        try:
            data = json.loads(json_str)

            # 验证JSON-RPC版本
            if data.get("jsonrpc") != "2.0":
                return JSONRPCResponse.error_response(
                    ErrorCodes.INVALID_REQUEST,
                    "Invalid JSON-RPC version"
                )

            # 判断消息类型
            if "method" in data:
                if "id" in data:
                    # 这是请求
                    return JSONRPCRequest(
                        method=data.get("method"),
                        params=data.get("params", {}),
                        request_id=data.get("id")
                    )
                else:
                    # 这是通知
                    return JSONRPCNotification(
                        method=data.get("method"),
                        params=data.get("params", {})
                    )
            elif "result" in data or "error" in data:
                # 这是响应
                return JSONRPCResponse(
                    result=data.get("result"),
                    error=data.get("error"),
                    request_id=data.get("id")
                )
            else:
                return JSONRPCResponse.error_response(
                    ErrorCodes.INVALID_REQUEST,
                    "Invalid JSON-RPC message"
                )

        except json.JSONDecodeError:
            return JSONRPCResponse.error_response(
                ErrorCodes.PARSE_ERROR,
                "Invalid JSON format"
            )
        except Exception as e:
            return JSONRPCResponse.error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Decode failed: {str(e)}"
            )

    @staticmethod
    def create_mock_request(method: str, ecu_id: str = "test_ecu_001",
                            device_type: str = None) -> JSONRPCRequest:
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now().isoformat()

        if device_type is None:
            device_type = DeviceTypes.SHARED_BIKE

        # 根据方法类型生成不同的参数
        base_params = {
            "ecu_id": ecu_id,
            "device_type": device_type,
            "timestamp": timestamp
        }

        method_params = {}

        if method == MessageTypes.STATUS_UPDATE:
            method_params = {
                "status": {
                    "battery": 78,  # 电量百分比
                    "online": True,
                    "locked": False,
                    "signal_strength": 4,
                    "temperature": 25.5,
                    "latitude": 31.2304,
                    "longitude": 121.4737,
                    "speed": 0,
                    "mileage": 1256.3
                }
            }
        elif method == MessageTypes.HEARTBEAT:
            method_params = {
                "interval": 60,
                "uptime": 3600,
                "memory_usage": 45.2
            }
        elif method == MessageTypes.LOCK:
            method_params = {
                "command": "lock",
                "force": False,
                "reason": "user_request"
            }
        elif method == MessageTypes.UNLOCK:
            method_params = {
                "command": "unlock",
                "duration": 300,
                "auth_code": "A1B2C3D4",
                "user_id": "user_001"
            }
        elif method == MessageTypes.GET_STATUS:
            method_params = {
                "detailed": True,
                "include_history": False
            }
        elif method == MessageTypes.GET_CONFIG:
            method_params = {
                "config_keys": ["general", "network", "security"]
            }
        elif method == MessageTypes.UPDATE_CONFIG:
            method_params = {
                "config": {
                    "polling_interval": 60,
                    "auto_lock": True,
                    "timeout": 300,
                    "heartbeat_interval": 30
                }
            }
        elif method == MessageTypes.FIRMWARE_UPDATE:
            method_params = {
                "version": "2.0.1",
                "url": "http://firmware.example.com/update.bin",
                "checksum": "a1b2c3d4e5f6"
            }
        elif method == MessageTypes.UPLOAD_DATA:
            method_params = {
                "data_type": "usage_log",
                "data": {
                    "start_time": (datetime.now() - timedelta(hours=1)).isoformat(),
                    "end_time": timestamp,
                    "distance": 5.2,
                    "calories": 120,
                    "user_id": "user_002"
                }
            }

        # 合并基础参数和方法特定参数
        params = {**base_params, **method_params}

        return JSONRPCRequest(method, params, request_id)

    @staticmethod
    def create_mock_response(request: JSONRPCRequest, success: bool = True,
                             error_code: int = None, delay: float = 0) -> JSONRPCResponse:
        """
        创建模拟响应

        Args:
            request: 原始请求对象
            success: 是否成功
            error_code: 错误代码（如果失败）
            delay: 模拟延迟（秒）

        Returns:
            模拟的JSON-RPC响应
        """
        import time
        if delay > 0:
            time.sleep(delay)

        if success:
            # 模拟成功响应
            base_result = {
                "success": True,
                "ecu_id": request.params.get("ecu_id", "unknown"),
                "timestamp": datetime.now().isoformat(),
                "request_id": request.id,
                "execution_time": 0.125
            }

            # 为特定方法添加额外数据
            method_result = {}

            if request.method == MessageTypes.GET_STATUS:
                method_result = {
                    "status": {
                        "device_type": request.params.get("device_type", DeviceTypes.SHARED_BIKE),
                        "online": True,
                        "status": DeviceStatus.ONLINE,
                        "locked": False,
                        "battery": 78,
                        "battery_voltage": 3.8,
                        "signal_strength": 4,
                        "temperature": 25.5,
                        "humidity": 60.2,
                        "last_seen": datetime.now().isoformat(),
                        "uptime": 86400,
                        "firmware_version": "1.2.3",
                        "serial_number": "SN202310001"
                    }
                }
            elif request.method == MessageTypes.GET_CONFIG:
                method_result = {
                    "config": {
                        "general": {
                            "device_name": "Smart Bike #001",
                            "timezone": "Asia/Shanghai",
                            "language": "zh_CN"
                        },
                        "network": {
                            "wifi_ssid": "IoT_Network",
                            "polling_interval": 60,
                            "retry_count": 3
                        },
                        "security": {
                            "auto_lock": True,
                            "timeout": 300,
                            "require_auth": True
                        },
                        "power": {
                            "sleep_mode": True,
                            "low_power_threshold": 20
                        }
                    }
                }
            elif request.method == MessageTypes.LOCK:
                method_result = {
                    "action": "lock",
                    "status": "locked",
                    "lock_time": datetime.now().isoformat(),
                    "lock_id": f"lock_{uuid.uuid4().hex[:6]}"
                }
            elif request.method == MessageTypes.UNLOCK:
                method_result = {
                    "action": "unlock",
                    "status": "unlocked",
                    "unlock_time": datetime.now().isoformat(),
                    "expires_at": (datetime.now() + timedelta(seconds=300)).isoformat(),
                    "unlock_code": "UNLK123456"
                }
            elif request.method == MessageTypes.FIRMWARE_UPDATE:
                method_result = {
                    "update_id": f"update_{uuid.uuid4().hex[:8]}",
                    "current_version": "1.2.3",
                    "target_version": "2.0.1",
                    "status": "downloading",
                    "progress": 25,
                    "estimated_time": 180
                }

            # 合并基础结果和方法特定结果
            result = {**base_result, **method_result}
            return JSONRPCResponse.success(result, request.id)

        else:
            # 模拟错误响应
            error_code = error_code or ErrorCodes.DEVICE_BUSY
            error_messages = {
                ErrorCodes.DEVICE_OFFLINE: "Device is currently offline",
                ErrorCodes.DEVICE_BUSY: "Device is busy processing another command",
                ErrorCodes.PERMISSION_DENIED: "Permission denied for this operation",
                ErrorCodes.COMMAND_TIMEOUT: "Command execution timeout",
                ErrorCodes.INVALID_STATE: "Device is not in a valid state for this command",
                ErrorCodes.DEVICE_NOT_FOUND: "Device not found in system"
            }

            error_message = error_messages.get(error_code, "Unknown error")

            error_data = {
                "ecu_id": request.params.get("ecu_id", "unknown"),
                "request_method": request.method,
                "timestamp": datetime.now().isoformat(),
                "suggested_action": "retry_later" if error_code == ErrorCodes.DEVICE_BUSY else "check_status"
            }

            return JSONRPCResponse.error_response(
                error_code,
                error_message,
                error_data,
                request.id
            )

    @staticmethod
    def create_mock_notification(method: str, ecu_id: str = "test_ecu_001") -> JSONRPCNotification:
        """
        创建模拟通知（无ID的请求）

        Args:
            method: 方法名
            ecu_id: ECU设备ID

        Returns:
            模拟的JSON-RPC通知
        """
        timestamp = datetime.now().isoformat()

        if method == MessageTypes.STATUS_UPDATE:
            params = {
                "ecu_id": ecu_id,
                "timestamp": timestamp,
                "event_type": "status_change",
                "data": {
                    "old_status": DeviceStatus.ONLINE,
                    "new_status": DeviceStatus.BUSY,
                    "reason": "processing_command"
                }
            }
        elif method == MessageTypes.HEARTBEAT:
            params = {
                "ecu_id": ecu_id,
                "timestamp": timestamp,
                "uptime": 87000,
                "memory_free": 1024000,
                "cpu_usage": 12.5
            }
        elif method == MessageTypes.LOG_REPORT:
            params = {
                "ecu_id": ecu_id,
                "timestamp": timestamp,
                "log_level": "INFO",
                "message": "Device started successfully",
                "component": "system",
                "details": {"boot_time": 3.2}
            }
        else:
            params = {
                "ecu_id": ecu_id,
                "timestamp": timestamp,
                "event": "unknown"
            }

        return JSONRPCNotification(method, params)


# 提供简单调用的函数
def encode_message(message: Union[JSONRPCRequest, JSONRPCResponse, JSONRPCNotification]) -> str:
    """编码消息的快捷函数"""
    return MockCodec.encode_message(message)


def decode_message(json_str: str) -> Union[JSONRPCRequest, JSONRPCResponse, JSONRPCNotification]:
    """解码消息的快捷函数"""
    return MockCodec.decode_message(json_str)