import json
import os
import random
import time
import requests
from pathlib import Path
from tqdm import tqdm
from openai import OpenAI
import os

# -------------------------
# Config
# -------------------------

os.environ["HTTP_PROXY"] = "http://127.0.0.1:7990"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7990"

IN_FILE = Path("txs_intents/actions_schema.jsonl")
OUT_FILE = Path("txs_intents/intent_action_pairs.jsonl")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY is not set")

MODEL = "google/gemini-2.5-flash"

# -------------------------
# Intent via LLM
# -------------------------

INTENT_SYSTEM_PROMPT = """
You are a Web3 User Intent Generator. Your goal is to reverse-engineer a raw blockchain transaction into a realistic user request.

### Logic: Imagine the User's Persona
1. **For Common Actions (Transfer/Swap/Wrap)**: 
   - Act as a casual user. Use colloquial language.
   - Example: "Send all my ETH to my ledger", "Swap 100 USDT for some Pepe", "Wrap 2 Ether".
   - *Key*: Focus on the "what" and "how much", keep it natural.

2. **For Complex/DeFi Actions (Staking/Liquidity/Vaults)**:
   - Act as a DeFi user. Be more precise about the protocol and the action.
   - You can even provide specific details(contract address, function signature) when the transaction is complex or contract is obscure. However, you should be careful about the extent to which you provide this information.
   - Example: "Deposit 500 USDC into the Aave V3 pool", "Claim my rewards from the Lido dashboard".

3. **For Low-level/Niche/Rare Contract Calls**:
   - Act as a power user or developer. If the contract is rare, include specific IDs or addresses provided in the parameters.
   - If the transaction contains a long hex string (like data or secret) that cannot be simplified, explicitly mention that 'pre-calculated data' or 'specific secret' should be used.
   - Example: "Vote 'Yes' on Proposal #42", "Mint 3 NFTs from the whitelist contract at 0x7f18bb4dd92cf2404c54cba1a9be4a1153bdb078", "Call the emergency withdraw on the vault".

### Core Rules:
- **No Technical Metadata**: Do NOT mention 'bytes', 'calldata' or 'uint256'.
- **Param Integration**: If a parameter looks like a 'recipient', 'amount', or 'token symbol', incorporate it into the sentence.
- **Vary the Tone**: Choose professional, casual, and urgent tones according to the transaction content.
- **Output Only**: Provide the sentence only, no preamble.

### User Persona Examples:
- [Input: Transfer ETH] -> "Give 0.5 ETH to my friend at 0x942a6a136f84d491134b9e03a35dafa701d7ea21"
- [Input: Uniswap Swap] -> "I want to exchange 1000 USDC for as much LINK as possible."
- [Input: Niche Mint] -> "Mint 5 tokens from the contract 0x7f18bb4dd92cf2404c54cba1a9be4a1153bdb078 on the mainnet."
"""

class OpenAIClient:
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def run(self, user_action: str) -> str:
        response = self.client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_action}
            ]
        )
        return response.choices[0].message.content

openai_client = OpenAIClient(api_key=OPENROUTER_API_KEY)

def infer_intent(action_obj):
    try:
        return openai_client.run(json.dumps(action_obj, ensure_ascii=False))
    except Exception as e:
        print(f"[LLM error]: {e}")
        return ""

# -------------------------
# Action sentence templates
# -------------------------

ACTION_TEMPLATES = [
    "Call {contract}.{function} with parameters {params} and value {value}",
    "Execute {function} on {contract}, passing {params}, sending {value}",
    "{contract}.{function} invoked using {params} (value: {value})",
    "Perform a contract call to {contract} using function {function} with arguments {params} and transaction value {value}",
    "Invoke {function} of {contract} with inputs {params}; ETH value = {value}",
]

def format_params(params: dict) -> str:
    parts = []
    for name, spec in params.items():
        parts.append(f"{name}:{spec.get('type')}")
    return ", ".join(parts)

def render_action(action_obj):
    tpl = random.choice(ACTION_TEMPLATES)

    params_str = format_params(action_obj.get("params", {}))
    value_obj = action_obj.get("value", {})
    value_str = value_obj.get("value", "0")
    if value_str == "0.000000000000000000":
        value_str = "0.0"

    return tpl.format(
        contract=action_obj.get("contract"),
        function=action_obj.get("function"),
        params=params_str,
        value=value_str,
    )

# -------------------------
# Resume helpers
# -------------------------

def load_done_hashes():
    if not OUT_FILE.exists():
        return set()

    done = set()
    with OUT_FILE.open() as f:
        for line in f:
            try:
                done.add(json.loads(line)["tx_hash"])
            except Exception:
                continue
    return done

def count_lines(path: Path) -> int:
    with path.open() as f:
        return sum(1 for _ in f)

# -------------------------
# Main
# -------------------------

def main():
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    done_hashes = load_done_hashes()
    total = count_lines(IN_FILE)

    kept = 0
    skipped = 0

    with IN_FILE.open() as f, OUT_FILE.open("a") as out:
        for line in tqdm(f, total=total, desc="Generating intents"):
            record = json.loads(line)
            tx_hash = record["tx_hash"]

            # ---- resume skip ----
            if tx_hash in done_hashes:
                skipped += 1
                continue

            action = record["action"]

            try:
                intent = infer_intent(action)
            except Exception as e:
                print(f"[LLM error] {tx_hash}: {e}")
                continue

            action_sentence = render_action(action)

            out.write(json.dumps({
                "tx_hash": tx_hash,
                "block_time": record["block_time"],
                "intent": intent,
                "action": action_sentence
            }, ensure_ascii=False) + "\n")

            out.flush()  # 💡 crash-safe
            kept += 1

            time.sleep(0.4)  # rate limit

    print(f"[OK] new={kept}, skipped={skipped}, total_done={kept + skipped}")

if __name__ == "__main__":
    main()
