import logging
import json
import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# 啟用日誌
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "7844559948:AAED2hkAOcLc2CqG_malaH3DqUMhpa5JWu0"

# 對話狀態
NAME, AGE, HOBBY = range(3)

# ---------- 命令處理 ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    now = datetime.now().strftime("%H:%M:%S")
    welcome = (
        f"👋 歡迎 {user.first_name}！(新啟動 @ {now})\n\n"
        "🔹 可用指令：\n"
        "/start - 重新開始\n"
        "/help - 取得幫助\n"
        "/menu - 開啟選單\n"
        "/survey - 開始問卷調查\n"
        "/time - 顯示目前時間\n"
        "/ping - 測試機器人是否在線\n"
        "/calc - 計算表達式 (例如: /calc 2+3)\n"
    )
    await update.message.reply_text(welcome)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 幫助中心\n\n"
        "基本指令：\n"
        "/start - 開始使用\n"
        "/help - 顯示此幫助\n"
        "/menu - 互動選單\n"
        "/survey - 問卷調查\n"
        "/time - 目前時間\n"
        "/ping - 測試連線\n"
        "/calc <表達式> - 計算數學\n\n"
        "💡 提示：點擊選單按鈕可以快速操作！"
    )
    await update.message.reply_text(help_text)


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 Pong！機器人運作正常！")


async def show_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await update.message.reply_text(f"🕐 目前時間：{now}")


async def calculate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        expression = " ".join(context.args)
        result = eval(expression)
        await update.message.reply_text(f"📐 {expression} = {result}")
    except Exception:
        await update.message.reply_text("❌ 請輸入正確的表達式，例如：/calc 2+3")


# ---------- 選單 ----------

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🕐 時間", callback_data="time")],
        [InlineKeyboardButton("🎲 骰子", callback_data="dice")],
        [InlineKeyboardButton("📊 狀態", callback_data="status")],
        [InlineKeyboardButton("❌ 關閉", callback_data="close_menu")],
    ]
    await update.message.reply_text(
        "📋 主選單：", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "time":
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await query.edit_message_text(f"🕐 {now}")
    elif data == "dice":
        await query.edit_message_text(f"🎲 擲出：{random.randint(1, 6)}")
    elif data == "status":
        await query.edit_message_text("✅ 機器人狀態：正常運作中")
    elif data == "close_menu":
        await query.edit_message_text("✅ 選單已關閉")
    else:
        await query.edit_message_text("未知選項")


# ---------- 問卷調查 (Conversation) ----------

async def survey_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 開始問卷調查！\n請問你的名字是什麼？")
    return NAME


async def survey_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text(f"你好 {update.message.text}！請問你幾歲？")
    return AGE


async def survey_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["age"] = update.message.text
    await update.message.reply_text("你的興趣是什麼？")
    return HOBBY


async def survey_hobby(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["hobby"] = update.message.text
    name = context.user_data["name"]
    age = context.user_data["age"]
    hobby = context.user_data["hobby"]

    summary = (
        f"✅ 問卷完成！\n\n"
        f"📌 姓名：{name}\n"
        f"📌 年齡：{age}\n"
        f"📌 興趣：{hobby}\n\n"
        "感謝你的參與！"
    )
    await update.message.reply_text(summary)
    return ConversationHandler.END


async def survey_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ 問卷已取消")
    return ConversationHandler.END


# ---------- 錯誤處理 ----------

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("⚠️ 發生錯誤，請稍後再試")


async def monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    logger.info(f"--- Incoming Message ---")
    logger.info(f"User: {user.first_name} (ID: {user.id})")
    logger.info(f"Chat ID: {chat.id}")
    logger.info(f"Text: {update.message.text if update.message else 'None'}")
    logger.info(f"------------------------")

# ---------- 主程式 ----------

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # 監控所有訊息
    application.add_handler(MessageHandler(filters.ALL, monitor), group=-1)

    # 命令
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("time", show_time))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("calc", calculate))

    # 選單回調
    application.add_handler(CallbackQueryHandler(menu_callback, pattern="^(time|dice|status|close_menu)$"))

    # 問卷對話
    survey_handler = ConversationHandler(
        entry_points=[CommandHandler("survey", survey_start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, survey_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, survey_age)],
            HOBBY: [MessageHandler(filters.TEXT & ~filters.COMMAND, survey_hobby)],
        },
        fallbacks=[CommandHandler("cancel", survey_cancel)],
    )
    application.add_handler(survey_handler)

    # 錯誤處理
    application.add_error_handler(error_handler)

    print("Robot started successfully! Press Ctrl+C to stop")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()