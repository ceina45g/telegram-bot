import requests
import time

TOKEN = "7844559948:AAED2hkAOcLc2CqG_malaH3DqUMhpa5JWu0"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

def main():
    print("啟動純 Request 模式機器人 (不使用 PTB 框架)...")
    offset = 0
    
    # 啟動時先清空舊更新
    requests.get(f"{BASE_URL}/getUpdates?offset=-1")
    
    while True:
        try:
            url = f"{BASE_URL}/getUpdates?timeout=10&offset={offset}"
            response = requests.get(url).json()
            
            if response.get("ok") and response.get("result"):
                for update in response["result"]:
                    update_id = update["update_id"]
                    offset = update_id + 1
                    
                    if "message" in update:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"].get("text", "")
                        print(f"收到訊息 [Chat: {chat_id}]: {text}")
                        
                        # 回覆訊息
                        reply_url = f"{BASE_URL}/sendMessage"
                        requests.post(reply_url, data={
                            "chat_id": chat_id,
                            "text": f"純 Request 模式收到你的訊息了：{text}"
                        })
            
        except Exception as e:
            print(f"錯誤: {e}")
        
        time.sleep(1)

if __name__ == "__main__":
    main()
