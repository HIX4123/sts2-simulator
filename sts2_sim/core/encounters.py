"""
STS2 인카운터 풀 — 디컴파일 Models.Encounters.* 구성 이식.

각 팩토리는 rng를 받아 원본 GenerateMonsters()의 무작위 구성을 재현한다.
미이식 몬스터가 포함된 인카운터는 부분 구성 (주석 표기).
"""
from __future__ import annotations
import random
from typing import Callable, Dict, List, Optional

from sts2_sim.entities.sts2_monster import (
    MonsterModel,
    TwigSlimeS, TwigSlimeM, Stabbot, Zapbot,
    AxeRubyRaider, FlailKnight, DampCultist, Chomper, FatGremlin,
)
from sts2_sim.entities.monsters_extra import (
    LeafSlimeS, LeafSlimeM, CalcifiedCultist,
    SpectralKnight, MagiKnight,
    AssassinRubyRaider, BruteRubyRaider, TrackerRubyRaider, CrossbowRubyRaider,
    SewerClam, SnappingJaxfruit, SneakyGremlin,
    Mawler, GlobeHead, VineShambler,
)


def _slimes_weak(rng: random.Random) -> List[MonsterModel]:
    """SlimesWeak: 소형 2종(순서 셔플) 사이에 중형 1종 무작위 — [소A, 중, 소B]."""
    smalls = [LeafSlimeS, TwigSlimeS]
    rng.shuffle(smalls)
    medium = rng.choice([LeafSlimeM, TwigSlimeM])
    return [smalls[0](), medium(), smalls[1]()]


def _raiders_normal(rng: random.Random) -> List[MonsterModel]:
    """RubyRaidersNormal: 레이더 5종 중 중복 없이 3종."""
    pool = [AxeRubyRaider, AssassinRubyRaider, BruteRubyRaider,
            CrossbowRubyRaider, TrackerRubyRaider]
    picks = rng.sample(pool, 3)
    return [cls() for cls in picks]


ENCOUNTERS: Dict[str, Callable[[random.Random], List[MonsterModel]]] = {
    # ── 원본 구성 그대로 ──
    "slimes_weak": _slimes_weak,
    "cultists_normal": lambda rng: [CalcifiedCultist(), DampCultist()],
    "chompers_normal": lambda rng: [Chomper(), Chomper(scream_first=True)],
    "raiders_normal": _raiders_normal,
    "knights_elite": lambda rng: [FlailKnight(), SpectralKnight(), MagiKnight()],
    "vine_shambler_normal": lambda rng: [VineShambler()],
    "mawler_normal": lambda rng: [Mawler()],
    "sewer_clam_normal": lambda rng: [SewerClam()],
    "globe_head_normal": lambda rng: [GlobeHead()],
    # ── 부분 구성 (미이식 몬스터 대체) ──
    # FabricatorNormal: Fabricator + 봇 소환 → 봇 2종만
    "bots_normal": lambda rng: [Stabbot(), Zapbot()],
    # SnappingJaxfruitNormal: Jaxfruit + Flyconid(미이식) → Jaxfruit ×2
    "jaxfruit_normal": lambda rng: [SnappingJaxfruit(), SnappingJaxfruit()],
    # GremlinMercNormal: GremlinMerc(미이식) ×2 + Fat/Sneaky → 그렘린 2종만
    "gremlins_weak": lambda rng: [SneakyGremlin(), FatGremlin()],
}

# 난이도 단계별 풀 (런 진행용) — 신선한 스타터 덱 그리디 승률 실측 기준 분류
# (20시드 실측: EASY/MEDIUM 전부 20/20, chompers 1/20, globe_head 0/20, knights 0/20)
EASY_POOL = ["slimes_weak", "bots_normal", "gremlins_weak"]
MEDIUM_POOL = ["raiders_normal", "vine_shambler_normal", "sewer_clam_normal",
               "jaxfruit_normal", "cultists_normal", "mawler_normal"]
HARD_POOL = ["chompers_normal", "globe_head_normal"]
ELITE_POOL = ["knights_elite"]
NORMAL_POOL = EASY_POOL + MEDIUM_POOL


def make_encounter(encounter_id: str, rng: Optional[random.Random] = None) -> List[MonsterModel]:
    """인카운터 ID로 몬스터 목록 생성."""
    factory = ENCOUNTERS.get(encounter_id)
    if factory is None:
        raise KeyError(f"알 수 없는 인카운터: {encounter_id}")
    return factory(rng or random.Random())


def random_encounter(rng: random.Random, elite: bool = False) -> List[MonsterModel]:
    """풀에서 무작위 인카운터 생성."""
    pool = ELITE_POOL if elite else NORMAL_POOL
    return make_encounter(rng.choice(pool), rng)


def random_encounter_from(rng: random.Random, pool: List[str]) -> List[MonsterModel]:
    """지정한 풀에서 무작위 인카운터 생성."""
    return make_encounter(rng.choice(pool), rng)
