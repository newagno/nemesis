import os
from typing import Dict, Any
from src.user_settings import userSettings
from src.core.utils import ensure_range

def load_config() -> Dict[str, Any]:
    cfg = userSettings.copy()
    
    # Validation
    if not cfg.get("rpcUrl"):
        raise ValueError("rpcUrl не вказано в налаштуваннях")
    
    if not os.path.exists(cfg.get("walletsFile", "wallets.txt")):
        # Create empty file if not exists
        with open(cfg.get("walletsFile", "wallets.txt"), "w") as f:
            pass
            
    # Normalize delays
    for key, val in cfg.get("delaysSeconds", {}).items():
        ensure_range(f"delaysSeconds.{key}", val)
        
    return cfg
