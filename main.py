
# 從環境變數讀取 Bot Token






    bot.reply_to(message, f"你說了：{message.text}")

if __name__ == "__main__":
    print("Telegram Bot 開始運行...")
    # 關鍵：使用 infinity_polling 讓程式不會中斷
    bot.infinity_polling()
