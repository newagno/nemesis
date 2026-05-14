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

    session_actions = 0
    session_errors = 0
    session_stats = {"swaps": 0, "liquidity": 0, "longs": 0, "shorts": 0}

    logger.info(f"")
    logger.info(f"━━━ [{name} | {short_addr(addr)}] ━━━")

    account = Account.from_key(pk)

    # 1. Faucet — окремо, помилка не зупиняє решту
    try:
        await check_and_faucet(w3, account, cfg["actions"])
    except Exception as e:
        logger.error(f"Faucet error: {e}")
        state["errors"] += 1
        session_errors += 1

    # 2. Список дій
    all_actions = [
        ("swap",             lambda: swap(w3, account, cfg["actions"], rng)),
        ("open_long",        lambda: open_long(w3, account, cfg["actions"], rng)),
        ("open_short",       lambda: open_short(w3, account, cfg["actions"], rng)),
        ("add_liquidity",    lambda: add_liquidity(w3, account, cfg["actions"], rng)),
        ("remove_liquidity", lambda: remove_liquidity(w3, account, cfg["actions"], rng)),
    ]

    if cfg.get("randomOrder", True):
        random.shuffle(all_actions)

    for act_id, act_fn in all_actions:
        settings = cfg["actions"].get(act_id)
        enabled = (isinstance(settings, dict) and settings.get("enabled")) or settings is True
        if not enabled:
            continue

        try:
            await act_fn()
            # ✅ Рахуємо тільки якщо дія СПРАВДІ виконалась без виключення
            state["actionsRun"] += 1
            session_actions += 1

            if act_id == "swap":
                session_stats["swaps"] += 1
            elif "liquidity" in act_id:
                session_stats["liquidity"] += 1
            elif act_id == "open_long":
                session_stats["longs"] += 1
            elif act_id == "open_short":
                session_stats["shorts"] += 1

            await sleep_range(cfg["delaysSeconds"]["betweenActions"], rng, logger, f"після {act_id}")

        except Exception as e:
            logger.error(f"❌ [{act_id}] помилка: {e}")
            state["errors"] += 1
            session_errors += 1
            # Продовжуємо з наступною дією навіть при помилці

    save_wallet_state(cfg["stateDir"], addr, state)

    logger.info(
        f"[{name}] Сесія завершена: "
        f"✅ {session_actions} дій | ❌ {session_errors} помилок"
    )

    return {
        "name": name,
        "address": addr,
        "actionsRun": state["actionsRun"],
        "errors": state["errors"],
        "sessionActions": session_actions,
        "sessionErrors": session_errors,
        "runCount": state["runCount"],
        "stats": session_stats,
    }


async def run_cycle(cfg: Dict[str, Any], cycle_num: int):
    wallets = load_wallets(cfg["walletsFile"])
    if not wallets:
        logger.error("Гаманці не знайдено у wallets.txt")
        return []

    w3 = get_web3(cfg["rpcUrl"])

    # Перевірка підключення до мережі
    try:
        chain_id = w3.eth.chain_id
        block = w3.eth.block_number
        logger.info(f"🌐 Підключено до мережі: chain_id={chain_id}, блок={block}")
        if chain_id != 11155111:
            logger.warning(f"⚠️  Очікується Sepolia (11155111), отримано {chain_id}!")
    except Exception as e:
        logger.error(f"❌ Не вдалося підключитися до RPC: {e}")
        return []

    rng = make_rng(cfg["seed"])

    logger.info(f"")
    logger.info(f"══ ПОЧАТОК ЦИКЛУ #{cycle_num} ({len(wallets)} гаманці) ══")

    results = []
    for i, wallet in enumerate(wallets):
        res = await run_wallet_actions(w3, wallet, cfg, rng)
        results.append(res)

        if i < len(wallets) - 1:
            await sleep_range(
                cfg["delaysSeconds"]["betweenWallets"], rng, logger, "між гаманцями"
            )

    logger.info(f"══ ЦИКЛ #{cycle_num} ЗАВЕРШЕНО ══")
    logger.info(f"")
    return results