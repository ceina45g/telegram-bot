import logging
import asyncio
import aiohttp
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ========== 設定 ==========
BOT_TOKEN = "7844559948:AAED2hkAOcLc2CqG_malaH3DqUMhpa5JWu0"
CHECK_INTERVAL = 60

# 監控目標
monitor_targets = {
    "https://www.google.com": {"name": "Google", "last_status": True, "keyword": "Google"},
}

# 日誌設定
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== 監控核心函式 ==========
async def check_url(session, url, name, keyword):
    """檢查單一 URL 是否包含特定關鍵字"""
    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status != 200:
                return False, f"HTTP {resp.status}"
            
            text = await resp.text()
            if keyword in text:
                return True, "關鍵字存在"
            else:
                return False, "關鍵字遺失"
    except asyncio.TimeoutError:
        return False, "連線超時"
    except Exception as e:
        return False, str(e)[:50]

async def monitor_loop(context: ContextTypes.DEFAULT_TYPE):
    """定時執行的監控任務"""
    bot = context.bot
    chat_id = context.job.chat_id

    async with aiohttp.ClientSession() as session:
        for url, info in monitor_targets.items():
            name = info["name"]
            keyword = info.get("keyword", "")
            current_status, detail = await check_url(session, url, name, keyword)
            previous_status = info["last_status"]

            if current_status != previous_status:
                status_text = "✅ 恢復正常" if current_status else "❌ 偵測到異常"
                message = (
                    f"🔔 關鍵字監控通知\n"
                    f"目標：{name}\n"
                    f"網址：{url}\n"
                    f"關鍵字：{keyword}\n"
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
        await update.message.reply_text("✅ 關鍵字監控已啟動！")
    else:
        await update.message.reply_text("⚠️ 監控已在運行中。")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    job_name = f"monitor_{chat_id}"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()
    await update.message.reply_text("🛑 監控已停止。")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    
    logger.info("Keyword Monitoring Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
