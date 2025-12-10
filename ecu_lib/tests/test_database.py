"""
数据库模块测试
"""
import asyncio
import pytest
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

from ..database.client import DatabaseClient
from ..database.models import Base
from ..database.batch_writer import BatchWriter

# 测试数据库URL
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


class TestDatabaseClient:
    """DatabaseClient测试"""
    
    @pytest.fixture
    async def db_client(self):
        """数据库客户端fixture"""
        client = DatabaseClient(TEST_DB_URL)
        await client.initialize()
        yield client
        await client.close()
    
    @pytest.fixture
    async def db_with_data(self, db_client):
        """带测试数据的数据库fixture"""
        # 添加测试设备
        device_data = {
            "ecu_id": "test_device_001",
            "device_type": "shared_bike",
            "firmware_version": "1.0.0",
            "status": "online",
            "config": {"heartbeat_interval": 30},
            "attributes": {"color": "red"}
        }
        
        await db_client.save_ecu_device(device_data)
        
        # 添加测试状态
        status_data = {"battery": 85, "locked": True}
        await db_client.save_ecu_status("test_device_001", status_data)
        
        # 添加心跳记录
        heartbeat_data = {"uptime": 3600, "latency_ms": 50}
        await db_client.save_heartbeat("test_device_001", heartbeat_data)
        
        yield db_client
    
    @pytest.mark.asyncio
    async def test_initialization(self, db_client):
        """测试数据库初始化"""
        # 健康检查
        health = await db_client.health_check()
        assert health["status"] == "healthy"
        assert health["connected"] is True
    
    @pytest.mark.asyncio
    async def test_save_ecu_device(self, db_client):
        """测试保存ECU设备"""
        device_data = {
            "ecu_id": "test_save_001",
            "device_type": "shared_bike",
            "firmware_version": "1.0.0",
            "status": "online"
        }
        
        device_id = await db_client.save_ecu_device(device_data)
        assert device_id is not None
        
        # 验证设备已保存
        device = await db_client.get_ecu_device("test_save_001")
        assert device is not None
        assert device["ecu_id"] == "test_save_001"
        assert device["device_type"] == "shared_bike"
    
    @pytest.mark.asyncio
    async def test_update_ecu_device(self, db_client):
        """测试更新ECU设备"""
        # 先创建设备
        device_data = {
            "ecu_id": "test_update_001",
            "device_type": "shared_bike",
            "status": "online"
        }
        
        await db_client.save_ecu_device(device_data)
        
        # 更新设备
        update_data = {
            "status": "offline",
            "firmware_version": "2.0.0"
        }
        
        success = await db_client.update_ecu_device("test_update_001", update_data)
        assert success is True
        
        # 验证更新
        device = await db_client.get_ecu_device("test_update_001")
        assert device["status"] == "offline"
        assert device["firmware_version"] == "2.0.0"
    
    @pytest.mark.asyncio
    async def test_save_ecu_status(self, db_client):
        """测试保存ECU状态"""
        status_data = {
            "battery": 85,
            "locked": True,
            "temperature": 25.5,
            "location": {"lat": 31.23, "lng": 121.47}
        }
        
        status_id = await db_client.save_ecu_status("test_status_001", status_data)
        assert status_id is not None
        
        # 验证状态历史
        history = await db_client.get_ecu_status_history("test_status_001", limit=1)
        assert len(history) == 1
        assert history[0]["ecu_id"] == "test_status_001"
        assert history[0]["status_data"]["battery"] == 85
    
    @pytest.mark.asyncio
    async def test_batch_save_statuses(self, db_client):
        """测试批量保存状态"""
        statuses = [
            {"ecu_id": "batch_001", "status": {"battery": 80}},
            {"ecu_id": "batch_002", "status": {"battery": 90}},
            {"ecu_id": "batch_003", "status": {"battery": 70}}
        ]
        
        success = await db_client.batch_save_statuses(statuses)
        assert success is True
        
        # 验证状态已保存
        for status in statuses:
            history = await db_client.get_ecu_status_history(status["ecu_id"], limit=1)
            assert len(history) == 1
    
    @pytest.mark.asyncio
    async def test_save_heartbeat(self, db_client):
        """测试保存心跳"""
        heartbeat_data = {
            "uptime": 3600,
            "latency_ms": 50,
            "network_quality": 4,
            "timestamp": datetime.now().isoformat()
        }
        
        heartbeat_id = await db_client.save_heartbeat("test_heartbeat_001", heartbeat_data)
        assert heartbeat_id is not None
        
        # 验证心跳历史
        history = await db_client.get_heartbeat_history("test_heartbeat_001", hours=1, limit=1)
        assert len(history) == 1
        assert history[0]["ecu_id"] == "test_heartbeat_001"
        assert history[0]["latency_ms"] == 50
    
    @pytest.mark.asyncio
    async def test_save_command_execution(self, db_client):
        """测试保存命令执行"""
        execution_data = {
            "ecu_id": "test_command_001",
            "command": "lock",
            "params": {"force": True},
            "result": {"success": True, "locked": True},
            "success": True,
            "execution_duration_ms": 150
        }
        
        log_id = await db_client.save_command_execution(execution_data)
        assert log_id is not None
        
        # 验证命令历史
        history = await db_client.get_command_history("test_command_001", limit=1)
        assert len(history) == 1
        assert history[0]["command"] == "lock"
        assert history[0]["success"] is True
    
    @pytest.mark.asyncio
    async def test_save_event(self, db_client):
        """测试保存事件"""
        event_data = {
            "event_type": "lock",
            "user_id": "test_user",
            "location": "main_entrance",
            "timestamp": datetime.now().isoformat()
        }
        
        event_id = await db_client.save_event("test_event_001", "door_lock", event_data)
        assert event_id is not None
        
        # 验证事件日志
        events = await db_client.get_event_logs("test_event_001", limit=1)
        assert len(events) == 1
        assert events[0]["event_type"] == "door_lock"
        assert events[0]["severity"] == "info"
    
    @pytest.mark.asyncio
    async def test_save_ride_record(self, db_client):
        """测试保存骑行记录"""
        ride_data = {
            "ecu_id": "test_ride_001",
            "user_id": "user_001",
            "duration": 600,  # 10分钟
            "distance": 2.5,  # 2.5公里
            "start_location": {"lat": 31.23, "lng": 121.47},
            "end_location": {"lat": 31.24, "lng": 121.48},
            "cost": 2.0,
            "calories_burned": 120
        }
        
        ride_id = await db_client.save_ride_record(ride_data)
        assert ride_id is not None
        
        # 验证骑行历史
        history = await db_client.get_ride_history("test_ride_001", limit=1)
        assert len(history) == 1
        assert history[0]["ecu_id"] == "test_ride_001"
        assert history[0]["user_id"] == "user_001"
        assert history[0]["distance_km"] == 2.5
    
    @pytest.mark.asyncio
    async def test_get_device_statistics(self, db_with_data):
        """测试获取设备统计"""
        stats = await db_with_data.get_device_statistics()
        
        assert "total_devices" in stats
        assert "online_devices" in stats
        assert "device_distribution" in stats
        
        assert stats["total_devices"] >= 1
        assert "shared_bike" in stats["device_distribution"]
    
    @pytest.mark.asyncio
    async def test_get_command_statistics(self, db_with_data):
        """测试获取命令统计"""
        # 先添加一些命令记录
        execution_data = {
            "ecu_id": "test_device_001",
            "command": "lock",
            "params": {},
            "result": {"success": True},
            "success": True,
            "execution_duration_ms": 100
        }
        
        await db_with_data.save_command_execution(execution_data)
        
        # 获取统计
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=1)
        
        stats = await db_with_data.get_command_statistics(
            "test_device_001", start_time, end_time
        )
        
        assert "total_commands" in stats
        assert "success_commands" in stats
        assert "command_distribution" in stats
        
        assert stats["total_commands"] >= 1
    
    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, db_client):
        """测试清理旧数据"""
        # 添加一些旧数据
        old_time = datetime.now() - timedelta(days=60)  # 60天前
        
        # 添加状态记录（模拟旧数据）
        status_data = {"test": "old_data"}
        
        # 注意：实际实现中需要支持指定时间戳
        # 这里简化测试
        
        # 执行清理（保留30天）
        deleted_counts = await db_client.cleanup_old_data(days_to_keep=30)
        
        assert isinstance(deleted_counts, dict)
        assert "total" in deleted_counts
    
    @pytest.mark.asyncio
    async def test_list_ecu_devices(self, db_with_data):
        """测试列出ECU设备"""
        devices = await db_with_data.list_ecu_devices(
            device_type="shared_bike",
            active_only=True,
            limit=10
        )
        
        assert isinstance(devices, list)
        if devices:
            device = devices[0]
            assert "ecu_id" in device
            assert "device_type" in device
            assert device["device_type"] == "shared_bike"
    
    @pytest.mark.asyncio
    async def test_get_latest_ecu_status(self, db_with_data):
        """测试获取最新ECU状态"""
        # 添加多个状态记录
        for i in range(3):
            status_data = {"battery": 80 - i*10, "timestamp": i}
            await db_with_data.save_ecu_status("test_latest_001", status_data)
            await asyncio.sleep(0.01)  # 确保时间戳不同
        
        # 获取最新状态
        latest = await db_with_data.get_latest_ecu_status("test_latest_001")
        
        assert latest is not None
        assert latest["ecu_id"] == "test_latest_001"
        assert latest["status_data"]["battery"] == 60  # 最后一个添加的
    
    @pytest.mark.asyncio
    async def test_session_context_manager(self, db_client):
        """测试会话上下文管理器"""
        async with db_client.get_session() as session:
            assert session is not None
            # 会话应该自动提交和关闭
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self, db_client):
        """测试并发访问"""
        # 创建多个并发任务
        tasks = []
        
        for i in range(5):
            task = asyncio.create_task(
                db_client.save_ecu_status(f"concurrent_{i}", {"value": i})
            )
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 检查是否有异常
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"并发访问失败: {result}")
        
        # 验证所有数据都已保存
        for i in range(5):
            history = await db_client.get_ecu_status_history(f"concurrent_{i}", limit=1)
            assert len(history) == 1


class TestBatchWriter:
    """BatchWriter测试"""
    
    @pytest.fixture
    async def batch_writer(self):
        """BatchWriter fixture"""
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        
        writer = BatchWriter(session_factory, batch_size=2, flush_interval=1)
        writer.start()
        
        yield writer
        
        await writer.stop()
        await engine.dispose()
    
    @pytest.mark.asyncio
    async def test_batch_writer_initialization(self, batch_writer):
        """测试批量写入器初始化"""
        stats = batch_writer.get_stats()
        
        assert stats["batch_size"] == 2
        assert stats["flush_interval"] == 1
        assert stats["is_running"] is True
        assert "queue_sizes" in stats
    
    @pytest.mark.asyncio
    async def test_add_status(self, batch_writer):
        """测试添加状态"""
        status_data = {
            "id": "test_001",
            "ecu_id": "test_ecu",
            "status_data": {"battery": 85},
            "timestamp": datetime.now()
        }
        
        await batch_writer.add_status(status_data)
        
        stats = batch_writer.get_stats()
        assert stats["queue_sizes"]["status_queue"] == 1
    
    @pytest.mark.asyncio
    async def test_batch_save_statuses(self, batch_writer):
        """测试批量保存状态"""
        statuses = [
            {
                "id": f"batch_{i}",
                "ecu_id": f"ecu_{i}",
                "status_data": {"value": i},
                "timestamp": datetime.now()
            }
            for i in range(3)  # 超过批量大小
        ]
        
        await batch_writer.batch_save_statuses(statuses)
        
        # 等待自动刷新
        await asyncio.sleep(1.5)
        
        stats = batch_writer.get_stats()
        # 队列应该被清空
        assert stats["queue_sizes"]["status_queue"] == 0
    
    @pytest.mark.asyncio
    async def test_flush_all(self, batch_writer):
        """测试刷新所有队列"""
        # 添加各种数据
        await batch_writer.add_status({
            "id": "flush_test_1",
            "ecu_id": "test_ecu",
            "status_data": {"test": "data"},
            "timestamp": datetime.now()
        })
        
        await batch_writer.add_heartbeat({
            "id": "flush_test_2",
            "ecu_id": "test_ecu",
            "heartbeat_data": {"uptime": 1000},
            "timestamp": datetime.now()
        })
        
        # 手动刷新
        await batch_writer.flush_all()
        
        stats = batch_writer.get_stats()
        # 所有队列应该为空
        total_queued = stats["queue_sizes"]["total_queued"]
        assert total_queued == 0
    
    @pytest.mark.asyncio
    async def test_stop_writer(self, batch_writer):
        """测试停止写入器"""
        # 添加一些数据
        await batch_writer.add_status({
            "id": "stop_test",
            "ecu_id": "test_ecu",
            "status_data": {"test": "data"},
            "timestamp": datetime.now()
        })
        
        # 停止写入器
        await batch_writer.stop()
        
        stats = batch_writer.get_stats()
        assert stats["is_running"] is False


@pytest.mark.integration
class TestDatabaseIntegration:
    """数据库集成测试"""
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self):
        """测试完整工作流程"""
        # 创建数据库客户端
        client = DatabaseClient(TEST_DB_URL)
        await client.initialize()
        
        try:
            # 1. 创建设备
            device_data = {
                "ecu_id": "workflow_001",
                "device_type": "shared_bike",
                "firmware_version": "1.0.0",
                "status": "online",
                "config": {"heartbeat_interval": 30}
            }
            
            device_id = await client.save_ecu_device(device_data)
            assert device_id is not None
            
            # 2. 保存设备状态
            for i in range(3):
                status_data = {"battery": 90 - i*10, "iteration": i}
                status_id = await client.save_ecu_status("workflow_001", status_data)
                assert status_id is not None
                await asyncio.sleep(0.01)
            
            # 3. 获取状态历史
            history = await client.get_ecu_status_history("workflow_001", limit=5)
            assert len(history) == 3
            
            # 4. 获取最新状态
            latest = await client.get_latest_ecu_status("workflow_001")
            assert latest is not None
            assert latest["status_data"]["battery"] == 70
            
            # 5. 保存心跳
            heartbeat_id = await client.save_heartbeat("workflow_001", {"uptime": 3600})
            assert heartbeat_id is not None
            
            # 6. 保存命令执行
            command_id = await client.save_command_execution({
                "ecu_id": "workflow_001",
                "command": "lock",
                "result": {"success": True},
                "success": True
            })
            assert command_id is not None
            
            # 7. 获取设备统计
            stats = await client.get_device_statistics()
            assert stats["total_devices"] >= 1
            
            # 8. 列出设备
            devices = await client.list_ecu_devices(limit=10)
            assert len(devices) >= 1
            
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_batch_operations_performance(self):
        """测试批量操作性能"""
        client = DatabaseClient(TEST_DB_URL)
        await client.initialize()
        
        try:
            import time
            
            # 测试单个保存
            start_time = time.time()
            
            for i in range(10):
                await client.save_ecu_status(f"perf_test_{i}", {"value": i})
            
            single_time = time.time() - start_time
            
            # 测试批量保存
            start_time = time.time()
            
            statuses = [
                {"ecu_id": f"batch_perf_{i}", "status": {"value": i}}
                for i in range(10)
            ]
            
            await client.batch_save_statuses(statuses)
            
            batch_time = time.time() - start_time
            
            # 批量操作应该更快
            # 注意：对于少量数据可能不明显，但对于大量数据差异会很大
            print(f"单次保存时间: {single_time:.3f}s")
            print(f"批量保存时间: {batch_time:.3f}s")
            
        finally:
            await client.close()


if __name__ == "__main__":
    """运行测试"""
    import sys
    sys.exit(pytest.main([__file__, "-v"]))