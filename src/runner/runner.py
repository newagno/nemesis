import asyncio
import random
from typing import Dict, Any, List
from src.core.logger import logger
from src.core.rng import make_rng
from src.core.utils import sleep_range, short_addr, now_iso
from src.runner.state import load_wallet_state, save_wallet_state
from src.runner.wallets import load_wallets
from src.web3_config import get_web3
from src.actions.actions import check_and_faucet, swap, open_long, open_short, add_liquidity, remove_liquidity
from eth_account import Account

async def run_wallet_actions(w3: Any, wallet: Dict[str, str], cfg: Dict[str, Any], rng: Any):
    addr = wallet["address"]
    pk = wallet["pk"]
    name = wallet["name"]
    
    state = load_wallet_state(cfg["stateDir"], addr)
    state["runCount"] += 1
    state["lastRun"] = now_iso()
    
    # Session stats
    session_actions = 0
    session_errors = 0
    session_stats = {
        "swaps": 0,
        "liquidity": 0,
        "longs": 0,
        "shorts": 0
    }
    
    logger.info(f"--- [Гаманець: {name} | {short_addr(addr)}] ---")
    
    account = Account.from_key(pk)
    
    # 1. Faucet
    try:
        await check_and_faucet(w3, account, cfg["actions"])
        session_actions += 1 # Count faucet request as an action if successful (or attempted)
    except Exception as e:
        logger.error(f"Faucet error: {e}")
        state["errors"] += 1
        session_errors += 1

    # 2. Actions List
    all_actions = [
        ("swap", lambda: swap(w3, account, cfg["actions"], rng)),
        ("open_long", lambda: open_long(w3, account, cfg["actions"], rng)),
        ("open_short", lambda: open_short(w3, account, cfg["actions"], rng)),
        ("add_liquidity", lambda: add_liquidity(w3, account, cfg["actions"], rng)),
        ("remove_liquidity", lambda: remove_liquidity(w3, account, cfg["actions"], rng)),
    ]
    
    if cfg.get("randomOrder", True):
        random.shuffle(all_actions)
        
    for act_id, act_fn in all_actions:
        try:
            settings = cfg["actions"].get(act_id)
            if (isinstance(settings, dict) and settings.get("enabled")) or settings is True:
                await act_fn()
                state["actionsRun"] += 1
                session_actions += 1
                
                # Update session stats
                if act_id == "swap": session_stats["swaps"] += 1
                elif "liquidity" in act_id: session_stats["liquidity"] += 1
                elif act_id == "open_long": session_stats["longs"] += 1
                elif act_id == "open_short": session_stats["shorts"] += 1
                
                await sleep_range(cfg["delaysSeconds"]["betweenActions"], rng, logger, f"після {act_id}")

        except Exception as e:
            logger.error(f"Action {act_id} failed: {e}")
            state["errors"] += 1
            session_errors += 1
            
    save_wallet_state(cfg["stateDir"], addr, state)
    return {
        "name": name,
        "address": addr,
        "actionsRun": state["actionsRun"],
        "errors": state["errors"],
        "sessionActions": session_actions,
        "sessionErrors": session_errors,
        "runCount": state["runCount"],
        "stats": session_stats
    }

async def run_cycle(cfg: Dict[str, Any], cycle_num: int):
    wallets = load_wallets(cfg["walletsFile"])
    if not wallets:
        logger.error("Гаманці не знайдені в wallets.txt")
        return []
        
    w3 = get_web3(cfg["rpcUrl"])
    rng = make_rng(cfg["seed"])
    
    logger.info(f"== ПОЧАТОК ЦИКЛУ {cycle_num} ({len(wallets)} гаманців) ==")
    
    results = []
    for wallet in wallets:
        res = await run_wallet_actions(w3, wallet, cfg, rng)
        results.append(res)
        
        if wallet != wallets[-1]:
            await sleep_range(cfg["delaysSeconds"]["betweenWallets"], rng, logger, "між гаманцями")
            
    logger.info(f"== ЦИКЛ {cycle_num} ЗАВЕРШЕНО ==")
    return results