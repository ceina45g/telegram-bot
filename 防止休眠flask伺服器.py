import os
import threading
import time
import requests
from flask import Flask, jsonify
from datetime import datetime

# ============================================================
# 環境變數設定（部署時請透過平台設定這些值）
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7844559948:AAED2hkAOcLc2CqG_malaH3DqUMhpa5JWu0")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1418292007")
BTC_ADDRESS = os.getenv("BTC_ADDRESS", "13NvdBs5dFarwR4TK373BMM4sEheAXbewB")
POOL_API_URL = os.getenv(
    "POOL_API_URL",
    f"https://pool.nerdminers.io/users/{BTC_ADDRESS}"
)
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # 秒
ALERT_HASHRATE_THRESHOLD = float(os.getenv("ALERT_HASHRATE_THRESHOLD", "0"))
ALERT_WORKERS_THRESHOLD = int(os.getenv("ALERT_WORKERS_THRESHOLD", "1"))
KEEPALIVE_INTERVAL = int(os.getenv("KEEPALIVE_INTERVAL", "60"))  # 秒
PORT = int(os.getenv("PORT", "10000"))

# ============================================================
# Flask App
# ============================================================
app = Flask(__name__)

@app.route("/")
def index():
    return jsonify({
        "status": "running",
        "service": "NerdMiner Monitor Bot",
        "time": datetime.utcnow().isoformat()
    })

@app.route("/alive")
def alive():
    """Keep-alive 端點，回傳存活狀態"""
    return "I am alive!", 200

@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200

# ============================================================
# Telegram Bot 發送訊息（簡易 HTTP 方式，無需完整 bot 框架）
# ============================================================
def send_telegram_message(text: str):
    """透過 Telegram Bot API 發送訊息"""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN":
        print("[WARN] Telegram Bot Token 未設定，跳過發送")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"[ERROR] Telegram 發送失敗: {resp.text}")
    except Exception as e:
        print(f"[ERROR] Telegram 發送異常: {e}")

# ============================================================
# 礦池監控邏輯
# ============================================================
def fetch_pool_stats():
    """從 NerdMiner 礦池 API 取得統計數據"""
    try:
        resp = requests.get(POOL_API_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 無法取得礦池數據: {e}")
        return None
    except ValueError as e:
        print(f"[ERROR] JSON 解析失敗: {e}")
        return None

def parse_hashrate(value) -> float:
    """解析帶有 K/M 後綴的算力字串"""
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return 0.0
    value = value.strip().upper()
    multipliers = {"K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12}
    for suffix, mult in multipliers.items():
        if value.endswith(suffix):
            try:
                return float(value[:-1]) * mult
            except ValueError:
                return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0

def format_hashrate(value: float) -> str:
    """格式化算力輸出"""
    if value >= 1e12:
        return f"{value/1e12:.2f} TH/s"
    elif value >= 1e9:
        return f"{value/1e9:.2f} GH/s"
    elif value >= 1e6:
        return f"{value/1e6:.2f} MH/s"
    elif value >= 1e3:
        return f"{value/1e3:.2f} KH/s"
    return f"{value:.2f} H/s"

def build_stats_message(data: dict) -> str:
    """將礦池數據格式化為 Telegram 訊息"""
    # 相容 public-pool 與 ckpool 兩種格式
    workers_count = data.get("workersCount")
    if workers_count is None:
        workers_count = data.get("workers", 0)

    best_diff = data.get("bestDifficulty")
    if best_diff is None:
        best_diff = data.get("bestshare", 0)

    # 算力欄位：public-pool 用 hashRate，ckpool 用 hashrate1hr
    raw_hashrate = data.get("hashRate")
    if raw_hashrate is None:
        raw_hashrate = data.get("hashrate1hr", "0")

    hashrate = parse_hashrate(raw_hashrate)
    shares = data.get("shares", data.get("sharesTotal", "N/A"))

    msg = (
        f"📊 <b>NerdMiner 礦池狀態</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⛏ <b>算力</b>: {format_hashrate(hashrate)}\n"
        f"👷 <b>Worker 數量</b>: {workers_count}\n"
        f"🎯 <b>最佳難度</b>: {best_diff}\n"
        f"📦 <b>Shares</b>: {shares}\n"
        f"🕐 <b>更新時間</b>: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )
    return msg

def check_and_alert():
    """檢查礦池狀態，異常時發送警報"""
    data = fetch_pool_stats()
    if data is None:
        send_telegram_message(
            "🚨 <b>礦池監控警告</b>\n\n"
            f"無法連線至礦池 API：\n<code>{POOL_API_URL}</code>\n\n"
            "請檢查網路或礦池狀態。"
        )
        return

    workers_count = data.get("workersCount")
    if workers_count is None:
        workers_count = data.get("workers", 0)

    raw_hashrate = data.get("hashRate")
    if raw_hashrate is None:
        raw_hashrate = data.get("hashrate1hr", "0")
    hashrate = parse_hashrate(raw_hashrate)

    alerts = []

    if workers_count < ALERT_WORKERS_THRESHOLD:
        alerts.append(
            f"⚠️ Worker 數量異常：<b>{workers_count}</b>（閾值：{ALERT_WORKERS_THRESHOLD}）"
        )

    if hashrate <= ALERT_HASHRATE_THRESHOLD:
        alerts.append(
            f"⚠️ 算力過低：<b>{format_hashrate(hashrate)}</b>（閾值：{format_hashrate(ALERT_HASHRATE_THRESHOLD)}）"
        )

    if alerts:
        msg = (
            "🚨 <b>NerdMiner 警報</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            + "\n".join(alerts)
            + "\n\n"
            + build_stats_message(data)
        )
        send_telegram_message(msg)
        print(f"[ALERT] {alerts}")
    else:
        print(f"[OK] Worker={workers_count}, Hashrate={format_hashrate(hashrate)}")

def monitor_loop():
    """背景監控迴圈"""
    # 啟動時先發送一次上線通知
    send_telegram_message(
        "✅ <b>NerdMiner 監控機器人已上線</b>\n"
        f"🔄 檢查間隔：{CHECK_INTERVAL} 秒\n"
        f"📡 礦池 API：<code>{POOL_API_URL}</code>"
    )
    while True:
        try:
            check_and_alert()
        except Exception as e:
            print(f"[ERROR] 監控迴圈異常: {e}")
        time.sleep(CHECK_INTERVAL)

def keepalive_loop():
    """內部自我 ping 迴圈，防止平台休眠"""
    url = f"http://127.0.0.1:{PORT}/alive"
    time.sleep(10)  # 等待 Flask 啟動
    while True:
        try:
            requests.get(url, timeout=5)
            print(f"[KEEPALIVE] Ping {url} OK")
        except Exception as e:
            print(f"[KEEPALIVE] Ping 失敗: {e}")
        time.sleep(KEEPALIVE_INTERVAL)

# ============================================================
# 啟動
# ============================================================
if __name__ == "__main__":
    # 啟動 Telegram 指令處理執行緒
    def telegram_command_loop():
        """簡易的 Telegram 指令輪詢"""
        offset = None
        base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
        while True:
            try:
                params = {"timeout": 30}
                if offset:
                    params["offset"] = offset
                resp = requests.get(
                    f"{base_url}/getUpdates", params=params, timeout=35
                )
                updates = resp.json().get("result", [])
                for update in updates:
                    offset = update["update_id"] + 1
                    msg = update.get("message", {})
                    text = msg.get("text", "")
                    chat_id = msg.get("chat", {}).get("id")

                    if text == "/start":
                        send_telegram_message(
                            "🤖 <b>NerdMiner 監控機器人</b>\n\n"
                            "可用指令：\n"
                            "/status — 查看當前礦池狀態\n"
                            "/help — 顯示說明"
                        )
                    elif text == "/status":
                        data = fetch_pool_stats()
                        if data:
                            send_telegram_message(build_stats_message(data))
                        else:
                            send_telegram_message("❌ 無法取得礦池數據，請稍後再試。")
                    elif text == "/help":
                        send_telegram_message(
                            "📖 <b>使用說明</b>\n\n"
                            "/status — 查詢礦池即時狀態\n"
                            "系統每 " + str(CHECK_INTERVAL) + " 秒自動檢查一次，\n"
                            "異常時會主動推送警報。"
                        )
            except Exception as e:
                print(f"[ERROR] Telegram 輪詢異常: {e}")
                time.sleep(5)

    # 啟動背景執行緒
    threading.Thread(target=monitor_loop, daemon=True).start()
    threading.Thread(target=keepalive_loop, daemon=True).start()
    threading.Thread(target=telegram_command_loop, daemon=True).start()

    print(f"[START] Flask 伺服器啟動於 port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)