import os
import telebot

# 建議在 Render 的 Environment 頁面新增 TELEGRAM_BOT_TOKEN
# 若尚未設定環境變數，可先替換為字串 "YOUR_BOT_TOKEN_HERE"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "你好！機器人已成功在 Render 上線運作。")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, message.text)

if __name__ == "__main__":
    print("Telegram Bot 正在啟動並監聽訊息...")
    # non_stop=True 確保在遭遇短暫網路錯誤時會持續嘗試重連
    bot.infinity_polling()

