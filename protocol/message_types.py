"""
协议常量定义
"""


# 消息方法类型
class MessageTypes:
    """ECU设备支持的所有命令方法"""

    # 状态相关
    STATUS_UPDATE = "status_update"  # 状态更新
    HEARTBEAT = "heartbeat"  # 心跳
    GET_STATUS = "get_status"  # 获取状态
    DEVICE_INFO = "device_info"  # 设备信息

    # 控制命令
    LOCK = "lock"  # 锁定
    UNLOCK = "unlock"  # 解锁
    POWER_ON = "power_on"  # 开机
    POWER_OFF = "power_off"  # 关机
    RESET = "reset"  # 重置
    REBOOT = "reboot"  # 重启

    # 配置命令
    UPDATE_CONFIG = "update_config"  # 更新配置
    GET_CONFIG = "get_config"  # 获取配置
    FACTORY_RESET = "factory_reset"  # 恢复出厂设置

    # 数据命令
    UPLOAD_DATA = "upload_data"  # 上传数据
    DOWNLOAD_DATA = "download_data"  # 下载数据
    QUERY_DATA = "query_data"  # 查询数据

    # 固件更新
    FIRMWARE_UPDATE = "firmware_update"  # 固件更新
    UPDATE_STATUS = "update_status"  # 更新状态

    # 诊断命令
    DIAGNOSTIC = "diagnostic"  # 诊断
    LOG_REPORT = "log_report"  # 日志报告


# 错误代码
class ErrorCodes:
    """JSON-RPC 错误代码"""

    # 标准JSON-RPC错误 (-32700 to -32600)
    PARSE_ERROR = -32700  # 解析错误
    INVALID_REQUEST = -32600  # 无效请求
    METHOD_NOT_FOUND = -32601  # 方法不存在
    INVALID_PARAMS = -32602  # 无效参数
    INTERNAL_ERROR = -32603  # 内部错误

    # 应用特定错误 (-32000 to -32099)
    DEVICE_OFFLINE = -32001  # 设备离线
    DEVICE_BUSY = -32002  # 设备忙
    PERMISSION_DENIED = -32003  # 权限拒绝
    COMMAND_TIMEOUT = -32004  # 命令超时
    INVALID_STATE = -32005  # 无效状态
    INVALID_COMMAND = -32006  # 无效命令
    RESOURCE_UNAVAILABLE = -32007  # 资源不可用
    NETWORK_ERROR = -32008  # 网络错误
    FIRMWARE_ERROR = -32009  # 固件错误

    # 业务逻辑错误 (-32100 to -32199)
    DEVICE_NOT_FOUND = -32100  # 设备未找到
    USER_NOT_AUTHORIZED = -32101  # 用户未授权
    INSUFFICIENT_BALANCE = -32102  # 余额不足
    SERVICE_UNAVAILABLE = -32103  # 服务不可用
    RATE_LIMIT_EXCEEDED = -32104  # 超过速率限制


# ECU设备类型
class DeviceTypes:
    """支持的ECU设备类型"""
    SHARED_BIKE = "shared_bike"  # 共享单车ECU
    ACCESS_CONTROL = "access_control"  # 门禁ECU
    SMART_METER = "smart_meter"  # 智能电表ECU
    IOT_GATEWAY = "iot_gateway"  # IoT网关
    VEHICLE_ECU = "vehicle_ecu"  # 车辆ECU
    SMART_LOCK = "smart_lock"  # 智能锁
    ENVIRONMENT_SENSOR = "environment_sensor"  # 环境传感器


# 设备状态
class DeviceStatus:
    """设备状态常量"""
    ONLINE = "online"  # 在线
    OFFLINE = "offline"  # 离线
    BUSY = "busy"  # 忙
    ERROR = "error"  # 错误
    UPDATING = "updating"  # 更新中
    MAINTENANCE = "maintenance"  # 维护中


# 命令状态
class CommandStatus:
    """命令执行状态"""
    PENDING = "pending"  # 等待中
    EXECUTING = "executing"  # 执行中
    SUCCESS = "success"  # 成功
    FAILED = "failed"  # 失败
    TIMEOUT = "timeout"  # 超时
    CANCELLED = "cancelled"  # 取消