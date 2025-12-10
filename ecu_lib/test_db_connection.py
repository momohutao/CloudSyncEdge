"""修复异步结果获取的MySQL测试脚本"""
import sys
import asyncio
import aiomysql

LOCAL_MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3307,
    "user": "root",
    # "password": "20051025",
"password": "123456",
    "db": "test_ecu"
}


async def test_local_mysql():
    print("===== 测试本地MySQL连接 =====")
    try:
        conn = await aiomysql.connect(
            **LOCAL_MYSQL_CONFIG,
            charset="utf8mb4"
        )
        print("✅ 本地MySQL连接成功！")

        async with conn.cursor() as cur:
            # 执行查询并等待结果返回
            await cur.execute("SELECT VERSION();")
            version_result = await cur.fetchone()  # 等待Future对象完成
            print(f"📌 MySQL版本：{version_result[0]}")  # 此时可正常索引

            # 创建测试表
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS ecu_info (
                    ecu_id VARCHAR(50) PRIMARY KEY,
                    device_type VARCHAR(50)
                )
            """)
            print("✅ 成功创建测试表 ecu_info")
        conn.close()
    except Exception as e:
        print(f"❌ 操作失败：{e}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_local_mysql())