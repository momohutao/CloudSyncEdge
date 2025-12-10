# southbound/database/config.py
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class MySQLConfig:
    """MySQL配置"""
    host: str = "localhost"
    port: int = 3307  # Docker MySQL端口
    user: str = "southbound_user"
    password: str = "southbound_pass"
    database: str = "southbound_db"
    pool_size: int = 5

    @classmethod
    def from_env(cls) -> 'MySQLConfig':
        """从环境变量加载配置"""
        return cls(
            host=os.getenv("MYSQL_HOST", cls.host),
            port=int(os.getenv("MYSQL_PORT", cls.port)),
            user=os.getenv("MYSQL_USER", cls.user),
            password=os.getenv("MYSQL_PASSWORD", cls.password),
            database=os.getenv("MYSQL_DATABASE", cls.database),
            pool_size=int(os.getenv("MYSQL_POOL_SIZE", cls.pool_size))
        )

    def get_dsn(self) -> str:
        """获取DSN连接字符串"""
        return f"mysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"