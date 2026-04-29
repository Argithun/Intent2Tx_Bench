CUDA_VISIBLE_DEVICES=0 python3 zero_shot.py Base 2>&1 > test.log

CUDA_VISIBLE_DEVICES=0 python3 zero_shot.py 200 2>&1 > test.log

CUDA_VISIBLE_DEVICES=0 python3 zero_shot.py 800 2>&1 > test.log

CUDA_VISIBLE_DEVICES=0 python3 zero_shot.py 2000 2>&1 > test.log

CUDA_VISIBLE_DEVICES=0 python3 zero_shot.py 8000 2>&1 > test.log

CUDA_VISIBLE_DEVICES=0 python3 zero_shot.py 14000 2>&1 > test.log

CUDA_VISIBLE_DEVICES=0 python3 zero_shot.py 20000 2>&1 > test.log

CUDA_VISIBLE_DEVICES=0 python3 zero_shot.py 28776 2>&1 > test.log

