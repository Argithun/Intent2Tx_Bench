import json
import sys
import time
from pathlib import Path
from web3 import Web3
from eth_abi import encode
from eth_utils import function_signature_to_4byte_selector

# ============================================================
# 配置
# ============================================================

INFURA_URL = "https://eth.drpc.org"
RAW_DATA_PATH = "../../data/txs_intents/intent_action_pairs.jsonl"

ANVIL_URL = "http://127.0.0.1:8545"

HTTP_TIMEOUT = 120
RPC_RETRY = 3

# ============================================================
# Web3 初始化
# ============================================================

w3_mainnet = Web3(Web3.HTTPProvider(
    INFURA_URL,
    request_kwargs={"timeout": HTTP_TIMEOUT, 'proxies': {'https': 'http://127.0.0.1:7990'}}
))

w3_anvil = Web3(Web3.HTTPProvider(
    ANVIL_URL,
    request_kwargs={"timeout": HTTP_TIMEOUT, 'proxies': {'https': 'http://127.0.0.1:7990'}}
))

# ============================================================
# ERC20 ABI
# ============================================================

MIN_ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]

# ============================================================
# RPC Retry
# ============================================================

def rpc_call(func, *args, **kwargs):
    for i in range(RPC_RETRY):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if i == RPC_RETRY - 1:
                raise
            time.sleep(1)

# ============================================================
# JSON 解析
# ============================================================

def safe_load_json(text):
    if not text:
        return None

    if isinstance(text, (list, dict)):
        return text

    if not isinstance(text, str):
        return None

    start_obj = text.find("{")
    start_arr = text.find("[")

    if start_obj == -1 and start_arr == -1:
        return None

    if start_obj == -1:
        start = start_arr
    elif start_arr == -1:
        start = start_obj
    else:
        start = min(start_obj, start_arr)

    end = max(text.rfind("}"), text.rfind("]"))

    if end <= start:
        return None

    json_str = text[start:end+1].strip("`\n ")

    try:
        return json.loads(json_str)
    except:
        return None

# ============================================================
# block 信息缓存
# ============================================================

def get_block_info(intent_str, raw_file_path):

    if not hasattr(get_block_info, "_cache"):
        get_block_info._cache = {}

        with open(raw_file_path) as f:
            for line in f:
                raw = json.loads(line)
                get_block_info._cache[raw["intent"].strip()] = raw["tx_hash"]

    clean_intent = intent_str.replace("User intent:\n", "").strip()

    tx_hash = get_block_info._cache.get(clean_intent)

    if not tx_hash:
        return None, None

    try:
        tx = rpc_call(w3_mainnet.eth.get_transaction, tx_hash)
        return tx["blockNumber"], tx["from"]
    except:
        return None, None

# ============================================================
# token 提取
# ============================================================

def get_touched_tokens(json_obj):

    addresses = set()

    if not json_obj or "params" not in json_obj:
        return addresses

    for p in json_obj["params"].values():

        if p["type"] == "address":
            addresses.add(p["val"])

        elif p["type"] == "address[]":
            addresses.update(p["val"])

    valid = []

    for addr in addresses:
        if isinstance(addr, str) and addr.startswith("0x") and len(addr) == 42:
            valid.append(Web3.to_checksum_address(addr))

    return set(valid)

# ============================================================
# 账户状态
# ============================================================

def get_account_state(user_address, tokens):

    state = {"ETH": rpc_call(w3_anvil.eth.get_balance, user_address)}

    for addr in tokens:
        try:
            contract = w3_anvil.eth.contract(address=addr, abi=MIN_ERC20_ABI)
            state[addr] = contract.functions.balanceOf(user_address).call()
        except:
            state[addr] = 0

    return state

# ============================================================
# delta
# ============================================================

def calculate_delta(before, after):

    delta = {}

    for k in before:
        delta[k] = after[k] - before[k]

    return delta

# ============================================================
# 模拟执行
# ============================================================

def simulate_and_trace(user_address, target_json):

    if not target_json:
        return False, "Invalid JSON", {}

    try:

        rpc_call(
            w3_anvil.provider.make_request,
            "anvil_setBalance",
            [user_address, hex(Web3.to_wei(20, "ether"))]
        )

        rpc_call(
            w3_anvil.provider.make_request,
            "anvil_impersonateAccount",
            [user_address]
        )

        contract_addr = Web3.to_checksum_address(target_json["contract_address"])

        tokens = get_touched_tokens(target_json)

        for token_addr in tokens:

            try:

                approve_data = "0x095ea7b3" + encode(
                    ["address", "uint256"],
                    [contract_addr, 2**256 - 1]
                ).hex()

                rpc_call(
                    w3_anvil.eth.send_transaction,
                    {
                        "from": user_address,
                        "to": token_addr,
                        "data": approve_data,
                        "gas": 100000
                    }
                )

            except:
                pass

        params_dict = target_json.get("params", {})

        param_types = []
        param_values = []

        def cast_value(v, t):

            if t.endswith("[]") and isinstance(v, list):

                base = t[:-2]

                return [cast_value(x, base) for x in v]

            if "uint" in t:
                return int(str(v), 0) if isinstance(v, str) else int(v)

            if t == "bytes":

                if not v or v == "0x":
                    return b""

                return Web3.to_bytes(hexstr=v.strip())

            return v

        for p_name, p_info in params_dict.items():

            p_type = p_info["type"]

            p_val = cast_value(p_info["val"], p_type)

            if p_name.lower() == "deadline":
                p_val = 9999999999

            param_types.append(p_type)
            param_values.append(p_val)

        func_sig = f"{target_json['function']}({','.join(param_types)})"

        selector = function_signature_to_4byte_selector(func_sig)

        calldata = "0x" + selector.hex() + encode(param_types, param_values).hex()

        tx_params = {
            "from": user_address,
            "to": contract_addr,
            "value": Web3.to_wei(target_json.get("value", 0), "ether"),
            "data": calldata,
            "gas": 8000000,
        }

        state_before = get_account_state(user_address, tokens)

        tx_hash = rpc_call(w3_anvil.eth.send_transaction, tx_params)

        receipt = rpc_call(
            w3_anvil.eth.wait_for_transaction_receipt,
            tx_hash,
            timeout=60
        )

        if receipt.status == 1:

            state_after = get_account_state(user_address, tokens)

            delta = calculate_delta(state_before, state_after)

            gas_cost = receipt.gasUsed * receipt.effectiveGasPrice

            delta["ETH"] += gas_cost

            return True, int(receipt.gasUsed), delta

        else:
            return False, "Reverted", {}

    except Exception as e:

        return False, str(e), {}

# ============================================================
# 主流程
# ============================================================

def run_evaluation(result_file):

    input_path = Path(result_file)

    output_dir = Path("./log")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"simulated_{input_path.name}"

    processed = set()

    if output_file.exists():

        with open(output_file) as f:
            for line in f:
                try:
                    processed.add(json.loads(line)["original_input"])
                except:
                    pass

        print(f"Resuming: {len(processed)} records already processed.")

    with open(result_file) as f_in, open(output_file, "a") as f_out:

        for i, line in enumerate(f_in):

            item = json.loads(line)

            original_input = item["input"]

            if original_input in processed:
                continue

            print(f"\n[{i}] Processing: {original_input[:60]}...")

            if item["llm_output"] is None or item["llm_output"].strip() == "ERROR":

                record = {
                    "original_input": original_input,
                    "gold_success": None,
                    "pred_success": None,
                    "is_state_equivalent": None,
                    "gold_delta": {},
                    "pred_delta": {},
                    "error_msg": "Empty LLM output"
                }

                f_out.write(json.dumps(record) + "\n")
                f_out.flush()
                continue

            gold_json = safe_load_json(item["output"])
            pred_json = safe_load_json(item["llm_output"])

            block_num, user_addr = get_block_info(original_input, RAW_DATA_PATH)

            if not block_num:
                continue

            block_num -= 1

            rpc_call(
                w3_anvil.provider.make_request,
                "anvil_reset",
                [{"forking": {"jsonRpcUrl": INFURA_URL, "blockNumber": hex(block_num)}}]
            )

            snap = rpc_call(
                w3_anvil.provider.make_request,
                "evm_snapshot",
                []
            )["result"]

            gold_success, gold_info, gold_delta = simulate_and_trace(user_addr, gold_json)

            rpc_call(
                w3_anvil.provider.make_request,
                "evm_revert",
                [snap]
            )

            pred_success, pred_info, pred_delta = simulate_and_trace(
                user_addr,
                pred_json
            ) if pred_json else (False, "Parse Error", {})

            is_state_equivalent = False

            if gold_success and pred_success:

                is_state_equivalent = True

                for token, g_val in gold_delta.items():

                    p_val = pred_delta.get(token, 0)

                    if g_val != 0:

                        err = abs((g_val - p_val) / g_val)

                        if err > 0.01:
                            is_state_equivalent = False
                            break

                    elif p_val != 0:
                        is_state_equivalent = False
                        break

            record = {
                "original_input": original_input,
                "gold_success": gold_success,
                "pred_success": pred_success,
                "is_state_equivalent": is_state_equivalent,
                "gold_delta": {k: str(v) for k, v in gold_delta.items()},
                "pred_delta": {k: str(v) for k, v in pred_delta.items()},
                "error_msg": pred_info if not pred_success else ""
            }

            f_out.write(json.dumps(record) + "\n")
            f_out.flush()

            print(f"Done. Status: Gold={gold_success}, Pred={pred_success}")

    print(f"\nEvaluation finished. Results saved to {output_file}")

# ============================================================

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage: python dynamic_simulate_eval.py <test_results.jsonl>")
    else:
        run_evaluation(sys.argv[1])