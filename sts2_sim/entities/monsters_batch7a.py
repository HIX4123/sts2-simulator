"""
STS2 몬스터 배치 7a — 디컴파일 Models.Monsters.* 이식 (5종).
FuzzyWurmCrawler / Nibbit / Seapunk / TurretOperator / PunchConstruct.
모든 수치는 Ascension 미적용 기본값 (AscensionHelper.GetValueIfAscension의 마지막 인자).
"""
from __future__ import annotations
import random
from typing import TYPE_CHECKING, List, Optional

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    MonsterModel, MonsterMoveStateMachine, MoveState, RandomBranchState,
    Intent, IntentType, MONSTER_REGISTRY,
)

if TYPE_CHECKING:
    from sts2_sim.core.combat import CombatState


class FuzzyWurmCrawler(MonsterModel):
    """퍼지 웜 크롤러 — HP 55~57.

    원본(FuzzyWurmCrawler.cs) 그래프: FIRST_ACID_GOOP → INHALE → ACID_GOOP →
    FIRST_ACID_GOOP → ... (3노드 순환). FIRST_ACID_GOOP과 ACID_GOOP은 완전히
    동일한 공격 동작이며 전자는 ShouldShowMoveInBestiary에서만 감춰지는 표시용
    구분이지만, ACID_GOOP → FIRST_ACID_GOOP 전환에서 공격이 연속 2회 발생하므로
    (공격, 버프, 공격, 공격, 버프, 공격, ...) 2상태 교대(ATTACK↔BUFF)로 단순화하면
    안 되고 TurretOperator(UNLOAD→UNLOAD_2→RELOAD)와 동형인 3상태 그래프로 이식.
    """
    monster_id = "fuzzy_wurm_crawler"
    title = "Fuzzy Wurm Crawler"

    @property
    def min_initial_hp(self) -> int:
        return 55

    @property
    def max_initial_hp(self) -> int:
        return 57

    @property
    def acid_goop_damage(self) -> int:
        return 4

    @property
    def inhale_strength(self) -> int:
        return 7

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        first_goop = MoveState("FIRST_ACID_GOOP", self._acid_goop_move,
                               Intent(IntentType.ATTACK, damage=self.acid_goop_damage))
        inhale = MoveState("INHALE", self._inhale_move, Intent(IntentType.BUFF))
        acid_goop = MoveState("ACID_GOOP", self._acid_goop_move,
                              Intent(IntentType.ATTACK, damage=self.acid_goop_damage))
        first_goop.follow_up_state = inhale
        inhale.follow_up_state = acid_goop
        acid_goop.follow_up_state = first_goop
        return MonsterMoveStateMachine([first_goop, inhale, acid_goop], first_goop)

    def _acid_goop_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.acid_goop_damage)

    def _inhale_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(self.inhale_strength))


class Nibbit(MonsterModel):
    """니빗 — HP 42~46.

    원본(Nibbit.cs) 초기 상태는 ConditionalBranchState("INIT_MOVE")로, 인카운터
    위치 플래그(IsAlone/IsFront — Chomper의 scream_first와 동일한 배치 의존적
    초기화 패턴)에 따라 GenerateMoveStateMachine 호출 시점에 이미 후보가 좁혀진다:
      - is_alone → BUTT_MOVE
      - is_front (혼자가 아님) → SLICE_MOVE
      - 그 외(뒷줄, 혼자 아님) → HISS_MOVE
    이후 순환: BUTT_MOVE → SLICE_MOVE → HISS_MOVE → BUTT_MOVE → ...
    """
    monster_id = "nibbit"
    title = "Nibbit"

    def __init__(self, is_alone: bool = False, is_front: bool = False):
        super().__init__()
        self.is_alone = is_alone
        self.is_front = is_front

    @property
    def min_initial_hp(self) -> int:
        return 42

    @property
    def max_initial_hp(self) -> int:
        return 46

    @property
    def butt_damage(self) -> int:
        return 12

    @property
    def slice_damage(self) -> int:
        return 6

    @property
    def slice_block(self) -> int:
        return 5

    @property
    def hiss_strength(self) -> int:
        return 2

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        butt = MoveState("BUTT_MOVE", self._butt_move,
                         Intent(IntentType.ATTACK, damage=self.butt_damage))
        slice_move = MoveState("SLICE_MOVE", self._slice_move,
                               Intent(IntentType.ATTACK_DEFEND, damage=self.slice_damage))
        hiss = MoveState("HISS_MOVE", self._hiss_move, Intent(IntentType.BUFF))
        butt.follow_up_state = slice_move
        slice_move.follow_up_state = hiss
        hiss.follow_up_state = butt
        if self.is_alone:
            initial = butt
        elif self.is_front:
            initial = slice_move
        else:
            initial = hiss
        return MonsterMoveStateMachine([butt, slice_move, hiss], initial)

    def _butt_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.butt_damage)

    def _slice_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.slice_damage)
        self.gain_block(self.slice_block)

    def _hiss_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(self.hiss_strength))


class Seapunk(MonsterModel):
    """씨펑크 — HP 44~46. SEA_KICK 11딜 → SPINNING_KICK 2딜×4 → BUBBLE_BURP 7블록+힘+1 순환."""
    monster_id = "seapunk"
    title = "Seapunk"

    @property
    def min_initial_hp(self) -> int:
        return 44

    @property
    def max_initial_hp(self) -> int:
        return 46

    @property
    def sea_kick_damage(self) -> int:
        return 11

    @property
    def spinning_kick_damage(self) -> int:
        return 2

    @property
    def spinning_kick_repeat(self) -> int:
        return 4

    @property
    def bubble_block(self) -> int:
        return 7

    @property
    def bubble_strength(self) -> int:
        return 1

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        sea_kick = MoveState("SEA_KICK_MOVE", self._sea_kick_move,
                             Intent(IntentType.ATTACK, damage=self.sea_kick_damage))
        spinning_kick = MoveState("SPINNING_KICK_MOVE", self._spinning_kick_move,
                                  Intent(IntentType.ATTACK, damage=self.spinning_kick_damage,
                                         times=self.spinning_kick_repeat))
        bubble_burp = MoveState("BUBBLE_BURP_MOVE", self._bubble_burp_move,
                                Intent(IntentType.DEFEND_BUFF))
        sea_kick.follow_up_state = spinning_kick
        spinning_kick.follow_up_state = bubble_burp
        bubble_burp.follow_up_state = sea_kick
        return MonsterMoveStateMachine([sea_kick, spinning_kick, bubble_burp], sea_kick)

    def _sea_kick_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.sea_kick_damage)

    def _spinning_kick_move(self, targets: List[Creature]) -> None:
        for _ in range(self.spinning_kick_repeat):
            for target in targets:
                self.attack(target, self.spinning_kick_damage)

    def _bubble_burp_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.gain_block(self.bubble_block)
        self.apply_power(Strength(self.bubble_strength))


class TurretOperator(MonsterModel):
    """터렛 오퍼레이터 — HP 41 (고정). UNLOAD 3딜×5 (연속 2회) → RELOAD 힘+1 순환."""
    monster_id = "turret_operator"
    title = "Turret Operator"

    @property
    def min_initial_hp(self) -> int:
        return 41

    @property
    def fire_damage(self) -> int:
        return 3

    @property
    def fire_repeat(self) -> int:
        return 5

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        unload_1 = MoveState("UNLOAD_MOVE", self._unload_move,
                             Intent(IntentType.ATTACK, damage=self.fire_damage,
                                    times=self.fire_repeat))
        unload_2 = MoveState("UNLOAD_MOVE_2", self._unload_move,
                             Intent(IntentType.ATTACK, damage=self.fire_damage,
                                    times=self.fire_repeat))
        reload_move = MoveState("RELOAD_MOVE", self._reload_move, Intent(IntentType.BUFF))
        unload_1.follow_up_state = unload_2
        unload_2.follow_up_state = reload_move
        reload_move.follow_up_state = unload_1
        return MonsterMoveStateMachine([unload_1, unload_2, reload_move], unload_1)

    def _unload_move(self, targets: List[Creature]) -> None:
        for _ in range(self.fire_repeat):
            for target in targets:
                self.attack(target, self.fire_damage)

    def _reload_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(1))


class PunchConstruct(MonsterModel):
    """펀치 컨스트럭트 — HP 55 (고정), 개전 시 Artifact 1.
    READY 10블록 → FAST_PUNCH 5딜×2+(전체 대상)허약 1 → STRONG_PUNCH 14딜 순환.

    starts_with_fast_punch — 원본 StartsWithFastPunch(인카운터별 초기 상태, Chomper의
    scream_first와 동일 패턴). starting_hp_reduction — 원본 StartingHpReduction
    (0보다 크면 AfterAddedToRoom에서 SetCurrentHpInternal로 HP를 직접 감소, 최소 1 유지);
    두 값 모두 인카운터 설정에서 주입되는 값이라 기본값은 0/False.
    """
    monster_id = "punch_construct"
    title = "Punch Construct"

    def __init__(self, starts_with_fast_punch: bool = False, starting_hp_reduction: int = 0):
        super().__init__()
        self.starts_with_fast_punch = starts_with_fast_punch
        self.starting_hp_reduction = starting_hp_reduction

    @property
    def min_initial_hp(self) -> int:
        return 55

    @property
    def strong_punch_damage(self) -> int:
        return 14

    @property
    def fast_punch_damage(self) -> int:
        return 5

    @property
    def fast_punch_repeat(self) -> int:
        return 2

    @property
    def ready_block(self) -> int:
        return 10

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import Artifact
        self.apply_power(Artifact(1))
        if self.starting_hp_reduction > 0:
            self._current_hp = max(1, self._current_hp - self.starting_hp_reduction)

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        ready = MoveState("READY_MOVE", self._ready_move, Intent(IntentType.DEFEND))
        fast_punch = MoveState("FAST_PUNCH_MOVE", self._fast_punch_move,
                               Intent(IntentType.ATTACK_DEBUFF, damage=self.fast_punch_damage,
                                      times=self.fast_punch_repeat))
        strong_punch = MoveState("STRONG_PUNCH_MOVE", self._strong_punch_move,
                                 Intent(IntentType.ATTACK, damage=self.strong_punch_damage))
        ready.follow_up_state = fast_punch
        fast_punch.follow_up_state = strong_punch
        strong_punch.follow_up_state = ready
        initial = fast_punch if self.starts_with_fast_punch else ready
        return MonsterMoveStateMachine([ready, fast_punch, strong_punch], initial)

    def _ready_move(self, targets: List[Creature]) -> None:
        self.gain_block(self.ready_block)

    def _fast_punch_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Frail
        for _ in range(self.fast_punch_repeat):
            for target in targets:
                self.attack(target, self.fast_punch_damage)
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Frail(1))

    def _strong_punch_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.strong_punch_damage)


BATCH_7A_MONSTERS = {
    "fuzzy_wurm_crawler": FuzzyWurmCrawler,
    "nibbit": Nibbit,
    "seapunk": Seapunk,
    "turret_operator": TurretOperator,
    "punch_construct": PunchConstruct,
}

MONSTER_REGISTRY.update(BATCH_7A_MONSTERS)
