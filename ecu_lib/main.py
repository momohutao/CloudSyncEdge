"""
ECU库主入口文件 - 简化版本
"""
import asyncio
import logging
import argparse
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from ecu_lib.database.client import DatabaseClient
from ecu_lib.core.ecu_factory import get_ecu_factory, ECUFactory
from ecu_lib.devices.device_registry import get_device_registry
from ecu_lib.interfaces.ecu_interface import DefaultECUInterface
from ecu_lib.shared.database import SimpleDB

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class SimpleECULibrary:
    """简化的ECU库"""
    
    def __init__(self):
        self.db_client = None
        self.device_registry = None
        self.ecu_interface = None
        self.initialized = False
    
    async def initialize(self):
        """初始化库"""
        try:
            logger.info("初始化ECU库...")
            
            # 1. 初始化数据库
            self.db_client = DatabaseClient()
            db_init = await self.db_client.initialize()
            
            if not db_init:
                logger.warning("数据库初始化失败，继续使用模拟模式")
            
            # 2. 初始化ECU工厂
            ECUFactory.initialize()
            logger.info("ECU工厂初始化完成")
            
            # 3. 初始化设备注册表
            self.device_registry = get_device_registry()
            logger.info("设备注册表初始化完成")
            
            # 4. 创建ECU接口
            self.ecu_interface = DefaultECUInterface(
                device_registry=self.device_registry,
                db_client=self.db_client
            )
            logger.info("ECU接口创建完成")
            
            self.initialized = True
            logger.info("✅ ECU库初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False
    
    async def create_demo_devices(self):
        """创建演示设备"""
        if not self.initialized:
            logger.error("ECU库未初始化")
            return False
        
        try:
            logger.info("创建演示设备...")
            
            # 创建共享单车
            bike_result = await self.ecu_interface.register_ecu({
                "ecu_id": "demo_bike_001",
                "device_type": "shared_bike",
                "firmware_version": "1.0.0",
                "heartbeat_interval": 30
            })
            
            if bike_result.get("success"):
                logger.info(f"✅ 创建共享单车: demo_bike_001")
                await self.ecu_interface.start_ecu("demo_bike_001")
            else:
                logger.error(f"❌ 创建共享单车失败: {bike_result}")
            
            # 创建门禁设备
            door_result = await self.ecu_interface.register_ecu({
                "ecu_id": "demo_door_001",
                "device_type": "door_access",
                "firmware_version": "1.0.0",
                "heartbeat_interval": 20
            })
            
            if door_result.get("success"):
                logger.info(f"✅ 创建门禁设备: demo_door_001")
                await self.ecu_interface.start_ecu("demo_door_001")
            else:
                logger.error(f"❌ 创建门禁设备失败: {door_result}")
            
            return True
            
        except Exception as e:
            logger.error(f"创建演示设备失败: {e}")
            return False
    
    async def run_demo_commands(self):
        """运行演示命令"""
        if not self.initialized:
            logger.error("ECU库未初始化")
            return False
        
        try:
            logger.info("运行演示命令...")
            
            # 获取所有设备
            devices = await self.ecu_interface.get_all_ecus()
            logger.info(f"设备总数: {len(devices)}")
            
            for device in devices:
                ecu_id = device["ecu_id"]
                
                # 获取状态
                status = await self.ecu_interface.get_ecu_status(ecu_id)
                if status.get("success"):
                    logger.info(f"📊 {ecu_id} 状态: {status['status']['status']}")
                else:
                    logger.warning(f"⚠️  获取{ecu_id}状态失败")
                
                # 根据设备类型执行命令
                if device["device_type"] == "shared_bike":
                    # 解锁单车
                    result = await self.ecu_interface.execute_command(
                        ecu_id, "unlock", {"user_id": "demo_user", "auth_code": "123456"}
                    )
                    if result.get("success"):
                        logger.info(f"🔓 {ecu_id} 解锁成功")
                    else:
                        logger.info(f"🔒 {ecu_id} 解锁失败: {result.get('error_message')}")
                
                elif device["device_type"] == "door_access":
                    # 解锁门禁
                    result = await self.ecu_interface.execute_command(
                        ecu_id, "unlock", {"user_id": "admin", "pin_code": "123456"}
                    )
                    if result.get("success"):
                        logger.info(f"🚪 {ecu_id} 解锁成功")
                    else:
                        logger.info(f"🔐 {ecu_id} 解锁失败: {result.get('error_message')}")
            
            # 健康检查
            health = await self.ecu_interface.health_check()
            logger.info(f"❤️  系统健康状态: {health['status']}")
            
            logger.info("✅ 演示命令完成")
            return True
            
        except Exception as e:
            logger.error(f"运行演示命令失败: {e}")
            return False
    
    async def cleanup(self):
        """清理资源"""
        try:
            logger.info("清理资源...")
            
            if self.ecu_interface:
                # 停止所有设备
                devices = await self.ecu_interface.get_all_ecus()
                for device in devices:
                    await self.ecu_interface.stop_ecu(device["ecu_id"])
                    await self.ecu_interface.unregister_ecu(device["ecu_id"])
            
            if self.db_client:
                await self.db_client.close()
            
            logger.info("资源清理完成")
            
        except Exception as e:
            logger.error(f"清理资源失败: {e}")
    
    async def get_status(self):
        """获取库状态"""
        try:
            devices = await self.ecu_interface.get_all_ecus() if self.ecu_interface else []
            
            return {
                "initialized": self.initialized,
                "devices_count": len(devices),
                "online_devices": len([d for d in devices if d.get("status") == "online"]),
                "database_connected": self.db_client.connected if self.db_client else False
            }
            
        except Exception as e:
            return {"error": str(e)}


async def test_database():
    """测试数据库连接"""
    print("=" * 50)
    print("测试数据库连接")
    print("=" * 50)
    
    try:
        # 测试MySQL连接
        connected = await SimpleDB.test_connection()
        
        if connected:
            print("✅ MySQL数据库连接正常")
            
            # 查询设备数量
            sql = "SELECT COUNT(*) as count FROM ecu_devices"
            result = await SimpleDB.execute(sql)
            count = result[0]["count"] if result else 0
            print(f"📊 数据库中现有设备: {count} 个")
            
            # 列出设备
            sql = "SELECT ecu_id, device_type, status FROM ecu_devices LIMIT 5"
            devices = await SimpleDB.execute(sql)
            
            if devices:
                print("\n设备列表:")
                for device in devices:
                    print(f"  - {device['ecu_id']}: {device['device_type']} ({device['status']})")
            else:
                print("⚠️  数据库中没有设备")
                
        else:
            print("❌ MySQL数据库连接失败")
            print("将在模拟模式下运行")
        
        print("=" * 50)
        return connected
        
    except Exception as e:
        print(f"❌ 数据库测试失败: {e}")
        return False


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="ECU库 - 成员A")
    parser.add_argument("--demo", action="store_true", help="运行演示")
    parser.add_argument("--test-db", action="store_true", help="测试数据库")
    parser.add_argument("--interactive", action="store_true", help="交互模式")
    
    args = parser.parse_args()
    
    print("🚀 ECU库启动...")
    print(f"📁 项目目录: {Path(__file__).parent}")
    
    # 测试数据库连接
    db_ok = await test_database()
    
    # 创建ECU库实例
    ecu_lib = SimpleECULibrary()
    
    try:
        # 初始化
        if not await ecu_lib.initialize():
            print("❌ ECU库初始化失败")
            return 1
        
        print("✅ ECU库初始化成功")
        
        # 根据参数执行操作
        if args.demo:
            print("\n🎬 运行演示...")
            await ecu_lib.create_demo_devices()
            await ecu_lib.run_demo_commands()
            print("\n🎉 演示完成")
        
        elif args.test_db:
            print("\n🧪 数据库测试已完成")
            
        elif args.interactive:
            print("\n💻 交互模式")
            print("输入 'help' 查看可用命令")
            print("输入 'exit' 退出")
            
            while True:
                try:
                    cmd = input("\nECU> ").strip().lower()
                    
                    if cmd in ["exit", "quit"]:
                        break
                    
                    elif cmd == "help":
                        print("可用命令:")
                        print("  status    - 查看库状态")
                        print("  devices   - 列出所有设备")
                        print("  demo      - 运行演示")
                        print("  create    - 创建设备")
                        print("  exit      - 退出")
                    
                    elif cmd == "status":
                        status = await ecu_lib.get_status()
                        print("库状态:")
                        print(f"  已初始化: {status.get('initialized', False)}")
                        print(f"  设备总数: {status.get('devices_count', 0)}")
                        print(f"  在线设备: {status.get('online_devices', 0)}")
                        print(f"  数据库连接: {status.get('database_connected', False)}")
                    
                    elif cmd == "devices":
                        if ecu_lib.ecu_interface:
                            devices = await ecu_lib.ecu_interface.get_all_ecus()
                            print(f"设备总数: {len(devices)}")
                            
                            for device in devices:
                                print(f"  - {device['ecu_id']} ({device['device_type']}): {device['status']}")
                        else:
                            print("ECU接口未初始化")
                    
                    elif cmd == "demo":
                        await ecu_lib.create_demo_devices()
                        await ecu_lib.run_demo_commands()
                    
                    elif cmd == "create":
                        ecu_id = input("设备ID: ").strip()
                        device_type = input("设备类型 (shared_bike/door_access): ").strip()
                        
                        if ecu_id and device_type in ["shared_bike", "door_access"]:
                            result = await ecu_lib.ecu_interface.register_ecu({
                                "ecu_id": ecu_id,
                                "device_type": device_type,
                                "firmware_version": "1.0.0"
                            })
                            
                            if result.get("success"):
                                print(f"✅ 创建设备成功: {ecu_id}")
                                await ecu_lib.ecu_interface.start_ecu(ecu_id)
                            else:
                                print(f"❌ 创建设备失败: {result.get('error_message')}")
                        else:
                            print("❌ 参数无效")
                    
                    else:
                        print("❌ 未知命令，输入 'help' 查看可用命令")
                        
                except KeyboardInterrupt:
                    print("\n退出交互模式")
                    break
                except Exception as e:
                    print(f"❌ 命令执行错误: {e}")
        
        else:
            print("\nℹ️  未指定操作模式，使用 --help 查看可用选项")
            print("示例:")
            print("  python main.py --demo")
            print("  python main.py --test-db")
            print("  python main.py --interactive")
        
        # 显示最终状态
        print("\n📊 最终状态:")
        status = await ecu_lib.get_status()
        
        if status.get("initialized"):
            print("✅ ECU库运行正常")
            print(f"📱 设备总数: {status.get('devices_count', 0)}")
            print(f"🌐 在线设备: {status.get('online_devices', 0)}")
        else:
            print("❌ ECU库存在问题")
        
        return 0
        
    except Exception as e:
        print(f"❌ ECU库运行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        # 清理资源
        await ecu_lib.cleanup()
        print("\n👋 ECU库已关闭")


if __name__ == "__main__":
    asyncio.run(main())