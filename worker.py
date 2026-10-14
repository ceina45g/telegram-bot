import socket
import json
import time
import ssl
import requests
import sys
from config import CONFIG

# 設定標準輸出為 UTF-8，避免 Windows CP950 編碼錯誤
if sys.stdout.encoding != 'utf-8':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except Exception:
        pass

# 強制輸出立即刷新
def log(msg):
    timestamp = time.strftime("%H:%M:%S")
    try:
        # 移除可能導致 cp950 崩潰的特殊字元
        clean_msg = msg.replace("✅", "[OK]").replace("❌", "[ERR]").replace("🚀", "[START]").replace("🤖", "[BOT]").replace("⚠️", "[WARN]")
        print(f"[{timestamp}] {clean_msg}", flush=True)
    except Exception:
        try:
            safe_msg = msg.encode('ascii', 'ignore').decode('ascii')
            print(f"[{timestamp}] [ENCODE_ERR] {safe_msg}", flush=True)
        except:
            pass

# ================= 設定區 =================
# 根據用戶要求，僅使用官方備用池
POOL_SERVERS = [
    ("pool.nerdminer.io", 3333, "官方備用池"),
]

# 預設使用第一個
POOL_HOST = POOL_SERVERS[0][0]
POOL_PORT = POOL_SERVERS[0][1]

# 從 config.py 讀取設定
WALLET_ADDRESS = CONFIG.get("MINER_WALLET", "13NvdBs5dFarwR4TK373BMM4sEheAXbewB")
BOT_TOKEN = CONFIG.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = CONFIG.get("CHAT_ID")

# 自訂礦工名稱
WORKER_NAME = "nerdminer_py"
FULL_WORKER = f"{WALLET_ADDRESS.strip()}.{WORKER_NAME}"

# 是否使用 SSL
USE_SSL = False
# =========================================

def send_telegram_msg(message):
    """發送 Telegram 通知"""
    if not BOT_TOKEN or not CHAT_ID:
        log("[WARN] Telegram 設定不完整，跳過通知。")
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message}
        log(f"[DEBUG] 正在發送 Telegram 通知: {message[:20]}...")
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code != 200:
            log(f"[WARN] Telegram API 回傳錯誤: {res.text}")
    except Exception as e:
        log(f"[WARN] Telegram 通知發送失敗: {e}")

class StratumClient:
    def __init__(self, servers, worker, use_ssl=False):
        self.servers = servers
        self.worker = worker
        self.use_ssl = use_ssl
        self.host = None
        self.port = None
        self.sock = None
        self.buffer = b""
        self.last_err_time = 0

    def connect(self):
        for host, port, desc in self.servers:
            log(f"正在連線到 {desc} ({host}:{port}) ...")
            self.host = host
            self.port = port
            self.buffer = b""
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(15)
                self.sock.connect((self.host, self.port))
                if self.use_ssl:
                    context = ssl.create_default_context()
                    self.sock = context.wrap_socket(self.sock, server_hostname=self.host)
                log(f"連線成功 ({desc})")
                return True
            except Exception as e:
                log(f"連線 {desc} 失敗: {e}")
                continue
        
        err_msg = "所有礦池連線均失敗。請檢查網路或 3333 埠位是否被封鎖。"
        log(err_msg)
        if time.time() - self.last_err_time > 300:
            send_telegram_msg(err_msg)
            self.last_err_time = time.time()
        return False

    def send(self, msg_dict):
        msg = json.dumps(msg_dict) + "\n"
        log(f"[SEND] {msg.strip()}")
        self.sock.sendall(msg.encode())

    def receive(self, timeout=30):
        self.sock.settimeout(timeout)
        try:
            while True:
                if b"\n" in self.buffer:
                    line, self.buffer = self.buffer.split(b"\n", 1)
                    return json.loads(line.decode())
                
                data = self.sock.recv(4096)
                if not data:
                    log("礦池中斷連線 (recv 0)")
                    return None
                self.buffer += data
        except socket.timeout:
            log("接收訊息超時 (timeout)")
            return None
        except Exception as e:
            log(f"接收訊息錯誤: {e}")
            return None

    def subscribe(self):
        msg_id = 1
        log("發送 Subscribe 請求...")
        self.send({"id": msg_id, "method": "mining.subscribe", "params": []})
        
        for _ in range(10):
            resp = self.receive(timeout=10)
            if not resp: 
                err_msg = "Subscribe 失敗: 礦池無回應 (超時)"
                log(err_msg)
                send_telegram_msg(err_msg)
                return False
            
            if resp.get("id") == msg_id:
                if resp.get("error"):
                    err_txt = f"Subscribe 失敗: {resp['error']}"
                    log(err_txt)
                    send_telegram_msg(err_txt)
                    return False
                log(f"Subscribe 成功: {resp}")
                return True
            log(f"忽略非同步訊息: {resp.get('method')}")
        return False

    def authorize(self):
        msg_id = 2
        log(f"發送 Authorize 請求 ({self.worker})...")
        self.send({"id": msg_id, "method": "mining.authorize", "params": [self.worker, "x"]})
        
        for _ in range(10):
            resp = self.receive(timeout=10)
            if not resp: 
                err_msg = "Authorize 失敗: 礦池無回應 (超時)"
                log(err_msg)
                send_telegram_msg(err_msg)
                return False
            
            if resp.get("id") == msg_id:
                if resp.get("result") is True:
                    log(f"Authorize 成功: {self.worker}")
                    return True
                err_txt = f"Authorize 失敗: {resp.get('error')}"
                log(err_txt)
                send_telegram_msg(err_txt)
                return False
            log(f"忽略非同步訊息: {resp.get('method')}")
        return False

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None

def main():
    log("=" * 50)
    log("NerdMiner Python Stratum 客戶端")
    log(f"首選礦池: {POOL_HOST}:{POOL_PORT}")
    log(f"礦工: {FULL_WORKER}")
    log("=" * 50)

    # 啟動測試通知
    send_telegram_msg("NerdMiner 腳本已啟動，正在嘗試登入礦池...")

    client = StratumClient(POOL_SERVERS, FULL_WORKER, USE_SSL)

    while True:
        if not client.connect():
            time.sleep(10)
            continue

        if not client.subscribe():
            log("Subscribe 階段失敗，準備重試...")
            client.close()
            time.sleep(10)
            continue

        if not client.authorize():
            log("Authorize 階段失敗，準備重試...")
            client.close()
            time.sleep(10)
            continue

        # 成功上線通知
        online_msg = f"NerdMiner 正式上線！\n礦池: {client.host}:{client.port}\n礦工: {FULL_WORKER}"
        log(f"\n{online_msg}\n")
        send_telegram_msg(online_msg)

        try:
            while True:
                msg = client.receive(timeout=60)
                if msg is None:
                    log("超過 60 秒未收到訊息，發送 ping...")
                    client.send({"id": 99, "method": "mining.ping", "params": []})
                    continue

                if "method" in msg:
                    method = msg["method"]
                    if method == "mining.notify":
                        params = msg.get("params", [])
                        if len(params) >= 9:
                            log(f"[JOB] 收到新任務! Job ID: {params[0]}")
                    elif method == "mining.set_difficulty":
                        log(f"難度更新: {msg.get('params')}")
                elif "result" in msg:
                    log(f"[PONG/RESULT] {msg}")

        except KeyboardInterrupt:
            log("使用者中斷程式。")
            client.close()
            break
        except Exception as e:
            err_text = f"[WARN] NerdMiner 斷開連線: {e}"
            log(err_text)
            send_telegram_msg(err_text)
        finally:
            client.close()
        
        log("等待 10 秒後重新連線...")
        time.sleep(10)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"程式發生致命錯誤: {e}")
        import traceback
        traceback.print_exc()
