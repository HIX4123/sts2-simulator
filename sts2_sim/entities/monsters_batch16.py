"""
STS2 몬스터 배치 16 (Phase 6u) — Tunneler / SlumberingBeetle / OwlMagistrate.
모든 수치는 Ascension 미적용 기본값.

세 마리 모두 "1턴짜리 무적 태세를 깔고 그 다음 턴에 큰 걸 친다"는 같은 골격을
서로 다른 파워로 구현한다: Tunneler는 유지되는 블록(BurrowedPower), OwlMagistrate는
받는 피해 절반(SoarPower), SlumberingBeetle은 개전부터 자고 있다가 깨어난다
(SlumberPower + Plating).
"""
from __future__ import annotations
from typing import List

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    MonsterModel, MonsterMoveStateMachine, MoveState, ConditionalBranchState,
    Intent, IntentType, MONSTER_REGISTRY,
)


class Tunneler(MonsterModel):
    """터널러 — HP 87 고정.

    원본(Tunneler.cs) 그래프: BITE(13) → BURROW(BurrowedPower + 블록 32) →
    BELOW(23, 무한 반복). 굴에 들어가면 블록이 턴 시작에 사라지지 않으므로
    BELOW를 계속 맞아야 하고, 블록을 전부 깨야만 BurrowedPower가 벗겨지며
    기절 → DIZZY(무행동) → BITE부터 다시 시작한다.

    DIZZY_MOVE는 원본 그래프에 노드로 존재하지만 정규 흐름에서는 진입하지
    않는다 — BurrowedPower가 `CreatureCmd.Stun`으로 임시 삽입할 때만 쓰인다."""
    monster_id = "tunneler"
    title = "Tunneler"

    @property
    def min_initial_hp(self) -> int:
        return 87

    @property
    def max_initial_hp(self) -> int:
        return 87

    @property
    def bite_damage(self) -> int:
        return 13

    @property
    def block_gain(self) -> int:
        return 32

    @property
    def below_damage(self) -> int:
        return 23

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        bite = MoveState("BITE_MOVE", self._bite_move,
                         Intent(IntentType.ATTACK, damage=self.bite_damage))
        burrow = MoveState("BURROW_MOVE", self._burrow_move, Intent(IntentType.DEFEND_BUFF))
        below = MoveState("BELOW_MOVE", self._below_move,
                          Intent(IntentType.ATTACK, damage=self.below_damage))
        dizzy = MoveState("DIZZY_MOVE", self.still_dizzy_move, Intent(IntentType.STUN))

        bite.follow_up_state = burrow
        burrow.follow_up_state = below
        below.follow_up_state = below
        dizzy.follow_up_state = bite

        return MonsterMoveStateMachine([bite, burrow, below, dizzy], bite)

    def _bite_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.bite_damage)

    def _burrow_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import BurrowedPower
        self.apply_power(BurrowedPower(1))
        self.gain_block(self.block_gain)

    def _below_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.below_damage)

    def get_stunned(self) -> None:
        """BurrowedPower가 깨졌을 때 호출 — 다음 턴을 DIZZY로 쓰고 BITE부터 재개
        (원본 CreatureCmd.Stun(owner, StillDizzyMove, "BITE_MOVE"))."""
        self.stun(self.still_dizzy_move, "BITE_MOVE")

    def still_dizzy_move(self, targets: List[Creature]) -> None:
        pass


class SlumberingBeetle(MonsterModel):
    """잠자는 딱정벌레 — HP 86 고정. 개전 Plating 15 + Slumber 3.

    원본(SlumberingBeetle.cs) 그래프: SNORE(무행동) → SNORE_NEXT 분기
    { Slumber 보유? SNORE : ROLL_OUT } / ROLL_OUT(16딜 + 자기 힘 +2, 무한 반복).
    Slumber가 0이 되는 순간 깨어나며 Plating을 잃는다."""
    monster_id = "slumbering_beetle"
    title = "Slumbering Beetle"

    def __init__(self):
        super().__init__()
        self.is_awake = False

    @property
    def min_initial_hp(self) -> int:
        return 86

    @property
    def max_initial_hp(self) -> int:
        return 86

    @property
    def rollout_damage(self) -> int:
        return 16

    @property
    def plating_amount(self) -> int:
        return 15

    @property
    def slumber_amount(self) -> int:
        return 3

    @property
    def rollout_strength(self) -> int:
        return 2

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import Plating, SlumberPower
        self.apply_power(Plating(self.plating_amount))
        self.apply_power(SlumberPower(self.slumber_amount))

    def wake_up_move(self, targets: List[Creature]) -> None:
        """기상 — Plating을 잃는다. SlumberPower가 두 경로(피해/턴 종료)에서
        호출하므로 멱등해야 한다."""
        self.is_awake = True
        if self.has_power("plating"):
            self.remove_power("plating")

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        snore = MoveState("SNORE_MOVE", self._snore_move, Intent(IntentType.SLEEP))
        rollout = MoveState("ROLL_OUT_MOVE", self._rollout_move,
                            Intent(IntentType.ATTACK_BUFF, damage=self.rollout_damage))
        branch = ConditionalBranchState("SNORE_NEXT")

        snore.follow_up_state = branch
        branch.add_state(snore, lambda: self.has_power("slumber"))
        branch.add_state(rollout, None)  # 원본 () => !HasPower<SlumberPower>()
        rollout.follow_up_state = rollout

        return MonsterMoveStateMachine([snore, branch, rollout], snore)

    def _snore_move(self, targets: List[Creature]) -> None:
        pass

    def _rollout_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        for target in targets:
            self.attack(target, self.rollout_damage)
        self.apply_power(Strength(self.rollout_strength))


class OwlMagistrate(MonsterModel):
    """올빼미 치안판사 — HP 231 고정.

    원본(OwlMagistrate.cs) 그래프 4단 순환:
      MAGISTRATE_SCRUTINY(16) → PECK_ASSAULT(4딜 ×6) → JUDICIAL_FLIGHT(SoarPower)
      → VERDICT(33딜 + 취약 4, SoarPower 제거) → 처음으로."""
    monster_id = "owl_magistrate"
    title = "Owl Magistrate"

    @property
    def min_initial_hp(self) -> int:
        return 231

    @property
    def max_initial_hp(self) -> int:
        return 231

    @property
    def scrutiny_damage(self) -> int:
        return 16

    @property
    def peck_damage(self) -> int:
        return 4

    @property
    def peck_hits(self) -> int:
        return 6

    @property
    def verdict_damage(self) -> int:
        return 33

    @property
    def verdict_vulnerable(self) -> int:
        return 4

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        scrutiny = MoveState("MAGISTRATE_SCRUTINY", self._scrutiny_move,
                             Intent(IntentType.ATTACK, damage=self.scrutiny_damage))
        peck = MoveState("PECK_ASSAULT", self._peck_move,
                         Intent(IntentType.ATTACK, damage=self.peck_damage,
                                times=self.peck_hits))
        flight = MoveState("JUDICIAL_FLIGHT", self._flight_move, Intent(IntentType.BUFF))
        verdict = MoveState("VERDICT", self._verdict_move,
                            Intent(IntentType.ATTACK_DEBUFF, damage=self.verdict_damage))

        scrutiny.follow_up_state = peck
        peck.follow_up_state = flight
        flight.follow_up_state = verdict
        verdict.follow_up_state = scrutiny

        return MonsterMoveStateMachine([scrutiny, peck, flight, verdict], scrutiny)

    def _scrutiny_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.scrutiny_damage)

    def _peck_move(self, targets: List[Creature]) -> None:
        for _ in range(self.peck_hits):
            for target in targets:
                self.attack(target, self.peck_damage)

    def _flight_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import SoarPower
        self.apply_power(SoarPower(1))

    def _verdict_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Vulnerable
        for target in targets:
            self.attack(target, self.verdict_damage)
            target.apply_power(Vulnerable(self.verdict_vulnerable), applier=self)
        if self.has_power("soar"):
            self.remove_power("soar")


BATCH16_MONSTERS = {
    "tunneler": Tunneler,
    "slumbering_beetle": SlumberingBeetle,
    "owl_magistrate": OwlMagistrate,
}

MONSTER_REGISTRY.update(BATCH16_MONSTERS)
