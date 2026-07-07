"""
STS2 Character System — 캐릭터 정의 및 시작 덱.
"""
from __future__ import annotations
from enum import Enum, auto
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from sts2_sim.models.sts2_card import STS2Card


class CharacterClass(Enum):
    """캐릭터 클래스."""
    IRONCLAD = auto()
    SILENT = auto()
    DEFECT = auto()
    WATCHER = auto()


class STS2Character:
    """캐릭터 베이스 클래스."""
    character_class: CharacterClass = CharacterClass.IRONCLAD
    name: str = "Unknown"
    max_hp: int = 75
    start_gold: int = 99

    def __init__(self):
        self.deck: List[STS2Card] = []
        self.relics: List = []
        self.current_hp: int = self.max_hp
        self.gold: int = self.start_gold

    def get_start_deck(self) -> List[str]:
        """시작 덱 카드 ID 리스트 (서브클래스에서 오버라이드)."""
        return []

    def get_start_relics(self) -> List[str]:
        """시작 렐릭 ID 리스트."""
        return []

    def gain_max_hp(self, amount: int) -> None:
        """최대 HP 증가."""
        self.max_hp += amount
        self.current_hp = min(self.current_hp + amount, self.max_hp)

    def heal(self, amount: int) -> None:
        """HP 회복."""
        self.current_hp = min(self.current_hp + amount, self.max_hp)

    def gain_gold(self, amount: int) -> None:
        """골드 획득."""
        self.gold += amount

    def __repr__(self) -> str:
        return f"{self.name}(HP:{self.current_hp}/{self.max_hp}, Gold:{self.gold})"


# ══════════════════════════════════════════
# 캐릭터 구현
# ══════════════════════════════════════════

class Ironclad(STS2Character):
    """아이언클래드 — 무술가."""
    character_class = CharacterClass.IRONCLAD
    name = "Ironclad"
    max_hp = 80
    start_gold = 99

    def get_start_deck(self) -> List[str]:
        """기본 덱: Strike x5, Defend x4, Bash x1."""
        return ["strike"] * 5 + ["defend"] * 4 + ["bash"]

    def get_start_relics(self) -> List[str]:
        """스타터 렐릭: Burning Blood."""
        return ["burning_blood"]


class Silent(STS2Character):
    """사일런트 — 암살자."""
    character_class = CharacterClass.SILENT
    name = "Silent"
    max_hp = 70
    start_gold = 99

    def get_start_deck(self) -> List[str]:
        """기본 덱: Strike x5, Defend x4, Shiv x1."""
        return ["strike"] * 5 + ["defend"] * 4 + ["shiv"]

    def get_start_relics(self) -> List[str]:
        """스타터 렐릭: Ring of Snake."""
        return ["ring_of_snake"]


class Defect(STS2Character):
    """디펙트 — 로봇."""
    character_class = CharacterClass.DEFECT
    name = "Defect"
    max_hp = 75
    start_gold = 99

    def get_start_deck(self) -> List[str]:
        """기본 덱: Strike x5, Defend x4, Spark x1."""
        return ["strike"] * 5 + ["defend"] * 4 + ["spark"]

    def get_start_relics(self) -> List[str]:
        """스타터 렐릭: Courier."""
        return ["courier"]


class Watcher(STS2Character):
    """워처 — 명상가."""
    character_class = CharacterClass.WATCHER
    name = "Watcher"
    max_hp = 72
    start_gold = 99

    def get_start_deck(self) -> List[str]:
        """기본 덱: Strike x5, Defend x4, Eruption x1."""
        return ["strike"] * 5 + ["defend"] * 4 + ["eruption"]

    def get_start_relics(self) -> List[str]:
        """스타터 렐릭: Empty Cage."""
        return ["empty_cage"]


# ══════════════════════════════════════════
# 캐릭터 팩토리
# ══════════════════════════════════════════

CHARACTER_REGISTRY = {
    "ironclad": Ironclad,
    "silent": Silent,
    "defect": Defect,
    "watcher": Watcher,
}


def create_character(character_id: str) -> Optional[STS2Character]:
    """캐릭터 생성."""
    char_class = CHARACTER_REGISTRY.get(character_id)
    if char_class:
        return char_class()
    return None
