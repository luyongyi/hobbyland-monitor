#!/bin/bash
# ============================================================
# GitHub Environment 配置脚本
# 用法: bash infra/setup-github-env.sh
#
# 在运行前，确保:
#   1. 已安装 gh CLI (brew install gh)
#   2. 已登录 gh (gh auth login)
#   3. 下方变量填入你的实际值
# ============================================================
set -e

REPO="luyongyi/hobbyland-monitor"

# ---- 填入你的实际值 ----
SERVER_HOST=""          # 服务器 IP，如 "1.2.3.4"
SERVER_USER=""          # SSH 用户名，如 "ubuntu"
SERVER_SSH_PORT=""      # SSH 端口，留空默认 22
# SERVER_SSH_KEY 会从 ~/.ssh/id_rsa 自动读取

# ---- 检查 ----
if [ -z "$SERVER_HOST" ]; then
    echo "❌ 请先编辑此脚本，填入 SERVER_HOST 和 SERVER_USER"
    exit 1
fi

echo "=== 配置 GitHub Secrets for $REPO ==="
echo ""

# SERVER_HOST
echo "[1/4] SERVER_HOST = $SERVER_HOST"
gh secret set SERVER_HOST --repo "$REPO" --body "$SERVER_HOST"

# SERVER_USER
echo "[2/4] SERVER_USER = $SERVER_USER"
gh secret set SERVER_USER --repo "$REPO" --body "$SERVER_USER"

# SERVER_SSH_KEY
SSH_KEY_FILE="$HOME/.ssh/id_rsa"
if [ ! -f "$SSH_KEY_FILE" ]; then
    SSH_KEY_FILE="$HOME/.ssh/id_ed25519"
fi
if [ ! -f "$SSH_KEY_FILE" ]; then
    echo "❌ 找不到 SSH 密钥 (试了 id_rsa 和 id_ed25519)"
    exit 1
fi
echo "[3/4] SERVER_SSH_KEY (from $SSH_KEY_FILE)"
gh secret set SERVER_SSH_KEY --repo "$REPO" < "$SSH_KEY_FILE"

# SERVER_SSH_PORT (可选)
if [ -n "$SERVER_SSH_PORT" ]; then
    echo "[4/4] SERVER_SSH_PORT = $SERVER_SSH_PORT"
    gh secret set SERVER_SSH_PORT --repo "$REPO" --body "$SERVER_SSH_PORT"
else
    echo "[4/4] SERVER_SSH_PORT = (跳过，默认 22)"
fi

echo ""
echo "=== ✅ 配置完成 ==="
echo ""
echo "当前 Secrets:"
gh secret list --repo "$REPO"
echo ""
echo "测试部署: gh workflow run deploy.yml --repo $REPO"
