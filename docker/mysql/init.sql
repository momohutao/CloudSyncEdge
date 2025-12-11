-- 创建南向模块专用的数据库和表

-- 1. 确保数据库存在（Docker环境变量已创建）
USE southbound_db;

-- 2. 创建设备管理日志表（成员B的职责）
CREATE TABLE IF NOT EXISTS ecu_admin_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ecu_id VARCHAR(100) NOT NULL COMMENT '设备ID',
    action_type ENUM('connect', 'disconnect', 'command', 'status_update', 'error', 'heartbeat') NOT NULL COMMENT '操作类型',
    action_data JSON NOT NULL COMMENT '操作详情',
    result JSON COMMENT '操作结果',
    admin_user VARCHAR(50) DEFAULT 'system' COMMENT '操作用户',
    ip_address VARCHAR(45) COMMENT 'IP地址',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    
    INDEX idx_ecu_id (ecu_id),
    INDEX idx_action_type (action_type),
    INDEX idx_created_at (created_at),
    INDEX idx_ecu_created (ecu_id, created_at),
    INDEX idx_ip_address (ip_address)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备管理日志表';

-- 3. 创建设备连接状态表（可选，用于快速查询在线设备）
CREATE TABLE IF NOT EXISTS ecu_connections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ecu_id VARCHAR(100) NOT NULL UNIQUE COMMENT '设备ID',
    protocol VARCHAR(20) COMMENT '连接协议',
    ip_address VARCHAR(45) COMMENT 'IP地址',
    port INT COMMENT '端口',
    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '连接时间',
    last_heartbeat TIMESTAMP NULL COMMENT '最后心跳时间',
    status ENUM('connected', 'disconnected', 'timeout') DEFAULT 'connected' COMMENT '连接状态',
    
    INDEX idx_ecu_id (ecu_id),
    INDEX idx_status (status),
    INDEX idx_last_heartbeat (last_heartbeat),
    INDEX idx_ip_port (ip_address, port)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备连接状态表';

-- 4. 插入测试数据（可选）
INSERT INTO ecu_admin_logs (ecu_id, action_type, action_data, ip_address, admin_user) VALUES
('test_bike_001', 'connect', '{"protocol": "websocket", "version": "1.0"}', '192.168.1.100', 'system'),
('test_gate_001', 'connect', '{"protocol": "modbus", "slave_id": 1}', '192.168.1.101', 'system');

INSERT INTO ecu_connections (ecu_id, protocol, ip_address, port, status) VALUES
('test_bike_001', 'websocket', '192.168.1.100', 8080, 'connected'),
('test_gate_001', 'modbus', '192.168.1.101', 502, 'connected');

-- 5. 显示表结构
SHOW TABLES;

SELECT '✅ 南向模块数据库初始化完成' as message;
