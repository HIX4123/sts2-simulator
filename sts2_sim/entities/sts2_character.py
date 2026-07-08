"""
STS2 Character System — 캐릭터 정의 및 시작 덱.
디컴파일 MegaCrit.Sts2.Core.Models.Characters.* 이식.

실제 STS2 플레이어블 로스터 (디컴파일 확인):
  Ironclad → Silent → Defect → Necrobinder → Regent
  (Watcher는 STS2에 존재하지 않음. Deprived는 IsPlayable=false 내부용.)
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
    NECROBINDER = auto()
    REGENT = auto()


class STS2Character:
    """캐릭터 베이스 클래스 (CharacterModel 대응)."""
    character_class: CharacterClass = CharacterClass.IRONCLAD
    name: str = "Unknown"
    max_hp: int = 75          # StartingHp
    start_gold: int = 99      # StartingGold
    max_energy: int = 3       # MaxEnergy (기본 3)
    base_orb_slot_count: int = 0  # Defect만 3

    def __init__(self):
        self.deck: List["STS2Card"] = []
        self.relics: List = []
        self.current_hp: int = self.max_hp
        self.gold: int = self.start_gold

    def get_start_deck(self) -> List[str]:
        """시작 덱 카드 ID 리스트."""
        return []

    def get_start_relics(self) -> List[str]:
        """시작 렐릭 ID 리스트."""
        return []

    def gain_max_hp(self, amount: int) -> None:
        self.max_hp += amount
        self.current_hp = min(self.current_hp + amount, self.max_hp)

    def heal(self, amount: int) -> None:
        self.current_hp = min(self.current_hp + amount, self.max_hp)

    def gain_gold(self, amount: int) -> None:
        self.gold += amount

    def __repr__(self) -> str:
        return f"{self.name}(HP:{self.current_hp}/{self.max_hp}, Gold:{self.gold})"


# ══════════════════════════════════════════
# 캐릭터 구현 (디컴파일 데이터 그대로)
# ══════════════════════════════════════════

class Ironclad(STS2Character):
    """아이언클래드 — StartingHp 80."""
    character_class = CharacterClass.IRONCLAD
    name = "Ironclad"
    max_hp = 80

    def get_start_deck(self) -> List[str]:
        """Strike×5, Defend×4, Bash."""
        return ["strike"] * 5 + ["defend"] * 4 + ["bash"]

    def get_start_relics(self) -> List[str]:
        return ["burning_blood"]


class Silent(STS2Character):
    """사일런트 — StartingHp 70, 12장 덱."""
    character_class = CharacterClass.SILENT
    name = "Silent"
    max_hp = 70

    def get_start_deck(self) -> List[str]:
        """Strike×5, Defend×5, Neutralize, Survivor (12장)."""
        return ["strike"] * 5 + ["defend"] * 5 + ["neutralize", "survivor"]

    def get_start_relics(self) -> List[str]:
        return ["ring_of_the_snake"]


class Defect(STS2Character):
    """디펙트 — StartingHp 75, 오브 슬롯 3."""
    character_class = CharacterClass.DEFECT
    name = "Defect"
    max_hp = 75
    base_orb_slot_count = 3

    def get_start_deck(self) -> List[str]:
        """Strike×4, Defend×4, Zap, Dualcast."""
        return ["strike"] * 4 + ["defend"] * 4 + ["zap", "dualcast"]

    def get_start_relics(self) -> List[str]:
        return ["cracked_core"]


class Necrobinder(STS2Character):
    """네크로바인더 (STS2 신규) — StartingHp 66, Osty 소환수."""
    character_class = CharacterClass.NECROBINDER
    name = "Necrobinder"
    max_hp = 66

    def get_start_deck(self) -> List[str]:
        """Strike×4, Defend×4, Bodyguard, Unleash."""
        return ["strike"] * 4 + ["defend"] * 4 + ["bodyguard", "unleash"]

    def get_start_relics(self) -> List[str]:
        return ["bound_phylactery"]


class Regent(STS2Character):
    """리전트 (STS2 신규) — StartingHp 75, Stars 자원."""
    character_class = CharacterClass.REGENT
    name = "Regent"
    max_hp = 75

    def get_start_deck(self) -> List[str]:
        """Strike×4, Defend×4, FallingStar, Venerate."""
        return ["strike"] * 4 + ["defend"] * 4 + ["falling_star", "venerate"]

    def get_start_relics(self) -> List[str]:
        return ["divine_right"]


# ══════════════════════════════════════════
# 캐릭터 팩토리
# ══════════════════════════════════════════

CHARACTER_REGISTRY = {
    "ironclad": Ironclad,
    "silent": Silent,
    "defect": Defect,
    "necrobinder": Necrobinder,
    "regent": Regent,
}


def create_character(character_id: str) -> Optional[STS2Character]:
    """캐릭터 생성."""
    char_class = CHARACTER_REGISTRY.get(character_id)
    return char_class() if char_class else None
