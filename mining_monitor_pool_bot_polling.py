#!/usr/bin/env python3
"""
NerdMiner 礦池監控 Telegram 機器人
支援 NerdMiners Pool (BTC)
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
    ContextTypes,
)

# ==================== 設定區域 ====================
CONFIG = {
    "TELEGRAM_BOT_TOKEN": "8874121666:AAGSCdYZJG84ffR2xjglsBYjw11zXzsEQXU",
    "CHAT_ID": "1418292007",                               # 請在啟動後輸入 /myid 取得並回來更新此處
    "MINER_WALLET": "13NvdBs5dFarwR4TK373BMM4sEheAXbewB",
    "POOL_TYPE": "nerdminer",                    # 支援 "nerdminer", "ethermine", "flexpool"
    "CHECK_INTERVAL": 60,                        # 檢查間隔（秒）
    "WORKER_THRESHOLD": 1,                       # worker 數量低於此值時發出警報
}

# 日誌設定
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# 用於記錄上一次的狀態，避免重複通知
last_state: Dict[str, Any] = {
    "workers_count": 0,
    "best_share": 0.0,
    "last_check_time": None
}

# ==================== 工具函式 ====================
def parse_hashrate(hr_str) -> float:
    """將帶單位的算力字串 (如 35.6K, 1.2M) 轉換為數值"""
    if isinstance(hr_str, (int, float)):
        return float(hr_str)
    
    hr_str = str(hr_str).upper().strip()
    match = re.match(r"([\d\.]+)([KMG]?)", hr_str)
    if not match:
        return 0.0
    
    value, unit = match.groups()
    value = float(value)
    
    multipliers = {"K": 1, "M": 1000, "G": 1000000} # 以 K 為基準單位
    return value * multipliers.get(unit, 1)

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
                    if resp.status != 200:
                        return None
                    # 礦池回傳 mimetype 為 application/octet-stream，需強制解析 JSON
                    return await resp.json(content_type=None)
            # 這裡可以保留 ethermine/flexpool 的擴充空間
            return None
        except Exception as e:
            logger.error(f"獲取礦池資料失敗: {e}")
            return None

# ==================== 通知邏輯 ====================
class MiningNotifier:
    def __init__(self, bot, chat_id: str):
        self.bot = bot
        self.chat_id = chat_id
        self.worker_threshold = CONFIG["WORKER_THRESHOLD"]

    async def check_and_notify(self, stats: Dict) -> None:
        if not stats or self.chat_id == "0":
            return

        # NerdMiner 資料解析
        current_workers = int(stats.get("workers", 0))
        best_share = float(stats.get("bestshare", 0.0))
        hashrate_1d = parse_hashrate(stats.get("hashrate1d", 0))

        notifications = []

        # 1. 檢查 worker 數量（離線警示）
        if current_workers < self.worker_threshold:
            if last_state.get("workers_count", 0) >= self.worker_threshold:
                notifications.append(
                    f"⚠️ NerdMiner 離線警報！\n"
                    f"當前上線數量：{current_workers}\n"
                    f"警報閾值：{self.worker_threshold}"
                )
        elif current_workers > last_state.get("workers_count", 0) and last_state.get("last_check_time"):
             notifications.append(f"✅ Worker 已恢復上線！目前數量：{current_workers}")

        # 2. 檢查 Best Share 更新 (幸運值提醒)
        if best_share > last_state.get("best_share", 0.0):
            if last_state.get("best_share", 0.0) > 0:
                notifications.append(
                    f"🚀 刷出更高難度 Share！\n"
                    f"舊紀錄：{last_state['best_share']:.2f}\n"
                    f"新紀錄：{best_share:.2f}"
                )

        # 發送所有通知
        for msg in notifications:
            try:
                await self.bot.send_message(chat_id=self.chat_id, text=msg)
            except Exception as e:
                logger.error(f"發送通知失敗: {e}")

        # 更新最後狀態
        last_state.update({
            "workers_count": current_workers,
            "best_share": best_share,
            "hashrate_1d": hashrate_1d,
            "last_check_time": datetime.now()
        })

# ==================== Telegram 指令 ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("📊 查看狀態", callback_data="status")],
        [InlineKeyboardButton("⛏️ 錢包資訊", callback_data="info")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🤖 NerdMiner 監控機器人\n\n"
        "可用指令：\n"
        "/status - 查看當前算力與 Share 狀況\n"
        "/myid - 取得你的 Chat ID (用於設定通知)\n"
        "/help - 顯示幫助",
        reply_markup=reply_markup,
    )

async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"您的 Chat ID 為：`{chat_id}`\n請將此數字填入程式碼的 CONFIG['CHAT_ID'] 中。", parse_mode="Markdown")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    stats = context.bot_data.get("last_stats")
    if not stats:
        await update.message.reply_text("⏳ 正在獲取礦池資料...")
        return

    msg = (
        f"📊 NerdMiner 狀態報告\n"
        f"📅 更新時間：{datetime.now().strftime('%H:%M:%S')}\n"
        f"─────────────────\n"
        f"🖥️ 上線 Worker：{stats.get('workers', 0)}\n"
        f"⚡ 24H 算力：{stats.get('hashrate1d', '0')}\n"
        f"🍀 Best Share：{float(stats.get('bestshare', 0)):.4f}\n"
        f"🏆 Best Ever：{float(stats.get('bestever', 0)):.4f}\n"
        f"📈 總 Shares：{stats.get('shares', 0)}"
    )
    await update.message.reply_text(msg)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("/start, /status, /myid")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.data == "status":
        await status(update, context)

# ==================== 定時監控任務 ====================
async def monitor_task(context: ContextTypes.DEFAULT_TYPE) -> None:
    client = context.bot_data.get("pool_client")
    notifier = context.bot_data.get("notifier")

    async with aiohttp.ClientSession() as session:
        stats = await client.fetch_stats(session)
        if stats:
            context.bot_data["last_stats"] = stats
            await notifier.check_and_notify(stats)

# ==================== 主程式 ====================
def main() -> None:
    if CONFIG["TELEGRAM_BOT_TOKEN"] == "YOUR_BOT_TOKEN_HERE":
        print("Error: TOKEN NOT SET")
        sys.exit(1)

    app = Application.builder().token(CONFIG["TELEGRAM_BOT_TOKEN"]).build()

    client = PoolAPIClient(CONFIG["POOL_TYPE"], CONFIG["MINER_WALLET"])
    notifier = MiningNotifier(app.bot, CONFIG["CHAT_ID"])

    app.bot_data["pool_client"] = client
    app.bot_data["notifier"] = notifier

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("myid", get_my_id))
    app.add_handler(CallbackQueryHandler(button_callback))

    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(monitor_task, interval=CONFIG["CHECK_INTERVAL"], first=5)

    logger.info("NerdMiner Monitor Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
