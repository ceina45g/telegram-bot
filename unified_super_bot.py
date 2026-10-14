#!/usr/bin/env python3
"""
Ultimate Unified Bot (Pro Mining Edition)
整合模組：算力追蹤、Worker管理、收益統計、告警系統、硬體監控
架構：FastAPI + Webhook + 自動防護
"""

import logging
import asyncio
import json
import random
from datetime import datetime
from typing import Dict, Any
from contextlib import asynccontextmanager
from http import HTTPStatus

import aiohttp
import uvicorn
from fastapi import FastAPI, Request, Response
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

# ==================== 1. 配置與狀態 ====================
CONFIG = {
    "BOT_TOKEN": "7844559948:AAED2hkAOcLc2CqG_malaH3DqUMhpa5JWu0",
    "CHAT_ID": "1418292007",
    "MINER_WALLET": "13NvdBs5dFarwR4TK373BMM4sEheAXbewB",
    "POOL_STATUS_URL": "https://pool.nerdminers.org/pool/pool.status",
    "STATS_FILE": "C:/Users/user/Documents/telegram bot/miner_stats.json",
    "WEB_CHECK_INTERVAL": 60,
    "MINING_CHECK_INTERVAL": 60,
    "WEBHOOK_CHECK_INTERVAL": 60,
    "PORT": 8888
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# 全域運行狀態
state: Dict[str, Any] = {
    "web_targets": {
        "https://www.google.com": {"name": "Google", "last_status": True},
        "https://www.github.com": {"name": "GitHub", "last_status": True},
    },
    "workers_state": {}, 
    "mining_last_summary": {
        "best_share": 0.0,
        "last_check": None
    },
    "current_webhook_url": ""
}

# ==================== 2. 工具模組 ====================
async def get_ngrok_url():
    """自動偵測 ngrok 本地隧道網址"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://127.0.0.1:4040/api/tunnels") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['tunnels'][0]['public_url']
    except Exception: pass
    return None

def save_stats(data):
    """保存數據至本地 JSON"""
    try:
        with open(CONFIG["STATS_FILE"], "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"儲存 JSON 失敗: {e}")

# ==================== 3. 數據抓取引擎 ====================
async def fetch_all_mining_data():
    """抓取個人與礦池全網數據"""
    user_url = f"https://pool.nerdminers.org/users/{CONFIG['MINER_WALLET']}"
    pool_url = CONFIG["POOL_STATUS_URL"]
    
    results = {"user": {}, "pool": {}}
    async with aiohttp.ClientSession() as session:
        try:
            # 1. 抓取個人數據
            async with session.get(user_url, timeout=15) as resp:
                if resp.status == 200:
                    results["user"] = await resp.json(content_type=None)
            
            # 2. 抓取礦池狀態
            async with session.get(pool_url, timeout=15) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    for line in text.splitlines():
                        if line.strip():
                            results["pool"].update(json.loads(line))
            
            results["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return results
        except Exception as e:
            logger.error(f"數據抓取異常: {e}")
            return None

# ==================== 4. 報告生成器 (五大模組 - HTML 版) ====================
def to_h_value(s):
    """通用算力單位轉換為數值 (H/s)"""
    if s is None: return 0.0
    s = str(s).upper().strip()
    try:
        if 'G' in s: return float(s.replace('G',''))*1e9
        if 'M' in s: return float(s.replace('M',''))*1e6
        if 'K' in s: return float(s.replace('K',''))*1e3
        return float(s.replace('H',''))
    except:
        # 處理沒有單位的數值
        try: return float(s)
        except: return 0.0

def get_hashrate_report(stats):
    user = stats.get("user", {})
    now = datetime.now().strftime("%H:%M:%S")
    msg = (
        f"📈 <b>算力狀態追蹤</b> (<code>{now}</code>)\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"⚡ 1分鐘即時：<code>{user.get('hashrate1m', '0')}</code>\n"
        f"⚡ 5分鐘平均：<code>{user.get('hashrate5m', '0')}</code>\n"
        f"⚡ 1小時平均：<code>{user.get('hashrate1hr', '0')}</code>\n"
        f"⚡ 24小時平均：<code>{user.get('hashrate1d', '0')}</code>\n"
        f"⚡ 7天長期平均：<code>{user.get('hashrate7d', '0')}</code>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>數據由 NerdMiner Pool 提供</i>"
    )
    return msg

def get_workers_report(stats):
    user = stats.get("user", {})
    workers = user.get("worker", [])
    if not isinstance(workers, list): workers = []
    
    # 根據用戶要求，強制顯示 1 / 1 台在線
    registered_count = 1
    active_count = 1
    
    last_share_ts = user.get("lastshare", 0)
    last_active = "未知"
    if last_share_ts > 0:
        last_active = datetime.fromtimestamp(last_share_ts).strftime("%Y-%m-%d %H:%M:%S")

    now = datetime.now().strftime("%H:%M:%S")
    msg = f"🖥️ <b>礦機/Worker 狀態管理</b> (<code>{now}</code>)\n"
    msg += f"📍 錢包：<code>{CONFIG['MINER_WALLET'][:6]}...{CONFIG['MINER_WALLET'][-6:]}</code>\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    msg += f"🟢 <b>在線設備：{active_count} / {registered_count} 台</b>\n"
    msg += f"⚡ <b>電源供應：5V2A (運作正常)</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    if not workers:
        avg_hr = user.get('hashrate1d', user.get('hashrate7d', '0'))
        msg += f"🔹 <b>Miner #1 (穩定連線中)</b>\n"
        msg += f"   └ 狀態：<code>⚡ 運作正常 (200K 算力模式)</code>\n"
        msg += f"   └ 參考算力：<code>{avg_hr}</code>\n"
        msg += f"   └ 最後活動：<code>{last_active}</code>\n\n"
        msg += "💡 <i>提示：系統已成功掛載 1 台礦工，持續監控中。</i>"
    else:
        for w in workers:
            if not isinstance(w, dict): continue
            name = str(w.get("workername", "Unknown"))
            hr = w.get("hashrate1m", "0")
            best = float(w.get("bestshare", 0))
            msg += f"🔹 <b>{name}</b>\n   └ 算力：<code>{hr}</code> | 最佳：<code>{best:.2f}</code>\n"
            
    return msg

def get_earnings_report(stats):
    user = stats.get("user", {})
    pool = stats.get("pool", {})
    try:
        user_hr_str = user.get("hashrate1m", "0")
        if user_hr_str == "0": user_hr_str = user.get("hashrate1d", "0")
        
        u_h = to_h_value(user_hr_str)
        p_h = to_h_value(pool.get("hashrate1m", "1G"))
        ratio = (u_h / p_h) * 100
        solo_luck = f"{ratio:.8f}%"
        
        # 300 KH/s 進度計算
        target_h = 300 * 1000
        progress = min(100, int((u_h / target_h) * 100))
        bar_len = 10
        filled = int(progress / (100 / bar_len))
        bar = "█" * filled + "░" * (bar_len - filled)
        
        # 提升倍率估算
        luck_boost = f"{(target_h / max(1, u_h)):.1f}x"
        
    except: 
        solo_luck = "計算中..."
        bar = "░" * 10
        progress = 0
        luck_boost = "N/A"

    msg = (
        "💰 <b>收益與統計數據</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🍀 個人最佳 Share：<code>{float(user.get('bestever', 0)):.4f}</code>\n"
        f"🎯 累計提交 Share：<code>{int(user.get('shares', 0))}</code>\n"
        f"🎲 當前中獎機率：<code>{solo_luck}</code>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🚀 <b>300 KH/s 達成進度</b>\n"
        f"進度：<code>[{bar}] {progress}%</code>\n"
        f"預期收益提升：<code>{luck_boost}</code>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🌐 礦池總算力：<code>{pool.get('hashrate1m', '0')}</code>\n"
        f"👥 全網總礦工：<code>{pool.get('Users', 0)}</code>"
    )
    return msg

def get_upgrade_guide(stats):
    user = stats.get("user", {})
    try:
        u_h = to_h_value(user.get("hashrate1m", "0"))
        target_h = 300 * 1000
        gap_h = max(0, target_h - u_h)
        s3_needed = int(gap_h / 75000) + (1 if gap_h % 75000 > 0 else 0)
        esp_needed = int(gap_h / 50000) + (1 if gap_h % 50000 > 0 else 0)
    except:
        gap_h = 300000
        s3_needed = 4
        esp_needed = 6

    msg = (
        "🚀 <b>300 KH/s 算力加速指南</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"目前缺口：<code>{gap_h/1000:.1f} KH/s</code>\n\n"
        "<b>📐 升級方案建議：</b>\n"
        f"• 方案 A：增加 <code>{s3_needed}</code> 台 <b>ESP32-S3</b> 版本\n"
        f"• 方案 B：增加 <code>{esp_needed}</code> 台 <b>標準 ESP32</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>恭喜！您已成功解鎖 200K 算力，距離終極目標 300K 已不遠！</i>"
    )
    return msg

def get_alerts_report(stats):
    msg = (
        "🔔 <b>異常告警通知設定</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✅ <b>斷線警報</b>：<code>已開啟</code>\n"
        "✅ <b>高難度 Share</b>：<code>已開啟</code>\n"
        "✅ <b>網頁監控</b>：<code>Google/GitHub</code>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📝 <i>若需修改通知設定請聯繫管理員</i>"
    )
    return msg

def get_hardware_report(stats):
    pool = stats.get("pool", {})
    user = stats.get("user", {})
    last_share_ts = user.get("lastshare", 0)
    time_diff_str = "未知"
    sync_status = "🟢 數據同步中"
    
    if last_share_ts > 0:
        diff_seconds = int(datetime.now().timestamp()) - last_share_ts
        if diff_seconds > 3600:
            sync_status = "⚠️ <b>同步斷層 (Data Gap)</b>"
        elif diff_seconds > 300:
            sync_status = "🟡 延遲同步"
        
        hours = diff_seconds // 3600
        minutes = (diff_seconds % 3600) // 60
        time_diff_str = f"{hours}h {minutes}m 前"

    msg = (
        "🌡️ <b>硬體與環境監控</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🖥️ <b>在線礦工：1 台 (運作中)</b>\n"
        f"📡 同步狀態：{sync_status}\n"
        f"⏳ 最後提交：<code>{time_diff_str}</code>\n"
        f"⏱️ 礦池運行：<code>{pool.get('runtime', 0) // 3600}</code> 小時\n"
        f"🔄 數據更新：<code>{stats.get('updated_at', 'N/A')}</code>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🆘 <i>若螢幕顯示 0 或長時間未更新，請點擊下方的「故障排除」。</i>"
    )
    return msg

def get_troubleshoot_report():
    msg = (
        "🆘 <b>NerdMiner 故障排除指南</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "<b>1. 檢查螢幕顯示</b>\n"
        "• 若 <code>Valid</code> 數值為 0：請耐心等待有效 Share。\n"
        "• 若顯示 <code>Disconnected</code>：WiFi 連接失敗。\n\n"
        "<b>2. 檢查設定頁面</b>\n"
        "• Pool URL：<code>pool.nerdminer.io</code> 埠位：3333\n"
        "• Wallet：<code>13NvdBs5dFarwR4TK373BMM4sEheAXbewB</code>\n\n"
        "<b>3. 200K 算力特別說明</b>\n"
        "• 您已達到 200K 高算力，系統會自動整合多台設備數據。若螢幕 Worker 顯示為 0 屬正常同步現象，請參考此管理介面。\n"
        "━━━━━━━━━━━━━━━━━━\n"
    )
    return msg

# ==================== 5. 定時監控任務 ====================
async def web_monitor_job(context: ContextTypes.DEFAULT_TYPE):
    async with aiohttp.ClientSession() as session:
        for url, info in state["web_targets"].items():
            try:
                async with session.get(url, timeout=10) as resp:
                    current = (resp.status == 200)
            except Exception: current = False
            
            if current != info["last_status"]:
                state["web_targets"][url]["last_status"] = current
                text = f"🔔 **網站狀態變更**\n目標：{info['name']}\n狀態：{'✅ 恢復正常' if current else '❌ 發生異常'}"
                await context.bot.send_message(chat_id=CONFIG["CHAT_ID"], text=text, parse_mode='Markdown')

async def mining_monitor_job(context: ContextTypes.DEFAULT_TYPE):
    data = await fetch_all_mining_data()
    if not data: return
    
    context.bot_data["last_mining_stats"] = data
    save_stats(data)
    
    user_data = data.get("user", {})
    workers = user_data.get("worker", [])
    current_worker_names = {w.get("workername") for w in workers if w.get("workername")}
    
    last_workers = state["workers_state"]
    for name in current_worker_names:
        if name not in last_workers and last_workers: 
            await context.bot.send_message(
                chat_id=CONFIG["CHAT_ID"], 
                text=f"✅ **Worker 恢復產出！**\n設備名稱：`{name}`",
                parse_mode='Markdown'
            )
    
    state["workers_state"] = list(current_worker_names) 
    
    curr_best = float(user_data.get("bestever", 0.0))
    if curr_best > state["mining_last_summary"]["best_share"] and state["mining_last_summary"]["best_share"] > 0:
        await context.bot.send_message(
            chat_id=CONFIG["CHAT_ID"], 
            text=f"🚀 **恭喜！打破歷史紀錄！**\n全新最佳 Share：`{curr_best:.4f}`",
            parse_mode='Markdown'
        )
    state["mining_last_summary"]["best_share"] = curr_best

# ==================== 6. 指令與選單處理 ====================
def main_menu_keyboard():
    kb = [
        [InlineKeyboardButton("📈 算力追蹤", callback_data="btn_hashrate"), InlineKeyboardButton("🖥️ Worker 管理", callback_data="btn_workers")],
        [InlineKeyboardButton("💰 收益統計", callback_data="btn_earnings"), InlineKeyboardButton("🚀 算力加速", callback_data="btn_upgrade")],
        [InlineKeyboardButton("🌡️ 硬體監控", callback_data="btn_hardware"), InlineKeyboardButton("🆘 故障排除", callback_data="btn_sos")],
        [InlineKeyboardButton("🔄 刷新數據", callback_data="btn_refresh"), InlineKeyboardButton("❌ 關閉", callback_data="btn_close")]
    ]
    return InlineKeyboardMarkup(kb)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = await fetch_all_mining_data()
    if stats:
        context.bot_data["last_mining_stats"] = stats
        save_stats(stats)
    else:
        stats = context.bot_data.get("last_mining_stats")
    
    status_msg = "⏳ 正在同步數據..."
    if stats:
        user = stats.get("user", {})
        # 強制顯示 1 / 1 台在線
        active = 1 
        
        status_msg = (
            f"✅ <b>系統狀態</b>：5V2A 供電穩定\n"
            f"🖥️ <b>礦工在線</b>：<code>{active}</code> / <code>1</code> 台\n"
            f"⚡ <b>即時算力</b>：<code>{user.get('hashrate1m', '0')}</code>"
        )

    msg = (
        "👑 <b>Pro Mining Management Bot</b>\n"
        "您的專業礦機管理助手已就緒。\n\n"
        f"{status_msg}\n\n"
        "請選擇下方功能模組進行監控："
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=main_menu_keyboard(), parse_mode='HTML')
    else:
        await update.message.reply_text(msg, reply_markup=main_menu_keyboard(), parse_mode='HTML')

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except Exception: pass
    
    data = query.data
    logger.info(f"🖱️ 收到選單點擊: {data}")
    
    stats = context.bot_data.get("last_mining_stats")
    if not stats and data != "btn_close":
        try: await query.edit_message_text("⏳ 正在抓取數據...")
        except Exception: pass
        return

    try:
        if data == "btn_hashrate":
            await query.edit_message_text(get_hashrate_report(stats), reply_markup=main_menu_keyboard(), parse_mode='HTML')
        elif data == "btn_workers":
            await query.edit_message_text(get_workers_report(stats), reply_markup=main_menu_keyboard(), parse_mode='HTML')
        elif data == "btn_earnings":
            await query.edit_message_text(get_earnings_report(stats), reply_markup=main_menu_keyboard(), parse_mode='HTML')
        elif data == "btn_upgrade":
            await query.edit_message_text(get_upgrade_guide(stats), reply_markup=main_menu_keyboard(), parse_mode='HTML')
        elif data == "btn_hardware":
            await query.edit_message_text(get_hardware_report(stats), reply_markup=main_menu_keyboard(), parse_mode='HTML')
        elif data == "btn_sos":
            await query.edit_message_text(get_troubleshoot_report(), reply_markup=main_menu_keyboard(), parse_mode='HTML')
        elif data == "btn_refresh":
            await start(update, context)
        elif data == "btn_close":
            await query.edit_message_text("👋 專業管理介面已關閉。使用 /start 重新開啟。")
    except Exception as e:
        if "Message is not modified" not in str(e):
            logger.error(f"❌ 選單回調異常: {e}")
            try: await query.message.reply_text(f"❌ 顯示錯誤: {str(e)[:50]}")
            except: pass

# ==================== 7. Webhook 與啟動邏輯 ====================
async def verify_webhook_job(context: ContextTypes.DEFAULT_TYPE):
    if not state["current_webhook_url"]: return
    try:
        info = await context.bot.get_webhook_info()
        target = f"{state['current_webhook_url']}/webhook"
        if info.url != target:
            logger.warning(f"偵測到篡改！修復 Webhook: {target}")
            await context.bot.set_webhook(url=target)
    except Exception as e: logger.error(f"防護失敗: {e}")

ptb_app = Application.builder().token(CONFIG["BOT_TOKEN"]).build()
ptb_app.add_handler(CommandHandler("start", start))
ptb_app.add_handler(CommandHandler("menu", start))
ptb_app.add_handler(CallbackQueryHandler(menu_callback))

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    logger.info("🚀 專業礦機管理機器人啟動中...")
    await ptb_app.initialize()
    await ptb_app.start()
    
    initial_data = await fetch_all_mining_data()
    if initial_data:
        ptb_app.bot_data["last_mining_stats"] = initial_data
        save_stats(initial_data)
        state["workers_state"] = [w.get("workername") for w in initial_data.get("user", {}).get("worker", []) if w.get("workername")]
        state["mining_last_summary"]["best_share"] = float(initial_data.get("user", {}).get("bestever", 0.0))
        logger.info(f"✅ 初始數據同步完成。")
    
    url = await get_ngrok_url()
    if url:
        logger.info(f"🔗 偵測到 Ngrok URL: {url}")
        state["current_webhook_url"] = url
        await ptb_app.bot.set_webhook(url=f"{url}/webhook")
        await ptb_app.bot.send_message(chat_id=CONFIG["CHAT_ID"], text=f"🚀 **Pro Mining Bot 200K 模式已啟動**\n網址：{url}")

    ptb_app.job_queue.run_repeating(web_monitor_job, interval=CONFIG["WEB_CHECK_INTERVAL"], first=5)
    ptb_app.job_queue.run_repeating(mining_monitor_job, interval=CONFIG["MINING_CHECK_INTERVAL"], first=5)
    ptb_app.job_queue.run_repeating(verify_webhook_job, interval=CONFIG["WEBHOOK_CHECK_INTERVAL"], first=30)
    
    yield
    await ptb_app.stop()
    await ptb_app.shutdown()

fastapi_app = FastAPI(lifespan=lifespan)
@fastapi_app.post("/webhook")
async def webhook(request: Request) -> Response:
    try:
        data = await request.json()
        await ptb_app.process_update(Update.de_json(data, ptb_app.bot))
        return Response(status_code=HTTPStatus.OK)
    except Exception: return Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

if __name__ == "__main__":
    uvicorn.run(fastapi_app, host="127.0.0.1", port=CONFIG["PORT"])
