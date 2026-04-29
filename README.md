# INTENT2TX

**INTENT2TX: Benchmarking LLMs for Translating Natural Language Intents into Ethereum Transactions**

This repository contains the data construction pipeline and experiment code for the INTENT2TX benchmark.  
The benchmark studies how well LLMs convert natural-language Web3 intents into structured Ethereum transaction plans.

- Hugging Face dataset: [Intent2Tx/web3_intents_to_ethereum_transactions](https://huggingface.co/datasets/Intent2Tx/web3_intents_to_ethereum_transactions)
- License (dataset): Apache-2.0

## Repository Structure

```text
Intent2Tx_Bench/
├── data/
│   ├── 1_bitquery_get_txs.py
│   ├── 2_extract_contracts_addr.py
│   ├── 3_etherscan_get_contracts.py
│   ├── 4_select_txs_for_intents.py
│   ├── 5_decode_calls_to_actions.py
│   ├── 6_generate_intents.py
│   ├── 7_generate_single_step_benchmark_data.py
│   ├── 8_0_tag_single_step_benchmark_data_rule_based.py
│   ├── 8_1_generate_multi_steps_benchmark_data.py
│   ├── 9_generate_address_book.py
│   ├── 10_build_hf_single_step_dataset.py
│   └── 11_build_hf_multi_steps_dataset.py
└── experiment/
    ├── evaluate_models/            # API-based zero-shot and three-shot evaluation
    ├── simulation_execution/       # on-chain fork simulation with Anvil
    ├── score/                      # static/simulation/scaling/generalization scoring
    ├── scaling_law/                # fine-tuning data scaling experiments
    └── genelization/               # cross-category generalization experiments
```

## Task Definition

Given a user intent in natural language, the model should output:

1. **Single-step**: one JSON action with:
   - `contract`
   - `contract_address`
   - `function`
   - `params` (Solidity type + value)
   - `value` (ETH amount)
2. **Multi-step**: an ordered JSON list of such actions.

## Data Construction Pipeline

The `data/` folder builds the benchmark progressively from historical Ethereum calls:

1. `1_bitquery_get_txs.py`  
   Pull successful Ethereum calls from Bitquery over a rolling time window.
2. `2_extract_contracts_addr.py`  
   Extract valid contract-related addresses.
3. `3_etherscan_get_contracts.py`  
   Fetch verified contract source/ABI from Etherscan.
4. `4_select_txs_for_intents.py`  
   Filter high-quality top-level function calls for intent reconstruction.
5. `5_decode_calls_to_actions.py`  
   Decode calldata with ABI into structured action schemas.
6. `6_generate_intents.py`  
   Use an LLM to reverse-generate natural-language user intents from actions.
7. `7_generate_single_step_benchmark_data.py`  
   Build instruction-input-output single-step records.
8. `8_0_tag_single_step_benchmark_data_rule_based.py`  
   Add rule-based taxonomy labels (`primary_category`, `sub_category`).
9. `8_1_generate_multi_steps_benchmark_data.py`  
   Construct multi-step samples by chaining intents/actions from the same sender.
10. `9_generate_address_book.py`  
    Generate a helpful protocol/token address book used in prompts.
11. `10_build_hf_single_step_dataset.py` and `11_build_hf_multi_steps_dataset.py`  
    Convert to Hugging Face viewer-friendly JSONL splits.

## Dataset Splits

Published dataset contains:

- `single_step`: ~29.9K samples
- `multi_step`: ~1.6K samples
- Total: ~31.5K samples

Typical fields:

- Single-step: `instruction`, `input`, `output`, `contract`, `function`, `primary_category`, `sub_category`, `tx_hash`, `metadata`
- Multi-step: `instruction`, `input`, `output` (ordered list of actions)

## Environment Setup

### 1) Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install requests tqdm openai web3 eth-abi eth-utils transformers peft torch matplotlib numpy
```

### 2) Required API keys

Set environment variables before running data collection and API-based evaluation:

```bash
export BITQUERY_API_KEY=...
export ETHERSCAN_API_KEY=...
export OPENROUTER_API_KEY=...
```

## Reproducing Data Build

Run from repository root:

```bash
python data/1_bitquery_get_txs.py
python data/2_extract_contracts_addr.py
python data/3_etherscan_get_contracts.py
python data/4_select_txs_for_intents.py
python data/5_decode_calls_to_actions.py
python data/6_generate_intents.py
python data/7_generate_single_step_benchmark_data.py
python data/8_0_tag_single_step_benchmark_data_rule_based.py
python data/8_1_generate_multi_steps_benchmark_data.py
python data/9_generate_address_book.py
python data/10_build_hf_single_step_dataset.py
python data/11_build_hf_multi_steps_dataset.py
```

## Experiments

### A) Zero-shot / Three-shot model evaluation (API models)

Run in `experiment/evaluate_models`:

```bash
python zero_shot.py
python three_shot.py
```

Or pass arguments directly:

```bash
python zero_shot.py "openai/gpt-5.2" "GPT_5_2" 3
python three_shot.py "openai/gpt-5.2" "GPT_5_2" 3
```

`mode`: `1` = multi-step, `2` = single-step, `3` = both.

### B) Scaling-law and generalization studies

- `experiment/scaling_law/`: split train/test, build LLaMA-Factory training data at different sizes, evaluate base + LoRA checkpoints.
- `experiment/genelization/`: category-based train/test split for cross-category transfer and fine-tuned model evaluation.

These folders include helper scripts:

- `split_data.py`
- `transfer_data_for_llama_factory.py`
- `llama_factory.sh`
- `zero_shot.py`
- `test.sh`

### C) Simulation-based execution evaluation

Start a mainnet-forked Anvil node:

```bash
bash experiment/simulation_execution/start_anvil.sh
```

Then evaluate generated results:

```bash
python experiment/simulation_execution/dynamic_simulate_eval.py \
  experiment/evaluate_models/log/zero_shot_<MODEL>_single_results.jsonl
```

### D) Scoring and table generation

In `experiment/score`:

```bash
python static_score_single_multi.py <results.jsonl>
python score_evaluate_models.py
python score_simulation.py
python score_scaling_law.py
python score_genelization.py
```

The scripts output markdown/LaTeX tables and (for some experiments) plots.


## Notes and Limitations

- The benchmark is derived from real historical transactions and ABI decoding; noisy samples may exist.
- Some scripts assume local proxy settings and specific filesystem paths (especially training scripts). Adjust paths for your environment.
- Outputs should be validated with simulation before any real-world usage.
