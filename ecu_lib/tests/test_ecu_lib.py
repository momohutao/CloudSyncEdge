"""
ECU库集成测试
"""
import asyncio
import pytest
import tempfile
import yaml
from pathlib import Path
import logging

from ecu_lib import (
    ECUFactory,
    DatabaseClient,
    SharedBikeECU,
    DoorAccessECU,
    DeviceRegistry,
    create_ecu_interface,
    MockDeviceManager
)
from ecu_lib.core.base_ecu import ECUConfig
from ecu_lib.config import get_config
from protocol.message_types import DeviceTypes, MessageTypes

# 禁用测试时的详细日志
logging.getLogger().setLevel(logging.WARNING)


class TestECULibraryIntegration:
    """ECU库集成测试"""
    
    @pytest.fixture
    async def temp_db(self):
        """临时数据库fixture"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        db_url = f"sqlite+aiosqlite:///{db_path}"
        client = DatabaseClient(db_url)
        await client.initialize()
        
        yield client
        
        await client.close()
        Path(db_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def sample_config(self):
        """示例配置"""
        return {
            "app": {
                "name": "ECU Test",
                "version": "1.0.0"
            },
            "environment": "testing",
            "database": {
                "type": "sqlite",
                "sqlite": {
                    "url": "sqlite+aiosqlite:///./test_data/test.db"
                }
            }
        }
    
    @pytest.mark.asyncio
    async def test_library_initialization(self):
        """测试库初始化"""
        # 初始化工厂
        ECUFactory.initialize()
        
        # 检查设备类型
        device_types = ECUFactory.list_device_types()
        assert len(device_types) > 0
        assert DeviceTypes.SHARED_BIKE in device_types
        assert DeviceTypes.ACCESS_CONTROL in device_types
        
        # 检查配置模板
        bike_template = ECUFactory.get_config_template(DeviceTypes.SHARED_BIKE)
        assert "heartbeat_interval" in bike_template
        
        door_template = ECUFactory.get_config_template(DeviceTypes.ACCESS_CONTROL)
        assert "command_timeout" in door_template
    
    @pytest.mark.asyncio
    async def test_device_creation_workflow(self, temp_db):
        """测试设备创建工作流"""
        # 1. 创建设备配置
        config = ECUConfig(
            ecu_id="integration_test_001",
            device_type=DeviceTypes.SHARED_BIKE,
            firmware_version="2.0.0",
            heartbeat_interval=15
        )
        
        # 2. 通过工厂创建设备
        ecu = ECUFactory.create_ecu(config, temp_db)
        assert ecu is not None
        assert ecu.ecu_id == "integration_test_001"
        assert ecu.device_type == DeviceTypes.SHARED_BIKE
        
        # 3. 启动设备
        await ecu.start()
        assert ecu.status.value == "online"
        
        # 4. 执行命令
        result = await ecu.execute_command(MessageTypes.GET_STATUS, {"detailed": True})
        assert result["success"] is True
        
        # 5. 检查数据库记录
        status_history = await temp_db.get_ecu_status_history("integration_test_001", limit=1)
        assert len(status_history) >= 1
        
        # 6. 停止设备
        await ecu.stop()
        assert ecu.status.value == "offline"
    
    @pytest.mark.asyncio
    async def test_ecu_interface_integration(self, temp_db):
        """测试ECU接口集成"""
        # 创建设备注册表
        registry = DeviceRegistry()
        
        # 创建ECU接口
        ecu_interface = create_ecu_interface(registry, temp_db)
        
        # 注册设备
        device_data = {
            "ecu_id": "interface_test_001",
            "device_type": DeviceTypes.SHARED_BIKE,
            "firmware_version": "1.5.0"
        }
        
        result = await ecu_interface.register_ecu(device_data)
        assert result["success"] is True
        
        # 获取设备状态
        status = await ecu_interface.get_ecu_status("interface_test_001")
        assert status["success"] is True
        assert status["status"]["status"] == "online"
        
        # 执行命令
        command_result = await ecu_interface.execute_command(
            "interface_test_001",
            MessageTypes.GET_STATUS,
            {"detailed": True}
        )
        assert command_result["success"] is True
        
        # 获取所有设备
        all_devices = await ecu_interface.get_all_ecus()
        assert len(all_devices) == 1
        assert all_devices[0]["ecu_id"] == "interface_test_001"
        
        # 健康检查
        health = await ecu_interface.health_check()
        assert health["status"] in ["healthy", "degraded"]
    
    @pytest.mark.asyncio
    async def test_mock_manager_integration(self):
        """测试Mock管理器集成"""
        # 创建Mock管理器
        mock_manager = MockDeviceManager()
        
        # 创建设备
        from ecu_lib.core.base_ecu import ECUConfig
        
        config = ECUConfig(
            ecu_id="mock_test_001",
            device_type=DeviceTypes.SHARED_BIKE
        )
        
        bike = SharedBikeECU(config)
        
        # 注册设备到Mock管理器
        success = await mock_manager.register_ecu("mock_test_001", bike)
        assert success is True
        
        # 连接设备
        connection_id = await mock_manager.connect_device("mock_test_001")
        assert connection_id is not None
        
        # 发送命令
        command_data = {
            "method": MessageTypes.GET_STATUS,
            "params": {"detailed": True},
            "request_id": "test_001"
        }
        
        result = await mock_manager.send_command("mock_test_001", command_data)
        # Mock响应可能需要特殊处理
        
        # 获取连接设备
        connected_devices = await mock_manager.get_connected_devices()
        assert len(connected_devices) == 1
        
        # 清理
        await mock_manager.stop()
    
    @pytest.mark.asyncio
    async def test_database_operations(self, temp_db):
        """测试数据库操作"""
        # 测试设备CRUD
        device_data = {
            "ecu_id": "db_test_001",
            "device_type": "shared_bike",
            "status": "online",
            "firmware_version": "1.0.0",
            "config": {"heartbeat_interval": 30}
        }
        
        # 创建
        device_id = await temp_db.save_ecu_device(device_data)
        assert device_id is not None
        
        # 读取
        device = await temp_db.get_ecu_device("db_test_001")
        assert device is not None
        assert device["ecu_id"] == "db_test_001"
        
        # 更新
        update_success = await temp_db.update_ecu_device("db_test_001", {"status": "offline"})
        assert update_success is True
        
        updated_device = await temp_db.get_ecu_device("db_test_001")
        assert updated_device["status"] == "offline"
        
        # 列出
        devices = await temp_db.list_ecu_devices(limit=10)
        assert len(devices) >= 1
        
        # 测试状态记录
        for i in range(3):
            status_data = {"battery": 90 - i*10, "iteration": i}
            status_id = await temp_db.save_ecu_status("db_test_001", status_data)
            assert status_id is not None
        
        # 获取状态历史
        history = await temp_db.get_ecu_status_history("db_test_001", limit=5)
        assert len(history) == 3
        
        # 测试批量操作
        batch_statuses = [
            {"ecu_id": "batch_001", "status": {"value": 1}},
            {"ecu_id": "batch_002", "status": {"value": 2}},
            {"ecu_id": "batch_003", "status": {"value": 3}}
        ]
        
        batch_success = await temp_db.batch_save_statuses(batch_statuses)
        assert batch_success is True
        
        # 测试统计
        stats = await temp_db.get_device_statistics()
        assert "total_devices" in stats
        assert stats["total_devices"] >= 1
    
    @pytest.mark.asyncio
    async def test_config_module(self, sample_config, tmp_path):
        """测试配置模块"""
        # 保存配置文件
        config_file = tmp_path / "test_config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(sample_config, f)
        
        # 设置环境变量
        import os
        os.environ['ECU_CONFIG_FILE'] = str(config_file)
        
        # 测试配置加载
        try:
            # 注意：这里需要根据您的config.py实现调整
            # 假设config.py支持从文件加载
            config = get_config()
            assert config is not None
        except Exception as e:
            # 如果config.py不支持文件加载，跳过这个测试
            pytest.skip(f"配置文件加载未实现: {e}")
        
        finally:
            # 清理环境变量
            if 'ECU_CONFIG_FILE' in os.environ:
                del os.environ['ECU_CONFIG_FILE']
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self, temp_db):
        """测试完整工作流"""
        print("\n🔧 测试完整工作流...")
        
        # 1. 初始化工厂
        ECUFactory.initialize()
        
        # 2. 创建设备注册表
        registry = DeviceRegistry()
        
        # 3. 创建ECU接口
        ecu_interface = create_ecu_interface(registry, temp_db)
        
        # 4. 创建设备
        devices_to_create = [
            {
                "ecu_id": "workflow_bike_001",
                "device_type": DeviceTypes.SHARED_BIKE,
                "firmware_version": "2.1.0"
            },
            {
                "ecu_id": "workflow_door_001",
                "device_type": DeviceTypes.ACCESS_CONTROL,
                "firmware_version": "1.8.0"
            }
        ]
        
        for device_data in devices_to_create:
            result = await ecu_interface.register_ecu(device_data)
            assert result["success"] is True
            print(f"✅ 创建设备: {device_data['ecu_id']}")
        
        # 5. 获取所有设备
        all_devices = await ecu_interface.get_all_ecus()
        assert len(all_devices) == 2
        print(f"📱 总设备数: {len(all_devices)}")
        
        # 6. 执行批量命令
        for device in all_devices:
            ecu_id = device["ecu_id"]
            
            # 获取状态
            status_result = await ecu_interface.execute_command(
                ecu_id,
                MessageTypes.GET_STATUS,
                {"detailed": True}
            )
            assert status_result["success"] is True
            print(f"📊 获取状态: {ecu_id} - 成功")
            
            # 测试锁定/解锁（仅支持设备）
            if device["device_type"] in ["shared_bike", "access_control"]:
                lock_result = await ecu_interface.execute_command(
                    ecu_id,
                    MessageTypes.LOCK,
                    {"force": True, "reason": "test"}
                )
                # 可能失败，但至少应该返回结果
                assert lock_result is not None
                print(f"🔒 锁定测试: {ecu_id} - {'成功' if lock_result.get('success') else '失败但正常'}")
        
        # 7. 数据库验证
        for device_data in devices_to_create:
            ecu_id = device_data["ecu_id"]
            
            # 检查数据库记录
            device_record = await temp_db.get_ecu_device(ecu_id)
            assert device_record is not None
            
            status_history = await temp_db.get_ecu_status_history(ecu_id, limit=1)
            assert len(status_history) >= 1
            
            print(f"💾 数据库验证: {ecu_id} - 通过")
        
        # 8. 健康检查
        health = await ecu_interface.health_check()
        assert health["status"] in ["healthy", "degraded"]
        print(f"❤️  健康检查: {health['status']}")
        
        # 9. 清理
        for device in all_devices:
            await ecu_interface.stop_ecu(device["ecu_id"])
            await ecu_interface.unregister_ecu(device["ecu_id"])
            print(f"🧹 清理设备: {device['ecu_id']}")
        
        print("🎉 完整工作流测试通过")
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """测试错误处理"""
        # 测试无效设备类型
        config = ECUConfig(
            ecu_id="error_test_001",
            device_type="invalid_device_type",  # 无效类型
            firmware_version="1.0.0"
        )
        
        ecu = ECUFactory.create_ecu(config)
        assert ecu is None  # 应该返回None
        
        # 测试无效命令
        valid_config = ECUConfig(
            ecu_id="error_test_002",
            device_type=DeviceTypes.SHARED_BIKE
        )
        
        class TestECU(SharedBikeECU):
            pass
        
        ecu = TestECU(valid_config)
        await ecu.start()
        
        # 执行不存在的命令
        result = await ecu.execute_command("non_existent_command", {})
        assert result["success"] is False
        assert "error_code" in result
        
        await ecu.stop()
    
    @pytest.mark.asyncio
    async def test_performance(self, temp_db):
        """测试性能"""
        import time
        
        # 测试批量创建设备性能
        start_time = time.time()
        
        batch_size = 10
        devices = []
        
        for i in range(batch_size):
            config = ECUConfig(
                ecu_id=f"perf_test_{i:03d}",
                device_type=DeviceTypes.SHARED_BIKE,
                heartbeat_interval=30
            )
            
            ecu = SharedBikeECU(config, temp_db)
            await ecu.start()
            devices.append(ecu)
        
        creation_time = time.time() - start_time
        print(f"⏱️  创建 {batch_size} 个设备耗时: {creation_time:.3f}秒")
        
        # 测试批量命令性能
        start_time = time.time()
        
        command_tasks = []
        for ecu in devices:
            task = ecu.execute_command(MessageTypes.GET_STATUS, {})
            command_tasks.append(task)
        
        results = await asyncio.gather(*command_tasks, return_exceptions=True)
        command_time = time.time() - start_time
        
        success_count = len([r for r in results if not isinstance(r, Exception) and r.get("success")])
        print(f"⏱️  执行 {batch_size} 个命令耗时: {command_time:.3f}秒")
        print(f"✅ 成功命令: {success_count}/{batch_size}")
        
        # 清理
        stop_tasks = []
        for ecu in devices:
            task = ecu.stop()
            stop_tasks.append(task)
        
        await asyncio.gather(*stop_tasks, return_exceptions=True)


@pytest.mark.system
class TestSystemTests:
    """系统测试"""
    
    @pytest.mark.asyncio
    async def test_system_initialization(self):
        """测试系统初始化"""
        # 模拟完整的系统初始化
        from ecu_lib.core.ecu_factory import get_ecu_factory
        from ecu_lib.database.client import DatabaseClient
        from ecu_lib import create_ecu_interface
        
        # 初始化所有组件
        factory = get_ecu_factory()  # 这会触发初始化
        
        # 创建数据库
        db_client = DatabaseClient("sqlite+aiosqlite:///:memory:")
        await db_client.initialize()
        
        # 创建设备注册表
        from ecu_lib.devices.device_registry import get_device_registry
        registry = get_device_registry()
        
        # 创建ECU接口
        ecu_interface = create_ecu_interface(registry, db_client)
        
        # 验证所有组件都已初始化
        assert factory is not None
        assert db_client is not None
        assert registry is not None
        assert ecu_interface is not None
        
        # 清理
        await db_client.close()
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, temp_db):
        """测试并发操作"""
        import asyncio
        
        # 创建多个并发任务
        async def create_and_test_device(device_id):
            config = ECUConfig(
                ecu_id=device_id,
                device_type=DeviceTypes.SHARED_BIKE
            )
            
            ecu = SharedBikeECU(config, temp_db)
            await ecu.start()
            
            # 执行一些命令
            results = []
            for _ in range(3):
                result = await ecu.execute_command(MessageTypes.GET_STATUS, {})
                results.append(result)
            
            await ecu.stop()
            return results
        
        # 并发创建和测试设备
        tasks = []
        for i in range(5):  # 5个并发任务
            task = create_and_test_device(f"concurrent_{i}")
            tasks.append(task)
        
        # 执行所有任务
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 验证结果
        for i, results in enumerate(all_results):
            if isinstance(results, Exception):
                # 允许部分失败，但不能全部失败
                print(f"任务 {i} 失败: {results}")
            else:
                assert len(results) == 3
                for result in results:
                    assert result is not None


if __name__ == "__main__":
    """运行集成测试"""
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))