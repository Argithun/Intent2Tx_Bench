import json
import re
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np

from static_score_single_multi import (
    safe_load_json,
    calculate_metrics,
    WEIGHTS
)

LOG_DIR = "../scaling_law/log"


# ============================================================
# 文件名解析
# ============================================================

def parse_filename(filename):
    """
    zero_shot_Qwen3_14B_Benchmark<scale>_single_results.jsonl
    """

    name = filename.replace("_results.jsonl", "")

    m = re.search(r"Benchmark(.+?)_single", name)

    if not m:
        raise ValueError(f"Cannot parse scale from {filename}")

    scale = m.group(1)

    return scale


# ============================================================
# 单文件评估（按 category 统计）
# ============================================================

def evaluate_file(file_path):

    stats = defaultdict(list)

    with open(file_path, "r", encoding="utf-8") as f:

        for line in f:

            try:
                item = json.loads(line)
            except:
                continue

            if item.get("llm_output") == "ERROR":
                continue

            gold = safe_load_json(item["output"])
            pred = safe_load_json(item["llm_output"])

            # ===== multi-step 处理 =====
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

            # ===== 记录各 metric =====

            for k in combined_m:
                stats[k].append(combined_m[k])

            final = sum(combined_m[k] * WEIGHTS[k] for k in WEIGHTS)

            stats["final"].append(final)

    # ===== 计算平均值 =====

    results = {}

    for k, v in stats.items():

        if len(v) == 0:
            results[k] = 0
        else:
            results[k] = sum(v) / len(v)

    return results


# ============================================================
# Markdown 表格
# ============================================================

def generate_markdown(results):

    def scale_key(x):
        if x == "Base":
            return (-1, 0)
        try:
            return (0, float(x))
        except:
            return (1, x)

    scales = sorted(results.keys(), key=scale_key)

    metrics = ["format", "logic", "param", "pass_at_1", "final"]

    md = []

    header = "| Scale | Format | Logic | Param | Pass@1 | Final |"
    sep = "|------|------|------|------|------|------|"

    md.append(header)
    md.append(sep)

    for scale in scales:

        r = results[scale]

        md.append(
            f"| {scale} | "
            f"{r.get('format',0):.3f} | "
            f"{r.get('logic',0):.3f} | "
            f"{r.get('param',0):.3f} | "
            f"{r.get('pass_at_1',0):.3f} | "
            f"**{r.get('final',0):.3f}** |"
        )

    return "\n".join(md)


def plot_scaling_curves(results, save_dir="./scaling_plots"):
    """
    Scaling curves（等距横轴版本）
    - categorical x-axis（等距）
    - 显示真实 scale 标签
    - 论文风格配色
    """

    Path(save_dir).mkdir(parents=True, exist_ok=True)

    # ===== scale 排序 =====
    def scale_key(x):
        if x == "Base":
            return -1
        try:
            return float(x)
        except:
            return 1e9

    scales = sorted(results.keys(), key=scale_key)

    # ===== 等距 x 轴 =====
    x_pos = np.arange(len(scales))

    # ===== 更友好的标签（k 格式）=====
    def format_label(s):
        if s == "Base":
            return "Base"
        try:
            v = float(s)
            if v >= 1000:
                return f"{int(v/1000)}k" if v % 1000 == 0 else f"{v/1000:.1f}k"
            return str(int(v))
        except:
            return s

    x_labels = [format_label(s) for s in scales]

    # ===== 论文配色（低饱和）=====
    COLORS = {
        "format": "#4C72B0",     # blue
        "logic": "#55A868",      # green
        "param": "#C44E52",      # red
        "pass_at_1": "#8172B2",  # purple
        "final": "#CCB974",      # gold
    }

    metrics = ["format", "logic", "param", "pass_at_1", "final"]

    for metric in metrics:

        y_vals = [results[s].get(metric, 0) for s in scales]

        plt.figure(figsize=(4, 3))

        # ===== 折线 =====
        plt.plot(
            x_pos,
            y_vals,
            marker='o',
            linewidth=1.8,
            markersize=4,
            color=COLORS[metric]
        )

        # ===== x 轴（等距）=====
        plt.xticks(x_pos, x_labels, rotation=30, fontsize=12)
        plt.yticks(fontsize=12)

        # ===== y 轴范围 =====
        y_min = min(y_vals)
        y_max = max(y_vals)

        margin = (y_max - y_min) * 0.1 if y_max > y_min else 0.05

        plt.ylim(
            max(0, y_min - margin),
            min(1.0, y_max + margin)
        )

        # ===== 标签 =====
        plt.xlabel("Training Instances", fontsize=14)
        plt.ylabel(metric.replace("_", " ").title(), fontsize=14)

        # ===== 网格 =====
        plt.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)

        plt.title(f"{metric} vs Scale", fontsize=14)

        # ===== 去边框（论文风格）=====
        ax = plt.gca()
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # ===== 保存 =====
        save_path = Path(save_dir) / f"{metric}.pdf"
        plt.tight_layout()
        plt.savefig(save_path)
        plt.close()

    print(f"Saved plots to {save_dir}")

# ============================================================
# 主程序
# ============================================================

def main():

    log_dir = Path(LOG_DIR)

    results = {}

    for file in sorted(log_dir.glob("*_results.jsonl")):

        scale = parse_filename(file.name)

        metrics = evaluate_file(file)

        results[scale] = metrics

    md_table = generate_markdown(results)

    print("\n===== Scaling Law Results =====\n")
    print(md_table)

    plot_scaling_curves(results)

if __name__ == "__main__":
    main()