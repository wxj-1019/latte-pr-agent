#!/usr/bin/env python3
"""
Latte PR Agent 后端启动脚本。

用法:
    python start.py              # 默认启动 (host=0.0.0.0, port=8000, reload)
    python start.py --port 8080  # 指定端口
    python start.py --prod       # 生产模式 (reload 关闭, workers=4)
"""

import argparse
import sys
import os


def check_env():
    """检查必需的环境变量。"""
    required = []
    missing = []
    for key in required:
        if not os.environ.get(key):
            missing.append(key)
    if missing:
        print(f"[警告] 缺少环境变量: {', '.join(missing)}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="启动 Latte PR Agent 后端服务")
    parser.add_argument("--host", default="0.0.0.0", help="绑定地址 (默认: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="监听端口 (默认: 8000)")
    parser.add_argument("--prod", action="store_true", help="生产模式 (关闭 reload)")
    parser.add_argument("--workers", type=int, default=4, help="工作进程数 (仅生产模式, 默认: 4)")
    args = parser.parse_args()

    # 将项目根目录加入路径，确保 src 可被导入
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    check_env()

    import uvicorn

    if args.prod:
        print(f"[Latte PR Agent] 生产模式启动 http://{args.host}:{args.port} (workers={args.workers})")
        uvicorn.run(
            "src.main:app",
            host=args.host,
            port=args.port,
            workers=args.workers,
            log_level="info",
        )
    else:
        print(f"[Latte PR Agent] 开发模式启动 http://{args.host}:{args.port} (reload=True)")
        uvicorn.run(
            "src.main:app",
            host=args.host,
            port=args.port,
            reload=True,
            log_level="debug",
        )


if __name__ == "__main__":
    main()
