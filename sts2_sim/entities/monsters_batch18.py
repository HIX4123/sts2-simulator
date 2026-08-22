"""
STS2 몬스터 배치 18 (S1.M3.B18) — BowlbugEgg / BowlbugNectar / BowlbugRock / BowlbugSilk.
모든 수치는 Ascension 미적용 기본값.

BowlbugRock은 개전 ImbalancedPower(1)를 갖고, 공격이 블록에 전부 막히면
off-balance 상태가 되어 다음 무브를 DIZZY로 전환한다. 나머지 세 종은 각각
단순 반복·초기 버프 후 고정 루프·디버프 시작 순환 등 다른 골격을 가진다.
"""
from __future__ import annotations
from typing import List

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    MonsterModel, MonsterMoveStateMachine, MoveState, ConditionalBranchState,
    Intent, IntentType, MONSTER_REGISTRY,
)


class BowlbugEgg(MonsterModel):
    """볼버그 알 — HP 21~22. 공격 7 + 방어 7 반복.

    원본(BowlbugEgg.cs) 그래프:
      BITE_MOVE(7딜 + 블록 7) → BITE_MOVE (자기 루프)."""
    monster_id = "bowlbug_egg"
    title = "Bowlbug Egg"

    @property
    def min_initial_hp(self) -> int:
        return 21

    @property
    def max_initial_hp(self) -> int:
        return 22

    @property
    def bite_damage(self) -> int:
        return 7

    @property
    def protect_block(self) -> int:
        return 7

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        bite = MoveState("BITE_MOVE", self._bite_move,
                         Intent(IntentType.ATTACK_DEFEND,
                                damage=self.bite_damage))
        bite.follow_up_state = bite
        return MonsterMoveStateMachine([bite], bite)

    def _bite_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.bite_damage)
        self.gain_block(self.protect_block)


class BowlbugNectar(MonsterModel):
    """볼버그 넥타 — HP 35~38. 공격 3 → 힘 +15 → 공격 3 무한.

    원본(BowlbugNectar.cs) 그래프:
      THRASH_MOVE(3딜) → BUFF_MOVE(힘+15) → THRASH2_MOVE(3딜, 자기 루프)."""
    monster_id = "bowlbug_nectar"
    title = "Bowlbug Nectar"

    @property
    def min_initial_hp(self) -> int:
        return 35

    @property
    def max_initial_hp(self) -> int:
        return 38

    @property
    def thrash_damage(self) -> int:
        return 3

    @property
    def buff_strength(self) -> int:
        return 15

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        thrash = MoveState("THRASH_MOVE", self._thrash_move,
                           Intent(IntentType.ATTACK, damage=self.thrash_damage))
        buff = MoveState("BUFF_MOVE", self._buff_move, Intent(IntentType.BUFF))
        thrash2 = MoveState("THRASH2_MOVE", self._thrash_move,
                            Intent(IntentType.ATTACK, damage=self.thrash_damage))

        thrash.follow_up_state = buff
        buff.follow_up_state = thrash2
        thrash2.follow_up_state = thrash2

        return MonsterMoveStateMachine([thrash, buff, thrash2], thrash)

    def _thrash_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.thrash_damage)

    def _buff_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(self.buff_strength))


class BowlbugRock(MonsterModel):
    """볼버그 바위 — HP 45~48. 개전 Imbalanced(1). 공격 15.

    원본(BowlbugRock.cs) 그래프:
      HEADBUTT_MOVE(15딜) → POST_HEADBUTT(조건 분기)
        IsOffBalance → DIZZY_MOVE(깃 초기화) → HEADBUTT_MOVE
        !IsOffBalance → HEADBUTT_MOVE

    HeadbuttMove는 공격 후 IsOffBalance를 검사해 기절하지만,
    현재 상태 머신에서는 POST_HEADBUTT 조건 분기가 같은 결과를
    더 안전하게 만든다 — 무브 실행 중 stun()이 history를 어지럽히는
    대신 분기가 DIZZY를 선택한다."""
    monster_id = "bowlbug_rock"
    title = "Bowlbug Rock"

    def __init__(self):
        super().__init__()
        self.is_off_balance = False

    @property
    def min_initial_hp(self) -> int:
        return 45

    @property
    def max_initial_hp(self) -> int:
        return 48

    @property
    def headbutt_damage(self) -> int:
        return 15

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import ImbalancedPower
        self.apply_power(ImbalancedPower(1))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        headbutt = MoveState("HEADBUTT_MOVE", self._headbutt_move,
                             Intent(IntentType.ATTACK,
                                    damage=self.headbutt_damage))
        dizzy = MoveState("DIZZY_MOVE", self._dizzy_move,
                          Intent(IntentType.STUN))
        branch = ConditionalBranchState("POST_HEADBUTT")

        headbutt.follow_up_state = branch
        branch.add_state(dizzy, lambda: self.is_off_balance)
        branch.add_state(headbutt, None)
        dizzy.follow_up_state = headbutt

        return MonsterMoveStateMachine([headbutt, dizzy, branch], headbutt)

    def _headbutt_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.headbutt_damage)

    def _dizzy_move(self, targets: List[Creature]) -> None:
        self.is_off_balance = False


class BowlbugSilk(MonsterModel):
    """볼버그 비단 — HP 40~43. 공격 4×2 ↔ 독침(약화 1) 순환.

    원본(BowlbugSilk.cs) 그래프:
      THRASH_MOVE(4딜×2) → TOXIC_SPIT_MOVE(약화 1) → THRASH_MOVE (자기 루프).
    시작 무브는 TOXIC_SPIT_MOVE다 (원본 initialState = moveState2)."""
    monster_id = "bowlbug_silk"
    title = "Bowlbug Silk"

    @property
    def min_initial_hp(self) -> int:
        return 40

    @property
    def max_initial_hp(self) -> int:
        return 43

    @property
    def thrash_damage(self) -> int:
        return 4

    @property
    def thrash_hits(self) -> int:
        return 2

    @property
    def weak_amount(self) -> int:
        return 1

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        thrash = MoveState("THRASH_MOVE", self._thrash_move,
                           Intent(IntentType.ATTACK, damage=self.thrash_damage,
                                  times=self.thrash_hits))
        spit = MoveState("TOXIC_SPIT_MOVE", self._spit_move,
                         Intent(IntentType.DEBUFF))

        thrash.follow_up_state = spit
        spit.follow_up_state = thrash

        return MonsterMoveStateMachine([thrash, spit], spit)

    def _thrash_move(self, targets: List[Creature]) -> None:
        for _ in range(self.thrash_hits):
            for target in targets:
                self.attack(target, self.thrash_damage)

    def _spit_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Weak
        for target in targets:
            target.apply_power(Weak(self.weak_amount), applier=self)


BATCH18_MONSTERS = {
    "bowlbug_egg": BowlbugEgg,
    "bowlbug_nectar": BowlbugNectar,
    "bowlbug_rock": BowlbugRock,
    "bowlbug_silk": BowlbugSilk,
}

MONSTER_REGISTRY.update(BATCH18_MONSTERS)
