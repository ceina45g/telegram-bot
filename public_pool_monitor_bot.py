#!/usr/bin/env python3
"""
Public Pool Monitor Bot (NerdMiner Edition)
支援 pool.nerdminers.org
"""

import asyncio
import logging
import sys
import re
from datetime import datetime
from typing import Dict, Any, Optional

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ==================== 設定區域 ====================
CONFIG = {
    "TELEGRAM_BOT_TOKEN": "8701675905:AAFAvA8v76DvJFM6JpJp4EMtiuJtNu61h18",
    "CHAT_ID": "1418292007",
    "MINER_WALLET": "13NvdBs5dFarwR4TK373BMM4sEheAXbewB",
    "CHECK_INTERVAL": 60,
    "WORKER_THRESHOLD": 1,
}

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
def parse_hashrate(hr_str) -> float:
    if isinstance(hr_str, (int, float)):
        return float(hr_str)
    hr_str = str(hr_str).upper().strip()
    match = re.match(r"([\d\.]+)([KMG]?)", hr_str)
    if not match: return 0.0
    value, unit = match.groups()
    value = float(value)
    multipliers = {"K": 1, "M": 1000, "G": 1000000}
    return value * multipliers.get(unit, 1)

# ==================== 礦池 API 客戶端 ====================
class NerdMinerClient:
    def __init__(self, wallet: str):
        self.wallet = wallet
        self.url = f"https://pool.nerdminers.org/users/{self.wallet}"

    async def fetch_stats(self, session: aiohttp.ClientSession) -> Optional[Dict]:
        try:
            async with session.get(self.url, timeout=15) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
                return None
        except Exception as e:
            logger.error(f"Fetch failed: {e}")
            return None

# ==================== 通知邏輯 ====================
class Notifier:
    def __init__(self, bot, chat_id: str):
        self.bot = bot
        self.chat_id = chat_id

    async def notify(self, stats: Dict) -> None:
        if not stats or self.chat_id == "0": return

        current_workers = int(stats.get("workers", 0))
        best_share = float(stats.get("bestshare", 0.0))
        
        notifications = []
        if current_workers < CONFIG["WORKER_THRESHOLD"]:
            if last_state.get("workers_count", 0) >= CONFIG["WORKER_THRESHOLD"]:
                notifications.append(f"⚠️ NerdMiner 離線警報！當前 Worker: {current_workers}")
        elif current_workers > last_state.get("workers_count", 0) and last_state.get("last_check_time"):
            notifications.append(f"✅ Worker 已恢復上線！目前數量：{current_workers}")

        if best_share > last_state.get("best_share", 0.0) and last_state.get("best_share", 0.0) > 0:
            notifications.append(f"🚀 刷出更高難度 Share！\n舊: {last_state['best_share']:.2f} -> 新: {best_share:.2f}")

        for msg in notifications:
            try:
                await self.bot.send_message(chat_id=self.chat_id, text=msg)
            except Exception as e:
                logger.error(f"通知發送失敗: {e}")

        last_state.update({
            "workers_count": current_workers,
            "best_share": best_share,
            "last_check_time": datetime.now()
        })

# ==================== 指令與監控 ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"收到 /start 指令，來自 Chat ID: {update.effective_chat.id}")
    await update.message.reply_text("⛏️ NerdMiner 監控中...\n使用 /status 查看狀態")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"收到 /status 指令，來自 Chat ID: {update.effective_chat.id}")
    stats = context.bot_data.get("last_stats")
    if not stats:
        await update.message.reply_text("⌛ 獲取資料中，請稍候再試...")
        return
    msg = (
        f"📊 NerdMiner 狀態\n"
        f"🖥️ Worker: {stats.get('workers', 0)}\n"
        f"⚡ 24H Hashrate: {stats.get('hashrate1d', '0')}\n"
        f"🍀 Best Share: {float(stats.get('bestshare', 0)):.4f}\n"
        f"📈 Total Shares: {stats.get('shares', 0)}"
    )
    await update.message.reply_text(msg)

async def debug_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """日誌記錄所有收到的訊息以便偵錯"""
    user_text = update.message.text if update.message else "非文字訊息"
    logger.info(f"收到訊息 [Chat ID: {update.effective_chat.id}]: {user_text}")

async def monitor_task(context: ContextTypes.DEFAULT_TYPE):
    client = context.bot_data["client"]
    notifier = context.bot_data["notifier"]
    async with aiohttp.ClientSession() as session:
        stats = await client.fetch_stats(session)
        if stats:
            context.bot_data["last_stats"] = stats
            await notifier.notify(stats)

def main():
    logger.info("正在初始化機器人...")
    app = Application.builder().token(CONFIG["TELEGRAM_BOT_TOKEN"]).build()
    app.bot_data["client"] = NerdMinerClient(CONFIG["MINER_WALLET"])
    app.bot_data["notifier"] = Notifier(app.bot, CONFIG["CHAT_ID"])
    
    # 註冊偵錯 Handler (group=-1 優先處理)
    app.add_handler(MessageHandler(filters.ALL, debug_log), group=-1)
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    
    if app.job_queue:
        app.job_queue.run_repeating(monitor_task, interval=CONFIG["CHECK_INTERVAL"], first=5)
        logger.info("定時監控任務已啟動。")
    
    logger.info("機器人開始輪詢 (Polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
