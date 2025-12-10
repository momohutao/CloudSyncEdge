"""
协议模块配置文件
"""
import os
from typing import Dict, Any

# 数据库配置
DATABASE_CONFIG = {
    'mock': {
        'type': 'mock',
        'name': 'Mock Database'
    },
    'mysql': {
        'type': 'mysql',
        'host': os.getenv('DB_HOST', '47.105.99.160'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', '123456'),
        'database': os.getenv('DB_NAME', 'ecu_management'),
        'charset': 'utf8mb4',
        'autocommit': True,
        'minsize': 1,
        'maxsize': 10
    },
    'sqlite': {
        'type': 'sqlite',
        'database': os.getenv('SQLITE_DB', 'protocol_logs.db'),
        'echo': False
    }
}

# 日志配置
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'detailed': {
            'format': '%(asctime)s [%(levelname)s] %(name)s.%(funcName)s:%(lineno)d: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'DEBUG',
            'formatter': 'detailed',
            'filename': 'protocol.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        }
    },
    'loggers': {
        'protocol': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False
        }
    }
}

# 协议配置
PROTOCOL_CONFIG = {
    'jsonrpc_version': '2.0',
    'encoding': 'utf-8',
    'default_timeout': 30.0,  # 默认超时时间（秒）
    'max_message_size': 1024 * 1024,  # 最大消息大小 1MB
    'heartbeat_interval': 60,  # 心跳间隔（秒）
    'retry_attempts': 3,  # 重试次数
    'retry_delay': 1.0,  # 重试延迟（秒）
    'enable_compression': False,  # 是否启用压缩
    'enable_encryption': False  # 是否启用加密
}

# Mock数据配置
MOCK_CONFIG = {
    'default_ecu_id': 'test_ecu_001',
    'default_device_type': 'shared_bike',
    'default_battery_level': 78,
    'default_signal_strength': 4,
    'enable_random_errors': True,
    'error_probability': 0.1,  # 10%的错误概率
    'min_response_time': 0.1,  # 最小响应时间（秒）
    'max_response_time': 2.0   # 最大响应时间（秒）
}

def get_config(config_type: str = 'protocol') -> Dict[str, Any]:
    """
    获取配置
    
    Args:
        config_type: 配置类型 ('database', 'logging', 'protocol', 'mock')
        
    Returns:
        配置字典
    """
    configs = {
        'database': DATABASE_CONFIG,
        'logging': LOGGING_CONFIG,
        'protocol': PROTOCOL_CONFIG,
        'mock': MOCK_CONFIG
    }
    
    return configs.get(config_type, {})


def setup_logging(config_type: str = 'default'):
    """
    设置日志配置
    
    Args:
        config_type: 配置类型
    """
    import logging.config
    
    if config_type == 'default':
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        logging.config.dictConfig(LOGGING_CONFIG)


# 环境变量映射
ENV_MAPPING = {
    'DB_TYPE': ('database', 'type'),
    'DB_HOST': ('database', 'host'),
    'DB_PORT': ('database', 'port'),
    'DB_USER': ('database', 'user'),
    'DB_PASSWORD': ('database', 'password'),
    'DB_NAME': ('database', 'database')
}


def load_from_env() -> Dict[str, Any]:
    """
    从环境变量加载配置
    
    Returns:
        配置字典
    """
    config = {}
    
    for env_var, (section, key) in ENV_MAPPING.items():
        value = os.getenv(env_var)
        if value:
            if section not in config:
                config[section] = {}
            config[section][key] = value
    
    return config