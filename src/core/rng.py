import random
from typing import Any, List, Optional

class Rng:
    def __init__(self, seed: Optional[int] = None):
        self.seed = seed
        if seed is not None:
            self._mulberry_state = seed & 0xFFFFFFFF
            # Match JavaScript's unsigned 32-bit behavior
        else:
            self._mulberry_state = None

    def _mulberry32(self) -> float:
        """Port of JavaScript's mulberry32 seed-based RNG."""
        if self._mulberry_state is None:
            return random.random()
        
        self._mulberry_state = (self._mulberry_state + 0x6d2b79f5) & 0xFFFFFFFF
        t = self._mulberry_state
        
        # Math.imul(t ^ (t >>> 15), t | 1)
        # Using 64-bit to safely simulate imul
        r = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        
        # r ^= r + Math.imul(r ^ (r >>> 7), r | 61)
        r = (r ^ (r + (((r ^ (r >> 7)) * (r | 61)) & 0xFFFFFFFF))) & 0xFFFFFFFF
        
        # return ((r ^ (r >>> 14)) >>> 0) / 4294967296
        return ((r ^ (r >> 14)) & 0xFFFFFFFF) / 4294967296

    def int(self, min_val: int, max_val: int) -> int:
        if max_val < min_val:
            min_val, max_val = max_val, min_val
        return int(self._mulberry32() * (max_val - min_val + 1)) + min_val

    def float(self, min_val: float, max_val: float) -> float:
        if max_val < min_val:
            min_val, max_val = max_val, min_val
        return self._mulberry32() * (max_val - min_val) + min_val

    def pick(self, arr: List[Any]) -> Any:
        if not arr:
            raise ValueError("Неможливо вибрати з порожнього масиву")
        return arr[int(self._mulberry32() * len(arr))]

    def bool(self, p: float = 0.5) -> bool:
        return self._mulberry32() < p

def make_rng(seed: Optional[int] = None) -> Rng:
    return Rng(seed)
