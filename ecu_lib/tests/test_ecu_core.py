"""
ECU核心模块测试
"""
import asyncio
import pytest
import logging
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from ..core.base_ecu import BaseECU, ECUConfig, ECUStatus, ECUCommand
from ..core.ecu_factory import ECUFactory, DeviceCategory
from ..core.ecu_simulator import ECUSimulator, SimulationMode, SimulationEvent
from protocol.message_types import DeviceTypes, MessageTypes, ErrorCodes

# 设置测试日志
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class TestBaseECU:
    """BaseECU测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.config = ECUConfig(
            ecu_id="test_ecu_001",
            device_type=DeviceTypes.SHARED_BIKE,
            firmware_version="1.0.0",
            heartbeat_interval=5,  # 测试中使用较短的心跳间隔
            command_timeout=2
        )
    
    def test_ecu_config_creation(self):
        """测试ECU配置创建"""
        assert self.config.ecu_id == "test_ecu_001"
        assert self.config.device_type == DeviceTypes.SHARED_BIKE
        assert self.config.heartbeat_interval == 5
        assert self.config.command_timeout == 2
    
    @pytest.mark.asyncio
    async def test_ecu_initialization(self):
        """测试ECU初始化"""
        # 创建Mock设备
        class MockECU(BaseECU):
            async def _execute_lock(self, params):
                return {"success": True}
            async def _execute_unlock(self, params):
                return {"success": True}
            async def _execute_get_status(self, params):
                return {"success": True, "status": {"test": "data"}}
        
        ecu = MockECU(self.config)
        
        assert ecu.ecu_id == "test_ecu_001"
        assert ecu.status == ECUStatus.OFFLINE
        assert ecu.device_type == DeviceTypes.SHARED_BIKE
    
    @pytest.mark.asyncio
    async def test_ecu_start_stop(self):
        """测试ECU启动和停止"""
        class MockECU(BaseECU):
            async def _execute_lock(self, params):
                return {"success": True}
            async def _execute_unlock(self, params):
                return {"success": True}
            async def _execute_get_status(self, params):
                return {"success": True, "status": {"test": "data"}}
        
        ecu = MockECU(self.config)
        
        # 启动ECU
        await ecu.start()
        assert ecu.status == ECUStatus.ONLINE
        
        # 等待一小段时间确保心跳任务启动
        await asyncio.sleep(0.1)
        
        # 停止ECU
        await ecu.stop()
        assert ecu.status == ECUStatus.OFFLINE
    
    @pytest.mark.asyncio
    async def test_ecu_execute_command(self):
        """测试ECU执行命令"""
        class MockECU(BaseECU):
            async def _execute_lock(self, params):
                return {"success": True, "action": "lock"}
            async def _execute_unlock(self, params):
                return {"success": True, "action": "unlock"}
            async def _execute_get_status(self, params):
                return {"success": True, "status": {"test": "data"}}
        
        ecu = MockECU(self.config)
        await ecu.start()
        
        # 测试有效命令
        result = await ecu.execute_command(MessageTypes.GET_STATUS, {})
        assert result["success"] is True
        
        # 测试无效命令
        result = await ecu.execute_command("invalid_command", {})
        assert result["success"] is False
        assert result["error_code"] == ErrorCodes.METHOD_NOT_FOUND
        
        await ecu.stop()
    
    @pytest.mark.asyncio
    async def test_ecu_get_status_dict(self):
        """测试获取状态字典"""
        class MockECU(BaseECU):
            async def _execute_lock(self, params):
                return {"success": True}
            async def _execute_unlock(self, params):
                return {"success": True}
            async def _execute_get_status(self, params):
                return {"success": True, "status": {"test": "data"}}
        
        ecu = MockECU(self.config)
        
        status = ecu.get_status_dict()
        assert status["ecu_id"] == "test_ecu_001"
        assert status["device_type"] == DeviceTypes.SHARED_BIKE
        assert status["status"] == ECUStatus.OFFLINE.value
        assert "timestamp" in status
    
    @pytest.mark.asyncio
    async def test_ecu_error_handling(self):
        """测试ECU错误处理"""
        class MockECU(BaseECU):
            async def _execute_lock(self, params):
                raise Exception("Test error")
            async def _execute_unlock(self, params):
                return {"success": True}
            async def _execute_get_status(self, params):
                return {"success": True, "status": {"test": "data"}}
        
        ecu = MockECU(self.config)
        await ecu.start()
        
        # 测试异常命令
        result = await ecu.execute_command(MessageTypes.LOCK, {})
        assert result["success"] is False
        assert result["error_code"] == ErrorCodes.INTERNAL_ERROR
        
        assert ecu._error_count > 0
        
        await ecu.stop()


class TestECUFactory:
    """ECUFactory测试"""
    
    def setup_method(self):
        """测试前设置"""
        ECUFactory.initialize()
    
    def test_factory_initialization(self):
        """测试工厂初始化"""
        device_types = ECUFactory.list_device_types()
        assert len(device_types) > 0
        assert DeviceTypes.SHARED_BIKE in device_types
        assert DeviceTypes.ACCESS_CONTROL in device_types
    
    def test_device_categories(self):
        """测试设备分类"""
        categories = ECUFactory.list_device_categories()
        assert DeviceCategory.TRANSPORTATION in categories
        assert DeviceCategory.SECURITY in categories
        
        # 检查共享单车分类
        bike_category = ECUFactory.get_device_category(DeviceTypes.SHARED_BIKE)
        assert bike_category == DeviceCategory.TRANSPORTATION
        
        # 检查门禁分类
        door_category = ECUFactory.get_device_category(DeviceTypes.ACCESS_CONTROL)
        assert door_category == DeviceCategory.SECURITY
    
    def test_config_templates(self):
        """测试配置模板"""
        bike_template = ECUFactory.get_config_template(DeviceTypes.SHARED_BIKE)
        assert "heartbeat_interval" in bike_template
        assert "command_timeout" in bike_template
        
        door_template = ECUFactory.get_config_template(DeviceTypes.ACCESS_CONTROL)
        assert "heartbeat_interval" in door_template
        assert "command_timeout" in door_template
    
    @pytest.mark.asyncio
    async def test_create_ecu(self):
        """测试创建ECU"""
        config = ECUConfig(
            ecu_id="factory_test_001",
            device_type=DeviceTypes.SHARED_BIKE,
            firmware_version="1.0.0"
        )
        
        ecu = ECUFactory.create_ecu(config)
        assert ecu is not None
        assert ecu.ecu_id == "factory_test_001"
        assert ecu.device_type == DeviceTypes.SHARED_BIKE
        
        # 测试未知设备类型
        config.device_type = "unknown_type"
        ecu = ECUFactory.create_ecu(config)
        assert ecu is None
    
    @pytest.mark.asyncio
    async def test_create_ecu_from_dict(self):
        """测试从字典创建ECU"""
        ecu_data = {
            "ecu_id": "dict_test_001",
            "device_type": DeviceTypes.SHARED_BIKE,
            "firmware_version": "2.0.0",
            "config": {
                "heartbeat_interval": 20,
                "command_timeout": 5
            }
        }
        
        ecu = ECUFactory.create_ecu_from_dict(ecu_data)
        assert ecu is not None
        assert ecu.ecu_id == "dict_test_001"
        assert ecu.firmware_version == "2.0.0"
        assert ecu.config.heartbeat_interval == 20
    
    def test_validate_device_config(self):
        """测试验证设备配置"""
        # 测试有效配置
        validation = ECUFactory.validate_device_config(
            ecu_id="valid_ecu",
            device_type=DeviceTypes.SHARED_BIKE,
            config={"heartbeat_interval": 30, "command_timeout": 10}
        )
        assert validation["valid"] is True
        assert len(validation["errors"]) == 0
        
        # 测试无效设备类型
        validation = ECUFactory.validate_device_config(
            ecu_id="invalid_ecu",
            device_type="unknown_type",
            config={}
        )
        assert validation["valid"] is False
        assert len(validation["errors"]) > 0
        
        # 测试无效ECU ID
        validation = ECUFactory.validate_device_config(
            ecu_id="",  # 空ID
            device_type=DeviceTypes.SHARED_BIKE,
            config={}
        )
        assert validation["valid"] is False
    
    def test_factory_statistics(self):
        """测试工厂统计"""
        stats = ECUFactory.get_statistics()
        assert "total_device_types" in stats
        assert "category_distribution" in stats
        assert "registered_types" in stats
        
        assert stats["total_device_types"] > 0


class TestECUSimulator:
    """ECUSimulator测试"""
    
    def setup_method(self):
        """测试前设置"""
        ECUFactory.initialize()
    
    @pytest.mark.asyncio
    async def test_simulator_initialization(self):
        """测试模拟器初始化"""
        simulator = ECUSimulator()
        
        assert simulator.simulation_mode == SimulationMode.DYNAMIC
        assert simulator.is_running is False
        assert len(simulator.simulated_devices) == 0
        
        # 检查统计信息
        stats = simulator.get_statistics()
        assert stats["is_running"] is False
        assert stats["current_devices"] == 0
    
    @pytest.mark.asyncio
    async def test_create_simulated_device(self):
        """测试创建模拟设备"""
        simulator = ECUSimulator()
        
        ecu = await simulator.create_simulated_device(
            ecu_id="sim_test_001",
            device_type=DeviceTypes.SHARED_BIKE,
            behavior="normal"
        )
        
        assert ecu is not None
        assert ecu.ecu_id == "sim_test_001"
        assert ecu.device_type == DeviceTypes.SHARED_BIKE
        assert ecu.status == ECUStatus.ONLINE
        
        # 检查设备是否已注册
        assert "sim_test_001" in simulator.simulated_devices
        assert simulator.stats["devices_created"] == 1
        
        # 清理
        await simulator.destroy_simulated_device("sim_test_001")
    
    @pytest.mark.asyncio
    async def test_simulate_device_behavior(self):
        """测试模拟设备行为"""
        simulator = ECUSimulator()
        
        # 创建设备
        await simulator.create_simulated_device(
            ecu_id="behavior_test_001",
            device_type=DeviceTypes.SHARED_BIKE,
            behavior="normal"
        )
        
        # 模拟行为（短时间）
        task = asyncio.create_task(
            simulator.simulate_device_behavior("behavior_test_001", duration=2)
        )
        
        # 等待模拟开始
        await asyncio.sleep(0.5)
        
        # 检查统计
        stats_before = simulator.stats["commands_sent"]
        
        # 等待模拟完成
        await asyncio.sleep(2)
        
        # 检查命令是否已发送
        stats_after = simulator.stats["commands_sent"]
        assert stats_after > stats_before
        
        # 清理
        await simulator.destroy_simulated_device("behavior_test_001")
        task.cancel()
    
    @pytest.mark.asyncio
    async def test_event_handling(self):
        """测试事件处理"""
        simulator = ECUSimulator()
        
        # 创建事件处理器
        events_received = []
        
        async def event_handler(data):
            events_received.append(data)
        
        # 注册事件处理器
        simulator.register_event_handler(SimulationEvent.DEVICE_CONNECT, event_handler)
        
        # 创建设备（应该触发事件）
        await simulator.create_simulated_device(
            ecu_id="event_test_001",
            device_type=DeviceTypes.SHARED_BIKE
        )
        
        # 等待事件处理
        await asyncio.sleep(0.1)
        
        assert len(events_received) > 0
        assert events_received[0]["ecu_id"] == "event_test_001"
        
        # 清理
        await simulator.destroy_simulated_device("event_test_001")
        simulator.unregister_event_handler(SimulationEvent.DEVICE_CONNECT, event_handler)
    
    @pytest.mark.asyncio
    async def test_generate_report(self):
        """测试生成报告"""
        simulator = ECUSimulator()
        
        # 创建设备
        await simulator.create_simulated_device(
            ecu_id="report_test_001",
            device_type=DeviceTypes.SHARED_BIKE
        )
        
        # 发送一些命令
        ecu = simulator.simulated_devices["report_test_001"]
        await ecu.execute_command(MessageTypes.GET_STATUS, {})
        
        # 生成报告
        report = await simulator.generate_report()
        
        assert "report_id" in report
        assert "summary" in report
        assert "device_analysis" in report
        assert "performance" in report
        
        assert report["summary"]["total_devices"] == 1
        assert report["summary"]["commands_sent"] >= 1
        
        # 清理
        await simulator.destroy_simulated_device("report_test_001")


@pytest.mark.integration
class TestIntegration:
    """集成测试"""
    
    @pytest.mark.asyncio
    async def test_factory_and_simulator_integration(self):
        """测试工厂和模拟器集成"""
        # 初始化
        ECUFactory.initialize()
        simulator = ECUSimulator()
        
        # 使用工厂创建设备配置
        config = ECUConfig(
            ecu_id="integration_test_001",
            device_type=DeviceTypes.SHARED_BIKE,
            firmware_version="1.0.0"
        )
        
        # 工厂创建设备
        ecu = ECUFactory.create_ecu(config)
        assert ecu is not None
        
        # 模拟器注册设备
        await ecu.start()
        # 注意：这里简化了，实际应该使用模拟器的方法
        
        # 测试设备功能
        status = ecu.get_status_dict()
        assert status["ecu_id"] == "integration_test_001"
        
        # 清理
        await ecu.stop()
    
    @pytest.mark.asyncio
    async def test_command_flow(self):
        """测试命令流程"""
        # 创建设备
        class TestECU(BaseECU):
            async def _execute_lock(self, params):
                return {"success": True, "locked": True}
            async def _execute_unlock(self, params):
                return {"success": True, "locked": False}
            async def _execute_get_status(self, params):
                return {"success": True, "status": {"test": "ok"}}
        
        config = ECUConfig(
            ecu_id="flow_test_001",
            device_type=DeviceTypes.SHARED_BIKE
        )
        
        ecu = TestECU(config)
        await ecu.start()
        
        # 测试命令序列
        commands = [
            (MessageTypes.GET_STATUS, {}),
            (MessageTypes.LOCK, {"force": True}),
            (MessageTypes.UNLOCK, {"user_id": "test"})
        ]
        
        for command, params in commands:
            result = await ecu.execute_command(command, params)
            assert result["success"] is True
        
        # 验证统计
        assert ecu._stats["commands_received"] == 3
        assert ecu._stats["commands_executed"] == 3
        
        await ecu.stop()


if __name__ == "__main__":
    """运行测试"""
    import sys
    sys.exit(pytest.main([__file__, "-v"]))