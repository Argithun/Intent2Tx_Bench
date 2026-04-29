"""Build a Huggingface-ready JSONL dataset from the tagged single-step
intent->tx benchmark.

For every record in ``tagged_single_step_intent2tx.jsonl`` the script:

1. Strips the leading ``"User intent:\n"`` header from ``input`` to recover
   the raw intent text.
2. Looks up the corresponding ``tx_hash`` in ``intent_action_pairs.jsonl``
   using the intent text as the key.
3. Uses that ``tx_hash`` to fetch the original on-chain call information from
   ``selected_calls_for_intents.jsonl``.
4. Emits a new record that keeps the original benchmark fields and attaches
   the resolved ``tx_hash`` plus the raw call as ``metadata``.

Records that cannot be matched are skipped and reported at the end.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

USER_INTENT_PREFIX = "User intent:\n"

DEFAULT_TAGGED_PATH = Path(
    "AgIntent_Benchmark/data/benchmark/tagged_single_step_intent2tx.jsonl"
)
DEFAULT_PAIRS_PATH = Path(
    "AgIntent_Benchmark/data/txs_intents/intent_action_pairs.jsonl"
)
DEFAULT_CALLS_PATH = Path(
    "AgIntent_Benchmark/data/txs_intents/selected_calls_for_intents.jsonl"
)
DEFAULT_OUTPUT_PATH = Path(
    "AgIntent_Benchmark/data/benchmark/hf_single_step_intent2tx.jsonl"
)


def strip_intent_header(raw_input: str) -> str:
    """Return the intent text without the standard ``User intent:\n`` prefix."""
    if raw_input.startswith(USER_INTENT_PREFIX):
        return raw_input[len(USER_INTENT_PREFIX):].strip()
    return raw_input.strip()


def load_intent_to_tx(path: Path) -> dict[str, str]:
    """Build a ``intent_text -> tx_hash`` mapping.

    Duplicate intents are kept as the first occurrence; collisions are
    counted so that the caller can warn about them.
    """
    mapping: dict[str, str] = {}
    duplicates: dict[str, int] = defaultdict(int)
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            intent = obj["intent"].strip()
            tx_hash = obj["tx_hash"]
            if intent in mapping and mapping[intent] != tx_hash:
                duplicates[intent] += 1
                continue
            mapping[intent] = tx_hash
    if duplicates:
        print(
            f"[warn] {len(duplicates)} intent texts mapped to multiple tx hashes; "
            "kept the first occurrence."
        )
    return mapping


def load_calls_by_hash(path: Path) -> dict[str, dict[str, Any]]:
    """Build a ``tx_hash -> raw call record`` mapping."""
    mapping: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            mapping[obj["tx_hash"]] = obj
    return mapping


def build_dataset(
    tagged_path: Path,
    pairs_path: Path,
    calls_path: Path,
    output_path: Path,
) -> None:
    print(f"[info] loading intent->tx mapping from {pairs_path}")
    intent_to_tx = load_intent_to_tx(pairs_path)
    print(f"[info] {len(intent_to_tx):,} unique intents indexed")

    print(f"[info] loading raw calls from {calls_path}")
    calls_by_hash = load_calls_by_hash(calls_path)
    print(f"[info] {len(calls_by_hash):,} unique tx hashes indexed")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    written = 0
    missing_intent = 0
    missing_call = 0

    print(f"[info] writing dataset to {output_path}")
    with tagged_path.open("r", encoding="utf-8") as fin, output_path.open(
        "w", encoding="utf-8"
    ) as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            total += 1
            entry = json.loads(line)

            intent_text = strip_intent_header(entry["input"])
            tx_hash = intent_to_tx.get(intent_text)
            if tx_hash is None:
                missing_intent += 1
                continue

            raw_call = calls_by_hash.get(tx_hash)
            if raw_call is None:
                missing_call += 1
                continue

            record = {
                "instruction": entry.get("instruction", ""),
                "input": entry["input"],
                "output": entry["output"],
                "contract": entry.get("contract"),
                "function": entry.get("function"),
                "primary_category": entry.get("primary_category"),
                "sub_category": entry.get("sub_category"),
                "tx_hash": tx_hash,
                "metadata": {
                    "intent": intent_text,
                    "block_time": raw_call.get("block_time"),
                    "contract_address": raw_call.get("contract"),
                    "contract_name": raw_call.get("contract_name"),
                    "selector": raw_call.get("selector"),
                    "input_data": raw_call.get("input"),
                    "from": raw_call.get("from"),
                    "value": raw_call.get("value"),
                    "gas_used": raw_call.get("gas_used"),
                },
            }
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

    print("\n[done] dataset built")
    print(f"  total tagged records : {total:,}")
    print(f"  written              : {written:,}")
    print(f"  missing intent match : {missing_intent:,}")
    print(f"  missing call match   : {missing_call:,}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tagged",
        type=Path,
        default=DEFAULT_TAGGED_PATH,
        help="Path to tagged_single_step_intent2tx.jsonl",
    )
    parser.add_argument(
        "--pairs",
        type=Path,
        default=DEFAULT_PAIRS_PATH,
        help="Path to intent_action_pairs.jsonl",
    )
    parser.add_argument(
        "--calls",
        type=Path,
        default=DEFAULT_CALLS_PATH,
        help="Path to selected_calls_for_intents.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to write the merged Huggingface-ready JSONL dataset",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_dataset(
        tagged_path=args.tagged,
        pairs_path=args.pairs,
        calls_path=args.calls,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
