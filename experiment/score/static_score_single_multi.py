import json
import sys
import os
import re
from pathlib import Path
from collections import defaultdict

# ============================================================
# 指标配置 (Weights)
# ============================================================
WEIGHTS = {
    "format": 0.10,   # JSON 解析成功率
    "logic": 0.30,    # Contract + Function 匹配度
    "param": 0.20,    # Params 内部 Key/Value 平均得分
    "pass_at_1": 0.40 # 整体完全一致 (Hard Match)
}

# ============================================================
# 工具函数
# ============================================================

def safe_load_json(text):
    if not text:
        return None
    if isinstance(text, list) or isinstance(text, dict):
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

    end_obj = text.rfind("}")
    end_arr = text.rfind("]")

    end = max(end_obj, end_arr)

    if end == -1 or end <= start:
        return None

    json_str = text[start:end + 1].strip("`\n ")

    try:
        return json.loads(json_str)
    except:
        return None

def normalize(s):
    """字符串标准化：去空格、转小写"""
    return str(s).strip().lower()

def compare_params(gold_params, pred_params):
    """
    深度对比参数：计算 Key 的召回率以及 Value 的准确度
    返回 0.0 ~ 1.0 之间的得分
    """
    if not gold_params: return 1.0 if not pred_params else 0.5
    if not pred_params: return 0.0
    
    scores = []
    gold_keys = set(gold_params.keys())
    pred_keys = set(pred_params.keys())
    
    all_keys = gold_keys | pred_keys
    for k in all_keys:
        if k in gold_keys and k in pred_keys:
            g_item = gold_params[k]
            p_item = pred_params[k]
            # 检查 type 和 val
            type_match = normalize(g_item.get("type")) == normalize(p_item.get("type"))
            val_match = normalize(g_item.get("val")) == normalize(p_item.get("val"))
            
            # Key 匹配基础分 0.4, Type 匹配 0.3, Val 匹配 0.3
            scores.append(0.4 + (0.3 if type_match else 0) + (0.3 if val_match else 0))
        else:
            # 漏掉 Key 或多出 Key 扣分
            scores.append(0.0)
            
    return sum(scores) / len(scores) if scores else 1.0

# ============================================================
# 核心评估逻辑
# ============================================================

def calculate_metrics(gold_obj, pred_obj):
    """计算单条记录的四个核心指标"""
    m = {"format": 0.0, "logic": 0.0, "param": 0.0, "pass_at_1": 0.0}

    # pred 不是 dict，直接判为解析失败
    if not isinstance(pred_obj, dict):
        return m

    # 1. Format Score
    m["format"] = 1.0

    # 2. Logic Score (Contract + Address + Function)
    try:
        c_match = normalize(gold_obj.get("contract_address")) == normalize(pred_obj.get("contract_address"))
    except:
        c_match = 0
    try:
        f_match = normalize(gold_obj.get("function")) == normalize(pred_obj.get("function"))
    except:
        f_match = 0
    try:
        n_match = normalize(gold_obj.get("contract")) == normalize(pred_obj.get("contract"))
    except:
        n_match = 0

    m["logic"] = (0.4 * c_match) + (0.4 * f_match) + (0.2 * n_match)

    # =========================================================
    # 3. Param Score (把 ETH value 作为参数纳入计算)
    # =========================================================
    try:
        gold_params = dict(gold_obj.get("params", {}))
        pred_params = dict(pred_obj.get("params", {}))

        # 将 value 注入 params
        if gold_obj.get("value") is not None:
            gold_params["__eth_value__"] = {
                "type": "uint256",
                "val": str(gold_obj.get("value"))
            }

        if pred_obj.get("value") is not None:
            pred_params["__eth_value__"] = {
                "type": "uint256",
                "val": str(pred_obj.get("value"))
            }

        m["param"] = compare_params(gold_params, pred_params)

    except:
        m["param"] = 0.0

    # =========================================================
    # 4. Pass@1 (Hard Match)
    # =========================================================
    try:
        if c_match and f_match and m["param"] == 1.0:
            m["pass_at_1"] = 1.0
    except:
        pass

    return m

def evaluate_file(file_path):
    print(f"\nEvaluating: {file_path}")
    print("=" * 60)
    
    stats = defaultdict(list)
    category_stats = defaultdict(lambda: defaultdict(list))
    total_count = 0

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            if item.get("llm_output") == "ERROR": continue
            
            total_count += 1
            gold = safe_load_json(item["output"])
            pred = safe_load_json(item["llm_output"])
            cat = item.get("primary_category", "Unknown")

            # 处理多步任务（List）与单步任务（Dict）
            if isinstance(gold, list):
                # 多步任务取平均分
                step_scores = []
                pred_list = pred if isinstance(pred, list) else [pred]
                for i in range(len(gold)):
                    p_step = pred_list[i] if i < len(pred_list) else None
                    step_scores.append(calculate_metrics(gold[i], p_step))
                
                combined_m = {k: sum(s[k] for s in step_scores)/len(gold) for k in step_scores[0]}
            else:
                combined_m = calculate_metrics(gold, pred)

            # 汇总
            for k, v in combined_m.items():
                stats[k].append(v)
                category_stats[cat][k].append(v)

    # 打印全局结果
    print(f"Total Samples: {total_count}")
    final_score = 0
    results_summary = {}
    for k, v in stats.items():
        avg = sum(v) / total_count if total_count > 0 else 0
        results_summary[k] = avg
        final_score += avg * WEIGHTS[k]
        print(f"{k.upper():<12}: {avg:.4f} (Weight: {WEIGHTS[k]:.0%})")

    print("-" * 60)
    print(f"FINAL WEIGHTED SCORE: {final_score:.4f}")
    print("=" * 60)

    # 打印分分类结果
    print("\nCategory-wise Breakdown (Pass@1):")
    for cat, c_m in category_stats.items():
        cat_pass = sum(c_m["pass_at_1"]) / len(c_m["pass_at_1"])
        print(f"- {cat:<20}: {cat_pass:.4f} (n={len(c_m['pass_at_1'])})")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python static_score_single_multi.py <results.jsonl>")
    else:
        evaluate_file(sys.argv[1])