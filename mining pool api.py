import requests
import json
from datetime import datetime

# 配置
BITCOIN_ADDRESS = "13NvdBs5dFarwR4TK373BMM4sEheAXbewB"  # 替换为你的地址
API_URL = f"https://pool.nerdminers.org/users/{BITCOIN_ADDRESS}"

def fetch_miner_stats():
    """抓取矿工统计数据"""
    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {e}")
        return None

def display_stats(data):
    """显示统计数据"""
    if not data:
        return

    print(f"\n{'='*50}")
    print(f"矿工数据更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")
    print(json.dumps(data, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    stats = fetch_miner_stats()
    display_stats(stats)