# Telegram 避難所查詢機器人

一個基於 Python + FastAPI 的 Telegram Bot，可以接收使用者的位置座標，並在 Neon 資料庫中使用 PostGIS 查詢最近的 3 個避難所。

## 功能特色

- 📍 接收使用者傳送的 GPS 座標
- 🗺️ 使用 PostGIS 地理資訊系統查詢最近的避難所
- 💾 直接連接 Neon PostgreSQL 資料庫
- 🔄 使用 Telegram Webhook 模式（適合生產環境）
- 🐳 Docker 容器化部署
- ☁️ 支援 Zeabur 平台部署

## 技術架構

```
使用者 → Telegram App
         ↓
    Telegram API Server
         ↓
    FastAPI Webhook (Docker)
         ↓
    Neon PostgreSQL + PostGIS
         ↓
    返回最近的 3 個避難所
```

## 技術棧

- **後端**: Python 3.12 + FastAPI
- **資料庫**: Neon PostgreSQL + PostGIS
- **容器化**: Docker + Docker Compose
- **部署平台**: Zeabur
- **套件管理**: uv

## 快速開始

### 環境需求

- Python 3.12+
- Docker 與 Docker Compose（本地測試用）
- Neon 帳號與資料庫
- Telegram Bot Token

### 1. 設定環境變數

複製範例檔案並填入你的資料：

```bash
cp docker/.env.example docker/.env
```

編輯 `docker/.env` 檔案：

```env
# Telegram Bot Token (從 @BotFather 取得)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Neon 資料庫連線
DATABASE_URL=postgresql://neondb_owner:[password]@ep-xxx-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require

# Webhook URL (部署後的公開網址)
WEBHOOK_URL=https://your-app.zeabur.app

# 可選：伺服器埠號
PORT=8000
```

### 2. 設定資料庫

確保 Neon 資料庫已經設定好：

```bash
# 執行資料庫設定 SQL
# 在 Neon Dashboard > SQL Editor 中執行 supabase/setup.sql
# 或使用 psql 連線執行
```

資料庫需包含：

- PostGIS 擴充功能
- `shelters` 資料表（包含地理座標欄位）
- `find_nearby_shelters` RPC 函數

### 3. 本地測試

#### 方法 A：使用 Docker Compose（推薦）

```bash
cd docker
docker-compose up --build
```

#### 方法 B：使用 Docker

```bash
cd docker
docker build -t telegram-shelter-bot .
docker run -p 8000:8000 --env-file .env telegram-shelter-bot
```

#### 方法 C：直接執行 Python

```bash
cd docker
pip install -r requirements.txt
python main.py
```

### 4. 測試 API

健康檢查：

```bash
curl http://localhost:8000/health
```

查看 Webhook 資訊：

```bash
curl http://localhost:8000/webhook-info
```

## 部署到 Zeabur

### 方法 A：使用 Zeabur CLI（推薦）

1. 安裝 Zeabur CLI：

```bash
npm install -g @zeabur/cli
```

2. 登入 Zeabur：

```bash
zeabur login
```

3. 初始化並部署：

```bash
cd docker
zeabur init
zeabur deploy
```

4. 在 Zeabur Dashboard 設定環境變數：
   - `TELEGRAM_BOT_TOKEN`
   - `DATABASE_URL`
   - `WEBHOOK_URL`（填入 Zeabur 提供的網址）

### 方法 B：使用 GitHub 整合

1. 將程式碼推送到 GitHub
2. 在 Zeabur Dashboard 中連接 GitHub repository
3. 選擇 `docker` 資料夾作為根目錄
4. 設定環境變數
5. 點擊 Deploy

### 部署後設定

部署完成後，**必須設定 Telegram Webhook**：

**選項 1（自動）**: 訪問以下網址

```
https://your-app.zeabur.app/set-webhook
```

**選項 2（手動）**: 使用 curl

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://your-app.zeabur.app/webhook"
```

驗證 webhook 設定：

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

## 使用說明

### 與機器人互動

1. 在 Telegram 中搜尋你的 Bot
2. 發送 `/start` 開始使用
3. 點擊 📎 (迴紋針圖示)
4. 選擇「Location」→「Send My Current Location」
5. 機器人會回傳最近的 3 個避難所資訊

### 回傳資訊格式

```
🏠 最近的避難所資訊：

1. 中正國小
📍 地址: 台北市中正區...
👥 容納人數: 500 人
📏 距離: 0.35 公里

2. 台北市立圖書館
📍 地址: 台北市中正區...
👥 容納人數: 300 人
📏 距離: 0.52 公里

3. 中正運動中心
📍 地址: 台北市中正區...
👥 容納人數: 800 人
📏 距離: 0.78 公里
```

## 專案結構

```
telegram-shelter-bot/
├── 📖 README.md               # 本檔案 - 完整專案說明
├── 🐳 docker/                 # Docker 部署檔案（📄 有獨立 README）
│   ├── README.md             # Docker 快速參考
│   ├── main.py               # FastAPI 主程式（生產環境代碼）
│   ├── requirements.txt      # Python 依賴套件
│   ├── Dockerfile            # Docker 映像建置檔
│   ├── docker-compose.yml    # Docker Compose 設定
│   ├── .env.example          # 環境變數範例
│   └── .dockerignore         # Docker 建置排除清單
├── 📊 documents/              # 資料檔案
│   ├── shelter.json          # 原始避難所資料
│   └── taipei_shelters.csv   # 處理後的避難所資料（公開資料）
├── 🔧 scripts/                # 資料庫設定腳本
│   ├── setup_database_and_import_shelters.py  # 建立表格並匯入資料
│   └── import_shelters_from_csv.py            # 僅匯入 CSV 資料
└── 🏠 local/                  # 本地測試檔案（polling 模式）
    ├── shelter_bot_polling.py  # 本地測試機器人
    ├── test_connection.py      # 資料庫連線測試
    └── test_telegram_api.py    # Telegram API 測試
```

> 💡 **提示**: `docker/` 資料夾有獨立的 [快速參考文件](docker/README.md)，適合只想快速部署的使用者。

## API 端點

- `GET /` - 歡迎訊息
- `GET /health` - 健康檢查
- `POST /webhook` - Telegram Webhook 接收端點
- `POST /set-webhook` - 手動設定 Telegram Webhook（測試用）
- `GET /webhook-info` - 取得 Webhook 資訊

## 環境變數說明

| 變數名稱 | 必填 | 說明 | 範例 |
|---------|------|------|------|
| `TELEGRAM_BOT_TOKEN` | ✅ | Telegram Bot Token | `123456:ABC-DEF1234ghIkl...` |
| `DATABASE_URL` | ✅ | PostgreSQL 連線字串 | `postgresql://user:pass@host:5432/db` |
| `WEBHOOK_URL` | ✅ | 部署後的公開網址 | `https://your-app.zeabur.app` |
| `PORT` | ❌ | 伺服器埠號（Zeabur 自動設定） | `8000` |

## 避難所資料來源

- 使用台北市政府開放資料平台的避難所 API
- 使用 OpenStreetMap 取得經緯度座標
- 資料處理後保存在 CSV 檔案中（避免重複呼叫 API）

## 疑難排解

### Webhook 設定失敗

檢查：

1. `TELEGRAM_BOT_TOKEN` 是否正確
2. `WEBHOOK_URL` 是否為有效的 HTTPS 網址
3. 網址是否可以從外部訪問

```bash
# 檢查 webhook 狀態
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

### 資料庫連線失敗

檢查：

1. `DATABASE_URL` 格式是否正確
2. Neon 資料庫是否啟用
3. 網路連線是否正常
4. SSL 連線是否正確（Neon 需要 `sslmode=require`）

### 查詢不到避難所

可能原因：

1. 資料庫中沒有避難所資料（執行 `scripts/setup_database_and_import_shelters.py`）
2. 使用者位置不在台北市範圍內
3. `find_nearby_shelters` 函數未正確建立

## 相關連結

- [Telegram Bot API 文件](https://core.telegram.org/bots/api)
- [FastAPI 文件](https://fastapi.tiangolo.com/)
- [Neon 文件](https://neon.tech/docs)
- [PostGIS 文件](https://postgis.net/documentation/)
- [Zeabur 文件](https://zeabur.com/docs)
