"""
STS2 Relic System — 디컴파일 원본 기반 렐릭 구현.
"""
from __future__ import annotations
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from sts2_sim.core.combat import CombatState
    from sts2_sim.entities.creature import Creature


class RelicRarity(Enum):
    """렐릭 희귀도."""
    STARTER = auto()
    COMMON = auto()
    UNCOMMON = auto()
    RARE = auto()
    SHOP = auto()
    ANCIENT = auto()
    EVENT = auto()


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

    def modify_hp_lost(self, amount: int) -> int:
        """소유자의 HP 손실량 수정."""
        return amount

    def on_combat_end(self, victory: bool) -> None:
        """전투 종료 시."""
        pass

    def on_card_played(self, card, combat: "CombatState" | None = None) -> None:
        """카드 플레이 시."""
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
        if victory and self.owner:
            self.owner.heal(6)


class RingOfTheSnake(STS2Relic):
    """뱀의 반지 — Silent 스타터."""
    relic_id = "ring_of_the_snake"
    name = "Ring of the Snake"
    rarity = RelicRarity.STARTER
    description = "전투 첫 턴에 카드 2장 추가 드로우"

    def modify_hand_draw(self, count: int, turn: int = 1) -> int:
        if turn <= 1:
            return count + 2
        return count


class CrackedCore(STS2Relic):
    """금간 코어 — Defect 스타터."""
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
    """묶인 성물함 — Necrobinder 스타터."""
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
    """신성한 권리 — Regent 스타터."""
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

class Anchor(STS2Relic):
    """닻 — 전투 시작 시 언파워드 블록 10."""
    relic_id = "anchor"
    name = "Anchor"
    rarity = RelicRarity.COMMON
    description = "전투 시작 시 블록 10 획득"

    def on_combat_start(self, combat=None) -> None:
        if self.owner:
            self.owner.gain_block(10, powered=False)


class BagOfPreparation(STS2Relic):
    """준비 가방 — 첫 턴 드로우 +2."""
    relic_id = "bag_of_preparation"
    name = "Bag of Preparation"
    rarity = RelicRarity.COMMON
    description = "전투 첫 턴에 카드 2장 추가 드로우"

    def modify_hand_draw(self, count: int, turn: int = 1) -> int:
        if turn <= 1:
            return count + 2
        return count


class BagOfMarbles(STS2Relic):
    """구슬 주머니 — 첫 턴에 모든 적에게 Vulnerable 1."""
    relic_id = "bag_of_marbles"
    name = "Bag of Marbles"
    rarity = RelicRarity.COMMON
    description = "전투 첫 턴에 모든 적에게 취약 1 부여"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if turn > 1 or combat is None or self.owner is None:
            return
        from sts2_sim.models.sts2_power import Vulnerable
        for enemy in list(combat.alive_enemies):
            enemy.apply_power(Vulnerable(1), applier=self.owner)


class BloodVial(STS2Relic):
    """피가 담긴 병 — 첫 턴 시작 시 HP 2 회복."""
    relic_id = "blood_vial"
    name = "Blood Vial"
    rarity = RelicRarity.COMMON
    description = "전투 첫 턴 시작 시 HP 2 회복"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if turn <= 1 and self.owner:
            self.owner.heal(2)


class BronzeScales(STS2Relic):
    """청동 비늘 — 전투 시작 시 Thorns 3."""
    relic_id = "bronze_scales"
    name = "Bronze Scales"
    rarity = RelicRarity.COMMON
    description = "전투 시작 시 가시 3 획득"

    def on_combat_start(self, combat=None) -> None:
        from sts2_sim.models.sts2_power import Thorns
        if self.owner:
            self.owner.apply_power(Thorns(3), applier=self.owner)


class DataDisk(STS2Relic):
    """데이터 디스크 — 전투 시작 시 Focus 1."""
    relic_id = "data_disk"
    name = "Data Disk"
    rarity = RelicRarity.COMMON
    description = "전투 시작 시 집중 1 획득"

    def on_combat_start(self, combat=None) -> None:
        if self.owner:
            from sts2_sim.models.sts2_power import Focus
            self.owner.apply_power(Focus(1), applier=self.owner)


class FestivePopper(STS2Relic):
    """축제 폭죽 — 첫 턴에 모든 적에게 언파워드 피해 9."""
    relic_id = "festive_popper"
    name = "Festive Popper"
    rarity = RelicRarity.COMMON
    description = "전투 첫 턴에 모든 적에게 피해 9"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if turn > 1 or combat is None or self.owner is None:
            return
        for enemy in list(combat.alive_enemies):
            enemy.take_damage(9, source=self.owner, powered=False)


class Gorget(STS2Relic):
    """고르겟 — 전투 시작 시 Plating 4."""
    relic_id = "gorget"
    name = "Gorget"
    rarity = RelicRarity.COMMON
    description = "전투 시작 시 도금 4 획득"

    def on_combat_start(self, combat=None) -> None:
        from sts2_sim.models.sts2_power import Plating
        if self.owner:
            self.owner.apply_power(Plating(4), applier=self.owner)


class Lantern(STS2Relic):
    """랜턴 — 첫 턴 에너지 +1."""
    relic_id = "lantern"
    name = "Lantern"
    rarity = RelicRarity.COMMON
    description = "전투 첫 턴에 에너지 1 획득"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if turn <= 1 and self.owner:
            gain = getattr(self.owner, "gain_energy", None)
            if gain:
                gain(1)


class OddlySmoothStone(STS2Relic):
    """묘하게 부드러운 돌 — 전투 시작 시 Dexterity 1."""
    relic_id = "oddly_smooth_stone"
    name = "Oddly Smooth Stone"
    rarity = RelicRarity.COMMON
    description = "전투 시작 시 민첩성 1 획득"

    def on_combat_start(self, combat=None) -> None:
        from sts2_sim.models.sts2_power import Dexterity
        if self.owner:
            self.owner.apply_power(Dexterity(1), applier=self.owner)


class RedMask(STS2Relic):
    """붉은 가면 — 첫 턴에 모든 적에게 Weak 1."""
    relic_id = "red_mask"
    name = "Red Mask"
    rarity = RelicRarity.COMMON
    description = "전투 첫 턴에 모든 적에게 약화 1 부여"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if turn > 1 or combat is None or self.owner is None:
            return
        from sts2_sim.models.sts2_power import Weak
        for enemy in list(combat.alive_enemies):
            enemy.apply_power(Weak(1), applier=self.owner)


class Vajra(STS2Relic):
    """금강저 — 전투 시작 시 Strength 1."""
    relic_id = "vajra"
    name = "Vajra"
    rarity = RelicRarity.COMMON
    description = "전투 시작 시 힘 1 획득"

    def on_combat_start(self, combat=None) -> None:
        from sts2_sim.models.sts2_power import Strength
        if self.owner:
            self.owner.apply_power(Strength(1), applier=self.owner)


# ══════════════════════════════════════════
# Uncommon 렐릭
# ══════════════════════════════════════════

class Candelabra(STS2Relic):
    """촛대 — 정확히 2턴째에 에너지 2."""
    relic_id = "candelabra"
    name = "Candelabra"
    rarity = RelicRarity.UNCOMMON
    description = "전투 2턴째에 에너지 2 획득"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if turn == 2 and self.owner:
            gain = getattr(self.owner, "gain_energy", None)
            if gain:
                gain(2)


class Akabeko(STS2Relic):
    """아카베코 — 첫 턴 시작 시 Vigor 8."""
    relic_id = "akabeko"
    name = "Akabeko"
    rarity = RelicRarity.UNCOMMON
    description = "전투 첫 턴에 기세 8 획득"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        from sts2_sim.models.sts2_power import Vigor
        if turn <= 1 and self.owner:
            self.owner.apply_power(Vigor(8), applier=self.owner)


class LetterOpener(STS2Relic):
    """편지 개봉기 — 한 턴에 스킬 3장마다 모든 적에게 언파워드 피해 5."""
    relic_id = "letter_opener"
    name = "Letter Opener"
    rarity = RelicRarity.UNCOMMON
    description = "한 턴에 스킬을 3장 사용할 때마다 모든 적에게 피해 5"

    def on_combat_start(self, combat=None) -> None:
        self.counter = 0

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if turn > 1:
            self.counter = 0

    def on_card_played(self, card, combat=None) -> None:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type != CardType.SKILL:
            return
        self.counter += 1
        if self.counter % 3 == 0 and combat is not None and self.owner is not None:
            for enemy in list(combat.alive_enemies):
                enemy.take_damage(5, source=self.owner, powered=False)

    def on_combat_end(self, victory: bool) -> None:
        self.counter = 0


class OrnamentalFan(STS2Relic):
    """장식용 부채 — 한 턴에 공격 3장마다 언파워드 블록 4."""
    relic_id = "ornamental_fan"
    name = "Ornamental Fan"
    rarity = RelicRarity.UNCOMMON
    description = "한 턴에 공격을 3장 사용할 때마다 블록 4 획득"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        self.counter = 0

    def on_card_played(self, card, combat=None) -> None:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type != CardType.ATTACK:
            return
        self.counter += 1
        if self.counter % 3 == 0 and self.owner:
            self.owner.gain_block(4, powered=False)

    def on_combat_end(self, victory: bool) -> None:
        self.counter = 0


class SymbioticVirus(STS2Relic):
    """공생 바이러스 — 첫 턴에 Dark 오브 1개 채널."""
    relic_id = "symbiotic_virus"
    name = "Symbiotic Virus"
    rarity = RelicRarity.UNCOMMON
    description = "전투 첫 턴에 어둠 오브 1개 채널"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if turn > 1 or self.owner is None:
            return
        queue = getattr(self.owner, "orb_queue", None)
        if queue is not None:
            from sts2_sim.models.sts2_orb import DarkOrb
            queue.channel(DarkOrb(), self.owner, combat)


class TwistedFunnel(STS2Relic):
    """뒤틀린 깔때기 — 첫 턴에 모든 적에게 Poison 4."""
    relic_id = "twisted_funnel"
    name = "Twisted Funnel"
    rarity = RelicRarity.UNCOMMON
    description = "전투 첫 턴에 모든 적에게 중독 4 부여"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if turn > 1 or combat is None or self.owner is None:
            return
        from sts2_sim.models.sts2_power import Poison
        for enemy in list(combat.alive_enemies):
            enemy.apply_power(Poison(4), applier=self.owner)


class MercuryHourglass(STS2Relic):
    """수은 모래시계 — 매 턴 시작 시 모든 적에게 언파워드 피해 3."""
    relic_id = "mercury_hourglass"
    name = "Mercury Hourglass"
    rarity = RelicRarity.UNCOMMON
    description = "매 턴 시작 시 모든 적에게 피해 3"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if combat is None or self.owner is None:
            return
        for enemy in list(combat.alive_enemies):
            enemy.take_damage(3, source=self.owner, powered=False)


# ══════════════════════════════════════════
# Rare 렐릭
# ══════════════════════════════════════════

class Brimstone(STS2Relic):
    """유황석 — 매 턴 시작 시 Strength 2(자신) + 1(모든 적)."""
    relic_id = "brimstone"
    name = "Brimstone"
    rarity = RelicRarity.SHOP
    description = "매 턴 시작 시 힘 2 획득, 모든 적은 힘 1 획득"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if self.owner is None or combat is None:
            return
        from sts2_sim.models.sts2_power import Strength
        self.owner.apply_power(Strength(2), applier=self.owner)
        for enemy in list(combat.alive_enemies):
            enemy.apply_power(Strength(1))


class Chandelier(STS2Relic):
    """샹들리에 — 정확히 3턴째에 에너지 3."""
    relic_id = "chandelier"
    name = "Chandelier"
    rarity = RelicRarity.RARE
    description = "전투 3턴째에 에너지 3 획득"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if turn == 3 and self.owner:
            gain = getattr(self.owner, "gain_energy", None)
            if gain:
                gain(3)


class Kunai(STS2Relic):
    """쿠나이 — 한 턴에 공격 3장마다 Dexterity 1."""
    relic_id = "kunai"
    name = "Kunai"
    rarity = RelicRarity.RARE
    description = "한 턴에 공격을 3장 사용할 때마다 민첩성 1 획득"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        self.counter = 0

    def on_card_played(self, card, combat=None) -> None:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type != CardType.ATTACK:
            return
        self.counter += 1
        if self.counter % 3 == 0 and self.owner:
            from sts2_sim.models.sts2_power import Dexterity
            self.owner.apply_power(Dexterity(1), applier=self.owner)

    def on_combat_end(self, victory: bool) -> None:
        self.counter = 0


class RainbowRing(STS2Relic):
    """무지개 반지 — 한 턴에 공/스킬/파워 각 1회 이상 플레이 시 Str1+Dex1 (턴당 1회)."""
    relic_id = "rainbow_ring"
    name = "Rainbow Ring"
    rarity = RelicRarity.RARE
    description = "한 턴에 공격·스킬·파워를 각각 1회 이상 플레이하면 힘과 민첩성 1 획득 (턴당 1회)"

    def __init__(self):
        super().__init__()
        self._attack_played = False
        self._skill_played = False
        self._power_played = False
        self._activated_this_turn = False

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        self._attack_played = False
        self._skill_played = False
        self._power_played = False
        self._activated_this_turn = False

    def on_card_played(self, card, combat=None) -> None:
        from sts2_sim.models.sts2_card import CardType
        if self._activated_this_turn or self.owner is None:
            return
        if card.card_type == CardType.ATTACK:
            self._attack_played = True
        elif card.card_type == CardType.SKILL:
            self._skill_played = True
        elif card.card_type == CardType.POWER:
            self._power_played = True
        if self._attack_played and self._skill_played and self._power_played:
            from sts2_sim.models.sts2_power import Strength, Dexterity
            self.owner.apply_power(Strength(1), applier=self.owner)
            self.owner.apply_power(Dexterity(1), applier=self.owner)
            self._activated_this_turn = True

    def on_combat_end(self, victory: bool) -> None:
        self._attack_played = False
        self._skill_played = False
        self._power_played = False
        self._activated_this_turn = False


class RunicCapacitor(STS2Relic):
    """룬 축전기 — 첫 턴에 오브 슬롯 3 추가."""
    relic_id = "runic_capacitor"
    name = "Runic Capacitor"
    rarity = RelicRarity.SHOP
    description = "전투 첫 턴에 오브 슬롯 3 추가"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if turn > 1 or self.owner is None:
            return
        queue = getattr(self.owner, "orb_queue", None)
        if queue is not None:
            queue.gain_slots(3)


class Shuriken(STS2Relic):
    """수리검 — 한 턴에 공격 3장마다 Strength 1."""
    relic_id = "shuriken"
    name = "Shuriken"
    rarity = RelicRarity.RARE
    description = "한 턴에 공격을 3장 사용할 때마다 힘 1 획득"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        self.counter = 0

    def on_card_played(self, card, combat=None) -> None:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type != CardType.ATTACK:
            return
        self.counter += 1
        if self.counter % 3 == 0 and self.owner:
            from sts2_sim.models.sts2_power import Strength
            self.owner.apply_power(Strength(1), applier=self.owner)

    def on_combat_end(self, victory: bool) -> None:
        self.counter = 0


class TungstenRod(STS2Relic):
    """텅스텐 봉 — HP 손실량 1 감소."""
    relic_id = "tungsten_rod"
    name = "Tungsten Rod"
    rarity = RelicRarity.RARE
    description = "HP를 잃을 때마다 손실량 1 감소"

    def modify_hp_lost(self, amount: int) -> int:
        return max(0, amount - 1)


# ══════════════════════════════════════════
# Ancient 렐릭
# ══════════════════════════════════════════

class Sai(STS2Relic):
    """인 — 매 턴 블록 7."""
    relic_id = "sai"
    name = "Sai"
    rarity = RelicRarity.ANCIENT
    description = "매 턴 시작 시 블록 7 획득"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if self.owner:
            self.owner.gain_block(7, powered=False)


class VeryHotCocoa(STS2Relic):
    """매우 뜨거운 코코아 — 첫 턴 에너지 +4."""
    relic_id = "very_hot_cocoa"
    name = "Very Hot Cocoa"
    rarity = RelicRarity.ANCIENT
    description = "전투 첫 턴에 에너지 4 획득"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if turn <= 1 and self.owner:
            gain = getattr(self.owner, "gain_energy", None)
            if gain:
                gain(4)


class IronClub(STS2Relic):
    """철클럽 — 카드 4장마다 드로우 +1."""
    relic_id = "iron_club"
    name = "Iron Club"
    rarity = RelicRarity.ANCIENT
    description = "카드를 4장 플레이할 때마다 카드 1장 드로우"

    def on_combat_start(self, combat=None) -> None:
        self.counter = 0

    def on_card_played(self, card, combat=None) -> None:
        self.counter += 1
        if self.counter % 4 == 0 and combat is not None:
            combat.draw_cards(1)

    def on_combat_end(self, victory: bool) -> None:
        self.counter = 0


# ══════════════════════════════════════════
# Event 렐릭
# ══════════════════════════════════════════

class MrStruggles(STS2Relic):
    """미스터 스트러글스 — 매 턴 모든 적에게 현재 턴 수만큼 피해."""
    relic_id = "mr_struggles"
    name = "Mr. Struggles"
    rarity = RelicRarity.EVENT
    description = "매 턴 시작 시 모든 적에게 현재 턴 번호만큼 피해"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if combat is None or self.owner is None:
            return
        for enemy in list(combat.alive_enemies):
            enemy.take_damage(turn, source=self.owner, powered=False)


class RoyalPoison(STS2Relic):
    """왕실 독약 — 첫 턴에 자기 4피해 (하향 렐릭)."""
    relic_id = "royal_poison"
    name = "Royal Poison"
    rarity = RelicRarity.EVENT
    description = "전투 첫 턴에 자기에게 4 피해"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if turn <= 1 and self.owner is not None:
            self.owner.take_damage(4, source=self.owner, powered=False)


class LostWisp(STS2Relic):
    """잃어버린 위스프 — 파워 카드 사용 시 모든 적에게 8 피해."""
    relic_id = "lost_wisp"
    name = "Lost Wisp"
    rarity = RelicRarity.EVENT
    description = "파워 카드를 사용할 때마다 모든 적에게 피해 8"

    def on_card_played(self, card, combat=None) -> None:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type != CardType.POWER:
            return
        if combat is None or self.owner is None:
            return
        for enemy in list(combat.alive_enemies):
            enemy.take_damage(8, source=self.owner, powered=False)


# ══════════════════════════════════════════
# Common 렐릭 (추가)
# ══════════════════════════════════════════

class HappyFlower(STS2Relic):
    """행복한 꽃 — 3턴마다 에너지 +1."""
    relic_id = "happy_flower"
    name = "Happy Flower"
    rarity = RelicRarity.COMMON
    description = "3턴마다 에너지 1 획득"

    def on_combat_start(self, combat=None) -> None:
        self.counter = 0

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        self.counter += 1
        if self.counter % 3 == 0 and self.owner:
            gain = getattr(self.owner, "gain_energy", None)
            if gain:
                gain(1)

    def on_combat_end(self, victory: bool) -> None:
        self.counter = 0


class Pendulum(STS2Relic):
    """진자 — 3턴마다 드로우 +1."""
    relic_id = "pendulum"
    name = "Pendulum"
    rarity = RelicRarity.COMMON
    description = "3턴마다 카드 1장 드로우"

    def on_combat_start(self, combat=None) -> None:
        self.counter = 0

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        self.counter += 1
        if self.counter % 3 == 0 and combat is not None:
            combat.draw_cards(1)

    def on_combat_end(self, victory: bool) -> None:
        self.counter = 0


# ══════════════════════════════════════════
# Uncommon 렐릭 (추가)
# ══════════════════════════════════════════

class HornCleat(STS2Relic):
    """뿔 클릿 — 턴2에 블록 14."""
    relic_id = "horn_cleat"
    name = "Horn Cleat"
    rarity = RelicRarity.UNCOMMON
    description = "전투 2턴째에 블록 14 획득"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if turn == 2 and self.owner:
            self.owner.gain_block(14, powered=False)


class Nunchaku(STS2Relic):
    """쌍절곤 — 공격 10장마다 에너지 +1."""
    relic_id = "nunchaku"
    name = "Nunchaku"
    rarity = RelicRarity.UNCOMMON
    description = "공격을 10장 사용할 때마다 에너지 1 획득"

    def on_combat_start(self, combat=None) -> None:
        self.counter = 0

    def on_card_played(self, card, combat=None) -> None:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type != CardType.ATTACK:
            return
        self.counter += 1
        if self.counter % 10 == 0 and self.owner:
            gain = getattr(self.owner, "gain_energy", None)
            if gain:
                gain(1)

    def on_combat_end(self, victory: bool) -> None:
        self.counter = 0


class TuningFork(STS2Relic):
    """튜닝 포크 — 스킬 10장마다 블록 7."""
    relic_id = "tuning_fork"
    name = "Tuning Fork"
    rarity = RelicRarity.UNCOMMON
    description = "스킬을 10장 사용할 때마다 블록 7 획득"

    def on_combat_start(self, combat=None) -> None:
        self.counter = 0

    def on_card_played(self, card, combat=None) -> None:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type != CardType.SKILL:
            return
        self.counter += 1
        if self.counter % 10 == 0 and self.owner:
            self.owner.gain_block(7, powered=False)

    def on_combat_end(self, victory: bool) -> None:
        self.counter = 0


class Kusarigama(STS2Relic):
    """쇠사슬낫 — 턴 중 공격 3장마다 무작위 적에게 6 피해."""
    relic_id = "kusarigama"
    name = "Kusarigama"
    rarity = RelicRarity.UNCOMMON
    description = "한 턴에 공격을 3장 사용할 때마다 무작위 적에게 피해 6"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        self.counter = 0

    def on_card_played(self, card, combat=None) -> None:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type != CardType.ATTACK:
            return
        self.counter += 1
        if self.counter % 3 == 0 and combat is not None and self.owner is not None:
            enemies = list(combat.alive_enemies)
            if enemies:
                combat.rng.choice(enemies).take_damage(6, source=self.owner, powered=False)

    def on_combat_end(self, victory: bool) -> None:
        self.counter = 0


class Permafrost(STS2Relic):
    """영구동토 — 전투당 처음 사용한 파워 카드로 블록 7."""
    relic_id = "permafrost"
    name = "Permafrost"
    rarity = RelicRarity.UNCOMMON
    description = "전투당 처음 파워 카드를 사용하면 블록 7 획득"

    def on_combat_start(self, combat=None) -> None:
        self._activated = False

    def on_card_played(self, card, combat=None) -> None:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type == CardType.POWER and not self._activated and self.owner:
            self.owner.gain_block(7, powered=False)
            self._activated = True


class StoneCracker(STS2Relic):
    """돌 분쇄기 — 전투 시작 시 뽑을 더미의 카드 2장을 무작위 업그레이드."""
    relic_id = "stone_cracker"
    name = "Stone Cracker"
    rarity = RelicRarity.UNCOMMON
    description = "전투 시작 시 뽑을 더미의 카드 2장을 무작위로 업그레이드"

    def on_combat_start(self, combat=None) -> None:
        if combat is None:
            return
        cards = [card for card in combat.draw_pile if card.is_upgradable]
        combat.rng.shuffle(cards)
        for card in cards[:2]:
            card.upgrade()


# ══════════════════════════════════════════
# Rare 렐릭 (추가)
# ══════════════════════════════════════════

class CaptainsWheel(STS2Relic):
    """선장 바퀴 — 턴3에 블록 18."""
    relic_id = "captains_wheel"
    name = "Captain's Wheel"
    rarity = RelicRarity.RARE
    description = "전투 3턴째에 블록 18 획득"

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if turn == 3 and self.owner:
            self.owner.gain_block(18, powered=False)


class Pocketwatch(STS2Relic):
    """주머니 시계 — 전 턴 카드 ≤3장 사용 시 다음 턴 드로우 +3."""
    relic_id = "pocketwatch"
    name = "Pocketwatch"
    rarity = RelicRarity.RARE
    description = "전 턴에 카드를 3장 이하 사용했으면 다음 턴 카드 3장 추가 드로우"

    def on_combat_start(self, combat=None) -> None:
        self._cards_this_turn = 0
        self._cards_last_turn = 0

    def on_card_played(self, card, combat=None) -> None:
        self._cards_this_turn += 1

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        # 현재 턴의 드로우 수정은 직전 턴 카운트로 판단
        self._cards_last_turn = self._cards_this_turn
        self._cards_this_turn = 0

    def modify_hand_draw(self, count: int, turn: int = 1) -> int:
        if turn <= 1:
            return count
        if self._cards_last_turn <= 3:
            return count + 3
        return count

    def on_combat_end(self, victory: bool) -> None:
        self._cards_this_turn = 0
        self._cards_last_turn = 0


class ArtOfWar(STS2Relic):
    """전쟁의 기술 — 직전 턴에 공격을 사용하지 않았으면 에너지 +1."""
    relic_id = "art_of_war"
    name = "Art of War"
    rarity = RelicRarity.RARE
    description = "직전 턴에 공격 카드를 사용하지 않았으면 에너지 1 획득"

    def on_combat_start(self, combat=None) -> None:
        self._attack_played = False

    def on_turn_start(self, combat=None, turn: int = 1) -> None:
        if turn > 1 and not self._attack_played and self.owner:
            self.owner.gain_energy(1)
        self._attack_played = False

    def on_card_played(self, card, combat=None) -> None:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type == CardType.ATTACK:
            self._attack_played = True

    def on_combat_end(self, victory: bool) -> None:
        self._attack_played = False


class RazorTooth(STS2Relic):
    """면도날 이빨 — 사용한 공격 또는 스킬 카드를 업그레이드."""
    relic_id = "razor_tooth"
    name = "Razor Tooth"
    rarity = RelicRarity.RARE
    description = "공격 또는 스킬 카드를 사용하면 그 카드를 업그레이드"

    def on_card_played(self, card, combat=None) -> None:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type in (CardType.ATTACK, CardType.SKILL) and card.is_upgradable:
            card.upgrade()


class BlackBlood(STS2Relic):
    """검은 피 — 전투 종료 시 HP 12 회복."""
    relic_id = "black_blood"
    name = "Black Blood"
    rarity = RelicRarity.STARTER
    description = "전투 종료 시 승리하면 12 HP 회복"

    def on_combat_end(self, victory: bool) -> None:
        if victory and self.owner:
            self.owner.heal(12)


RELIC_REGISTRY = {
    # Starter
    "burning_blood": BurningBlood,
    "ring_of_the_snake": RingOfTheSnake,
    "cracked_core": CrackedCore,
    "bound_phylactery": BoundPhylactery,
    "divine_right": DivineRight,
    "black_blood": BlackBlood,
    # Common
    "anchor": Anchor,
    "bag_of_marbles": BagOfMarbles,
    "bag_of_preparation": BagOfPreparation,
    "blood_vial": BloodVial,
    "bronze_scales": BronzeScales,
    "data_disk": DataDisk,
    "festive_popper": FestivePopper,
    "gorget": Gorget,
    "happy_flower": HappyFlower,
    "lantern": Lantern,
    "oddly_smooth_stone": OddlySmoothStone,
    "pendulum": Pendulum,
    "red_mask": RedMask,
    "vajra": Vajra,
    # Uncommon
    "akabeko": Akabeko,
    "candelabra": Candelabra,
    "horn_cleat": HornCleat,
    "kusarigama": Kusarigama,
    "letter_opener": LetterOpener,
    "mercury_hourglass": MercuryHourglass,
    "nunchaku": Nunchaku,
    "ornamental_fan": OrnamentalFan,
    "permafrost": Permafrost,
    "stone_cracker": StoneCracker,
    "symbiotic_virus": SymbioticVirus,
    "tuning_fork": TuningFork,
    "twisted_funnel": TwistedFunnel,
    # Rare
    "art_of_war": ArtOfWar,
    "captains_wheel": CaptainsWheel,
    "chandelier": Chandelier,
    "kunai": Kunai,
    "pocketwatch": Pocketwatch,
    "rainbow_ring": RainbowRing,
    "razor_tooth": RazorTooth,
    "shuriken": Shuriken,
    "tungsten_rod": TungstenRod,
    # Shop
    "brimstone": Brimstone,
    "runic_capacitor": RunicCapacitor,
    # Ancient
    "sai": Sai,
    "very_hot_cocoa": VeryHotCocoa,
    "iron_club": IronClub,
    # Event
    "mr_struggles": MrStruggles,
    "royal_poison": RoyalPoison,
    "lost_wisp": LostWisp,
}


def create_relic(relic_id: str) -> Optional[STS2Relic]:
    """렐릭 생성."""
    relic_class = RELIC_REGISTRY.get(relic_id)
    if relic_class:
        return relic_class()
    return None
