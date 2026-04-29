import json
import torch
import os
import sys
from pathlib import Path
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

# ==========================
# 1. 配置与路径
# ==========================
BASE_MODEL_PATH = "/workspace/train_agintent/model/Qwen3-14B"
ADDRESS_BOOK_PATH = "../../data/benchmark/helpful_address_book.md"
TEST_FILE = Path("./test.jsonl")
OUTPUT_DIR = Path("./log")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 定义模型映射
LORA_MODELS = {
    "Base": None,
    "Gen": "/workspace/train_agintent/model/Qwen3-14B-BenchmarkGenelization",
}

MAX_NEW_TOKENS = 512
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ==========================
# 2. 交互逻辑
# ==========================
def get_model_config():
    # 检查是否有命令行参数输入
    if len(sys.argv) > 1:
        arg_tag = sys.argv[1]
        if arg_tag in LORA_MODELS:
            return arg_tag, LORA_MODELS[arg_tag]
        else:
            print(f"错误: 提供的参数 '{arg_tag}' 不在预定义模型列表中。")
            sys.exit(1)

    # 如果没有参数，进入交互模式
    keys = list(LORA_MODELS.keys())
    print("\n--- 可用的测试模型阶梯 ---")
    for i, key in enumerate(keys):
        path = LORA_MODELS[key] if LORA_MODELS[key] else "原始基座模型"
        print(f"[{i}] {key} (Path: {path})")
    
    try:
        idx = int(input("\n未检测到参数，请手动选择模型索引: "))
        selected_key = keys[idx]
        return selected_key, LORA_MODELS[selected_key]
    except (ValueError, IndexError):
        print("输入无效，退出。")
        sys.exit(1)

# ==========================
# 3. 推理核心
# ==========================
def main():
    # 1. 选择模型
    size_tag, lora_path = get_model_config()
    out_path = OUTPUT_DIR / f"zero_shot_Qwen3_14B_Benchmark{size_tag}_single_results.jsonl"

    # 2. 加载地址簿
    print(f"Loading Address Book from {ADDRESS_BOOK_PATH}...")
    with open(ADDRESS_BOOK_PATH, "r", encoding="utf-8") as f:
        address_book_str = f.read()

    # 3. 加载测试集
    with open(TEST_FILE, 'r', encoding='utf-8') as f:
        test_data = [json.loads(line) for line in f if line.strip()]

    # 4. 检查断点续传
    done_ids = set()
    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    done_ids.add(obj.get("input"))
                except: pass
        print(f"检测到断点，已跳过 {len(done_ids)} 条数据。")

    # 5. 加载模型与分词器
    print(f"Loading Base Model: {BASE_MODEL_PATH}...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True
    )

    if lora_path:
        print(f"Loading LoRA Adapter: {lora_path}...")
        model = PeftModel.from_pretrained(base_model, lora_path)
    else:
        model = base_model
    
    model.eval()


    # 6. 开始执行
    print(f"开始推理，结果将保存至: {out_path}")
    with open(out_path, "a", encoding="utf-8") as fout:
        for idx, item in enumerate(tqdm(test_data, desc="Inferencing")):
            # 确保每条数据有唯一 ID（如果没有则用索引）
            sample_id = item.get("input", idx)
            if sample_id in done_ids:
                continue

            # 构建增强型 System Prompt
            system_prompt = item.get("instruction", "").strip() + "\n\n" + address_book_str
            # system_prompt = item.get("instruction", "").strip()  # 仅使用原始指令，不添加地址簿
            user_input = item.get("input", "").strip()
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ]
            
            prompt = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True, enable_thinking=False,
            )
            
            inputs = tokenizer(prompt, return_tensors="pt").to(DEVICE)
            
            with torch.no_grad():
                generate_ids = model.generate(
                    **inputs,
                    max_new_tokens=MAX_NEW_TOKENS,
                    temperature=0.0,
                    do_sample=False,
                    pad_token_id=tokenizer.eos_token_id
                )
            
            response = tokenizer.decode(
                generate_ids[0][inputs["input_ids"].shape[-1]:], 
                skip_special_tokens=True
            ).strip()
            
            # 保存结果
            result_item = item.copy()
            result_item["id"] = sample_id
            result_item["llm_output"] = response
            
            fout.write(json.dumps(result_item, ensure_ascii=False) + "\n")
            fout.flush()

    print(f"\n✅ 模型 {size_tag} 测试完成！")

if __name__ == "__main__":
    main()