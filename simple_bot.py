import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"收到訊息: {update.message.text}")
    await update.message.reply_text(f"回傳: {update.message.text}")

def main():
    app = Application.builder().token("7844559948:AAED2hkAOcLc2CqG_malaH3DqUMhpa5JWu0").build()
    app.add_handler(MessageHandler(filters.TEXT, echo))
    print("啟動極簡機器人...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
