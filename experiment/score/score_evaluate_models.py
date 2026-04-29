import json
import os
import re
from pathlib import Path
from collections import defaultdict

# 直接复用你的评测逻辑
from static_score_single_multi import (
    safe_load_json,
    calculate_metrics,
    WEIGHTS
)

LOG_DIR = "../evaluate_models/log"


# ============================================================
# 文件名解析
# ============================================================

def parse_filename(filename):
    """
    <task name>_<model name>_<mode>_results.jsonl
    """
    name = filename.replace("_results.jsonl", "")
    parts = name.split("_")

    task = parts[0] + "_" + parts[1]    # zero_shot / three_shot
    mode = parts[-1]                    # single / multi
    model = "_".join(parts[2:-1])       # model name

    return task, model, mode


# ============================================================
# 单文件评估（完整复用 multi-step 逻辑）
# ============================================================

def evaluate_file(file_path):

    stats = defaultdict(list)
    total_count = 0

    with open(file_path, "r", encoding="utf-8") as f:

        for line in f:

            try:
                item = json.loads(line)
            except:
                print(f"Warning: Failed to parse line: {line[:100]}... in {file_path}")
                continue

            if item.get("llm_output") == "ERROR":
                continue

            total_count += 1

            gold = safe_load_json(item["output"])
            pred = safe_load_json(item["llm_output"])

            # ===== 关键：multi-step 处理 =====
            if isinstance(gold, list):

                step_scores = []

                pred_list = pred if isinstance(pred, list) else [pred]

                for i in range(len(gold)):

                    p_step = pred_list[i] if i < len(pred_list) else None

                    step_scores.append(
                        calculate_metrics(gold[i], p_step)
                    )

                combined_m = {
                    k: sum(s[k] for s in step_scores) / len(step_scores)
                    for k in step_scores[0]
                }

            else:

                combined_m = calculate_metrics(gold, pred)

            for k, v in combined_m.items():
                stats[k].append(v)

    # ===== 计算平均指标 =====

    results = {}

    final_score = 0

    for k, v in stats.items():

        avg = sum(v) / total_count if total_count > 0 else 0

        results[k] = avg

        final_score += avg * WEIGHTS[k]

    results["final"] = final_score
    results["samples"] = total_count

    return results


# ============================================================
# Markdown 表格生成
# ============================================================

def generate_markdown(results):

    models = sorted(set(r["model"] for r in results))

    tasks = ["zero_shot", "three_shot"]
    modes = ["single", "multi"]

    md = []

    md.append("| Model | Format | Logic | Param | Pass@1 | Final |")
    md.append("|------|------|------|------|------|------|")
    md.append("|  | ZS-S / ZS-M / 3S-S / 3S-M |  |  |  |  |")

    for model in models:

        row_values = {
            "format": [],
            "logic": [],
            "param": [],
            "pass_at_1": [],
            "final": []
        }

        for task in tasks:
            for mode in modes:

                r = next(
                    (x for x in results
                     if x["model"] == model.replace("_", " ")
                     and x["task"] == task
                     and x["mode"] == mode),
                    None
                )

                if r is None:
                    for k in row_values:
                        row_values[k].append("-")
                    continue

                row_values["format"].append(f"{r['format']:.3f}")
                row_values["logic"].append(f"{r['logic']:.3f}")
                row_values["param"].append(f"{r['param']:.3f}")
                row_values["pass_at_1"].append(f"{r['pass_at_1']:.3f}")
                row_values["final"].append(f"{r['final']:.3f}")

        md.append(
            f"| {model} | "
            f"{'/'.join(row_values['format'])} | "
            f"{'/'.join(row_values['logic'])} | "
            f"{'/'.join(row_values['param'])} | "
            f"{'/'.join(row_values['pass_at_1'])} | "
            f"**{'/'.join(row_values['final'])}** |"
        )

    return "\n".join(md)


def generate_latex_table(results):
    """
    NeurIPS 风格：每个 setting 内包含 Final
    """

    models = sorted(set(r["model"] for r in results))

    tasks = ["zero_shot", "three_shot"]
    modes = ["single", "multi"]

    def get_metrics(model, task, mode):
        r = next(
            (x for x in results
             if x["model"] == model
             and x["task"] == task
             and x["mode"] == mode),
            None
        )
        if r is None:
            return ["-"] * 5

        return [
            f"{r['format']:.2f}",
            f"{r['logic']:.2f}",
            f"{r['param']:.2f}",
            f"{r['pass_at_1']:.2f}",
            f"{r['final']:.2f}",
        ]

    lines = []

    lines.append(r"\begin{table*}[t]")
    lines.append(r"\centering")
    lines.append(r"\scriptsize")
    lines.append(r"\setlength{\tabcolsep}{3pt}")
    lines.append(r"\begin{tabular}{l|ccccc|ccccc|ccccc|ccccc}")
    lines.append(r"\toprule")

    # ===== Header 1 =====
    lines.append(
        r"& \multicolumn{5}{c|}{Direct, Single-step} "
        r"& \multicolumn{5}{c|}{Direct, Multi-step} "
        r"& \multicolumn{5}{c|}{Retrieval, Single-step} "
        r"& \multicolumn{5}{c}{Retrieval, Multi-step} \\"
    )

    # ===== Header 2 =====
    lines.append(
        r"Model "
        r"& $S_{fmt}$ & $S_{log}$ & $S_{prm}$ & $S_{pass}$ & $S_{final}$ "
        r"& $S_{fmt}$ & $S_{log}$ & $S_{prm}$ & $S_{pass}$ & $S_{final}$ "
        r"& $S_{fmt}$ & $S_{log}$ & $S_{prm}$ & $S_{pass}$ & $S_{final}$ "
        r"& $S_{fmt}$ & $S_{log}$ & $S_{prm}$ & $S_{pass}$ & $S_{final}$ \\"
    )

    lines.append(r"\midrule")

    # ===== Rows =====
    for model in models:

        row = [model.replace("_", " ")]

        for task in tasks:
            for mode in modes:
                row.extend(get_metrics(model, task, mode))

        lines.append(" & ".join(row) + r" \\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")

    lines.append(
        r"\caption{Evaluation results across direct and retrieval settings. "
        r"Each setting reports format ($S_{fmt}$), logic ($S_{log}$), parameter accuracy ($S_{prm}$), pass@1 ($S_{pass}$), and final weighted score ($S_{final}$).}"
    )

    lines.append(r"\end{table*}")

    return "\n".join(lines)

# ============================================================
# 主程序
# ============================================================

def main():

    log_dir = Path(LOG_DIR)

    results = []

    for file in sorted(log_dir.glob("*_results.jsonl")):

        task, model, mode = parse_filename(file.name)

        metrics = evaluate_file(file)

        results.append({
            "task": task,
            "model": model,
            "mode": mode,
            **metrics
        })

    md_table = generate_markdown(results)

    print("\n\n===== Evaluation Results (Markdown) =====\n")

    print(md_table)

    latex_table = generate_latex_table(results)

    print("\n\n===== LaTeX Table =====\n")

    print(latex_table)


if __name__ == "__main__":
    main()