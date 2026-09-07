"""
STS2 몬스터 배치 22 (S1.M3.B22) — TheAdversary Mk1~Mk3.
모든 수치는 Ascension 미적용 기본값.

세 시험용 적은 별도 인카운터 없이 registry에 등록한다. decompiled 데이터에도
EncounterModel 참조가 없고, TestSubjectBoss는 이름과 달리 TestSubject 단독이다.
"""
from __future__ import annotations
from typing import List

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    Intent, IntentType, MONSTER_REGISTRY, MonsterModel,
    MonsterMoveStateMachine, MoveState,
)


class TheAdversaryMkOne(MonsterModel):
    """The Adversary Mk1 — HP 100, 12 → 15 → 8×2+힘2 순환."""
    monster_id = "the_adversary_mk_one"
    title = "The Adversary Mk1"

    @property
    def min_initial_hp(self) -> int:
        return 100

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        smash = MoveState("SMASH_MOVE", self._smash_move,
                          Intent(IntentType.ATTACK, damage=12))
        beam = MoveState("BEAM_MOVE", self._beam_move,
                         Intent(IntentType.ATTACK, damage=15))
        barrage = MoveState("BARRAGE_MOVE", self._barrage_move,
                            Intent(IntentType.ATTACK_BUFF, damage=8, times=2))
        smash.follow_up_state = beam
        beam.follow_up_state = barrage
        barrage.follow_up_state = smash
        return MonsterMoveStateMachine([smash, beam, barrage], smash)

    def _smash_move(self, targets: List[Creature]) -> None:
        self._attack_all(targets, 12)

    def _beam_move(self, targets: List[Creature]) -> None:
        self._attack_all(targets, 15)

    def _barrage_move(self, targets: List[Creature]) -> None:
        self._multi_attack_all(targets, 8, 2)
        self._gain_strength(2)

    def _attack_all(self, targets: List[Creature], damage: int) -> None:
        for target in targets:
            self.attack(target, damage)

    def _multi_attack_all(self, targets: List[Creature], damage: int, times: int) -> None:
        for _ in range(times):
            self._attack_all(targets, damage)

    def _gain_strength(self, amount: int) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(amount), applier=self)


class TheAdversaryMkTwo(TheAdversaryMkOne):
    """The Adversary Mk2 — HP 200, Artifact 1, 13 → 16 → 9×3+힘3 순환."""
    monster_id = "the_adversary_mk_two"
    title = "The Adversary Mk2"

    @property
    def min_initial_hp(self) -> int:
        return 200

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import Artifact
        self.apply_power(Artifact(1), applier=self)

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        bash = MoveState("BASH_MOVE", self._bash_move,
                         Intent(IntentType.ATTACK, damage=13))
        flame = MoveState("FLAME_BEAM_MOVE", self._flame_beam_move,
                          Intent(IntentType.ATTACK, damage=16))
        barrage = MoveState("BARRAGE_MOVE", self._barrage_move,
                            Intent(IntentType.ATTACK_BUFF, damage=9, times=3))
        bash.follow_up_state = flame
        flame.follow_up_state = barrage
        barrage.follow_up_state = bash
        return MonsterMoveStateMachine([bash, flame, barrage], bash)

    def _bash_move(self, targets: List[Creature]) -> None:
        self._attack_all(targets, 13)

    def _flame_beam_move(self, targets: List[Creature]) -> None:
        self._attack_all(targets, 16)

    def _barrage_move(self, targets: List[Creature]) -> None:
        self._multi_attack_all(targets, 9, 3)
        self._gain_strength(3)


class TheAdversaryMkThree(TheAdversaryMkOne):
    """The Adversary Mk3 — HP 300, Artifact 2, 15 → 18 → 10×4+힘4 순환."""
    monster_id = "the_adversary_mk_three"
    title = "The Adversary Mk3"

    @property
    def min_initial_hp(self) -> int:
        return 300

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import Artifact
        self.apply_power(Artifact(2), applier=self)

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        crash = MoveState("CRASH_MOVE", self._crash_move,
                          Intent(IntentType.ATTACK, damage=15))
        flame = MoveState("FLAME_BEAM_MOVE", self._flame_beam_move,
                          Intent(IntentType.ATTACK, damage=18))
        barrage = MoveState("BARRAGE_MOVE", self._barrage_move,
                            Intent(IntentType.ATTACK_BUFF, damage=10, times=4))
        crash.follow_up_state = flame
        flame.follow_up_state = barrage
        barrage.follow_up_state = crash
        return MonsterMoveStateMachine([crash, flame, barrage], crash)

    def _crash_move(self, targets: List[Creature]) -> None:
        self._attack_all(targets, 15)

    def _flame_beam_move(self, targets: List[Creature]) -> None:
        self._attack_all(targets, 18)

    def _barrage_move(self, targets: List[Creature]) -> None:
        self._multi_attack_all(targets, 10, 4)
        self._gain_strength(4)


BATCH22_MONSTERS = {
    cls.monster_id: cls for cls in (
        TheAdversaryMkOne, TheAdversaryMkTwo, TheAdversaryMkThree)
}

MONSTER_REGISTRY.update(BATCH22_MONSTERS)
