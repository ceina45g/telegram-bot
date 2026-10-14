import socket
import time

targets = [
    ("pool.nerdminers.org", 3333, "NerdMiner 官方池"),
    ("pool.nerdminer.io", 3333, "NerdMiner 備用池"),
    ("solo.ckpool.org", 3333, "CKPool (標準 Solo)"),
    ("public-pool.io", 21496, "Public-Pool (替代埠)"),
]

def test_connection(host, port, desc):
    print(f"正在測試 {desc} ({host}:{port})...", end=" ", flush=True)
    start = time.time()
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        elapsed = (time.time() - start) * 1000
        if result == 0:
            print(f"✅ 成功! (延遲: {elapsed:.1f}ms)")
            return True
        else:
            print(f"❌ 失敗 (錯誤碼: {result})")
            return False
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        return False
    finally:
        if sock:
            sock.close()

if __name__ == "__main__":
    print("=== NerdMiner 連線診斷工具 ===")
    results = []
    for host, port, desc in targets:
        results.append(test_connection(host, port, desc))
    
    print("\n診斷建議:")
    if any(results):
        print("找到可連線的礦池，請將 worker.py 中的 POOL_HOST 和 POOL_PORT 修改為成功的組合。")
    else:
        print("所有連線均失敗。這通常代表您的 ISP 或路由器防護攔截了挖礦流量。")
        print("建議測試：")
        print("1. 使用手機 4G/5G 熱點連線測試。")
        print("2. 檢查 Windows Defender 是否已將此資料夾排除。")
