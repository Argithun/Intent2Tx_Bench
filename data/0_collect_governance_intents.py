#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collect natively human-written intent -> transaction pairs from on-chain DAO governance.

OpenZeppelin Governor and Compound GovernorBravo both emit

    ProposalCreated(uint256 proposalId, address proposer, address[] targets, uint256[] values,
                    string[] signatures, bytes[] calldatas, uint256 startBlock, uint256 endBlock,
                    string description)

so a single topic0 query finds proposals from every such governor on Ethereum mainnet, without a
hand-maintained list of DAOs. The human-written `description` is the intent, and the proposal's
(targets, values, calldatas) are the transactions that were actually executed on-chain.

Pipeline (each stage is cached under governance/ so the script can be resumed):
  1. fetch ProposalCreated / ProposalExecuted logs in the benchmark window (Etherscan getLogs)
  2. keep executed proposals with 1-5 calls
  3. decode every call with the target's verified ABI (Etherscan getsourcecode, proxies resolved)
  4. turn the description into an intent (title + first summary paragraph)
  5. write single-step / multi-step records in the same HF format as the existing benchmark

Usage:
  python 12_collect_governance_intents.py            # all stages
  python 12_collect_governance_intents.py --max 600  # cap the number of kept proposals
"""
import argparse
import datetime as dt
import importlib.util
import json
import re
import time
from pathlib import Path

import requests
from eth_abi import decode, encode
from eth_utils import keccak, to_checksum_address, to_hex

API_KEY = "GUFYAMHAXEXJZWMYNJYY8R6DXU5ASWVG9T"
ETHERSCAN = "https://api.etherscan.io/v2/api"
RPC_URL = "https://eth-mainnet.g.alchemy.com/v2/GAX_-5YBHqnLeCM7dL0MR"
CHAIN_ID = 1
CD = 0.22                      # Etherscan request interval (free tier: 5 req/s)

# Same collection window as the rest of the benchmark (2025.03 - 2026.01).
WINDOW_START = dt.datetime(2025, 3, 1, tzinfo=dt.timezone.utc)
WINDOW_END = dt.datetime(2026, 2, 1, tzinfo=dt.timezone.utc)
MAX_STEPS = 5                  # the multi-step split uses 2-5 actions

OUT_DIR = Path("governance")
SRC_DIR = Path("contracts/sources")        # shared ABI cache with 3_etherscan_get_contracts.py
LOG_CACHE = OUT_DIR / "logs_cache.json"
RAW_FILE = OUT_DIR / "proposals_decoded.jsonl"
SINGLE_FILE = OUT_DIR / "hf_single_step_governance.jsonl"
MULTI_FILE = OUT_DIR / "hf_multi_steps_governance.jsonl"

TOPIC_CREATED = "0x" + keccak(text="ProposalCreated(uint256,address,address[],uint256[],string[],bytes[],uint256,uint256,string)").hex()
TOPIC_EXECUTED = "0x" + keccak(text="ProposalExecuted(uint256)").hex()
CREATED_TYPES = ["uint256", "address", "address[]", "uint256[]", "string[]", "bytes[]", "uint256", "uint256", "string"]

session = requests.Session()


# -------------------------
# Etherscan / RPC helpers
# -------------------------

def etherscan(**params):
    params.update(chainid=CHAIN_ID, apikey=API_KEY)
    for attempt in range(5):
        try:
            r = session.get(ETHERSCAN, params=params, timeout=30).json()
            time.sleep(CD)
            if r.get("message") == "NOTOK" and "rate limit" in str(r.get("result", "")).lower():
                time.sleep(2)
                continue
            return r
        except requests.RequestException:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Etherscan request failed: {params.get('action')}")


def rpc_call(to, data):
    body = {"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": to, "data": data}, "latest"]}
    try:
        return session.post(RPC_URL, json=body, timeout=30).json().get("result")
    except requests.RequestException:
        return None


def block_by_time(ts):
    return int(etherscan(module="block", action="getblocknobytime", timestamp=int(ts), closest="before")["result"])


def get_logs(topic0, b0, b1):
    """All logs with topic0 in [b0, b1]; splits the range when Etherscan's 1000-row page fills up."""
    r = etherscan(module="logs", action="getLogs", fromBlock=b0, toBlock=b1, topic0=topic0, page=1, offset=1000)
    rows = r.get("result") if isinstance(r.get("result"), list) else []
    if len(rows) < 1000 or b0 == b1:
        return rows
    mid = (b0 + b1) // 2
    return get_logs(topic0, b0, mid) + get_logs(topic0, mid + 1, b1)


# -------------------------
# ABI helpers
# -------------------------

def load_source(addr):
    """Verified source JSON for addr (cached); None for EOAs / unverified contracts."""
    addr = addr.lower()
    p = SRC_DIR / f"{addr}.json"
    if p.exists():
        return json.loads(p.read_text())
    r = etherscan(module="contract", action="getsourcecode", address=addr)
    if r.get("status") != "1" or not r["result"][0].get("SourceCode"):
        return None
    src = r["result"][0]
    p.write_text(json.dumps(src, indent=2))
    return src


def load_abi(addr):
    """(contract_name, abi) of addr, following EIP-1967-style proxies to their implementation."""
    src = load_source(addr)
    if not src or not src.get("ABI") or src["ABI"].startswith("Contract source code not verified"):
        return None, None
    name, abi = src.get("ContractName"), json.loads(src["ABI"])
    impl = src.get("Implementation")
    if src.get("Proxy") == "1" and impl:
        isrc = load_source(impl)
        if isrc and isrc.get("ABI") and not isrc["ABI"].startswith("Contract source code not verified"):
            name, abi = isrc.get("ContractName") or name, json.loads(isrc["ABI"])
    return name, abi


def canonical_type(inp):
    """ABI input -> canonical type string, expanding tuples, e.g. (address,uint256)[]."""
    t = inp["type"]
    if t.startswith("tuple"):
        return "(" + ",".join(canonical_type(c) for c in inp["components"]) + ")" + t[len("tuple"):]
    return t


def selector_of(fn):
    return to_hex(keccak(text=fn["name"] + "(" + ",".join(canonical_type(i) for i in fn["inputs"]) + ")")[:4])


def to_json_value(v):
    if isinstance(v, bytes):
        return to_hex(v)
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return str(v)
    if isinstance(v, (list, tuple)):
        return [to_json_value(x) for x in v]
    if isinstance(v, str) and v.startswith("0x") and len(v) == 42:
        return v.lower()
    return v


def decode_call(target, calldata_hex):
    """Decode one call into the benchmark action schema; None if the ABI cannot explain it."""
    name, abi = load_abi(target)
    if not abi or len(calldata_hex) < 10:
        return None
    sel = calldata_hex[:10].lower()
    for fn in abi:
        if fn.get("type") != "function" or selector_of(fn) != sel:
            continue
        types = [canonical_type(i) for i in fn["inputs"]]
        try:
            vals = decode(types, bytes.fromhex(calldata_hex[10:])) if types else []
        except Exception:
            return None
        if types and encode(types, vals).hex() != calldata_hex[10:].lower():
            return None                                # trailing / malformed bytes: not a clean decode
        params = {(i["name"] or f"arg{k}"): {"type": t, "val": to_json_value(v)}
                  for k, (i, t, v) in enumerate(zip(fn["inputs"], types, vals))}
        return {"contract": name, "contract_address": target.lower(), "function": fn["name"], "params": params}
    return None


# -------------------------
# Description -> intent
# -------------------------

MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
URL = re.compile(r"(?:[A-Za-z ]*(?:link|forum|discussion|snapshot|details)\s*:\s*)?https?://\S+", re.I)


def clean_md(s):
    s = MD_LINK.sub(r"\1", s)
    s = URL.sub("", s)
    s = re.sub(r"[*_`>]+", "", s)
    return re.sub(r"\s+", " ", s).strip(" .:-")


def unwrap_description(desc):
    """Some front-ends store {"title": ..., "description": ...} JSON as the on-chain description."""
    s = desc.strip()
    if s.startswith("{"):
        try:
            obj = json.loads(s)
            title, body = obj.get("title", ""), obj.get("description", "")
            if body.lstrip().startswith("#"):
                return body
            return f"# {title}\n\n{body}" if title else body
        except (ValueError, AttributeError):
            pass
    return desc


def description_to_intent(desc, max_chars=600):
    """Title plus the first prose paragraph of the proposal description, verbatim apart from markdown."""
    desc = unwrap_description(desc)
    lines = [l.strip() for l in desc.replace("\r", "").split("\n")]
    title, body, para = None, [], []
    for l in lines:
        if not l:
            if para:
                body.append(" ".join(para)); para = []
            continue
        if title is None:
            title = clean_md(l.lstrip("#").strip())
            continue
        if l.startswith(("#", "|", "---", "![", "<")) or re.fullmatch(r"[-*]\s*", l):
            if para:
                body.append(" ".join(para)); para = []
            continue
        para.append(l)
        if len(body) >= 3:
            break
    if para:
        body.append(" ".join(para))
    labels = {"summary", "abstract", "tl;dr", "tldr", "overview", "simple summary", ""}
    meta = re.compile(r"^(proposal\s+)?(authors?|created by|proposer|date|submitted by|category|type|status)\b", re.I)
    lead = re.compile(r"^(simple summary|summary|abstract|tl;dr|tldr|overview)\s*[:\-]?\s+", re.I)
    first = next((lead.sub("", p) for p in map(clean_md, body)
                  if p.lower().rstrip(":") not in labels and not meta.match(p)), "")
    if len(first) > max_chars:                      # cut at a sentence boundary
        cut = first[:max_chars]
        first = cut[: cut.rfind(". ") + 1] if ". " in cut else cut.rsplit(" ", 1)[0] + "..."
    if not title:
        return None
    title = title.rstrip(".")
    return f"{title}. {first}".strip() if first and first.lower() not in title.lower() else title + "."


def good_intent(text):
    if not text or len(text.split()) < 5:
        return False
    ascii_ratio = sum(c.isascii() for c in text) / len(text)
    return ascii_ratio > 0.95


# -------------------------
# Main stages
# -------------------------

def fetch_logs():
    if LOG_CACHE.exists():
        return json.loads(LOG_CACHE.read_text())
    b0, b1 = block_by_time(WINDOW_START.timestamp()), block_by_time(WINDOW_END.timestamp())
    print(f"[logs] block window {b0} - {b1}")
    created = get_logs(TOPIC_CREATED, b0, b1)
    executed = get_logs(TOPIC_EXECUTED, b0, b1)       # executed inside the same window
    data = {"window": [b0, b1], "created": created, "executed": executed}
    LOG_CACHE.write_text(json.dumps(data))
    print(f"[logs] ProposalCreated={len(created)}  ProposalExecuted={len(executed)}")
    return data


def parse_proposals(logs):
    executed = {}
    for e in logs["executed"]:
        if len(e["data"]) < 66:
            continue
        pid = int(e["data"][2:66], 16)
        executed[(e["address"].lower(), pid)] = e
    out = []
    for c in logs["created"]:
        try:
            v = decode(CREATED_TYPES, bytes.fromhex(c["data"][2:]))
        except Exception:
            continue
        pid, proposer, targets, values, sigs, calldatas, _, _, desc = v
        gov = c["address"].lower()
        ex = executed.get((gov, pid))
        if ex is None or not (1 <= len(targets) <= MAX_STEPS):
            continue
        calls = []
        for t, val, sig, cd in zip(targets, values, sigs, calldatas):
            data = (to_hex(keccak(text=sig)[:4]) + cd.hex()) if sig else to_hex(cd)
            calls.append({"target": t.lower(), "value_wei": int(val), "calldata": data})
        out.append({"governor": gov, "proposal_id": str(pid), "proposer": proposer.lower(),
                    "created_tx": c["transactionHash"], "executed_tx": ex["transactionHash"],
                    "executed_block": int(ex["blockNumber"], 16), "executed_time": int(ex["timeStamp"], 16),
                    "executed_gas_used": int(ex["gasUsed"], 16), "description": desc, "calls": calls})
    return out


def executor_of(governor, cache={}):
    """Address that executes the calls: the governor's timelock if it has one, else the governor."""
    if governor not in cache:
        res = rpc_call(to_checksum_address(governor), "0xd33219b4")       # timelock()
        cache[governor] = ("0x" + res[-40:]).lower() if res and len(res) >= 66 and int(res, 16) else governor
    return cache[governor]


def load_tagger():
    spec = importlib.util.spec_from_file_location("tagger", "7_2_tag_single_step_benchmark_data_rule_based.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.tag_item


def existing_instructions():
    single = json.loads(open("benchmark/hf_single_step_intent2tx.jsonl").readline())["instruction"]
    multi = json.loads(open("benchmark/hf_multi_steps_intent2tx.jsonl").readline())["instruction"]
    return single, multi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=None, help="cap on the number of kept proposals")
    args = ap.parse_args()
    OUT_DIR.mkdir(exist_ok=True)
    SRC_DIR.mkdir(parents=True, exist_ok=True)

    proposals = parse_proposals(fetch_logs())
    print(f"[parse] executed proposals with 1-{MAX_STEPS} calls: {len(proposals)}")

    tag_item = load_tagger()
    single_instr, multi_instr = existing_instructions()
    kept = {"single": 0, "multi": 0}
    drop = {"intent": 0, "decode": 0}
    seen_intents = set()

    with RAW_FILE.open("w") as fraw, SINGLE_FILE.open("w") as fs, MULTI_FILE.open("w") as fm:
        for p in sorted(proposals, key=lambda x: x["executed_block"]):
            if args.max and kept["single"] + kept["multi"] >= args.max:
                break
            intent = description_to_intent(p["description"])
            if not good_intent(intent) or intent in seen_intents:
                drop["intent"] += 1
                continue
            actions = []
            for c in p["calls"]:
                a = decode_call(c["target"], c["calldata"])
                if a is None:
                    break
                a["value"] = c["value_wei"] / 1e18
                actions.append(a)
            if len(actions) != len(p["calls"]):
                drop["decode"] += 1
                continue
            seen_intents.add(intent)
            p.update(intent=intent, executor=executor_of(p["governor"]), actions=actions)
            fraw.write(json.dumps(p) + "\n")

            user_input = f"User intent:\n{intent}"
            if len(actions) == 1:
                a, c = actions[0], p["calls"][0]
                output = json.dumps(a, ensure_ascii=False)
                primary, sub = tag_item({"contract": a["contract"], "function": a["function"],
                                         "input": user_input, "output": output})
                rec = {
                    "instruction": single_instr, "input": user_input, "output": output,
                    "contract": a["contract"], "function": a["function"],
                    "primary_category": primary, "sub_category": sub,
                    "tx_hash": p["executed_tx"],
                    "metadata": {
                        "intent": intent,
                        "block_time": dt.datetime.fromtimestamp(p["executed_time"], dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "contract_address": a["contract_address"],
                        "contract_name": a["contract"],
                        "selector": c["calldata"][:10],
                        "input_data": c["calldata"],
                        "from": p["executor"],
                        "value": str(c["value_wei"] / 1e18),
                        "gas_used": p["executed_gas_used"],
                    },
                }
                fs.write(json.dumps(rec, ensure_ascii=False) + "\n")
                kept["single"] += 1
            else:
                rec = {"instruction": multi_instr, "input": user_input,
                       "output": json.dumps(actions, ensure_ascii=False)}
                fm.write(json.dumps(rec, ensure_ascii=False) + "\n")
                kept["multi"] += 1

    print(f"[done] single-step={kept['single']}  multi-step={kept['multi']}  "
          f"dropped: intent={drop['intent']} undecodable={drop['decode']}")
    print(f"       raw provenance: {RAW_FILE}")


if __name__ == "__main__":
    main()
