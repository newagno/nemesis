from typing import Dict, Any, List, Optional

userSettings: Dict[str, Any] = {
    # RPC URL for connection (Sepolia)
    "rpcUrl": "https://ethereum-sepolia-rpc.publicnode.com",

    # File with wallets (one private key per line)
    "walletsFile": "wallets.txt",

    # Fixed seed for repeatable randomness (None = full randomness)
    "seed": None,

    # Number of cycles (0 = infinite)
    "cycles": 1,

    # Random order of actions
    "randomOrder": True,

    # Folders for logs and state
    "logsDir": "logs",
    "stateDir": "state",

    # Delays in seconds: [min, max]
    "delaysSeconds": {
        # Pause between actions
        "betweenActions": {"min": 30, "max": 90},

        # Pause between wallets
        "betweenWallets": {"min": 300, "max": 900},
    },

    "actions": {
        # Enable faucet
        "faucet": {
            "enabled": True,
            "threshold": 30.0, # If balance > 30 USDC/ETH, skip faucet
        },

        "swap": {
            "enabled": True,
            "count": {"min": 1, "max": 3},
            "amount": {"min": 0.1, "max": 1.0},
            "pairs": ["ETH/USDC", "USDC/ETH", "ETH/BASE", "BASE/ETH"]
        },

        "open_long": {
            "enabled": True,
            "leverage": {"min": 2, "max": 10},
            "amount": {"min": 10, "max": 50},
        },

        "open_short": {
            "enabled": True,
            "leverage": {"min": 2, "max": 10},
            "amount": {"min": 10, "max": 50},
        },

        "add_liquidity": {
            "enabled": True,
            "amount": {"min": 5, "max": 20},
        },

        "remove_liquidity": {
            "enabled": False, # disabled by default
        },

        # ON-CHAIN GM (0x474d)
        "send_gm": {
            "enabled": True,
        },
    },

    # TELEGRAM NOTIFICATIONS
    "telegram": {
        "botToken": "8390511439:AAFv0Zil24CgiYrqIJN4sqbWTf3p83dlQb8",
        "chatId": "441388332",
    },
}