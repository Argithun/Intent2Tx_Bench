import json
import os

# ==========================
# 1. 配置路径与分类规则
# ==========================
SOURCE_FILE = "../../data/benchmark/tagged_single_step_intent2tx.jsonl"
TRAIN_OUT = "./fine_tuning.jsonl"
TEST_OUT = "./test.jsonl"

# 定义训练集包含的类别
TRAIN_CATEGORIES = {
    "Transfer", "Swap", "TokenLifecycle", 
    "Lending", "Staking", "AssetTransformation"
}

# 定义测试集包含的类别
TEST_CATEGORIES = {
    "Other", "Governance", "Liquidity", "NFT", "Vault"
}

def split_data():
    if not os.path.exists(SOURCE_FILE):
        print(f"Error: 找不到源文件 {SOURCE_FILE}")
        return

    train_count = 0
    test_count = 0
    ignored_count = 0

    print(f"开始读取: {SOURCE_FILE}")

    with open(SOURCE_FILE, 'r', encoding='utf-8') as f, \
         open(TRAIN_OUT, 'w', encoding='utf-8') as f_train, \
         open(TEST_OUT, 'w', encoding='utf-8') as f_test:

        for line in f:
            line = line.strip()
            if not line:
                continue
            
            try:
                item = json.loads(line)
                category = item.get("primary_category")

                if category in TRAIN_CATEGORIES:
                    f_train.write(json.dumps(item, ensure_ascii=False) + "\n")
                    train_count += 1
                elif category in TEST_CATEGORIES:
                    f_test.write(json.dumps(item, ensure_ascii=False) + "\n")
                    test_count += 1
                else:
                    # 如果有类别不在上述两个集合中，记录下来
                    ignored_count += 1
            except json.JSONDecodeError:
                print("跳过一行损坏的 JSON 数据")

    print("-" * 30)
    print("划分完成！")
    print(f"写入训练集 ({TRAIN_OUT}): {train_count} 条")
    print(f"写入测试集 ({TEST_OUT}): {test_count} 条")
    if ignored_count > 0:
        print(f"未匹配分类（已忽略）: {ignored_count} 条")
    print("-" * 30)

if __name__ == "__main__":
    split_data()