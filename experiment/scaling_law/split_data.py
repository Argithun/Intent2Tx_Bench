import json
import random
import os
from collections import defaultdict

# 配置路径
SINGLE_FILE = "../../data/benchmark/tagged_single_step_intent2tx.jsonl"
TRAIN_FILE = "./fine_tuning.jsonl"
TEST_FILE = "./test.jsonl"

def sample_single():
    buckets = defaultdict(list)
    all_data = []

    # 1. 读取所有数据并按类别分桶
    with open(SINGLE_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            item = json.loads(line)
            buckets[item["primary_category"]].append(item)
            all_data.append(item)

    sampled_test = []

    # 2. 执行你的采样逻辑 (约 3% 作为测试集)
    for cat, items in buckets.items():
        k = max(5, int(len(items) * 0.03))
        k = min(k, len(items))
        sampled_test.extend(random.sample(items, k))

    # 3. 构建测试集的 input 集合，用于过滤
    # 使用 input 作为唯一键（Web3 意图通常 input 是唯一的）
    test_inputs = {item["input"] for item in sampled_test}

    # 4. 剩余数据全部进入微调集
    fine_tuning_data = [item for item in all_data if item["input"] not in test_inputs]

    return sampled_test, fine_tuning_data

def save_jsonl(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

if __name__ == "__main__":
    print(f"Reading from: {SINGLE_FILE}")
    
    test_set, train_set = sample_single()
    
    # 保存文件
    save_jsonl(test_set, TEST_FILE)
    save_jsonl(train_set, TRAIN_FILE)
    
    print("-" * 30)
    print(f"Successfully split data:")
    print(f"Total samples: {len(test_set) + len(train_set)}")
    print(f"Test set ({TEST_FILE}): {len(test_set)} samples")
    print(f"Fine-tuning set ({TRAIN_FILE}): {len(train_set)} samples")