"""
STS2 몬스터 배치 21 (S1.M3.B21) — KnowledgeDemon.
모든 수치는 Ascension 미적용 기본값.

Knowledge Demon은 처음 세 순환에서 회차별 두 Status 중 하나를 선택해 즉시
디버프를 부여한다. 선택 UI가 없는 헤드리스 경로에서는 전투 RNG로 두 후보 중
하나를 고른다. 세 번째 선택 뒤에는 Curse 무브를 건너뛴다.
"""
from __future__ import annotations
from typing import List

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    ConditionalBranchState, Intent, IntentType, MONSTER_REGISTRY,
    MonsterModel, MonsterMoveStateMachine, MoveState,
)
from sts2_sim.models.sts2_card import create_card


class KnowledgeDemon(MonsterModel):
    """지식의 악마 — HP 379, 세 차례 선택형 영구 디버프를 사용하는 보스."""
    monster_id = "knowledge_demon"
    title = "Knowledge Demon"

    _CURSE_SETS = (
        ("disintegration", "mind_rot"),
        ("disintegration", "sloth"),
        ("disintegration", "waste_away"),
    )
    _DISINTEGRATION_DAMAGE = (6, 7, 8)

    def __init__(self):
        super().__init__()
        self._curse_of_knowledge_counter = 0
        self._is_burnt = False

    @property
    def min_initial_hp(self) -> int:
        return 379

    @property
    def max_initial_hp(self) -> int:
        return 379

    @property
    def should_disappear_from_doom(self) -> bool:
        return False

    @property
    def slap_damage(self) -> int:
        return 17

    @property
    def knowledge_overwhelming_damage(self) -> int:
        return 8

    @property
    def ponder_damage(self) -> int:
        return 11

    @property
    def ponder_strength(self) -> int:
        return 2

    @property
    def is_burnt(self) -> bool:
        return self._is_burnt

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        curse = MoveState(
            "CURSE_OF_KNOWLEDGE_MOVE", self._curse_of_knowledge_move,
            Intent(IntentType.DEBUFF))
        slap = MoveState(
            "SLAP_MOVE", self._slap_move,
            Intent(IntentType.ATTACK, damage=self.slap_damage))
        overwhelming = MoveState(
            "KNOWLEDGE_OVERWHELMING_MOVE", self._knowledge_overwhelming_move,
            Intent(IntentType.ATTACK, damage=self.knowledge_overwhelming_damage, times=3))
        ponder = MoveState(
            "PONDER_MOVE", self._ponder_move,
            Intent(IntentType.ATTACK_BUFF, damage=self.ponder_damage))
        branch = ConditionalBranchState("CurseOfKnowledgeBranch")

        curse.follow_up_state = slap
        slap.follow_up_state = overwhelming
        overwhelming.follow_up_state = ponder
        ponder.follow_up_state = branch
        branch.add_state(curse, lambda: self._curse_of_knowledge_counter < 3)
        branch.add_state(slap, lambda: self._curse_of_knowledge_counter >= 3)

        return MonsterMoveStateMachine(
            [branch, curse, slap, ponder, overwhelming], curse)

    def _curse_of_knowledge_move(self, targets: List[Creature]) -> None:
        index = self._curse_of_knowledge_counter
        if index >= len(self._CURSE_SETS):
            raise ValueError(f"No valid curse set at index {index}")
        if self.combat_state is None:
            return
        for target in targets:
            if target.is_dead:
                continue
            card = create_card(self.combat_state.rng.choice(self._CURSE_SETS[index]))
            if card is None:
                continue
            if card.card_id == "disintegration":
                card.on_chosen(target, self._DISINTEGRATION_DAMAGE[index])
            else:
                card.on_chosen(target)
        if not getattr(self.combat_state, "_combat_over", False):
            self._curse_of_knowledge_counter += 1

    def _slap_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.slap_damage)

    def _knowledge_overwhelming_move(self, targets: List[Creature]) -> None:
        self._is_burnt = True
        for _ in range(3):
            for target in targets:
                self.attack(target, self.knowledge_overwhelming_damage)

    def _ponder_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self._is_burnt = False
        for target in targets:
            self.attack(target, self.ponder_damage)
        self.heal(30 * len(targets))
        self.apply_power(Strength(self.ponder_strength), applier=self)


BATCH21_MONSTERS = {
    "knowledge_demon": KnowledgeDemon,
}

MONSTER_REGISTRY.update(BATCH21_MONSTERS)
