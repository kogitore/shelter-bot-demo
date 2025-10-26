"""
Telegram 避難所查詢機器人 - Polling 模式
本地開發測試使用，生產環境請使用 docker/main.py
"""
import os
import logging
import psycopg
from psycopg.rows import dict_row
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 環境變數
DATABASE_URL = os.getenv("DATABASE_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL 環境變數未設定")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN 環境變數未設定")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理 /start 命令"""
    await update.message.reply_text(
        "歡迎使用台北避難所查詢機器人！\n"
        "請傳送您的定位訊息以查詢最近的避難所。"
    )


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理位置訊息"""
    if not update.message or not update.message.location:
        await update.message.reply_text("請傳送有效的定位訊息。")
        return

    location = update.message.location
    logger.info(f"收到位置訊息: lat={location.latitude}, lon={location.longitude}")

    query = """
        SELECT
            name,
            address,
            capacity,
            district,
            ROUND(
                CAST(
                    ST_Distance(
                        geom,
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                    ) / 1000 AS NUMERIC
                ), 2
            ) AS distance_km
        FROM shelters
        WHERE ST_DWithin(
            geom,
            ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
            10000
        )
        ORDER BY distance_km
        LIMIT 3
    """

    async with await psycopg.AsyncConnection.connect(DATABASE_URL, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                query,
                (location.longitude, location.latitude, location.longitude, location.latitude)
            )
            shelters = await cur.fetchall()

    if not shelters:
        await update.message.reply_text("抱歉，找不到附近的避難所。")
        return

    lines = ["🏠 最近的避難所資訊：\n"]
    for i, shelter in enumerate(shelters, 1):
        lines.append(
            f"{i}. **{shelter['name']}**\n"
            f"📍 地址: {shelter['address']}\n"
            f"👥 容納人數: {shelter['capacity']} 人\n"
            f"📏 距離: {shelter['distance_km']} 公里\n"
        )

    await update.message.reply_text("\n".join(lines), parse_mode='Markdown')


if __name__ == "__main__":
    logger.info("機器人啟動中...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.run_polling()
