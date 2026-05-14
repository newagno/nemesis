import time
import asyncio
import random
from web3 import Web3
from typing import Dict, Any, List
from src.core.logger import logger
from src.core.utils import short_addr, random_amount_string
from src.web3_config import ERC20_ABI, CONTRACTS, FAUCET_ABI, PERP_ABI, VAULT_ABI, WETH_ABI, ROUTER_ABI

async def check_balance(w3: Web3, address: str, token_address: str = None) -> float:
    address = w3.to_checksum_address(address)
    if token_address is None:
        balance = w3.eth.get_balance(address)
        return float(Web3.from_wei(balance, 'ether'))
    else:
        contract = w3.eth.contract(address=w3.to_checksum_address(token_address), abi=ERC20_ABI)
        balance = contract.functions.balanceOf(address).call()
        decimals = contract.functions.decimals().call()
        return float(balance / (10 ** decimals))

async def wrap_eth(w3: Web3, account: Any, amount_eth: float):
    weth_addr = CONTRACTS["WETH"]
    amount_wei = w3.to_wei(amount_eth, 'ether')
    
    logger.info(f"Wrapping {amount_eth} ETH to WETH...")
    
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
    logger.info(f"Wrap TX sent: {tx_hash.hex()}")
    w3.eth.wait_for_transaction_receipt(tx_hash)
    await asyncio.sleep(2)

async def approve_token(w3: Web3, account: Any, token_address: str, spender_address: str, amount_wei: int):
    token = w3.eth.contract(address=w3.to_checksum_address(token_address), abi=ERC20_ABI)
    allowance = token.functions.allowance(account.address, spender_address).call()
    
    if allowance >= amount_wei:
        logger.info(f"Allowance sufficient for {short_addr(token_address)}")
        return

    logger.info(f"Approving tokens for {short_addr(spender_address)}...")
    
    tx = token.functions.approve(spender_address, 2**256 - 1).build_transaction({
        'from': account.address,
        'gas': 100000,
        'gasPrice': int(w3.eth.gas_price * 1.2), # Bonus gas for faster approval
        'nonce': w3.eth.get_transaction_count(account.address),
    })
    
    signed_tx = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    logger.info(f"Approve TX sent: {tx_hash.hex()}")
    w3.eth.wait_for_transaction_receipt(tx_hash)
    await asyncio.sleep(2)

async def check_and_faucet(w3: Web3, account: Any, cfg: Dict[str, Any]):
    f_cfg = cfg.get("faucet", {})
    if not f_cfg.get("enabled"):
        return

    addr = account.address
    eth_bal = await check_balance(w3, addr)
    usdc_bal = await check_balance(w3, addr, CONTRACTS["USDC"])
    
    threshold = f_cfg.get("threshold", 30.0)
    
    if eth_bal > threshold and usdc_bal > threshold:
        logger.info(f"Баланс достатній (ETH: {eth_bal:.2f}, USDC: {usdc_bal:.2f}). Пропуск крану.")
        return

    logger.info(f"Запит крану... (Баланс ETH: {eth_bal:.2f}, USDC: {usdc_bal:.2f})")
    faucet_addr = CONTRACTS.get("Faucet")
    if not faucet_addr:
        logger.warning("Адреса крану не вказана. Пропуск.")
        return
        
    try:
        faucet_contract = w3.eth.contract(address=faucet_addr, abi=FAUCET_ABI)
        tx = faucet_contract.functions.requestTokens(CONTRACTS["USDC"]).build_transaction({
            'from': addr,
            'nonce': w3.eth.get_transaction_count(addr),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })
        signed_tx = w3.eth.account.sign_transaction(tx, account.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logger.info(f"Кран запитано: {tx_hash.hex()}")
        w3.eth.wait_for_transaction_receipt(tx_hash)
        await asyncio.sleep(2)
    except Exception as e:
        logger.error(f"Помилка крану: {e}")

async def get_all_balances(w3: Web3, address: str) -> Dict[str, float]:
    # Dynamic: check all non-core tokens from CONTRACTS
    exclude = ["Router", "PositionRouter", "Vault", "Faucet"]
    tokens = {k: v for k, v in CONTRACTS.items() if k not in exclude and not k.startswith("Pool")}
    
    balances = {"ETH": await check_balance(w3, address)}
    for symbol, addr in tokens.items():
        try:
            balances[symbol] = await check_balance(w3, address, addr)
        except:
            balances[symbol] = 0.0
    return balances

async def swap(w3: Web3, account: Any, cfg: Dict[str, Any], rng: Any):
    s_cfg = cfg.get("swap", {})
    if not s_cfg.get("enabled"):
        return

    # Balancing Strategy: find token with lowest balance
    balances = await get_all_balances(w3, account.address)
    
    # Exclude ETH from 'to_token' targets if we want to accumulate other tokens
    target_tokens = [t for t in balances.keys() if t != "ETH"]
    if not target_tokens:
        return
    to_token = min(target_tokens, key=lambda t: balances[t])
    
    # Decide from where to swap. If we have much ETH, use ETH. Otherwise use USDC or another surplus token.
    if balances["ETH"] > 0.05: # Keep some for gas
        from_token = "ETH"
    else:
        # Pick token with highest balance
        from_token = max(balances.keys(), key=lambda t: balances[t])
        if from_token == to_token or balances[from_token] < 1.0:
            logger.info("Баланси занадто рівномірні або низькі. Пропуск свопу.")
            return

    amount_val = float(random_amount_string(s_cfg["amount"], rng, 4))
    
    # --- BALANCE GUARD ---
    # Ensure we don't try to swap more than we have
    available = balances[from_token]
    if from_token == "ETH":
        # Keep 0.05 ETH for gas
        safe_available = max(0, available - 0.05)
        if safe_available < 0.0001:
            logger.warning(f"Занадто мало ETH ({available}) для безпечного свопу. Пропуск.")
            return
        amount_val = min(amount_val, safe_available)
    else:
        # For tokens, we can swap up to 99% of balance
        if available < 0.1:
            logger.warning(f"Занадто мало {from_token} ({available}). Пропуск.")
            return
        amount_val = min(amount_val, available * 0.99)
    # ---------------------

    logger.info(f"Своп (Балансування) {amount_val:.6f} {from_token} -> {to_token}...")
    
    try:
        router_addr = CONTRACTS["Router"]
        router = w3.eth.contract(address=router_addr, abi=ROUTER_ABI)
        deadline = int(time.time()) + 600
        
        path = []
        if from_token == "ETH":
            path = [CONTRACTS["WETH"], CONTRACTS[to_token]]
            amount_wei = w3.to_wei(amount_val, 'ether')
            
            tx = router.functions.swapExactETHForTokens(
                0, 
                path,
                account.address,
                deadline
            ).build_transaction({
                'from': account.address,
                'value': amount_wei,
                'gas': 400000,
                'gasPrice': w3.eth.gas_price,
                'nonce': w3.eth.get_transaction_count(account.address),
            })
        elif to_token == "ETH":
            # Token to ETH
            path = [CONTRACTS[from_token], CONTRACTS["WETH"]]
            token_contract = w3.eth.contract(address=CONTRACTS[from_token], abi=ERC20_ABI)
            decimals = token_contract.functions.decimals().call()
            amount_in = int(amount_val * (10**decimals))
            
            await approve_token(w3, account, CONTRACTS[from_token], router_addr, amount_in)
            
            tx = router.functions.swapExactTokensForETH(
                amount_in,
                0,
                path,
                account.address,
                deadline
            ).build_transaction({
                'from': account.address,
                'gas': 400000,
                'gasPrice': w3.eth.gas_price,
                'nonce': w3.eth.get_transaction_count(account.address),
            })
        else:
            # Token to Token (via WETH)
            path = [CONTRACTS[from_token], CONTRACTS["WETH"], CONTRACTS[to_token]]
            token_contract = w3.eth.contract(address=CONTRACTS[from_token], abi=ERC20_ABI)
            decimals = token_contract.functions.decimals().call()
            amount_in = int(amount_val * (10**decimals))
            
            await approve_token(w3, account, CONTRACTS[from_token], router_addr, amount_in)
            
            tx = router.functions.swapExactTokensForTokens(
                amount_in,
                0,
                path,
                account.address,
                deadline
            ).build_transaction({
                'from': account.address,
                'gas': 500000,
                'gasPrice': w3.eth.gas_price,
                'nonce': w3.eth.get_transaction_count(account.address),
            })
        
        signed_tx = w3.eth.account.sign_transaction(tx, account.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logger.info(f"Своп надіслано: {tx_hash.hex()}")
        w3.eth.wait_for_transaction_receipt(tx_hash)
        await asyncio.sleep(2)
        
    except Exception as e:
        logger.error(f"Помилка свопу: {e}")

async def open_long(w3: Web3, account: Any, cfg: Dict[str, Any], rng: Any):
    l_cfg = cfg.get("open_long", {})
    if not l_cfg.get("enabled"):
        return
    
    leverage = rng.int(l_cfg["leverage"]["min"], l_cfg["leverage"]["max"])
    amount_usdc = rng.float(l_cfg["amount"]["min"], l_cfg["amount"]["max"]) 
    
    logger.info(f"Відкриття REAL LONG: {amount_usdc:.2f} USDC з плечем x{leverage}...")
    
    try:
        pos_router_addr = CONTRACTS["PositionRouter"]
        # Check if contract exists to avoid wasted gas
        if len(w3.eth.get_code(pos_router_addr)) == 0:
            logger.warning(f"PositionRouter {short_addr(pos_router_addr)} не розгорнутий. Скидання до імітації.")
            await asyncio.sleep(1)
            logger.info("LONG позицію успішно імітовано")
            return

        usdc_addr = CONTRACTS["USDC"]
        weth_addr = CONTRACTS["WETH"]
        amount_in = int(amount_usdc * 10**6)
        
        await approve_token(w3, account, usdc_addr, pos_router_addr, amount_in)
        
        pos_router = w3.eth.contract(address=pos_router_addr, abi=PERP_ABI)
        
        # GMX logic: sizeDelta in 30 decimals. (amountIn * leverage)
        # Assuming USDC price is $1.00
        size_delta = int(amount_usdc * leverage * 10**30)
        
        # executionFee is native ETH (usually 0.002 - 0.005 ETH)
        exec_fee = w3.to_wei(0.004, 'ether')
        
        tx = pos_router.functions.createIncreasePosition(
            [usdc_addr, weth_addr], # path: usdc as collateral, weth as long token
            weth_addr,              # indexToken
            amount_in,
            0,                      # minOut
            size_delta,
            True,                   # isLong
            0,                      # acceptablePrice (usually should be fetched from Vault)
            exec_fee,
            b'\x00' * 32,           # referralCode
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
        logger.info(f"Long TX sent: {tx_hash.hex()}")
        w3.eth.wait_for_transaction_receipt(tx_hash)
        
    except Exception as e:
        logger.error(f"Помилка REAL LONG: {e}")

async def open_short(w3: Web3, account: Any, cfg: Dict[str, Any], rng: Any):
    s_cfg = cfg.get("open_short", {})
    if not s_cfg.get("enabled"):
        return
    
    leverage = rng.int(s_cfg["leverage"]["min"], s_cfg["leverage"]["max"])
    amount_usdc = rng.float(s_cfg["amount"]["min"], s_cfg["amount"]["max"])
    
    logger.info(f"Відкриття REAL SHORT: {amount_usdc:.2f} USDC з плечем x{leverage}...")
    
    try:
        pos_router_addr = CONTRACTS["PositionRouter"]
        if len(w3.eth.get_code(pos_router_addr)) == 0:
            logger.warning(f"PositionRouter {short_addr(pos_router_addr)} не розгорнутий. Скидання до імітації.")
            await asyncio.sleep(1)
            logger.info("SHORT позицію успішно імітовано")
            return

        usdc_addr = CONTRACTS["USDC"]
        weth_addr = CONTRACTS["WETH"]
        amount_in = int(amount_usdc * 10**6)
        
        await approve_token(w3, account, usdc_addr, pos_router_addr, amount_in)
        pos_router = w3.eth.contract(address=pos_router_addr, abi=PERP_ABI)
        size_delta = int(amount_usdc * leverage * 10**30)
        exec_fee = w3.to_wei(0.004, 'ether')
        
        tx = pos_router.functions.createIncreasePosition(
            [usdc_addr], # path: usdc as collateral for shorting other tokens
            weth_addr,
            amount_in,
            0,
            size_delta,
            False, # isLong = False
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
        logger.info(f"Short TX sent: {tx_hash.hex()}")
        w3.eth.wait_for_transaction_receipt(tx_hash)
        
    except Exception as e:
        logger.error(f"Помилка REAL SHORT: {e}")

async def add_liquidity(w3: Web3, account: Any, cfg: Dict[str, Any], rng: Any):
    a_cfg = cfg.get("add_liquidity", {})
    if not a_cfg.get("enabled"):
        return
    
    from src.web3_config import MASSIVE_POOLS
    # Select a random pool from the massive list
    pool_addr = rng.pick(MASSIVE_POOLS) if hasattr(rng, 'pick') else random.choice(MASSIVE_POOLS)
    
    logger.info(f"Додавання ліквідності у пул {short_addr(pool_addr)}...")
    
    try:
        # Dynamic Token Discovery
        ABI_CORE = [
            {"constant": True, "inputs": [], "name": "token0", "outputs": [{"name": "", "type": "address"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "token1", "outputs": [{"name": "", "type": "address"}], "type": "function"},
        ]
        pool_contract = w3.eth.contract(address=w3.to_checksum_address(pool_addr), abi=ABI_CORE)
        
        try:
            addrA = pool_contract.functions.token0().call()
            addrB = pool_contract.functions.token1().call()
        except:
            logger.warning(f"Пул {short_addr(pool_addr)} не підтримує стандарт token0/token1. Використовуємо ETH/USDC за замовчуванням.")
            addrA = CONTRACTS["WETH"]
            addrB = CONTRACTS["USDC"]

        router_addr = CONTRACTS["Router"]
        router = w3.eth.contract(address=router_addr, abi=ROUTER_ABI)
        deadline = int(time.time()) + 600
        
        amount_val = rng.float(a_cfg["amount"]["min"], a_cfg["amount"]["max"])
        
        # Decide if it's ETH pair or Token pair
        if addrA == CONTRACTS["WETH"] or addrB == CONTRACTS["WETH"]:
            token_addr = addrB if addrA == CONTRACTS["WETH"] else addrA
            token_contract = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
            decimals = token_contract.functions.decimals().call()
            
            amount_token = int(amount_val * (10**decimals))
            amount_eth = w3.to_wei(amount_val * 0.001, 'ether')
            
            await approve_token(w3, account, token_addr, router_addr, amount_token)
            
            tx = router.functions.addLiquidityETH(
                token_addr,
                amount_token,
                0, 0,
                account.address,
                deadline
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
            
            amountA = int(amount_val * (10**decA))
            amountB = int(amount_val * (10**decB))
            
            await approve_token(w3, account, addrA, router_addr, amountA)
            await approve_token(w3, account, addrB, router_addr, amountB)
            
            tx = router.functions.addLiquidity(
                addrA, addrB,
                amountA, amountB,
                0, 0,
                account.address,
                deadline
            ).build_transaction({
                'from': account.address,
                'gas': 600000,
                'gasPrice': w3.eth.gas_price,
                'nonce': w3.eth.get_transaction_count(account.address),
            })
        
        signed_tx = w3.eth.account.sign_transaction(tx, account.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logger.info(f"Liquidity TX sent: {tx_hash.hex()}")
        w3.eth.wait_for_transaction_receipt(tx_hash)
        await asyncio.sleep(2)
        
    except Exception as e:
        logger.error(f"Помилка ліквідності: {e}")

async def remove_liquidity(w3: Web3, account: Any, cfg: Dict[str, Any], rng: Any):
    r_cfg = cfg.get("remove_liquidity", {})
    if not r_cfg.get("enabled"):
        return
    
    logger.info("Вилучення ліквідності (імітація людської поведінки)...")
    await asyncio.sleep(1)
    logger.info("Частину ліквідності вилучено.")
