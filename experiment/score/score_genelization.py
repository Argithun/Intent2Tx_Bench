import json
import re
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict

from static_score_single_multi import (
    safe_load_json,
    calculate_metrics,
    WEIGHTS
)

LOG_DIR = "../genelization/log"


# ============================================================
# 文件名解析
# ============================================================

def parse_filename(filename):
    """
    zero_shot_Qwen3_14B_BenchmarkBase_single_results.jsonl
    """

    m = re.search(r"zero_shot_Qwen3_14B_Benchmark(.+?)_single_results.jsonl", filename)

    if not m:
        raise ValueError(f"Cannot parse model from {filename}")

    model = m.group(1)

    return model


# ============================================================
# 单文件评估（按 category + metrics）
# ============================================================

def evaluate_file(file_path):

    category_stats = defaultdict(lambda: defaultdict(list))

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

            cat = item.get("primary_category", "Unknown")

            # ===== multi-step =====
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

            # Final
            final = sum(combined_m[k] * WEIGHTS[k] for k in WEIGHTS)
            combined_m["final"] = final

            # 记录
            for k, v in combined_m.items():
                category_stats[cat][k].append(v)

    # ===== 计算平均 =====

    results = {}

    for cat, metric_dict in category_stats.items():

        results[cat] = {}

        for metric, vals in metric_dict.items():

            if len(vals) == 0:
                results[cat][metric] = 0
            else:
                results[cat][metric] = sum(vals) / len(vals)

    return results


# ============================================================
# Markdown 表格生成
# ============================================================

def generate_markdown(results):

    models = sorted(results.keys())

    # 收集所有 category
    all_categories = set()

    for r in results.values():
        all_categories.update(r.keys())

    categories = sorted(all_categories)

    md = []

    header = "| Category | " + " | ".join(models) + " |"
    sep = "|------|" + "|".join(["------"] * len(models)) + "|"

    md.append(header)
    md.append(sep)

    for cat in categories:

        row = [cat]

        for model in models:

            r = results[model]

            metrics = r.get(cat, {})

            fmt = metrics.get("format", 0)
            logic = metrics.get("logic", 0)
            param = metrics.get("param", 0)
            p1 = metrics.get("pass_at_1", 0)
            final = metrics.get("final", 0)

            cell = f"{fmt:.3f}/{logic:.3f}/{param:.3f}/{p1:.3f}/{final:.3f}"

            row.append(cell)

        md.append("| " + " | ".join(row) + " |")

    return "\n".join(md)



import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import matplotlib.colors as mcolors


def lighten_color(color, amount=0.5):
    """生成浅色版本"""
    c = mcolors.to_rgb(color)
    return tuple(1 - (1 - x) * (1 - amount) for x in c)


import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import matplotlib.colors as mcolors

def lighten_color(color, amount=0.5):
    """
    更稳健的颜色变亮函数
    """
    try:
        c = mcolors.cnames[color]
    except:
        c = color
    c = mcolors.to_rgb(c)
    return mcolors.to_rgb(tuple([1 - (1 - x) * amount for x in c]))

def plot_generalization(results, save_path="./generalization_plot_pro.pdf"):
    # ===== 1. 全局样式设置 (科技论文核心) =====
    plt.rcParams.update({
        "font.family": "serif",
    "font.serif": ["DejaVu Serif", "Liberation Serif", "STIXGeneral"], # 备选列表
        "font.size": 10,
        "axes.linewidth": 0.8,
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
        "pdf.fonttype": 42, # 确保字体在PDF中可编辑
        "ps.fonttype": 42
    })

    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    models = sorted(results.keys())

    # ===== 2. 模型识别 =====
    base_model = next((m for m in models if "base" in m.lower()), None)
    ft_model = next((m for m in models if m != base_model), None)

    if not base_model or not ft_model:
        raise ValueError("Need one base model and one finetuned model")

    categories = sorted({cat for r in results.values() for cat in r.keys()})
    metrics = ["format", "logic", "param", "pass_at_1", "final"]

    # ===== 3. 调色盘与纹理 (高级审美) =====
    # 使用互补且不刺眼的科技感色系
    metric_colors = {
        "format": "#4878D0",    # 深蓝色
        "logic": "#6ACC64",     # 柔和绿
        "param": "#D65F5F",     # 砖红
        "pass_at_1": "#956CB4", # 丁香紫
        "final": "#D5BB67",     # 哑光金
    }
    
    # Base 用斜纹理，FT 用实色，这是区分实验组与对照组的经典做法
    base_hatch = "////" 
    edge_color = "#333333" # 深灰边框比纯黑更高级

    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300) # 提高分辨率

    x = np.arange(len(categories))
    group_width = 0.85
    sub_width = group_width / len(metrics)
    bar_width = sub_width * 0.42  # 稍微留一点缝隙

    # ===== 4. 核心绘图逻辑 =====
    for mi, metric in enumerate(metrics):
        base_vals = [results[base_model].get(cat, {}).get(metric, 0) for cat in categories]
        ft_vals = [results[ft_model].get(cat, {}).get(metric, 0) for cat in categories]

        color = metric_colors[metric]
        x_offset = x - group_width/2 + (mi + 0.5) * sub_width

        # Base Model (带纹理，颜色稍浅)
        ax.bar(
            x_offset - bar_width/2, base_vals, 
            width=bar_width, 
            color=lighten_color(color, 0.4),
            edgecolor=color, # 边框使用原色
            linewidth=0.8,
            hatch=base_hatch,
            label=None
        )

        # Finetuned Model (实心，颜色深)
        ax.bar(
            x_offset + bar_width/2, ft_vals, 
            width=bar_width, 
            color=color,
            edgecolor=edge_color,
            linewidth=0.6,
            label=None
        )

    # ===== 5. 坐标轴美化 =====
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=11, fontweight='bold')
    ax.set_ylabel("Normalized Score", fontsize=12, labelpad=10)
    
    # 细化网格：仅保留Y轴水平线，且置于底层
    ax.grid(axis='y', linestyle='-', linewidth=0.5, color='#e0e0e0', alpha=0.7, zorder=0)
    ax.set_axisbelow(True)

    # 范围调整
    ax.set_ylim(0, 1.1) # 科技论文通常留白至1.1以放置图例
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(1.2)
    ax.spines["bottom"].set_linewidth(1.2)

    # ===== 6. 整合双图例 (顶级排版) =====
    # 图例1: Metric (颜色块)
    metric_legend_elements = [
        plt.Rectangle((0, 0), 1, 1, facecolor=metric_colors[m], label=m.replace("_", " ").title())
        for m in metrics
    ]
    leg1 = ax.legend(
        handles=metric_legend_elements,
        loc="upper left",
        bbox_to_anchor=(0, 1.02),
        ncol=5,
        frameon=False,
        columnspacing=1.2,
        handletextpad=0.4,
        fontsize=9
    )

    # 图例2: Model Type (纹理 vs 实心)
    model_legend_elements = [
        plt.Rectangle((0, 0), 1, 1, facecolor="white", edgecolor=edge_color, hatch=base_hatch, label="Base Model"),
        plt.Rectangle((0, 0), 1, 1, facecolor="gray", edgecolor=edge_color, label="Finetuned")
    ]
    leg2 = ax.legend(
        handles=model_legend_elements,
        loc="upper right",
        bbox_to_anchor=(1, 1.02),
        ncol=2,
        frameon=False,
        handlelength=1.5,
        fontsize=9
    )
    
    ax.add_artist(leg1) # 重新添加第一个图例

    plt.tight_layout()
    plt.savefig(save_path, bbox_inches='tight')
    plt.show()


# ============================================================
# 主程序
# ============================================================

def main():

    log_dir = Path(LOG_DIR)

    if not log_dir.exists():
        raise ValueError(f"Directory not found: {LOG_DIR}")

    results = {}

    for file in sorted(log_dir.glob("*_results.jsonl")):

        model = parse_filename(file.name)

        metrics = evaluate_file(file)

        results[model] = metrics

    md_table = generate_markdown(results)

    print("\n===== Generalization Results =====\n")
    print(md_table)

    plot_generalization(results)


if __name__ == "__main__":
    main()