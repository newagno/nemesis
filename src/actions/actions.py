import time
import asyncio
import random
from web3 import Web3
from typing import Dict, Any, List, Optional
from src.core.logger import logger
from src.core.utils import short_addr, random_amount_string
from src.web3_config import ERC20_ABI, CONTRACTS, FAUCET_ABI, PERP_ABI, VAULT_ABI, WETH_ABI, ROUTER_ABI

# ──────────────────────────────────────────────
# СПРАВЖНІЙ USDC на Sepolia (Circle офіційний)
REAL_USDC = Web3.to_checksum_address("0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238")
# Токени для свопів (тільки реальні, не NLP/тестові)
SWAP_TOKENS = ["WETH", "DAI", "LINK", "PEPE", "SHIB", "UNI"]
# ──────────────────────────────────────────────


def check_tx_receipt(receipt: Any, action: str):
    """Перевіряє статус транзакції. Кидає виняток якщо TX reverted."""
    if receipt is None:
        raise RuntimeError(f"[{action}] Receipt = None, транзакція не підтверджена")
    if receipt.get("status") == 0:
        tx_hash = receipt.get("transactionHash", b"").hex()
        raise RuntimeError(f"[{action}] Транзакція REVERTED! TX: {tx_hash}")
    tx_hash = receipt.get("transactionHash", b"").hex()
    logger.info(f"[{action}] ✅ TX підтверджено: {tx_hash}")


async def check_balance(w3: Web3, address: str, token_address: str = None) -> float:
    """Перевіряє баланс ETH або ERC-20 токену."""
    address = w3.to_checksum_address(address)
    if token_address is None:
        balance = w3.eth.get_balance(address)
        return float(Web3.from_wei(balance, 'ether'))
    else:
        contract = w3.eth.contract(
            address=w3.to_checksum_address(token_address), abi=ERC20_ABI
        )
        balance = contract.functions.balanceOf(address).call()
        decimals = contract.functions.decimals().call()
        return float(balance / (10 ** decimals))


async def wrap_eth(w3: Web3, account: Any, amount_eth: float):
    """Wrap ETH → WETH."""
    weth_addr = CONTRACTS["WETH"]
    amount_wei = w3.to_wei(amount_eth, 'ether')
    logger.info(f"Wrapping {amount_eth:.6f} ETH → WETH...")

    weth = w3.eth.contract(address=weth_addr, abi=WETH_ABI)
    tx = weth.functions.deposit().build_transaction({
        'from': account.address,
        'value': amount_wei,
        'gas': 100000,
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(account.address),
    })
    signed_tx = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    logger.info(f"Wrap TX: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    check_tx_receipt(receipt, "wrap_eth")
    await asyncio.sleep(2)


async def approve_token(
    w3: Web3, account: Any, token_address: str, spender_address: str, amount_wei: int
):
    """Approve ERC-20 токен для spender. Пропускає якщо allowance достатній."""
    token = w3.eth.contract(
        address=w3.to_checksum_address(token_address), abi=ERC20_ABI
    )
    allowance = token.functions.allowance(account.address, spender_address).call()

    if allowance >= amount_wei:
        logger.info(f"Allowance достатній для {short_addr(token_address)}")
        return

    logger.info(f"Approve {short_addr(token_address)} для {short_addr(spender_address)}...")
    tx = token.functions.approve(spender_address, 2**256 - 1).build_transaction({
        'from': account.address,
        'gas': 100000,
        'gasPrice': int(w3.eth.gas_price * 1.2),
        'nonce': w3.eth.get_transaction_count(account.address),
    })
    signed_tx = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    logger.info(f"Approve TX: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    check_tx_receipt(receipt, "approve_token")
    await asyncio.sleep(2)


async def check_and_faucet(w3: Web3, account: Any, cfg: Dict[str, Any]):
    """Перевіряє баланс і запитує фаусет якщо потрібно."""
    f_cfg = cfg.get("faucet", {})
    if not f_cfg.get("enabled"):
        return

    addr = account.address
    eth_bal = await check_balance(w3, addr)
    # Використовуємо РЕАЛЬНИЙ USDC (Circle Sepolia)
    usdc_bal = await check_balance(w3, addr, REAL_USDC)

    threshold = f_cfg.get("threshold", 0.05)

    logger.info(f"Баланс: ETH={eth_bal:.6f} | USDC={usdc_bal:.4f}")

    if eth_bal < 0.001:
        logger.warning(
            f"⚠️  ETH критично низький ({eth_bal:.6f}). "
            f"Поповни через: https://cloud.google.com/application/web3/faucet/ethereum/sepolia "
            f"або https://www.alchemy.com/faucets/ethereum-sepolia"
        )

    faucet_addr = CONTRACTS.get("Faucet")
    if not faucet_addr:
        logger.warning("Адреса фаусету не вказана. Пропуск.")
        return

    # Перевіряємо чи фаусет контракт існує
    code = w3.eth.get_code(faucet_addr)
    if len(code) == 0:
        logger.warning(f"Фаусет {short_addr(faucet_addr)} — контракт не розгорнутий. Пропуск.")
        return

    if eth_bal > threshold and usdc_bal > threshold:
        logger.info(f"Баланс достатній. Пропуск фаусету.")
        return

    logger.info(f"Запит фаусету... (ETH: {eth_bal:.6f}, USDC: {usdc_bal:.4f})")
    try:
        faucet_contract = w3.eth.contract(address=faucet_addr, abi=FAUCET_ABI)
        tx = faucet_contract.functions.requestTokens(REAL_USDC).build_transaction({
            'from': addr,
            'nonce': w3.eth.get_transaction_count(addr),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price,
        })
        signed_tx = w3.eth.account.sign_transaction(tx, account.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logger.info(f"Фаусет TX: {tx_hash.hex()}")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        check_tx_receipt(receipt, "faucet")
        await asyncio.sleep(3)
    except Exception as e:
        logger.error(f"Помилка фаусету: {e}")
        raise


async def get_swap_balances(w3: Web3, address: str) -> Dict[str, float]:
    """Повертає баланси тільки реальних токенів для свопу."""
    result = {"ETH": await check_balance(w3, address)}

    token_map = {
        "USDC": REAL_USDC,
        "WETH": CONTRACTS["WETH"],
        "DAI": CONTRACTS.get("DAI", CONTRACTS.get("DAI_1")),
        "LINK": CONTRACTS.get("LINK_1", CONTRACTS.get("LINK")),
        "PEPE": CONTRACTS.get("PEPE"),
        "SHIB": CONTRACTS.get("SHIB"),
    }

    for symbol, addr in token_map.items():
        if not addr:
            continue
        try:
            result[symbol] = await check_balance(w3, address, addr)
        except Exception:
            result[symbol] = 0.0

    return result


def get_token_address(symbol: str) -> Optional[str]:
    """Повертає адресу токену за символом."""
    special = {"USDC": REAL_USDC, "WETH": CONTRACTS["WETH"]}
    if symbol in special:
        return special[symbol]
    return CONTRACTS.get(symbol) or CONTRACTS.get(f"{symbol}_1")


async def swap(w3: Web3, account: Any, cfg: Dict[str, Any], rng: Any):
    """Своп токенів через Router."""
    s_cfg = cfg.get("swap", {})
    if not s_cfg.get("enabled"):
        return

    balances = await get_swap_balances(w3, account.address)
    logger.info(f"Баланси для свопу: { {k: f'{v:.6f}' for k, v in balances.items()} }")

    # Вибираємо to_token — той з найменшим балансом серед не-ETH
    candidates = {k: v for k, v in balances.items() if k not in ("ETH",)}
    if not candidates:
        logger.warning("Немає токенів для свопу. Пропуск.")
        return

    to_token = min(candidates, key=lambda t: candidates[t])

    # Вибираємо from_token
    eth_safe = balances["ETH"] - 0.005  # резерв на газ
    if eth_safe > 0.001:
        from_token = "ETH"
    else:
        # Беремо токен з найбільшим балансом
        from_candidates = {k: v for k, v in candidates.items() if k != to_token and v > 0.01}
        if not from_candidates:
            logger.warning(
                f"Недостатньо балансу для свопу. ETH={balances['ETH']:.6f}. "
                f"Поповни гаманець через Sepolia фаусет."
            )
            return
        from_token = max(from_candidates, key=lambda t: from_candidates[t])

    if from_token == to_token:
        logger.warning("from_token == to_token. Пропуск свопу.")
        return

    amount_val = rng.float(s_cfg["amount"]["min"], s_cfg["amount"]["max"])

    # Захист від свопу більше ніж маємо
    if from_token == "ETH":
        available = balances["ETH"] - 0.005
        if available < 0.0001:
            logger.warning(f"Замало ETH для свопу ({balances['ETH']:.6f}). Пропуск.")
            return
        amount_val = min(amount_val, available)
    else:
        available = balances.get(from_token, 0)
        if available < 0.01:
            logger.warning(f"Замало {from_token} ({available:.6f}). Пропуск.")
            return
        amount_val = min(amount_val, available * 0.95)

    logger.info(f"🔄 Своп {amount_val:.6f} {from_token} → {to_token}")

    try:
        router_addr = CONTRACTS["Router"]
        router = w3.eth.contract(address=router_addr, abi=ROUTER_ABI)
        deadline = int(time.time()) + 600

        if from_token == "ETH":
            to_addr = get_token_address(to_token)
            if not to_addr:
                logger.warning(f"Невідома адреса токену {to_token}")
                return
            path = [CONTRACTS["WETH"], to_addr]
            amount_wei = w3.to_wei(amount_val, 'ether')

            tx = router.functions.swapExactETHForTokens(
                0, path, account.address, deadline
            ).build_transaction({
                'from': account.address,
                'value': amount_wei,
                'gas': 400000,
                'gasPrice': w3.eth.gas_price,
                'nonce': w3.eth.get_transaction_count(account.address),
            })

        elif to_token == "ETH":
            from_addr = get_token_address(from_token)
            if not from_addr:
                logger.warning(f"Невідома адреса токену {from_token}")
                return
            path = [from_addr, CONTRACTS["WETH"]]
            token_contract = w3.eth.contract(address=from_addr, abi=ERC20_ABI)
            decimals = token_contract.functions.decimals().call()
            amount_in = int(amount_val * (10 ** decimals))

            await approve_token(w3, account, from_addr, router_addr, amount_in)

            tx = router.functions.swapExactTokensForETH(
                amount_in, 0, path, account.address, deadline
            ).build_transaction({
                'from': account.address,
                'gas': 400000,
                'gasPrice': w3.eth.gas_price,
                'nonce': w3.eth.get_transaction_count(account.address),
            })

        else:
            from_addr = get_token_address(from_token)
            to_addr = get_token_address(to_token)
            if not from_addr or not to_addr:
                logger.warning(f"Невідома адреса токену {from_token} або {to_token}")
                return
            path = [from_addr, CONTRACTS["WETH"], to_addr]
            token_contract = w3.eth.contract(address=from_addr, abi=ERC20_ABI)
            decimals = token_contract.functions.decimals().call()
            amount_in = int(amount_val * (10 ** decimals))

            await approve_token(w3, account, from_addr, router_addr, amount_in)

            tx = router.functions.swapExactTokensForTokens(
                amount_in, 0, path, account.address, deadline
            ).build_transaction({
                'from': account.address,
                'gas': 500000,
                'gasPrice': w3.eth.gas_price,
                'nonce': w3.eth.get_transaction_count(account.address),
            })

        signed_tx = w3.eth.account.sign_transaction(tx, account.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logger.info(f"Своп TX надіслано: {tx_hash.hex()}")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        check_tx_receipt(receipt, "swap")
        await asyncio.sleep(2)

    except Exception as e:
        logger.error(f"❌ Помилка свопу ({from_token}→{to_token}): {e}")
        raise


async def open_long(w3: Web3, account: Any, cfg: Dict[str, Any], rng: Any):
    """Відкриття LONG позиції через PositionRouter."""
    l_cfg = cfg.get("open_long", {})
    if not l_cfg.get("enabled"):
        return

    # Перевіряємо чи PositionRouter розгорнутий
    pos_router_addr = CONTRACTS["PositionRouter"]
    code = w3.eth.get_code(pos_router_addr)
    if len(code) == 0:
        logger.warning(
            f"⚠️  PositionRouter {short_addr(pos_router_addr)} НЕ РОЗГОРНУТИЙ на цій мережі. "
            f"Дія open_long пропущена (НЕ симулюється)."
        )
        return

    leverage = rng.int(l_cfg["leverage"]["min"], l_cfg["leverage"]["max"])
    amount_usdc = rng.float(l_cfg["amount"]["min"], l_cfg["amount"]["max"])

    # Перевірка балансу USDC
    usdc_bal = await check_balance(w3, account.address, REAL_USDC)
    if usdc_bal < amount_usdc:
        logger.warning(
            f"Замало USDC для LONG: потрібно {amount_usdc:.2f}, є {usdc_bal:.4f}. Пропуск."
        )
        return

    # Перевірка балансу ETH на execution fee
    eth_bal = await check_balance(w3, account.address)
    exec_fee_eth = 0.004
    if eth_bal < exec_fee_eth + 0.005:
        logger.warning(
            f"Замало ETH для execution fee: потрібно ≥{exec_fee_eth + 0.005:.4f}, є {eth_bal:.6f}. Пропуск."
        )
        return

    logger.info(f"📈 Відкриття LONG: {amount_usdc:.2f} USDC | плече x{leverage}")

    try:
        usdc_addr = REAL_USDC
        weth_addr = CONTRACTS["WETH"]
        amount_in = int(amount_usdc * 10 ** 6)

        await approve_token(w3, account, usdc_addr, pos_router_addr, amount_in)

        pos_router = w3.eth.contract(address=pos_router_addr, abi=PERP_ABI)
        size_delta = int(amount_usdc * leverage * 10 ** 30)
        exec_fee = w3.to_wei(exec_fee_eth, 'ether')

        tx = pos_router.functions.createIncreasePosition(
            [usdc_addr, weth_addr],
            weth_addr,
            amount_in,
            0,
            size_delta,
            True,
            0,
            exec_fee,
            b'\x00' * 32,
            "0x0000000000000000000000000000000000000000"
        ).build_transaction({
            'from': account.address,
            'value': exec_fee,
            'gas': 600000,
            'gasPrice': w3.eth.gas_price,
            'nonce': w3.eth.get_transaction_count(account.address),
        })

        signed_tx = w3.eth.account.sign_transaction(tx, account.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logger.info(f"Long TX: {tx_hash.hex()}")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        check_tx_receipt(receipt, "open_long")

    except Exception as e:
        logger.error(f"❌ Помилка LONG: {e}")
        raise


async def open_short(w3: Web3, account: Any, cfg: Dict[str, Any], rng: Any):
    """Відкриття SHORT позиції через PositionRouter."""
    s_cfg = cfg.get("open_short", {})
    if not s_cfg.get("enabled"):
        return

    pos_router_addr = CONTRACTS["PositionRouter"]
    code = w3.eth.get_code(pos_router_addr)
    if len(code) == 0:
        logger.warning(
            f"⚠️  PositionRouter {short_addr(pos_router_addr)} НЕ РОЗГОРНУТИЙ. "
            f"Дія open_short пропущена (НЕ симулюється)."
        )
        return

    leverage = rng.int(s_cfg["leverage"]["min"], s_cfg["leverage"]["max"])
    amount_usdc = rng.float(s_cfg["amount"]["min"], s_cfg["amount"]["max"])

    usdc_bal = await check_balance(w3, account.address, REAL_USDC)
    if usdc_bal < amount_usdc:
        logger.warning(
            f"Замало USDC для SHORT: потрібно {amount_usdc:.2f}, є {usdc_bal:.4f}. Пропуск."
        )
        return

    eth_bal = await check_balance(w3, account.address)
    exec_fee_eth = 0.004
    if eth_bal < exec_fee_eth + 0.005:
        logger.warning(
            f"Замало ETH для execution fee SHORT: є {eth_bal:.6f}. Пропуск."
        )
        return

    logger.info(f"📉 Відкриття SHORT: {amount_usdc:.2f} USDC | плече x{leverage}")

    try:
        usdc_addr = REAL_USDC
        weth_addr = CONTRACTS["WETH"]
        amount_in = int(amount_usdc * 10 ** 6)

        await approve_token(w3, account, usdc_addr, pos_router_addr, amount_in)

        pos_router = w3.eth.contract(address=pos_router_addr, abi=PERP_ABI)
        size_delta = int(amount_usdc * leverage * 10 ** 30)
        exec_fee = w3.to_wei(exec_fee_eth, 'ether')

        tx = pos_router.functions.createIncreasePosition(
            [usdc_addr],
            weth_addr,
            amount_in,
            0,
            size_delta,
            False,
            0,
            exec_fee,
            b'\x00' * 32,
            "0x0000000000000000000000000000000000000000"
        ).build_transaction({
            'from': account.address,
            'value': exec_fee,
            'gas': 600000,
            'gasPrice': w3.eth.gas_price,
            'nonce': w3.eth.get_transaction_count(account.address),
        })

        signed_tx = w3.eth.account.sign_transaction(tx, account.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logger.info(f"Short TX: {tx_hash.hex()}")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        check_tx_receipt(receipt, "open_short")

    except Exception as e:
        logger.error(f"❌ Помилка SHORT: {e}")
        raise


async def add_liquidity(w3: Web3, account: Any, cfg: Dict[str, Any], rng: Any):
    """Додавання ліквідності у пул."""
    a_cfg = cfg.get("add_liquidity", {})
    if not a_cfg.get("enabled"):
        return

    from src.web3_config import MASSIVE_POOLS
    pool_addr = rng.pick(MASSIVE_POOLS)

    logger.info(f"💧 Додавання ліквідності: пул {short_addr(pool_addr)}")

    try:
        ABI_CORE = [
            {"constant": True, "inputs": [], "name": "token0",
             "outputs": [{"name": "", "type": "address"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "token1",
             "outputs": [{"name": "", "type": "address"}], "type": "function"},
        ]
        pool_contract = w3.eth.contract(
            address=w3.to_checksum_address(pool_addr), abi=ABI_CORE
        )

        try:
            addrA = pool_contract.functions.token0().call()
            addrB = pool_contract.functions.token1().call()
        except Exception:
            logger.warning(f"Пул {short_addr(pool_addr)} не підтримує token0/token1. Використовуємо WETH/USDC.")
            addrA = CONTRACTS["WETH"]
            addrB = REAL_USDC

        router_addr = CONTRACTS["Router"]
        router = w3.eth.contract(address=router_addr, abi=ROUTER_ABI)
        deadline = int(time.time()) + 600

        amount_val = rng.float(a_cfg["amount"]["min"], a_cfg["amount"]["max"])

        weth_addr = CONTRACTS["WETH"]

        if addrA == weth_addr or addrB == weth_addr:
            token_addr = addrB if addrA == weth_addr else addrA
            token_contract = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
            decimals = token_contract.functions.decimals().call()

            amount_token = int(amount_val * (10 ** decimals))
            amount_eth = w3.to_wei(amount_val * 0.001, 'ether')

            # Перевіряємо баланси
            eth_bal = await check_balance(w3, account.address)
            eth_needed = float(Web3.from_wei(amount_eth, 'ether')) + 0.005
            if eth_bal < eth_needed:
                logger.warning(
                    f"Замало ETH для add_liquidity: потрібно ≥{eth_needed:.6f}, є {eth_bal:.6f}. Пропуск."
                )
                return

            token_bal = await check_balance(w3, account.address, token_addr)
            token_needed = float(amount_token) / (10 ** decimals)
            if token_bal < token_needed:
                logger.warning(
                    f"Замало токену {short_addr(token_addr)}: потрібно {token_needed:.6f}, є {token_bal:.6f}. Пропуск."
                )
                return

            await approve_token(w3, account, token_addr, router_addr, amount_token)

            tx = router.functions.addLiquidityETH(
                token_addr, amount_token, 0, 0, account.address, deadline
            ).build_transaction({
                'from': account.address,
                'value': amount_eth,
                'gas': 500000,
                'gasPrice': w3.eth.gas_price,
                'nonce': w3.eth.get_transaction_count(account.address),
            })
        else:
            decA = w3.eth.contract(address=addrA, abi=ERC20_ABI).functions.decimals().call()
            decB = w3.eth.contract(address=addrB, abi=ERC20_ABI).functions.decimals().call()

            amountA = int(amount_val * (10 ** decA))
            amountB = int(amount_val * (10 ** decB))

            balA = await check_balance(w3, account.address, addrA)
            balB = await check_balance(w3, account.address, addrB)
            if balA < amount_val or balB < amount_val:
                logger.warning(
                    f"Замало токенів для add_liquidity: "
                    f"A={balA:.6f} (потрібно {amount_val:.6f}), "
                    f"B={balB:.6f} (потрібно {amount_val:.6f}). Пропуск."
                )
                return

            await approve_token(w3, account, addrA, router_addr, amountA)
            await approve_token(w3, account, addrB, router_addr, amountB)

            tx = router.functions.addLiquidity(
                addrA, addrB, amountA, amountB, 0, 0, account.address, deadline
            ).build_transaction({
                'from': account.address,
                'gas': 600000,
                'gasPrice': w3.eth.gas_price,
                'nonce': w3.eth.get_transaction_count(account.address),
            })

        signed_tx = w3.eth.account.sign_transaction(tx, account.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logger.info(f"Liquidity TX: {tx_hash.hex()}")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        check_tx_receipt(receipt, "add_liquidity")
        await asyncio.sleep(2)

    except Exception as e:
        logger.error(f"❌ Помилка add_liquidity: {e}")
        raise


async def remove_liquidity(w3: Web3, account: Any, cfg: Dict[str, Any], rng: Any):
    """Remove liquidity — вимкнено за замовчуванням, без симуляції."""
    r_cfg = cfg.get("remove_liquidity", {})
    if not r_cfg.get("enabled"):
        logger.info("remove_liquidity вимкнено в налаштуваннях. Пропуск.")
        return

    # Реальна реалізація: знайти LP токени на гаманці і вилучити ліквідність
    logger.info("remove_liquidity: реальна реалізація потребує LP-токен адрес. Пропуск.")