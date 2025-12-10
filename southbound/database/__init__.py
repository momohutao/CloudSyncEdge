# southbound/database/__init__.py
"""
南向模块数据库包
"""
from typing import Optional

from .client import (
    SouthboundMySQLClient,
    ConnectionInfo,
    DeviceLog
)
from .config import MySQLConfig

# 全局数据库客户端实例
_db_client: Optional[SouthboundMySQLClient] = None


def get_database_client() -> SouthboundMySQLClient:
    """获取数据库客户端实例（单例模式）"""
    global _db_client
    if _db_client is None:
        raise RuntimeError("数据库客户端未初始化，请先调用 init_database()")
    return _db_client


async def init_database(config: Optional[MySQLConfig] = None):
    """初始化数据库"""
    global _db_client

    if _db_client is not None:
        print("⚠️ 数据库已初始化，跳过重复初始化")
        return

    if config is None:
        config = MySQLConfig.from_env()

    _db_client = SouthboundMySQLClient(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=config.database,
        pool_size=config.pool_size
    )

    await _db_client.initialize()

    # 健康检查
    health = await _db_client.health_check()
    if health['status'] == 'healthy':
        print(f"✅ 南向MySQL数据库初始化完成: {config.get_dsn()}")
        print(f"   可用表: {', '.join(health['tables'])}")
    else:
        print(f"⚠️ 数据库健康检查警告: {health.get('error')}")


async def close_database():
    """关闭数据库连接"""
    global _db_client
    if _db_client:
        await _db_client.close()
        _db_client = None


__all__ = [
    'SouthboundMySQLClient',
    'ConnectionInfo',
    'DeviceLog',
    'MySQLConfig',
    'get_database_client',
    'init_database',
    'close_database'
]