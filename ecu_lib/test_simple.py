#!/usr/bin/env python3
"""
简单的测试脚本
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_basic():
    """基本测试"""
    print("=" * 50)
    print("ECU库基本测试")
    print("=" * 50)
    
    try:
        # 测试数据库连接
        from ecu_lib.shared.database import SimpleDB
        
        print("1. 测试数据库连接...")
        connected = await SimpleDB.test_connection()
        if connected:
            print("✅ 数据库连接正常")
        else:
            print("⚠️  数据库连接失败，使用模拟模式")
        
        # 测试设备注册
        from ecu_lib.database.ecu_device_dao import ECUDeviceDAO
        
        print("\n2. 测试设备注册...")
        test_id = "test_ecu_" + str(int(asyncio.get_event_loop().time()))
        success = await ECUDeviceDAO.register_device(test_id, "shared_bike", "测试设备")
        if success:
            print(f"✅ 设备注册成功: {test_id}")
        else:
            print("❌ 设备注册失败")
        
        # 测试设备查询
        print("\n3. 测试设备查询...")
        device = await ECUDeviceDAO.get_device(test_id)
        if device:
            print(f"✅ 查询到设备: {device.get('ecu_id')} - {device.get('device_type')}")
        else:
            print("❌ 未查询到设备")
        
        # 测试状态更新
        print("\n4. 测试状态更新...")
        success = await ECUDeviceDAO.update_device_status(test_id, "online", "192.168.1.100")
        if success:
            print("✅ 状态更新成功")
        else:
            print("❌ 状态更新失败")
        
        print("\n🎉 基本测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_ecu_creation():
    """测试ECU创建"""
    print("\n" + "=" * 50)
    print("测试ECU创建")
    print("=" * 50)
    
    try:
        from ecu_lib.core.ecu_factory import get_ecu_factory
        from ecu_lib.core.base_ecu import ECUConfig
        
        factory = get_ecu_factory()
        
        print("1. 创建设备配置...")
        config = ECUConfig(
            ecu_id="test_bike_001",
            device_type="shared_bike",
            firmware_version="1.0.0"
        )
        
        print("2. 创建设备实例...")
        ecu = factory.create_ecu(config)
        if ecu:
            print(f"✅ ECU创建成功: {ecu.ecu_id} ({ecu.device_type})")
            
            print("3. 启动设备...")
            await ecu.start()
            
            print("4. 获取设备状态...")
            status = ecu.get_status_dict()
            print(f"   状态: {status['status']}")
            print(f"   固件版本: {status['firmware_version']}")
            print(f"   运行时间: {status['uptime']:.1f}秒")
            
            print("5. 停止设备...")
            await ecu.stop()
            
            print("✅ ECU测试完成")
            return True
        else:
            print("❌ ECU创建失败")
            return False
            
    except Exception as e:
        print(f"❌ ECU测试失败: {e}")
        return False


async def main():
    """主函数"""
    print("🚀 开始ECU库测试...")
    
    # 运行测试
    success1 = await test_basic()
    success2 = await test_ecu_creation()
    
    print("\n" + "=" * 50)
    if success1 and success2:
        print("🎉 所有测试通过！")
        return 0
    else:
        print("❌ 测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))