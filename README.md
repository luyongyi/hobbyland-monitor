# 🤖 Hobbyland Gundam 库存监控

监控 [hobbylandeshop.com](https://www.hobbylandeshop.com) 上的高达模型，提供 Web 界面让你轻松管理关注的商品，并在到货、打折、降价时收到提醒。

## ✨ 功能

- **📦 商品目录**：可视化展示 700+ 高达模型，含图片、价格、库存状态
- **⭐ 智能关注**：一键关注，系统根据商品当前状态自动推荐关注类型
- **🔔 三种关注模式**：
  - **到货关注** 🟢 — 缺货商品有货时提醒
  - **打折关注** 🏷️ — 原价商品开始打折时提醒
  - **更低价关注** 🔥 — 已打折商品价格进一步下降时提醒
- **📜 告警历史**：完整的告警记录时间线
- **🔄 定时扫描**：每天定时检查（默认中午 12:00），可手动触发
- **📨 多渠道通知**：Web UI / 日志 / Telegram Bot（可扩展）

## 🚀 快速开始

```bash
# 1. 启动服务（首次需构建镜像，约 3-5 分钟）
docker compose up -d

# 2. 打开浏览器访问
open http://localhost:8000

# 3. 查看日志
docker compose logs -f
```

启动后会自动执行首次扫描（约 1 分钟），把 hobbyland 的 700+ 商品全部入库。然后你就可以在 Web 界面里浏览、搜索、关注商品了。

## 🎯 使用流程

1. **浏览商品** — 访问首页，搜索/筛选你感兴趣的高达模型
2. **关注商品** — 点击商品卡片上的「⭐ 关注」按钮，系统自动推荐关注类型：
   - 缺货商品 → 自动推荐「到货关注」
   - 有货原价 → 自动推荐「打折关注」
   - 有货已打折 → 自动推荐「更低价关注」
3. **管理关注** — 在「我的关注」页面查看所有关注的商品（按类型分组）
4. **查看告警** — 在「告警历史」页面查看所有触发过的提醒

## 🔔 配置 Telegram 通知（可选）

```bash
# 创建 .env 文件
cat > .env <<EOF
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
EOF

# 编辑 config/config.yaml，设置 notifiers.telegram.enabled: true
# 重启
docker compose restart
```

## 🛠 开发模式

```bash
# 后端
pip install -r requirements.txt
python -m uvicorn src.main:app --reload --port 8000

# 前端（另一个终端）
cd frontend
npm install
npm run dev  # http://localhost:5173, API 代理到 8000
```

## 📁 项目结构

```
模型监控/
├── src/                     # Python 后端 (FastAPI + APScheduler)
│   ├── main.py              # FastAPI 应用入口
│   ├── api/                 # REST API 路由
│   ├── client/              # Hobbyland API 客户端
│   ├── db/                  # SQLAlchemy 模型 & 引擎
│   ├── repository/          # 数据访问层
│   ├── service/             # 核心业务逻辑
│   ├── notifier/            # 通知模块（日志/Telegram）
│   └── scheduler/           # 定时任务
├── frontend/                # Vue 3 前端 (Vite + Tailwind)
│   ├── src/
│   │   ├── views/           # 三个主页面
│   │   ├── components/      # 复用组件
│   │   └── api/             # API 客户端
│   └── dist/                # 构建产物 (Docker 构建时生成)
├── config/config.yaml       # 配置文件
├── data/                    # SQLite 数据库（Docker 卷）
├── Dockerfile               # 多阶段构建
└── docker-compose.yml
```

## 📊 数据库

SQLite 在 `data/monitor.db`，五张表：

- `products` — 商品最新状态（含图片URL）
- `price_history` — 价格变动历史
- `stock_history` — 库存变动历史
- `watchlist` — 关注列表（SKU + 关注类型）
- `alerts` — 告警记录

## 🔌 API 文档

启动后访问 `http://localhost:8000/docs` 查看 OpenAPI 文档。

## License

MIT
