# 接收 user 發送的定位訊息，並回傳最近的三個台北避難所資訊
# 本地測試使用 polling 模式查詢訊息
# 生產環境部署使用 webhook 模式 (見 docker/main.py)
import os
import logging
import psycopg
from psycopg.rows import dict_row
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv("DATABASE_URL")
SHELTER_TABLE = "shelters"
MAX_RESULTS = 3

tg_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
if not tg_bot_token:
    raise ValueError("TELEGRAM_BOT_TOKEN 環境變數未設定")
app = ApplicationBuilder().token(tg_bot_token).build()
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("歡迎使用台北避難所查詢機器人！請傳送您的定位訊息以查詢最近的避難所。")
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.location:
        await update.message.reply_text("請傳送有效的定位訊息。")
        return

    user_location = update.message.location
    user_lat = user_location.latitude
    user_lon = user_location.longitude
    logger.info(f"收到位置訊息: lat={user_lat}, lon={user_lon}")

    try:
        # 查詢最近的避難所
        query = """
            SELECT name, address, capacity, district,
                   ST_Distance(
                       geom,
                       ST_GeogFromText(%s)
                   ) AS distance
            FROM shelters
            WHERE geom IS NOT NULL
            ORDER BY distance
            LIMIT %s;
        """
        
        point_wkt = f'POINT({user_lon} {user_lat})'
        
        async with await psycopg.AsyncConnection.connect(DATABASE_URL, row_factory=dict_row) as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (point_wkt, MAX_RESULTS))
                shelters = await cur.fetchall()

        if not shelters:
            await update.message.reply_text("抱歉，找不到附近的避難所。")
            return

        response_lines = ["🏠 最近的避難所資訊：\n"]
        for i, shelter in enumerate(shelters, 1):
            distance_km = shelter['distance'] / 1000  # 轉換為公里
            line = (f"{i}. **{shelter['name']}**\n"
                   f"📍 地址: {shelter['address']}\n"
                   f"👥 容納人數: {shelter['capacity']} 人\n"
                   f"📏 距離: {distance_km:.2f} 公里\n")
            response_lines.append(line)

        await update.message.reply_text("\n".join(response_lines), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"處理位置訊息時發生錯誤: {e}")
        await update.message.reply_text("抱歉，查詢避難所時發生錯誤，請稍後再試。")
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.LOCATION, handle_location))
if __name__ == "__main__":
    logger.info("機器人啟動中...")
    app.run_polling()