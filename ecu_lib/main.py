"""
ECU库主入口文件
"""
import asyncio
import logging
import argparse
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from ecu_lib.core.ecu_factory import ECUFactory, get_ecu_factory
from ecu_lib.core.ecu_simulator import ECUSimulator
from ecu_lib.database.client import DatabaseClient
from ecu_lib.interface.ecu_interface import create_ecu_interface
from ecu_lib.devices.device_registry import get_device_registry
from ecu_lib.mock.mock_manager import create_mock_device_manager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ecu_library.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class ECULibrary:
    """ECU库主类"""
    
    def __init__(self, db_url: str = None):
        """
        初始化ECU库
        
        Args:
            db_url: 数据库URL，如果为None则使用内存数据库
        """
        self.db_url = db_url or "sqlite+aiosqlite:///./data/ecu.db"
        self.db_client: Optional[DatabaseClient] = None
        self.ecu_factory: Optional[ECUFactory] = None
        self.device_registry = None
        self.ecu_interface = None
        self.mock_manager = None
        self.simulator = None
        
        # 确保数据目录存在
        data_dir = Path("./data")
        data_dir.mkdir(exist_ok=True)
        
        logger.info(f"ECU库初始化，数据库: {self.db_url}")
    
    async def initialize(self):
        """初始化库组件"""
        try:
            # 初始化数据库
            self.db_client = DatabaseClient(self.db_url)
            await self.db_client.initialize()
            logger.info("数据库初始化完成")
            
            # 初始化ECU工厂
            self.ecu_factory = get_ecu_factory()
            logger.info("ECU工厂初始化完成")
            
            # 初始化设备注册表
            self.device_registry = get_device_registry()
            logger.info("设备注册表初始化完成")
            
            # 创建ECU接口
            self.ecu_interface = create_ecu_interface(
                self.device_registry, 
                self.db_client
            )
            logger.info("ECU接口创建完成")
            
            # 创建Mock管理器
            self.mock_manager = create_mock_device_manager()
            logger.info("Mock管理器创建完成")
            
            # 创建模拟器
            self.simulator = ECUSimulator(self.db_client)
            logger.info("ECU模拟器创建完成")
            
            logger.info("🎉 ECU库初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"ECU库初始化失败: {e}")
            return False
    
    async def create_sample_devices(self):
        """创建示例设备"""
        try:
            logger.info("创建示例设备...")
            
            # 共享单车设备
            bike_config = {
                "ecu_id": "sample_bike_001",
                "device_type": "shared_bike",
                "firmware_version": "2.0.0",
                "config": {
                    "heartbeat_interval": 30,
                    "command_timeout": 10,
                    "enable_logging": True
                }
            }
            
            bike_result = await self.ecu_interface.register_ecu(bike_config)
            if bike_result["success"]:
                logger.info(f"✅ 创建共享单车: {bike_config['ecu_id']}")
            else:
                logger.error(f"❌ 创建共享单车失败: {bike_result}")
            
            # 门禁设备
            door_config = {
                "ecu_id": "sample_door_001",
                "device_type": "access_control",
                "firmware_version": "1.5.0",
                "config": {
                    "heartbeat_interval": 20,
                    "command_timeout": 8,
                    "security_level": "medium"
                }
            }
            
            door_result = await self.ecu_interface.register_ecu(door_config)
            if door_result["success"]:
                logger.info(f"✅ 创建门禁设备: {door_config['ecu_id']}")
            else:
                logger.error(f"❌ 创建门禁设备失败: {door_result}")
            
            # 启动设备
            await self.ecu_interface.start_ecu("sample_bike_001")
            await self.ecu_interface.start_ecu("sample_door_001")
            
            logger.info("示例设备创建完成")
            return True
            
        except Exception as e:
            logger.error(f"创建示例设备失败: {e}")
            return False
    
    async def run_demo_commands(self):
        """运行演示命令"""
        try:
            logger.info("运行演示命令...")
            
            # 1. 获取所有设备
            devices = await self.ecu_interface.get_all_ecus()
            logger.info(f"📱 设备总数: {len(devices)}")
            
            # 2. 获取设备状态
            for device in devices:
                ecu_id = device["ecu_id"]
                status = await self.ecu_interface.get_ecu_status(ecu_id)
                
                if status["success"]:
                    logger.info(f"📊 设备状态: {ecu_id} -> {status['status']['status']}")
                else:
                    logger.warning(f"⚠️  获取状态失败: {ecu_id}")
            
            # 3. 执行命令
            commands = [
                ("get_status", {"detailed": True}),
                ("lock", {"force": True, "reason": "demo"}),
                ("unlock", {"user_id": "demo_user", "auth_code": "DEMO123"})
            ]
            
            for command, params in commands:
                for device in devices:
                    ecu_id = device["ecu_id"]
                    
                    # 跳过不支持锁定的设备类型
                    if command in ["lock", "unlock"] and device["device_type"] not in ["shared_bike", "access_control"]:
                        continue
                    
                    result = await self.ecu_interface.execute_command(ecu_id, command, params)
                    
                    if result["success"]:
                        logger.info(f"✅ 命令成功: {ecu_id} -> {command}")
                    else:
                        logger.warning(f"⚠️  命令失败: {ecu_id} -> {command}: {result.get('error_message')}")
            
            # 4. 健康检查
            health = await self.ecu_interface.health_check()
            logger.info(f"❤️  健康检查: {health['status']}")
            
            logger.info("演示命令运行完成")
            return True
            
        except Exception as e:
            logger.error(f"运行演示命令失败: {e}")
            return False
    
    async def run_simulation(self, scenario_name: str = "basic_test"):
        """运行模拟"""
        try:
            logger.info(f"开始模拟: {scenario_name}")
            
            if not self.simulator:
                logger.error("模拟器未初始化")
                return False
            
            # 创建预设场景
            from ecu_lib.core.ecu_simulator import SimulationEvent
            
            # 注册事件处理器
            async def handle_device_connect(data):
                logger.info(f"📱 模拟设备连接: {data.get('ecu_id')}")
            
            async def handle_command_received(data):
                logger.info(f"📨 模拟命令接收: {data.get('ecu_id', 'global')}")
            
            self.simulator.register_event_handler(SimulationEvent.DEVICE_CONNECT, handle_device_connect)
            self.simulator.register_event_handler(SimulationEvent.COMMAND_RECEIVED, handle_command_received)
            
            # 运行场景
            success = await self.simulator.start_simulation(scenario_name)
            
            if success:
                logger.info("✅ 模拟完成")
                
                # 生成报告
                report = await self.simulator.generate_report()
                logger.info(f"📊 模拟报告: {report['summary']}")
            else:
                logger.error("❌ 模拟失败")
            
            return success
            
        except Exception as e:
            logger.error(f"运行模拟失败: {e}")
            return False
    
    async def cleanup(self):
        """清理资源"""
        try:
            logger.info("清理资源...")
            
            # 停止模拟器
            if self.simulator:
                await self.simulator.stop_simulation()
            
            # 停止所有设备
            if self.ecu_interface:
                devices = await self.ecu_interface.get_all_ecus()
                for device in devices:
                    await self.ecu_interface.stop_ecu(device["ecu_id"])
                    await self.ecu_interface.unregister_ecu(device["ecu_id"])
            
            # 关闭数据库
            if self.db_client:
                await self.db_client.close()
            
            logger.info("资源清理完成")
            
        except Exception as e:
            logger.error(f"清理资源失败: {e}")
    
    async def get_status(self) -> Dict[str, Any]:
        """获取库状态"""
        try:
            status = {
                "initialized": all([
                    self.db_client is not None,
                    self.ecu_factory is not None,
                    self.ecu_interface is not None
                ]),
                "components": {
                    "database": self.db_client is not None,
                    "ecu_factory": self.ecu_factory is not None,
                    "device_registry": self.device_registry is not None,
                    "ecu_interface": self.ecu_interface is not None,
                    "mock_manager": self.mock_manager is not None,
                    "simulator": self.simulator is not None
                }
            }
            
            if self.ecu_interface:
                try:
                    health = await self.ecu_interface.health_check()
                    status["health"] = health
                except Exception as e:
                    status["health_error"] = str(e)
            
            if self.simulator:
                status["simulator_stats"] = self.simulator.get_statistics()
            
            return status
            
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            return {"error": str(e)}


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="ECU库命令行接口")
    parser.add_argument("--db-url", help="数据库URL", default="sqlite+aiosqlite:///./data/ecu.db")
    parser.add_argument("--demo", action="store_true", help="运行演示")
    parser.add_argument("--simulate", type=str, help="运行模拟场景", choices=["basic_test", "stress_test", "unstable_network", "mixed_environment"])
    parser.add_argument("--test", action="store_true", help="运行测试")
    parser.add_argument("--interactive", action="store_true", help="交互模式")
    
    args = parser.parse_args()
    
    print("🚀 启动ECU库...")
    
    # 创建ECU库实例
    ecu_lib = ECULibrary(args.db_url)
    
    try:
        # 初始化
        if not await ecu_lib.initialize():
            print("❌ ECU库初始化失败")
            return 1
        
        print("✅ ECU库初始化成功")
        
        # 根据参数执行不同操作
        if args.demo:
            print("\n🎬 运行演示...")
            
            # 创建示例设备
            await ecu_lib.create_sample_devices()
            
            # 运行演示命令
            await ecu_lib.run_demo_commands()
            
            print("\n🎉 演示完成")
        
        elif args.simulate:
            print(f"\n🎮 运行模拟场景: {args.simulate}")
            await ecu_lib.run_simulation(args.simulate)
        
        elif args.test:
            print("\n🧪 运行测试...")
            import subprocess
            import sys
            
            # 运行pytest
            test_result = subprocess.run([
                sys.executable, "-m", "pytest",
                "ecu_lib/tests/",
                "-v",
                "--tb=short"
            ])
            
            return test_result.returncode
        
        elif args.interactive:
            print("\n💻 交互模式")
            print("输入 'help' 查看可用命令")
            
            while True:
                try:
                    command = input("\nECU> ").strip().lower()
                    
                    if command in ["exit", "quit"]:
                        print("退出交互模式")
                        break
                    
                    elif command == "help":
                        print("可用命令:")
                        print("  status     - 查看库状态")
                        print("  devices    - 列出所有设备")
                        print("  demo       - 运行演示")
                        print("  simulate   - 运行模拟")
                        print("  test       - 运行测试")
                        print("  exit       - 退出")
                    
                    elif command == "status":
                        status = await ecu_lib.get_status()
                        print(f"库状态: {'已初始化' if status['initialized'] else '未初始化'}")
                        
                        if "health" in status:
                            health = status["health"]
                            print(f"健康状态: {health['status']}")
                            print(f"设备总数: {health['statistics']['total_devices']}")
                            print(f"在线设备: {health['statistics']['online_devices']}")
                    
                    elif command == "devices":
                        if ecu_lib.ecu_interface:
                            devices = await ecu_lib.ecu_interface.get_all_ecus()
                            print(f"设备总数: {len(devices)}")
                            
                            for device in devices:
                                print(f"  - {device['ecu_id']} ({device['device_type']}): {device['status']}")
                        else:
                            print("ECU接口未初始化")
                    
                    elif command == "demo":
                        await ecu_lib.create_sample_devices()
                        await ecu_lib.run_demo_commands()
                    
                    elif command == "simulate":
                        scenario = input("选择场景 (basic_test/stress_test/unstable_network/mixed_environment): ").strip()
                        if scenario in ["basic_test", "stress_test", "unstable_network", "mixed_environment"]:
                            await ecu_lib.run_simulation(scenario)
                        else:
                            print("无效的场景")
                    
                    elif command == "test":
                        import subprocess
                        import sys
                        
                        test_result = subprocess.run([
                            sys.executable, "-m", "pytest",
                            "ecu_lib/tests/test_ecu_core.py",
                            "-v"
                        ])
                    
                    else:
                        print("未知命令，输入 'help' 查看可用命令")
                        
                except KeyboardInterrupt:
                    print("\n退出交互模式")
                    break
                except Exception as e:
                    print(f"命令执行错误: {e}")
        
        else:
            print("\nℹ️  未指定操作模式，使用 --help 查看可用选项")
            print("示例:")
            print("  python -m ecu_lib.main --demo")
            print("  python -m ecu_lib.main --simulate basic_test")
            print("  python -m ecu_lib.main --interactive")
        
        # 获取最终状态
        print("\n📊 最终状态:")
        status = await ecu_lib.get_status()
        
        if status["initialized"]:
            print("✅ ECU库运行正常")
            
            if "health" in status:
                health = status["health"]
                print(f"📈 健康分数: {health.get('health_score', 0):.1f}")
                print(f"📱 设备统计: {health['statistics']}")
        else:
            print("❌ ECU库存在问题")
        
        return 0
        
    except Exception as e:
        print(f"❌ ECU库运行失败: {e}")
        logger.exception("ECU库运行异常")
        return 1
    
    finally:
        # 清理资源
        await ecu_lib.cleanup()
        print("\n👋 ECU库已关闭")


if __name__ == "__main__":
    asyncio.run(main())