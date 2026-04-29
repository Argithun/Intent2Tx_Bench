#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path
from tqdm import tqdm

# -------------------------
# Paths
# -------------------------

INTENT_FILE = Path("txs_intents/intent_action_pairs.jsonl")
ACTION_FILE = Path("txs_intents/actions_schema.jsonl")
OUT_FILE = Path("txs_intents/single_step_intent2tx.jsonl")

# -------------------------
# Improved Prompt template
# -------------------------

SYSTEM_PROMPT = (
    "You are a DeFi execution planner.\n\n"
    "Your task is to convert a user's high-level intent into a SINGLE on-chain action represented as a JSON object.\n\n"
    "Output requirements:\n"
    "- Output JSON only, no explanations.\n"
    "- Follow the exact schema defined below.\n"
    "- For each parameter, you must provide both its Solidity type and the specific value inferred from the intent.\n\n"
    "JSON schema:\n"
    "{\n"
    '  "contract": string,              // contract name (e.g., "UniswapV2Router02")\n'
    '  "contract_address": string,      // contract address (e.g., "0x7a250d5630b4cf539739df2c5dacabf6959a1e")\n'
    '  "function": string,              // function name (e.g., "transfer")\n'           
    '  "params": {                      // map of parameters\n'
    '    "<param_name>": {\n'
    '      "type": string,              // Solidity type (e.g., "address", "uint256")\n'
    '      "val": any                   // specific value inferred from the intent\n'
    '    }\n'
    '    ... // more parameters if needed \n'
    "  },\n"
    '  "value": float                   // Ether amount sent with the transaction (in ETH)\n'
    "}\n\n"
)

# -------------------------
# Action abstraction
# -------------------------

def abstract_action(action_record: dict) -> dict:
    """
    保持原始数据的 params 结构：{"param_name": {"type": "...", "val": "..."}}
    """
    action = action_record.get("action", {})
    
    contract = action.get("contract") or action.get("protocol", "Unknown")
    function = action.get("function", "")
    params = action.get("params", {})
    value_obj = action.get("value", {})

    # 构建与原始数据一致的 params 结构
    formatted_params = {}
    for name, spec in params.items():
        formatted_params[name] = {
            "type": spec.get("type"),
            "val": spec.get("val")
        }

    try:
        eth_value = float(value_obj.get("value", 0))
    except (TypeError, ValueError):
        eth_value = 0.0

    return {
        "contract": contract,
        "contract_address": action.get("protocol", "0xUnknown"),
        "function": function,
        "params": formatted_params,
        "value": eth_value,
    }

# -------------------------
# Main logic
# -------------------------

def main():
    # 1. 加载 Intent
    intents = {}
    if not INTENT_FILE.exists():
        print(f"Error: {INTENT_FILE} not found.")
        return

    with INTENT_FILE.open() as f:
        for line in f:
            try:
                obj = json.loads(line)
                intents[obj["tx_hash"]] = obj["intent"]
            except: continue

    # 2. 加载原始 Action 记录
    actions_records = {}
    with ACTION_FILE.open() as f:
        for line in f:
            try:
                obj = json.loads(line)
                actions_records[obj["tx_hash"]] = obj
            except: continue

    kept, skipped = 0, 0

    # 3. 构造 Benchmark 数据集
    with OUT_FILE.open("w") as out:
        for tx_hash, intent in tqdm(intents.items(), desc="Building benchmark"):
            if tx_hash not in actions_records:
                skipped += 1
                continue

            record = actions_records[tx_hash]
            abstracted = abstract_action(record)

            # 生成标准的 Completion JSON
            completion = json.dumps(abstracted, ensure_ascii=False)

            out.write(json.dumps({
                "instruction": SYSTEM_PROMPT,
                "input": f"User intent:\n{intent}",
                "output": completion
            }, ensure_ascii=False) + "\n")

            kept += 1

    print(f"[OK] Total generated: {kept}, Skipped: {skipped}")

if __name__ == "__main__":
    main()