import requests
import json
from datetime import datetime

# ================== 配置区 ==================
BITCOIN_ADDRESS = "13NvdBs5dFarwR4TK373BMM4sEheAXbewB"  # 你要监控的地址
USER_API_URL = f"https://pool.nerdminers.org/users/{BITCOIN_ADDRESS}"
POOL_API_URL = "https://pool.nerdminers.org/pool/pool.status"
# ==========================================

def fetch_data(url, description, is_pool_status=False):
    """通用抓取函数"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        if is_pool_status:
            # 矿池状态回传多行 JSON，需要逐行解析并合并
            merged_data = {}
            for line in response.text.splitlines():
                if line.strip():
                    merged_data.update(json.loads(line))
            print(f"✅ {description} 抓取成功 (已合併多行数据)")
            return merged_data
        else:
            data = response.json()
            print(f"✅ {description} 抓取成功")
            return data
    except requests.exceptions.RequestException as e:
        print(f"❌ {description} 请求失败: {e}")
        return None
    except (json.JSONDecodeError, ValueError) as e:
        print(f"❌ {description} 数据解析失败: {e}")
        return None

def display_stats(user_data, pool_data):
    """显示抓取结果"""
    print("\n" + "="*60)
    print(f"⏰ 更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📍 监控地址: {BITCOIN_ADDRESS}")
    print("="*60)

    if user_data:
        print("\n👤 矿工数据 (User Stats):")
        print(json.dumps(user_data, indent=2, ensure_ascii=False))
    else:
        print("\n⚠️ 未获取到矿工数据 (地址可能无效或无挖矿记录)")

    if pool_data:
        print("\n🌐 矿池状态 (Pool Status):")
        print(json.dumps(pool_data, indent=2, ensure_ascii=False))
    else:
        print("\n⚠️ 未获取到矿池状态數據")

if __name__ == "__main__":
    # 1. 抓取用户数据
    user_stats = fetch_data(USER_API_URL, "矿工数据")

    # 2. 抓取矿池数据 (開啟多行解析模式)
    pool_stats = fetch_data(POOL_API_URL, "矿池状态", is_pool_status=True)

    # 3. 展示結果
    display_stats(user_stats, pool_stats)
