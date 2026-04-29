import json
import os
import random
import multiprocessing
from collections import defaultdict
import sys
from time import sleep
from difflib import SequenceMatcher
from openai import OpenAI

# ============================================================
# Config & Client (继承自你的 zero_shot)
# ============================================================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY is not set")

BASE_URL = "https://openrouter.ai/api/v1"
MULTI_FILE = "../../data/benchmark/multi_steps_intent2tx.jsonl"
SINGLE_FILE = "../../data/benchmark/tagged_single_step_intent2tx.jsonl"
ADDRESS_BOOK = "../../data/benchmark/helpful_address_book.md"
LOG_DIR = "log"
os.makedirs(LOG_DIR, exist_ok=True)

client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=BASE_URL)

# ============================================================
# RAG Engine: Simple Similarity Matcher
# ============================================================

class SimpleRAG:
    def __init__(self):
        self.corpus_single = []
        self.corpus_multi = []
        self._load_corpus()

    def _load_corpus(self):
        # 模式隔离加载
        if os.path.exists(SINGLE_FILE):
            with open(SINGLE_FILE, 'r') as f:
                for line in f:
                    self.corpus_single.append(json.loads(line))
        
        if os.path.exists(MULTI_FILE):
            with open(MULTI_FILE, 'r') as f:
                for line in f:
                    self.corpus_multi.append(json.loads(line))
        print(f"RAG Engine loaded: {len(self.corpus_single)} Single, {len(self.corpus_multi)} Multi entries.")

    def get_query_signature(self, item):
        """
        根据数据集格式提取特征签名 [(contract, function), ...]
        """
        # 检查是否是 Multi 模式（output 是一个 list）
        output_data = item.get("output", "")
        
        # 处理可能被字符串化的 output
        if isinstance(output_data, str):
            try:
                output_data = json.loads(output_data)
            except:
                pass

        if isinstance(output_data, list):
            # Multi-step 模式：遍历列表中的每一个 action
            return [(step.get("contract", ""), step.get("function", "")) for step in output_data]
        
        # Single-step 模式：直接读取外层字段
        # 注意：示例中 single 数据的 contract/function 就在 key 层
        contract = item.get("contract", "")
        function = item.get("function", "")
        
        # 如果外层没有，尝试解析 output 字典
        if not contract and isinstance(output_data, dict):
            contract = output_data.get("contract", "")
            function = output_data.get("function", "")
            
        return [(contract, function)]

    def calculate_score(self, sig1, sig2):
        """签名重合度 Jaccard 相似度思路"""
        set1 = set(sig1)
        set2 = set(sig2)
        if not set1: return 0
        intersection = set1.intersection(set2)
        # 使用交集大小除以当前查询签名的集合大小
        return len(intersection) / len(set1)

    def retrieve_top_k(self, current_item, mode, k=3):
        """根据 mode 分开检索"""
        query_sig = self.get_query_signature(current_item)
        current_input = current_item.get("input", "")
        
        # 选择池
        search_pool = self.corpus_multi if mode == "multi" else self.corpus_single
        
        scored_results = []
        for cand in search_pool:
            # 排除当前处理的样本
            if cand.get("input") == current_input:
                continue
            
            cand_sig = self.get_query_signature(cand)
            score = self.calculate_score(query_sig, cand_sig)
            
            # 如果逻辑签名不匹配（例如新协议），尝试 Input 文本相似度匹配
            if score == 0:
                # 降低文本匹配权重，优先保证逻辑匹配
                score = SequenceMatcher(None, current_input, cand.get("input", "")).ratio() * 0.4
            
            scored_results.append((score, cand))
        
        # 按照相似度降序排列
        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [res[1] for res in scored_results[:k]]

rag_engine = SimpleRAG()

# ============================================================
# Core Logic
# ============================================================

def format_example(item):
    """将检索到的数据格式化为 Prompt 中的 Example"""
    return f"Example Input: {item['input']}\nExample Output: {item['output']}\n"

def run_eval_three_shot(data, model_name, model_tag, mode):
    log_file = os.path.join(LOG_DIR, f"three_shot_{model_tag}_{mode}_results.jsonl")
    print(f"\n🚀 Running {mode} THREE-SHOT test, saving to {log_file}")

    with open(ADDRESS_BOOK, "r") as f:
        address_book_str = f.read()

    with open(log_file, "a") as fout:
        for i, item in enumerate(data):
            # 1. 检索相似示例
            examples = rag_engine.retrieve_top_k(item, mode, k=3)
            examples_str = "\n## Reference Examples (Few-Shot):\n"
            for idx, ex in enumerate(examples):
                examples_str += f"--- Example {idx+1} ---\n{format_example(ex)}\n"

            # 2. 组装 Prompt
            # 将 Examples 放在 Instruction 之后，Input 之前
            base_instruction = item.get("instruction", "You are a DeFi execution planner.")
            system_prompt = f"{base_instruction}\n\n{address_book_str}\n\n{examples_str}"
            user_prompt = f"Now, please process the following intent:\nUser intent: {item.get('input', '')}"

            # 3. 请求模型 (调用你原有的 query_model 函数)
            llm_output = "ERROR"
            cnt = 3
            while llm_output == "ERROR" and cnt > 0:
                llm_output = query_model(model_name, system_prompt, user_prompt)
                cnt -= 1
                if llm_output == "ERROR": sleep(2)

            # 保存结果
            item["llm_output"] = llm_output
            item["retrieved_examples"] = [ex.get("input") for ex in examples] # 记录检索了啥，方便 debug
            
            json.dump(item, fout)
            fout.write("\n")
            print(f"[{i+1}/{len(data)}] Processed with 3-shot RAG")


# ============================================================
# Model List
# ============================================================

MODELS = {
    "GPT 5.2": "openai/gpt-5.2",
    "GPT 5.2 Codex": "openai/gpt-5.2-codex",
    "Claude Haiku 4.5": "anthropic/claude-haiku-4.5",
    "Claude Opus 4.5": "anthropic/claude-opus-4.5",
    "Gemini 2.5 Flash": "google/gemini-2.5-flash",
    "Gemini 2.5 Pro": "google/gemini-2.5-pro",
    "DeepSeek 3.2": "deepseek/deepseek-v3.2",
    "Kimi 2": "moonshotai/kimi-k2-0905",
    "Llama 3.1 8B": "meta-llama/llama-3.1-8b-instruct",
    "Llama 3.3 70B": "meta-llama/llama-3.3-70b-instruct",
    "Qwen3 235B": "qwen/qwen3-235b-a22b-2507",
    "Qwen3 Coder": "qwen/qwen3-coder-next",
    "Ministral 14B": "mistralai/ministral-14b-2512",
    "Codestral": "mistralai/codestral-2508",
    "GLM 4.6": "z-ai/glm-4.6",
    "GLM 4 32B": "z-ai/glm-4-32b",
}

# ============================================================
# Utils
# ============================================================

def choose_model():
    print("\nAvailable models:\n")
    for i, name in enumerate(MODELS.keys()):
        print(f"{i}. {name}")

    idx = int(input("\nSelect model index: "))
    key = list(MODELS.keys())[idx]
    return MODELS[key], key.replace(" ", "_").replace("-", "_")


def sample_multi():
    data = []
    with open(MULTI_FILE) as f:
        for line in f:
            data.append(json.loads(line))

    k = max(1, int(len(data) * 0.1))
    return random.sample(data, k)


def sample_single():
    buckets = defaultdict(list)

    with open(SINGLE_FILE) as f:
        for line in f:
            item = json.loads(line)
            buckets[item["primary_category"]].append(item)

    sampled = []

    for cat, items in buckets.items():
        k = max(5, int(len(items) * 0.03))
        k = min(k, len(items))
        sampled.extend(random.sample(items, k))

    return sampled


def query_model_with_timeout(args, return_dict):
    model_name, system_prompt, user_prompt = args
    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )
        return_dict["result"] = completion.choices[0].message.content
    except Exception as e:
        print(f"Error querying model: {e}")
        return_dict["result"] = "ERROR"


def query_model(model_name, system_prompt, user_prompt, timeout=120):
    manager = multiprocessing.Manager()
    return_dict = manager.dict()

    p = multiprocessing.Process(
        target=query_model_with_timeout,
        args=((model_name, system_prompt, user_prompt), return_dict),
    )

    p.start()
    p.join(timeout)

    if p.is_alive():
        print("⏰ Hard kill process")
        p.terminate()
        p.join()
        return "ERROR"

    return return_dict.get("result", "ERROR")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    # 比如：python script.py "openai/gpt-5.2" "GPT_5_2" 1
    if len(sys.argv) > 3:
        model_name = sys.argv[1]
        model_tag = sys.argv[2]
        mode = sys.argv[3]
    else:
        # 如果没传参数，再走原来的交互流程
        model_name, model_tag = choose_model()
        print("\n1. Multi-step test")
        print("2. Single-step test")
        print("3. Both")
        mode = input("\nSelect mode: ")

    if mode == "1":
        data = sample_multi()
        run_eval_three_shot(data, model_name, model_tag, "multi")

    elif mode == "2":
        data = sample_single()
        run_eval_three_shot(data, model_name, model_tag, "single")

    elif mode == "3":
        run_eval_three_shot(sample_multi(), model_name, model_tag, "multi")
        run_eval_three_shot(sample_single(), model_name, model_tag, "single")

    else:
        print("Invalid mode.")

