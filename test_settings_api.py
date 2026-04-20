#!/usr/bin/env python3
"""
测试设置API端点的简单脚本
"""
import asyncio
import os
import sys
from pathlib import Path

# 设置环境变量
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["ADMIN_API_KEY"] = "j7Pl_ct9i8iskh2nFg4PwQQkJXxPCJpjWDOL35KDZFY="
os.environ["APP_ENV"] = "development"
os.environ["CORS_ORIGINS"] = "*"

import httpx
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import text

# 导入应用
sys.path.insert(0, str(Path(__file__).parent))

# 确保所有模型都被导入
from src.models import Base, SystemSettings
from src.main import app
from src.models.base import async_engine

async def init_db():
    """初始化数据库"""
    async with async_engine.begin() as conn:
        # 先删除已存在的表（测试用）
        await conn.run_sync(Base.metadata.drop_all)
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)
    print("数据库初始化完成")

async def test_settings_api():
    """测试设置API"""
    # 使用TestClient而不是httpx.AsyncClient
    from fastapi.testclient import TestClient

    admin_key = os.environ["ADMIN_API_KEY"]

    headers = {
        "X-API-Key": admin_key,
        "Content-Type": "application/json"
    }

    with TestClient(app) as client:
        print("1. 测试获取设置列表...")
        try:
            response = client.get("/settings", headers=headers)
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   响应: {data}")
                print("   成功: 获取设置列表成功")
            else:
                print(f"   失败: {response.text}")
        except Exception as e:
            print(f"   异常: {e}")

        print("\n2. 测试批量更新设置...")
        try:
            update_data = {
                "settings": [
                    {"key": "github_token", "value": "test_updated_token"},
                    {"key": "deepseek_api_key", "value": "test_updated_key"}
                ]
            }
            response = client.put("/settings", json=update_data, headers=headers)
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   响应: {data}")
                print("   成功: 批量更新设置成功")
            else:
                print(f"   失败: {response.text}")
        except Exception as e:
            print(f"   异常: {e}")

        print("\n3. 测试Webhook测试功能...")
        try:
            test_data = {"platform": "github"}
            response = client.post("/settings/test-webhook", json=test_data, headers=headers)
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   响应: {data}")
                print("   成功: Webhook测试成功")
            else:
                print(f"   失败: {response.text}")
        except Exception as e:
            print(f"   异常: {e}")

async def main():
    """主函数"""
    print("开始测试设置API...")

    # 初始化数据库
    await init_db()

    # 测试API
    await test_settings_api()

    print("\n测试完成!")

if __name__ == "__main__":
    asyncio.run(main())