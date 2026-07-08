"""
STS2 Card System — 디컴파일 MegaCrit.Sts2.Core.Models.Cards.* 이식.

모든 수치는 디컴파일 코드에서 추출한 실제값:
  Strike: 1코스트 6딜 (업글 +3)      | Defend: 1코스트 5블록 (업글 +3)
  Bash: 2코스트 8딜+취약2 (업글 +2/+1) | Shiv: 0코스트 4딜, 소모 (업글 +2)
  Deflect: 0코스트 4블록 (업글 +3)    | Acrobatics: 1코스트 3드로우+1버리기 (업글 +1)
  Neutralize: 0코스트 3딜+약화1       | Survivor: 1코스트 8블록+1버리기
  Zap: 1코스트 라이트닝 채널 (업글 0코스트)
  Dualcast: 1코스트 선두 오브 2회 이보크 (업글 0코스트)
  Bodyguard: 1코스트 Osty 5 소환 (업글 +2)
  Unleash: 1코스트 (6 + Osty HP)딜 (업글 +3)
  FallingStar: 0코스트/별 2 소모, 8딜+약화1+취약1 (업글 +4)
  Venerate: 1코스트 별 2 획득 (업글 +1)
"""
from __future__ import annotations
from enum import Enum, auto
from typing import TYPE_CHECKING, List, Optional

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
    TOKEN = auto()


def _deal_attack(source, target, base_damage: int) -> None:
    """공격 데미지 파이프라인: 공격자 수정(Strength/Weak) → 피격 처리."""
    calc = getattr(source, "compute_attack_damage", None)
    dmg = calc(base_damage) if calc else base_damage
    target.take_damage(dmg, source=source)


class STS2Card:
    """STS2 카드 베이스 클래스 (CardModel 대응)."""
    card_id: str = "unknown_card"
    name: str = "Unknown Card"
    card_type: CardType = CardType.ATTACK
    rarity: Rarity = Rarity.BASIC
    cost: int = 0
    star_cost: int = 0      # Regent 전용: 카드 플레이에 필요한 Stars
    exhausts: bool = False

    def __init__(self):
        self.upgraded = False
        self.is_ethereal = False
        self.times_upgraded = 0
        self.cost = type(self).cost  # 인스턴스별 비용 (업그레이드로 변동 가능)

    def use(self, source, targets: List["Creature"], combat=None) -> None:
        """카드 사용. combat은 전투 컨텍스트 (드로우/오브 등 필요 시)."""
        pass

    def upgrade(self) -> None:
        self.upgraded = True
        self.times_upgraded += 1

    def __repr__(self) -> str:
        plus = "+" if self.upgraded else ""
        return f"{self.name}{plus}[{self.cost}]"


# ══════════════════════════════════════════
# 공용 기본 카드 (캐릭터별 Strike/Defend 동일 수치)
# ══════════════════════════════════════════

class Strike(STS2Card):
    """타격 — 6딜 (업글 9)."""
    card_id = "strike"
    name = "Strike"
    card_type = CardType.ATTACK
    rarity = Rarity.BASIC
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        damage = 9 if self.upgraded else 6
        for target in targets:
            _deal_attack(source, target, damage)


class Defend(STS2Card):
    """수비 — 5블록 (업글 8)."""
    card_id = "defend"
    name = "Defend"
    card_type = CardType.SKILL
    rarity = Rarity.BASIC
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        block = 8 if self.upgraded else 5
        source.gain_block(block)


# ══════════════════════════════════════════
# Ironclad
# ══════════════════════════════════════════

class Bash(STS2Card):
    """강타 — 8딜 + 취약 2 (업글 10딜 + 취약 3)."""
    card_id = "bash"
    name = "Bash"
    card_type = CardType.ATTACK
    rarity = Rarity.BASIC
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Vulnerable
        damage = 10 if self.upgraded else 8
        vuln = 3 if self.upgraded else 2
        for target in targets:
            _deal_attack(source, target, damage)
            if hasattr(target, "apply_power"):
                target.apply_power(Vulnerable(vuln))


# ══════════════════════════════════════════
# Silent
# ══════════════════════════════════════════

class Neutralize(STS2Card):
    """무력화 — 0코스트 3딜 + 약화 1 (업글 4딜 + 약화 2)."""
    card_id = "neutralize"
    name = "Neutralize"
    card_type = CardType.ATTACK
    rarity = Rarity.BASIC
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Weak
        damage = 4 if self.upgraded else 3
        weak = 2 if self.upgraded else 1
        for target in targets:
            _deal_attack(source, target, damage)
            if hasattr(target, "apply_power"):
                target.apply_power(Weak(weak))


class Survivor(STS2Card):
    """생존자 — 8블록 + 카드 1 버리기 (업글 11블록)."""
    card_id = "survivor"
    name = "Survivor"
    card_type = CardType.SKILL
    rarity = Rarity.BASIC
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        block = 11 if self.upgraded else 8
        source.gain_block(block)
        if combat and hasattr(combat, "discard_from_hand"):
            combat.discard_from_hand(1)


class Shiv(STS2Card):
    """단검 — 0코스트 4딜, 소모 (업글 6딜). Token 카드."""
    card_id = "shiv"
    name = "Shiv"
    card_type = CardType.ATTACK
    rarity = Rarity.TOKEN
    cost = 0
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        damage = 6 if self.upgraded else 4
        for target in targets:
            _deal_attack(source, target, damage)


class Acrobatics(STS2Card):
    """곡예 — 3드로우 + 1버리기 (업글 4드로우). STS2에서 Uncommon."""
    card_id = "acrobatics"
    name = "Acrobatics"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        draw = 4 if self.upgraded else 3
        if combat:
            if hasattr(combat, "draw_cards"):
                combat.draw_cards(draw)
            if hasattr(combat, "discard_from_hand"):
                combat.discard_from_hand(1)


class Deflect(STS2Card):
    """방향 전환 — 0코스트 4블록 (업글 7)."""
    card_id = "deflect"
    name = "Deflect"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        block = 7 if self.upgraded else 4
        source.gain_block(block)


# ══════════════════════════════════════════
# Defect (Orb)
# ══════════════════════════════════════════

class Zap(STS2Card):
    """전격 — 라이트닝 오브 채널 (업글 0코스트)."""
    card_id = "zap"
    name = "Zap"
    card_type = CardType.SKILL
    rarity = Rarity.BASIC
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import LightningOrb
        queue = getattr(source, "orb_queue", None)
        if queue is not None:
            queue.channel(LightningOrb(), source, combat)

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)


class Dualcast(STS2Card):
    """이중 시전 — 선두 오브를 2회 이보크 (업글 0코스트)."""
    card_id = "dualcast"
    name = "Dualcast"
    card_type = CardType.SKILL
    rarity = Rarity.BASIC
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        queue = getattr(source, "orb_queue", None)
        if queue is not None and len(queue) > 0:
            queue.evoke_next(combat, dequeue=False)
            queue.evoke_next(combat, dequeue=True)

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)


# ══════════════════════════════════════════
# Necrobinder (Osty)
# ══════════════════════════════════════════

class Bodyguard(STS2Card):
    """경호원 — Osty 5 소환 (업글 +2)."""
    card_id = "bodyguard"
    name = "Bodyguard"
    card_type = CardType.SKILL
    rarity = Rarity.BASIC
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        amount = 7 if self.upgraded else 5
        summon = getattr(source, "summon_osty", None)
        if summon:
            summon(amount)


class Unleash(STS2Card):
    """해방 — Osty가 (6 + Osty 현재 HP)만큼 공격 (업글 기본 +3)."""
    card_id = "unleash"
    name = "Unleash"
    card_type = CardType.ATTACK
    rarity = Rarity.BASIC
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        base = 9 if self.upgraded else 6
        osty = getattr(source, "osty", None)
        osty_hp = osty.current_hp if (osty and osty.is_alive) else 0
        damage = base + osty_hp
        attacker = osty if (osty and osty.is_alive) else source
        for target in targets:
            _deal_attack(attacker, target, damage)


# ══════════════════════════════════════════
# Regent (Stars)
# ══════════════════════════════════════════

class FallingStar(STS2Card):
    """유성 — 0코스트/별 2 소모, 8딜 + 약화 1 + 취약 1 (업글 12딜)."""
    card_id = "falling_star"
    name = "Falling Star"
    card_type = CardType.ATTACK
    rarity = Rarity.BASIC
    cost = 0
    star_cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Weak, Vulnerable
        damage = 12 if self.upgraded else 8
        for target in targets:
            _deal_attack(source, target, damage)
            if hasattr(target, "apply_power"):
                target.apply_power(Weak(1))
                target.apply_power(Vulnerable(1))


class Venerate(STS2Card):
    """숭배 — 별 2 획득 (업글 +1)."""
    card_id = "venerate"
    name = "Venerate"
    card_type = CardType.SKILL
    rarity = Rarity.BASIC
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        stars = 3 if self.upgraded else 2
        gain = getattr(source, "gain_stars", None)
        if gain:
            gain(stars)


# ══════════════════════════════════════════
# 카드 팩토리
# ══════════════════════════════════════════

CARD_REGISTRY = {
    # 공용 Basic
    "strike": Strike,
    "defend": Defend,
    # Ironclad
    "bash": Bash,
    # Silent
    "neutralize": Neutralize,
    "survivor": Survivor,
    "shiv": Shiv,
    "acrobatics": Acrobatics,
    "deflect": Deflect,
    # Defect
    "zap": Zap,
    "dualcast": Dualcast,
    # Necrobinder
    "bodyguard": Bodyguard,
    "unleash": Unleash,
    # Regent
    "falling_star": FallingStar,
    "venerate": Venerate,
}


def create_card(card_id: str) -> Optional[STS2Card]:
    """카드 생성."""
    card_class = CARD_REGISTRY.get(card_id)
    return card_class() if card_class else None
