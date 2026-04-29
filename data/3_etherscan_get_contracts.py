import requests
import time
import json
from pathlib import Path
from tqdm import tqdm
import os

API_KEY = os.getenv("ETHERSCAN_API_KEY")
if not API_KEY:
    raise ValueError("ETHERSCAN_API_KEY is not set")

CHAIN_ID = 1

# ===== Clash 代理配置 =====
PROXIES = {
    "http":  "socks5h://127.0.0.1:7991",
    "https": "socks5h://127.0.0.1:7991",
}

ADDR_DIR = Path("contracts")
ADDR_FILE = ADDR_DIR / "addresses.txt"

FETCHED_FILE = ADDR_DIR / "fetched.txt"
FAILED_FILE = ADDR_DIR / "failed.txt"

SRC_DIR = ADDR_DIR / "sources"
SRC_DIR.mkdir(exist_ok=True)

CD = 0.22         # 正常请求间隔
NET_ERR_SLEEP = 10 # 网络错误后的退避
SESSION_RESET_N = 100  # 每多少次请求重建 session

# ---------------- 工具函数 ----------------

def load_set(path: Path):
    if not path.exists():
        return set()
    return set(x.strip() for x in path.open())

def mark(path: Path, addr: str):
    with path.open("a") as f:
        f.write(addr + "\n")

def new_session():
    """
    创建一个走 Clash SOCKS5 代理的 session
    """
    s = requests.Session()
    s.proxies.update(PROXIES)

    adapter = requests.adapters.HTTPAdapter(
        pool_connections=100,
        pool_maxsize=100,
        max_retries=0
    )
    s.mount("http://", adapter)
    s.mount("https://", adapter)

    return s

def looks_like_system_addr(addr: str) -> bool:
    """
    跳过明显不可能是合约的地址（precompile / 系统地址）
    """
    try:
        return int(addr, 16) < 0x1000
    except Exception:
        return True

# ---------------- 预处理 ----------------

fetched = load_set(FETCHED_FILE)
failed = load_set(FAILED_FILE)

with ADDR_FILE.open() as f:
    all_addrs = [x.strip() for x in f]

pending_addrs = [
    a for a in all_addrs
    if a not in fetched and a not in failed
]

total = len(pending_addrs)
print(f"Total pending contracts: {total}")

# ---------------- 主循环 ----------------

session = new_session()

with tqdm(total=total, desc="Fetching contracts", unit="addr") as pbar:
    for i, addr in enumerate(pending_addrs):

        # ---- 定期重建 session（关键！）----
        if i > 0 and i % SESSION_RESET_N == 0:
            session.close()
            session = new_session()

        # ---- 跳过系统地址 ----
        if looks_like_system_addr(addr):
            mark(FAILED_FILE, addr)
            pbar.update(1)
            continue

        url = (
            "https://api.etherscan.io/v2/api"
            f"?apikey={API_KEY}"
            f"&chainid={CHAIN_ID}"
            "&module=contract"
            "&action=getsourcecode"
            f"&address={addr}"
        )

        try:
            # ---- 显式关闭 response + 短 timeout ----
            with session.get(url, timeout=8) as r:
                data = r.json()

            # ---- 明确 API 返回失败 ----
            if data.get("status") != "1":
                mark(FAILED_FILE, addr)
                pbar.update(1)
                time.sleep(CD)
                continue

            result = data["result"][0]

            # ---- EOA / 未验证合约 ----
            if not result.get("SourceCode"):
                mark(FAILED_FILE, addr)
                pbar.update(1)
                time.sleep(CD)
                continue

            # ---- 保存源码 ----
            out = SRC_DIR / f"{addr}.json"
            with out.open("w") as fw:
                json.dump(result, fw, indent=2)

            mark(FETCHED_FILE, addr)

        except requests.exceptions.RequestException as e:
            # ⚠️ 网络错误：不要标 failed
            print(f"[NET ERROR] {addr}: {e}")
            time.sleep(NET_ERR_SLEEP)
            continue

        except Exception as e:
            # ⚠️ 真正的逻辑错误才记 failed
            print(f"[ERROR] {addr}: {e}")
            mark(FAILED_FILE, addr)

        pbar.update(1)
        time.sleep(CD)

session.close()
