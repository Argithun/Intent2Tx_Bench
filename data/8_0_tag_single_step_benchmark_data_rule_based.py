import json
import os

INPUT_FILE = "txs_intents/single_step_intent2tx.jsonl"
OUTPUT_FILE = "benchmark/tagged_single_step_intent2tx.jsonl"

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)


# ============================================================
# DeFi Taxonomy (Primary -> SubCategory -> Keywords)
# ============================================================

TAXONOMY = {
    "Swap": {
        "ExactInputSwap": [
            "swapexact", "exactinput", "swapexacttokens"
        ],
        "ExactOutputSwap": [
            "exactoutput"
        ],
        "MultiHopSwap": [
            "multihop", "router"
        ],
        "AggregatorSwap": [
            "1inch", "aggregator"
        ],
        "GenericSwap": [
            "swap", "exchange", "trade"
        ],
    },

    "Liquidity": {
        "AddLiquidity": [
            "addliquidity", "increaseLiquidity", "mintposition"
        ],
        "RemoveLiquidity": [
            "removeliquidity", "decreaseLiquidity", "burnposition"
        ],
        "CollectFees": [
            "collect"
        ],
    },

    "Lending": {
        "Supply": [
            "supply", "deposit"
        ],
        "Withdraw": [
            "withdraw", "redeem"
        ],
        "Borrow": [
            "borrow"
        ],
        "Repay": [
            "repay"
        ],
        "Liquidation": [
            "liquidate"
        ],
        "FlashLoan": [
            "flashloan"
        ],
    },

    "Staking": {
        "Stake": [
            "stake"
        ],
        "Unstake": [
            "unstake"
        ],
        "Delegate": [
            "delegate"
        ],
        "ClaimReward": [
            "claim", "reward"
        ],
    },

    "Governance": {
        "Propose": [
            "propose"
        ],
        "Vote": [
            "vote", "castvote"
        ],
        "Queue": [
            "queue"
        ],
        "ExecuteProposal": [
            "execute"
        ],
    },

    "TokenLifecycle": {
        "Mint": [
            "mint"
        ],
        "Burn": [
            "burn"
        ],
        "Approve": [
            "approve", "permit", "allowance"
        ],
    },

    "Transfer": {
        "ERC20Transfer": [
            "transferfrom", "transfer", "safetransfer"
        ],
        "ETHTransfer": [
            "send", "ethtransfer"
        ],
        "BatchTransfer": [
            "multisend", "batchtransfer"
        ],
    },

    "AssetTransformation": {
        "Wrap": [
            "wrap"
        ],
        "Unwrap": [
            "unwrap"
        ],
        "Lock": [
            "lock"
        ],
        "Unlock": [
            "unlock"
        ],
        "Bridge": [
            "bridge"
        ],
    },

    "NFT": {
        "MintNFT": [
            "mintnft"
        ],
        "TransferNFT": [
            "safetransferfrom", "transferfrom"
        ],
        "Auction": [
            "auction", "bid"
        ],
        "Marketplace": [
            "seaport", "opensea", "blur"
        ],
    },

    "Vault": {
        "DepositVault": [
            "vaultdeposit"
        ],
        "WithdrawVault": [
            "vaultwithdraw"
        ],
        "Rebalance": [
            "rebalance"
        ],
        "StrategyUpdate": [
            "setstrategy", "updatestrategy"
        ],
    },
}


# ============================================================
# Matching Logic
# ============================================================

def match_text(text):
    text = text.lower()

    for primary, sub_map in TAXONOMY.items():
        for sub, keywords in sub_map.items():
            for kw in keywords:
                if kw.lower() in text:
                    return primary, sub

    return "Other", "Other"


def tag_item(item):

    function = item.get("function", "")
    contract = item.get("contract", "")
    input_text = item.get("input", "")
    output_text = item.get("output", "")

    # 优先级：contract > function > output > input
    for field in [contract, function, output_text, input_text]:
        if field:
            primary, sub = match_text(field)
            if primary != "Other":
                return primary, sub

    return "Other", "Other"


# ============================================================
# Main
# ============================================================

def main():

    with open(INPUT_FILE) as fin, open(OUTPUT_FILE, "w") as fout:

        for line in fin:

            item = json.loads(line)
            output_json = json.loads(item["output"])

            data = {
                "instruction": item["instruction"],
                "input": item["input"],
                "output": item["output"],
                "contract": output_json["contract"],
                "function": output_json["function"]
            }

            primary, sub = tag_item(data)

            data["primary_category"] = primary
            data["sub_category"] = sub

            json.dump(data, fout)
            fout.write("\n")

    print("Tagging complete:", OUTPUT_FILE)


if __name__ == "__main__":
    main()