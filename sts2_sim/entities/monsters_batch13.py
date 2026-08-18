"""
STS2 몬스터 배치 13 (Phase 6r) — 신규 서브시스템 없이 이식 가능한 몬스터.
모든 수치는 Ascension 미적용 기본값.

Architect(HP 9999, 무행동)는 연출/개발용 더미라 제외했다.
"""
from __future__ import annotations
from typing import List

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    MonsterModel, MonsterMoveStateMachine, MoveState, RandomBranchState,
    Intent, IntentType, MONSTER_REGISTRY,
)


class CubexConstruct(MonsterModel):
    """큐벡스 컨스트럭트 — HP 65. 개전 시 블록 13 + ArtifactPower(1).

    원본(CubexConstruct.cs) 그래프: CHARGE_UP(힘 +2) → REPEATER_BLAST(7딜 + 힘 +2)
    → REPEATER_BLAST_2(같은 동작의 별개 상태) → EXPEL(5딜×2) →
    REPEATER_BLAST → ... (첫 CHARGE_UP 이후 3순환).

    IsBurrowed/IsCharging 플래그와 CurrentHpChanged 훅은 스파인 애니메이션·
    SFX 전용이라 이식하지 않는다 (전투 판정에 관여하지 않음)."""
    monster_id = "cubex_construct"
    title = "Cubex Construct"

    @property
    def min_initial_hp(self) -> int:
        return 65

    @property
    def max_initial_hp(self) -> int:
        return 65

    @property
    def opening_block(self) -> int:
        return 13

    @property
    def blast_damage(self) -> int:
        return 7

    @property
    def expel_damage(self) -> int:
        return 5

    @property
    def expel_repeat(self) -> int:
        return 2

    @property
    def strength_gain(self) -> int:
        return 2

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import Artifact
        self.gain_block(self.opening_block)  # 원본 ValueProp.Move
        self.apply_power(Artifact(1))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        charge = MoveState("CHARGE_UP_MOVE", self._charge_up_move, Intent(IntentType.BUFF))
        blast1 = MoveState("REPEATER_BLAST_MOVE", self._repeater_blast_move,
                           Intent(IntentType.ATTACK_BUFF, damage=self.blast_damage))
        blast2 = MoveState("REPEATER_BLAST_MOVE_2", self._repeater_blast_move,
                           Intent(IntentType.ATTACK_BUFF, damage=self.blast_damage))
        expel = MoveState("EXPEL_MOVE", self._expel_move,
                          Intent(IntentType.ATTACK, damage=self.expel_damage,
                                 times=self.expel_repeat))
        charge.follow_up_state = blast1
        blast1.follow_up_state = blast2
        blast2.follow_up_state = expel
        expel.follow_up_state = blast1
        return MonsterMoveStateMachine([charge, blast1, blast2, expel], charge)

    def _charge_up_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(self.strength_gain))

    def _repeater_blast_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        for target in targets:
            self.attack(target, self.blast_damage)
        self.apply_power(Strength(self.strength_gain))

    def _expel_move(self, targets: List[Creature]) -> None:
        for _ in range(self.expel_repeat):
            for target in targets:
                self.attack(target, self.expel_damage)


class SoulNexus(MonsterModel):
    """소울 넥서스 (엘리트) — HP 234, 개전 파워 없음.

    원본(SoulNexus.cs) 그래프: SOUL_BURN(29딜) / MAELSTROM(6딜×4) /
    DRAIN_LIFE(18딜 + 취약 2 + 약화 2) 3분기 RAND, 세 분기 모두
    CannotRepeat + 가중치 1. 모든 무브가 RAND로 복귀하며 첫 무브는 SOUL_BURN."""
    monster_id = "soul_nexus"
    title = "Soul Nexus"

    @property
    def min_initial_hp(self) -> int:
        return 234

    @property
    def max_initial_hp(self) -> int:
        return 234

    @property
    def soul_burn_damage(self) -> int:
        return 29

    @property
    def maelstrom_damage(self) -> int:
        return 6

    @property
    def maelstrom_repeat(self) -> int:
        return 4

    @property
    def drain_life_damage(self) -> int:
        return 18

    @property
    def drain_life_debuff(self) -> int:
        return 2

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        soul_burn = MoveState("SOUL_BURN_MOVE", self._soul_burn_move,
                              Intent(IntentType.ATTACK, damage=self.soul_burn_damage))
        maelstrom = MoveState("MAELSTROM_MOVE", self._maelstrom_move,
                              Intent(IntentType.ATTACK, damage=self.maelstrom_damage,
                                     times=self.maelstrom_repeat))
        drain = MoveState("DRAIN_LIFE_MOVE", self._drain_life_move,
                          Intent(IntentType.ATTACK_DEBUFF, damage=self.drain_life_damage))
        rand = RandomBranchState("RAND")
        rand.add_branch(soul_burn, cannot_repeat=True)
        rand.add_branch(maelstrom, cannot_repeat=True)
        rand.add_branch(drain, cannot_repeat=True)
        soul_burn.follow_up_state = rand
        maelstrom.follow_up_state = rand
        drain.follow_up_state = rand
        return MonsterMoveStateMachine([soul_burn, maelstrom, drain, rand], soul_burn)

    def _soul_burn_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.soul_burn_damage)

    def _maelstrom_move(self, targets: List[Creature]) -> None:
        for _ in range(self.maelstrom_repeat):
            for target in targets:
                self.attack(target, self.maelstrom_damage)

    def _drain_life_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Vulnerable, Weak
        for target in targets:
            self.attack(target, self.drain_life_damage)
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Vulnerable(self.drain_life_debuff), applier=self)
                target.apply_power(Weak(self.drain_life_debuff), applier=self)


BATCH13_MONSTERS = {
    "cubex_construct": CubexConstruct,
    "soul_nexus": SoulNexus,
}

MONSTER_REGISTRY.update(BATCH13_MONSTERS)
