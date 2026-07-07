"""
STS2 Card System — STS2 스타일 카드 기본 구현.
"""
from __future__ import annotations
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    from sts2_sim.entities.creature import Creature


class CardType(Enum):
    """카드 타입."""
    ATTACK = auto()
    SKILL = auto()
    POWER = auto()
    CURSE = auto()
    STATUS = auto()


class Rarity(Enum):
    """카드 희귀도."""
    BASIC = auto()
    COMMON = auto()
    UNCOMMON = auto()
    RARE = auto()


class STS2Card:
    """STS2 카드 베이스 클래스."""
    card_id: str = "unknown_card"
    name: str = "Unknown Card"
    card_type: CardType = CardType.ATTACK
    rarity: Rarity = Rarity.BASIC
    cost: int = 0
    exhausts: bool = False

    def __init__(self):
        self.upgraded = False
        self.is_ethereal = False
        self.times_upgraded = 0

    def use(self, source: Creature, targets: List[Creature]) -> None:
        """카드 사용 (구현은 서브클래스)."""
        pass

    def upgrade(self) -> None:
        """업그레이드."""
        self.upgraded = True
        self.times_upgraded += 1

    def __repr__(self) -> str:
        cost_str = f"[{self.cost}]" if self.cost > 0 else ""
        return f"{self.name}{cost_str}"


# ══════════════════════════════════════════
# Ironclad 카드 예제
# ══════════════════════════════════════════

class Strike(STS2Card):
    """기본 공격."""
    card_id = "strike"
    name = "Strike"
    card_type = CardType.ATTACK
    rarity = Rarity.BASIC
    cost = 1

    def use(self, source: Creature, targets: List[Creature]) -> None:
        damage = 6 if self.upgraded else 5
        for target in targets:
            target.take_damage(damage, source=source)


class Defend(STS2Card):
    """기본 방어."""
    card_id = "defend"
    name = "Defend"
    card_type = CardType.SKILL
    rarity = Rarity.BASIC
    cost = 1

    def use(self, source: Creature, targets: List[Creature]) -> None:
        block = 8 if self.upgraded else 7
        source.gain_block(block)


class Bash(STS2Card):
    """강격."""
    card_id = "bash"
    name = "Bash"
    card_type = CardType.ATTACK
    rarity = Rarity.BASIC
    cost = 2

    def use(self, source: Creature, targets: List[Creature]) -> None:
        damage = 10 if self.upgraded else 8
        for target in targets:
            target.take_damage(damage, source=source)
            # TODO: Vulnerable 부여


class Cleave(STS2Card):
    """갈라지기."""
    card_id = "cleave"
    name = "Cleave"
    card_type = CardType.ATTACK
    rarity = Rarity.COMMON
    cost = 1

    def use(self, source: Creature, targets: List[Creature]) -> None:
        damage = 16 if self.upgraded else 14
        # 모든 적에게 피해
        for target in targets:
            target.take_damage(damage, source=source)


class HeavyBlade(STS2Card):
    """무거운 검."""
    card_id = "heavy_blade"
    name = "Heavy Blade"
    card_type = CardType.ATTACK
    rarity = Rarity.COMMON
    cost = 3

    def use(self, source: Creature, targets: List[Creature]) -> None:
        # 블록에 따라 데미지 변동
        base_damage = 32 if self.upgraded else 29
        # TODO: 블록 관계식 추가
        for target in targets:
            target.take_damage(base_damage, source=source)


class Pummel(STS2Card):
    """난타."""
    card_id = "pummel"
    name = "Pummel"
    card_type = CardType.ATTACK
    rarity = Rarity.COMMON
    cost = 1

    def use(self, source: Creature, targets: List[Creature]) -> None:
        damage = 4 if self.upgraded else 3
        times = 4 if self.upgraded else 4
        for target in targets:
            for _ in range(times):
                target.take_damage(damage, source=source)


# ══════════════════════════════════════════
# Silent 카드 예제
# ══════════════════════════════════════════

class Shiv(STS2Card):
    """단검."""
    card_id = "shiv"
    name = "Shiv"
    card_type = CardType.ATTACK
    rarity = Rarity.BASIC
    cost = 0
    exhausts = True

    def use(self, source: Creature, targets: List[Creature]) -> None:
        damage = 5 if self.upgraded else 4
        for target in targets:
            target.take_damage(damage, source=source)


class QuickSlash(STS2Card):
    """빠른 베기."""
    card_id = "quick_slash"
    name = "Quick Slash"
    card_type = CardType.ATTACK
    rarity = Rarity.COMMON
    cost = 1

    def use(self, source: Creature, targets: List[Creature]) -> None:
        damage = 16 if self.upgraded else 12
        for target in targets:
            target.take_damage(damage, source=source)


class Acrobatics(STS2Card):
    """곡예."""
    card_id = "acrobatics"
    name = "Acrobatics"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 1

    def use(self, source: Creature, targets: List[Creature]) -> None:
        # TODO: 카드 드로우
        block = 8 if self.upgraded else 7
        source.gain_block(block)


class Deflect(STS2Card):
    """방향 전환."""
    card_id = "deflect"
    name = "Deflect"
    card_type = CardType.SKILL
    rarity = Rarity.BASIC
    cost = 1

    def use(self, source: Creature, targets: List[Creature]) -> None:
        block = 4 if self.upgraded else 3
        source.gain_block(block)


# ══════════════════════════════════════════
# 카드 팩토리
# ══════════════════════════════════════════

CARD_REGISTRY = {
    # Ironclad Basic
    "strike": Strike,
    "defend": Defend,
    "bash": Bash,
    # Ironclad Common
    "cleave": Cleave,
    "heavy_blade": HeavyBlade,
    "pummel": Pummel,
    # Silent Basic
    "shiv": Shiv,
    # Silent Common
    "quick_slash": QuickSlash,
    "acrobatics": Acrobatics,
    "deflect": Deflect,
}


def create_card(card_id: str) -> Optional[STS2Card]:
    """카드 생성."""
    card_class = CARD_REGISTRY.get(card_id)
    if card_class:
        return card_class()
    return None
