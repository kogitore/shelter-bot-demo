# Docker 部署快速參考

本資料夾包含 Telegram 避難所查詢機器人的 Docker 部署所需檔案。

## 🚀 快速開始

```bash
# 1. 設定環境變數
cp .env.example .env
# 編輯 .env 填入你的 Telegram Bot Token 和資料庫連線資訊

# 2. 啟動服務
docker-compose up --build

# 3. 測試
curl http://localhost:8000/health
```

## 📚 完整文件

**本檔案僅為快速參考。完整說明請查看：**

👉 [專案根目錄 README](../README.md)

包含：
- 完整的部署指南（Zeabur CLI 和 GitHub 整合）
- 詳細的疑難排解
- API 端點文件
- 資料庫設定說明
- 開發指南
- 安全注意事項

## 📁 檔案說明

```
docker/
├── main.py                # FastAPI 主程式（Webhook 模式）
├── requirements.txt       # Python 依賴套件
├── Dockerfile            # Docker 映像建置檔
├── docker-compose.yml    # 本地測試用 Docker Compose 配置
├── .env.example          # 環境變數範例（需複製為 .env）
├── .dockerignore         # Docker 建置排除清單
├── test_database.py      # 資料庫測試腳本
└── test_neon.py          # Neon 資料庫測試腳本
```

## 🔧 常用指令

```bash
# 本地開發
docker-compose up --build          # 建置並啟動
docker-compose up -d               # 背景執行
docker-compose logs -f             # 查看即時 logs
docker-compose down                # 停止服務

# 直接使用 Docker
docker build -t telegram-shelter-bot .
docker run -p 8000:8000 --env-file .env telegram-shelter-bot

# 進入容器執行指令
docker exec -it telegram-shelter-bot bash
```

## 🌐 部署到 Zeabur

詳細步驟請參考 [根目錄 README - 部署到 Zeabur 章節](../README.md#部署到-zeabur)

快速提示：
1. 將程式碼推送到 GitHub
2. 在 Zeabur Dashboard 連接 repository
3. 設定環境變數（TELEGRAM_BOT_TOKEN, DATABASE_URL, WEBHOOK_URL）
4. 部署後訪問 `https://your-app.zeabur.app/set-webhook` 設定 webhook

## 🆘 需要幫助？

- 📖 [完整文件](../README.md)
- 🐛 [Issue Tracker](../../issues)
- 💬 [Discussions](../../discussions)
