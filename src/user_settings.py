from typing import Dict, Any

userSettings: Dict[str, Any] = {
    # RPC URL (Sepolia). Рекомендовано: Alchemy або Infura для надійності
    # Безкоштовні фаусети ETH:
    #   https://www.alchemy.com/faucets/ethereum-sepolia
    #   https://cloud.google.com/application/web3/faucet/ethereum/sepolia
    "rpcUrl": "https://ethereum-sepolia-rpc.publicnode.com",

    # Файл з приватними ключами (один ключ на рядок, рядки з # ігноруються)
    "walletsFile": "wallets.txt",

    # Фіксований seed для відтворюваної рандомізації (None = повна рандомізація)
    "seed": None,

    # Кількість циклів (0 = нескінченно)
    "cycles": 1,

    # Випадковий порядок дій (анти-сибіл)
    "randomOrder": True,

    # Директорії
    "logsDir": "logs",
    "stateDir": "state",

    # Затримки між діями/гаманцями (секунди)
    "delaysSeconds": {
        # Пауза між окремими діями
        "betweenActions": {"min": 15, "max": 45},
        # Пауза між гаманцями
        "betweenWallets": {"min": 60, "max": 180},
    },

    "actions": {
        # ── Фаусет ──────────────────────────────────────────────────────────
        "faucet": {
            "enabled": True,
            # Якщо ETH < threshold → логуємо попередження про поповнення
            # Якщо USDC < threshold → запитуємо фаусет контракт
            "threshold": 0.05,
        },

        # ── Своп ─────────────────────────────────────────────────────────────
        # Реальні свопи ETH↔токени через Router на Sepolia
        # УВАГА: потрібен ETH на газ (~0.005 ETH мінімум) та базовий баланс
        "swap": {
            "enabled": True,
            "count": {"min": 1, "max": 2},
            # Сума в ETH (якщо свопаємо ETH) або в одиницях токену
            "amount": {"min": 0.001, "max": 0.005},
        },

        # ── Long/Short через PositionRouter ──────────────────────────────────
        # Потрібен розгорнутий PositionRouter + USDC + ETH на execution fee (0.004 ETH)
        # Якщо контракт не розгорнутий — дія пропускається (НЕ симулюється)
        "open_long": {
            "enabled": True,
            "leverage": {"min": 2, "max": 5},
            # Сума в USDC
            "amount": {"min": 1.0, "max": 5.0},
        },

        "open_short": {
            "enabled": True,
            "leverage": {"min": 2, "max": 5},
            "amount": {"min": 1.0, "max": 5.0},
        },

        # ── Ліквідність ──────────────────────────────────────────────────────
        "add_liquidity": {
            "enabled": True,
            # Сума в одиницях токену
            "amount": {"min": 0.5, "max": 2.0},
        },

        # remove_liquidity вимкнено — потребує окремої реалізації з LP токенами
        "remove_liquidity": {
            "enabled": False,
        },
    },

    # ── Telegram ─────────────────────────────────────────────────────────────
    "telegram": {
        "botToken": "8390511439:AAFv0Zil24CgiYrqIJN4sqbWTf3p83dlQb8",
        "chatId": "441388332",
    },
}