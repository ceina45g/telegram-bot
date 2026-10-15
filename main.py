
# 從環境變數讀取 Bot Token


def send_welcome(message):
    bot.reply_to(message, "你好！我已經成功在 Render 上永久運行了！")

@bot.message_handler(func=lambda msg: True)
def echo_all(message):
    bot.reply_to(message, f"你說了：{message.text}")

if __name__ == "__main__":
    print("Telegram Bot 開始運行...")
    # 關鍵：使用 infinity_polling 讓程式不會中斷
    bot.infinity_polling()
