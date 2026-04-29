nohup python3 zero_shot.py "google/gemini-2.5-flash" "Gemini_2.5_Flash" 3 2>&1 >> test1.log & #
nohup python3 zero_shot.py "google/gemini-2.5-pro" "Gemini_2.5_Pro" 3 2>&1 >> test2.log & #

nohup python3 zero_shot.py "openai/gpt-5.2" "GPT_5.2" 3 2>&1 >> test1.log & #
nohup python3 zero_shot.py "openai/gpt-5.2-codex" "GPT_5.2_Codex" 3 2>&1 >> test2.log & #

nohup python3 zero_shot.py "anthropic/claude-haiku-4.5" "Claude_Haiku_4.5" 3 2>&1 >> test1.log & #
nohup python3 zero_shot.py "anthropic/claude-opus-4.5" "Claude_Opus_4.5" 3 2>&1 >> test2.log & #

nohup python3 zero_shot.py "deepseek/deepseek-v3.2" "DeepSeek_3.2" 3 2>&1 >> test1.log & #
nohup python3 zero_shot.py "moonshotai/kimi-k2-0905" "Kimi_2" 3 2>&1 >> test2.log & #

nohup python3 zero_shot.py "meta-llama/llama-3.1-8b-instruct" "Llama_3.1_8B" 3 2>&1 >> test1.log & #
nohup python3 zero_shot.py "meta-llama/llama-3.3-70b-instruct" "Llama_3.3_70B" 3 2>&1 >> test2.log & #

nohup python3 zero_shot.py "qwen/qwen3-235b-a22b-2507" "Qwen3_235B" 3 2>&1 >> test1.log & #
nohup python3 zero_shot.py "qwen/qwen3-coder-next" "Qwen3_Coder" 3 2>&1 >> test2.log & #

nohup python3 zero_shot.py "mistralai/ministral-14b-2512" "Ministral_14B" 3 2>&1 >> test1.log & #
nohup python3 zero_shot.py "mistralai/codestral-2508" "Codestral" 3 2>&1 >> test2.log & #

nohup python3 zero_shot.py "z-ai/glm-4.6" "GLM_4.6" 3 2>&1 >> test2.log & #
nohup python3 zero_shot.py "z-ai/glm-4-32b" "GLM_4_32B" 3 2>&1 >> test2.log & #

#-------------------------

nohup python3 three_shot.py "google/gemini-2.5-flash" "Gemini_2.5_Flash" 3 2>&1 >> test3.log & #
nohup python3 three_shot.py "google/gemini-2.5-pro" "Gemini_2.5_Pro" 3 2>&1 >> test4.log & #

nohup python3 three_shot.py "openai/gpt-5.2" "GPT_5.2" 3 2>&1 >> test3.log &
nohup python3 three_shot.py "openai/gpt-5.2-codex" "GPT_5.2_Codex" 3 2>&1 >> test4.log & #

nohup python3 three_shot.py "anthropic/claude-haiku-4.5" "Claude_Haiku_4.5" 3 2>&1 >> test3.log & #
nohup python3 three_shot.py "anthropic/claude-opus-4.5" "Claude_Opus_4.5" 3 2>&1 >> test4.log & #

nohup python3 three_shot.py "deepseek/deepseek-v3.2" "DeepSeek_3.2" 3 2>&1 >> test3.log & #
nohup python3 three_shot.py "moonshotai/kimi-k2-0905" "Kimi_2" 3 2>&1 >> test4.log & #

nohup python3 three_shot.py "meta-llama/llama-3.1-8b-instruct" "Llama_3.1_8B" 3 2>&1 >> test3.log & #
nohup python3 three_shot.py "meta-llama/llama-3.3-70b-instruct" "Llama_3.3_70B" 3 2>&1 >> test4.log & #

nohup python3 three_shot.py "qwen/qwen3-235b-a22b-2507" "Qwen3_235B" 3 2>&1 >> test3.log & #
nohup python3 three_shot.py "qwen/qwen3-coder-next" "Qwen3_Coder" 3 2>&1 >> test4.log & #

nohup python3 three_shot.py "mistralai/ministral-14b-2512" "Ministral_14B" 3 2>&1 >> test3.log & #
nohup python3 three_shot.py "mistralai/codestral-2508" "Codestral" 3 2>&1 >> test4.log & #

nohup python3 three_shot.py "z-ai/glm-4.6" "GLM_4.6" 3 2>&1 >> test3.log & #
nohup python3 three_shot.py "z-ai/glm-4-32b" "GLM_4_32B" 3 2>&1 >> test4.log & #