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


class TwoTailedRat(MonsterModel):
    """투테일드 랫 — HP 17~21. 전투 중 동족을 불러들인다.

    원본(TwoTailedRat.cs) 그래프: SCRATCH(8딜) / DISEASE_BITE(6딜) /
    SCREECH(허약 1) / CALL_FOR_BACKUP(동족 1마리 소환) 4분기 RAND.
    모든 무브가 RAND로 복귀한다.

    분기 가중치가 상수가 아니라 CanSummon() 상태에 따라 갈리는 람다다
    (원본 `Func<float>` 오버로드):
      - 소환 불가: 공격 3종 각 1.0, CALL_FOR_BACKUP 0.0(제외)
      - 소환 가능: 공격 3종 각 1/12, CALL_FOR_BACKUP 0.75 → 소환이 75% 확률
    SCREECH는 3-인자 AddBranch(state, 3, MoveRepeatType, ...)라 "3"이 weight가
    아니라 **cooldown**이다 (최근 3무브 안에 있으면 제외).
    CALL_FOR_BACKUP은 MoveRepeatType.UseOnlyOnce — 한 마리당 한 번만.

    CanSummon 조건 (원본):
      1. TurnsUntilSummonable > 0이면 불가 — 공격/비명 무브를 수행할 때마다
         1씩 줄어 개전 후 2턴은 소환할 수 없다
      2. CallForBackupCount >= 3이면 불가 (전투 전체 소환 3회 상한, 같은 편
         쥐들이 카운터를 공유한다)
      3. 빈 슬롯이 없으면 불가
      4. 같은 편에 이미 CALL_FOR_BACKUP을 예약한 쥐가 있으면 불가 (중복 소환 방지)
    """
    monster_id = "two_tailed_rat"
    title = "Two-Tailed Rat"

    CALL_FOR_BACKUP_LIMIT = 3
    SUMMON_DELAY_TURNS = 2

    def __init__(self, starter_move_index: int = -1):
        super().__init__()
        self.starter_move_index = starter_move_index
        self.turns_until_summonable = self.SUMMON_DELAY_TURNS
        self.call_for_backup_count = 0

    @property
    def min_initial_hp(self) -> int:
        return 17

    @property
    def max_initial_hp(self) -> int:
        return 21

    @property
    def scratch_damage(self) -> int:
        return 8

    @property
    def disease_bite_damage(self) -> int:
        return 6

    @property
    def screech_frail(self) -> int:
        return 1

    def _allies(self) -> List["TwoTailedRat"]:
        combat = self.combat_state
        if combat is None:
            return [self]
        return [m for m in combat.alive_enemies if isinstance(m, TwoTailedRat)]

    def can_summon(self) -> bool:
        if self.turns_until_summonable > 0:
            return False
        if self.call_for_backup_count >= self.CALL_FOR_BACKUP_LIMIT:
            return False
        combat = self.combat_state
        if combat is None or combat.next_free_slot() is None:
            return False
        for ally in self._allies():
            if ally is self:
                continue
            sm = ally._move_state_machine
            if sm is not None and sm.get_current_move_name() == "CALL_FOR_BACKUP_MOVE":
                return False
        return True

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        self.turns_until_summonable = self.SUMMON_DELAY_TURNS
        scratch = MoveState("SCRATCH_MOVE", self._scratch_move,
                            Intent(IntentType.ATTACK, damage=self.scratch_damage))
        bite = MoveState("DISEASE_BITE_MOVE", self._disease_bite_move,
                         Intent(IntentType.ATTACK, damage=self.disease_bite_damage))
        screech = MoveState("SCREECH_MOVE", self._screech_move, Intent(IntentType.DEBUFF))
        backup = MoveState("CALL_FOR_BACKUP_MOVE", self._call_for_backup_move,
                           Intent(IntentType.BUFF))  # 원본 SummonIntent
        rand = RandomBranchState("RAND")
        # 원본 람다 가중치를 그대로: 소환 가능하면 공격 3종이 1/12로 눌리고
        # 소환이 0.75를 가져간다 (rng.choices는 가중치 합을 정규화하므로 비율만 맞으면 됨)
        attack_weight = lambda: 1.0 if not self.can_summon() else 1.0 / 12.0
        rand.add_branch(scratch, weight=attack_weight, cannot_repeat=True)
        rand.add_branch(bite, weight=attack_weight, cannot_repeat=True)
        rand.add_branch(screech, weight=attack_weight, cannot_repeat=True, cooldown=3)
        rand.add_branch(backup, weight=lambda: 0.0 if not self.can_summon() else 0.75,
                        use_only_once=True)
        scratch.follow_up_state = rand
        bite.follow_up_state = rand
        screech.follow_up_state = rand
        backup.follow_up_state = rand
        states = [rand, scratch, bite, screech, backup]
        if self.starter_move_index == -1:
            return MonsterMoveStateMachine(states, rand)
        initial = {0: scratch, 1: bite}.get(self.starter_move_index % 3, screech)
        return MonsterMoveStateMachine(states, initial)

    def _scratch_move(self, targets: List[Creature]) -> None:
        self.turns_until_summonable -= 1
        for target in targets:
            self.attack(target, self.scratch_damage)

    def _disease_bite_move(self, targets: List[Creature]) -> None:
        self.turns_until_summonable -= 1
        for target in targets:
            self.attack(target, self.disease_bite_damage)

    def _screech_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Frail
        self.turns_until_summonable -= 1
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Frail(self.screech_frail), applier=self)

    def _call_for_backup_move(self, targets: List[Creature]) -> None:
        combat = self.combat_state
        if combat is None:
            return
        slot = combat.next_free_slot()
        if slot:
            combat.add_monster(TwoTailedRat(), slot_name=slot)
        # 원본: 살아있는 모든 쥐의 카운터를 (최대값 + 1)로 동기화
        allies = self._allies()
        shared = max(r.call_for_backup_count for r in allies) + 1 if allies else 1
        for rat in allies:
            rat.call_for_backup_count = shared


BATCH12_MONSTERS = {
    "phrog_parasite": PhrogParasite,
    "two_tailed_rat": TwoTailedRat,
}

MONSTER_REGISTRY.update(BATCH12_MONSTERS)
