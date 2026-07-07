"""
Silent 비공통(Uncommon) 카드.
sts2.dll MegaCrit.Sts2.Core.Models.Cards.Silent 대응.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from sts2_sim.models.card_model import CardModel, CardType, CardRarity, TargetType

if TYPE_CHECKING:
    from sts2_sim.core.combat_state import CombatState
    from sts2_sim.entities.creature import Creature


class Backstab(CardModel):
    """0 에너지 : 데미지 11. 소모. 첫 번째 카드 (전투에서 한 번만)."""
    card_id = "backstab"
    name = "Backstab"
    card_type = CardType.ATTACK
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 0

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        dmg = 15 if self.is_upgraded else 11
        ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
        ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
        target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)

    def get_result_pile(self, state):
        from sts2_sim.models.card_model import PileType
        return PileType.EXHAUST

    def _upgrade_internal(self): pass


class CalculatedGamble(CardModel):
    """0 에너지 : 핸드 버리고 같은 수만큼 드로우. 소모."""
    card_id = "calculated_gamble"
    name = "Calculated Gamble"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 0

    def use(self, state: "CombatState", target=None):
        count = len([c for c in state.hand if c is not self])
        for card in [c for c in state.hand if c is not self]:
            state.move_card_to_discard(card)
        for _ in range(count):
            state.draw_card()

    def get_result_pile(self, state):
        from sts2_sim.models.card_model import PileType
        return PileType.EXHAUST

    def _upgrade_internal(self): pass


class Caltrops(CardModel):
    """1 에너지 : 파워. 공격받을 때 적에게 데미지 3."""
    card_id = "caltrops"
    name = "Caltrops"
    card_type = CardType.POWER
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        from sts2_sim.models.power_model import Thorns
        amount = 5 if self.is_upgraded else 3
        state.player.creature.apply_power(Thorns(), amount, state.player.creature)

    def _upgrade_internal(self): pass


class Catalyst(CardModel):
    """1 에너지 : 적의 독 2배. 소모."""
    card_id = "catalyst"
    name = "Catalyst"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        multiplier = 3 if self.is_upgraded else 2
        p = target.get_power("poison")
        if p:
            p._amount = int(p._amount * multiplier)

    def get_result_pile(self, state):
        from sts2_sim.models.card_model import PileType
        return PileType.EXHAUST

    def _upgrade_internal(self): pass


class Choke(CardModel):
    """2 에너지 : 데미지 12. 이번 턴 카드 플레이 시 적 HP 3 감소."""
    card_id = "choke"
    name = "Choke"
    card_type = CardType.ATTACK
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 2

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        dmg = 14 if self.is_upgraded else 12
        ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
        ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
        target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        # 간략화: 추가 3 데미지
        target.take_damage(3, source=state.player.creature)

    def _upgrade_internal(self): pass


class Concentrate(CardModel):
    """0 에너지 : 핸드 3장 버리기. 에너지 +2."""
    card_id = "concentrate"
    name = "Concentrate"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 0

    def use(self, state: "CombatState", target=None):
        discard_count = 2 if self.is_upgraded else 3
        others = [c for c in state.hand if c is not self]
        for _ in range(min(discard_count, len(others))):
            if others:
                card = state.combat_rng.choice(others)
                others.remove(card)
                state.move_card_to_discard(card)
        state.player.gain_energy(2)

    def _upgrade_internal(self): pass


class CripplingCloud(CardModel):
    """2 에너지 : 전체 적 Weak 4, Poison 4. 소모."""
    card_id = "crippling_cloud"
    name = "Crippling Cloud"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 2

    def use(self, state: "CombatState", target=None):
        weak = 5 if self.is_upgraded else 4
        poison = 5 if self.is_upgraded else 4
        from sts2_sim.models.power_model import Weak, Poison
        for enemy in list(state.living_enemies):
            enemy.apply_power(Weak(), weak, state.player.creature)
            enemy.apply_power(Poison(), poison, state.player.creature)

    def get_result_pile(self, state):
        from sts2_sim.models.card_model import PileType
        return PileType.EXHAUST

    def _upgrade_internal(self): pass


class DeadlyPoison(CardModel):
    """1 에너지 : 독 5 부여."""
    card_id = "deadly_poison"
    name = "Deadly Poison"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        amount = 7 if self.is_upgraded else 5
        from sts2_sim.models.power_model import Poison
        target.apply_power(Poison(), amount, state.player.creature)

    def _upgrade_internal(self): pass


class Distraction(CardModel):
    """0 에너지 : 핸드에 랜덤 스킬 카드 추가 (비용 0). 소모."""
    card_id = "distraction"
    name = "Distraction"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 0

    def use(self, state: "CombatState", target=None):
        from sts2_sim.cards.silent.basic import Acrobatics, Survivor
        pool = [Acrobatics, Survivor]
        cls = state.combat_rng.choice(pool)
        card = cls()
        card.base_energy_cost = 0
        state.hand.append(card)

    def get_result_pile(self, state):
        from sts2_sim.models.card_model import PileType
        return PileType.EXHAUST

    def _upgrade_internal(self): pass


class Endless_Agony(CardModel):
    """0 에너지 : 데미지 4. 드로우·핸드에 복사본 추가. 소모."""
    card_id = "endless_agony"
    name = "Endless Agony"
    card_type = CardType.ATTACK
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 0

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        dmg = 6 if self.is_upgraded else 4
        ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
        ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
        target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        # 복사본 드로우에 추가 (간략화: 핸드에 추가)
        copy = Endless_Agony()
        state.hand.append(copy)

    def get_result_pile(self, state):
        from sts2_sim.models.card_model import PileType
        return PileType.EXHAUST

    def _upgrade_internal(self): pass


class Escape_Plan(CardModel):
    """0 에너지 : 카드 드로우 1. 스킬이면 블록 3."""
    card_id = "escape_plan"
    name = "Escape Plan"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 0

    def use(self, state: "CombatState", target=None):
        block = 5 if self.is_upgraded else 3
        # 드로우 후 체크
        before = len(state.hand)
        state.draw_card()
        after = len(state.hand)
        if after > before:
            drawn = state.hand[-1]
            if getattr(drawn, "card_type", None) == CardType.SKILL:
                state.player.creature.gain_block(block, source=state.player.creature)

    def _upgrade_internal(self): pass


class Expertise(CardModel):
    """1 에너지 : 핸드 6장이 될 때까지 드로우."""
    card_id = "expertise"
    name = "Expertise"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        target_count = 7 if self.is_upgraded else 6
        while len(state.hand) < target_count:
            before = len(state.hand)
            state.draw_card()
            if len(state.hand) == before:
                break

    def _upgrade_internal(self): pass


class Footwork(CardModel):
    """1 에너지 : Dexterity +2 (영구)."""
    card_id = "footwork"
    name = "Footwork"
    card_type = CardType.POWER
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        amount = 3 if self.is_upgraded else 2
        from sts2_sim.models.power_model import Dexterity
        state.player.creature.apply_power(Dexterity(), amount, state.player.creature)

    def _upgrade_internal(self): pass


class InfiniteBlades(CardModel):
    """1 에너지 : 매 턴 시작 핸드에 상처 카드 1장."""
    card_id = "infinite_blades"
    name = "Infinite Blades"
    card_type = CardType.POWER
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        from sts2_sim.cards.silent.basic import Shiv
        # 간략화: 즉시 상처 1장 추가
        state.hand.append(Shiv())

    def _upgrade_internal(self): pass


class NoxiousFumes(CardModel):
    """1 에너지 : 매 턴 시작 적 전체 Poison 2."""
    card_id = "noxious_fumes"
    name = "Noxious Fumes"
    card_type = CardType.POWER
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        # 간략화: 즉시 독 2 부여
        amount = 3 if self.is_upgraded else 2
        from sts2_sim.models.power_model import Poison
        for enemy in list(state.living_enemies):
            enemy.apply_power(Poison(), amount, state.player.creature)

    def _upgrade_internal(self): pass


class Riddle_With_Holes(CardModel):
    """2 에너지 : 단일 적에게 데미지 3 × 5."""
    card_id = "riddle_with_holes"
    name = "Riddle With Holes"
    card_type = CardType.ATTACK
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 2

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        dmg = 3
        hits = 6 if self.is_upgraded else 5
        for _ in range(hits):
            ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)

    def _upgrade_internal(self): pass


class Setup(CardModel):
    """0 에너지 : 핸드에서 카드 1장 선택해 비용 0으로 드로우에 추가."""
    card_id = "setup"
    name = "Setup"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 0

    def use(self, state: "CombatState", target=None):
        others = [c for c in state.hand if c is not self]
        if others:
            card = state.combat_rng.choice(others)
            state.hand.remove(card)
            card.base_energy_cost = 0
            state.draw_pile.insert(0, card)

    def _upgrade_internal(self): pass


class StrikeSilent(CardModel):
    """1 에너지 : 데미지 6 (Silent 스타터)."""
    card_id = "strike_g"
    name = "Strike"
    card_type = CardType.ATTACK
    rarity = CardRarity.STARTER
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        dmg = 9 if self.is_upgraded else 6
        ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
        ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
        target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)

    def _upgrade_internal(self): pass


class Terror(CardModel):
    """1 에너지 : 단일 적 Vulnerable 99. 소모."""
    card_id = "terror"
    name = "Terror"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        amount = 99
        from sts2_sim.models.power_model import Vulnerable
        target.apply_power(Vulnerable(), amount, state.player.creature)

    def get_result_pile(self, state):
        from sts2_sim.models.card_model import PileType
        return PileType.EXHAUST

    def _upgrade_internal(self): pass


class ToolsOfTheTrade(CardModel):
    """1 에너지 : 파워. 매 턴 드로우 1 + 버리기 1."""
    card_id = "tools_of_the_trade"
    name = "Tools of the Trade"
    card_type = CardType.POWER
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        from sts2_sim.models.power_model import ToolsOfTradePower
        state.player.creature.apply_power(ToolsOfTradePower(), 1, state.player.creature)

    def _upgrade_internal(self):
        self.base_energy_cost = 0


class Unload(CardModel):
    """1 에너지 : 데미지 14, 공격 카드 외 모두 버리기."""
    card_id = "unload"
    name = "Unload"
    card_type = CardType.ATTACK
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        dmg = 18 if self.is_upgraded else 14
        ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
        ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
        target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        to_discard = [c for c in state.hand
                      if c is not self and getattr(c, "card_type", None) != CardType.ATTACK]
        for c in to_discard:
            state.move_card_to_discard(c)

    def _upgrade_internal(self): pass


class WellLaidPlans(CardModel):
    """1 에너지 : 턴 종료 시 카드 최대 1장 보존."""
    card_id = "well_laid_plans"
    name = "Well-Laid Plans"
    card_type = CardType.POWER
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        # 간략화: 즉시 드로우 1장
        state.draw_card()

    def _upgrade_internal(self): pass
