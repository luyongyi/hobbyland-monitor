#!/bin/bash
# ============================================================
# GitHub Secrets 配置脚本
# 用法: bash infra/setup-github-env.sh
#
# 在运行前，确保:
#   1. 已安装 gh CLI (brew install gh)
#   2. 已登录 gh (gh auth login)
#   3. 下方变量填入你的实际值
# ============================================================
set -e

REPO="luyongyi/hobbyland-monitor"

# ---- 填入你的实际值（这些都不会进入 git 历史） ----
SERVER_HOST=""          # 服务器 IP，例如 "1.2.3.4"
SERVER_USER=""          # SSH 用户名，例如 "ubuntu"
SERVER_SSH_PORT=""      # SSH 端口，留空默认 22
DOMAIN=""               # 部署的域名，例如 "app.example.com"
SSL_CERT_NAME=""        # SSL 证书文件名（不含扩展），通常是基础域名 "example.com"
# SERVER_SSH_KEY 会从 ~/.ssh/id_rsa 自动读取

# ---- 检查 ----
if [ -z "$SERVER_HOST" ] || [ -z "$SERVER_USER" ] || [ -z "$DOMAIN" ]; then
    echo "❌ 请先编辑此脚本，填入 SERVER_HOST、SERVER_USER、DOMAIN"
    exit 1
fi

echo "=== 配置 GitHub Secrets for $REPO ==="
echo ""

gh secret set SERVER_HOST    --repo "$REPO" --body "$SERVER_HOST"  && echo "  ✅ SERVER_HOST"
gh secret set SERVER_USER    --repo "$REPO" --body "$SERVER_USER"  && echo "  ✅ SERVER_USER"
gh secret set DOMAIN         --repo "$REPO" --body "$DOMAIN"       && echo "  ✅ DOMAIN"
gh secret set SSL_CERT_NAME  --repo "$REPO" --body "${SSL_CERT_NAME:-$DOMAIN}" && echo "  ✅ SSL_CERT_NAME"

# SERVER_SSH_KEY
SSH_KEY_FILE="$HOME/.ssh/id_rsa"
[ -f "$SSH_KEY_FILE" ] || SSH_KEY_FILE="$HOME/.ssh/id_ed25519"
if [ ! -f "$SSH_KEY_FILE" ]; then
    echo "❌ 找不到 SSH 私钥（试了 id_rsa 和 id_ed25519）"
    exit 1
fi
gh secret set SERVER_SSH_KEY --repo "$REPO" < "$SSH_KEY_FILE" && echo "  ✅ SERVER_SSH_KEY (from $SSH_KEY_FILE)"

# SERVER_SSH_PORT (可选)
if [ -n "$SERVER_SSH_PORT" ]; then
    gh secret set SERVER_SSH_PORT --repo "$REPO" --body "$SERVER_SSH_PORT" && echo "  ✅ SERVER_SSH_PORT"
fi

echo ""
echo "=== ✅ 配置完成 ==="
echo ""
echo "当前 Secrets:"
gh secret list --repo "$REPO"
