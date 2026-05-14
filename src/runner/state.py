import os
import json
from typing import Dict, Any, Optional

def get_state_path(state_dir: str, address: str) -> str:
    if not os.path.exists(state_dir):
        os.makedirs(state_dir)
    return os.path.join(state_dir, f"{address.lower()}.json")

def load_wallet_state(state_dir: str, address: str) -> Dict[str, Any]:
    path = get_state_path(state_dir, address)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except:
            pass
    
    return {
        "address": address,
        "runCount": 0,
        "actionsRun": 0,
        "errors": 0,
        "stats": {
            "usdcSent": "0",
            "ethSpent": "0",
        },
        "lastRun": ""
    }

def save_wallet_state(state_dir: str, address: str, state: Dict[str, Any]):
    path = get_state_path(state_dir, address)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)
