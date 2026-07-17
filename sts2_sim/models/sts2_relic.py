"""
STS2 Relic System — STS2 스타일 렐릭 구현.
"""
from __future__ import annotations
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    from sts2_sim.entities.creature import Creature


class RelicRarity(Enum):
    """렐릭 희귀도."""
    STARTER = auto()
    COMMON = auto()
    UNCOMMON = auto()
    RARE = auto()
    BOSS = auto()
    SHOP = auto()


class STS2Relic:
    """STS2 렐릭 베이스 클래스."""
    relic_id: str = "unknown_relic"
    name: str = "Unknown Relic"
    rarity: RelicRarity = RelicRarity.COMMON
    description: str = ""

    def __init__(self):
        self.owner: Optional[Creature] = None
        self.counter: int = 0

    def on_equip(self, owner: Creature) -> None:
        """렐릭 장착 시."""
        self.owner = owner

    def on_unequip(self) -> None:
        """렐릭 제거 시."""
        self.owner = None

    def on_combat_start(self, combat=None) -> None:
        """전투 시작 시."""
        pass

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        """플레이어 턴 시작 시."""
        pass

    def modify_hand_draw(self, count: int, turn: int = 1) -> int:
        """턴 시작 드로우 수 수정."""
        return count

    def on_combat_end(self, victory: bool) -> None:
        """전투 종료 시."""
        pass

    def on_card_played(self, card) -> None:
        """카드 플레이 시."""
        pass

    def on_card_upgraded(self, card) -> None:
        """카드 업그레이드 시."""
        pass

    def on_damage_taken(self, damage: int) -> None:
        """피해 입을 시."""
        pass

    def on_power_applied(self, power) -> None:
        """파워 적용 시."""
        pass

    def on_gold_gained(self, amount: int) -> None:
        """골드 획득 시."""
        pass

    def __repr__(self) -> str:
        return self.name


# ══════════════════════════════════════════
# 스타터 렐릭 (캐릭터별)
# ══════════════════════════════════════════

class BurningBlood(STS2Relic):
    """화염의 피 — Ironclad 스타터."""
    relic_id = "burning_blood"
    name = "Burning Blood"
    rarity = RelicRarity.STARTER
    description = "전투 종료 시 승리하면 6 HP 회복"

    def on_combat_end(self, victory: bool) -> None:
        """승리 시 6 HP 회복."""
        if victory and self.owner:
            self.owner.heal(6)


class RingOfTheSnake(STS2Relic):
    """뱀의 반지 — Silent 스타터. 첫 턴 드로우 +2 (디컴파일: ModifyHandDraw)."""
    relic_id = "ring_of_the_snake"
    name = "Ring of the Snake"
    rarity = RelicRarity.STARTER
    description = "전투 첫 턴에 카드 2장 추가 드로우"

    def modify_hand_draw(self, count: int, turn: int = 1) -> int:
        if turn <= 1:
            return count + 2
        return count


class CrackedCore(STS2Relic):
    """금간 코어 — Defect 스타터. 첫 턴에 라이트닝 오브 1개 채널."""
    relic_id = "cracked_core"
    name = "Cracked Core"
    rarity = RelicRarity.STARTER
    description = "전투 첫 턴에 라이트닝 오브 채널"

    def on_combat_start(self, combat=None) -> None:
        from sts2_sim.models.sts2_orb import LightningOrb
        if self.owner is None:
            return
        queue = getattr(self.owner, "orb_queue", None)
        if queue is not None:
            queue.channel(LightningOrb(), self.owner, combat)


class BoundPhylactery(STS2Relic):
    """묶인 성물함 — Necrobinder 스타터. 전투 시작 및 매 턴 Osty 1 소환."""
    relic_id = "bound_phylactery"
    name = "Bound Phylactery"
    rarity = RelicRarity.STARTER
    description = "전투 시작 시 및 2턴째부터 매 턴 Osty 1 소환"

    def _summon(self) -> None:
        summon = getattr(self.owner, "summon_osty", None) if self.owner else None
        if summon:
            summon(1)

    def on_combat_start(self, combat=None) -> None:
        self._summon()

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if turn > 1:
            self._summon()


class DivineRight(STS2Relic):
    """신성한 권리 — Regent 스타터. 전투 입장 시 별 3 획득."""
    relic_id = "divine_right"
    name = "Divine Right"
    rarity = RelicRarity.STARTER
    description = "전투 입장 시 Stars 3 획득"

    def on_combat_start(self, combat=None) -> None:
        gain = getattr(self.owner, "gain_stars", None) if self.owner else None
        if gain:
            gain(3)


# ══════════════════════════════════════════
# Common 렐릭
# ══════════════════════════════════════════

class Akabeko(STS2Relic):
    """아카베코."""
    relic_id = "akabeko"
    name = "Akabeko"
    rarity = RelicRarity.COMMON
    description = "공격 카드 플레이 시 1 데미지 증가"

    def on_card_played(self, card) -> None:
        """공격 카드 플레이 시."""
        if card and hasattr(card, 'card_type'):
            from sts2_sim.models.sts2_card import CardType
            if card.card_type == CardType.ATTACK and self.owner:
                # 다음 공격에 +1 데미지
                pass


class Anchor(STS2Relic):
    """닻."""
    relic_id = "anchor"
    name = "Anchor"
    rarity = RelicRarity.COMMON
    description = "최대 HP +10"

    def on_equip(self, owner: Creature) -> None:
        """장착 시 최대 HP 증가."""
        super().on_equip(owner)
        if owner:
            owner.gain_max_hp(10)


class BronzeScale(STS2Relic):
    """동 비늘."""
    relic_id = "bronze_scale"
    name = "Bronze Scale"
    rarity = RelicRarity.COMMON
    description = "상태 이상 피해 20% 감소"

    def on_damage_taken(self, damage: int) -> int:
        """상태 이상 피해 20% 감소."""
        # TODO: 상태 이상 판별
        return damage


class BurningSkull(STS2Relic):
    """타오르는 해골."""
    relic_id = "burning_skull"
    name = "Burning Skull"
    rarity = RelicRarity.COMMON
    description = "공격 후 적에게 1 화상 부여"

    def on_card_played(self, card) -> None:
        """공격 카드 플레이 후."""
        if card and hasattr(card, 'card_type'):
            from sts2_sim.models.sts2_card import CardType
            if card.card_type == CardType.ATTACK:
                # TODO: 적에게 Burning 부여
                pass


class Centipede(STS2Relic):
    """지네."""
    relic_id = "centipede"
    name = "Centipede"
    rarity = RelicRarity.COMMON
    description = "매 턴 시작 시 20 증가량 손실 시 1 블록 획득"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        """턴 시작 시."""
        # TODO: 턴 시작 HP 손실 감지
        pass


class Cloak(STS2Relic):
    """망토."""
    relic_id = "cloak"
    name = "Cloak"
    rarity = RelicRarity.COMMON
    description = "스킬 카드 플레이 시 1 블록 획득"

    def on_card_played(self, card) -> None:
        """스킬 카드 플레이 시."""
        if card and hasattr(card, 'card_type'):
            from sts2_sim.models.sts2_card import CardType
            if card.card_type == CardType.SKILL and self.owner:
                self.owner.gain_block(1, powered=False)


class Courier(STS2Relic):
    """배달원."""
    relic_id = "courier"
    name = "Courier"
    rarity = RelicRarity.COMMON
    description = "전투 승리 후 카드 1 획득"

    def on_combat_end(self, victory: bool) -> None:
        """전투 승리 후."""
        if victory:
            self.counter += 1


class DreamCatcher(STS2Relic):
    """드림 캐쳐."""
    relic_id = "dream_catcher"
    name = "Dream Catcher"
    rarity = RelicRarity.COMMON
    description = "카드 업그레이드 시 비용 1 감소"

    def on_card_upgraded(self, card) -> None:
        """카드 업그레이드 시."""
        if card and hasattr(card, 'cost'):
            card.cost = max(0, card.cost - 1)


class EnchanterMask(STS2Relic):
    """마법사 마스크."""
    relic_id = "enchanter_mask"
    name = "Enchanter's Mask"
    rarity = RelicRarity.COMMON
    description = "전투 시작 시 1 파워 생성"

    def on_combat_start(self, combat=None) -> None:
        """전투 시작 시."""
        self.counter += 1


# ══════════════════════════════════════════
# Uncommon 렐릭 (선별)
# ══════════════════════════════════════════

class FossilizedHelix(STS2Relic):
    """화석화된 나선."""
    relic_id = "fossilized_helix"
    name = "Fossilized Helix"
    rarity = RelicRarity.UNCOMMON
    description = "최대 HP +25"

    def on_equip(self, owner: Creature) -> None:
        """장착 시 최대 HP 증가."""
        super().on_equip(owner)
        if owner:
            owner.gain_max_hp(25)


class Matryoshka(STS2Relic):
    """마트료시카."""
    relic_id = "matryoshka"
    name = "Matryoshka"
    rarity = RelicRarity.UNCOMMON
    description = "카드 3개 획득 시 골드 9 획득"

    def on_card_reward(self, count: int) -> None:
        """카드 획득 시."""
        self.counter += count
        if self.counter >= 3 and self.owner:
            self.owner.gain_gold(9)
            self.counter = 0


class MercuryHourglass(STS2Relic):
    """수은 시계."""
    relic_id = "mercury_hourglass"
    name = "Mercury Hourglass"
    rarity = RelicRarity.UNCOMMON
    description = "전투 시작 시 턴 스킵"

    def on_combat_start(self, combat=None) -> None:
        """전투 시작 시 턴 스킵."""
        # TODO: 턴 스킵 로직
        self.counter += 1


class OddlySmoothStone(STS2Relic):
    """묘하게 부드러운 돌."""
    relic_id = "oddly_smooth_stone"
    name = "Oddly Smooth Stone"
    rarity = RelicRarity.UNCOMMON
    description = "상태 이상 저항 10%"

    def on_power_applied(self, power) -> None:
        """파워 적용 시."""
        # TODO: 확률 기반 거부
        pass


class Ornithopter(STS2Relic):
    """비행기."""
    relic_id = "ornithopter"
    name = "Ornithopter"
    rarity = RelicRarity.UNCOMMON
    description = "최대 블록 +1"

    # TODO: 블록 상한 증가


# ══════════════════════════════════════════
# Rare 렐릭 (선별)
# ══════════════════════════════════════════

class Runic(STS2Relic):
    """룬."""
    relic_id = "runic"
    name = "Runic"
    rarity = RelicRarity.RARE
    description = "카드 획득 시 모든 카드 업그레이드"

    def on_card_reward(self, cards: List) -> None:
        """카드 획득 시."""
        if cards:
            for card in cards:
                if card and hasattr(card, 'upgrade'):
                    card.upgrade()


class TungstenRod(STS2Relic):
    """텅스텐 봉."""
    relic_id = "tungsten_rod"
    name = "Tungsten Rod"
    rarity = RelicRarity.RARE
    description = "매 턴 시작 시 방어력 +3"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        """턴 시작 시."""
        if self.owner:
            self.owner.gain_block(3, powered=False)


# ══════════════════════════════════════════
# Boss 렐릭 (선별)
# ══════════════════════════════════════════

class SpikedDefense(STS2Relic):
    """가시 방어."""
    relic_id = "spiked_defense"
    name = "Spiked Defense"
    rarity = RelicRarity.BOSS
    description = "블록 획득 시 공격자에게 1 피해"

    # TODO: 반격 로직


# ══════════════════════════════════════════
# 렐릭 팩토리
# ══════════════════════════════════════════

RELIC_REGISTRY = {
    # Starter
    "burning_blood": BurningBlood,
    "ring_of_the_snake": RingOfTheSnake,
    "cracked_core": CrackedCore,
    "bound_phylactery": BoundPhylactery,
    "divine_right": DivineRight,
    # Common
    "akabeko": Akabeko,
    "anchor": Anchor,
    "bronze_scale": BronzeScale,
    "burning_skull": BurningSkull,
    "centipede": Centipede,
    "cloak": Cloak,
    "courier": Courier,
    "dream_catcher": DreamCatcher,
    "enchanter_mask": EnchanterMask,
    # Uncommon
    "fossilized_helix": FossilizedHelix,
    "matryoshka": Matryoshka,
    "mercury_hourglass": MercuryHourglass,
    "oddly_smooth_stone": OddlySmoothStone,
    "ornithopter": Ornithopter,
    # Rare
    "runic": Runic,
    "tungsten_rod": TungstenRod,
    # Boss
    "spiked_defense": SpikedDefense,
}


def create_relic(relic_id: str) -> Optional[STS2Relic]:
    """렐릭 생성."""
    relic_class = RELIC_REGISTRY.get(relic_id)
    if relic_class:
        return relic_class()
    return None
