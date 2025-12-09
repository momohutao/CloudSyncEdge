# ECU设备库

一个用于管理IoT ECU设备的Python库，提供设备模拟、管理和数据库集成功能。

## 功能特性

- ✅ **设备管理**：支持多种ECU设备类型（共享单车、门禁系统等）
- ✅ **协议支持**：集成JSON-RPC 2.0协议
- ✅ **数据库集成**：完整的CRUD操作和批量写入机制
- ✅ **设备模拟**：可配置的设备行为模拟器
- ✅ **接口规范**：清晰的接口契约，便于团队协作
- ✅ **测试覆盖**：完整的单元测试和集成测试
- ✅ **部署就绪**：Docker支持，一键部署

## 安装

### 从源代码安装

```bash
# 克隆仓库
git clone https://github.com/your-org/ecu-library.git
cd ecu-library

# 安装依赖
pip install -e .

# 安装开发依赖（可选）
pip install -e ".[dev]"