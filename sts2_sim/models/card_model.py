"""
CardModel — 카드 기반 클래스.
sts2.dll MegaCrit.Sts2.Core.Models.CardModel 대응.
"""
from __future__ import annotations
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

from sts2_sim.models.abstract_model import AbstractModel

if TYPE_CHECKING:
    from sts2_sim.core.combat_state import CombatState
    from sts2_sim.entities.creature import Creature


class CardType(Enum):
    ATTACK = auto()
    SKILL = auto()
    POWER = auto()
    STATUS = auto()
    CURSE = auto()


class CardRarity(Enum):
    BASIC = auto()
    STARTER = auto()
    COMMON = auto()
    UNCOMMON = auto()
    RARE = auto()
    SPECIAL = auto()
    CURSE = auto()


class TargetType(Enum):
    NONE = auto()          # 타겟 없음 (블록 등)
    SINGLE_ENEMY = auto()  # 단일 적
    ALL_ENEMIES = auto()   # 전체 적
    SELF = auto()          # 자신
    ANY = auto()           # 아무 크리쳐


class PileType(Enum):
    HAND = auto()
    DRAW = auto()
    DISCARD = auto()
    EXHAUST = auto()
    VOID = auto()   # 완전히 제거


class CardModel(AbstractModel):
    """
    모든 카드의 기반 클래스.
    서브클래스에서 use()를 구현해 카드 효과를 정의한다.
    """

    # 서브클래스에서 클래스 변수로 정의
    card_id: str = "unknown"
    name: str = "Unknown Card"
    card_type: CardType = CardType.SKILL
    rarity: CardRarity = CardRarity.COMMON
    target_type: TargetType = TargetType.NONE
    base_energy_cost: int = 1
    base_star_cost: int = 0       # STS2 Stars 시스템
    exhausts: bool = False
    ethereal: bool = False        # 턴 종료 시 소모
    innate: bool = False          # 항상 초기 핸드에

    def __init__(self):
        super().__init__()
        self._energy_cost: int = self.base_energy_cost
        self._star_cost: int = self.base_star_cost
        self._upgraded: bool = False
        self._temporary_cost_mods: list[int] = []  # 일시적 비용 변경
        self.owner: Optional[object] = None  # Player 참조
        self._exhaust_on_next_play: bool = False

    # ──────────────────────────────────────────
    # 비용
    # ──────────────────────────────────────────

    @property
    def energy_cost(self) -> int:
        """현재 에너지 비용 (임시 수정 포함)."""
        cost = self._energy_cost
        for mod in self._temporary_cost_mods:
            cost += mod
        return max(0, cost)

    @property
    def star_cost(self) -> int:
        return max(0, self._star_cost)

    def add_temporary_cost_mod(self, delta: int):
        self._temporary_cost_mods.append(delta)

    def clear_temporary_cost_mods(self):
        self._temporary_cost_mods.clear()

    def can_play(self, state: "CombatState") -> bool:
        """이 카드를 현재 플레이할 수 있는지 확인."""
        player = state.player
        if player.creature.is_dead:
            return False
        if player.energy < self.energy_cost:
            return False
        if self.star_cost > 0 and player.stars < self.star_cost:
            return False
        return True

    # ──────────────────────────────────────────
    # 카드 효과 (서브클래스에서 구현)
    # ──────────────────────────────────────────

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        """카드 효과 구현. 서브클래스에서 override."""
        raise NotImplementedError(f"{self.__class__.__name__}.use() not implemented")

    # ──────────────────────────────────────────
    # 파일 이동 결정
    # ──────────────────────────────────────────

    def get_result_pile(self, state: "CombatState") -> PileType:
        """
        플레이 후 이동할 파일 타입.
        GetResultPileTypeAndPositionForCardPlay() 대응.
        """
        if self.exhausts or self._exhaust_on_next_play:
            return PileType.EXHAUST
        if self.ethereal:
            return PileType.EXHAUST
        return PileType.DISCARD

    # ──────────────────────────────────────────
    # 업그레이드 (서브클래스에서 override)
    # ──────────────────────────────────────────

    @property
    def is_upgraded(self) -> bool:
        return self._upgraded

    def upgrade(self):
        if not self._upgraded:
            self._upgraded = True
            self._upgrade_internal()

    def _upgrade_internal(self):
        """업그레이드 효과. 서브클래스에서 override."""
        pass

    # ──────────────────────────────────────────
    # 유틸
    # ──────────────────────────────────────────

    def create_clone(self) -> "CardModel":
        import copy
        return copy.deepcopy(self)

    def end_of_turn_cleanup(self, state: "CombatState"):
        """턴 종료 시 임시 비용 초기화 등."""
        self.clear_temporary_cost_mods()
        self._exhaust_on_next_play = False

    def __repr__(self):
        upg = "+" if self._upgraded else ""
        return f"{self.name}{upg}(cost={self.energy_cost})"
