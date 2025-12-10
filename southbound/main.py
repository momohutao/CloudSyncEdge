
"""
南向模块启动脚本
"""
import asyncio
import sys
import os


from  .server import SouthboundWebSocketServer

async def main():
    print("=" * 50)
    print("🚀 CloudSyncEdge 南向通信模块")
    print("=" * 50)

    # 创建服务器
    server = SouthboundWebSocketServer("0.0.0.0", 8082)

    try:
        await server.start()
    except KeyboardInterrupt:
        print("\n📴 接收到停止信号")
    except Exception as e:
        print(f"\n❌ 服务器运行出错: {e}")
    finally:
        await server.stop()

if __name__ == "__main__":
    asyncio.run(main())