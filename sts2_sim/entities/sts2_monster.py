"""
STS2 MonsterModel — 디컴파일 MegaCrit.Sts2.Core.Models.Monsters.* 이식.

- MonsterModel은 Creature를 상속 (HP/블록/파워/데미지 파이프라인 공유)
- MonsterMoveStateMachine: MoveState(고정 전환) + RandomBranchState(가중치 분기)
- 모든 수치는 디컴파일 기준값 (Ascension 미적용 기본값)
"""
from __future__ import annotations
import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable, List, Optional

from sts2_sim.entities.creature import Creature

if TYPE_CHECKING:
    from sts2_sim.core.combat import CombatState


class IntentType(Enum):
    """STS2 Intent 타입."""
    ATTACK = auto()
    ATTACK_BUFF = auto()
    ATTACK_DEBUFF = auto()
    ATTACK_DEFEND = auto()
    BUFF = auto()
    DEBUFF = auto()
    DEFEND = auto()
    DEFEND_BUFF = auto()
    DEFEND_DEBUFF = auto()
    STATUS = auto()
    SLEEP = auto()
    STUN = auto()
    ESCAPE = auto()
    HIDDEN = auto()
    UNKNOWN = auto()


@dataclass
class Intent:
    """인텐트 정보."""
    intent_type: IntentType
    damage: int = 0
    times: int = 1


class MonsterState:
    """상태 머신 노드 베이스."""
    def __init__(self, name: str):
        self.name = name


class MoveState(MonsterState):
    """몬스터의 한 행동 상태."""
    def __init__(self, name: str, execute: Callable, intent: Intent):
        super().__init__(name)
        self.execute = execute
        self.intent = intent
        self.follow_up_state: Optional[MonsterState] = None


class RandomBranchState(MonsterState):
    """가중치 기반 무작위 분기 (디컴파일 RandomBranchState 대응).

    cannot_repeat=True인 분기는 직전 행동과 같으면 선택되지 않는다
    (디컴파일 MoveRepeatType.CannotRepeat).
    """
    def __init__(self, name: str):
        super().__init__(name)
        self.branches: List[tuple] = []  # (state, weight, cannot_repeat)

    def add_branch(self, state: MoveState, weight: int = 1, cannot_repeat: bool = False):
        self.branches.append((state, weight, cannot_repeat))

    def resolve(self, rng: random.Random, last_move_name: Optional[str]) -> MoveState:
        candidates = [
            (s, w) for s, w, cr in self.branches
            if not (cr and s.name == last_move_name)
        ]
        if not candidates:
            candidates = [(s, w) for s, w, _ in self.branches]
        states = [s for s, _ in candidates]
        weights = [w for _, w in candidates]
        return rng.choices(states, weights=weights, k=1)[0]


class MonsterMoveStateMachine:
    """상태 머신: 몬스터의 행동 순서를 관리.

    initial_state로 RandomBranchState도 허용 — setup_for_combat에서 rng 주입 후
    resolve_initial()이 시드 rng로 첫 행동을 결정한다 (재현성 보장).
    """

    def __init__(self, states: List[MonsterState], initial_state: MonsterState):
        self.states = states
        self.current_state: MonsterState = initial_state
        self.rng: random.Random = random.Random()
        self._last_move_name: Optional[str] = None

    def resolve_initial(self) -> None:
        """초기 상태가 RandomBranchState면 현재 rng로 해석."""
        if isinstance(self.current_state, RandomBranchState):
            self.current_state = self.current_state.resolve(self.rng, None)

    def get_current_intent(self) -> Intent:
        return self.current_state.intent

    def get_current_move_name(self) -> str:
        return self.current_state.name

    def execute_move(self, targets: List[Creature]) -> None:
        if self.current_state.execute:
            self.current_state.execute(targets)
        self._last_move_name = self.current_state.name

    def advance_state(self) -> None:
        nxt = self.current_state.follow_up_state
        while isinstance(nxt, RandomBranchState):
            nxt = nxt.resolve(self.rng, self._last_move_name)
        if nxt is not None:
            self.current_state = nxt


class MonsterModel(Creature):
    """STS2 몬스터 베이스 (MonsterModel 대응). Creature 상속으로 파워/블록 공유."""

    monster_id: str = "unknown_monster"
    title: str = "Unknown Monster"

    def __init__(self):
        super().__init__(self.title, 1)
        self._move_state_machine: Optional[MonsterMoveStateMachine] = None
        self.combat_state: Optional["CombatState"] = None
        self.escaped = False

    @property
    def min_initial_hp(self) -> int:
        return 0

    @property
    def max_initial_hp(self) -> int:
        return self.min_initial_hp

    @property
    def is_gone(self) -> bool:
        """전투에서 제거됨 (사망 또는 도주)."""
        return self.is_dead or self.escaped

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        nothing = MoveState("NOTHING", self._nothing_move, Intent(IntentType.HIDDEN))
        nothing.follow_up_state = nothing
        return MonsterMoveStateMachine([nothing], nothing)

    def _nothing_move(self, targets: List[Creature]) -> None:
        pass

    def setup_for_combat(self, state: Optional["CombatState"], rng: Optional[random.Random] = None) -> None:
        """전투 시작 시 초기화. 이후 after_added_to_room() 트리거."""
        self.combat_state = state
        self._max_hp = self.max_initial_hp
        self._current_hp = self.max_initial_hp
        self._block = 0
        self.escaped = False
        self._move_state_machine = self.generate_move_state_machine()
        if rng is not None:
            self._move_state_machine.rng = rng
        self._move_state_machine.resolve_initial()
        self.after_added_to_room()

    def after_added_to_room(self) -> None:
        """전투 투입 직후 (개전 버프 등, 서브클래스 오버라이드)."""
        pass

    def get_current_intent(self) -> Intent:
        if self._move_state_machine:
            return self._move_state_machine.get_current_intent()
        return Intent(IntentType.UNKNOWN)

    def take_turn(self, targets: List[Creature]) -> None:
        """현재 행동 실행 후 다음 상태로 전환."""
        if self._move_state_machine:
            self._move_state_machine.execute_move(targets)
            self._move_state_machine.advance_state()

    def attack(self, target: Creature, base_damage: int) -> None:
        """공격 파이프라인 (자신의 Strength/Weak 반영)."""
        target.take_damage(self.compute_attack_damage(base_damage), source=self)

    def add_status_to_player_discard(self, card_id: str, count: int) -> None:
        """플레이어 버림 더미에 상태이상 카드 삽입 (Dazed/Slimed)."""
        if self.combat_state and hasattr(self.combat_state, "add_status_to_discard"):
            self.combat_state.add_status_to_discard(card_id, count)

    def escape(self) -> None:
        """전투에서 도주 (FatGremlin 등)."""
        self.escaped = True

    def __repr__(self) -> str:
        return f"{self.title}({self._current_hp}/{self._max_hp})"


# ══════════════════════════════════════════
# 테스트 지원 몬스터 (디컴파일에도 존재)
# ══════════════════════════════════════════

class BigDummy(MonsterModel):
    """테스트용 더미 (HP 9999)."""
    monster_id = "big_dummy"
    title = "Big Dummy"

    @property
    def min_initial_hp(self) -> int:
        return 9999


class SingleAttackMoveMonster(MonsterModel):
    """단일 공격 테스트 몬스터 (POKE 1딜)."""
    monster_id = "single_attack"
    title = "Single Attack Monster"

    @property
    def min_initial_hp(self) -> int:
        return 999

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        poke = MoveState("POKE", self._poke_move, Intent(IntentType.ATTACK, damage=1))
        poke.follow_up_state = poke
        return MonsterMoveStateMachine([poke], poke)

    def _poke_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, 1)


class MultiAttackMoveMonster(MonsterModel):
    """다중 공격 테스트 몬스터 (2딜×3)."""
    monster_id = "multi_attack"
    title = "Multi Attack Monster"

    @property
    def min_initial_hp(self) -> int:
        return 999

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        atk = MoveState("ATTACK", self._attack_move, Intent(IntentType.ATTACK, damage=2, times=3))
        atk.follow_up_state = atk
        return MonsterMoveStateMachine([atk], atk)

    def _attack_move(self, targets: List[Creature]) -> None:
        for _ in range(3):
            for target in targets:
                self.attack(target, 2)


# ══════════════════════════════════════════
# 실전 몬스터 (디컴파일 수치)
# ══════════════════════════════════════════

class TwigSlimeS(MonsterModel):
    """나뭇가지 슬라임 (소) — HP 7~11, TACKLE 4딜."""
    monster_id = "twig_slime_s"
    title = "Twig Slime (S)"

    @property
    def min_initial_hp(self) -> int:
        return 7

    @property
    def max_initial_hp(self) -> int:
        return 11

    @property
    def tackle_damage(self) -> int:
        return 4

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        tackle = MoveState("TACKLE_MOVE", self._tackle_move,
                           Intent(IntentType.ATTACK, damage=self.tackle_damage))
        tackle.follow_up_state = tackle
        return MonsterMoveStateMachine([tackle], tackle)

    def _tackle_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.tackle_damage)


class TwigSlimeM(MonsterModel):
    """나뭇가지 슬라임 (중) — HP 26~28. POKEY_POUNCE 11딜 / STICKY_SHOT Slimed 1장."""
    monster_id = "twig_slime_m"
    title = "Twig Slime (M)"

    @property
    def min_initial_hp(self) -> int:
        return 26

    @property
    def max_initial_hp(self) -> int:
        return 28

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        pounce = MoveState("POKEY_POUNCE_MOVE", self._pounce_move,
                           Intent(IntentType.ATTACK, damage=11))
        sticky = MoveState("STICKY_SHOT_MOVE", self._sticky_move,
                           Intent(IntentType.STATUS))
        branch = RandomBranchState("RAND")
        branch.add_branch(pounce, weight=2)
        branch.add_branch(sticky, weight=1, cannot_repeat=True)
        pounce.follow_up_state = branch
        sticky.follow_up_state = branch
        return MonsterMoveStateMachine([pounce, sticky, branch], sticky)

    def _pounce_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, 11)

    def _sticky_move(self, targets: List[Creature]) -> None:
        self.add_status_to_player_discard("slimed", 1)


class Stabbot(MonsterModel):
    """스탭봇 — HP 18~23, STAB 11딜 + 허약 1."""
    monster_id = "stabbot"
    title = "Stabbot"

    @property
    def min_initial_hp(self) -> int:
        return 18

    @property
    def max_initial_hp(self) -> int:
        return 23

    @property
    def stab_damage(self) -> int:
        return 11

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        stab = MoveState("STAB_MOVE", self._stab_move,
                         Intent(IntentType.ATTACK_DEBUFF, damage=self.stab_damage))
        stab.follow_up_state = stab
        return MonsterMoveStateMachine([stab], stab)

    def _stab_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Frail
        for target in targets:
            self.attack(target, self.stab_damage)
            if hasattr(target, "apply_power"):
                target.apply_power(Frail(1))


class Zapbot(MonsterModel):
    """잽봇 — HP 18~23, ZAP 14딜. (개전 시 HighVoltage 2 — 파워 미이식)."""
    monster_id = "zapbot"
    title = "Zapbot"

    @property
    def min_initial_hp(self) -> int:
        return 18

    @property
    def max_initial_hp(self) -> int:
        return 23

    @property
    def zap_damage(self) -> int:
        return 14

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        zap = MoveState("ZAP", self._zap_move,
                        Intent(IntentType.ATTACK, damage=self.zap_damage))
        zap.follow_up_state = zap
        return MonsterMoveStateMachine([zap], zap)

    def _zap_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.zap_damage)


class Guardbot(MonsterModel):
    """가드봇 — HP 16~20. GUARD: Fabricator 아군에 15블록 (Fabricator 미이식 시 무동작)."""
    monster_id = "guardbot"
    title = "Guardbot"

    @property
    def min_initial_hp(self) -> int:
        return 16

    @property
    def max_initial_hp(self) -> int:
        return 20

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        guard = MoveState("GUARD_MOVE", self._guard_move, Intent(IntentType.DEFEND))
        guard.follow_up_state = guard
        return MonsterMoveStateMachine([guard], guard)

    def _guard_move(self, targets: List[Creature]) -> None:
        if self.combat_state is None:
            return
        for ally in getattr(self.combat_state, "monsters", []):
            if getattr(ally, "monster_id", "") == "fabricator" and not ally.is_gone:
                ally.gain_block(15)


class AxeRubyRaider(MonsterModel):
    """도끼 루비 약탈자 — HP 20~22. SWING 5딜+5블록 ×2 → BIG_SWING 12딜 순환."""
    monster_id = "axe_ruby_raider"
    title = "Axe Ruby Raider"

    @property
    def min_initial_hp(self) -> int:
        return 20

    @property
    def max_initial_hp(self) -> int:
        return 22

    @property
    def swing_damage(self) -> int:
        return 5

    @property
    def swing_block(self) -> int:
        return 5

    @property
    def big_swing_damage(self) -> int:
        return 12

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        swing1 = MoveState("SWING_1", self._swing_move,
                           Intent(IntentType.ATTACK_DEFEND, damage=self.swing_damage))
        swing2 = MoveState("SWING_2", self._swing_move,
                           Intent(IntentType.ATTACK_DEFEND, damage=self.swing_damage))
        big = MoveState("BIG_SWING", self._big_swing_move,
                        Intent(IntentType.ATTACK, damage=self.big_swing_damage))
        swing1.follow_up_state = swing2
        swing2.follow_up_state = big
        big.follow_up_state = swing1
        return MonsterMoveStateMachine([swing1, swing2, big], swing1)

    def _swing_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.swing_damage)
        self.gain_block(self.swing_block)

    def _big_swing_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.big_swing_damage)


class FlailKnight(MonsterModel):
    """도리깨 기사 (엘리트) — HP 101.
    WAR_CHANT 힘+3 (연속 불가) / FLAIL 9딜×2 (w2) / RAM 15딜 (w2). 초기 RAM."""
    monster_id = "flail_knight"
    title = "Flail Knight"

    @property
    def min_initial_hp(self) -> int:
        return 101

    @property
    def flail_damage(self) -> int:
        return 9

    @property
    def ram_damage(self) -> int:
        return 15

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        chant = MoveState("WAR_CHANT", self._war_chant_move, Intent(IntentType.BUFF))
        flail = MoveState("FLAIL_MOVE", self._flail_move,
                          Intent(IntentType.ATTACK, damage=self.flail_damage, times=2))
        ram = MoveState("RAM_MOVE", self._ram_move,
                        Intent(IntentType.ATTACK, damage=self.ram_damage))
        branch = RandomBranchState("RAND")
        branch.add_branch(chant, weight=1, cannot_repeat=True)
        branch.add_branch(flail, weight=2)
        branch.add_branch(ram, weight=2)
        chant.follow_up_state = branch
        flail.follow_up_state = branch
        ram.follow_up_state = branch
        return MonsterMoveStateMachine([chant, flail, ram, branch], ram)

    def _war_chant_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(3))

    def _flail_move(self, targets: List[Creature]) -> None:
        for _ in range(2):
            for target in targets:
                self.attack(target, self.flail_damage)

    def _ram_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.ram_damage)


class DampCultist(MonsterModel):
    """축축한 광신도 — HP 51~53. INCANTATION 의식+5 → DARK_STRIKE 1딜 반복."""
    monster_id = "damp_cultist"
    title = "Damp Cultist"

    @property
    def min_initial_hp(self) -> int:
        return 51

    @property
    def max_initial_hp(self) -> int:
        return 53

    @property
    def dark_strike_damage(self) -> int:
        return 1

    @property
    def incantation_amount(self) -> int:
        return 5

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        incant = MoveState("INCANTATION_MOVE", self._incantation_move, Intent(IntentType.BUFF))
        strike = MoveState("DARK_STRIKE_MOVE", self._dark_strike_move,
                           Intent(IntentType.ATTACK, damage=self.dark_strike_damage))
        incant.follow_up_state = strike
        strike.follow_up_state = strike
        return MonsterMoveStateMachine([incant, strike], incant)

    def _incantation_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Ritual
        self.apply_power(Ritual(self.incantation_amount))

    def _dark_strike_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.dark_strike_damage)


class Chomper(MonsterModel):
    """쵸퍼 — HP 60~64, 개전 시 Artifact 2.
    CLAMP 8딜×2 ↔ SCREECH Dazed 3장 삽입."""
    monster_id = "chomper"
    title = "Chomper"

    def __init__(self, scream_first: bool = False):
        super().__init__()
        self.scream_first = scream_first

    @property
    def min_initial_hp(self) -> int:
        return 60

    @property
    def max_initial_hp(self) -> int:
        return 64

    @property
    def clamp_damage(self) -> int:
        return 8

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import Artifact
        self.apply_power(Artifact(2))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        clamp = MoveState("CLAMP_MOVE", self._clamp_move,
                          Intent(IntentType.ATTACK, damage=self.clamp_damage, times=2))
        screech = MoveState("SCREECH_MOVE", self._screech_move, Intent(IntentType.STATUS))
        clamp.follow_up_state = screech
        screech.follow_up_state = clamp
        initial = screech if self.scream_first else clamp
        return MonsterMoveStateMachine([clamp, screech], initial)

    def _clamp_move(self, targets: List[Creature]) -> None:
        for _ in range(2):
            for target in targets:
                self.attack(target, self.clamp_damage)

    def _screech_move(self, targets: List[Creature]) -> None:
        self.add_status_to_player_discard("dazed", 3)


class FatGremlin(MonsterModel):
    """뚱보 그렘린 — HP 13~17. 소환 첫 턴 대기 후 도주."""
    monster_id = "fat_gremlin"
    title = "Fat Gremlin"

    @property
    def min_initial_hp(self) -> int:
        return 13

    @property
    def max_initial_hp(self) -> int:
        return 17

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        spawned = MoveState("SPAWNED_MOVE", self._spawned_move, Intent(IntentType.STUN))
        flee = MoveState("FLEE_MOVE", self._flee_move, Intent(IntentType.ESCAPE))
        spawned.follow_up_state = flee
        flee.follow_up_state = flee
        return MonsterMoveStateMachine([spawned, flee], spawned)

    def _spawned_move(self, targets: List[Creature]) -> None:
        pass

    def _flee_move(self, targets: List[Creature]) -> None:
        self.escape()


# ── HP만 확정, 행동은 단순화된 몬스터 (TODO: 디컴파일 행동 이식) ──

class Parafright(MonsterModel):
    """파라프라이트 — HP 21 (행동 단순화)."""
    monster_id = "parafright"
    title = "Parafright"

    @property
    def min_initial_hp(self) -> int:
        return 21

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        atk = MoveState("ATTACK", self._attack_move, Intent(IntentType.ATTACK, damage=3))
        atk.follow_up_state = atk
        return MonsterMoveStateMachine([atk], atk)

    def _attack_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, 3)


class EyeWithTeeth(MonsterModel):
    """이빨 달린 눈 — HP 6 (행동 단순화)."""
    monster_id = "eye_with_teeth"
    title = "Eye With Teeth"

    @property
    def min_initial_hp(self) -> int:
        return 6

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        bite = MoveState("BITE", self._bite_move, Intent(IntentType.ATTACK, damage=2))
        bite.follow_up_state = bite
        return MonsterMoveStateMachine([bite], bite)

    def _bite_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, 2)


class BattleFriendV1(MonsterModel):
    """전투 친구 V1 — HP 75 (테스트 지원, 행동 단순화)."""
    monster_id = "battle_friend_v1"
    title = "Battle Friend V1"

    @property
    def min_initial_hp(self) -> int:
        return 75

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        support = MoveState("SUPPORT", self._support_move, Intent(IntentType.BUFF))
        atk = MoveState("ATTACK", self._attack_move, Intent(IntentType.ATTACK, damage=8))
        support.follow_up_state = atk
        atk.follow_up_state = support
        return MonsterMoveStateMachine([support, atk], support)

    def _support_move(self, targets: List[Creature]) -> None:
        self.gain_block(10)

    def _attack_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, 8)


class BattleFriendV2(MonsterModel):
    """전투 친구 V2 — HP 150 (테스트 지원, 행동 단순화)."""
    monster_id = "battle_friend_v2"
    title = "Battle Friend V2"

    @property
    def min_initial_hp(self) -> int:
        return 150

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        support = MoveState("SUPPORT", self._support_move, Intent(IntentType.BUFF))
        atk = MoveState("ATTACK", self._attack_move, Intent(IntentType.ATTACK, damage=16))
        support.follow_up_state = atk
        atk.follow_up_state = support
        return MonsterMoveStateMachine([support, atk], support)

    def _support_move(self, targets: List[Creature]) -> None:
        self.gain_block(20)

    def _attack_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, 16)


MONSTER_REGISTRY = {
    "big_dummy": BigDummy,
    "single_attack": SingleAttackMoveMonster,
    "multi_attack": MultiAttackMoveMonster,
    "twig_slime_s": TwigSlimeS,
    "twig_slime_m": TwigSlimeM,
    "stabbot": Stabbot,
    "zapbot": Zapbot,
    "guardbot": Guardbot,
    "axe_ruby_raider": AxeRubyRaider,
    "flail_knight": FlailKnight,
    "damp_cultist": DampCultist,
    "chomper": Chomper,
    "fat_gremlin": FatGremlin,
    "parafright": Parafright,
    "eye_with_teeth": EyeWithTeeth,
    "battle_friend_v1": BattleFriendV1,
    "battle_friend_v2": BattleFriendV2,
}


def create_monster(monster_id: str) -> Optional[MonsterModel]:
    """몬스터 생성."""
    cls = MONSTER_REGISTRY.get(monster_id)
    return cls() if cls else None
