import json
import re
from pathlib import Path
from collections import defaultdict

LOG_DIR = "../simulation_execution/log"


# ============================================================
# 文件名解析
# ============================================================

def parse_filename(filename):
    """
    simulated_<task>_<model>_single_results.jsonl
    """

    m = re.match(r"simulated_(zero_shot|three_shot)_(.+?)_single_results.jsonl", filename)

    if not m:
        raise ValueError(f"Cannot parse filename: {filename}")

    task = m.group(1)
    model = m.group(2)

    return task, model


# ============================================================
# 单文件评估
# ============================================================

def evaluate_file(file_path):

    total = 0
    exec_ok = 0
    state_ok = 0

    with open(file_path, "r", encoding="utf-8") as f:

        for line in f:

            try:
                item = json.loads(line)
            except:
                continue

            # 只看 gold_success = True
            if not item.get("gold_success", False):
                continue

            total += 1

            if item.get("pred_success", False):
                exec_ok += 1

            if item.get("is_state_equivalent", False):
                state_ok += 1

    if total == 0:
        return {
            "exec": 0.0,
            "state_eq": 0.0,
            "samples": 0
        }

    return {
        "exec": exec_ok / total,
        "state_eq": state_ok / total,
        "samples": total
    }


# ============================================================
# Markdown 表格
# ============================================================

def generate_markdown(results):

    models = sorted(set(m for (_, m) in results.keys()))

    tasks = ["zero_shot", "three_shot"]

    md = []
    md.append("Exec: Executability; StateEq: State Equivalent")
    md.append("| Model | Zero-shot (Exec / StateEq) | Three-shot (Exec / StateEq) |")
    md.append("|------|-----------------------------|-----------------------------|")

    for model in models:

        row = [model]

        for task in tasks:

            r = results.get((task, model), None)

            if r is None or r["samples"] == 0:
                cell = "-"
            else:
                cell = f"{r['exec']:.3f}/{r['state_eq']:.3f}"

            row.append(cell)

        md.append("| " + " | ".join(row) + " |")

    return "\n".join(md)


# def generate_latex_table(results):
    """
    生成 NeurIPS 风格 LaTeX 表格
    """

    models = sorted(set(m for (_, m) in results.keys()))
    tasks = ["zero_shot", "three_shot"]

    lines = []

    lines.append("\\begin{table}[t]")
    lines.append("\\centering")
    lines.append("\\small")
    lines.append("\\setlength{\\tabcolsep}{6pt}")
    lines.append("\\begin{tabular}{lcccc}")
    lines.append("\\toprule")

    # ===== 表头 =====
    lines.append(
        " & \\multicolumn{2}{c}{Direct} & \\multicolumn{2}{c}{Retrieval} \\\\"
    )
    lines.append(
        "\\cmidrule(lr){2-3} \\cmidrule(lr){4-5}"
    )
    lines.append(
        "Model & Exec & StateEq  & Exec  & StateEq  \\\\"
    )

    lines.append("\\midrule")

    # ===== 内容 =====
    for model in models:

        row = [model.replace("_", " ")]

        for task in tasks:

            r = results.get((task, model), None)

            if r is None or r["samples"] == 0:
                row.append("-")
                row.append("-")
            else:
                row.append(f"{r['exec']:.3f}")
                row.append(f"{r['state_eq']:.3f}")

        lines.append(" & ".join(row) + " \\\\")

    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")

    # ===== caption =====
    lines.append(
        "\\caption{"
        "Simulation execution performance. "
        "Exec denotes executability, and StateEq denotes state equivalence with the ground truth. "
        "All results are computed over instances with successful ground-truth execution. "
        "}"
    )

    lines.append("\\label{tab:simulation_execution}")
    lines.append("\\end{table}")

    return "\n".join(lines)

def generate_latex_table(results):
    """
    生成并排双表（前8个模型 / 后8个模型）
    """

    models = sorted(set(m for (_, m) in results.keys()))
    tasks = ["zero_shot", "three_shot"]

    # ===== 切分 =====
    split_idx = (len(models) + 1) // 2
    models_left = models[:split_idx]
    models_right = models[split_idx:]

    def build_rows(model_list):
        rows = []
        for model in model_list:

            row = [model.replace("_", " ")]

            for task in tasks:
                r = results.get((task, model), None)

                if r is None or r["samples"] == 0:
                    row.append("-")
                    row.append("-")
                else:
                    row.append(f"{r['exec']:.3f}")
                    row.append(f"{r['state_eq']:.3f}")

            rows.append(" & ".join(row) + " \\\\")
        return rows

    left_rows = build_rows(models_left)
    right_rows = build_rows(models_right)

    # ===== 开始拼 LaTeX =====
    lines = []

    lines.append("\\begin{table*}[t]")
    lines.append("\\centering")
    lines.append("\\small")
    lines.append("\\setlength{\\tabcolsep}{5pt}")

    # 两个表并排
    lines.append("\\begin{tabular}{lcccc @{\hspace{1.5em}} lcccc}")
    lines.append("\\toprule")

    # ===== 表头（双块）=====
    lines.append(
        " & \\multicolumn{2}{c}{Direct} & \\multicolumn{2}{c}{Retrieval} "
        "& "
        " & \\multicolumn{2}{c}{Direct} & \\multicolumn{2}{c}{Retrieval} \\\\"
    )

    lines.append(
        "\\cmidrule(lr){2-3} \\cmidrule(lr){4-5} "
        "\\cmidrule(lr){7-8} \\cmidrule(lr){9-10}"
    )

    lines.append(
        "Model & Exec & StateEq & Exec & StateEq "
        "& "
        "Model & Exec & StateEq & Exec & StateEq \\\\"
    )

    lines.append("\\midrule")

    # ===== 行对齐（关键点）=====
    max_len = max(len(left_rows), len(right_rows))

    for i in range(max_len):

        left = left_rows[i] if i < len(left_rows) else " & & & & \\\\"
        right = right_rows[i] if i < len(right_rows) else " & & & & \\\\"

        # 去掉结尾 \\ 再拼
        left = left.rstrip("\\\\")
        right = right.rstrip("\\\\")

        lines.append(left + " & " + right + " \\\\")

    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")

    # ===== caption =====
    lines.append(
        "\\caption{"
        "Simulation execution performance. "
        "Exec denotes executability, and StateEq denotes state equivalence with the ground truth. "
        "Results are split into two blocks for readability. "
        "}"
    )

    lines.append("\\label{tab:simulation_execution_split}")
    lines.append("\\end{table*}")

    return "\n".join(lines)

# ============================================================
# 主程序
# ============================================================

def main():

    log_dir = Path(LOG_DIR)

    if not log_dir.exists():
        raise ValueError(f"Directory not found: {LOG_DIR}")

    results = {}

    for file in sorted(log_dir.glob("*.jsonl")):

        task, model = parse_filename(file.name)

        metrics = evaluate_file(file)

        results[(task, model)] = metrics

    md_table = generate_markdown(results)

    print("\n===== Simulation Execution Results =====\n")
    print(md_table)

    latex_table = generate_latex_table(results)
    print("\n===== LaTeX Table =====\n")
    print(latex_table)


if __name__ == "__main__":
    main()