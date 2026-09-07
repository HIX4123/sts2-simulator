"""
STS2 몬스터 배치 19 (S1.M3.B19) — KaiserCrabBoss: Crusher / Rocket.
모든 수치는 Ascension 미적용 기본값.

카이저 크랩 보스는 좌·우 두 팔(Crusher=왼팔, Rocket=오른팔)로 구성된 보스다.
두 팔 모두 고정 5무브 순환이며, 어느 한쪽이 먼저 죽으면 남은 팔이 CrabRage로
폭주한다(힘 +6, 블록 99). Rocket이 개전 시 플레이어에게 SurroundedPower를
걸어, 플레이어가 등을 보이는 쪽 팔의 파워드 공격을 1.5배로 받게 만든다.
두 몬스터 모두 ShouldDisappearFromDoom=false — Doom으로 즉사하지 않는다.
"""
from __future__ import annotations
from typing import List

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    MonsterModel, MonsterMoveStateMachine, MoveState,
    Intent, IntentType, MONSTER_REGISTRY,
)


class Crusher(MonsterModel):
    """크러셔 (왼팔) — HP 209. 개전 BackAttackLeft(1) + CrabRage(1).

    원본(Crusher.cs) 그래프 (고정 순환):
      THRASH_MOVE(12) → ENLARGING_STRIKE_MOVE(4) → BUG_STING_MOVE(6×2, 약화2+허약2)
        → ADAPT_MOVE(힘+2) → GUARDED_STRIKE_MOVE(12 + 블록18) → THRASH_MOVE."""
    monster_id = "crusher"
    title = "Crusher"

    @property
    def min_initial_hp(self) -> int:
        return 209

    @property
    def max_initial_hp(self) -> int:
        return 209

    @property
    def should_disappear_from_doom(self) -> bool:
        return False

    @property
    def thrash_damage(self) -> int:
        return 12

    @property
    def enlarging_strike_damage(self) -> int:
        return 4

    @property
    def bug_sting_damage(self) -> int:
        return 6

    @property
    def bug_sting_times(self) -> int:
        return 2

    @property
    def adapt_strength(self) -> int:
        return 2

    @property
    def guarded_strike_damage(self) -> int:
        return 12

    @property
    def guarded_strike_block(self) -> int:
        return 18

    @property
    def weak_amount(self) -> int:
        return 2

    @property
    def frail_amount(self) -> int:
        return 2

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import BackAttackLeftPower, CrabRagePower
        self.apply_power(BackAttackLeftPower(1))
        self.apply_power(CrabRagePower(1))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        thrash = MoveState("THRASH_MOVE", self._thrash_move,
                           Intent(IntentType.ATTACK, damage=self.thrash_damage))
        enlarging = MoveState("ENLARGING_STRIKE_MOVE", self._enlarging_move,
                              Intent(IntentType.ATTACK,
                                     damage=self.enlarging_strike_damage))
        bug_sting = MoveState("BUG_STING_MOVE", self._bug_sting_move,
                              Intent(IntentType.ATTACK_DEBUFF,
                                     damage=self.bug_sting_damage,
                                     times=self.bug_sting_times))
        adapt = MoveState("ADAPT_MOVE", self._adapt_move, Intent(IntentType.BUFF))
        guarded = MoveState("GUARDED_STRIKE_MOVE", self._guarded_move,
                            Intent(IntentType.ATTACK_DEFEND,
                                   damage=self.guarded_strike_damage))

        thrash.follow_up_state = enlarging
        enlarging.follow_up_state = bug_sting
        bug_sting.follow_up_state = adapt
        adapt.follow_up_state = guarded
        guarded.follow_up_state = thrash

        return MonsterMoveStateMachine(
            [thrash, enlarging, bug_sting, adapt, guarded], thrash)

    def _thrash_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.thrash_damage)

    def _enlarging_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.enlarging_strike_damage)

    def _bug_sting_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Weak, Frail
        for _ in range(self.bug_sting_times):
            for target in targets:
                self.attack(target, self.bug_sting_damage)
        for target in targets:
            target.apply_power(Weak(self.weak_amount), applier=self)
            target.apply_power(Frail(self.frail_amount), applier=self)

    def _adapt_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(self.adapt_strength))

    def _guarded_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.guarded_strike_damage)
        self.gain_block(self.guarded_strike_block)


class Rocket(MonsterModel):
    """로켓 (오른팔) — HP 199. 개전 플레이어에게 Surrounded(1),
    자신에게 BackAttackRight(1) + CrabRage(1).

    원본(Rocket.cs) 그래프 (고정 순환):
      TARGETING_RETICLE_MOVE(3) → PRECISION_BEAM_MOVE(18) → CHARGE_UP_MOVE(힘+2)
        → LASER_MOVE(31) → RECHARGE_MOVE(SleepIntent, 무행동) → TARGETING_RETICLE_MOVE."""
    monster_id = "rocket"
    title = "Rocket"

    @property
    def min_initial_hp(self) -> int:
        return 199

    @property
    def max_initial_hp(self) -> int:
        return 199

    @property
    def should_disappear_from_doom(self) -> bool:
        return False

    @property
    def reticle_damage(self) -> int:
        return 3

    @property
    def precision_beam_damage(self) -> int:
        return 18

    @property
    def charge_up_strength(self) -> int:
        return 2

    @property
    def laser_damage(self) -> int:
        return 31

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import (
            SurroundedPower, BackAttackRightPower, CrabRagePower,
        )
        # 원본 GetOpponentsOf(self) → 플레이어에게 Surrounded 적용
        if self.combat_state is not None and self.combat_state.player is not None:
            self.combat_state.player.apply_power(SurroundedPower(1), applier=self)
        self.apply_power(BackAttackRightPower(1))
        self.apply_power(CrabRagePower(1))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        reticle = MoveState("TARGETING_RETICLE_MOVE", self._reticle_move,
                            Intent(IntentType.ATTACK, damage=self.reticle_damage))
        beam = MoveState("PRECISION_BEAM_MOVE", self._beam_move,
                         Intent(IntentType.ATTACK,
                                damage=self.precision_beam_damage))
        charge = MoveState("CHARGE_UP_MOVE", self._charge_move,
                           Intent(IntentType.BUFF))
        laser = MoveState("LASER_MOVE", self._laser_move,
                          Intent(IntentType.ATTACK, damage=self.laser_damage))
        recharge = MoveState("RECHARGE_MOVE", self._recharge_move,
                             Intent(IntentType.SLEEP))

        reticle.follow_up_state = beam
        beam.follow_up_state = charge
        charge.follow_up_state = laser
        laser.follow_up_state = recharge
        recharge.follow_up_state = reticle

        return MonsterMoveStateMachine(
            [reticle, beam, charge, laser, recharge], reticle)

    def _reticle_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.reticle_damage)

    def _beam_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.precision_beam_damage)

    def _charge_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(self.charge_up_strength))

    def _laser_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.laser_damage)

    def _recharge_move(self, targets: List[Creature]) -> None:
        pass  # 원본 RechargeMove — 재충전(SleepIntent), 무행동


BATCH19_MONSTERS = {
    "crusher": Crusher,
    "rocket": Rocket,
}

MONSTER_REGISTRY.update(BATCH19_MONSTERS)
