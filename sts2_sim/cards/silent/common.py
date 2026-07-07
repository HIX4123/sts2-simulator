"""
Silent 공용(Common) 카드.
sts2.dll MegaCrit.Sts2.Core.Models.Cards.Silent 대응.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from sts2_sim.models.card_model import CardModel, CardType, CardRarity, TargetType

if TYPE_CHECKING:
    from sts2_sim.core.combat_state import CombatState
    from sts2_sim.entities.creature import Creature


class Survivor(CardModel):
    """1 에너지 : 8 블록 + 카드 1장 버리기."""
    card_id = "survivor"
    name = "Survivor"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        block = 11 if self.is_upgraded else 8
        state.player.creature.gain_block(block, source=state.player.creature)
        # 핸드에서 랜덤 카드 버리기
        others = [c for c in state.hand if c is not self]
        if others:
            discard = state.combat_rng.choice(others)
            state.move_card_to_discard(discard)

    def _upgrade_internal(self): pass


class Acupuncture(CardModel):
    """1 에너지 : 데미지 5 × 2, Weak 1."""
    card_id = "acupuncture"
    name = "Acupuncture"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        hits = 3 if self.is_upgraded else 2
        dmg = 5
        for _ in range(hits):
            ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        from sts2_sim.models.power_model import Weak
        target.apply_power(Weak(), 1, state.player.creature)

    def _upgrade_internal(self): pass


class AllOutAttack(CardModel):
    """1 에너지 : 전체 적 데미지 10, 핸드에서 랜덤 카드 버리기."""
    card_id = "all_out_attack"
    name = "All-Out Attack"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.ALL_ENEMIES
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        dmg = 14 if self.is_upgraded else 10
        for enemy in list(state.living_enemies):
            ctx = {"amount": dmg, "source": state.player.creature, "target": enemy, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            enemy.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        others = [c for c in state.hand if c is not self]
        if others:
            discard = state.combat_rng.choice(others)
            state.move_card_to_discard(discard)

    def _upgrade_internal(self): pass


class Backflip(CardModel):
    """1 에너지 : 5 블록 + 카드 2장 드로우."""
    card_id = "backflip"
    name = "Backflip"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        block = 8 if self.is_upgraded else 5
        state.player.creature.gain_block(block, source=state.player.creature)
        state.draw_card()
        state.draw_card()

    def _upgrade_internal(self): pass


class Bane(CardModel):
    """1 에너지 : 데미지 7. 독에 걸린 대상이면 추가 데미지 7."""
    card_id = "bane"
    name = "Bane"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        dmg = 10 if self.is_upgraded else 7
        ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
        ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
        target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        if target.has_power("poison"):
            ctx2 = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
            ctx2 = state.bus.fire("AfterModifyingDamageAmount", **ctx2)
            target.take_damage(max(0, int(ctx2["amount"])), source=state.player.creature)

    def _upgrade_internal(self): pass


class BladeDance(CardModel):
    """1 에너지 : 핸드에 상처(Wound) 카드 3장 추가."""
    card_id = "blade_dance"
    name = "Blade Dance"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        count = 4 if self.is_upgraded else 3
        from sts2_sim.cards.silent.basic import Shiv
        for _ in range(count):
            state.hand.append(Shiv())

    def _upgrade_internal(self): pass


class CloakAndDagger(CardModel):
    """1 에너지 : 6 블록, 핸드에 상처 카드 1장 추가."""
    card_id = "cloak_and_dagger"
    name = "Cloak and Dagger"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        block = 6
        count = 2 if self.is_upgraded else 1
        state.player.creature.gain_block(block, source=state.player.creature)
        from sts2_sim.cards.silent.basic import Shiv
        for _ in range(count):
            state.hand.append(Shiv())

    def _upgrade_internal(self): pass


class DaggerSpray(CardModel):
    """1 에너지 : 전체 적 데미지 4 × 2."""
    card_id = "dagger_spray"
    name = "Dagger Spray"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.ALL_ENEMIES
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        dmg = 4
        hits = 3 if self.is_upgraded else 2
        for _ in range(hits):
            for enemy in list(state.living_enemies):
                ctx = {"amount": dmg, "source": state.player.creature, "target": enemy, "card": self}
                ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
                enemy.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)

    def _upgrade_internal(self): pass


class DaggerThrow(CardModel):
    """1 에너지 : 데미지 9, 카드 드로우 1, 카드 버리기 1."""
    card_id = "dagger_throw"
    name = "Dagger Throw"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        dmg = 11 if self.is_upgraded else 9
        ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
        ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
        target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        state.draw_card()
        others = [c for c in state.hand if c is not self]
        if others:
            discard = state.combat_rng.choice(others)
            state.move_card_to_discard(discard)

    def _upgrade_internal(self): pass


class Deflect(CardModel):
    """0 에너지 : 4 블록. 소모."""
    card_id = "deflect"
    name = "Deflect"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.NONE
    base_energy_cost = 0

    def use(self, state: "CombatState", target=None):
        block = 7 if self.is_upgraded else 4
        state.player.creature.gain_block(block, source=state.player.creature)

    def _upgrade_internal(self): pass


class DodgeAndRoll(CardModel):
    """1 에너지 : 4 블록. 다음 턴 시작 시 4 블록 추가."""
    card_id = "dodge_and_roll"
    name = "Dodge and Roll"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        block = 6 if self.is_upgraded else 4
        state.player.creature.gain_block(block, source=state.player.creature)
        # 다음 턴 블록은 간략화: 즉시 추가
        state.player.creature.gain_block(block, source=state.player.creature)

    def _upgrade_internal(self): pass


class FlyingKnee(CardModel):
    """1 에너지 : 데미지 8. 다음 턴 에너지 +1."""
    card_id = "flying_knee"
    name = "Flying Knee"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        dmg = 11 if self.is_upgraded else 8
        ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
        ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
        target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        state.player.gain_energy(1)

    def _upgrade_internal(self): pass


class Outmaneuver(CardModel):
    """0 에너지 : 다음 턴 에너지 +2."""
    card_id = "outmaneuver"
    name = "Outmaneuver"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.NONE
    base_energy_cost = 0

    def use(self, state: "CombatState", target=None):
        gain = 3 if self.is_upgraded else 2
        state.player.gain_energy(gain)

    def _upgrade_internal(self): pass


class PiercingWail(CardModel):
    """1 에너지 : 전체 적 Strength -6. 소모."""
    card_id = "piercing_wail"
    name = "Piercing Wail"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        amount = 8 if self.is_upgraded else 6
        from sts2_sim.models.power_model import Strength
        for enemy in list(state.living_enemies):
            enemy.apply_power(Strength(), -amount, state.player.creature)

    def _upgrade_internal(self): pass


class PoisonedStab(CardModel):
    """1 에너지 : 데미지 6, Poison 3."""
    card_id = "poisoned_stab"
    name = "Poisoned Stab"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        dmg = 8 if self.is_upgraded else 6
        poison = 4 if self.is_upgraded else 3
        ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
        ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
        target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        from sts2_sim.models.power_model import Poison
        target.apply_power(Poison(), poison, state.player.creature)

    def _upgrade_internal(self): pass


class Prepared(CardModel):
    """0 에너지 : 드로우 1, 버리기 1."""
    card_id = "prepared"
    name = "Prepared"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.NONE
    base_energy_cost = 0

    def use(self, state: "CombatState", target=None):
        count = 2 if self.is_upgraded else 1
        for _ in range(count):
            state.draw_card()
        others = [c for c in state.hand if c is not self]
        if others:
            discard = state.combat_rng.choice(others)
            state.move_card_to_discard(discard)

    def _upgrade_internal(self): pass


class QuickSlash(CardModel):
    """1 에너지 : 데미지 8 + 드로우 1."""
    card_id = "quick_slash"
    name = "Quick Slash"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        dmg = 12 if self.is_upgraded else 8
        ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
        ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
        target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        state.draw_card()

    def _upgrade_internal(self): pass


class Slice(CardModel):
    """0 에너지 : 데미지 6."""
    card_id = "slice"
    name = "Slice"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 0

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


class Sneaky_Strike(CardModel):
    """2 에너지 : 데미지 12. 이번 턴 카드 버렸으면 에너지 +2."""
    card_id = "sneaky_strike"
    name = "Sneaky Strike"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 2

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        dmg = 16 if self.is_upgraded else 12
        ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
        ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
        target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        if getattr(state, "cards_discarded_this_turn", 0) > 0:
            state.player.gain_energy(2)

    def _upgrade_internal(self): pass


class SuckerPunch(CardModel):
    """1 에너지 : 데미지 7, Weak 1."""
    card_id = "sucker_punch"
    name = "Sucker Punch"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        dmg = 9 if self.is_upgraded else 7
        weak = 2 if self.is_upgraded else 1
        ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
        ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
        target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        from sts2_sim.models.power_model import Weak
        target.apply_power(Weak(), weak, state.player.creature)

    def _upgrade_internal(self): pass
