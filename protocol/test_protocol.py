#!/usr/bin/env python3
"""
协议模块测试 - 修复版本
"""

import json
import asyncio
import sys
import os
from datetime import datetime, timedelta

# 打印调试信息
print("📁 当前目录:", os.getcwd())

# 手动加载模块
def load_modules():
    """手动加载所有模块"""
    modules = {}
    
    try:
        # 加载 jsonrpc.py
        import importlib.util
        spec = importlib.util.spec_from_file_location("jsonrpc", "jsonrpc.py")
        jsonrpc_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(jsonrpc_module)
        modules['jsonrpc'] = jsonrpc_module
        print("✅ 加载 jsonrpc.py")
    except Exception as e:
        print(f"❌ 加载 jsonrpc.py 失败: {e}")
        return None
    
    try:
        # 加载 message_types.py
        spec = importlib.util.spec_from_file_location("message_types", "message_types.py")
        message_types_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(message_types_module)
        modules['message_types'] = message_types_module
        print("✅ 加载 message_types.py")
    except Exception as e:
        print(f"❌ 加载 message_types.py 失败: {e}")
        return None
    
    try:
        # 加载 mock_codec.py
        spec = importlib.util.spec_from_file_location("mock_codec", "mock_codec.py")
        mock_codec_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mock_codec_module)
        modules['mock_codec'] = mock_codec_module
        print("✅ 加载 mock_codec.py")
    except Exception as e:
        print(f"❌ 加载 mock_codec.py 失败: {e}")
        return None
    
    try:
        # 加载 base_logger.py
        spec = importlib.util.spec_from_file_location("base_logger", "base_logger.py")
        base_logger_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(base_logger_module)
        modules['base_logger'] = base_logger_module
        print("✅ 加载 base_logger.py")
    except Exception as e:
        print(f"❌ 加载 base_logger.py 失败: {e}")
        return None
    
    try:
        # 加载 models.py
        spec = importlib.util.spec_from_file_location("models", "models.py")
        models_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(models_module)
        modules['models'] = models_module
        print("✅ 加载 models.py")
    except Exception as e:
        print(f"❌ 加载 models.py 失败: {e}")
        return None
    
    return modules

# 加载所有模块
modules = load_modules()
if not modules:
    print("❌ 无法加载模块，退出")
    sys.exit(1)

# 从模块中获取类
JSONRPCRequest = modules['jsonrpc'].JSONRPCRequest
JSONRPCResponse = modules['jsonrpc'].JSONRPCResponse
JSONRPCNotification = modules['jsonrpc'].JSONRPCNotification

MessageTypes = modules['message_types'].MessageTypes
ErrorCodes = modules['message_types'].ErrorCodes
DeviceTypes = modules['message_types'].DeviceTypes
DeviceStatus = modules['message_types'].DeviceStatus
CommandStatus = modules['message_types'].CommandStatus

MockCodec = modules['mock_codec'].MockCodec
encode_message = modules['mock_codec'].encode_message
decode_message = modules['mock_codec'].decode_message

MockDatabaseLogger = modules['base_logger'].MockDatabaseLogger
LogDirection = modules['base_logger'].LogDirection

ProtocolLogBase = modules['models'].ProtocolLogBase

print("\n✅ 所有模块加载完成，开始测试...\n")

# 修复类型检查问题
# 当我们使用importlib动态加载时，类实例的__class__.__name__是正确的
# 但isinstance检查会失败，因为类来自不同的模块实例

# 创建一个改进的断言类
class TestAssertions:
    """改进的测试断言类"""
    
    @staticmethod
    def assert_equal(actual, expected, message=""):
        if actual != expected:
            raise AssertionError(f"{message} Expected: {expected}, Actual: {actual}")
    
    @staticmethod
    def assert_true(condition, message=""):
        if not condition:
            raise AssertionError(f"{message} Condition is False")
    
    @staticmethod
    def assert_false(condition, message=""):
        if condition:
            raise AssertionError(f"{message} Condition is True")
    
    @staticmethod
    def assert_is_instance(obj, cls, message=""):
        # 检查类名而不是实例类型（解决动态导入问题）
        actual_class_name = obj.__class__.__name__
        expected_class_name = cls.__name__
        if actual_class_name != expected_class_name:
            raise AssertionError(
                f"{message} Expected instance of {expected_class_name}, got {actual_class_name}"
            )
    
    @staticmethod
    def assert_is_same_type(obj1, obj2, message=""):
        """检查两个对象是否是相同类型（按类名）"""
        if obj1.__class__.__name__ != obj2.__class__.__name__:
            raise AssertionError(
                f"{message} Types don't match: {obj1.__class__.__name__} vs {obj2.__class__.__name__}"
            )

# 创建断言实例
assertions = TestAssertions()


def test_basic_classes():
    """测试基础类"""
    print("🧪 测试基础类...")

    # 测试请求对象
    request = JSONRPCRequest(
        method=MessageTypes.STATUS_UPDATE,
        params={"ecu_id": "test_001", "value": 100},
        request_id="123"
    )

    assertions.assert_equal(request.method, MessageTypes.STATUS_UPDATE)
    assertions.assert_equal(request.params["ecu_id"], "test_001")
    assertions.assert_equal(request.id, "123")
    print("  ✅ JSONRPCRequest 测试通过")

    # 测试响应对象
    response = JSONRPCResponse.success(
        {"status": "ok"},
        request_id="123"
    )

    assertions.assert_true(response.is_success())
    assertions.assert_false(response.is_error())
    assertions.assert_equal(response.result["status"], "ok")
    print("  ✅ JSONRPCResponse.success 测试通过")

    # 测试错误响应
    error_response = JSONRPCResponse.error_response(
        ErrorCodes.DEVICE_OFFLINE,
        "Device is offline",
        request_id="456"
    )

    assertions.assert_true(error_response.is_error())
    assertions.assert_false(error_response.is_success())
    assertions.assert_equal(error_response.error["code"], ErrorCodes.DEVICE_OFFLINE)
    print("  ✅ JSONRPCResponse.error_response 测试通过")

    # 测试通知对象
    notification = JSONRPCNotification(
        method=MessageTypes.HEARTBEAT,
        params={"ecu_id": "test_002"}
    )

    assertions.assert_equal(notification.method, MessageTypes.HEARTBEAT)
    assertions.assert_equal(notification.params["ecu_id"], "test_002")
    print("  ✅ JSONRPCNotification 测试通过")


def test_encoding_decoding():
    """测试编码解码"""
    print("\n🧪 测试编码解码...")

    # 创建请求
    request = JSONRPCRequest(
        method=MessageTypes.LOCK,
        params={"ecu_id": "lock_001", "force": True},
        request_id="req_001"
    )

    # 编码
    json_str = encode_message(request)
    data = json.loads(json_str)

    assertions.assert_equal(data["jsonrpc"], "2.0")
    assertions.assert_equal(data["method"], MessageTypes.LOCK)
    assertions.assert_equal(data["params"]["ecu_id"], "lock_001")
    print("  ✅ 编码测试通过")

    # 解码
    decoded = decode_message(json_str)

    # 使用改进的类型检查
    assertions.assert_is_same_type(decoded, request)
    assertions.assert_equal(decoded.method, MessageTypes.LOCK)
    assertions.assert_equal(decoded.params["force"], True)
    assertions.assert_equal(decoded.id, "req_001")
    print("  ✅ 解码测试通过")


def test_mock_functions():
    """测试Mock函数"""
    print("\n🧪 测试Mock函数...")

    # 测试创建Mock请求
    mock_request = MockCodec.create_mock_request(
        MessageTypes.GET_STATUS,
        ecu_id="bike_123",
        device_type=DeviceTypes.SHARED_BIKE
    )

    assertions.assert_equal(mock_request.method, MessageTypes.GET_STATUS)
    assertions.assert_equal(mock_request.params["ecu_id"], "bike_123")
    assertions.assert_equal(mock_request.params["device_type"], DeviceTypes.SHARED_BIKE)
    print("  ✅ create_mock_request 测试通过")

    # 测试创建Mock响应
    mock_response = MockCodec.create_mock_response(mock_request, success=True)

    assertions.assert_true(mock_response.is_success())
    assertions.assert_equal(mock_response.result["ecu_id"], "bike_123")
    print("  ✅ create_mock_response (success) 测试通过")

    # 测试错误响应
    error_response = MockCodec.create_mock_response(
        mock_request,
        success=False,
        error_code=ErrorCodes.DEVICE_BUSY
    )

    assertions.assert_true(error_response.is_error())
    assertions.assert_equal(error_response.error["code"], ErrorCodes.DEVICE_BUSY)
    print("  ✅ create_mock_response (error) 测试通过")

    # 测试创建通知
    notification = MockCodec.create_mock_notification(
        MessageTypes.HEARTBEAT,
        ecu_id="sensor_456"
    )

    assertions.assert_equal(notification.method, MessageTypes.HEARTBEAT)
    assertions.assert_equal(notification.params["ecu_id"], "sensor_456")
    print("  ✅ create_mock_notification 测试通过")


def test_error_handling():
    """测试错误处理"""
    print("\n🧪 测试错误处理...")

    # 测试无效JSON
    invalid_json = "这不是有效的JSON"
    result = decode_message(invalid_json)

    # 检查是否是响应类型（按类名）
    assertions.assert_equal(result.__class__.__name__, "JSONRPCResponse")
    assertions.assert_true(result.is_error())
    print("  ✅ 无效JSON处理测试通过")

    # 测试无效请求
    invalid_request = json.dumps({"jsonrpc": "1.0", "method": "test"})
    result = decode_message(invalid_request)

    assertions.assert_equal(result.__class__.__name__, "JSONRPCResponse")
    assertions.assert_true(result.is_error())
    print("  ✅ 无效JSON-RPC版本处理测试通过")

    # 测试有效请求
    valid_request = json.dumps({
        "jsonrpc": "2.0",
        "method": "test_method",
        "params": {"test": "data"},
        "id": "123"
    })
    result = decode_message(valid_request)
    
    assertions.assert_equal(result.__class__.__name__, "JSONRPCRequest")
    assertions.assert_equal(result.method, "test_method")
    print("  ✅ 有效请求处理测试通过")


def test_message_types():
    """测试消息类型常量"""
    print("\n🧪 测试消息类型常量...")
    
    # 测试一些关键消息类型
    test_cases = [
        ("STATUS_UPDATE", "status_update"),
        ("HEARTBEAT", "heartbeat"),
        ("LOCK", "lock"),
        ("UNLOCK", "unlock"),
        ("GET_STATUS", "get_status"),
    ]
    
    for attr_name, expected_value in test_cases:
        actual_value = getattr(MessageTypes, attr_name)
        assertions.assert_equal(actual_value, expected_value, 
                              f"MessageTypes.{attr_name}")
        print(f"  ✅ MessageTypes.{attr_name} = {actual_value}")
    
    print("  ✅ 所有消息类型常量测试通过")


def test_error_codes():
    """测试错误代码常量"""
    print("\n🧪 测试错误代码常量...")
    
    # 测试一些关键错误代码
    test_cases = [
        ("PARSE_ERROR", -32700),
        ("INVALID_REQUEST", -32600),
        ("DEVICE_OFFLINE", -32001),
        ("DEVICE_BUSY", -32002),
    ]
    
    for attr_name, expected_value in test_cases:
        actual_value = getattr(ErrorCodes, attr_name)
        assertions.assert_equal(actual_value, expected_value, 
                              f"ErrorCodes.{attr_name}")
        print(f"  ✅ ErrorCodes.{attr_name} = {actual_value}")
    
    print("  ✅ 所有错误代码常量测试通过")


async def test_database_logger():
    """测试数据库日志服务"""
    print("\n🧪 测试数据库日志服务...")
    
    # 测试Mock数据库日志服务
    logger = MockDatabaseLogger()
    
    # 测试协议消息日志
    log_id = await logger.log_protocol_message(
        LogDirection.INBOUND,
        MessageTypes.STATUS_UPDATE,
        {"ecu_id": "test_001", "battery": 85},
        ecu_id="test_001",
        request_id="req_123"
    )
    
    assertions.assert_true(len(log_id) > 0)
    print(f"  ✅ 协议消息日志测试通过 (log_id: {log_id[:8]}...)")
    
    # 测试错误日志
    error_id = await logger.log_error(
        ErrorCodes.DEVICE_OFFLINE,
        "设备离线",
        {"ip": "192.168.1.100"},
        "test_001"
    )
    
    assertions.assert_true(len(error_id) > 0)
    print(f"  ✅ 错误日志测试通过 (error_id: {error_id[:8]}...)")
    
    # 测试心跳日志
    heartbeat_id = await logger.log_heartbeat(
        "test_001",
        {"battery": 85, "signal": 4}
    )
    
    assertions.assert_true(len(heartbeat_id) > 0)
    print(f"  ✅ 心跳日志测试通过 (heartbeat_id: {heartbeat_id[:8]}...)")
    
    # 测试统计功能
    start_time = datetime.now() - timedelta(minutes=5)
    end_time = datetime.now()
    stats = await logger.get_protocol_stats(start_time, end_time)
    
    assertions.assert_true("total_messages" in stats)
    assertions.assert_true(stats["total_messages"] >= 0)
    print(f"  ✅ 协议统计测试通过 (总消息数: {stats['total_messages']})")


async def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("🚀 开始协议模块测试")
    print("=" * 60)

    # 运行同步测试
    sync_tests = [
        test_basic_classes,
        test_encoding_decoding,
        test_mock_functions,
        test_error_handling,
        test_message_types,
        test_error_codes,
    ]

    passed = 0
    total = len(sync_tests)

    for test in sync_tests:
        try:
            test()
            passed += 1
            print(f"  ✅ {test.__name__} 通过")
        except Exception as e:
            print(f"  ❌ {test.__name__} 失败: {e}")

    # 运行异步测试
    try:
        await test_database_logger()
        passed += 1
        total += 1
        print(f"  ✅ test_database_logger 通过")
    except Exception as e:
        print(f"  ❌ test_database_logger 失败: {e}")

    print("\n" + "=" * 60)
    print(f"📊 测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有测试通过！协议模块准备就绪。")
    else:
        print("⚠️  部分测试失败，请检查代码。")

    print("=" * 60)


def main():
    """主函数"""
    # 运行异步测试
    asyncio.run(run_all_tests())


if __name__ == "__main__":
    main()