import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# 啟用日誌
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 把你的 Bot Token 放在這裡
BOT_TOKEN = "7844559948:AAED2hkAOcLc2CqG_malaH3DqUMhpa5JWu0"

# ---------- 命令處理函式 ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理 /start 命令"""
    user = update.effective_user
    welcome_text = (
        f"👋 嗨 {user.first_name}！\n\n"
        "歡迎使用我的機器人！\n"
        "以下是可用的指令：\n"
        "/start - 顯示歡迎訊息\n"
        "/help - 顯示幫助\n"
        "/about - 關於這個機器人\n"
        "/menu - 顯示選單"
    )
    await update.message.reply_text(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理 /help 命令"""
    help_text = (
        "📖 幫助中心\n\n"
        "基本指令：\n"
        "/start - 開始使用\n"
        "/help - 顯示此幫助\n"
        "/about - 關於機器人\n"
        "/menu - 互動選單\n\n"
        "你也可以直接傳送訊息給我，我會回覆你！"
    )
    await update.message.reply_text(help_text)


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理 /about 命令"""
    about_text = (
        "🤖 關於這個機器人\n\n"
        "版本: 1.0.0\n"
        "使用 python-telegram-bot v20.x\n"
        "Powered by Python 🐍"
    )
    await update.message.reply_text(about_text)


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """顯示互動選單"""
    keyboard = [
        [
            InlineKeyboardButton("📊 今日天氣", callback_data="weather"),
            InlineKeyboardButton("📰 最新消息", callback_data="news"),
        ],
        [
            InlineKeyboardButton("🎲 隨機數字", callback_data="random"),
            InlineKeyboardButton("📝 關於", callback_data="about"),
        ],
        [
            InlineKeyboardButton("❌ 關閉選單", callback_data="close"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("請選擇一個選項：", reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理按鈕點擊事件"""
    query = update.callback_query
    await query.answer()  # 回覆按鈕點擊（避免超時）

    data = query.data
    responses = {
        "weather": "🌤️ 今天天氣晴朗，溫度 28°C",
        "news": "📰 今日頭條：Python 成為最受歡迎的程式語言！",
        "random": f"🎲 你的隨機數字是：{__import__('random').randint(1, 100)}",
        "about": "🤖 這是一個用 python-telegram-bot 建立的機器人",
        "close": "✅ 選單已關閉",
    }

    text = responses.get(data, "未知選項")
    await query.edit_message_text(text=text)


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """回覆使用者傳送的訊息"""
    user_message = update.message.text
    await update.message.reply_text(f"你說了：{user_message}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理錯誤"""
    logger.error(f"Update {update} caused error {context.error}")


# ---------- 主程式 ----------

def main():
    """啟動機器人"""
    # 建立應用程式
    application = Application.builder().token(BOT_TOKEN).build()

    # 註冊命令處理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("menu", menu))

    # 註冊按鈕回調處理器
    application.add_handler(CallbackQueryHandler(button_callback))

    # 註冊訊息處理器（處理一般文字訊息）
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # 註冊錯誤處理器
    application.add_error_handler(error_handler)

    # 啟動機器人
    print("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
