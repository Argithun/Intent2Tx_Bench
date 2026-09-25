#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge the governance intent->tx pairs (12_collect_governance_intents.py) into the HF benchmark.

Records are appended to the existing single-step / multi-step splits in the same format, without any
extra field. The original files are copied to benchmark/pre_governance/ first, and the dataset card's
example counts are updated. Re-running is safe: records already present (same input text) are skipped.
"""
import json
import re
import shutil
from pathlib import Path

BENCH = Path("benchmark")
BACKUP = BENCH / "pre_governance"
SPLITS = [
    (Path("governance/hf_single_step_governance.jsonl"), BENCH / "hf_single_step_intent2tx.jsonl"),
    (Path("governance/hf_multi_steps_governance.jsonl"), BENCH / "hf_multi_steps_intent2tx.jsonl"),
]
README = BENCH / "README.md"


def read_jsonl(p):
    with p.open() as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    BACKUP.mkdir(exist_ok=True)
    counts = {}
    for new_path, bench_path in SPLITS:
        backup = BACKUP / bench_path.name
        if not backup.exists():                       # keep the very first original
            shutil.copy2(bench_path, backup)
        base = read_jsonl(backup)
        seen = {r["input"] for r in base}
        added = [r for r in read_jsonl(new_path) if r["input"] not in seen]
        with bench_path.open("w") as f:
            for r in base + added:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        counts[bench_path.name] = (len(base), len(added), len(base) + len(added))
        print(f"[merge] {bench_path.name}: {len(base)} + {len(added)} = {len(base) + len(added)}")

    single = counts["hf_single_step_intent2tx.jsonl"][2]
    multi = counts["hf_multi_steps_intent2tx.jsonl"][2]
    card = README.read_text()
    card = re.sub(r"- Total examples: [\d,]+", f"- Total examples: {single + multi:,}", card)
    card = re.sub(r"- `single_step`: [\d,]+ examples", f"- `single_step`: {single:,} examples", card)
    card = re.sub(r"- `multi_step`: [\d,]+ examples", f"- `multi_step`: {multi:,} examples", card)
    README.write_text(card)
    print(f"[card] updated counts: single={single:,} multi={multi:,}")


if __name__ == "__main__":
    main()
