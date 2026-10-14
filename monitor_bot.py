#!/usr/bin/env python3
import logging
import asyncio
import aiohttp
from datetime import datetime
from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI, Request, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ========== 設定 ==========
BOT_TOKEN = "8963675814:AAG1CcOhfyIvA5hj6gVrCZTjtKB8l3qLUwo"
CHECK_INTERVAL = 60
PORT = 8000

# 預設監控清單
monitor_targets = {
    "https://www.google.com": {"name": "Google", "last_status": True},
    "https://www.github.com": {"name": "GitHub", "last_status": True},
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== 工具函式 ==========
async def get_ngrok_url():
    """從 ngrok 本地 API 自動獲取公網網址"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://127.0.0.1:4040/api/tunnels") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['tunnels'][0]['public_url']
    except Exception:
        pass
    return None

async def check_url(session, url, name):
    try:
        async with session.get(url, timeout=10) as resp:
            return resp.status == 200, f"HTTP {resp.status}"
    except Exception as e:
        return False, str(e)[:50]

async def monitor_loop(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    chat_id = context.job.chat_id

    async with aiohttp.ClientSession() as session:
        for url, info in monitor_targets.items():
            name = info["name"]
            current_status, detail = await check_url(session, url, name)
            previous_status = info["last_status"]

            if current_status != previous_status:
                status_text = "✅ 恢復正常" if current_status else "❌ 發生異常"
                message = (
                    f"🔔 網站監控通知\n"
                    f"目標：{name} ({url})\n"
                    f"狀態：{status_text}\n"
                    f"詳情：{detail}\n"
                    f"時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                try:
                    await bot.send_message(chat_id=chat_id, text=message)
                except Exception as e:
                    logger.error(f"通知失敗: {e}")

                monitor_targets[url]["last_status"] = current_status
                logger.info(f"{name} 狀態變更: {current_status}")

# ========== 指令處理 ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    job_name = f"monitor_{chat_id}"
    
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    if not current_jobs:
        context.job_queue.run_repeating(
            monitor_loop,
            interval=CHECK_INTERVAL,
            first=5,
            name=job_name,
            chat_id=chat_id,
        )
        await update.message.reply_text(f"🚀 Webhook 監控已啟動！\n每 {CHECK_INTERVAL} 秒檢查一次。")
    else:
        await update.message.reply_text("⚠️ 監控正在運行中。")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📋 網站狀態清單：\n"
    for url, info in monitor_targets.items():
        status = "✅" if info["last_status"] else "❌"
        text += f"{status} {info['name']} - {url}\n"
    await update.message.reply_text(text)

# ========== 初始化 PTB ==========
ptb_app = Application.builder().token(BOT_TOKEN).build()
ptb_app.add_handler(CommandHandler("start", start))
ptb_app.add_handler(CommandHandler("status", status_cmd))

# ========== FastAPI 應用 ==========
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    logger.info("正在啟動 Webhook 機器人...")
    await ptb_app.initialize()
    await ptb_app.start()
    
    url = await get_ngrok_url()
    if url:
        webhook_url = f"{url}/webhook"
        logger.info(f"自動偵測 Webhook: {webhook_url}")
        await ptb_app.bot.set_webhook(url=webhook_url)
    
    yield
    
    logger.info("正在關閉...")
    await ptb_app.stop()
    await ptb_app.shutdown()

fastapi_app = FastAPI(lifespan=lifespan)

@fastapi_app.post("/webhook")
async def webhook_endpoint(request: Request) -> Response:
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(status_code=HTTPStatus.OK)

@fastapi_app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(fastapi_app, host="0.0.0.0", port=PORT)
