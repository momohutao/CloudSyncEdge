#!/usr/bin/env python3
"""
数据库初始化脚本
创建 ecu_management 数据库和表结构
"""
import asyncio
import aiomysql
import sys

async def create_database():
    """创建数据库和表"""
    print("=" * 50)
    print("初始化数据库")
    print("=" * 50)
    
    # 首先连接到MySQL（不指定数据库）
    try:
        conn = await aiomysql.connect(
            host='localhost',
            port=3307,#看你的docker中的mysql映射到哪
            user='root',
            # password='20051025'
            password='123456'#你的数据库密码
        )
        print("✅ 连接到MySQL服务器")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False
    
    try:
        async with conn.cursor() as cursor:
            # 1. 创建数据库
            print("\n1. 创建数据库...")
            await cursor.execute("CREATE DATABASE IF NOT EXISTS ecu_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print("   ✅ 数据库 ecu_management 创建/确认成功")
            
            # 切换到新数据库
            await cursor.execute("USE ecu_management")
            
            # 2. 创建 ecu_devices 表（成员A负责）
            print("\n2. 创建 ecu_devices 表...")
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS ecu_devices (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    ecu_id VARCHAR(64) UNIQUE NOT NULL COMMENT '设备唯一标识',
                    device_type VARCHAR(32) NOT NULL DEFAULT 'bike' COMMENT '设备类型: bike/door/other',
                    device_name VARCHAR(128) COMMENT '设备名称',
                    status ENUM('online', 'offline', 'error', 'maintenance') DEFAULT 'offline' COMMENT '设备状态',
                    ip_address VARCHAR(45) COMMENT '最后连接的IP地址',
                    firmware_version VARCHAR(32) COMMENT '固件版本',
                    last_seen DATETIME COMMENT '最后在线时间',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    
                    INDEX idx_ecu_id (ecu_id),
                    INDEX idx_status (status),
                    INDEX idx_last_seen (last_seen),
                    INDEX idx_device_type (device_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            print("   ✅ ecu_devices 表创建成功")
            
            # 3. 创建 ecu_admin_logs 表（成员B负责）
            print("\n3. 创建 ecu_admin_logs 表...")
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS ecu_admin_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    ecu_id VARCHAR(64) NOT NULL COMMENT '设备ID',
                    action_type VARCHAR(32) NOT NULL COMMENT '操作类型: connect/disconnect/command/status_update',
                    action_data JSON COMMENT '操作数据',
                    result JSON COMMENT '执行结果',
                    admin_user VARCHAR(64) DEFAULT 'system' COMMENT '操作管理员',
                    ip_address VARCHAR(45) COMMENT '操作来源IP',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    
                    INDEX idx_ecu_id (ecu_id),
                    INDEX idx_action_type (action_type),
                    INDEX idx_admin_user (admin_user),
                    INDEX idx_created_at (created_at),
                    FOREIGN KEY (ecu_id) REFERENCES ecu_devices(ecu_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            print("   ✅ ecu_admin_logs 表创建成功")
            
            # 4. 插入一些测试数据
            print("\n4. 插入测试数据...")
            test_devices = [
                ('BIKE001', 'bike', '共享单车001', 'online', '192.168.1.101'),
                ('BIKE002', 'bike', '共享单车002', 'offline', None),
                ('DOOR001', 'door', '公司门禁001', 'online', '192.168.1.102'),
                ('DOOR002', 'door', '实验室门禁', 'maintenance', '192.168.1.103'),
            ]
            
            for ecu_id, dev_type, name, status, ip in test_devices:
                await cursor.execute("""
                    INSERT INTO ecu_devices 
                    (ecu_id, device_type, device_name, status, ip_address, last_seen)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                    device_name = VALUES(device_name),
                    status = VALUES(status),
                    ip_address = VALUES(ip_address),
                    last_seen = NOW()
                """, (ecu_id, dev_type, name, status, ip))
            
            print(f"   ✅ 插入 {len(test_devices)} 条测试设备数据")
            
            # 提交更改
            await conn.commit()
            print("\n✅ 数据库初始化完成！")
            
            return True
            
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        await conn.rollback()
        return False
    finally:
        conn.close()

async def verify_database():
    """验证数据库是否正常"""
    print("\n" + "=" * 50)
    print("验证数据库")
    print("=" * 50)
    
    try:
        # 使用 aiomysql 直接连接
        conn = await aiomysql.connect(
            host='localhost',
            port=3307,
            user='root',
            password='123456',
            db='ecu_management'
        )
        
        async with conn.cursor() as cursor:
            # 检查表
            await cursor.execute("SHOW TABLES")
            tables = await cursor.fetchall()
            print(f"✅ 数据库中有 {len(tables)} 个表:")
            for table in tables:
                print(f"   - {table[0]}")
            
            # 检查设备数据
            await cursor.execute("SELECT COUNT(*) as count FROM ecu_devices")
            count_result = await cursor.fetchone()
            device_count = count_result[0]
            print(f"✅ ecu_devices 表中有 {device_count} 条记录")
            
            # 显示部分设备
            await cursor.execute("""
                SELECT ecu_id, device_type, device_name, status, ip_address 
                FROM ecu_devices 
                LIMIT 3
            """)
            devices = await cursor.fetchall()
            print("\n示例设备:")
            for device in devices:
                print(f"   {device[0]} - {device[2]} ({device[1]}) - 状态: {device[3]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False

async def main():
    """主函数"""
    success = await create_database()
    if success:
        await verify_database()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 数据库准备就绪！")
        print("现在可以运行你的ECU应用了。")
    else:
        print("❌ 数据库初始化失败")
        print("请检查MySQL服务和连接配置。")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())