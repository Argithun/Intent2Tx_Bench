"""Convert multi-step benchmark JSONL into HF viewer-friendly JSONL.

Why this exists:
- The original `multi_steps_intent2tx.jsonl` stores `output` as a nested list
  of objects with highly heterogeneous `params` keys across rows.
- Hugging Face dataset viewer can fail to infer/cast such complex nested
  schemas (especially when used with another split/config expecting string).

This script normalizes `output` to a JSON string so each row has a stable and
simple schema for streaming/viewing.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_INPUT = Path("AgIntent_Benchmark/data/benchmark/multi_steps_intent2tx.jsonl")
DEFAULT_OUTPUT = Path("AgIntent_Benchmark/data/benchmark/hf_multi_steps_intent2tx.jsonl")


def convert(input_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    written = 0

    with input_path.open("r", encoding="utf-8") as fin, output_path.open(
        "w", encoding="utf-8"
    ) as fout:
        for line in fin:
            if not line.strip():
                continue
            total += 1
            record = json.loads(line)

            # Normalize `output` to a JSON string for stable HF schema.
            output_value = record.get("output")
            if isinstance(output_value, (list, dict)):
                record["output"] = json.dumps(output_value, ensure_ascii=False)
            elif output_value is None:
                record["output"] = "[]"
            else:
                record["output"] = str(output_value)

            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

    print("[done] hf multi-step file generated")
    print(f"  input : {input_path}")
    print(f"  output: {output_path}")
    print(f"  rows  : {written}/{total}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    convert(input_path=args.input, output_path=args.output)


if __name__ == "__main__":
    main()

