import json
import os
import random
import multiprocessing
from collections import defaultdict
import sys
from time import sleep

from openai import OpenAI


# ============================================================
# Config
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
# Client
# ============================================================

client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=BASE_URL,
)


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


def query_model(model_name, system_prompt, user_prompt, timeout=60):
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


def run_eval(data, model_name, model_tag, mode):

    log_file = os.path.join(
        LOG_DIR,
        f"zero_shot_{model_tag}_{mode}_results.jsonl"
    )

    print(f"\nRunning {mode} test, saving to {log_file}")
    print(f"Total samples: {len(data)}\n")

    with open(ADDRESS_BOOK, "r") as f:
        address_book_str = f.read()

    with open(log_file, "a") as fout:
        for i, item in enumerate(data):
            system_prompt = item.get("instruction", "") + "\n" + address_book_str
            # system_prompt = item.get("instruction", "")
            user_prompt = item.get("input", "")

            llm_output = "ERROR"
            cnt = 3
            while llm_output == "ERROR" and cnt > 0:
                llm_output = query_model(
                    model_name,
                    system_prompt,
                    user_prompt
                )
                cnt -= 1
                sleep(1)

            item["llm_output"] = llm_output

            json.dump(item, fout)
            fout.write("\n")

            print(f"[{i+1}/{len(data)}] Done")

    print("\nCompleted.")


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
        run_eval(data, model_name, model_tag, "multi")

    elif mode == "2":
        data = sample_single()
        run_eval(data, model_name, model_tag, "single")

    elif mode == "3":
        run_eval(sample_multi(), model_name, model_tag, "multi")
        run_eval(sample_single(), model_name, model_tag, "single")

    else:
        print("Invalid mode.")