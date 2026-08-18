"""
STS2 몬스터 배치 12 (Phase 6o) — 전투 중 소환 계열.
모든 수치는 Ascension 미적용 기본값.

이 배치는 `CombatState.add_monster`(원본 `CreatureCmd.Add`) 위에 선다 —
전투 도중 새 몬스터를 전투에 투입하는 구조가 없어 Phase 6l부터 세 번
미뤄왔던 계열이다.
"""
from __future__ import annotations
from typing import List

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    MonsterModel, MonsterMoveStateMachine, MoveState, RandomBranchState,
    Intent, IntentType, MONSTER_REGISTRY,
)


class PhrogParasite(MonsterModel):
    """프로그 패러사이트 (엘리트) — HP 61~64, 개전 시 스스로에게 InfestedPower(4)
    (죽으면 Wriggler 4마리가 스턴 상태로 소환된다).

    원본(PhrogParasite.cs) 그래프: INFECT_MOVE(감염 3장을 버림 더미로) ↔
    LASH_MOVE(4딜×4) 고정 교대. RAND 노드가 생성되어 상태 목록에는 들어가지만
    두 무브의 FollowUpState가 서로를 직접 가리켜 실제로는 진입하지 않는다 —
    원본 구성을 그대로 보존한다."""
    monster_id = "phrog_parasite"
    title = "Phrog Parasite"

    @property
    def min_initial_hp(self) -> int:
        return 61

    @property
    def max_initial_hp(self) -> int:
        return 64

    @property
    def lash_damage(self) -> int:
        return 4

    @property
    def lash_repeat(self) -> int:
        return 4

    @property
    def infest_amount(self) -> int:
        return 3

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import InfestedPower
        self.apply_power(InfestedPower(4))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        infect = MoveState("INFECT_MOVE", self._infect_move, Intent(IntentType.STATUS))
        lash = MoveState("LASH_MOVE", self._lash_move,
                         Intent(IntentType.ATTACK, damage=self.lash_damage,
                                times=self.lash_repeat))
        rand = RandomBranchState("RAND")  # 원본 구성 보존 — 실제로는 진입하지 않음
        rand.add_branch(infect, cannot_repeat=True)
        rand.add_branch(lash, cannot_repeat=True)
        infect.follow_up_state = lash
        lash.follow_up_state = infect
        return MonsterMoveStateMachine([infect, lash, rand], infect)

    def _infect_move(self, targets: List[Creature]) -> None:
        self.add_status_to_player_discard("infection", self.infest_amount)

    def _lash_move(self, targets: List[Creature]) -> None:
        for _ in range(self.lash_repeat):
            for target in targets:
                self.attack(target, self.lash_damage)


BATCH12_MONSTERS = {
    "phrog_parasite": PhrogParasite,
}

MONSTER_REGISTRY.update(BATCH12_MONSTERS)
