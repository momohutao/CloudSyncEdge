"""
ECU模拟器 - 用于测试和开发的ECU设备模拟
"""
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from enum import Enum

from CloudSyncEdge.src.protocol.message_types import MessageTypes, DeviceTypes

from .base_ecu import BaseECU
from ..database.client import DatabaseClient

logger = logging.getLogger(__name__)


class SimulationMode(Enum):
    """模拟模式"""
    STATIC = "static"      # 静态模式：固定数据
    DYNAMIC = "dynamic"    # 动态模式：随机变化数据
    REALISTIC = "realistic" # 现实模式：基于规则的变化
    STRESS = "stress"      # 压力模式：高负载测试


class SimulationEvent(Enum):
    """模拟事件类型"""
    DEVICE_CONNECT = "device_connect"
    DEVICE_DISCONNECT = "device_disconnect"
    STATUS_UPDATE = "status_update"
    COMMAND_RECEIVED = "command_received"
    COMMAND_EXECUTED = "command_executed"
    ERROR_OCCURRED = "error_occurred"
    HEARTBEAT = "heartbeat"
    NETWORK_LATENCY = "network_latency"
    DEVICE_RESTART = "device_restart"


class SimulationScenario:
    """模拟场景定义"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.device_specs = []
        self.events = []
        self.duration_seconds = 300  # 默认5分钟
        self.start_time = None
        self.end_time = None
    
    def add_device(self, ecu_id: str, device_type: str, count: int = 1, 
                  config: Dict = None, behavior: str = "normal"):
        """添加设备规格"""
        for i in range(count):
            device_id = ecu_id if count == 1 else f"{ecu_id}_{i+1:03d}"
            self.device_specs.append({
                "ecu_id": device_id,
                "device_type": device_type,
                "config": config or {},
                "behavior": behavior
            })
        return self
    
    def add_event(self, event_type: SimulationEvent, time_offset: int, 
                 device_id: str = None, data: Dict = None):
        """添加事件"""
        self.events.append({
            "type": event_type,
            "time_offset": time_offset,
            "device_id": device_id,
            "data": data or {}
        })
        return self
    
    def set_duration(self, seconds: int):
        """设置持续时间"""
        self.duration_seconds = seconds
        return self


class ECUSimulator:
    """ECU模拟器 - 模拟多个ECU设备的行为"""
    
    def __init__(self, db_client: Optional[DatabaseClient] = None):
        self.db_client = db_client
        self.factory = get_ecu_factory()
        
        # 模拟设备
        self.simulated_devices: Dict[str, BaseECU] = {}
        self.device_behaviors: Dict[str, Dict] = {}
        
        # 模拟状态
        self.simulation_mode = SimulationMode.DYNAMIC
        self.is_running = False
        self.start_time = None
        
        # 事件处理器
        self.event_handlers: Dict[SimulationEvent, List[Callable]] = {}
        
        # 统计信息
        self.stats = {
            "devices_created": 0,
            "devices_destroyed": 0,
            "commands_sent": 0,
            "events_triggered": 0,
            "errors_occurred": 0,
            "simulation_duration": 0
        }
        
        # 模拟任务
        self._simulation_tasks = []
        self._event_queue = asyncio.Queue(maxsize=1000)
        
        logger.info("ECU模拟器初始化完成")
    
    def register_event_handler(self, event_type: SimulationEvent, handler: Callable):
        """注册事件处理器"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def unregister_event_handler(self, event_type: SimulationEvent, handler: Callable):
        """注销事件处理器"""
        if event_type in self.event_handlers:
            if handler in self.event_handlers[event_type]:
                self.event_handlers[event_type].remove(handler)
    
    async def _trigger_event(self, event_type: SimulationEvent, data: Dict):
        """触发事件"""
        self.stats["events_triggered"] += 1
        
        # 调用事件处理器
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        handler(data)
                except Exception as e:
                    logger.error(f"事件处理器执行失败: {e}")
        
        # 记录事件
        event_data = {
            "type": event_type.value,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        if self.db_client:
            try:
                await self.db_client.save_event("simulator", f"simulation_{event_type.value}", event_data)
            except Exception as e:
                logger.error(f"保存模拟事件失败: {e}")
    
    async def create_simulated_device(self, ecu_id: str, device_type: str, 
                                     behavior: str = "normal", config: Dict = None) -> Optional[BaseECU]:
        """创建模拟设备"""
        try:
            # 创建配置
            device_config = {
                "ecu_id": ecu_id,
                "device_type": device_type,
                "heartbeat_interval": 30,
                "command_timeout": 10,
                "enable_logging": True
            }
            
            if config:
                device_config.update(config)
            
            # 根据行为模式调整配置
            if behavior == "unstable":
                device_config["heartbeat_interval"] = random.randint(60, 120)
                device_config["command_timeout"] = random.randint(20, 60)
            elif behavior == "responsive":
                device_config["heartbeat_interval"] = 15
                device_config["command_timeout"] = 5
            elif behavior == "slow":
                device_config["heartbeat_interval"] = 60
                device_config["command_timeout"] = 30
            
            # 创建设备
            ecu = self.factory.create_ecu_from_dict({
                "ecu_id": ecu_id,
                "device_type": device_type,
                "config": device_config
            }, self.db_client)
            
            if not ecu:
                logger.error(f"创建设备失败: {ecu_id}")
                return None
            
            # 启动设备
            await ecu.start()
            
            # 存储设备和行为
            self.simulated_devices[ecu_id] = ecu
            self.device_behaviors[ecu_id] = {
                "type": device_type,
                "behavior": behavior,
                "config": device_config,
                "created_at": datetime.now()
            }
            
            self.stats["devices_created"] += 1
            
            # 触发设备连接事件
            await self._trigger_event(SimulationEvent.DEVICE_CONNECT, {
                "ecu_id": ecu_id,
                "device_type": device_type,
                "behavior": behavior
            })
            
            logger.info(f"创建模拟设备: {ecu_id} ({device_type}, {behavior})")
            return ecu
            
        except Exception as e:
            logger.error(f"创建模拟设备失败: {ecu_id}: {e}")
            return None
    
    async def destroy_simulated_device(self, ecu_id: str, reason: str = "normal"):
        """销毁模拟设备"""
        try:
            if ecu_id not in self.simulated_devices:
                logger.warning(f"设备不存在: {ecu_id}")
                return False
            
            ecu = self.simulated_devices[ecu_id]
            
            # 停止设备
            await ecu.stop()
            
            # 从字典中移除
            del self.simulated_devices[ecu_id]
            del self.device_behaviors[ecu_id]
            
            self.stats["devices_destroyed"] += 1
            
            # 触发设备断开事件
            await self._trigger_event(SimulationEvent.DEVICE_DISCONNECT, {
                "ecu_id": ecu_id,
                "reason": reason,
                "device_type": ecu.device_type
            })
            
            logger.info(f"销毁模拟设备: {ecu_id} ({reason})")
            return True
            
        except Exception as e:
            logger.error(f"销毁模拟设备失败: {ecu_id}: {e}")
            return False
    
    async def simulate_device_behavior(self, ecu_id: str, duration: int = 300):
        """模拟设备行为"""
        try:
            if ecu_id not in self.simulated_devices:
                logger.error(f"设备不存在: {ecu_id}")
                return
            
            ecu = self.simulated_devices[ecu_id]
            behavior = self.device_behaviors[ecu_id]["behavior"]
            
            logger.info(f"开始模拟设备行为: {ecu_id} ({behavior}, {duration}s)")
            
            start_time = datetime.now()
            end_time = start_time + timedelta(seconds=duration)
            
            while datetime.now() < end_time and ecu_id in self.simulated_devices:
                try:
                    # 根据行为模式执行不同操作
                    if behavior == "normal":
                        await self._simulate_normal_behavior(ecu)
                    elif behavior == "unstable":
                        await self._simulate_unstable_behavior(ecu)
                    elif behavior == "responsive":
                        await self._simulate_responsive_behavior(ecu)
                    elif behavior == "slow":
                        await self._simulate_slow_behavior(ecu)
                    elif behavior == "stress":
                        await self._simulate_stress_behavior(ecu)
                    else:
                        await self._simulate_normal_behavior(ecu)
                    
                    # 随机间隔
                    if behavior == "unstable":
                        await asyncio.sleep(random.uniform(5, 30))
                    elif behavior == "responsive":
                        await asyncio.sleep(random.uniform(2, 10))
                    elif behavior == "slow":
                        await asyncio.sleep(random.uniform(20, 60))
                    else:
                        await asyncio.sleep(random.uniform(10, 20))
                        
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"设备行为模拟异常: {ecu_id}: {e}")
                    await asyncio.sleep(5)  # 错误后等待
            
            logger.info(f"设备行为模拟完成: {ecu_id}")
            
        except Exception as e:
            logger.error(f"模拟设备行为失败: {ecu_id}: {e}")
    
    async def _simulate_normal_behavior(self, ecu: BaseECU):
        """模拟正常行为"""
        # 随机发送状态更新
        if random.random() < 0.3:  # 30%概率
            await ecu.execute_command(MessageTypes.STATUS_UPDATE, {
                "status": {"random_value": random.randint(1, 100)}
            })
            self.stats["commands_sent"] += 1
        
        # 随机切换锁定状态（仅适用于支持锁定的设备）
        if ecu.device_type in [DeviceTypes.SHARED_BIKE, DeviceTypes.ACCESS_CONTROL]:
            if random.random() < 0.1:  # 10%概率
                if random.random() < 0.5:
                    await ecu.execute_command(MessageTypes.LOCK, {"reason": "auto_lock"})
                else:
                    await ecu.execute_command(MessageTypes.UNLOCK, {
                        "user_id": "sim_user",
                        "auth_code": f"sim_{random.randint(1000, 9999)}"
                    })
                self.stats["commands_sent"] += 1
    
    async def _simulate_unstable_behavior(self, ecu: BaseECU):
        """模拟不稳定行为"""
        # 随机断开连接
        if random.random() < 0.05:  # 5%概率
            logger.warning(f"模拟设备断开: {ecu.ecu_id}")
            await ecu.stop()
            await asyncio.sleep(random.uniform(10, 30))
            await ecu.start()
            
            await self._trigger_event(SimulationEvent.DEVICE_RESTART, {
                "ecu_id": ecu.ecu_id,
                "reason": "unstable_behavior"
            })
        
        # 随机命令失败
        if random.random() < 0.2:  # 20%概率
            await ecu.execute_command(MessageTypes.STATUS_UPDATE, {
                "status": {"error_simulation": True}
            })
            self.stats["commands_sent"] += 1
            self.stats["errors_occurred"] += 1
    
    async def _simulate_responsive_behavior(self, ecu: BaseECU):
        """模拟响应式行为"""
        # 频繁发送状态更新
        if random.random() < 0.7:  # 70%概率
            await ecu.execute_command(MessageTypes.STATUS_UPDATE, {
                "status": {"responsive_mode": True}
            })
            self.stats["commands_sent"] += 1
    
    async def _simulate_slow_behavior(self, ecu: BaseECU):
        """模拟缓慢行为"""
        # 模拟网络延迟
        await asyncio.sleep(random.uniform(1, 3))
        
        # 偶尔发送状态更新
        if random.random() < 0.1:  # 10%概率
            await ecu.execute_command(MessageTypes.STATUS_UPDATE, {
                "status": {"slow_mode": True}
            })
            self.stats["commands_sent"] += 1
    
    async def _simulate_stress_behavior(self, ecu: BaseECU):
        """模拟压力行为"""
        # 快速连续发送命令
        for _ in range(random.randint(3, 10)):
            try:
                await ecu.execute_command(MessageTypes.STATUS_UPDATE, {
                    "status": {"stress_test": random.randint(1, 1000)}
                })
                self.stats["commands_sent"] += 1
                await asyncio.sleep(0.1)  # 快速发送
            except Exception as e:
                logger.debug(f"压力测试命令失败: {e}")
    
    async def run_scenario(self, scenario: SimulationScenario):
        """运行模拟场景"""
        try:
            logger.info(f"开始运行模拟场景: {scenario.name}")
            print(f"📋 场景: {scenario.name}")
            print(f"📝 描述: {scenario.description}")
            print(f"⏱️  持续时间: {scenario.duration_seconds}秒")
            print(f"📱 设备数量: {len(scenario.device_specs)}")
            print(f"🎬 事件数量: {len(scenario.events)}")
            print("=" * 50)
            
            scenario.start_time = datetime.now()
            
            # 创建所有设备
            device_tasks = []
            for spec in scenario.device_specs:
                task = self.create_simulated_device(
                    ecu_id=spec["ecu_id"],
                    device_type=spec["device_type"],
                    behavior=spec.get("behavior", "normal"),
                    config=spec.get("config", {})
                )
                device_tasks.append(task)
            
            devices = await asyncio.gather(*device_tasks)
            created_count = len([d for d in devices if d is not None])
            print(f"✅ 创建设备: {created_count}/{len(device_tasks)}")
            
            # 启动设备行为模拟
            behavior_tasks = []
            for ecu in devices:
                if ecu:
                    task = asyncio.create_task(
                        self.simulate_device_behavior(ecu.ecu_id, scenario.duration_seconds)
                    )
                    behavior_tasks.append(task)
            
            # 调度事件
            event_tasks = []
            for event in scenario.events:
                time_offset = event["time_offset"]
                if time_offset <= scenario.duration_seconds:
                    task = asyncio.create_task(
                        self._schedule_event(event, scenario.start_time)
                    )
                    event_tasks.append(task)
            
            # 等待场景持续时间
            print(f"⏳ 模拟进行中... (剩余{scenario.duration_seconds}秒)")
            await asyncio.sleep(scenario.duration_seconds)
            
            # 停止所有行为模拟
            for task in behavior_tasks:
                task.cancel()
            
            if behavior_tasks:
                await asyncio.gather(*behavior_tasks, return_exceptions=True)
            
            # 销毁所有设备
            destroy_tasks = []
            for spec in scenario.device_specs:
                task = self.destroy_simulated_device(spec["ecu_id"], "scenario_end")
                destroy_tasks.append(task)
            
            destroy_results = await asyncio.gather(*destroy_tasks, return_exceptions=True)
            destroyed_count = len([r for r in destroy_results if r is True])
            print(f"✅ 销毁设备: {destroyed_count}/{len(destroy_tasks)}")
            
            scenario.end_time = datetime.now()
            actual_duration = (scenario.end_time - scenario.start_time).total_seconds()
            
            # 更新统计
            self.stats["simulation_duration"] += actual_duration
            
            print("=" * 50)
            print(f"🎉 场景完成: {scenario.name}")
            print(f"⏱️  实际耗时: {actual_duration:.1f}秒")
            print(f"📊 发送命令: {self.stats['commands_sent']}")
            print(f"⚠️  发生错误: {self.stats['errors_occurred']}")
            print(f"🎬 触发事件: {self.stats['events_triggered']}")
            
            return True
            
        except Exception as e:
            logger.error(f"运行模拟场景失败: {scenario.name}: {e}")
            print(f"❌ 场景失败: {e}")
            return False
    
    async def _schedule_event(self, event: Dict, start_time: datetime):
        """调度事件"""
        try:
            time_offset = event["time_offset"]
            await asyncio.sleep(time_offset)
            
            event_type = SimulationEvent(event["type"])
            device_id = event.get("device_id")
            data = event.get("data", {})
            
            event_data = {
                "event_type": event_type.value,
                "scheduled_time": (start_time + timedelta(seconds=time_offset)).isoformat(),
                "actual_time": datetime.now().isoformat(),
                "data": data
            }
            
            if device_id:
                event_data["ecu_id"] = device_id
                
                if device_id in self.simulated_devices:
                    ecu = self.simulated_devices[device_id]
                    
                    # 根据事件类型执行相应操作
                    if event_type == SimulationEvent.COMMAND_RECEIVED:
                        # 发送随机命令
                        commands = [
                            MessageTypes.GET_STATUS,
                            MessageTypes.LOCK,
                            MessageTypes.UNLOCK,
                            MessageTypes.STATUS_UPDATE
                        ]
                        
                        command = random.choice(commands)
                        params = data.get("params", {"reason": "scheduled_event"})
                        
                        result = await ecu.execute_command(command, params)
                        self.stats["commands_sent"] += 1
                        
                        event_data["command_result"] = result
                    
                    elif event_type == SimulationEvent.ERROR_OCCURRED:
                        # 模拟错误
                        ecu._error_count += 1
                        ecu._errors.append({
                            "timestamp": datetime.now(),
                            "error": data.get("error", "simulated_error"),
                            "severity": data.get("severity", "warning")
                        })
            
            await self._trigger_event(event_type, event_data)
            
        except Exception as e:
            logger.error(f"调度事件失败: {e}")
    
    async def create_preset_scenario(self, preset_name: str) -> Optional[SimulationScenario]:
        """创建预设场景"""
        if preset_name == "basic_test":
            scenario = SimulationScenario(
                name="基本测试",
                description="基础设备连接和命令测试"
            )
            scenario.add_device("test_bike_001", DeviceTypes.SHARED_BIKE, 2)
            scenario.add_device("test_door_001", DeviceTypes.ACCESS_CONTROL, 2)
            scenario.set_duration(180)  # 3分钟
            
            # 添加事件
            scenario.add_event(SimulationEvent.COMMAND_RECEIVED, 30, "test_bike_001")
            scenario.add_event(SimulationEvent.COMMAND_RECEIVED, 60, "test_door_001")
            scenario.add_event(SimulationEvent.STATUS_UPDATE, 120)
            
            return scenario
        
        elif preset_name == "stress_test":
            scenario = SimulationScenario(
                name="压力测试",
                description="高负载压力测试"
            )
            scenario.add_device("stress_bike_", DeviceTypes.SHARED_BIKE, 10, 
                              behavior="stress")
            scenario.add_device("stress_door_", DeviceTypes.ACCESS_CONTROL, 5,
                              behavior="stress")
            scenario.set_duration(300)  # 5分钟
            
            # 添加大量事件
            for i in range(20):
                time_offset = random.randint(10, 290)
                device_id = random.choice(["stress_bike_001", "stress_door_001"])
                scenario.add_event(SimulationEvent.COMMAND_RECEIVED, time_offset, device_id)
            
            return scenario
        
        elif preset_name == "unstable_network":
            scenario = SimulationScenario(
                name="不稳定网络测试",
                description="模拟不稳定网络环境"
            )
            scenario.add_device("unstable_bike_", DeviceTypes.SHARED_BIKE, 3,
                              behavior="unstable")
            scenario.add_device("unstable_door_", DeviceTypes.ACCESS_CONTROL, 2,
                              behavior="unstable")
            scenario.set_duration(240)  # 4分钟
            
            # 添加网络相关事件
            scenario.add_event(SimulationEvent.DEVICE_DISCONNECT, 60, "unstable_bike_001",
                             {"reason": "network_timeout"})
            scenario.add_event(SimulationEvent.DEVICE_CONNECT, 120, "unstable_bike_001")
            scenario.add_event(SimulationEvent.NETWORK_LATENCY, 180,
                             {"latency_ms": random.randint(500, 2000)})
            
            return scenario
        
        elif preset_name == "mixed_environment":
            scenario = SimulationScenario(
                name="混合环境测试",
                description="多种设备类型和行为混合测试"
            )
            scenario.add_device("mixed_bike_normal", DeviceTypes.SHARED_BIKE, 2,
                              behavior="normal")
            scenario.add_device("mixed_bike_responsive", DeviceTypes.SHARED_BIKE, 2,
                              behavior="responsive")
            scenario.add_device("mixed_door_normal", DeviceTypes.ACCESS_CONTROL, 2,
                              behavior="normal")
            scenario.add_device("mixed_door_slow", DeviceTypes.ACCESS_CONTROL, 2,
                              behavior="slow")
            scenario.set_duration(360)  # 6分钟
            
            # 添加混合事件
            for i in range(15):
                time_offset = random.randint(30, 350)
                device_type = random.choice(["bike", "door"])
                behavior = random.choice(["normal", "responsive", "slow"])
                device_id = f"mixed_{device_type}_{behavior}_001"
                
                scenario.add_event(SimulationEvent.COMMAND_RECEIVED, time_offset, device_id,
                                 {"test_case": f"mixed_{i}"})
            
            return scenario
        
        else:
            logger.error(f"未知的预设场景: {preset_name}")
            return None
    
    async def start_simulation(self, scenario_name: str = None):
        """开始模拟"""
        if self.is_running:
            logger.warning("模拟器已在运行中")
            return False
        
        try:
            self.is_running = True
            self.start_time = datetime.now()
            
            if scenario_name:
                # 运行预设场景
                scenario = await self.create_preset_scenario(scenario_name)
                if scenario:
                    return await self.run_scenario(scenario)
            else:
                # 运行自定义模拟
                await self._run_continuous_simulation()
            
            return True
            
        except Exception as e:
            logger.error(f"开始模拟失败: {e}")
            self.is_running = False
            return False
    
    async def _run_continuous_simulation(self):
        """运行持续模拟"""
        print("🔄 开始持续模拟...")
        
        try:
            # 创建一些初始设备
            initial_devices = [
                {"ecu_id": "sim_bike_001", "device_type": DeviceTypes.SHARED_BIKE, "behavior": "normal"},
                {"ecu_id": "sim_door_001", "device_type": DeviceTypes.ACCESS_CONTROL, "behavior": "normal"},
                {"ecu_id": "sim_bike_002", "device_type": DeviceTypes.SHARED_BIKE, "behavior": "responsive"},
            ]
            
            for device_spec in initial_devices:
                await self.create_simulated_device(**device_spec)
            
            # 持续运行
            while self.is_running:
                try:
                    # 随机添加/移除设备
                    if random.random() < 0.1:  # 10%概率
                        if random.random() < 0.5 and len(self.simulated_devices) < 20:
                            # 添加新设备
                            device_type = random.choice([DeviceTypes.SHARED_BIKE, DeviceTypes.ACCESS_CONTROL])
                            behavior = random.choice(["normal", "responsive", "slow"])
                            device_id = f"auto_{device_type}_{random.randint(100, 999)}"
                            
                            await self.create_simulated_device(
                                ecu_id=device_id,
                                device_type=device_type,
                                behavior=behavior
                            )
                        elif len(self.simulated_devices) > 5:
                            # 随机移除一个设备
                            device_id = random.choice(list(self.simulated_devices.keys()))
                            await self.destroy_simulated_device(device_id, "auto_cleanup")
                    
                    # 随机发送全局事件
                    if random.random() < 0.05:  # 5%概率
                        event_type = random.choice([
                            SimulationEvent.STATUS_UPDATE,
                            SimulationEvent.NETWORK_LATENCY
                        ])
                        
                        await self._trigger_event(event_type, {
                            "message": f"随机全局事件: {event_type.value}",
                            "random_value": random.randint(1, 100)
                        })
                    
                    await asyncio.sleep(10)  # 10秒间隔
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"持续模拟循环异常: {e}")
                    await asyncio.sleep(5)
            
            print("⏹️  持续模拟停止")
            
        except Exception as e:
            logger.error(f"持续模拟失败: {e}")
    
    async def stop_simulation(self):
        """停止模拟"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 停止所有设备
        destroy_tasks = []
        for ecu_id in list(self.simulated_devices.keys()):
            task = self.destroy_simulated_device(ecu_id, "simulation_stop")
            destroy_tasks.append(task)
        
        if destroy_tasks:
            await asyncio.gather(*destroy_tasks, return_exceptions=True)
        
        # 停止所有任务
        for task in self._simulation_tasks:
            task.cancel()
        
        if self._simulation_tasks:
            await asyncio.gather(*self._simulation_tasks, return_exceptions=True)
        
        # 更新统计
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
            self.stats["simulation_duration"] = duration
        
        logger.info(f"模拟停止，持续时间: {self.stats['simulation_duration']:.1f}秒")
        print(f"⏹️  模拟已停止，持续时间: {self.stats['simulation_duration']:.1f}秒")
    
    def get_statistics(self) -> Dict:
        """获取模拟器统计信息"""
        current_time = datetime.now()
        duration = 0
        
        if self.start_time:
            if self.is_running:
                duration = (current_time - self.start_time).total_seconds()
            else:
                duration = self.stats["simulation_duration"]
        
        return {
            "is_running": self.is_running,
            "simulation_mode": self.simulation_mode.value,
            "current_devices": len(self.simulated_devices),
            "device_behaviors": {
                behavior: len([d for d in self.device_behaviors.values() if d["behavior"] == behavior])
                for behavior in ["normal", "unstable", "responsive", "slow", "stress"]
            },
            "stats": self.stats.copy(),
            "duration_seconds": duration,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "current_time": current_time.isoformat()
        }
    
    async def generate_report(self) -> Dict:
        """生成模拟报告"""
        stats = self.get_statistics()
        
        # 计算成功率
        total_commands = stats["stats"]["commands_sent"]
        errors = stats["stats"]["errors_occurred"]
        success_rate = 100.0 if total_commands == 0 else ((total_commands - errors) / total_commands * 100)
        
        # 设备状态统计
        device_statuses = {}
        for ecu_id, ecu in self.simulated_devices.items():
            status = ecu.status.value
            if status not in device_statuses:
                device_statuses[status] = 0
            device_statuses[status] += 1
        
        report = {
            "report_id": f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_devices": stats["current_devices"],
                "simulation_duration": f"{stats['duration_seconds']:.1f}秒",
                "commands_sent": total_commands,
                "errors_occurred": errors,
                "success_rate": f"{success_rate:.1f}%",
                "events_triggered": stats["stats"]["events_triggered"]
            },
            "device_analysis": {
                "by_type": {},
                "by_behavior": stats["device_behaviors"],
                "by_status": device_statuses
            },
            "performance": {
                "commands_per_second": total_commands / max(stats['duration_seconds'], 1),
                "devices_per_minute": stats["stats"]["devices_created"] / max(stats['duration_seconds'] / 60, 1),
                "error_rate_percent": (errors / max(total_commands, 1)) * 100
            },
            "recommendations": []
        }
        
        # 分析设备类型分布
        for ecu_id, behavior in self.device_behaviors.items():
            device_type = behavior["type"]
            if device_type not in report["device_analysis"]["by_type"]:
                report["device_analysis"]["by_type"][device_type] = 0
            report["device_analysis"]["by_type"][device_type] += 1
        
        # 添加建议
        if success_rate < 90:
            report["recommendations"].append("成功率较低，建议检查网络连接和设备配置")
        
        if errors > total_commands * 0.2:
            report["recommendations"].append("错误率较高，建议优化设备稳定性")
        
        if stats["current_devices"] > 50:
            report["recommendations"].append("设备数量较多，建议考虑负载均衡")
        
        return report


# =============== 使用示例 ===============

async def demo_ecu_simulator():
    """演示ECU模拟器使用"""
    print("🚀 演示ECU模拟器使用...")
    
    try:
        # 创建模拟器
        simulator = ECUSimulator()
        
        # 注册事件处理器
        async def handle_device_connect(data):
            print(f"📱 设备连接: {data.get('ecu_id')}")
        
        async def handle_command_received(data):
            print(f"📨 命令接收: {data.get('ecu_id', 'global')}")
        
        simulator.register_event_handler(SimulationEvent.DEVICE_CONNECT, handle_device_connect)
        simulator.register_event_handler(SimulationEvent.COMMAND_RECEIVED, handle_command_received)
        
        # 运行基本测试场景
        print("\n1️⃣ 运行基本测试场景...")
        scenario = await simulator.create_preset_scenario("basic_test")
        if scenario:
            await simulator.run_scenario(scenario)
        
        # 运行压力测试场景
        print("\n2️⃣ 运行压力测试场景...")
        scenario = await simulator.create_preset_scenario("stress_test")
        if scenario:
            await simulator.run_scenario(scenario)
        
        # 获取统计信息
        print("\n3️⃣ 获取模拟器统计...")
        stats = simulator.get_statistics()
        print(f"✅ 总命令发送: {stats['stats']['commands_sent']}")
        print(f"⚠️  总错误发生: {stats['stats']['errors_occurred']}")
        print(f"🎬 总事件触发: {stats['stats']['events_triggered']}")
        
        # 生成报告
        print("\n4️⃣ 生成模拟报告...")
        report = await simulator.generate_report()
        print(f"📊 报告ID: {report['report_id']}")
        print(f"📈 成功率: {report['summary']['success_rate']}")
        print(f"⏱️  持续时间: {report['summary']['simulation_duration']}")
        
        print("\n🎉 ECU模拟器演示完成")
        
    except Exception as e:
        print(f"❌ 演示失败: {e}")


if __name__ == "__main__":
    import asyncio
    
    # 初始化工厂
    get_ecu_factory()
    
    # 运行演示
    asyncio.run(demo_ecu_simulator())