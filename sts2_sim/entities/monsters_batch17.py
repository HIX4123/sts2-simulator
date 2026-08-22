"""
STS2 몬스터 배치 17 (Phase 6v) — Entomancer / KinFollower / TorchHeadAmalgam.
모든 수치는 Ascension 미적용 기본값.

Entomancer만 신규 파워(PersonalHivePower)를 쓰고, 나머지 둘은 이미 이식된
MinionPower만 붙는 순수 무브 그래프 몬스터다 — 원본에서 각각 TheKinBoss와
QueenBoss의 동료로 등장하지만 리더(KinPriest/Queen)가 아직 미이식이라
인카운터는 동료 쪽만 배치한다.
"""
from __future__ import annotations
from typing import List

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    MonsterModel, MonsterMoveStateMachine, MoveState,
    Intent, IntentType, MONSTER_REGISTRY,
)


class Entomancer(MonsterModel):
    """엔토맨서 — HP 145 고정. 개전 PersonalHivePower(1).

    원본(Entomancer.cs) 그래프 3단 순환:
      PHEROMONE_SPIT(벌집/힘 강화) → BEES(3딜 ×7) → SPEAR(18딜) → 처음으로.
    시작 무브는 SPIT이 아니라 BEES다(원본 initialState = moveState2).

    SPIT은 벌집이 이미 3 이상이면 더 늘리지 않고 힘 +2로 바꾼다 — 벌집이
    무한정 쌓여 Dazed로 덱을 덮어버리지 않게 하는 상한이다."""
    monster_id = "entomancer"
    title = "Entomancer"

    @property
    def min_initial_hp(self) -> int:
        return 145

    @property
    def max_initial_hp(self) -> int:
        return 145

    @property
    def spear_damage(self) -> int:
        return 18

    @property
    def bees_damage(self) -> int:
        return 3

    @property
    def bees_repeat(self) -> int:
        return 7

    @property
    def hive_cap(self) -> int:
        return 3

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import PersonalHivePower
        self.apply_power(PersonalHivePower(1))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        spit = MoveState("PHEROMONE_SPIT_MOVE", self._spit_move, Intent(IntentType.BUFF))
        bees = MoveState("BEES_MOVE", self._bees_move,
                         Intent(IntentType.ATTACK, damage=self.bees_damage,
                                times=self.bees_repeat))
        spear = MoveState("SPEAR_MOVE", self._spear_move,
                          Intent(IntentType.ATTACK, damage=self.spear_damage))

        spit.follow_up_state = bees
        bees.follow_up_state = spear
        spear.follow_up_state = spit

        return MonsterMoveStateMachine([spit, bees, spear], bees)

    def _spit_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import PersonalHivePower, Strength
        # 원본: 벌집이 없거나(hive == null) 이미 상한 이상이면 힘 +2만.
        if not self.has_power("personal_hive") or \
                self.get_power_amount("personal_hive") >= self.hive_cap:
            self.apply_power(Strength(2))
            return
        self.apply_power(PersonalHivePower(1))
        self.apply_power(Strength(1))

    def _bees_move(self, targets: List[Creature]) -> None:
        for _ in range(self.bees_repeat):
            for target in targets:
                self.attack(target, self.bees_damage)

    def _spear_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.spear_damage)


class KinFollower(MonsterModel):
    """킨 추종자 — HP 58~59. 개전 MinionPower(1).

    원본(KinFollower.cs) 그래프 3단 순환:
      QUICK_SLASH(5) → BOOMERANG(2딜 ×2) → POWER_DANCE(자기 힘 +2) → 처음으로.
    starts_with_dance=True면 POWER_DANCE부터 시작한다 — 원본 TheKinBoss가
    두 추종자 중 slot1 쪽에만 켜서 두 마리의 무브를 어긋나게 한다."""
    monster_id = "kin_follower"
    title = "Kin Follower"

    def __init__(self, starts_with_dance: bool = False):
        super().__init__()
        self.starts_with_dance = starts_with_dance

    @property
    def min_initial_hp(self) -> int:
        return 58

    @property
    def max_initial_hp(self) -> int:
        return 59

    @property
    def quick_slash_damage(self) -> int:
        return 5

    @property
    def boomerang_damage(self) -> int:
        return 2

    @property
    def boomerang_repeat(self) -> int:
        return 2

    @property
    def dance_strength(self) -> int:
        return 2

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import MinionPower
        self.apply_power(MinionPower(1))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        slash = MoveState("QUICK_SLASH_MOVE", self._slash_move,
                          Intent(IntentType.ATTACK, damage=self.quick_slash_damage))
        boomerang = MoveState("BOOMERANG_MOVE", self._boomerang_move,
                              Intent(IntentType.ATTACK, damage=self.boomerang_damage,
                                     times=self.boomerang_repeat))
        dance = MoveState("POWER_DANCE_MOVE", self._dance_move, Intent(IntentType.BUFF))

        slash.follow_up_state = boomerang
        boomerang.follow_up_state = dance
        dance.follow_up_state = slash

        initial = dance if self.starts_with_dance else slash
        return MonsterMoveStateMachine([slash, boomerang, dance], initial)

    def _slash_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.quick_slash_damage)

    def _boomerang_move(self, targets: List[Creature]) -> None:
        for _ in range(self.boomerang_repeat):
            for target in targets:
                self.attack(target, self.boomerang_damage)

    def _dance_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(self.dance_strength))


class TorchHeadAmalgam(MonsterModel):
    """횃불머리 혼합체 — HP 199 고정. 개전 MinionPower(1).

    원본(TorchHeadAmalgam.cs) 그래프 5노드:
      TACKLE(18) → TACKLE_2(18) → BEAM(8딜 ×3) → TACKLE_3(14) → TACKLE_4(14) → BEAM
    즉 앞의 강한 태클 2연타는 전투 시작에 한 번만 나오고, 그 뒤로는
    BEAM → 약태클 ×2 3턴 루프가 무한 반복된다."""
    monster_id = "torch_head_amalgam"
    title = "Torch Head Amalgam"

    @property
    def min_initial_hp(self) -> int:
        return 199

    @property
    def max_initial_hp(self) -> int:
        return 199

    @property
    def tackle_damage(self) -> int:
        return 18

    @property
    def weak_tackle_damage(self) -> int:
        return 14

    @property
    def beam_damage(self) -> int:
        return 8

    @property
    def beam_repeat(self) -> int:
        return 3

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import MinionPower
        self.apply_power(MinionPower(1))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        tackle1 = MoveState("TACKLE_MOVE", self._tackle_move,
                            Intent(IntentType.ATTACK, damage=self.tackle_damage))
        tackle2 = MoveState("TACKLE_2_MOVE", self._tackle_move,
                            Intent(IntentType.ATTACK, damage=self.tackle_damage))
        beam = MoveState("BEAM_MOVE", self._beam_move,
                         Intent(IntentType.ATTACK, damage=self.beam_damage,
                                times=self.beam_repeat))
        tackle3 = MoveState("TACKLE_3_MOVE", self._weak_tackle_move,
                            Intent(IntentType.ATTACK, damage=self.weak_tackle_damage))
        tackle4 = MoveState("TACKLE_4_MOVE", self._weak_tackle_move,
                            Intent(IntentType.ATTACK, damage=self.weak_tackle_damage))

        tackle1.follow_up_state = tackle2
        tackle2.follow_up_state = beam
        beam.follow_up_state = tackle3
        tackle3.follow_up_state = tackle4
        tackle4.follow_up_state = beam  # 앞의 강태클 2연타로는 돌아오지 않는다

        return MonsterMoveStateMachine(
            [tackle1, tackle2, beam, tackle3, tackle4], tackle1)

    def _tackle_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.tackle_damage)

    def _weak_tackle_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.weak_tackle_damage)

    def _beam_move(self, targets: List[Creature]) -> None:
        for _ in range(self.beam_repeat):
            for target in targets:
                self.attack(target, self.beam_damage)


BATCH17_MONSTERS = {
    "entomancer": Entomancer,
    "kin_follower": KinFollower,
    "torch_head_amalgam": TorchHeadAmalgam,
}

MONSTER_REGISTRY.update(BATCH17_MONSTERS)
