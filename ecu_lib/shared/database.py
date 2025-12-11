"""
共享数据库工具类
所有团队成员都使用这个类来操作数据库
"""
import aiomysql
import logging
from typing import List, Dict, Any, Optional
import asyncio

logger = logging.getLogger(__name__)


class SimpleDB:
    """简单的异步MySQL数据库工具类"""
    
    _pool: Optional[aiomysql.Pool] = None
    _use_mock: bool = False
    _mock_data: Dict = {}  # Mock数据存储
    
    # 数据库配置
    DB_CONFIG = {
        'host': 'localhost',
        'port': 3307,
        'user': 'root',
        'password': 'root123456',
        'db': 'ecu_management',
        'autocommit': True,
        'minsize': 1,
        'maxsize': 10,
        'charset': 'utf8mb4'
    }
    
    @classmethod
    def enable_mock_mode(cls):
        """启用Mock模式（无数据库时使用）"""
        cls._use_mock = True
        cls._mock_data = {
            'ecu_devices': [],
            'ecu_admin_logs': []
        }
        logger.info("启用数据库Mock模式")
    
    @classmethod
    def disable_mock_mode(cls):
        """禁用Mock模式"""
        cls._use_mock = False
        logger.info("禁用数据库Mock模式")
    
    @classmethod
    def is_mock_mode(cls) -> bool:
        """是否在Mock模式"""
        return cls._use_mock
    
    @classmethod
    async def get_pool(cls) -> aiomysql.Pool:
        """获取数据库连接池"""
        if cls._use_mock:
            raise RuntimeError("Mock模式下没有数据库连接池")
            
        if cls._pool is None:
            try:
                logger.info("创建数据库连接池...")
                cls._pool = await aiomysql.create_pool(**cls.DB_CONFIG)
                logger.info("数据库连接池创建成功")
            except Exception as e:
                logger.warning(f"创建数据库连接池失败，将使用Mock模式: {e}")
                cls.enable_mock_mode()
                raise
        return cls._pool
    
    @classmethod
    async def execute(cls, sql: str, *args) -> Any:
        """
        执行SQL语句 - 支持Mock模式
        
        Args:
            sql: SQL语句
            *args: 参数
            
        Returns:
            SELECT查询返回列表，其他返回最后插入的ID
        """
        if cls._use_mock:
            return cls._mock_execute(sql, *args)
        
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                try:
                    await cursor.execute(sql, args)
                    
                    if sql.strip().upper().startswith('SELECT'):
                        result = await cursor.fetchall()
                        logger.debug(f"执行查询: {sql}, 返回行数: {len(result)}")
                        return result
                    else:
                        return cursor.lastrowid
                        
                except aiomysql.Error as e:
                    logger.error(f"SQL执行错误: {e}")
                    raise
    
    @classmethod
    def _mock_execute(cls, sql: str, *args) -> Any:
        """Mock模式下的SQL执行"""
        logger.debug(f"Mock执行: {sql}, 参数: {args}")
        
        sql_upper = sql.strip().upper()
        
        # SELECT查询
        if sql_upper.startswith('SELECT'):
            if "FROM ecu_devices" in sql_upper:
                return cls._mock_data['ecu_devices']
            elif "FROM ecu_admin_logs" in sql_upper:
                return cls._mock_data['ecu_admin_logs']
            else:
                return []
        
        # INSERT操作
        elif sql_upper.startswith('INSERT'):
            if "INTO ecu_devices" in sql_upper:
                device_id = args[0] if args else f"device_{len(cls._mock_data['ecu_devices'])}"
                device = {
                    'ecu_id': device_id,
                    'device_type': args[1] if len(args) > 1 else 'bike',
                    'status': 'offline',
                    'last_seen': '2024-01-01 00:00:00'
                }
                cls._mock_data['ecu_devices'].append(device)
                return len(cls._mock_data['ecu_devices'])
        
        return 0
    
    @classmethod
    async def test_connection(cls) -> bool:
        """测试数据库连接"""
        if cls._use_mock:
            logger.info("Mock模式下，跳过真实数据库连接测试")
            return True
            
        try:
            pool = await cls.get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    result = await cursor.fetchone()
                    return result[0] == 1
        except Exception as e:
            logger.warning(f"数据库连接测试失败，将使用Mock模式: {e}")
            cls.enable_mock_mode()
            return True  # Mock模式下返回True
    
    @classmethod
    async def close(cls):
        """关闭数据库连接池"""
        if not cls._use_mock and cls._pool:
            cls._pool.close()
            await cls._pool.wait_closed()
            cls._pool = None
            logger.info("数据库连接池已关闭")