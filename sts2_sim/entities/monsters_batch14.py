"""
STS2 몬스터 배치 14 (Phase 6s) — 환영(Illusion) 소환 계열.
모든 수치는 Ascension 미적용 기본값.

Fogmog는 EyeWithTeeth를, TheObscura는 Parafright를 "illusion" 슬롯에 소환한다.
두 소환체 모두 개전 IllusionPower(사망 후 다음 턴 최대 HP로 부활)를 받으므로,
이 배치는 소환체 쪽 정식 이식(sts2_monster.py의 기존 스텁 교체)이 선행됐다.
"""
from __future__ import annotations
from typing import List

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    MonsterModel, MonsterMoveStateMachine, MoveState, RandomBranchState,
    Intent, IntentType, MONSTER_REGISTRY,
)


class Fogmog(MonsterModel):
    """포그모그 — HP 74, 개전 파워 없음.

    원본(Fogmog.cs) 그래프: ILLUSION_MOVE(EyeWithTeeth 1마리 소환) →
    SWIPE_MOVE(8딜 + 자신 힘 +1) → BRANCH →
      { SWIPE_RANDOM_MOVE(SWIPE와 동일 동작, 가중치 0.4) → HEADBUTT_MOVE,
        HEADBUTT_MOVE(14딜, 가중치 0.6) → SWIPE_MOVE }
    두 분기 모두 CannotRepeat. 가중치가 람다(`() => 0.4f` / `() => 0.6f`)지만
    상태에 따라 변하지 않는 상수라 그대로 상수로 이식한다."""
    monster_id = "fogmog"
    title = "Fogmog"

    @property
    def min_initial_hp(self) -> int:
        return 74

    @property
    def max_initial_hp(self) -> int:
        return 74

    @property
    def swipe_damage(self) -> int:
        return 8

    @property
    def swipe_strength_gain(self) -> int:
        return 1

    @property
    def headbutt_damage(self) -> int:
        return 14

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        illusion = MoveState("ILLUSION_MOVE", self._illusion_move, Intent(IntentType.BUFF))
        swipe = MoveState("SWIPE_MOVE", self._swipe_move,
                          Intent(IntentType.ATTACK_BUFF, damage=self.swipe_damage))
        swipe_random = MoveState("SWIPE_RANDOM_MOVE", self._swipe_move,
                                 Intent(IntentType.ATTACK_BUFF, damage=self.swipe_damage))
        headbutt = MoveState("HEADBUTT_MOVE", self._headbutt_move,
                             Intent(IntentType.ATTACK, damage=self.headbutt_damage))
        branch = RandomBranchState("BRANCH")
        branch.add_branch(swipe_random, weight=0.4, cannot_repeat=True)
        branch.add_branch(headbutt, weight=0.6, cannot_repeat=True)
        illusion.follow_up_state = swipe
        swipe.follow_up_state = branch
        swipe_random.follow_up_state = headbutt
        headbutt.follow_up_state = swipe
        return MonsterMoveStateMachine(
            [illusion, swipe, swipe_random, branch, headbutt], illusion)

    def _illusion_move(self, targets: List[Creature]) -> None:
        from sts2_sim.entities.sts2_monster import EyeWithTeeth
        combat = self.combat_state
        if combat is not None:
            combat.add_monster(EyeWithTeeth(), slot_name="illusion")

    def _swipe_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        for target in targets:
            self.attack(target, self.swipe_damage)
        self.apply_power(Strength(self.swipe_strength_gain))

    def _headbutt_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.headbutt_damage)


class TheObscura(MonsterModel):
    """디 옵스큐라 — HP 123, 개전 파워 없음.

    원본(TheObscura.cs) 그래프: ILLUSION_MOVE(Parafright 1마리 소환) → RAND,
    RAND = { PIERCING_GAZE(10딜), SAIL_MOVE(같은 편 전체 힘 +3),
    HARDENING_STRIKE(6딜 + 블록 6) } 각 CannotRepeat + 가중치 1.
    모든 무브가 RAND로 복귀한다.
    (원본 상태 ID "SAIL_MOVE"의 콜백 이름은 WailMove — ID를 그대로 따른다.
    SAIL_MOVE는 자신이 아니라 GetTeammatesOf 전체가 대상이라 소환한
    Parafright도 함께 강화된다.)"""
    monster_id = "the_obscura"
    title = "The Obscura"

    @property
    def min_initial_hp(self) -> int:
        return 123

    @property
    def max_initial_hp(self) -> int:
        return 123

    @property
    def piercing_gaze_damage(self) -> int:
        return 10

    @property
    def hardening_strike_damage(self) -> int:
        return 6

    @property
    def hardening_strike_block(self) -> int:
        return 6

    @property
    def wail_strength_gain(self) -> int:
        return 3

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        illusion = MoveState("ILLUSION_MOVE", self._illusion_move, Intent(IntentType.BUFF))
        gaze = MoveState("PIERCING_GAZE_MOVE", self._piercing_gaze_move,
                         Intent(IntentType.ATTACK, damage=self.piercing_gaze_damage))
        wail = MoveState("SAIL_MOVE", self._wail_move, Intent(IntentType.BUFF))
        strike = MoveState("HARDENING_STRIKE_MOVE", self._hardening_strike_move,
                           Intent(IntentType.ATTACK_DEFEND,
                                  damage=self.hardening_strike_damage))
        rand = RandomBranchState("RAND")
        rand.add_branch(gaze, cannot_repeat=True)
        rand.add_branch(wail, cannot_repeat=True)
        rand.add_branch(strike, cannot_repeat=True)
        illusion.follow_up_state = rand
        gaze.follow_up_state = rand
        wail.follow_up_state = rand
        strike.follow_up_state = rand
        return MonsterMoveStateMachine([illusion, gaze, wail, strike, rand], illusion)

    def _illusion_move(self, targets: List[Creature]) -> None:
        from sts2_sim.entities.sts2_monster import Parafright
        combat = self.combat_state
        if combat is not None:
            combat.add_monster(Parafright(), slot_name="illusion")

    def _piercing_gaze_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.piercing_gaze_damage)

    def _wail_move(self, targets: List[Creature]) -> None:
        """원본 GetTeammatesOf(self) — 자신을 포함한 같은 편 전체에 힘 +3."""
        from sts2_sim.models.sts2_power import Strength
        combat = self.combat_state
        allies = list(combat.alive_enemies) if combat is not None else [self]
        for ally in allies:
            ally.apply_power(Strength(self.wail_strength_gain))

    def _hardening_strike_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.hardening_strike_damage)
        self.gain_block(self.hardening_strike_block)  # 원본 ValueProp.Move


BATCH14_MONSTERS = {
    "fogmog": Fogmog,
    "the_obscura": TheObscura,
}

MONSTER_REGISTRY.update(BATCH14_MONSTERS)
