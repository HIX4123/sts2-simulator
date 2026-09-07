"""
STS2 몬스터 배치 20 (S1.M3.B20) — CeremonialBeast.
모든 수치는 Ascension 미적용 기본값.

CeremonialBeast는 STAMP로 PlowPower를 준비한 뒤 PLOW를 반복한다. 실제 피해로
HP가 150 이하가 되면 힘을 모두 잃고 한 턴 기절하며, 이후 BEAST_CRY → STOMP
→ CRUSH 순환으로 전환한다. BEAST_CRY는 플레이어 카드에 Ringing을 부여한다.
"""
from __future__ import annotations
from typing import List

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    MonsterModel, MonsterMoveStateMachine, MoveState,
    Intent, IntentType, MONSTER_REGISTRY,
)


class CeremonialBeast(MonsterModel):
    """의식의 야수 — HP 252, Plow 임계 전이와 Ringing을 사용하는 보스."""
    monster_id = "ceremonial_beast"
    title = "Ceremonial Beast"

    def __init__(self):
        super().__init__()
        self._is_in_second_phase = False
        self._is_stunned_by_plow = False

    @property
    def min_initial_hp(self) -> int:
        return 252

    @property
    def max_initial_hp(self) -> int:
        return 252

    @property
    def should_disappear_from_doom(self) -> bool:
        return False

    @property
    def plow_amount(self) -> int:
        return 150

    @property
    def plow_damage(self) -> int:
        return 18

    @property
    def plow_strength(self) -> int:
        return 2

    @property
    def stomp_damage(self) -> int:
        return 15

    @property
    def crush_damage(self) -> int:
        return 17

    @property
    def crush_strength(self) -> int:
        return 3

    @property
    def is_in_second_phase(self) -> bool:
        return self._is_in_second_phase

    @property
    def is_stunned_by_plow(self) -> bool:
        return self._is_stunned_by_plow

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        stamp = MoveState("STAMP_MOVE", self._stamp_move, Intent(IntentType.BUFF))
        plow = MoveState("PLOW_MOVE", self._plow_move,
                         Intent(IntentType.ATTACK_BUFF, damage=self.plow_damage))
        stun = MoveState("STUN_MOVE", self._stunned_move, Intent(IntentType.STUN))
        beast_cry = MoveState("BEAST_CRY_MOVE", self._beast_cry_move,
                              Intent(IntentType.DEBUFF))
        stomp = MoveState("STOMP_MOVE", self._stomp_move,
                          Intent(IntentType.ATTACK, damage=self.stomp_damage))
        crush = MoveState("CRUSH_MOVE", self._crush_move,
                          Intent(IntentType.ATTACK_BUFF, damage=self.crush_damage))

        stamp.follow_up_state = plow
        plow.follow_up_state = plow
        stun.follow_up_state = beast_cry
        beast_cry.follow_up_state = stomp
        stomp.follow_up_state = crush
        crush.follow_up_state = beast_cry

        # 원본 상태 목록 순서: PLOW, STAMP, STUN, BEAST_CRY, STOMP, CRUSH.
        return MonsterMoveStateMachine(
            [plow, stamp, stun, beast_cry, stomp, crush], stamp)

    def _stamp_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import PlowPower
        self.apply_power(PlowPower(self.plow_amount))

    def _plow_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        for target in targets:
            self.attack(target, self.plow_damage)
        self.apply_power(Strength(self.plow_strength))

    def set_stunned_by_plow(self) -> None:
        self._is_stunned_by_plow = True
        self._is_in_second_phase = True

    def _stunned_move(self, targets: List[Creature]) -> None:
        self._is_stunned_by_plow = False

    def _beast_cry_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import RingingPower
        for target in targets:
            target.apply_power(RingingPower(1), applier=self)

    def _stomp_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.stomp_damage)

    def _crush_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        for target in targets:
            self.attack(target, self.crush_damage)
        self.apply_power(Strength(self.crush_strength))


BATCH20_MONSTERS = {
    "ceremonial_beast": CeremonialBeast,
}

MONSTER_REGISTRY.update(BATCH20_MONSTERS)
