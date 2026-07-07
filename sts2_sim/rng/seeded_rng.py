"""
SeededRng — STS2 결정론적 난수 생성기
Java Random 호환 LCG 방식 (STS1 기준, STS2 검증 필요)
"""
from __future__ import annotations


class SeededRng:
    """
    Java Random 호환 48-bit LCG.
    STS1은 이 방식을 사용했으며, STS2도 유사할 것으로 추정.
    실제 게임 수치와 대조해 보정 필요.
    """
    _MULTIPLIER = 0x5DEECE66D
    _ADDEND = 0xB
    _MASK = (1 << 48) - 1

    def __init__(self, seed: int):
        self._seed = (seed ^ self._MULTIPLIER) & self._MASK
        self._call_count = 0  # 재현 디버깅용

    def _next_bits(self, bits: int) -> int:
        self._seed = (self._seed * self._MULTIPLIER + self._ADDEND) & self._MASK
        self._call_count += 1
        return self._seed >> (48 - bits)

    def next_int(self, bound: int) -> int:
        """[0, bound) 범위의 정수"""
        if bound <= 0:
            raise ValueError(f"bound must be positive, got {bound}")
        if bound & (bound - 1) == 0:  # 2의 거듭제곱
            return (bound * self._next_bits(31)) >> 31
        while True:
            bits = self._next_bits(31)
            val = bits % bound
            if bits - val + (bound - 1) >= 0:
                return val

    def next_float(self) -> float:
        """[0.0, 1.0) 범위의 float"""
        return self._next_bits(24) / (1 << 24)

    def next_bool(self) -> bool:
        return self._next_bits(1) != 0

    def shuffle(self, lst: list) -> list:
        """Fisher-Yates 셔플 (STS 방식: i=len-1 → 1)"""
        result = list(lst)
        for i in range(len(result) - 1, 0, -1):
            j = self.next_int(i + 1)
            result[i], result[j] = result[j], result[i]
        return result

    def choice(self, lst: list):
        """리스트에서 무작위 원소 선택"""
        if not lst:
            raise ValueError("Cannot choose from empty list")
        return lst[self.next_int(len(lst))]

    def fork(self, offset: int = 0) -> "SeededRng":
        """독립 서브스트림 생성 (PlayerRng, PlayerOdds 등 분리용)"""
        return SeededRng(self._seed ^ (offset * 0x9E3779B9))

    @property
    def call_count(self) -> int:
        return self._call_count

    def __repr__(self):
        return f"SeededRng(seed={self._seed:#x}, calls={self._call_count})"
