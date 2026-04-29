import json
from pathlib import Path

# ------------------------
# Paths
# ------------------------
TX_FILE = Path("txs/ethereum_txs_300d.jsonl")

CONTRACT_DIR = Path("contracts")
FETCHED_FILE = CONTRACT_DIR / "fetched.txt"
SOURCE_DIR = CONTRACT_DIR / "sources"

OUT_FILE = Path("txs_intents/selected_calls_for_intents.jsonl")

# ------------------------
# Config
# ------------------------
MIN_GAS_USED = 5000   # 经验阈值，可调

# ------------------------
# Load fetched contracts
# ------------------------
fetched_contracts = set(
    addr.strip().lower()
    for addr in FETCHED_FILE.open()
    if addr.strip()
)

def load_contract_name(addr: str) -> str:
    src = SOURCE_DIR / f"{addr}.json"
    if not src.exists():
        return ""
    try:
        with src.open() as f:
            return json.load(f).get("ContractName", "")
    except Exception:
        return ""

# ------------------------
# Main filter loop
# ------------------------
kept = 0
seen = 0

with TX_FILE.open() as fin, OUT_FILE.open("w") as fout:
    for line in fin:
        seen += 1
        try:
            row = json.loads(line)
        except Exception:
            continue

        call = row.get("Call", {})
        tx = row.get("Transaction", {})
        block = row.get("Block", {})

        # ---- 1. 原子 call ----
        if call.get("Depth") != 0:
            continue
        if call.get("CallPath") not in ([], None):
            continue

        # ---- 2. 成功 & 非 view ----
        if not call.get("Success"):
            continue

        gas_used = int(call.get("GasUsed", "0"))
        if gas_used < MIN_GAS_USED:
            continue

        # ---- 3. 合约地址必须有源码 ----
        to_addr = (call.get("To") or "").lower()
        if not to_addr or to_addr not in fetched_contracts:
            continue

        # ---- 4. 必须是函数调用 ----
        input_data = call.get("Input", "")
        if not input_data or input_data == "0x" or len(input_data) < 10:
            continue

        selector = input_data[:10]

        contract_name = load_contract_name(to_addr)

        out = {
            "tx_hash": tx.get("Hash"),
            "block_time": block.get("Time"),
            "contract": to_addr,
            "contract_name": contract_name,
            "selector": selector,
            "input": input_data,
            "from": call.get("From"),
            "value": call.get("Value"),
            "gas_used": gas_used
        }

        fout.write(json.dumps(out) + "\n")
        kept += 1

print(f"Done. Kept {kept} / {seen} calls.")
print(f"Output written to {OUT_FILE}")
