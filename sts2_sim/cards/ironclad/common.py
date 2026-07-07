"""
Ironclad 커먼 카드 (나머지).
Heavy Blade, Perfected Strike, Pommel Strike,
Sword Boomerang, Wild Strike, Armaments.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from sts2_sim.models.card_model import CardModel, CardType, CardRarity, TargetType

if TYPE_CHECKING:
    from sts2_sim.core.combat_state import CombatState
    from sts2_sim.entities.creature import Creature


class HeavyBlade(CardModel):
    """Strength을 3배로 적용한 강타."""
    card_id = "heavy_blade"
    name = "Heavy Blade"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 2

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        base = 14 if not self.is_upgraded else 18
        strength_mult = 3 if not self.is_upgraded else 5
        if target is None:
            target = state.get_random_enemy()
        if target:
            str_amount = state.player.get_power_amount("strength")
            damage = base + str_amount * strength_mult
            ctx = {"amount": damage, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)


class PerfectedStrike(CardModel):
    """덱의 Strike 카드 수만큼 데미지 증가."""
    card_id = "perfected_strike"
    name = "Perfected Strike"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 2

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        base = 6 if not self.is_upgraded else 9
        bonus_per_strike = 2 if not self.is_upgraded else 3
        if target is None:
            target = state.get_random_enemy()
        if target:
            # 모든 파일(드로우+핸드+버리기+소모)에서 Strike 계열 카드 수 계산
            all_cards = (
                list(state.draw_pile) + state.hand +
                state.discard_pile + state.exhausted
            )
            strike_count = sum(
                1 for c in all_cards
                if "strike" in getattr(c, "card_id", "").lower()
            )
            damage = base + strike_count * bonus_per_strike
            ctx = {"amount": damage, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)


class PommelStrike(CardModel):
    """공격 + 카드 1장 드로우."""
    card_id = "pommel_strike"
    name = "Pommel Strike"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        damage = 9 if not self.is_upgraded else 10
        draw = 1 if not self.is_upgraded else 2
        if target is None:
            target = state.get_random_enemy()
        if target:
            ctx = {"amount": damage, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        for _ in range(draw):
            state.draw_card()


class SwordBoomerang(CardModel):
    """무작위 적에게 3회 공격."""
    card_id = "sword_boomerang"
    name = "Sword Boomerang"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.ANY
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        hits = 3 if not self.is_upgraded else 4
        damage = 3
        for _ in range(hits):
            t = state.get_random_enemy()
            if t:
                ctx = {"amount": damage, "source": state.player.creature, "target": t, "card": self}
                ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
                t.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)


class WildStrike(CardModel):
    """강타 + 버리기 파일에 Wound 추가."""
    card_id = "wild_strike"
    name = "Wild Strike"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        damage = 12 if not self.is_upgraded else 17
        if target is None:
            target = state.get_random_enemy()
        if target:
            ctx = {"amount": damage, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        # Wound 카드를 버리기 파일에 추가
        state.discard_pile.append(Wound())


class Armaments(CardModel):
    """블록 + 핸드의 카드 1장(업그레이드 시 전부) 업그레이드."""
    card_id = "armaments"
    name = "Armaments"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        block = 5 if not self.is_upgraded else 5
        ctx = {"amount": block, "source": state.player.creature}
        ctx = state.bus.fire("AfterModifyingBlockAmount", **ctx)
        state.player.creature.gain_block(max(0, int(ctx["amount"])))

        if self.is_upgraded:
            # 전부 업그레이드
            for c in state.hand:
                if c is not self and not c.is_upgraded:
                    c.upgrade()
        else:
            # 무작위 1장 업그레이드
            upgradable = [c for c in state.hand if c is not self and not c.is_upgraded]
            if upgradable:
                chosen = state.combat_rng.choice(upgradable)
                chosen.upgrade()


# ──────────────────────────────────────────
# 저주/상태이상 카드
# ──────────────────────────────────────────

class Wound(CardModel):
    """0코스트 플레이 불가 상태이상 카드."""
    card_id = "wound"
    name = "Wound"
    card_type = CardType.STATUS
    rarity = CardRarity.SPECIAL
    target_type = TargetType.NONE
    base_energy_cost = 1

    def can_play(self, state) -> bool:
        return False

    def use(self, state, target=None):
        pass


class Dazed(CardModel):
    """Ethereal 상태이상 카드."""
    card_id = "dazed"
    name = "Dazed"
    card_type = CardType.STATUS
    rarity = CardRarity.SPECIAL
    target_type = TargetType.NONE
    base_energy_cost = 0
    ethereal = True

    def can_play(self, state) -> bool:
        return False

    def use(self, state, target=None):
        pass


class Burn(CardModel):
    """Unplayable. 플레이 시 2 데미지."""
    card_id = "burn"
    name = "Burn"
    card_type = CardType.STATUS
    rarity = CardRarity.SPECIAL
    target_type = TargetType.NONE
    base_energy_cost = 0

    def can_play(self, state) -> bool:
        return False

    def use(self, state, target=None):
        pass


class Slimed(CardModel):
    """Unplayable 상태이상 - 슬라임 계열 몬스터가 추가."""
    card_id = "slimed"
    name = "Slimed"
    card_type = CardType.STATUS
    rarity = CardRarity.SPECIAL
    target_type = TargetType.NONE
    base_energy_cost = 1
    exhausts = True

    def can_play(self, state) -> bool:
        return True  # 플레이하면 소모

    def use(self, state, target=None):
        pass  # 그냥 소모
