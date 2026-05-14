from typing import TypedDict, List, Optional, Union, Dict

class Range(TypedDict):
    min: float
    max: float

class TelegramSettings(TypedDict):
    botToken: str
    chatId: str

class ActionSettings(TypedDict):
    enabled: bool
    # Custom fields for specific actions can be added here
    count: Optional[Range]
    amount: Optional[Range]
    slippageBps: Optional[Range]

class UserSettings(TypedDict):
    rpcUrl: str
    walletsFile: str
    seed: Optional[int]
    cycles: int
    randomOrder: bool
    logsDir: str
    stateDir: str
    delaysSeconds: Dict[str, Range]
    actions: Dict[str, Union[bool, ActionSettings, Dict]]
    telegram: TelegramSettings

class WalletStats(TypedDict):
    usdcSent: str
    ethSpent: str
    actionsRun: int
    errors: int
    runCount: int

class WalletState(TypedDict):
    address: str
    stats: WalletStats
    lastRun: str
