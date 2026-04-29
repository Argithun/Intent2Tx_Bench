import requests
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from pathlib import Path
import os

# ------------------------
# Logging
# ------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("bitquery_calls")

# ------------------------
# Config
# ------------------------
BITQUERY_ENDPOINT = "https://streaming.bitquery.io/graphql"

OUTPUT_DIR = Path("./txs")
OUTPUT_DIR.mkdir(exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "ethereum_txs_300d.jsonl"
CHECKPOINT_FILE = OUTPUT_DIR / "checkpoint.json"

# ------------------------
# Core Extractor
# ------------------------
class BitqueryCallExtractor:

    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })

        self.max_retries = 5
        self.base_retry_sleep = 10
        self.request_timeout = 1200

        # ---- tuning knobs ----
        self.window_hours = 4          # 初始时间窗口
        self.min_window_hours = 1      # 最小窗口
        self.limit = 400               # 每个窗口最多返回 calls

        self.cooldown_on_429 = 180        # 429 后强制冷却（秒）
        self.max_windows_per_min = 5     # 每分钟最多查询窗口数
        self.last_window_ts = 0


    # ------------------------
    # GraphQL Query (字段完全不变)
    # ------------------------
    def query(self) -> str:
        return """
        query GetEthereumContractCalls(
          $since: DateTime!,
          $till: DateTime!,
          $limit: Int!
        ) {
          EVM(dataset: archive, network: eth) {
            Calls(
              where: {
                Block: { Time: { since: $since, till: $till } }
                Call: { Success: true }
              }
              orderBy: [{ ascending: Block_Time }]
              limit: { count: $limit }
            ) {
              Block {
                Time
                Number
                Date
              }
              Transaction {
                Hash
                From
                To
                Gas
                GasPrice
                Cost
                Index
              }
              Call {
                From
                To
                Value
                Gas
                GasUsed
                Success
                Create
                Depth
                CallPath
                Input
                Output
              }
            }
          }
        }
        """

    # ------------------------
    # Request with retry
    # ------------------------
    def fetch(self, since: str, till: str):
        payload = {
            "query": self.query(),
            "variables": {
                "since": since,
                "till": till,
                "limit": self.limit
            }
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                r = self.session.post(
                    BITQUERY_ENDPOINT,
                    json=payload,
                    timeout=self.request_timeout
                )

                r.raise_for_status()
                data = r.json()

                if "errors" in data:
                    if "Too Many Requests" in data["errors"][0].get("message", ""):
                        logger.error("429 Too Many Requests from ClickHouse — entering cooldown")
                        time.sleep(self.cooldown_on_429)
                        return None, "429"

                    logger.warning(f"GraphQL error: {data['errors']}")
                    return None, "graphql_error"

                return data["data"]["EVM"]["Calls"], "success"

            except Exception as e:
                logger.warning(f"Request failed (attempt {attempt}): {e}")
                time.sleep(self.base_retry_sleep * attempt)

        return None, "max_retries_exceeded"


    # ------------------------
    # Checkpoint
    # ------------------------
    def load_checkpoint(self) -> datetime:
        if CHECKPOINT_FILE.exists():
            with open(CHECKPOINT_FILE) as f:
                ts = json.load(f)["cursor"]
                return datetime.fromisoformat(ts)
        return None

    def save_checkpoint(self, cursor: datetime):
        with open(CHECKPOINT_FILE, "w") as f:
            json.dump({"cursor": cursor.isoformat()}, f)

    # ------------------------
    # Save
    # ------------------------
    def save_calls(self, calls: List[Dict]):
        with open(OUTPUT_FILE, "a") as f:
            for c in calls:
                f.write(json.dumps(c) + "\n")

    # ------------------------
    # Main loop
    # ------------------------
    def run(self, days: int = 300):
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)

        cursor = self.load_checkpoint() or start
        window = timedelta(hours=self.window_hours)

        logger.info(f"Starting from {cursor.isoformat()}")

        while cursor < now:
            till = min(cursor + window, now)

            since_iso = cursor.isoformat()
            till_iso = till.isoformat()

            logger.info(f"Query window: {since_iso} → {till_iso}")

            calls, mes = self.fetch(since_iso, till_iso)

            if calls is None:
                if mes == "429":
                    continue

                # 降级窗口
                if window > timedelta(hours=self.min_window_hours):
                    window /= 2
                    logger.warning(f"Reducing window to {window}")
                    time.sleep(10)
                    continue
                else:
                    logger.error("Minimum window reached, skipping window")
                    cursor = till
                    self.save_checkpoint(cursor)
                    time.sleep(10)
                    continue

            if calls:
                self.save_calls(calls)
                logger.info(f"Saved {len(calls)} calls")

            cursor = till
            self.save_checkpoint(cursor)

            time.sleep(10)

        logger.info("Extraction completed")

# ------------------------
# Entrypoint
# ------------------------
def main():
    api_key = os.getenv("BITQUERY_API_KEY")
    if not api_key:
        raise ValueError("BITQUERY_API_KEY is not set")
    
    extractor = BitqueryCallExtractor(api_key)
    extractor.run(days=300)

if __name__ == "__main__":
    main()
