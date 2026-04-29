import json
import os
import random
from collections import defaultdict

# 配置路径
FINE_TUNING_FILE = "./fine_tuning.jsonl"
OUTPUT_DIR = "/workspace/train_agintent/model/LLaMA-Factory/data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "agintent_benchmark.jsonl")

def generate_sharegpt_format(target_size):
    if not os.path.exists(FINE_TUNING_FILE):
        print(f"Error: {FINE_TUNING_FILE} not found.")
        return

    # 1. 加载数据并按类别分桶
    buckets = defaultdict(list)
    with open(FINE_TUNING_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            item = json.loads(line)
            # 使用 primary_category 进行分层
            cat = item.get("primary_category", "Other")
            buckets[cat].append(item)

    all_categories = list(buckets.keys())
    total_available = sum(len(v) for v in buckets.values())
    
    if target_size > total_available:
        print(f"Warning: Requested {target_size} but only {total_available} available. Using all.")
        target_size = total_available

    # 2. 分层抽取逻辑
    sampled_data = []
    # 计算每个类别的理想占比
    for cat in all_categories:
        category_items = buckets[cat]
        # 按照该类别在原始数据中的比例分配配额
        category_quota = int((len(category_items) / total_available) * target_size)
        # 确保每个类别至少有数据（如果配额太小则取1，除非本身没数据）
        category_quota = max(1, min(category_quota, len(category_items)))
        
        sampled_data.extend(random.sample(category_items, category_quota))

    # 3. 如果因为取整导致数量不足，随机补齐
    remaining = target_size - len(sampled_data)
    if remaining > 0:
        flattened_pool = [item for item in sum(buckets.values(), []) if item not in sampled_data]
        sampled_data.extend(random.sample(flattened_pool, min(remaining, len(flattened_pool))))

    # 打乱顺序，增加训练随机性
    random.shuffle(sampled_data)

    # 4. 转换为 ShareGPT 格式并保存
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as fout:
        for item in sampled_data:
            # 构建 LLaMA-Factory 要求的结构
            sharegpt_item = {
                "system": item.get("instruction", "").strip(),
                "conversations": [
                    {
                        "from": "human",
                        "value": item.get("input", "").strip()
                    },
                    {
                        "from": "gpt",
                        "value": "```json\n" + item.get("output", "").strip() + "\n```"
                    }
                ]
            }
            fout.write(json.dumps(sharegpt_item, ensure_ascii=False) + '\n')

    print(f"✅ Successfully generated {len(sampled_data)} samples to {OUTPUT_FILE}")

if __name__ == "__main__":
    try:
        size = int(input("请输入需要生成的训练数据体量 (例如 200, 800, 2000, 8000, 14000, 20000, 28776, ...): "))
        generate_sharegpt_format(size)
    except ValueError:
        print("请输入有效的数字。")