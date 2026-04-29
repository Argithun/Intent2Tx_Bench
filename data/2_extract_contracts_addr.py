import json
import re
from pathlib import Path

INPUT_FILE = Path("txs/ethereum_txs_300d.jsonl")
ADDR_DIR = Path("contracts")
ADDR_DIR.mkdir(parents=True, exist_ok=True)

ADDR_FILE = ADDR_DIR / "addresses.txt"

ADDR_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

def is_valid_eth_address(addr: str) -> bool:
    if not addr:
        return False
    if not ADDR_RE.match(addr):
        return False

    # 剔除 precompile / 系统地址
    if int(addr, 16) < 0x1000:
        return False

    return True

addresses = set()

with INPUT_FILE.open() as f:
    for line in f:
        obj = json.loads(line)

        call = obj.get("Call", {})
        tx = obj.get("Transaction", {})

        for addr in (
            call.get("To"),
            call.get("From"),
            tx.get("To"),
        ):
            if isinstance(addr, str):
                addr = addr.lower()
                if is_valid_eth_address(addr):
                    addresses.add(addr)

with ADDR_FILE.open("w") as f:
    for a in sorted(addresses):
        f.write(a + "\n")

print(f"Extracted {len(addresses)} valid Ethereum addresses")
