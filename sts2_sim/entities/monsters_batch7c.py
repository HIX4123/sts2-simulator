"""
STS2 몬스터 배치 7c — 디컴파일 Models.Monsters.* 이식 (3종).
Wriggler / Myte / FrogKnight.
모든 수치는 Ascension 미적용 기본값 (AscensionHelper.GetValueIfAscension(..., tough, normal)의
normal/마지막 인자를 사용).
"""
from __future__ import annotations
import random
from typing import List, Optional

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    MonsterModel, MonsterMoveStateMachine, MoveState, RandomBranchState,
    Intent, IntentType, MONSTER_REGISTRY,
)


class Wriggler(MonsterModel):
    """리글러 — HP 17~21.

    원본(Wriggler.cs) 그래프: SPAWNED_MOVE(스턴, StartStunned일 때만) →
    ConditionalBranchState("INIT_MOVE") → NASTY_BITE_MOVE(6딜) ↔
    WRIGGLE_MOVE(대상마다 Infection 1장 버림더미 + 자신 힘+2) 교대 순환.

    INIT_MOVE는 슬롯 이름 분기(wriggler1/3 → NASTY_BITE, wriggler2/4 → WRIGGLE)로,
    Nibbit(is_alone/is_front)과 동일하게 생성자 플래그 starts_with_wriggle로 인코딩
    (짝수 슬롯 = True). start_stunned — 원본 StartStunned(소환 직후 1턴 대기,
    FatGremlin SPAWNED_MOVE와 동일 패턴), 인카운터/소환자에서 주입되므로 기본 False.
    ShouldShowMoveInBestiary(NASTY_BITE/SPAWNED 숨김)는 도감 표시 전용이라 미이식.
    """
    monster_id = "wriggler"
    title = "Wriggler"

    def __init__(self, starts_with_wriggle: bool = False, start_stunned: bool = False):
        super().__init__()
        self.starts_with_wriggle = starts_with_wriggle
        self.start_stunned = start_stunned

    @property
    def min_initial_hp(self) -> int:
        return 17

    @property
    def max_initial_hp(self) -> int:
        return 21

    @property
    def bite_damage(self) -> int:
        return 6

    @property
    def wriggle_strength(self) -> int:
        return 2

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        bite = MoveState("NASTY_BITE_MOVE", self._bite_move,
                         Intent(IntentType.ATTACK, damage=self.bite_damage))
        wriggle = MoveState("WRIGGLE_MOVE", self._wriggle_move,
                            Intent(IntentType.BUFF))  # 원본: BuffIntent + StatusIntent(1)
        spawned = MoveState("SPAWNED_MOVE", self._spawned_move, Intent(IntentType.STUN))
        bite.follow_up_state = wriggle
        wriggle.follow_up_state = bite
        # 원본 ConditionalBranchState("INIT_MOVE") — 슬롯 위치를 생성자 플래그로 해석
        first = wriggle if self.starts_with_wriggle else bite
        spawned.follow_up_state = first
        initial = spawned if self.start_stunned else first
        return MonsterMoveStateMachine([spawned, bite, wriggle], initial)

    def _spawned_move(self, targets: List[Creature]) -> None:
        pass  # 원본 SpawnedMove: Task.CompletedTask (아무것도 안 함)

    def _bite_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.bite_damage)

    def _wriggle_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        # 원본: CardPileCmd.AddToCombatAndPreview<Infection>(targets, Discard, 1)
        # — 대상마다 1장. 싱글플레이 기준 플레이어 버림더미에 1장.
        self.add_status_to_player_discard("infection", 1)
        self.apply_power(Strength(self.wriggle_strength))


class Myte(MonsterModel):
    """마이트 — HP 61~67.

    원본(Myte.cs) 그래프: ConditionalBranchState("INIT_MOVE")로 슬롯 이름 분기
    (first → TOXIC_MOVE, second → SUCK_MOVE — 생성자 플래그 is_second로 인코딩) 후
    TOXIC_MOVE(Toxic 2장 손패 삽입) → BITE_MOVE(13딜) →
    SUCK_MOVE(4딜 + 자신 힘+2) → TOXIC_MOVE 순환.
    """
    monster_id = "myte"
    title = "Myte"

    def __init__(self, is_second: bool = False):
        super().__init__()
        self.is_second = is_second

    @property
    def min_initial_hp(self) -> int:
        return 61

    @property
    def max_initial_hp(self) -> int:
        return 67

    @property
    def bite_damage(self) -> int:
        return 13

    @property
    def suck_damage(self) -> int:
        return 4

    @property
    def suck_strength(self) -> int:
        return 2

    @property
    def toxic_count(self) -> int:
        return 2

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        toxic = MoveState("TOXIC_MOVE", self._toxic_move, Intent(IntentType.STATUS))
        bite = MoveState("BITE_MOVE", self._bite_move,
                         Intent(IntentType.ATTACK, damage=self.bite_damage))
        suck = MoveState("SUCK_MOVE", self._suck_move,
                         Intent(IntentType.ATTACK_BUFF, damage=self.suck_damage))
        toxic.follow_up_state = bite
        bite.follow_up_state = suck
        suck.follow_up_state = toxic
        # 원본 ConditionalBranchState("INIT_MOVE") — 슬롯 위치를 생성자 플래그로 해석
        initial = suck if self.is_second else toxic
        return MonsterMoveStateMachine([toxic, bite, suck], initial)

    def _toxic_move(self, targets: List[Creature]) -> None:
        # 원본: CardPileCmd.AddToCombatAndPreview<Toxic>(targets, Hand, 2)
        # — 대상마다 손패에 2장. 싱글플레이 기준 플레이어 손패에 2장
        # (손패 10장 초과분은 버림더미 — 엔진 generate_card 동작과 동일).
        if self.combat_state is not None and hasattr(self.combat_state, "generate_card"):
            self.combat_state.generate_card("toxic", count=self.toxic_count,
                                            to="hand", creator_is_player=False)

    def _bite_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.bite_damage)

    def _suck_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        for target in targets:
            self.attack(target, self.suck_damage)
        self.apply_power(Strength(self.suck_strength))


class _FrogKnightHalfHealthBranch(RandomBranchState):
    """FrogKnight 전용 런타임 조건 분기 (원본 ConditionalBranchState "HALF_HEALTH").

    슬롯 위치 분기(생성 시점 확정)와 달리 현재 HP를 매 턴 검사해야 하므로
    생성자 플래그로 인코딩할 수 없다. advance_state()가 RandomBranchState의
    resolve()를 호출하는 것을 이용해, resolve()에서 무작위 대신 원본 조건
    (HasBeetleCharged || CurrentHp >= MaxHp/2 → TONGUE_LASH,
     !HasBeetleCharged && CurrentHp < MaxHp/2 → BEETLE_CHARGE)을 평가한다.
    """

    def __init__(self, name: str, owner: "FrogKnight",
                 tongue_lash: MoveState, beetle_charge: MoveState):
        super().__init__(name)
        self._owner = owner
        self._tongue_lash = tongue_lash
        self._beetle_charge = beetle_charge

    def resolve(self, rng: random.Random, last_move_name: Optional[str],
                history: Optional[List[str]] = None) -> MoveState:
        owner = self._owner
        if (not owner.has_beetle_charged
                and owner.current_hp < owner.max_hp // 2):
            return self._beetle_charge
        return self._tongue_lash


class FrogKnight(MonsterModel):
    """개구리 기사 (엘리트) — HP 191 (고정), 개전 시 Plating 15.

    원본(FrogKnight.cs) 그래프:
      TONGUE_LASH(13딜 + 전체 허약 2) [초기] → STRIKE_DOWN_EVIL(21딜) →
      FOR_THE_QUEEN(자신 힘+5) → HALF_HEALTH 분기:
        - HasBeetleCharged 또는 HP >= 최대 HP의 절반 → TONGUE_LASH
        - 아직 돌진 안 했고 HP < 절반 → BEETLE_CHARGE(35딜, 1회 한정) → TONGUE_LASH
    HALF_HEALTH는 런타임 HP 조건이므로 _FrogKnightHalfHealthBranch
    (RandomBranchState.resolve 오버라이드)로 이식.
    """
    monster_id = "frog_knight"
    title = "Frog Knight"

    def __init__(self):
        super().__init__()
        self.has_beetle_charged = False

    @property
    def min_initial_hp(self) -> int:
        return 191

    @property
    def strike_down_evil_damage(self) -> int:
        return 21

    @property
    def tongue_lash_damage(self) -> int:
        return 13

    @property
    def tongue_lash_frail(self) -> int:
        return 2

    @property
    def beetle_charge_damage(self) -> int:
        return 35

    @property
    def plating_amount(self) -> int:
        return 15

    @property
    def for_the_queen_strength(self) -> int:
        return 5

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import Plating
        self.apply_power(Plating(self.plating_amount))
        self.has_beetle_charged = False

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        queen = MoveState("FOR_THE_QUEEN", self._for_the_queen_move,
                          Intent(IntentType.BUFF))
        strike = MoveState("STRIKE_DOWN_EVIL", self._strike_down_evil_move,
                           Intent(IntentType.ATTACK, damage=self.strike_down_evil_damage))
        lash = MoveState("TONGUE_LASH", self._tongue_lash_move,
                         Intent(IntentType.ATTACK_DEBUFF, damage=self.tongue_lash_damage))
        charge = MoveState("BEETLE_CHARGE", self._beetle_charge_move,
                           Intent(IntentType.ATTACK, damage=self.beetle_charge_damage))
        half_health = _FrogKnightHalfHealthBranch("HALF_HEALTH", self, lash, charge)
        queen.follow_up_state = half_health
        strike.follow_up_state = queen
        lash.follow_up_state = strike
        charge.follow_up_state = lash
        return MonsterMoveStateMachine([half_health, queen, strike, lash, charge], lash)

    def _for_the_queen_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(self.for_the_queen_strength))

    def _strike_down_evil_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.strike_down_evil_damage)

    def _tongue_lash_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Frail
        for target in targets:
            self.attack(target, self.tongue_lash_damage)
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Frail(self.tongue_lash_frail))

    def _beetle_charge_move(self, targets: List[Creature]) -> None:
        self.has_beetle_charged = True
        for target in targets:
            self.attack(target, self.beetle_charge_damage)


BATCH7C_MONSTERS = {
    "wriggler": Wriggler,
    "myte": Myte,
    "frog_knight": FrogKnight,
}

MONSTER_REGISTRY.update(BATCH7C_MONSTERS)
