"""
Ironclad 레어 카드.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from sts2_sim.models.card_model import CardModel, CardType, CardRarity, TargetType

if TYPE_CHECKING:
    from sts2_sim.core.combat_state import CombatState
    from sts2_sim.entities.creature import Creature


class DemonFormCard(CardModel):
    """매 턴 Strength +2 영구."""
    card_id = "demon_form"
    name = "Demon Form"
    card_type = CardType.POWER
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = 3

    def use(self, state: "CombatState", target=None):
        amount = 2 if not self.is_upgraded else 3
        from sts2_sim.models.power_model import DemonForm
        state.player.apply_power(DemonForm(), amount, state.player.creature)


class Barricade(CardModel):
    """턴 시작 시 블록 제거 안 됨."""
    card_id = "barricade"
    name = "Barricade"
    card_type = CardType.POWER
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = 3

    def use(self, state: "CombatState", target=None):
        from sts2_sim.models.power_model import Barricade as BarricadePower
        state.player.apply_power(BarricadePower(), 1, state.player.creature)

    def _upgrade_internal(self):
        self._energy_cost = 2


class Corruption(CardModel):
    """스킬 카드 비용 0. 플레이 후 소모."""
    card_id = "corruption"
    name = "Corruption"
    card_type = CardType.POWER
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = 3

    def use(self, state: "CombatState", target=None):
        from sts2_sim.models.power_model import Corruption as CorruptionPower
        state.player.apply_power(CorruptionPower(), 1, state.player.creature)
        # Corruption 활성화: 이후 스킬 카드는 0코스트 + 소모
        state._corruption_active = True

    def _upgrade_internal(self):
        self._energy_cost = 2


class LimitBreakCard(CardModel):
    """Strength 2배. 소모."""
    card_id = "limit_break"
    name = "Limit Break"
    card_type = CardType.SKILL
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = 1
    exhausts = True

    def use(self, state: "CombatState", target=None):
        from sts2_sim.models.power_model import Strength
        str_amount = state.player.get_power_amount("strength")
        if str_amount > 0:
            state.player.apply_power(Strength(), str_amount, state.player.creature)
        if self.is_upgraded:
            self.exhausts = False  # 업그레이드 시 소모 안 함


class Juggernaut(CardModel):
    """블록 획득 시 무작위 적에게 데미지."""
    card_id = "juggernaut"
    name = "Juggernaut"
    card_type = CardType.POWER
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = 2

    def use(self, state: "CombatState", target=None):
        amount = 5 if not self.is_upgraded else 7
        from sts2_sim.models.power_model import Juggernaut as JuggernautPower
        state.player.apply_power(JuggernautPower(), amount, state.player.creature)


class Reaper(CardModel):
    """전체 적 공격. 딜한 데미지만큼 HP 회복. 소모."""
    card_id = "reaper"
    name = "Reaper"
    card_type = CardType.ATTACK
    rarity = CardRarity.RARE
    target_type = TargetType.ALL_ENEMIES
    base_energy_cost = 2
    exhausts = True

    def use(self, state: "CombatState", target=None):
        damage = 4 if not self.is_upgraded else 5
        total_heal = 0
        for enemy in list(state.living_enemies):
            ctx = {"amount": damage, "source": state.player.creature, "target": enemy, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            result = enemy.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
            total_heal += result.hp_lost
        if total_heal > 0:
            state.player.creature.heal(total_heal)


class Offering(CardModel):
    """HP 6 지불, 에너지 2 회복, 카드 3 드로우. 소모."""
    card_id = "offering"
    name = "Offering"
    card_type = CardType.SKILL
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = 0
    exhausts = True

    def use(self, state: "CombatState", target=None):
        hp_cost = 6
        energy_gain = 2
        draw = 3 if not self.is_upgraded else 5
        state.player.creature.lose_hp(hp_cost)
        state.player.energy += energy_gain
        for _ in range(draw):
            state.draw_card()


class Feed(CardModel):
    """공격. 처치 시 최대 HP +3 영구. 소모."""
    card_id = "feed"
    name = "Feed"
    card_type = CardType.ATTACK
    rarity = CardRarity.RARE
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1
    exhausts = True

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        damage = 10 if not self.is_upgraded else 12
        hp_gain = 3 if not self.is_upgraded else 4
        if target is None:
            target = state.get_random_enemy()
        if target:
            hp_before = target.current_hp
            ctx = {"amount": damage, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            result = target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
            if result.killed:
                state.player.creature.set_max_hp(
                    state.player.creature.max_hp + hp_gain
                )
                state.player.creature._current_hp = min(
                    state.player.creature._current_hp + hp_gain,
                    state.player.creature.max_hp
                )


class FiendFire(CardModel):
    """핸드 전체 소모. 카드당 7 데미지. 소모."""
    card_id = "fiend_fire"
    name = "Fiend Fire"
    card_type = CardType.ATTACK
    rarity = CardRarity.RARE
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 2
    exhausts = True

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        damage_per = 7 if not self.is_upgraded else 10
        if target is None:
            target = state.get_random_enemy()
        # 핸드의 다른 카드 모두 소모
        cards_to_exhaust = [c for c in list(state.hand) if c is not self]
        for card in cards_to_exhaust:
            state.move_card_to_exhaust(card)
        hit_count = len(cards_to_exhaust)
        if target and hit_count > 0:
            for _ in range(hit_count):
                ctx = {"amount": damage_per, "source": state.player.creature,
                       "target": target, "card": self}
                ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
                target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
                if target.is_dead:
                    break


class Immolate(CardModel):
    """전체 적 21 데미지. 버리기 파일에 Burn 추가."""
    card_id = "immolate"
    name = "Immolate"
    card_type = CardType.ATTACK
    rarity = CardRarity.RARE
    target_type = TargetType.ALL_ENEMIES
    base_energy_cost = 2

    def use(self, state: "CombatState", target=None):
        damage = 21 if not self.is_upgraded else 28
        for enemy in list(state.living_enemies):
            ctx = {"amount": damage, "source": state.player.creature, "target": enemy, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            enemy.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        from sts2_sim.cards.ironclad.common import Burn
        state.discard_pile.append(Burn())


class Impervious(CardModel):
    """블록 30 획득. 소모."""
    card_id = "impervious"
    name = "Impervious"
    card_type = CardType.SKILL
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = 2
    exhausts = True

    def use(self, state: "CombatState", target=None):
        block = 30 if not self.is_upgraded else 40
        ctx = {"amount": block, "source": state.player.creature}
        ctx = state.bus.fire("AfterModifyingBlockAmount", **ctx)
        state.player.creature.gain_block(max(0, int(ctx["amount"])))


class Bludgeon(CardModel):
    """강타 32."""
    card_id = "bludgeon"
    name = "Bludgeon"
    card_type = CardType.ATTACK
    rarity = CardRarity.RARE
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 3

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        damage = 32 if not self.is_upgraded else 42
        if target is None:
            target = state.get_random_enemy()
        if target:
            ctx = {"amount": damage, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
