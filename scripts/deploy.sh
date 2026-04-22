#!/bin/bash
# Latte PR Agent 生产环境部署脚本
# 用法: ./scripts/deploy.sh

set -e

echo "=========================================="
echo "Latte PR Agent 生产环境部署"
echo "=========================================="

# 1. 拉取最新代码
echo "[1/6] 拉取最新代码..."
git pull origin main

# 2. 检查 .env 是否存在
if [ ! -f .env ]; then
    echo "[错误] .env 文件不存在，请复制 .env.example 并配置"
    exit 1
fi

# 3. 检查并执行数据库迁移
echo "[2/6] 检查数据库迁移..."

# 先确保 postgres 容器在运行
if ! docker-compose -f docker-compose.prod.yml ps | grep -q "postgres.*Up"; then
    echo "       启动 postgres 容器..."
    docker-compose -f docker-compose.prod.yml up -d postgres
    sleep 5
fi

# 检查 project_repos 表是否存在
TABLE_EXISTS=$(docker-compose -f docker-compose.prod.yml exec -T postgres \
    psql -U postgres -d code_review -tAc \
    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'project_repos');" 2>/dev/null || echo "f")

if [ "$TABLE_EXISTS" = "t" ]; then
    echo "       project_repos 表已存在，跳过迁移"
else
    echo "       需要执行数据库迁移..."
    # 将迁移脚本复制到 postgres 容器内并执行
    docker cp scripts/migrate-add-project-tables.sql $(docker-compose -f docker-compose.prod.yml ps -q postgres):/tmp/migrate.sql
    docker-compose -f docker-compose.prod.yml exec -T postgres \
        psql -U postgres -d code_review -f /tmp/migrate.sql
    echo "       迁移完成"
fi

# 4. 构建并重启服务
echo "[3/6] 构建后端 Docker 镜像..."
docker-compose -f docker-compose.prod.yml build --no-cache webhook-server celery-worker

echo "[4/6] 构建前端..."
cd frontend
if [ -f .env.production ]; then
    cp .env.production .env
fi
npm install
npm run build
cd ..

echo "[5/6] 启动/重启所有服务..."
docker-compose -f docker-compose.prod.yml up -d --remove-orphans

# 6. 健康检查
echo "[6/6] 健康检查..."
sleep 8

HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "000")
if [ "$HEALTH_STATUS" = "200" ]; then
    echo "=========================================="
    echo "部署成功！"
    echo "后端健康检查: OK (200)"
    echo "=========================================="
else
    echo "=========================================="
    echo "警告: 健康检查返回 $HEALTH_STATUS"
    echo "请检查日志: docker-compose -f docker-compose.prod.yml logs -f webhook-server"
    echo "=========================================="
fi

echo ""
echo "常用命令:"
echo "  查看后端日志: docker-compose -f docker-compose.prod.yml logs -f webhook-server"
echo "  查看 Worker:  docker-compose -f docker-compose.prod.yml logs -f celery-worker"
echo "  查看前端日志: docker-compose -f docker-compose.prod.yml logs -f frontend"
echo "  重启服务:     docker-compose -f docker-compose.prod.yml restart"
