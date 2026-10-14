#!/usr/bin/env python3
import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from http import HTTPStatus

import aiohttp
from fastapi import FastAPI, Request, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ==================== 設定區域 ====================
CONFIG = {
    "TELEGRAM_BOT_TOKEN": "7844559948:AAED2hkAOcLc2CqG_malaH3DqUMhpa5JWu0",
    "CHAT_ID": "1418292007",
    "MINER_WALLET": "13NvdBs5dFarwR4TK373BMM4sEheAXbewB",
    "POOL_TYPE": "nerdminer",
    "CHECK_INTERVAL": 60,
    "WORKER_THRESHOLD": 1,
}
PORT = 8000

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

last_state: Dict[str, Any] = {
    "workers_count": 0,
    "best_share": 0.0,
    "last_check_time": None
}

# ==================== 工具函式 ====================
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

def parse_hashrate(hr_str) -> float:
    if isinstance(hr_str, (int, float)): return float(hr_str)
    hr_str = str(hr_str).upper().strip()
    match = re.match(r"([\d\.]+)([KMG]?)", hr_str)
    if not match: return 0.0
    value, unit = match.groups()
    multipliers = {"K": 1, "M": 1000, "G": 1000000}
    return float(value) * multipliers.get(unit, 1)

# ==================== 礦池 API 客戶端 ====================
class PoolAPIClient:
    def __init__(self, pool_type: str, wallet: str):
        self.pool_type = pool_type.lower()
        self.wallet = wallet

    async def fetch_stats(self, session: aiohttp.ClientSession) -> Optional[Dict]:
        try:
            if self.pool_type == "nerdminer":
                url = f"https://pool.nerdminers.org/users/{self.wallet}"
                async with session.get(url, timeout=15) as resp:
                    if resp.status != 200: return None
                    return await resp.json(content_type=None)
            return None
        except Exception as e:
            logger.error(f"獲取礦池資料失敗: {e}")
            return None

# ==================== 通知邏輯 ====================
class MiningNotifier:
    def __init__(self, bot, chat_id: str):
        self.bot = bot
        self.chat_id = chat_id

    async def check_and_notify(self, stats: Dict) -> None:
        if not stats or self.chat_id == "0": return

        current_workers = int(stats.get("workers", 0))
        best_share = float(stats.get("bestshare", 0.0))
        notifications = []

        if current_workers < CONFIG["WORKER_THRESHOLD"]:
            if last_state.get("workers_count", 0) >= CONFIG["WORKER_THRESHOLD"]:
                notifications.append(f"⚠️ NerdMiner 離線警報！目前數量：{current_workers}")
        elif current_workers > last_state.get("workers_count", 0) and last_state.get("last_check_time"):
             notifications.append(f"✅ Worker 已恢復上線！目前數量：{current_workers}")

        if best_share > last_state.get("best_share", 0.0) and last_state.get("best_share", 0.0) > 0:
            notifications.append(f"🚀 刷出更高難度 Share！\n舊: {last_state['best_share']:.2f} -> 新: {best_share:.2f}")

        for msg in notifications:
            await self.bot.send_message(chat_id=self.chat_id, text=msg)

        last_state.update({
            "workers_count": current_workers,
            "best_share": best_share,
            "last_check_time": datetime.now()
        })

# ==================== Telegram 指令 ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🤖 礦池 Webhook 監控機器人已啟動！\n使用 /status 查看狀態。")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    stats = context.bot_data.get("last_stats")
    if not stats:
        await update.message.reply_text("⏳ 正在獲取資料...")
        return
    msg = (
        f"📊 NerdMiner 狀態報告\n"
        f"🖥️ Worker：{stats.get('workers', 0)}\n"
        f"⚡ 24H 算力：{stats.get('hashrate1d', '0')}\n"
        f"🍀 Best Share：{float(stats.get('bestshare', 0)):.4f}\n"
        f"🏆 Best Ever：{float(stats.get('bestever', 0)):.4f}"
    )
    await update.message.reply_text(msg)

# ==================== 定時任務與應用初始化 ====================
ptb_app = Application.builder().token(CONFIG["TELEGRAM_BOT_TOKEN"]).build()
ptb_app.add_handler(CommandHandler("start", start))
ptb_app.add_handler(CommandHandler("status", status))

async def monitor_task(context: ContextTypes.DEFAULT_TYPE) -> None:
    client = context.bot_data.get("pool_client")
    notifier = context.bot_data.get("notifier")
    async with aiohttp.ClientSession() as session:
        stats = await client.fetch_stats(session)
        if stats:
            context.bot_data["last_stats"] = stats
            await notifier.check_and_notify(stats)

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    logger.info("啟動 Webhook 機器人...")
    client = PoolAPIClient(CONFIG["POOL_TYPE"], CONFIG["MINER_WALLET"])
    notifier = MiningNotifier(ptb_app.bot, CONFIG["CHAT_ID"])
    ptb_app.bot_data["pool_client"] = client
    ptb_app.bot_data["notifier"] = notifier
    
    await ptb_app.initialize()
    await ptb_app.start()
    
    # 自動設定 Webhook
    base_url = await get_ngrok_url()
    if base_url:
        webhook_url = f"{base_url}/webhook"
        logger.info(f"設定 Webhook: {webhook_url}")
        await ptb_app.bot.set_webhook(url=webhook_url)
    
    # 啟動定時監控
    ptb_app.job_queue.run_repeating(monitor_task, interval=CONFIG["CHECK_INTERVAL"], first=5)
    
    yield
    logger.info("關閉中...")
    await ptb_app.stop()
    await ptb_app.shutdown()

fastapi_app = FastAPI(lifespan=lifespan)

@fastapi_app.post("/webhook")
async def webhook(request: Request) -> Response:
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
