"""
协议模块测试
"""

import json
from datetime import datetime
from jsonrpc import JSONRPCRequest, JSONRPCResponse, JSONRPCNotification
from message_types import MessageTypes, ErrorCodes, DeviceTypes, DeviceStatus
from mock_codec import MockCodec, encode_message, decode_message


def test_basic_classes():
    """测试基础类"""
    print("🧪 测试基础类...")
    
    # 测试请求对象
    request = JSONRPCRequest(
        method=MessageTypes.STATUS_UPDATE,
        params={"ecu_id": "test_001", "value": 100},
        request_id="123"
    )
    
    assert request.method == MessageTypes.STATUS_UPDATE
    assert request.params["ecu_id"] == "test_001"
    assert request.id == "123"
    print("  ✅ JSONRPCRequest 测试通过")
    
    # 测试响应对象
    response = JSONRPCResponse.success(
        {"status": "ok"},
        request_id="123"
    )
    
    assert response.is_success()
    assert not response.is_error()
    assert response.result["status"] == "ok"
    print("  ✅ JSONRPCResponse.success 测试通过")
    
    # 测试错误响应
    error_response = JSONRPCResponse.error_response(
        ErrorCodes.DEVICE_OFFLINE,
        "Device is offline",
        request_id="456"
    )
    
    assert error_response.is_error()
    assert error_response.error["code"] == ErrorCodes.DEVICE_OFFLINE
    print("  ✅ JSONRPCResponse.error_response 测试通过")
    
    # 测试通知对象
    notification = JSONRPCNotification(
        method=MessageTypes.HEARTBEAT,
        params={"ecu_id": "test_002"}
    )
    
    assert notification.method == MessageTypes.HEARTBEAT
    assert notification.params["ecu_id"] == "test_002"
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
    
    assert data["jsonrpc"] == "2.0"
    assert data["method"] == MessageTypes.LOCK
    assert data["params"]["ecu_id"] == "lock_001"
    print("  ✅ 编码测试通过")
    
    # 解码
    decoded = decode_message(json_str)
    
    assert isinstance(decoded, JSONRPCRequest)
    assert decoded.method == MessageTypes.LOCK
    assert decoded.params["force"] is True
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
    
    assert mock_request.method == MessageTypes.GET_STATUS
    assert mock_request.params["ecu_id"] == "bike_123"
    assert mock_request.params["device_type"] == DeviceTypes.SHARED_BIKE
    print("  ✅ create_mock_request 测试通过")
    
    # 测试创建Mock响应
    mock_response = MockCodec.create_mock_response(mock_request, success=True)
    
    assert mock_response.is_success()
    assert mock_response.result["ecu_id"] == "bike_123"
    print("  ✅ create_mock_response (success) 测试通过")
    
    # 测试错误响应
    error_response = MockCodec.create_mock_response(
        mock_request, 
        success=False,
        error_code=ErrorCodes.DEVICE_BUSY
    )
    
    assert error_response.is_error()
    assert error_response.error["code"] == ErrorCodes.DEVICE_BUSY
    print("  ✅ create_mock_response (error) 测试通过")
    
    # 测试创建通知
    notification = MockCodec.create_mock_notification(
        MessageTypes.HEARTBEAT,
        ecu_id="sensor_456"
    )
    
    assert notification.method == MessageTypes.HEARTBEAT
    assert notification.params["ecu_id"] == "sensor_456"
    print("  ✅ create_mock_notification 测试通过")


def test_error_handling():
    """测试错误处理"""
    print("\n🧪 测试错误处理...")
    
    # 测试无效JSON
    invalid_json = "这不是有效的JSON"
    result = decode_message(invalid_json)
    
    assert isinstance(result, JSONRPCResponse)
    assert result.is_error()
    assert result.error["code"] == ErrorCodes.PARSE_ERROR
    print("  ✅ 无效JSON处理测试通过")
    
    # 测试无效请求
    invalid_request = json.dumps({"jsonrpc": "1.0", "method": "test"})
    result = decode_message(invalid_request)
    
    assert result.is_error()
    print("  ✅ 无效JSON-RPC版本处理测试通过")


def test_all_message_types():
    """测试所有消息类型"""
    print("\n🧪 测试所有消息类型...")
    
    test_methods = [
        MessageTypes.STATUS_UPDATE,
        MessageTypes.HEARTBEAT,
        MessageTypes.GET_STATUS,
        MessageTypes.LOCK,
        MessageTypes.UNLOCK,
        MessageTypes.GET_CONFIG,
        MessageTypes.UPDATE_CONFIG,
        MessageTypes.FIRMWARE_UPDATE
    ]
    
    for method in test_methods:
        request = MockCodec.create_mock_request(method)
        response = MockCodec.create_mock_response(request)
        
        assert request.method == method
        assert response.is_success()
        print(f"  ✅ {method} 测试通过")
    
    print(f"  ✅ 所有 {len(test_methods)} 种消息类型测试通过")


def test_imports():
    """测试导入"""
    print("\n🧪 测试导入...")
    
    # 直接测试已导入的模块（从文件开头的导入）
    try:
        # 使用已经导入的模块
        request = JSONRPCRequest("test", {})
        print("  ✅ JSONRPCRequest 导入测试通过")
        
        # 测试常量
        print(f"  ✅ MessageTypes.STATUS_UPDATE = {MessageTypes.STATUS_UPDATE}")
        print(f"  ✅ ErrorCodes.DEVICE_OFFLINE = {ErrorCodes.DEVICE_OFFLINE}")
        print(f"  ✅ DeviceTypes.SHARED_BIKE = {DeviceTypes.SHARED_BIKE}")
        
        print("  ✅ 所有导入测试通过")
    except Exception as e:
        print(f"  ❌ 导入测试失败: {e}")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("🚀 开始协议模块测试")
    print("=" * 60)
    
    tests = [
        test_basic_classes,
        test_encoding_decoding,
        test_mock_functions,
        test_error_handling,
        test_all_message_types,
        test_imports
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ❌ {test.__name__} 失败: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！协议模块准备就绪。")
    else:
        print("⚠️  部分测试失败，请检查代码。")
    
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()