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
    LivingShield,
)
from sts2_sim.entities.monsters_batch7a import (
    FuzzyWurmCrawler, Nibbit, Seapunk, TurretOperator, PunchConstruct,
)
from sts2_sim.entities.monsters_batch7b import (
    DevotedSculptor, Toadpole, SludgeSpinner, HauntedShip,
)
from sts2_sim.entities.monsters_batch7c import (
    Myte, FrogKnight,
)
from sts2_sim.entities.monsters_batch8 import (
    MysteriousKnight, Flyconid, ShrinkerBeetle, LouseProgenitor, SpinyToad,
    Byrdonis, FossilStalker, SoulFysh,
)
from sts2_sim.entities.monsters_batch9 import (
    CorpseSlug, SkulkingColony, TerrorEel, PhantasmalGardener, LagavulinMatriarch,
)
from sts2_sim.entities.monsters_batch10 import WaterfallGiant
from sts2_sim.entities.monsters_batch11 import (
    SlimedBerserker, SlitheringStrangler, Exoskeleton, HunterKiller,
    MechaKnight, BygoneEffigy, Inklet, ScrollOfBiting, Vantom,
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


def _nibbits_weak(rng: random.Random) -> List[MonsterModel]:
    """NibbitsWeak: Nibbit 1마리, IsAlone=True로 시작 (BUTT_MOVE부터)."""
    return [Nibbit(is_alone=True)]


def _nibbits_normal(rng: random.Random) -> List[MonsterModel]:
    """NibbitsNormal: Nibbit 2마리, front 슬롯만 IsFront=True (SLICE_MOVE부터)."""
    return [Nibbit(is_front=True), Nibbit()]


def _toadpoles_weak(rng: random.Random) -> List[MonsterModel]:
    """ToadpolesWeak: Toadpole 2마리, 1마리만 IsFront=True (SPIKEN_MOVE부터)."""
    return [Toadpole(is_front=True), Toadpole(is_front=False)]


def _mytes_normal(rng: random.Random) -> List[MonsterModel]:
    """MytesNormal: Myte 2마리, first→TOXIC_MOVE / second→SUCK_MOVE로 시작."""
    return [Myte(), Myte(is_second=True)]


def _flyconid_normal(rng: random.Random) -> List[MonsterModel]:
    """FlyconidNormal: 중형 슬라임(LeafSlimeM/TwigSlimeM 중 무작위 1) + Flyconid."""
    medium = rng.choice([LeafSlimeM, TwigSlimeM])
    return [medium(), Flyconid()]


def _corpse_slugs(rng: random.Random, count: int) -> List[MonsterModel]:
    """CorpseSlugsNormal(3)/Weak(2) 공통: 원본 EnsureCorpseSlugsStartWithDifferentMoves —
    공유 인카운터 rng로 시작 인덱스를 뽑고 슬러그마다 +1씩 밀어 서로 다른
    시작 무브를 배정한다 (마릿수가 3 이하이므로 항상 전부 다름)."""
    start = rng.randrange(3)
    return [CorpseSlug(starter_move_idx=start + i) for i in range(count)]


def _phantasmal_gardeners(rng: random.Random) -> List[MonsterModel]:
    """PhantasmalGardenersElite: 4마리, 슬롯 first/second/third/fourth 고정 배정
    (원본 GenerateMonsters — 무작위 없이 고정 순서)."""
    gardeners = [PhantasmalGardener() for _ in range(4)]
    for gardener, slot in zip(gardeners, ("first", "second", "third", "fourth")):
        gardener.slot_name = slot
    return gardeners


def _exoskeletons(rng: random.Random, count: int) -> List[MonsterModel]:
    """ExoskeletonsNormal(4)/Weak(3): 슬롯 first/second/third(/fourth) 고정 배정.
    Exoskeleton의 INIT_MOVE가 슬롯으로 시작 무브를 결정하므로 슬롯 배정이 필수.
    Weak는 슬롯이 3개뿐이라 fourth(RAND 시작) 개체가 나오지 않는다."""
    slots = ("first", "second", "third", "fourth")[:count]
    roaches = []
    for slot in slots:
        roach = Exoskeleton()
        roach.slot_name = slot
        roaches.append(roach)
    return roaches


def _inklets_normal(rng: random.Random) -> List[MonsterModel]:
    """InkletsNormal: 3마리 중 가운데만 MiddleInklet=True (WHIRLWIND부터 시작)."""
    return [Inklet(), Inklet(middle_inklet=True), Inklet()]


def _scrolls_of_biting(rng: random.Random, count: int) -> List[MonsterModel]:
    """ScrollsOfBitingNormal(4)/Weak(3): 앞 3마리는 무작위 시작 인덱스에서
    +1씩 밀어 서로 다른 시작 무브를 갖고, Normal의 4번째만 인덱스 2 고정
    (원본 GenerateMonsters — (num+3)%3 회전이 아니라 상수 2)."""
    start = rng.randrange(3)
    scrolls = [ScrollOfBiting(starter_move_idx=(start + i) % 3) for i in range(3)]
    if count == 4:
        scrolls.append(ScrollOfBiting(starter_move_idx=2))
    return scrolls


def _slithering_strangler_normal(rng: random.Random) -> List[MonsterModel]:
    """SlitheringStranglerNormal: 보조 적 구성 3종 중 1개를 뽑고 마지막에
    Strangler를 붙인다 — SnappingJaxfruit 1 / 중형 슬라임 1 / 소형 슬라임 2.
    소형 2마리는 각각 독립 추첨이라 같은 종이 두 번 나올 수 있다 (원본
    NextItem 2회 — slimes_weak의 셔플 방식과 다르다)."""
    kind = rng.choice(("jaxfruit", "medium_slime", "small_slimes"))
    if kind == "jaxfruit":
        others: List[MonsterModel] = [SnappingJaxfruit()]
    elif kind == "medium_slime":
        others = [rng.choice([LeafSlimeM, TwigSlimeM])()]
    else:
        others = [rng.choice([LeafSlimeS, TwigSlimeS])() for _ in range(2)]
    return [*others, SlitheringStrangler()]


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
    "jaxfruit_normal": lambda rng: [SnappingJaxfruit(), Flyconid()],
    # GremlinMercNormal: GremlinMerc(미이식) ×2 + Fat/Sneaky → 그렘린 2종만
    "gremlins_weak": lambda rng: [SneakyGremlin(), FatGremlin()],
    # ── Phase 6j 배치1 (원본 구성 그대로) ──
    "fuzzy_wurm_crawler_weak": lambda rng: [FuzzyWurmCrawler()],
    "nibbits_weak": _nibbits_weak,
    "nibbits_normal": _nibbits_normal,
    "seapunk_weak": lambda rng: [Seapunk()],
    "seapunk_normal": lambda rng: [CalcifiedCultist(), Seapunk()],
    "turret_operator_weak": lambda rng: [LivingShield(), TurretOperator()],
    "punch_construct_normal": lambda rng: [PunchConstruct()],
    "devoted_sculptor_weak": lambda rng: [DevotedSculptor()],
    "toadpoles_weak": _toadpoles_weak,
    "sludge_spinner_weak": lambda rng: [SludgeSpinner()],
    "haunted_ship_normal": lambda rng: [HauntedShip()],
    "mytes_normal": _mytes_normal,
    "frog_knight_normal": lambda rng: [FrogKnight()],
    # Wriggler: 독립 인카운터 없음 — 원본에서는 PhrogParasite(미이식, AfterDeath 소환)
    # 전용 소환체. KinPriest: TheKinBoss(보스, KinFollower 미이식) 전용이라 미배치.
    # ── Phase 6k 배치8 (원본 구성 그대로) ──
    "mysterious_knight_event": lambda rng: [MysteriousKnight()],
    "flyconid_normal": _flyconid_normal,
    "shrinker_beetle_weak": lambda rng: [ShrinkerBeetle()],
    "louse_progenitor_normal": lambda rng: [LouseProgenitor()],
    "spiny_toad_normal": lambda rng: [SpinyToad()],
    "byrdonis_elite": lambda rng: [Byrdonis()],
    "fossil_stalker_normal": lambda rng: [FossilStalker()],
    "soul_fysh_boss": lambda rng: [SoulFysh()],
    # ── Phase 6l (Act1 완결, 원본 구성 그대로) ──
    "corpse_slugs_normal": lambda rng: _corpse_slugs(rng, 3),
    "corpse_slugs_weak": lambda rng: _corpse_slugs(rng, 2),
    "skulking_colony_elite": lambda rng: [SkulkingColony()],
    "terror_eel_elite": lambda rng: [TerrorEel()],
    "phantasmal_gardeners_elite": _phantasmal_gardeners,
    "lagavulin_matriarch_boss": lambda rng: [LagavulinMatriarch()],
    # ── Phase 6m ──
    "waterfall_giant_boss": lambda rng: [WaterfallGiant()],
    # ── Phase 6n 배치11 (원본 구성 그대로) ──
    "slimed_berserker_normal": lambda rng: [SlimedBerserker()],
    "slithering_strangler_normal": _slithering_strangler_normal,
    "exoskeletons_normal": lambda rng: _exoskeletons(rng, 4),
    "exoskeletons_weak": lambda rng: _exoskeletons(rng, 3),
    "hunter_killer_normal": lambda rng: [HunterKiller()],
    "mecha_knight_elite": lambda rng: [MechaKnight()],
    "bygone_effigy_elite": lambda rng: [BygoneEffigy()],
    "inklets_normal": _inklets_normal,
    "scrolls_of_biting_normal": lambda rng: _scrolls_of_biting(rng, 4),
    "scrolls_of_biting_weak": lambda rng: _scrolls_of_biting(rng, 3),
    "vantom_boss": lambda rng: [Vantom()],
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
