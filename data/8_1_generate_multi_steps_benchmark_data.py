import json
import random
import os

# 定义关联词
connectors = ["then", "and", "after that", "followed by", "next", "subsequently"]

# 文件路径
actions_schema_path = "txs_intents/actions_schema.jsonl"
single_step_path = "txs_intents/single_step_intent2tx.jsonl"
output_path = "benchmark/hf_multi_steps_intent2tx.jsonl"

# 读取 actions_schema.jsonl
actions = []
with open(actions_schema_path, 'r', encoding='utf-8') as f:
    for line in f:
        actions.append(json.loads(line.strip()))

# 读取 single_step_intent2tx.jsonl
single_steps = []
with open(single_step_path, 'r', encoding='utf-8') as f:
    for line in f:
        single_steps.append(json.loads(line.strip()))

# 检查行数是否一致
assert len(actions) == len(single_steps), "文件行数不一致"

# 按 from 字段分组
from_groups = {}
for idx, action in enumerate(actions):
    from_addr = action["from"]
    if from_addr not in from_groups:
        from_groups[from_addr] = []
    from_groups[from_addr].append(idx)

# 多步 instruction
multi_step_instruction = """You are a DeFi execution planner.

Your task is to convert a user's high-level intent into an ordered list of on-chain actions on Ethereum. Each action must be represented as a JSON object within a list.

Output requirements:
- Output a JSON list only, no explanations.
- Follow the exact schema defined below for each action.
- For each parameter, you must provide both its Solidity type and the specific value (val) inferred from the intent.
- Ensure the actions are in the correct logical execution order.

JSON schema for each action:
{
  "contract": string,              // contract name or role (e.g., "TetherToken")
  "contract_address": string,      // contract address (e.g., "0x7a250d5630b4cf539739df2c5dacabf6959a1e")
  "function": string,              // function to be called (e.g., "approve")
  "params": {                      // map of parameters
    "<param_name>": {
      "type": string,              // Solidity type (e.g., "address", "uint256", "bytes")
      "val": any                   // specific value inferred from the intent (address hex, large integer string, etc.)
    }
    ... // more parameters if needed
  },
  "value": float                   // the amount of Ether (in ETH) sent with the transaction; set to 0.0 if not applicable.
}

Example structure:
[
  { "contract": "TokenA", "function": "approve", "params": { "spender": {"type": "address", "val": "0x..."}, "amount": {"type": "uint256", "val": "1000..."} }, "value": 0.0 },
  { "contract": "DexRouter", "function": "swap", "params": { ... }, "value": 0.0 }
]
"""

# 生成多步数据
with open(output_path, 'w', encoding='utf-8') as f:
    for from_addr, indices in from_groups.items():
        if len(indices) >= 2:
            end = random.randint(2, min(5, len(indices)))  # 每条数据包含 2-5 步
            selected_indices = indices[:end]  # 选择前 end 条记录
            selected_indices.sort()  # 按时间顺序？

            # 获取 inputs 和 outputs
            inputs = [single_steps[idx]["input"] for idx in selected_indices]
            outputs = [json.loads(single_steps[idx]["output"]) for idx in selected_indices]

            # 组合 input
            combined_input = "User intent:\n" + inputs[0].replace("User intent:\n", "")
            for i in range(1, len(inputs)):
                connector = random.choice(connectors)
                intent_part = inputs[i].replace("User intent:\n", "")
                combined_input += f"{connector} {intent_part}"

            # 输出
            record = {
                "instruction": multi_step_instruction,
                "input": combined_input,
                "output": outputs
            }
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

print(f"[OK] Generated into {output_path}")
