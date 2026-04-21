#!/bin/bash
set -e

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DEPLOY_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

check_env() {
    if [ ! -f .env ]; then
        error ".env 文件不存在，请复制 .env.example 并填写配置: cp .env.example .env"
    fi

    source .env

    local missing=0
    for var in POSTGRES_PASSWORD; do
        if [ -z "${!var}" ]; then
            warn "缺少必要环境变量: $var"
            missing=1
        fi
    done

    if [ "$missing" -eq 1 ]; then
        error "请先在 .env 中填写所有必要配置"
    fi
    ok ".env 配置检查通过"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        error "Docker 未安装"
    fi
    if ! docker compose version &> /dev/null; then
        error "Docker Compose 未安装"
    fi
    ok "Docker & Docker Compose 已就绪"
}

build_backend() {
    info "构建后端镜像 (webhook-server + celery-worker)..."
    docker compose -f docker-compose.prod.yml build webhook-server celery-worker
    ok "后端镜像构建完成"
}

build_frontend() {
    info "构建前端镜像 (frontend)..."
    docker compose -f docker-compose.prod.yml build frontend
    ok "前端镜像构建完成"
}

start_services() {
    info "启动所有服务..."
    docker compose -f docker-compose.prod.yml up -d
    ok "所有服务已启动"
}

wait_healthy() {
    info "等待服务就绪..."
    local max_wait=60
    local waited=0

    while [ $waited -lt $max_wait ]; do
        if curl -sf http://localhost:${1:-80}/health > /dev/null 2>&1; then
            ok "后端服务健康检查通过"
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
        echo -n "."
    done
    echo ""
    warn "后端健康检查超时，请检查日志: docker compose -f docker-compose.prod.yml logs webhook-server"
}

show_status() {
    echo ""
    info "服务状态:"
    docker compose -f docker-compose.prod.yml ps
    echo ""

    local health
    health=$(curl -sf http://localhost:${1:-80}/health 2>/dev/null || echo "FAILED")
    if [ "$health" != "FAILED" ]; then
        ok "后端 API: $health"
    else
        warn "后端 API 暂时不可达，可能需要几秒钟启动"
    fi
    echo ""
    info "访问地址:"
    echo "  前端 Dashboard: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost')"
    echo "  后端 API:       http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost')/health"
}

do_deploy() {
    echo ""
    info "========== Latte PR Agent 一键部署 =========="
    echo ""

    check_docker
    check_env

    build_backend
    build_frontend
    start_services
    wait_healthy "$@"
    show_status "$@"

    echo ""
    ok "========== 部署完成 =========="
}

do_rebuild() {
    echo ""
    info "========== 重建并重启所有服务 =========="
    echo ""

    check_docker
    check_env

    info "停止旧服务..."
    docker compose -f docker-compose.prod.yml down

    build_backend
    build_frontend
    start_services
    wait_healthy "$@"
    show_status "$@"

    echo ""
    ok "========== 重建完成 =========="
}

do_stop() {
    info "停止所有服务..."
    docker compose -f docker-compose.prod.yml down
    ok "所有服务已停止"
}

do_restart() {
    info "重启所有服务..."
    docker compose -f docker-compose.prod.yml restart
    ok "所有服务已重启"
    show_status
}

do_logs() {
    local service="${1:-}"
    if [ -n "$service" ]; then
        docker compose -f docker-compose.prod.yml logs -f --tail=100 "$service"
    else
        docker compose -f docker-compose.prod.yml logs -f --tail=50
    fi
}

do_status() {
    docker compose -f docker-compose.prod.yml ps
    echo ""
    local health
    health=$(curl -sf http://localhost:80/health 2>/dev/null || echo "FAILED")
    echo "Health: $health"
}

do_update() {
    echo ""
    info "========== 拉取最新代码并重新部署 =========="
    echo ""

    check_docker
    check_env

    info "拉取最新代码..."
    git pull origin main || warn "Git pull 失败，继续使用当前代码"

    build_backend
    build_frontend

    info "重启服务..."
    docker compose -f docker-compose.prod.yml up -d --force-recreate
    wait_healthy
    show_status

    echo ""
    ok "========== 更新完成 =========="
}

case "${1:-deploy}" in
    deploy)
        do_deploy "${2:-80}"
        ;;
    rebuild)
        do_rebuild "${2:-80}"
        ;;
    stop)
        do_stop
        ;;
    restart)
        do_restart
        ;;
    logs)
        do_logs "$2"
        ;;
    status)
        do_status
        ;;
    update)
        do_update
        ;;
    build)
        check_docker
        check_env
        build_backend
        build_frontend
        ;;
    *)
        echo "用法: $0 {deploy|rebuild|stop|restart|logs|status|update|build}"
        echo ""
        echo "命令说明:"
        echo "  deploy   - 首次部署（构建 + 启动）"
        echo "  rebuild  - 停止 → 重建 → 启动"
        echo "  stop     - 停止所有服务"
        echo "  restart  - 重启所有服务（不重新构建）"
        echo "  logs     - 查看日志（可选指定服务名）"
        echo "  status   - 查看服务状态"
        echo "  update   - git pull + 重新构建 + 重启"
        echo "  build    - 仅构建镜像"
        echo ""
        echo "示例:"
        echo "  $0 deploy          # 首次部署"
        echo "  $0 logs webhook-server  # 查看后端日志"
        echo "  $0 update          # 拉取最新代码并重新部署"
        exit 1
        ;;
esac
