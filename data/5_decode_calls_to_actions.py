import json
from pathlib import Path
from eth_utils import keccak, to_hex
from eth_abi import decode

TX_FILE = Path("txs_intents/selected_calls_for_intents.jsonl")
SRC_DIR = Path("contracts/sources")
OUT_FILE = Path("txs_intents/actions_schema.jsonl")

# -------------------------
# ABI helpers
# -------------------------

def load_contract_source(addr: str):
    p = SRC_DIR / f"{addr.lower()}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())

def load_abi(src_json):
    abi = src_json.get("ABI")
    if not abi:
        return None
    if isinstance(abi, str):
        abi = json.loads(abi)
    return abi

def abi_selector(fn_abi):
    sig = fn_abi["name"] + "(" + ",".join(i["type"] for i in fn_abi["inputs"]) + ")"
    return to_hex(keccak(text=sig)[:4])

# -------------------------
# Decode calldata
# -------------------------

def decode_params(entry, calldata_hex: str):
    inputs = entry.get("inputs", [])
    if not inputs:
        return {}

    types = [inp["type"] for inp in inputs]
    names = [
        inp["name"] or f"arg{i}"
        for i, inp in enumerate(inputs)
    ]

    try:
        # Handle both "0x" prefixed and non-prefixed hex strings
        if calldata_hex.startswith("0x"):
            data = bytes.fromhex(calldata_hex[10:])  # strip "0x" (2 chars) + selector (8 chars = 4 bytes)
        else:
            data = bytes.fromhex(calldata_hex[8:])  # strip selector (8 chars = 4 bytes)
        
        values = decode(types, data)
    except Exception:
        # If decoding fails (e.g., InsufficientDataBytes), return None
        return None

    def convert_value(val):
        """Recursively convert bytes and int to JSON-serializable types"""
        if isinstance(val, bytes):
            return to_hex(val)
        elif isinstance(val, int):
            return str(val)
        elif isinstance(val, (list, tuple)):
            return [convert_value(v) for v in val]
        else:
            return val

    params = {}
    for name, typ, val in zip(names, types, values):
        val = convert_value(val)
        params[name] = {
            "type": typ,
            "val": val
        }

    return params

# -------------------------
# Core extraction
# -------------------------

def extract_action_schema(tx):
    addr = tx["contract"].lower()
    src = load_contract_source(addr)
    if not src:
        return None

    abi = load_abi(src)
    if not abi:
        return None

    selector = tx["selector"]
    calldata = tx["input"]

    for entry in abi:
        if entry.get("type") != "function":
            continue

        if abi_selector(entry) != selector:
            continue

        params = decode_params(entry, calldata)
        if params is None:  # Handle decode failure
            return None

        # ETH value（永远保留）
        value = {
            "type": "ether",
            "value": tx.get("value", "0")
        }

        return {
            "tx_hash": tx["tx_hash"],
            "block_time": tx["block_time"],
            "from": tx["from"],
            "action": {
                "protocol": addr,  # namespace only
                "contract": src.get("ContractName") or tx.get("contract_name"),
                "function": entry["name"],
                "params": params,
                "value": value
            }
        }

    return None

# -------------------------
# Run
# -------------------------

def main():
    kept = 0
    dropped = 0

    with TX_FILE.open() as f, OUT_FILE.open("w") as out:
        for line in f:
            tx = json.loads(line)
            res = extract_action_schema(tx)
            if res:
                out.write(json.dumps(res) + "\n")
                kept += 1
            else:
                dropped += 1

    print(f"[OK] schemas={kept}, dropped={dropped}")

if __name__ == "__main__":
    main()
