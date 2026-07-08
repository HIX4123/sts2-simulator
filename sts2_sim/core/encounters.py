"""
STS2 인카운터 풀 — 디컴파일 Models.Encounters.* 구성 기준.
이식된 몬스터만으로 구성 (미이식 몬스터가 포함된 인카운터는 부분 구성, 주석 표기).
"""
from __future__ import annotations
import random
from typing import Callable, Dict, List

from sts2_sim.entities.sts2_monster import (
    MonsterModel,
    TwigSlimeS, TwigSlimeM, Stabbot, Zapbot,
    AxeRubyRaider, FlailKnight, DampCultist, Chomper,
)


# 디컴파일 인카운터 구성 (부분 이식은 주석):
#   SlimesWeak: LeafSlimeS/M + TwigSlimeS/M 혼합 → Twig 계열만 이식됨
#   CultistsNormal: CalcifiedCultist + DampCultist → DampCultist ×2로 대체
#   ChompersNormal: Chomper ×2 (하나는 ScreamFirst)
#   RubyRaidersNormal: 5종 레이더 혼합 → AxeRubyRaider ×2로 대체
#   KnightsElite: FlailKnight + SpectralKnight + MagiKnight → FlailKnight 단독
ENCOUNTERS: Dict[str, Callable[[], List[MonsterModel]]] = {
    "slimes_weak": lambda: [TwigSlimeS(), TwigSlimeM()],
    "cultists_normal": lambda: [DampCultist(), DampCultist()],
    "chompers_normal": lambda: [Chomper(), Chomper(scream_first=True)],
    "bots_normal": lambda: [Stabbot(), Zapbot()],
    "raiders_normal": lambda: [AxeRubyRaider(), AxeRubyRaider()],
    "knights_elite": lambda: [FlailKnight()],
}

NORMAL_POOL = ["slimes_weak", "cultists_normal", "chompers_normal", "bots_normal", "raiders_normal"]
ELITE_POOL = ["knights_elite"]


def make_encounter(encounter_id: str) -> List[MonsterModel]:
    """인카운터 ID로 몬스터 목록 생성."""
    factory = ENCOUNTERS.get(encounter_id)
    if factory is None:
        raise KeyError(f"알 수 없는 인카운터: {encounter_id}")
    return factory()


def random_encounter(rng: random.Random, elite: bool = False) -> List[MonsterModel]:
    """풀에서 무작위 인카운터 생성."""
    pool = ELITE_POOL if elite else NORMAL_POOL
    return make_encounter(rng.choice(pool))
