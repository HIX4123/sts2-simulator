"""
Ironclad 및 공용 렐릭 구현.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from sts2_sim.models.relic_model import RelicModel

if TYPE_CHECKING:
    from sts2_sim.core.combat_state import CombatState


# ── 스타터 렐릭 ──────────────────────────────

class BurningBlood(RelicModel):
    """전투 종료 후 HP 6 회복."""
    relic_id = "burning_blood"
    name = "Burning Blood"

    def AfterCombatVictory(self, ctx: dict):
        if self.owner:
            self.owner.creature.heal(6)

    def subscribed_hooks(self):
        return ["AfterCombatVictory"]


# ── 커먼 렐릭 ──────────────────────────────

class Anchor(RelicModel):
    """전투 시작 시 블록 10."""
    relic_id = "anchor"
    name = "Anchor"

    def BeforeCombatStart(self, ctx: dict):
        if self.owner:
            self.owner.creature._block += 10

    def subscribed_hooks(self):
        return ["BeforeCombatStart"]


class BagOfMarbles(RelicModel):
    """전투 시작 시 모든 적 Vulnerable 1."""
    relic_id = "bag_of_marbles"
    name = "Bag of Marbles"

    def BeforeCombatStart(self, ctx: dict):
        state = ctx.get("state")
        if state:
            from sts2_sim.models.power_model import Vulnerable
            for enemy in state.enemies:
                enemy.apply_power(Vulnerable(), 1, self.owner.creature if self.owner else None)

    def subscribed_hooks(self):
        return ["BeforeCombatStart"]


class BagOfPreparation(RelicModel):
    """전투 시작 시 2장 추가 드로우."""
    relic_id = "bag_of_preparation"
    name = "Bag of Preparation"

    def AfterPlayerTurnStart(self, ctx: dict):
        state = ctx.get("state")
        if state and state.round_number == 1:
            state.draw_card()
            state.draw_card()

    def subscribed_hooks(self):
        return ["AfterPlayerTurnStart"]


class BronzeScales(RelicModel):
    """전투 시작 시 Thorns 3."""
    relic_id = "bronze_scales"
    name = "Bronze Scales"

    def BeforeCombatStart(self, ctx: dict):
        if self.owner:
            from sts2_sim.models.power_model import Thorns
            self.owner.apply_power(Thorns(), 3, self.owner.creature)

    def subscribed_hooks(self):
        return ["BeforeCombatStart"]


class CentennialPuzzle(RelicModel):
    """전투 중 처음 HP 잃을 때 카드 3장 드로우."""
    relic_id = "centennial_puzzle"
    name = "Centennial Puzzle"

    def __init__(self):
        super().__init__()
        self._triggered = False

    def AfterCurrentHpChanged(self, ctx: dict):
        state_ref = ctx.get("state")
        creature = ctx.get("creature")
        if (not self._triggered and self.owner and
                creature is self.owner.creature and ctx.get("delta", 0) < 0):
            self._triggered = True
            if self.owner.creature.combat_state:
                cs = self.owner.creature.combat_state
                for _ in range(3):
                    cs.draw_card()

    def AfterCombatEnd(self, ctx: dict):
        self._triggered = False

    def subscribed_hooks(self):
        return ["AfterCurrentHpChanged", "AfterCombatEnd"]


class Nunchaku(RelicModel):
    """공격 카드 10장 플레이할 때마다 에너지 1."""
    relic_id = "nunchaku"
    name = "Nunchaku"

    def __init__(self):
        super().__init__()
        self._counter = 0

    def AfterCardPlayed(self, ctx: dict):
        from sts2_sim.models.card_model import CardType
        card = ctx.get("card")
        if card and getattr(card, "card_type", None) == CardType.ATTACK:
            self._counter += 1
            if self._counter >= 10:
                self._counter = 0
                if self.owner:
                    self.owner.energy += 1

    def subscribed_hooks(self):
        return ["AfterCardPlayed"]


class OddMushroom(RelicModel):
    """Vulnerable 받는 데미지 추가량 25% → 50% 아닌 것으로 감소."""
    relic_id = "odd_mushroom"
    name = "Odd Mushroom"
    # Vulnerable 효과를 1.5배 대신 1.25배로 낮춤
    # Vulnerable 파워의 AfterModifyingDamageAmount에서 체크 필요 - 간략화

    def subscribed_hooks(self):
        return []


class Vajra(RelicModel):
    """전투 시작 시 Strength 1."""
    relic_id = "vajra"
    name = "Vajra"

    def BeforeCombatStart(self, ctx: dict):
        if self.owner:
            from sts2_sim.models.power_model import Strength
            self.owner.apply_power(Strength(), 1, self.owner.creature)

    def subscribed_hooks(self):
        return ["BeforeCombatStart"]


class RedSkull(RelicModel):
    """HP 50% 이하일 때 Strength +3 (조건부)."""
    relic_id = "red_skull"
    name = "Red Skull"

    def __init__(self):
        super().__init__()
        self._active = False

    def AfterCurrentHpChanged(self, ctx: dict):
        if not self.owner:
            return
        creature = ctx.get("creature")
        if creature is not self.owner.creature:
            return
        hp_pct = creature.hp_percent
        should_be_active = hp_pct <= 0.5
        if should_be_active and not self._active:
            self._active = True
            from sts2_sim.models.power_model import Strength
            self.owner.apply_power(Strength(), 3, creature)
        elif not should_be_active and self._active:
            self._active = False
            from sts2_sim.models.power_model import Strength
            self.owner.apply_power(Strength(), -3, creature)

    def subscribed_hooks(self):
        return ["AfterCurrentHpChanged"]


class PenNib(RelicModel):
    """공격 카드 10장마다 다음 공격 2배 데미지."""
    relic_id = "pen_nib"
    name = "Pen Nib"

    def __init__(self):
        super().__init__()
        self._counter = 0
        self._doubling = False

    def AfterCardPlayed(self, ctx: dict):
        from sts2_sim.models.card_model import CardType
        card = ctx.get("card")
        if card and getattr(card, "card_type", None) == CardType.ATTACK:
            if self._doubling:
                self._doubling = False
            else:
                self._counter += 1
                if self._counter >= 10:
                    self._counter = 0
                    self._doubling = True

    def AfterModifyingDamageAmount(self, ctx: dict):
        from sts2_sim.models.card_model import CardType
        card = ctx.get("card")
        if (self._doubling and card and
                getattr(card, "card_type", None) == CardType.ATTACK):
            ctx["amount"] = ctx["amount"] * 2

    def subscribed_hooks(self):
        return ["AfterCardPlayed", "AfterModifyingDamageAmount"]


class Akabeko(RelicModel):
    """첫 번째 공격 카드 +8 데미지."""
    relic_id = "akabeko"
    name = "Akabeko"

    def __init__(self):
        super().__init__()
        self._first_attack_done = False

    def AfterModifyingDamageAmount(self, ctx: dict):
        from sts2_sim.models.card_model import CardType
        card = ctx.get("card")
        if (not self._first_attack_done and card and
                getattr(card, "card_type", None) == CardType.ATTACK):
            ctx["amount"] = ctx["amount"] + 8
            self._first_attack_done = True

    def AfterCombatEnd(self, ctx: dict):
        self._first_attack_done = False

    def subscribed_hooks(self):
        return ["AfterModifyingDamageAmount", "AfterCombatEnd"]


class DuVuDoll(RelicModel):
    """저주 카드 1장당 Strength 1."""
    relic_id = "du_vu_doll"
    name = "Du-Vu Doll"

    def BeforeCombatStart(self, ctx: dict):
        if not self.owner:
            return
        from sts2_sim.models.card_model import CardType
        curse_count = sum(
            1 for c in self.owner.deck
            if c.card_type == CardType.CURSE
        )
        if curse_count > 0:
            from sts2_sim.models.power_model import Strength
            self.owner.apply_power(Strength(), curse_count, self.owner.creature)

    def subscribed_hooks(self):
        return ["BeforeCombatStart"]


class GoldenIdol(RelicModel):
    """전투 후 골드 +25."""
    relic_id = "golden_idol"
    name = "Golden Idol"

    def AfterCombatVictory(self, ctx: dict):
        state = ctx.get("state")
        if self.owner and state:
            self.owner.gain_gold(25, state.bus)

    def subscribed_hooks(self):
        return ["AfterCombatVictory"]


class HappyFlower(RelicModel):
    """3턴마다 에너지 1."""
    relic_id = "happy_flower"
    name = "Happy Flower"

    def __init__(self):
        super().__init__()
        self._counter = 0

    def AfterPlayerTurnStart(self, ctx: dict):
        self._counter += 1
        if self._counter >= 3:
            self._counter = 0
            if self.owner:
                self.owner.energy += 1

    def subscribed_hooks(self):
        return ["AfterPlayerTurnStart"]


class Orichalcum(RelicModel):
    """턴 종료 시 블록이 0이면 블록 6."""
    relic_id = "orichalcum"
    name = "Orichalcum"

    def AfterSideTurnEnd(self, ctx: dict):
        if self.owner and self.owner.creature.block == 0:
            self.owner.creature._block = 6

    def subscribed_hooks(self):
        return ["AfterSideTurnEnd"]


class Pocketwatch(RelicModel):
    """이번 턴 3장 이하 플레이 시 다음 턴 3장 추가 드로우."""
    relic_id = "pocketwatch"
    name = "Pocketwatch"

    def __init__(self):
        super().__init__()
        self._cards_this_turn = 0
        self._extra_draw_next = False

    def AfterCardPlayed(self, ctx: dict):
        self._cards_this_turn += 1

    def AfterPlayerTurnStart(self, ctx: dict):
        state = ctx.get("state")
        if self._extra_draw_next and state:
            for _ in range(3):
                state.draw_card()
            self._extra_draw_next = False

    def AfterSideTurnEnd(self, ctx: dict):
        if self._cards_this_turn <= 3:
            self._extra_draw_next = True
        self._cards_this_turn = 0

    def subscribed_hooks(self):
        return ["AfterCardPlayed", "AfterPlayerTurnStart", "AfterSideTurnEnd"]


# ── 언커먼 렐릭 ──────────────────────────────

class DataDisk(RelicModel):
    """전투 시작 시 Accuracy 1 (Shivs +1 데미지 — 간략화: Strength 1)."""
    relic_id = "data_disk"
    name = "Data Disk"

    def BeforeCombatStart(self, ctx: dict):
        if self.owner:
            from sts2_sim.models.power_model import Strength
            self.owner.apply_power(Strength(), 1, self.owner.creature)

    def subscribed_hooks(self):
        return ["BeforeCombatStart"]
