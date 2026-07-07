"""
STS2 MonsterModel — STS2 디컴파일 데이터 기반 몬스터 구현.
디컬파일 코드 구조를 모방한 Python 포트.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional, List, Callable, Dict, Any
import asyncio

if TYPE_CHECKING:
    from sts2_sim.core.combat_state import CombatState
    from sts2_sim.entities.creature import Creature


class IntentType(Enum):
    """STS2 Intent 타입."""
    ATTACK = auto()
    ATTACK_BUFF = auto()
    ATTACK_DEBUFF = auto()
    ATTACK_DEFEND = auto()
    BUFF = auto()
    DEBUFF = auto()
    DEFEND = auto()
    DEFEND_BUFF = auto()
    DEFEND_DEBUFF = auto()
    SLEEP = auto()
    STUN = auto()
    HIDDEN = auto()
    UNKNOWN = auto()


@dataclass
class Intent:
    """인텐트 정보."""
    intent_type: IntentType
    damage: int = 0
    times: int = 1


@dataclass
class MoveState:
    """몬스터의 한 행동 상태."""
    name: str
    execute: Callable  # async callable
    intent: Intent
    follow_up_state: Optional[MoveState] = None


class MonsterMoveStateMachine:
    """상태 머신: 몬스터의 행동 순서를 관리."""
    def __init__(self, states: List[MoveState], initial_state: MoveState):
        self.states = states
        self.current_state = initial_state
        self._move_history: List[str] = []

    def get_current_intent(self) -> Intent:
        return self.current_state.intent

    def get_current_move_name(self) -> str:
        return self.current_state.name

    async def execute_move(self, targets: List[Creature]) -> None:
        """현재 상태의 행동 실행."""
        if self.current_state.execute:
            await self.current_state.execute(targets)
        self._move_history.append(self.current_state.name)

    def advance_state(self) -> None:
        """다음 상태로 진행."""
        if self.current_state.follow_up_state:
            self.current_state = self.current_state.follow_up_state


class MonsterModel:
    """
    STS2 MonsterModel.
    게임의 모든 몬스터 베이스 클래스.
    """
    monster_id: str = "unknown_monster"
    title: str = "Unknown Monster"

    def __init__(self):
        self._current_hp: int = 0
        self._block: int = 0
        self._powers: Dict[str, Any] = {}
        self._move_state_machine: Optional[MonsterMoveStateMachine] = None
        self.combat_state: Optional[CombatState] = None
        self.creature: Optional[Creature] = None

    @property
    def min_initial_hp(self) -> int:
        """최소 초기 HP."""
        return 0

    @property
    def max_initial_hp(self) -> int:
        """최대 초기 HP (난이도 무관)."""
        return self.min_initial_hp

    @property
    def current_hp(self) -> int:
        return self._current_hp

    @property
    def max_hp(self) -> int:
        return self.max_initial_hp

    @property
    def block(self) -> int:
        return self._block

    @property
    def is_dead(self) -> bool:
        return self._current_hp <= 0

    @property
    def hp_percent(self) -> float:
        return self._current_hp / self.max_hp if self.max_hp > 0 else 0.0

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        """상태 머신 생성 (서브클래스에서 오버라이드)."""
        # 기본: 아무것도 안 하는 상태
        nothing_state = MoveState("NOTHING", self._nothing_move, Intent(IntentType.HIDDEN))
        nothing_state.follow_up_state = nothing_state
        return MonsterMoveStateMachine([nothing_state], nothing_state)

    async def _nothing_move(self, targets: List[Creature]) -> None:
        """아무것도 하지 않는 행동."""
        pass

    def setup_for_combat(self, state: CombatState) -> None:
        """전투 시작 시 초기화."""
        self.combat_state = state
        self._current_hp = self.max_initial_hp
        self._block = 0
        self._move_state_machine = self.generate_move_state_machine()

    async def after_added_to_room(self) -> None:
        """방에 추가된 후 호출 (오버라이드 가능)."""
        pass

    def get_current_intent(self) -> Intent:
        """현재 행동의 인텐트."""
        if self._move_state_machine:
            return self._move_state_machine.get_current_intent()
        return Intent(IntentType.UNKNOWN)

    async def take_turn(self, targets: List[Creature]) -> None:
        """몬스터의 턴 실행."""
        if self._move_state_machine:
            await self._move_state_machine.execute_move(targets)
            self._move_state_machine.advance_state()

    def prepare_for_next_turn(self) -> None:
        """다음 턴 준비 (블록 초기화, 파워 틱 등)."""
        self._block = 0
        # TODO: 파워 틱
        # for p in self._powers.values():
        #     p.tick_duration()

    def gain_block(self, amount: int) -> None:
        """블록 획득."""
        self._block += max(0, amount)

    def lose_hp(self, amount: int) -> int:
        """HP 감소."""
        actual = min(amount, self._current_hp)
        self._current_hp -= actual
        return actual

    def take_damage(self, amount: int, source: Optional[Creature] = None) -> Dict[str, Any]:
        """데미지 처리."""
        if amount <= 0:
            return {"hp_lost": 0, "killed": False}

        # 블록 처리
        block_absorbed = min(self._block, amount)
        self._block -= block_absorbed
        hp_dmg = amount - block_absorbed

        # HP 감소
        hp_lost = self.lose_hp(hp_dmg)
        return {"hp_lost": hp_lost, "killed": self.is_dead}

    def heal(self, amount: int) -> None:
        """HP 회복."""
        self._current_hp = min(self._current_hp + amount, self.max_hp)

    def __repr__(self) -> str:
        return f"{self.title}({self._current_hp}/{self.max_hp})"


# ══════════════════════════════════════════
# STS2 구체 몬스터 구현 (선별)
# ══════════════════════════════════════════

class BigDummy(MonsterModel):
    """테스트용 더미."""
    monster_id = "big_dummy"
    title = "Big Dummy"

    @property
    def min_initial_hp(self) -> int:
        return 9999

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        nothing_state = MoveState("NOTHING", self._nothing_move, Intent(IntentType.HIDDEN))
        nothing_state.follow_up_state = nothing_state
        return MonsterMoveStateMachine([nothing_state], nothing_state)


class SingleAttackMoveMonster(MonsterModel):
    """단일 공격만 하는 몬스터."""
    monster_id = "single_attack"
    title = "Single Attack Monster"

    @property
    def min_initial_hp(self) -> int:
        return 999

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        poke_state = MoveState("POKE", self._poke_move, Intent(IntentType.ATTACK, damage=1, times=1))
        poke_state.follow_up_state = poke_state
        return MonsterMoveStateMachine([poke_state], poke_state)

    async def _poke_move(self, targets: List[Creature]) -> None:
        """1의 데미지 공격."""
        if targets:
            for target in targets:
                target.take_damage(1, source=self)


class MultiAttackMoveMonster(MonsterModel):
    """여러 번 공격하는 몬스터."""
    monster_id = "multi_attack"
    title = "Multi Attack Monster"

    @property
    def min_initial_hp(self) -> int:
        return 999

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        attack_state = MoveState("ATTACK", self._attack_move, Intent(IntentType.ATTACK, damage=2, times=3))
        attack_state.follow_up_state = attack_state
        return MonsterMoveStateMachine([attack_state], attack_state)

    async def _attack_move(self, targets: List[Creature]) -> None:
        """2의 데미지를 3번 공격."""
        if targets:
            for _ in range(3):
                for target in targets:
                    target.take_damage(2, source=self)


# ══════════════════════════════════════════
# STS2 실제 몬스터들
# ══════════════════════════════════════════

class TwigSlimeS(MonsterModel):
    """작은 나뭇가지 슬라임."""
    monster_id = "twig_slime_s"
    title = "Twig Slime (S)"

    @property
    def min_initial_hp(self) -> int:
        return 7  # 기본값 (ToughEnemies 난이도: 8)

    @property
    def max_initial_hp(self) -> int:
        return 11  # 기본값 (ToughEnemies 난이도: 12)

    @property
    def tackle_damage(self) -> int:
        return 4  # 기본값 (DeadlyEnemies 난이도: 5)

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        tackle_state = MoveState(
            "TACKLE_MOVE",
            self._tackle_move,
            Intent(IntentType.ATTACK, damage=self.tackle_damage, times=1)
        )
        tackle_state.follow_up_state = tackle_state
        return MonsterMoveStateMachine([tackle_state], tackle_state)

    async def _tackle_move(self, targets: List[Creature]) -> None:
        """태클 공격."""
        if targets:
            for target in targets:
                target.take_damage(self.tackle_damage, source=self)


class Stabbot(MonsterModel):
    """스탭봇 로봇."""
    monster_id = "stabbot"
    title = "Stabbot"

    @property
    def min_initial_hp(self) -> int:
        return 18  # 기본값 (ToughEnemies: 19)

    @property
    def max_initial_hp(self) -> int:
        return 23  # 기본값 (ToughEnemies: 24)

    @property
    def stab_damage(self) -> int:
        return 11  # 기본값 (DeadlyEnemies: 12)

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        stab_state = MoveState(
            "STAB_MOVE",
            self._stab_move,
            Intent(IntentType.ATTACK_DEBUFF, damage=self.stab_damage, times=1)
        )
        stab_state.follow_up_state = stab_state
        return MonsterMoveStateMachine([stab_state], stab_state)

    async def _stab_move(self, targets: List[Creature]) -> None:
        """찌르기 공격 + Frail 부여."""
        if targets:
            for target in targets:
                target.take_damage(self.stab_damage, source=self)
                # TODO: Frail 파워 부여 (1 스택)


class AxeRubyRaider(MonsterModel):
    """도끼 루비 약탈자."""
    monster_id = "axe_ruby_raider"
    title = "Axe Ruby Raider"

    @property
    def min_initial_hp(self) -> int:
        return 20  # 기본값 (ToughEnemies: 21)

    @property
    def max_initial_hp(self) -> int:
        return 22  # 기본값 (ToughEnemies: 23)

    @property
    def swing_damage(self) -> int:
        return 5  # 기본값 (DeadlyEnemies: 6)

    @property
    def swing_block(self) -> int:
        return 5  # 기본값 (DeadlyEnemies: 6)

    @property
    def big_swing_damage(self) -> int:
        return 12  # 기본값 (DeadlyEnemies: 13)

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        swing1_state = MoveState(
            "SWING_1",
            self._swing_move,
            Intent(IntentType.ATTACK_DEFEND, damage=self.swing_damage, times=1)
        )
        swing2_state = MoveState(
            "SWING_2",
            self._swing_move,
            Intent(IntentType.ATTACK_DEFEND, damage=self.swing_damage, times=1)
        )
        big_swing_state = MoveState(
            "BIG_SWING",
            self._big_swing_move,
            Intent(IntentType.ATTACK, damage=self.big_swing_damage, times=1)
        )

        # 상태 전환: SWING_1 → SWING_2 → BIG_SWING → SWING_1
        swing1_state.follow_up_state = swing2_state
        swing2_state.follow_up_state = big_swing_state
        big_swing_state.follow_up_state = swing1_state

        return MonsterMoveStateMachine([swing1_state, swing2_state, big_swing_state], swing1_state)

    async def _swing_move(self, targets: List[Creature]) -> None:
        """일반 스윙: 데미지 + 블록 획득."""
        if targets:
            for target in targets:
                target.take_damage(self.swing_damage, source=self)
        self.gain_block(self.swing_block)

    async def _big_swing_move(self, targets: List[Creature]) -> None:
        """큰 스윙: 데미지만."""
        if targets:
            for target in targets:
                target.take_damage(self.big_swing_damage, source=self)
