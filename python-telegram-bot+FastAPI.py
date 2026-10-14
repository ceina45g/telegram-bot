#!/usr/bin/env python
import logging
import json
from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ==================== 設定 ====================
TOKEN = "7844559948:AAED2hkAOcLc2CqG_malaH3DqUMhpa5JWu0"
PORT = 8001

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def get_ngrok_url():
    """從 ngrok 本地 API 自動獲取公網網址"""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get("http://127.0.0.1:4040/api/tunnels") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['tunnels'][0]['public_url']
    except Exception:
        pass
    return None

# ==================== 機器人處理器 ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"收到 /start，來自 Chat ID: {update.effective_chat.id}")
    await update.message.reply_text("👋 你好！我是使用 Webhook 模式的機器人！")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("可用指令：/start, /help")

# ==================== 建立 Application ====================
ptb_app = Application.builder().token(TOKEN).build()
ptb_app.add_handler(CommandHandler("start", start))
ptb_app.add_handler(CommandHandler("help", help_command))

# ==================== FastAPI 應用 ====================
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """啟動時初始化 PTB 並自動偵測 Webhook"""
    try:
        logger.info("Lifespan 啟動: 正在初始化 PTB...")
        await ptb_app.initialize()
        await ptb_app.start()
        
        # 自動獲取並設定 Webhook
        url = await get_ngrok_url()
        if url:
            webhook_url = f"{url}/webhook"
            logger.info(f"自動偵測到 ngrok 網址: {webhook_url}")
            await ptb_app.bot.set_webhook(url=webhook_url)
            logger.info("Webhook 註冊成功！")
        else:
            logger.warning("未偵測到 ngrok 隧道，Webhook 可能無法運作。")
            
    except Exception as e:
        logger.error(f"啟動錯誤: {e}", exc_info=True)
    
    yield
    
    logger.info("正在關閉...")
    try:
        await ptb_app.stop()
        await ptb_app.shutdown()
    except Exception:
        pass

fastapi_app = FastAPI(lifespan=lifespan)

@fastapi_app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"請求: {request.method} {request.url.path}")
    response = await call_next(request)
    return response

@fastapi_app.post("/webhook")
async def webhook_endpoint(request: Request) -> Response:
    try:
        data = await request.json()
        update = Update.de_json(data, ptb_app.bot)
        await ptb_app.process_update(update)
        return Response(status_code=HTTPStatus.OK)
    except Exception as e:
        logger.error(f"Webhook 處理錯誤: {e}")
        return Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

@fastapi_app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(fastapi_app, host="0.0.0.0", port=PORT)
