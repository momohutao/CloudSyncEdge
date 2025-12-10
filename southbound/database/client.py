import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import aiomysql
from pydantic import BaseModel, Field


class ConnectionInfo(BaseModel):
    """连接信息模型"""
    ecu_id: str
    protocol: str = "websocket"
    ip_address: str
    port: Optional[int] = None
    device_type: Optional[str] = "bike"
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DeviceLog(BaseModel):
    """设备日志模型"""
    ecu_id: str
    action_type: str  # connect, disconnect, command, status_update, error, heartbeat
    action_data: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    admin_user: str = "system"
    ip_address: Optional[str] = None


class SouthboundMySQLClient:
    """南向模块专用的MySQL数据库客户端"""

    def __init__(
            self,
            host: str = "localhost",
            port: int = 3307,  # Docker映射的端口
            user: str = "southbound_user",
            password: str = "southbound_pass",
            database: str = "southbound_db",
            pool_size: int = 5
    ):
        self.host = os.getenv("MYSQL_HOST", host)
        self.port = int(os.getenv("MYSQL_PORT", port))
        self.user = os.getenv("MYSQL_USER", user)
        self.password = os.getenv("MYSQL_PASSWORD", password)
        self.database = os.getenv("MYSQL_DATABASE", database)
        self.pool_size = pool_size

        self.pool: Optional[aiomysql.Pool] = None

    async def initialize(self):
        """初始化数据库连接池"""
        if self.pool is None:
            self.pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.database,
                autocommit=True,
                minsize=self.pool_size,
                maxsize=self.pool_size * 2,
                pool_recycle=3600
            )
            print(f"✅ MySQL连接池初始化成功: {self.host}:{self.port}/{self.database}")

        # 测试连接
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT 1")
                result = await cursor.fetchone()
                if result[0] == 1:
                    print("✅ MySQL连接测试成功")
                else:
                    raise Exception("MySQL连接测试失败")

        return self

    async def close(self):
        """关闭连接池"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            self.pool = None
            print("✅ MySQL连接池已关闭")


    @asynccontextmanager
    async def get_connection(self):
        """获取数据库连接（上下文管理器）"""
        if self.pool is None:
            await self.initialize()

        async with self.pool.acquire() as conn:
            yield conn#函数暂停，把 conn 赋值给外部的 conn 变量；不用手动归还

    @asynccontextmanager
    async def get_cursor(self, conn=None):
        """获取游标（上下文管理器）"""
        # 场景1：外部没传入连接（conn=None）→ 自动获取连接 + 创建游标
        if conn is None:
            # 1. 调用之前的 get_connection() 获取数据库连接（自动从池里拿）
            async with self.get_connection() as conn:
                # 2. 基于该连接创建 DictCursor 游标
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 3. 暂停函数，把游标交给外部使用
                    yield cursor
        # 场景2：外部已传入连接 → 基于已有连接创建游标
        else:
            # 1. 基于传入的连接创建 DictCursor 游标
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 2. 暂停函数，把游标交给外部使用
                yield cursor

    # ============ 设备连接管理 ============

    async def add_connection(self, connection: ConnectionInfo) -> bool:
        """添加设备连接记录"""
        async with self.get_connection() as conn:
            async with self.get_cursor(conn) as cursor:
                try:
                    # 使用REPLACE INTO确保唯一性
                    await cursor.execute("""
                        REPLACE INTO ecu_connections 
                        (ecu_id, protocol, ip_address, port, device_type, metadata, connected_at, status)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW(), 'connected')
                    """, (
                        connection.ecu_id,
                        connection.protocol,
                        connection.ip_address,
                        connection.port,
                        connection.device_type,
                        json.dumps(connection.metadata)
                    ))

                    # 记录连接日志
                    log = DeviceLog(
                        ecu_id=connection.ecu_id,
                        action_type="connect",
                        action_data={
                            "protocol": connection.protocol,
                            "ip": connection.ip_address,
                            "port": connection.port,
                            "device_type": connection.device_type,
                            "metadata": connection.metadata
                        },
                        ip_address=connection.ip_address
                    )
                    await self.add_log(log)

                    return True
                except Exception as e:
                    print(f"添加连接失败:{e}")
                    return False
    async def remove_connection(self, ecu_id: str, reason: str = "disconnect") -> bool:
        """移除设备连接记录"""
        async with self.get_connection() as conn:
            async with self.get_cursor(conn) as cursor:
                try:
                    #获取连接信息用于日志
                    await cursor.execute(
                        "SELECT ip_address FROM ecu_connections WHERE ecu_id = %s",(ecu_id,)
                    )
                    result=await cursor.fetchone()
                    ip_address=result['ip_address'] if result else None
                    #删除连接记录
                    await cursor.execute(
                        "DELETE FROM ecu_connections WHERE ecu_id = %s",
                        (ecu_id,)
                    )
                    #记录断开日志
                    log=DeviceLog(ecu_id=ecu_id,
                                  action_type="disconnect",
                                  action_data={"reason":reason},
                                  ip_address=ip_address
                                  )
                    await self.add_log(log)
                    return True
                except Exception as e:
                    print(f"移除连接失败: {e}")
                    return False

    async def update_heartbeat(self, ecu_id: str) -> bool:
        """更新设备心跳时间"""
        async with self.get_connection() as conn:
            async with self.get_cursor(conn) as cursor:
                try:
                    await cursor.execute("""
                                        UPDATE ecu_connections 
                                        SET last_heartbeat = NOW(), status = 'connected'
                                        WHERE ecu_id = %s
                                    """, (ecu_id,))
                    return cursor.rowcount>0
                except Exception as e:
                    print(f"更新心跳失败：{e}")
                    return False

    async def get_connected_devices(self) -> List[Dict[str, Any]]:
        """获取所有已连接设备"""
        async with self.get_connection() as conn:
            async with self.get_cursor(conn) as cursor:
                await cursor.execute("""
                    SELECT ecu_id, protocol, ip_address, port, device_type, 
                           metadata, connected_at, last_heartbeat, status
                    FROM ecu_connections 
                    WHERE status = 'connected'
                    ORDER BY connected_at DESC
                """)
                return await cursor.fetchall()

    async def is_device_connected(self, ecu_id: str) -> bool:
        """检查设备是否在线"""
        async with self.get_connection() as conn:
            async with self.get_cursor(conn) as cursor:
                await cursor.execute("""
                    SELECT 1 FROM ecu_connections 
                    WHERE ecu_id = %s AND status = 'connected'
                """, (ecu_id,))
                return await cursor.fetchone() is not None
    async def cleanup_timeout_connections(self,timeout_seconds:int =60)->int:
        """清理超时连接"""
        async with self.get_connection() as conn:
            async with self.get_cursor(conn) as cursor:
                try:
                    timeout_time=datetime.now()-timedelta(seconds=timeout_seconds)
                    # 查找超时设备
                    await cursor.execute(""" SELECT ecu_id, ip_address 
                        FROM ecu_connections 
                        WHERE status = 'connected' 
                        AND (last_heartbeat IS NULL OR last_heartbeat < %s)""")
                    # 5. 获取查询结果（字典列表，比如 [{"ecu_id":"ECU001", "ip_address":"192.168.1.1"}, ...]）
                    timeout_devices = await cursor.fetchall()
                    # 6. 第二步SQL：批量更新超时设备的状态为timeout
                    await cursor.execute("""
                                    UPDATE ecu_connections 
                                    SET status = 'timeout'
                                    WHERE status = 'connected' 
                                    AND (last_heartbeat IS NULL OR last_heartbeat < %s)
                                """, (timeout_time,))
                    # 7. 为每个超时设备记录日志
                    for device in timeout_devices:
                        # 构造日志对象（基于之前定义的DeviceLog模型）
                        log = DeviceLog(
                            ecu_id=device['ecu_id'],  # 设备唯一标识
                            action_type="disconnect",  # 动作类型：断开连接
                            action_data={
                                "reason": "timeout",  # 断开原因：超时
                                "timeout_seconds": timeout_seconds  # 超时秒数
                            },
                            ip_address=device.get('ip_address')  # 设备IP（可能为None）
                        )
                        await self.add_log(log)
                    return len(timeout_devices)
                except Exception as e:
                    print(f"清理连接超时失败{e}")
                    return 0

    async def add_log(self, log: DeviceLog) -> int:
        """添加设备日志"""
        async with self.get_connection() as conn:
            async with self.get_cursor(conn) as cursor:
                try:
                    await cursor.execute("""                        INSERT INTO ecu_admin_logs 
                        (ecu_id, action_type, action_data, result, admin_user, ip_address)
                        VALUES (%s, %s, %s, %s, %s, %s)""",(
                        log.ecu_id,
                        log.action_type,
                        json.dumps(log.action_data),
                        json.dumps(log.result) if log.result else None,
                        log.admin_user,
                        log.ip_address))
                    return cursor.lastrowid
                except Exception as e:
                    print(f"❌ 添加日志失败: {e}")
                    return -1

    async def log_command(self,
                          ecu_id: str,
                          command: str,
                          params: Dict[str, Any],
                          result: Dict[str, Any],
                          admin_user: str = "system",
                          ip_address: Optional[str] = None) -> int:
        """记录命令执行日志"""
        log = DeviceLog(
            ecu_id=ecu_id,
            action_type="command",
            action_data={
                "command": command,
                "params": params,
                "timestamp": datetime.now().isoformat()
            },
            result=result,
            admin_user=admin_user,
            ip_address=ip_address
        )
        return await self.add_log(log)
    async def get_device_logs(self,ecu_id:str,limit:int=50,action_type:Optional[str]=None)->List[Dict[str,Any]]:
        """获取设备日志"""
        async with self.get_connection() as conn:
            async with self.get_cursor(conn) as cursor:
                try:
                    sql = """
                            SELECT id, ecu_id, action_type, action_data, result, 
                                   admin_user, ip_address, created_at
                            FROM ecu_admin_logs
                            WHERE ecu_id = %s
                                    """
                    params = [ecu_id]

                    if action_type:
                        sql+="AND action_type = %s"
                        params.append(action_type)
                    sql+= " ORDER BY created_at DESC LIMIT %s"
                    params.append(limit)

                    await cursor.execute(sql,params)
                    logs=await cursor.fetchall()
                    #解析JSON字段
                    for log in logs:
                        if log['action_data']:
                            log['action_data'] = json.loads(log['action_data'])
                        if log['result']:
                            log['result'] = json.loads(log['result'])
                    return logs
                except Exception as e:
                    print(f"❌ 获取设备日志失败: {e}")
                    return []

    async def get_recent_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的日志"""
        async with self.get_connection() as conn:
            async with self.get_cursor(conn) as cursor:
                try:
                    await cursor.execute("""
                           SELECT id, ecu_id, action_type, action_data, admin_user, 
                                  ip_address, created_at
                           FROM ecu_admin_logs
                           ORDER BY created_at DESC
                           LIMIT %s
                       """, (limit,))

                    logs = await cursor.fetchall()

                    for log in logs:
                        if log['action_data']:
                            log['action_data'] = json.loads(log['action_data'])

                    return logs

                except Exception as e:
                    print(f"❌ 获取最近日志失败: {e}")
                    return []
    async def get_statistics(self)->Dict[str,Any]:
        """获取统计信息"""
        async with self.get_connection() as conn:
            async with self.get_cursor(conn) as cursor:
                try:
                    #连接统计
                    await cursor.execute("""                        SELECT 
                            COUNT(*) as total_connections,
                            SUM(CASE WHEN status = 'connected' THEN 1 ELSE 0 END) as active_connections,
                            SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END) as timeout_connections
                        FROM ecu_connections""")
                    conn_stats = await cursor.fetchone()
                    #日志统计
                    await cursor.execute("""
                                           SELECT 
                                               COUNT(*) as total_logs,
                                               COUNT(DISTINCT ecu_id) as unique_devices,
                                               action_type,
                                               COUNT(*) as count
                                           FROM ecu_admin_logs
                                           GROUP BY action_type
                                       """)
                    log_stats = await cursor.fetchall()
                    # 设备类型统计
                    await cursor.execute("""
                                       SELECT 
                                           device_type,
                                           COUNT(*) as count
                                       FROM ecu_connections
                                       WHERE device_type IS NOT NULL
                                       GROUP BY device_type
                                   """)
                    device_stats = await cursor.fetchall()

                    return {
                        "timestamp": datetime.now().isoformat(),
                        "connections": conn_stats,
                        "logs_by_action": log_stats,
                        "devices_by_type": device_stats
                    }
                except Exception as e:
                    print(f"❌ 获取统计信息失败: {e}")
                    return {}

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            async with self.get_connection() as conn:
                async with self.get_cursor(conn) as cursor:
                    # 检查连接
                    await cursor.execute("SELECT 1 as status")
                    result = await cursor.fetchone()

                    # 检查表
                    await cursor.execute("SHOW TABLES")
                    tables = await cursor.fetchall()

                    return {
                        "status": "healthy" if result and result['status'] == 1 else "unhealthy",
                        "database": self.database,
                        "tables": [table['Tables_in_southbound_db'] for table in tables],
                        "timestamp": datetime.now().isoformat()
                    }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }