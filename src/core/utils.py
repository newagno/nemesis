import time
import asyncio
from typing import List, Tuple, Any, Optional
from datetime import datetime

class Range:
    def __init__(self, min_val: float, max_val: float):
        self.min = min_val
        self.max = max_val

async def sleep(ms: int):
    await asyncio.sleep(ms / 1000)

def format_ms(ms: int) -> str:
    if ms < 1000:
        return f"{ms}ms"
    sec = ms / 1000
    return f"{sec:.1f}s"

def now_iso() -> str:
    return datetime.now().isoformat()

def short_addr(addr: str) -> str:
    return f"{addr[:6]}...{addr[-4:]}"

def ensure_range(name: str, range_val):
    if isinstance(range_val, (list, tuple)):
        min_v, max_v = range_val[0], range_val[1]
    else:
        min_v, max_v = range_val.get('min', 0), range_val.get('max', 0)
    if min_v > max_v:
        raise ValueError(f"Некоректний діапазон для {name}: min > max ({min_v} > {max_v})")
    if min_v < 0 or max_v < 0:
        raise ValueError(f"Некоректний діапазон для {name}: від'ємні значення не дозволені")

async def sleep_range(range_val, rng: Any, log: Any, reason: str):
    if isinstance(range_val, (list, tuple)):
        min_s, max_s = range_val[0], range_val[1]
    else:
        min_s, max_s = range_val.get('min', 0), range_val.get('max', 0)
    ms = rng.int(int(min_s * 1000), int(max_s * 1000))
    log.wait(f"Пауза {format_ms(ms)} ({reason})")
    await sleep(ms)

def sanitize_name(value: str) -> str:
    import re
    return re.sub(r'[^a-zA-Z0-9_-]', '_', value)

def random_amount_string(range_val: dict, rng: Any, decimals: int = 2) -> str:
    value = rng.float(range_val['min'], range_val['max'])
    return f"{value:.{decimals}f}"

def pick_two_distinct(arr: List[Any], rng: Any) -> Tuple[Any, Any]:
    if len(arr) < 2:
        raise ValueError('Потрібно щонайменше два елементи, щоб вибрати різні значення')
    i = rng.int(0, len(arr) - 1)
    j = rng.int(0, len(arr) - 1)
    while j == i:
        j = rng.int(0, len(arr) - 1)
    return arr[i], arr[j]
