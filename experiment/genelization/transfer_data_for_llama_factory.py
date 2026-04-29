import json
import os

# ==========================
# 1. 配置路径
# ==========================
# 刚才划分好的训练集源文件
INPUT_FILE = "./fine_tuning.jsonl" 
# LLaMA-Factory 数据目录
OUTPUT_DIR = "/workspace/train_agintent/model/LLaMA-Factory/data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "agintent_benchmark.jsonl")

def convert_to_sharegpt():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: 找不到源文件 {INPUT_FILE}")
        return

    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"开始转化: {INPUT_FILE} -> {OUTPUT_FILE}")
    
    count = 0
    with open(INPUT_FILE, 'r', encoding='utf-8') as f_in, \
         open(OUTPUT_FILE, 'w', encoding='utf-8') as f_out:
        
        for line in f_in:
            line = line.strip()
            if not line:
                continue
                
            try:
                item = json.loads(line)
                
                # 构造符合 LLaMA-Factory 注册配置的 ShareGPT 结构
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
                
                # 写入 jsonl
                f_out.write(json.dumps(sharegpt_item, ensure_ascii=False) + '\n')
                count += 1
                
            except Exception as e:
                print(f"跳过错误行: {e}")

    print(f"✅ 转化完成！共处理 {count} 条数据。")
    print(f"现在你可以使用 'agintent_benchmark' 作为数据集名称进行训练了。")

if __name__ == "__main__":
    convert_to_sharegpt()