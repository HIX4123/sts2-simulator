"""
STS2 몬스터 배치 15 (Phase 6t) — Ovicopter + ToughEgg (알 낳기/부화 계열).
모든 수치는 Ascension 미적용 기본값.

Ovicopter가 빈 알 슬롯에 ToughEgg를 낳고(뒤에서부터 채움), ToughEgg는 첫 턴에
부화(HP 재설정)한 뒤 매 턴 갉아먹는다. 소환 엔진(add_monster)과 MinionPower는
이미 이식돼 있어 신규 인프라는 HatchPower(표시용 카운터)와 last-free-slot 헬퍼뿐.
"""
from __future__ import annotations
from typing import List

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    MonsterModel, MonsterMoveStateMachine, MoveState, ConditionalBranchState,
    Intent, IntentType, MONSTER_REGISTRY,
)


class ToughEgg(MonsterModel):
    """터프 에그 — 알 HP 14~18. 개전 HatchPower(2).

    원본(ToughEgg.cs) 그래프: HATCH_MOVE(부화 — HatchPower 및 MinionPower를
    제외한 모든 파워 제거 + HP를 19~22로 재설정) → NIBBLE_MOVE(4딜, 무한 반복).
    첫 턴에 반드시 부화하고 이후 계속 갉아먹는다. Ovicopter가 소환하는 대상이며
    개전 시 MinionPower(1)를 함께 받는다(소환 측에서 적용)."""
    monster_id = "tough_egg"
    title = "Tough Egg"

    def __init__(self):
        super().__init__()
        self._hatch_hp = 19  # 부화 후 HP (setup 시 시드 rng로 19~22 재추첨)

    @property
    def min_initial_hp(self) -> int:
        return 14

    @property
    def max_initial_hp(self) -> int:
        return 18

    @property
    def nibble_damage(self) -> int:
        return 4

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import HatchPower
        # 원본: 플레이어 편이 아니면(=적 편) HatchPower 2, 아니면 1. 이 시뮬레이터는
        # 소환체가 항상 적 편이므로 2.
        self.apply_power(HatchPower(2))
        # 부화 후 HP를 시드 rng로 확정해 재현성을 유지 (원본 RunRng.Niche.NextInt).
        sm = self._move_state_machine
        if sm is not None:
            self._hatch_hp = sm.rng.randint(19, 22)

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        hatch = MoveState("HATCH_MOVE", self._hatch_move, Intent(IntentType.BUFF))
        nibble = MoveState("NIBBLE_MOVE", self._nibble_move,
                           Intent(IntentType.ATTACK, damage=self.nibble_damage))
        hatch.follow_up_state = nibble
        nibble.follow_up_state = nibble
        return MonsterMoveStateMachine([hatch, nibble], hatch)

    def _hatch_move(self, targets: List[Creature]) -> None:
        # 원본 HatchMove: HatchPower 제거 → MinionPower를 제외한 모든 파워 제거 →
        # 최대/현재 HP를 부화 HP로 재설정.
        for pid in list(self._powers.keys()):
            if pid != "minion":
                self._powers[pid].remove()
        self._max_hp = self._hatch_hp
        self._current_hp = self._hatch_hp

    def _nibble_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.nibble_damage)


class Ovicopter(MonsterModel):
    """오비콥터 — HP 124~130. 개전 파워 없음.

    원본(Ovicopter.cs) 그래프:
      LAY_EGGS(빈 알 슬롯 3칸까지 ToughEgg 소환+MinionPower) → SMASH
      SMASH(16딜) → TENDERIZER
      TENDERIZER(7딜 + 취약 2) → SUMMON_BRANCH
      SUMMON_BRANCH = { CanLay ? LAY_EGGS : NUTRITIONAL_PASTE }
      NUTRITIONAL_PASTE(자기 힘 +3) → SMASH
    시작 무브는 LAY_EGGS. CanLay = GetTeammatesOf(자신 포함) 살아있는 수 ≤ 3."""
    monster_id = "ovicopter"
    title = "Ovicopter"

    @property
    def min_initial_hp(self) -> int:
        return 124

    @property
    def max_initial_hp(self) -> int:
        return 130

    @property
    def smash_damage(self) -> int:
        return 16

    @property
    def tenderizer_damage(self) -> int:
        return 7

    @property
    def tenderizer_vulnerable(self) -> int:
        return 2

    @property
    def paste_strength(self) -> int:
        return 3

    def _can_lay(self) -> bool:
        """원본 CanLay: GetTeammatesOf(self)(자신 포함) 중 살아있는 수 ≤ 3.
        alive_enemies는 몬스터 편(=Ovicopter 자신 + 살아있는 알)이므로 그대로
        ≤ 3을 검사한다. 즉 자신 외 살아있는 알이 2마리 이하일 때만 새로 낳는다."""
        combat = self.combat_state
        if combat is None:
            return True
        return len(combat.alive_enemies) <= 3

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        lay = MoveState("LAY_EGGS_MOVE", self._lay_eggs_move, Intent(IntentType.BUFF))
        smash = MoveState("SMASH_MOVE", self._smash_move,
                          Intent(IntentType.ATTACK, damage=self.smash_damage))
        tenderizer = MoveState("TENDERIZER_MOVE", self._tenderizer_move,
                               Intent(IntentType.ATTACK_DEBUFF, damage=self.tenderizer_damage))
        paste = MoveState("NUTRITIONAL_PASTE_MOVE", self._paste_move, Intent(IntentType.BUFF))
        branch = ConditionalBranchState("SUMMON_BRANCH_STATE")

        lay.follow_up_state = smash
        paste.follow_up_state = smash
        smash.follow_up_state = tenderizer
        tenderizer.follow_up_state = branch
        branch.add_state(lay, self._can_lay)
        branch.add_state(paste, None)  # 원본 () => !CanLay — 폴백(무조건)

        return MonsterMoveStateMachine([lay, smash, tenderizer, paste, branch], lay)

    def _lay_eggs_move(self, targets: List[Creature]) -> None:
        # 원본: 빈 알 슬롯을 뒤에서부터(LastOrDefault) 최대 3칸까지 ToughEgg로 채운다.
        from sts2_sim.models.sts2_power import MinionPower
        combat = self.combat_state
        if combat is None:
            return
        for _ in range(3):
            slot = combat.last_free_slot()
            if slot is None:
                break
            egg = combat.add_monster(ToughEgg(), slot_name=slot)
            egg.apply_power(MinionPower(1), applier=self)

    def _smash_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.smash_damage)

    def _tenderizer_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Vulnerable
        for target in targets:
            self.attack(target, self.tenderizer_damage)
            target.apply_power(Vulnerable(self.tenderizer_vulnerable), applier=self)

    def _paste_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(self.paste_strength))


BATCH15_MONSTERS = {
    "tough_egg": ToughEgg,
    "ovicopter": Ovicopter,
}

MONSTER_REGISTRY.update(BATCH15_MONSTERS)
