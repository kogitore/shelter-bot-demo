"""
Telegram 避難所查詢機器人 - FastAPI + Docker 版本
使用 Webhook 模式接收 Telegram 訊息，並查詢 Supabase 資料庫
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

import httpx
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from pydantic_settings import BaseSettings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============= 設定 =============
class Settings(BaseSettings):
    """環境變數設定"""
    telegram_bot_token: str
    database_url: str
    webhook_url: str
    port: int = 8000

    class Config:
        env_file = ".env"
        case_sensitive = False


# ============= Telegram 資料格式 =============
class TelegramLocation(BaseModel):
    latitude: float
    longitude: float


class TelegramChat(BaseModel):
    id: int


class TelegramMessage(BaseModel):
    message_id: int
    chat: TelegramChat
    text: Optional[str] = None
    location: Optional[TelegramLocation] = None


class TelegramUpdate(BaseModel):
    update_id: int
    message: Optional[TelegramMessage] = None


# ============= 避難所資料格式 =============
class Shelter(BaseModel):
    id: int
    name: str
    address: str
    capacity: int
    district: Optional[str] = None
    latitude: float
    longitude: float
    distance_km: float


settings = Settings()


# ============= 資料庫操作 =============
class DatabaseManager:
    """資料庫管理類別"""

    def __init__(self, database_url: str):
        self.database_url = database_url

    def get_connection(self):
        """取得資料庫連線"""
        return psycopg2.connect(self.database_url)

    def find_nearby_shelters(
        self,
        latitude: float,
        longitude: float,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """查詢最近的避難所 - 使用 PostGIS 直接計算距離"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    id,
                    name,
                    address,
                    capacity,
                    district,
                    ST_Y(geom::geometry) AS latitude,
                    ST_X(geom::geometry) AS longitude,
                    ST_Distance(
                        geom,
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                    ) / 1000 AS distance_km
                FROM shelters
                WHERE ST_DWithin(
                    geom,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    10000
                )
                ORDER BY distance_km
                LIMIT %s
            """

            cursor.execute(query, (longitude, latitude, longitude, latitude, limit))
            results = cursor.fetchall()
            cursor.close()
            conn.close()

            # 轉換為字典列表
            shelters = []
            for row in results:
                shelters.append({
                    'id': row['id'],
                    'name': row['name'],
                    'address': row['address'],
                    'capacity': row['capacity'],
                    'district': row['district'],
                    'latitude': float(row['latitude']) if row['latitude'] else 0,
                    'longitude': float(row['longitude']) if row['longitude'] else 0,
                    'distance_km': round(float(row['distance_km']), 2)
                })

            logger.info(f"找到 {len(shelters)} 個避難所")
            return shelters

        except Exception as e:
            logger.error(f"資料庫查詢錯誤: {e}")
            raise


# ============= Telegram Bot 操作 =============
class TelegramBot:
    """Telegram Bot 管理類別"""

    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML"):
        """發送訊息"""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }

        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"訊息已發送到 chat_id: {chat_id}")
            return response.json()
        except Exception as e:
            logger.error(f"發送訊息失敗: {e}")
            raise

    async def set_webhook(self, webhook_url: str):
        """設定 Webhook"""
        url = f"{self.base_url}/setWebhook"
        payload = {"url": f"{webhook_url}/webhook"}

        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Webhook 設定成功: {result}")
            return result
        except Exception as e:
            logger.error(f"設定 Webhook 失敗: {e}")
            raise

    async def get_webhook_info(self):
        """取得 Webhook 資訊"""
        url = f"{self.base_url}/getWebhookInfo"

        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"取得 Webhook 資訊失敗: {e}")
            raise

    async def close(self):
        """關閉 HTTP 客戶端"""
        await self.client.aclose()


class MessageHandler:
    """Telegram 訊息處理器"""

    def __init__(self, bot: TelegramBot, db: DatabaseManager):
        self.bot = bot
        self.db = db

    async def handle_start(self, chat_id: int):
        """處理 /start 命令"""
        welcome_text = (
            "🏠 <b>歡迎使用台北避難所查詢機器人！</b>\n\n"
            "📍 請傳送您的定位訊息以查詢最近的避難所。\n\n"
            "<b>使用方式：</b>\n"
            "1. 點擊 📎 (迴紋針圖示)\n"
            "2. 選擇「Location」\n"
            "3. 選擇「Send My Current Location」\n\n"
            "機器人會為您找到最近的 3 個避難所資訊。"
        )
        await self.bot.send_message(chat_id, welcome_text)

    async def handle_location(self, chat_id: int, latitude: float, longitude: float):
        """處理位置訊息"""
        try:
            await self.bot.send_message(chat_id, "🔍 正在查詢最近的避難所...")

            shelters = self.db.find_nearby_shelters(latitude, longitude, limit=3)

            if not shelters:
                await self.bot.send_message(
                    chat_id,
                    "❌ 抱歉，找不到附近的避難所。\n請確認您的位置是否在台北市範圍內。"
                )
                return

            # 格式化並發送避難所資訊
            message = self.format_shelters_message(shelters)
            await self.bot.send_message(chat_id, message)

        except Exception as e:
            logger.error(f"處理位置訊息錯誤: {e}")
            error_message = (
                f"❌ 查詢避難所時發生錯誤。\n"
                f"請稍後再試，或聯絡管理員。\n\n"
                f"錯誤詳情: {str(e)[:100]}"
            )
            await self.bot.send_message(chat_id, error_message)

    async def handle_text(self, chat_id: int, text: str):
        """處理一般文字訊息"""
        help_text = (
            "請傳送您的位置訊息以查詢最近的避難所。\n\n"
            "<b>使用方式：</b>\n"
            "1. 點擊 📎 (迴紋針圖示)\n"
            "2. 選擇「Location」\n"
            "3. 選擇「Send My Current Location」"
        )
        await self.bot.send_message(chat_id, help_text)

    def format_shelters_message(self, shelters: List[Dict[str, Any]]) -> str:
        """格式化避難所訊息"""
        lines = ["🏠 <b>最近的避難所資訊：</b>\n"]

        for idx, shelter in enumerate(shelters, 1):
            shelter_text = (
                f"<b>{idx}. {shelter['name']}</b>\n"
                f"📍 地址: {shelter['address']}\n"
                f"👥 容納人數: {shelter['capacity']} 人\n"
                f"📏 距離: {shelter['distance_km']} 公里\n"
            )
            lines.append(shelter_text)

        return "\n".join(lines)

    async def process_update(self, update: TelegramUpdate):
        """處理 Telegram 更新"""
        if not update.message:
            logger.info("收到非訊息更新，忽略")
            return

        message = update.message
        chat_id = message.chat.id

        if message.text == "/start":
            await self.handle_start(chat_id)
            return

        if message.location:
            await self.handle_location(
                chat_id,
                message.location.latitude,
                message.location.longitude
            )
            return

        if message.text:
            await self.handle_text(chat_id, message.text)
            return


# ============= FastAPI 應用程式 =============
@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理"""
    logger.info("🚀 應用程式啟動")
    logger.info(f"Webhook URL: {settings.webhook_url}")

    app.state.bot = TelegramBot(settings.telegram_bot_token)
    app.state.db = DatabaseManager(settings.database_url)
    app.state.handler = MessageHandler(app.state.bot, app.state.db)

    yield

    logger.info("👋 應用程式關閉")
    await app.state.bot.close()


app = FastAPI(
    title="Telegram 避難所查詢機器人",
    description="使用 PostGIS 查詢最近的避難所",
    version="1.0.0",
    lifespan=lifespan
)


# ============= API 路由 =============
@app.get("/")
async def root():
    """根路徑"""
    return {
        "message": "🏠 Telegram 避難所查詢機器人運行中",
        "status": "ok",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """健康檢查"""
    return {
        "status": "healthy",
        "service": "telegram-shelter-bot"
    }


@app.post("/webhook")
async def webhook(request: Request):
    """Telegram Webhook 端點"""
    try:
        data = await request.json()
        logger.info(f"收到 Webhook: {data.get('update_id')}")

        update = TelegramUpdate(**data)
        await request.app.state.handler.process_update(update)

        return {"ok": True}

    except Exception as e:
        logger.error(f"處理 Webhook 錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/set-webhook")
async def set_webhook_endpoint(request: Request):
    """手動設定 Webhook（測試用）"""
    try:
        result = await request.app.state.bot.set_webhook(settings.webhook_url)
        return {
            "success": True,
            "result": result,
            "webhook_url": f"{settings.webhook_url}/webhook"
        }
    except Exception as e:
        logger.error(f"設定 Webhook 錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/webhook-info")
async def get_webhook_info(request: Request):
    """取得 Webhook 資訊"""
    try:
        info = await request.app.state.bot.get_webhook_info()
        return info
    except Exception as e:
        logger.error(f"取得 Webhook 資訊錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= 主程式 =============
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
