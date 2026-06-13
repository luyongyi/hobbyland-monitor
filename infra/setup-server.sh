#!/bin/bash
# ============================================================
# 服务器初始化脚本 — 在新服务器上只需运行一次
#
# 用法：
#   DOMAIN=app.example.com SSL_CERT_NAME=example.com bash setup-server.sh
#
# 也可以提前 export 环境变量再运行。
# ============================================================
set -e

DEPLOY_DIR="${DEPLOY_DIR:-/opt/hobbyland-monitor}"
REPO_URL="${REPO_URL:-https://github.com/luyongyi/hobbyland-monitor.git}"
DOMAIN="${DOMAIN:-}"
SSL_CERT_NAME="${SSL_CERT_NAME:-$DOMAIN}"

if [ -z "$DOMAIN" ]; then
    echo "❌ 请先设置 DOMAIN 环境变量，例如:"
    echo "   DOMAIN=app.example.com SSL_CERT_NAME=example.com bash setup-server.sh"
    exit 1
fi

echo "=== [1/5] 安装 Docker ==="
if command -v docker &>/dev/null; then
    echo "  Docker 已安装: $(docker --version)"
else
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER"
    echo "  Docker 安装完成，已将 $USER 加入 docker 组"
fi

echo ""
echo "=== [2/5] 克隆仓库 ==="
if [ -d "$DEPLOY_DIR" ]; then
    echo "  $DEPLOY_DIR 已存在，跳过"
else
    sudo git clone "$REPO_URL" "$DEPLOY_DIR"
    sudo chown -R "$USER:$USER" "$DEPLOY_DIR"
    echo "  克隆完成"
fi

echo ""
echo "=== [3/5] 配置 nginx ==="
SITE_CONF="/etc/nginx/sites-available/hobbyland-monitor"
sed -e "s|__DOMAIN__|${DOMAIN}|g" \
    -e "s|__SSL_CERT_NAME__|${SSL_CERT_NAME}|g" \
    "$DEPLOY_DIR/infra/nginx/site.conf.template" | sudo tee "$SITE_CONF" > /dev/null
sudo ln -sf "$SITE_CONF" /etc/nginx/sites-enabled/hobbyland-monitor

# 检查 SSL 证书
if [ ! -f "/etc/nginx/ssl/${SSL_CERT_NAME}.crt" ]; then
    echo "  ⚠️  SSL 证书不存在: /etc/nginx/ssl/${SSL_CERT_NAME}.crt"
    echo "  请放置通配符或对应域名证书后再运行: sudo nginx -t && sudo nginx -s reload"
else
    sudo nginx -t && sudo nginx -s reload
    echo "  nginx 配置生效"
fi

echo ""
echo "=== [4/5] 创建 .env ==="
cd "$DEPLOY_DIR"
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  已从 .env.example 创建 .env，请编辑填入实际配置"
else
    echo "  .env 已存在，跳过"
fi

echo ""
echo "=== [5/5] 启动服务 ==="
sudo mkdir -p data
sudo docker compose up -d --build
echo "  容器已启动"

echo ""
echo "==========================================="
echo "  ✅ 初始化完成!"
echo ""
echo "  访问: https://${DOMAIN}"
echo "  数据目录: $DEPLOY_DIR/data/"
echo "  配置文件: $DEPLOY_DIR/.env"
echo "  日志: sudo docker compose -f $DEPLOY_DIR/docker-compose.yml logs -f"
echo "==========================================="
