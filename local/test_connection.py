# ---------------------------
# test_connection.py
# ---------------------------
# 這個腳本用來測試：
# 1. Neon PostgreSQL 資料庫是否能連線並查詢
# 2. Telegram Bot Token 是否可正常呼叫 API
# 執行完後應能印出兩段確認訊息：
#    Database connection successful
#    Telegram bot connection successful
#  commend: uv run --env-file .env python3 test_connection.py
# ---------------------------

# --- 模組區 ---
# psycopg: 這是官方新版的 PostgreSQL 驅動程式。
# psycopg[binary] 表示使用二進位封裝版本（無需自行編譯 libpq）
# 可讓 Python 與 Postgres 連線並執行 SQL 查詢。
import psycopg
from psycopg import OperationalError, DatabaseError
import os
import requests  # 或 import httpx

# --- 資料庫連線區 ---
# 1️⃣ 從環境變數讀取 DATABASE_URL
#    範例格式：
#    postgresql://user:password@host/dbname?sslmode=require
# 2️⃣ 建立連線：psycopg.connect()
try:
    database_url = os.environ.get("DATABASE_URL")
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")  # 或 SELECT PostGIS_Version();
            result = cur.fetchone()
            print("✅ Database connection successful:", result)
except (OperationalError, DatabaseError) as e:
    print("Database connection failed:", e)
# 3️⃣ 建立 cursor 並執行一個簡單查詢，例如：
#    SELECT version(); 或 SELECT PostGIS_Version();
# 4️⃣ 印出查詢結果以確認成功。
# 5️⃣ 若出現 OperationalError 或 DatabaseError，印出錯誤訊息。

# --- Telegram 測試區 ---
# 1️⃣ 從環境變數讀取 TELEGRAM_BOT_TOKEN
# 2️⃣ 建立測試 API URL：
#    f"https://api.telegram.org/bot{token}/getMe"
# 3️⃣ 用 requests.get() 或 httpx.get() 發送請求
# 4️⃣ 解析回傳的 JSON，應包含 "ok": true 與 "result" 欄位。
# 5️⃣ 若 status_code != 200，印出錯誤。
try:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/getMe"
    response = requests.get(url)
    data = response.json()
    if response.status_code == 200 and data.get("ok"):
        print("Telegram bot connection successful:", data.get("result"))
    else:
        print("Telegram bot connection failed:", data)
except Exception as e:
    print("Telegram bot connection error:", e)

# --- 結束區 ---
# 印出最終確認訊息，例如：
#    Database test passed
#    Telegram API reachable
# 若任一測試失敗，印出 ❌ 並提示檢查環境變數。

# --- 補充 ---
# 在執行前請確認：
# export DATABASE_URL="你的Neon連線字串"
# export TELEGRAM_BOT_TOKEN="你的Bot Token"
# 然後執行：
# python test_connection.py
