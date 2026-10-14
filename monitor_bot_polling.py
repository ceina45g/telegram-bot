import logging
import asyncio
import aiohttp
from datetime import datetime
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
BOT_TOKEN = "8963675814:AAG1CcOhfyIvA5hj6gVrCZTjtKB8l3qLUwo"          # 請替換
CHECK_INTERVAL = 60                   # 檢查間隔（秒）

# 預設監控清單
monitor_targets = {
    "https://www.google.com": {"name": "Google", "last_status": True},
    "https://www.github.com": {"name": "GitHub", "last_status": True},
}

# 日誌設定
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== 監控核心函式 ==========
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
                status_text = "✅ 正常" if current_status else "❌ 異常"
                message = (
                    f"🔔 監控通知\n"
                    f"目標：{name} ({url})\n"
                    f"狀態：{status_text}\n"
                    f"詳情：{detail}\n"
                    f"時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                try:
                    await bot.send_message(chat_id=chat_id, text=message)
                except Exception as e:
                    logger.error(f"發送通知失敗：{e}")

                monitor_targets[url]["last_status"] = current_status
                logger.info(f"{name} 狀態變更為 {current_status}")

# ========== 機器人指令 ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    logger.info(f"收到 /start 指令，來自 Chat ID: {chat_id}")

    job_name = f"monitor_{chat_id}"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    if not current_jobs:
        context.job_queue.run_repeating(
            monitor_loop,
            interval=CHECK_INTERVAL,
            first=10,
            name=job_name,
            chat_id=chat_id,
        )
        await update.message.reply_text(
            f"✅ 監控已啟動！每 {CHECK_INTERVAL} 秒檢查一次。\n"
            "目前監控清單：\n" + "\n".join(f"- {v['name']} ({k})" for k, v in monitor_targets.items())
        )
    else:
        await update.message.reply_text("⚠️ 監控已經在執行中。")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    job_name = f"monitor_{chat_id}"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()
    await update.message.reply_text("🛑 監控已停止。")

async def list_targets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not monitor_targets:
        await update.message.reply_text("📭 目前沒有任何監控目標。")
        return
    text = "📋 監控目標清單：\n"
    for url, info in monitor_targets.items():
        status = "✅" if info["last_status"] else "❌"
        text += f"{status} {info['name']} - {url}\n"
    await update.message.reply_text(text)

async def monitor_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text if update.message else "非文字訊息"
    logger.info(f"偵測到訊息 - 來自: {user.first_name} (ID: {user.id}), 內容: {text}")

# ========== 錯誤處理 ==========
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"更新 {update} 造成錯誤 {context.error}")

# ========== 主程式 ==========
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # 註冊指令
    app.add_handler(MessageHandler(filters.ALL, monitor_debug), group=-1)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("list", list_targets))

    app.add_error_handler(error_handler)

    logger.info("機器人啟動中...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
