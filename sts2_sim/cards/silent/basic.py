"""
Silent 기본/커먼/언커먼/레어 카드 구현.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from sts2_sim.models.card_model import CardModel, CardType, CardRarity, TargetType

if TYPE_CHECKING:
    from sts2_sim.core.combat_state import CombatState
    from sts2_sim.entities.creature import Creature


# ── 스타터 ──────────────────────────────

class Strike_Silent(CardModel):
    card_id = "strike_silent"
    name = "Strike"
    card_type = CardType.ATTACK
    rarity = CardRarity.BASIC
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1
    def use(self, state, target=None):
        dmg = 6 if not self.is_upgraded else 9
        if target is None: target = state.get_random_enemy()
        if target:
            ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)


class Defend_Silent(CardModel):
    card_id = "defend_silent"
    name = "Defend"
    card_type = CardType.SKILL
    rarity = CardRarity.BASIC
    target_type = TargetType.NONE
    base_energy_cost = 1
    def use(self, state, target=None):
        blk = 5 if not self.is_upgraded else 8
        ctx = {"amount": blk, "source": state.player.creature}
        ctx = state.bus.fire("AfterModifyingBlockAmount", **ctx)
        state.player.creature.gain_block(max(0, int(ctx["amount"])))


class Survivor(CardModel):
    """블록 + 카드 1장 버리기."""
    card_id = "survivor"
    name = "Survivor"
    card_type = CardType.SKILL
    rarity = CardRarity.BASIC
    target_type = TargetType.NONE
    base_energy_cost = 1
    def use(self, state, target=None):
        blk = 8 if not self.is_upgraded else 11
        ctx = {"amount": blk, "source": state.player.creature}
        ctx = state.bus.fire("AfterModifyingBlockAmount", **ctx)
        state.player.creature.gain_block(max(0, int(ctx["amount"])))
        # 핸드에서 무작위 카드 버리기
        hand_others = [c for c in state.hand if c is not self]
        if hand_others:
            discard_c = state.combat_rng.choice(hand_others)
            state.move_card_to_discard(discard_c)


class Neutralize(CardModel):
    """약한 공격 + Weak."""
    card_id = "neutralize"
    name = "Neutralize"
    card_type = CardType.ATTACK
    rarity = CardRarity.BASIC
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 0
    def use(self, state, target=None):
        dmg = 3 if not self.is_upgraded else 4
        weak = 1 if not self.is_upgraded else 2
        if target is None: target = state.get_random_enemy()
        if target:
            ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
            from sts2_sim.models.power_model import Weak
            target.apply_power(Weak(), weak, state.player.creature)


# ── 커먼 ──────────────────────────────

class Acrobatics(CardModel):
    """카드 3 드로우 + 1장 버리기."""
    card_id = "acrobatics"
    name = "Acrobatics"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.NONE
    base_energy_cost = 1
    def use(self, state, target=None):
        draw = 3 if not self.is_upgraded else 4
        for _ in range(draw): state.draw_card()
        hand_others = [c for c in state.hand if c is not self]
        if hand_others:
            discard_c = state.combat_rng.choice(hand_others)
            state.move_card_to_discard(discard_c)


class Backstab(CardModel):
    """Innate. 강타 11. 소모."""
    card_id = "backstab"
    name = "Backstab"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 0
    exhausts = True
    innate = True
    def use(self, state, target=None):
        dmg = 11 if not self.is_upgraded else 15
        if target is None: target = state.get_random_enemy()
        if target:
            ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)


class Bane(CardModel):
    """공격. 대상이 Poison이면 데미지 2배."""
    card_id = "bane"
    name = "Bane"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1
    def use(self, state, target=None):
        dmg = 7 if not self.is_upgraded else 10
        if target is None: target = state.get_random_enemy()
        if target:
            if target.has_power("poison"):
                dmg *= 2
            ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)


class DeadlyPoison(CardModel):
    """Poison 5 부여."""
    card_id = "deadly_poison"
    name = "Deadly Poison"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1
    def use(self, state, target=None):
        stacks = 5 if not self.is_upgraded else 7
        if target is None: target = state.get_random_enemy()
        if target:
            from sts2_sim.models.power_model import Poison
            target.apply_power(Poison(), stacks, state.player.creature)


class Blade_Dance(CardModel):
    """Shiv 3장 핸드에 추가."""
    card_id = "blade_dance"
    name = "Blade Dance"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.NONE
    base_energy_cost = 1
    def use(self, state, target=None):
        count = 3 if not self.is_upgraded else 4
        for _ in range(count):
            state.hand.append(Shiv())


class Shiv(CardModel):
    """0코스트 공격 4. 소모."""
    card_id = "shiv"
    name = "Shiv"
    card_type = CardType.ATTACK
    rarity = CardRarity.SPECIAL
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 0
    exhausts = True
    def use(self, state, target=None):
        dmg = 4 if not self.is_upgraded else 6
        if target is None: target = state.get_random_enemy()
        if target:
            ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)


class DaggerSpray(CardModel):
    """전체 적 2회 공격."""
    card_id = "dagger_spray"
    name = "Dagger Spray"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.ALL_ENEMIES
    base_energy_cost = 1
    def use(self, state, target=None):
        dmg = 4 if not self.is_upgraded else 6
        for _ in range(2):
            for enemy in list(state.living_enemies):
                ctx = {"amount": dmg, "source": state.player.creature, "target": enemy, "card": self}
                ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
                enemy.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)


class DaggerThrow(CardModel):
    """공격 + 카드 1 드로우 + 1 버리기."""
    card_id = "dagger_throw"
    name = "Dagger Throw"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1
    def use(self, state, target=None):
        dmg = 9 if not self.is_upgraded else 12
        if target is None: target = state.get_random_enemy()
        if target:
            ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        state.draw_card()
        hand_others = [c for c in state.hand if c is not self]
        if hand_others:
            state.move_card_to_discard(state.combat_rng.choice(hand_others))


class Deflect(CardModel):
    """블록 4. 소모."""
    card_id = "deflect"
    name = "Deflect"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.NONE
    base_energy_cost = 0
    exhausts = True
    def use(self, state, target=None):
        blk = 4 if not self.is_upgraded else 7
        ctx = {"amount": blk, "source": state.player.creature}
        ctx = state.bus.fire("AfterModifyingBlockAmount", **ctx)
        state.player.creature.gain_block(max(0, int(ctx["amount"])))


class PoisonedStab(CardModel):
    """공격 + Poison 3."""
    card_id = "poisoned_stab"
    name = "Poisoned Stab"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1
    def use(self, state, target=None):
        dmg = 6 if not self.is_upgraded else 8
        stacks = 3 if not self.is_upgraded else 4
        if target is None: target = state.get_random_enemy()
        if target:
            ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
            from sts2_sim.models.power_model import Poison
            target.apply_power(Poison(), stacks, state.player.creature)


class QuickSlash(CardModel):
    """빠른 공격 + 카드 1 드로우."""
    card_id = "quick_slash"
    name = "Quick Slash"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1
    def use(self, state, target=None):
        dmg = 8 if not self.is_upgraded else 12
        if target is None: target = state.get_random_enemy()
        if target:
            ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        state.draw_card()


# ── 언커먼 ──────────────────────────────

class Caltrops(CardModel):
    """Thorns 3 파워."""
    card_id = "caltrops"
    name = "Caltrops"
    card_type = CardType.POWER
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 1
    def use(self, state, target=None):
        amt = 3 if not self.is_upgraded else 5
        from sts2_sim.models.power_model import Thorns
        state.player.apply_power(Thorns(), amt, state.player.creature)


class Choke(CardModel):
    """공격. 이번 턴 카드 플레이마다 적 2 데미지."""
    card_id = "choke"
    name = "Choke"
    card_type = CardType.ATTACK
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 2
    def use(self, state, target=None):
        dmg = 12 if not self.is_upgraded else 15
        if target is None: target = state.get_random_enemy()
        if target:
            ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)


class CloakAndDagger(CardModel):
    """블록 + Shiv 1장."""
    card_id = "cloak_and_dagger"
    name = "Cloak And Dagger"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 1
    def use(self, state, target=None):
        blk = 6 if not self.is_upgraded else 6
        shivs = 1 if not self.is_upgraded else 2
        ctx = {"amount": blk, "source": state.player.creature}
        ctx = state.bus.fire("AfterModifyingBlockAmount", **ctx)
        state.player.creature.gain_block(max(0, int(ctx["amount"])))
        for _ in range(shivs):
            state.hand.append(Shiv())


class Distilled_Chaos(CardModel):
    """드로우 파일 상위 3장 플레이."""
    card_id = "distilled_chaos"
    name = "Distilled Chaos"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 1
    def use(self, state, target=None):
        count = 3 if not self.is_upgraded else 5
        for _ in range(count):
            if state.draw_pile:
                from collections import deque
                card = state.draw_pile.popleft()
                state.hand.append(card)
                from sts2_sim.core.combat_manager import apply_play_card
                t = state.get_random_enemy()
                apply_play_card(state, card, t)
                if state.is_over: break


class Predator(CardModel):
    """강타 15. 다음 턴 시작 시 카드 2 드로우."""
    card_id = "predator"
    name = "Predator"
    card_type = CardType.ATTACK
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 2
    def use(self, state, target=None):
        dmg = 15 if not self.is_upgraded else 20
        if target is None: target = state.get_random_enemy()
        if target:
            ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        # 다음 턴 추가 드로우 (간략화: 즉시 드로우)
        state.draw_card()
        state.draw_card()


class PiercingWail(CardModel):
    """적 전체 Str -6. 소모."""
    card_id = "piercing_wail"
    name = "Piercing Wail"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.ALL_ENEMIES
    base_energy_cost = 1
    exhausts = True
    def use(self, state, target=None):
        amt = 6 if not self.is_upgraded else 8
        from sts2_sim.models.power_model import Strength
        for enemy in list(state.living_enemies):
            enemy.apply_power(Strength(), -amt, state.player.creature)


class Catalyst(CardModel):
    """대상의 Poison 2배. 소모."""
    card_id = "catalyst"
    name = "Catalyst"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1
    exhausts = True
    def use(self, state, target=None):
        mult = 2 if not self.is_upgraded else 3
        if target is None: target = state.get_random_enemy()
        if target and target.has_power("poison"):
            p = target._powers.get("poison")
            if p:
                p._amount *= mult


# ── 레어 ──────────────────────────────

class Adrenaline(CardModel):
    """에너지 1 획득 + 카드 2 드로우. 소모."""
    card_id = "adrenaline"
    name = "Adrenaline"
    card_type = CardType.SKILL
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = 0
    exhausts = True
    def use(self, state, target=None):
        energy = 1 if not self.is_upgraded else 2
        draw = 2
        state.player.energy += energy
        for _ in range(draw): state.draw_card()


class CorpseExplosion(CardModel):
    """대상에게 Poison량만큼 데미지 × 2. 소모."""
    card_id = "corpse_explosion"
    name = "Corpse Explosion"
    card_type = CardType.SKILL
    rarity = CardRarity.RARE
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 2
    exhausts = True
    def use(self, state, target=None):
        if target is None: target = state.get_random_enemy()
        if target:
            poison_amt = target.get_power_amount("poison")
            if poison_amt > 0:
                dmg = poison_amt * 2
                ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
                ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
                target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)


class GlassKnife(CardModel):
    """공격 12 × 2. 플레이마다 데미지 -2."""
    card_id = "glass_knife"
    name = "Glass Knife"
    card_type = CardType.ATTACK
    rarity = CardRarity.RARE
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1
    def __init__(self):
        super().__init__()
        self._extra_dmg_penalty = 0
    def use(self, state, target=None):
        dmg = max(0, (12 if not self.is_upgraded else 16) - self._extra_dmg_penalty)
        self._extra_dmg_penalty += 2
        if target is None: target = state.get_random_enemy()
        for _ in range(2):
            if target:
                ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
                ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
                target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)


class ToolsOfTheTrade(CardModel):
    """매 턴 시작: 카드 1 드로우 + 1 버리기."""
    card_id = "tools_of_the_trade"
    name = "Tools of the Trade"
    card_type = CardType.POWER
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = 1
    def use(self, state, target=None):
        from sts2_sim.models.power_model import ToolsOfTradePower
        state.player.apply_power(ToolsOfTradePower(), 1, state.player.creature)


def make_silent_starter_deck():
    """Silent 스타터 덱: Strike×5, Defend×5, Survivor×1, Neutralize×1."""
    deck = []
    for _ in range(5): deck.append(Strike_Silent())
    for _ in range(5): deck.append(Defend_Silent())
    deck.append(Survivor())
    deck.append(Neutralize())
    return deck
