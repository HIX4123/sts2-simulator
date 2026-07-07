"""
Ironclad 언커먼 카드.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from sts2_sim.models.card_model import CardModel, CardType, CardRarity, TargetType

if TYPE_CHECKING:
    from sts2_sim.core.combat_state import CombatState
    from sts2_sim.entities.creature import Creature


class Inflame(CardModel):
    """Strength +2 영구."""
    card_id = "inflame"
    name = "Inflame"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        amount = 2 if not self.is_upgraded else 3
        from sts2_sim.models.power_model import Strength
        state.player.apply_power(Strength(), amount, state.player.creature)


class Shockwave(CardModel):
    """전체 적 Weak + Vulnerable 부여. 소모."""
    card_id = "shockwave"
    name = "Shockwave"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.ALL_ENEMIES
    base_energy_cost = 2
    exhausts = True

    def use(self, state: "CombatState", target=None):
        stacks = 3 if not self.is_upgraded else 5
        from sts2_sim.models.power_model import Weak, Vulnerable
        for enemy in list(state.living_enemies):
            enemy.apply_power(Weak(), stacks, state.player.creature)
            enemy.apply_power(Vulnerable(), stacks, state.player.creature)


class Uppercut(CardModel):
    """공격 + Weak + Vulnerable 1씩 부여."""
    card_id = "uppercut"
    name = "Uppercut"
    card_type = CardType.ATTACK
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 2

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        damage = 13 if not self.is_upgraded else 13
        debuff = 1 if not self.is_upgraded else 2
        if target is None:
            target = state.get_random_enemy()
        if target:
            ctx = {"amount": damage, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
            from sts2_sim.models.power_model import Weak, Vulnerable
            target.apply_power(Weak(), debuff, state.player.creature)
            target.apply_power(Vulnerable(), debuff, state.player.creature)


class Whirlwind(CardModel):
    """남은 에너지만큼 전체 적에게 5 데미지씩."""
    card_id = "whirlwind"
    name = "Whirlwind"
    card_type = CardType.ATTACK
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.ALL_ENEMIES
    base_energy_cost = -1  # X 코스트

    def can_play(self, state) -> bool:
        return state.player.energy > 0

    @property
    def energy_cost(self) -> int:
        return 0  # 실제 소비는 use() 내부에서

    def use(self, state: "CombatState", target=None):
        damage_per_hit = 5 if not self.is_upgraded else 8
        hits = state.player.energy  # X = 남은 에너지
        # 에너지 전부 소모
        spent = state.player.energy
        state.player.energy = 0
        state.bus.fire("AfterEnergySpent", player=state.player, amount=spent)

        for _ in range(hits):
            for enemy in list(state.living_enemies):
                ctx = {"amount": damage_per_hit, "source": state.player.creature,
                       "target": enemy, "card": self}
                ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
                enemy.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)


class Dropkick(CardModel):
    """공격. 대상이 Vulnerable이면 에너지 1 회복 + 카드 1 드로우."""
    card_id = "dropkick"
    name = "Dropkick"
    card_type = CardType.ATTACK
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        damage = 5 if not self.is_upgraded else 8
        if target is None:
            target = state.get_random_enemy()
        if target:
            ctx = {"amount": damage, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
            if target.has_power("vulnerable"):
                state.player.energy += 1
                state.draw_card()


class DualWield(CardModel):
    """핸드의 공격/스킬 카드 1장 복사. 업그레이드: 2장."""
    card_id = "dual_wield"
    name = "Dual Wield"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        copies = 1 if not self.is_upgraded else 2
        candidates = [
            c for c in state.hand
            if c is not self and c.card_type in (CardType.ATTACK, CardType.SKILL)
        ]
        if candidates:
            chosen = state.combat_rng.choice(candidates)
            for _ in range(copies):
                state.hand.append(chosen.create_clone())


class Entrench(CardModel):
    """현재 블록을 2배로."""
    card_id = "entrench"
    name = "Entrench"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 2

    def use(self, state: "CombatState", target=None):
        if not self.is_upgraded:
            pass  # 업그레이드 시 비용 1
        current_block = state.player.creature.block
        state.player.creature._block += current_block  # 배가


class FlameBarrier(CardModel):
    """블록 + 이번 턴 공격받으면 반격 4 데미지. Combustion 파워."""
    card_id = "flame_barrier"
    name = "Flame Barrier"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 2

    def use(self, state: "CombatState", target=None):
        block = 12 if not self.is_upgraded else 16
        ctx = {"amount": block, "source": state.player.creature}
        ctx = state.bus.fire("AfterModifyingBlockAmount", **ctx)
        state.player.creature.gain_block(max(0, int(ctx["amount"])))
        thorns = 4 if not self.is_upgraded else 6
        from sts2_sim.models.power_model import Thorns
        state.player.apply_power(Thorns(), thorns, state.player.creature)


class Hemokinesis(CardModel):
    """HP 2 지불 후 Strength +2. 공격."""
    card_id = "hemokinesis"
    name = "Hemokinesis"
    card_type = CardType.ATTACK
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        hp_cost = 2
        damage = 14 if not self.is_upgraded else 20
        # HP 지불
        state.player.creature.lose_hp(hp_cost)
        from sts2_sim.models.power_model import Strength
        state.player.apply_power(Strength(), 2, state.player.creature)
        if target is None:
            target = state.get_random_enemy()
        if target:
            ctx = {"amount": damage, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)


class SpotWeakness(CardModel):
    """대상이 공격 의도 → Strength +3."""
    card_id = "spot_weakness"
    name = "Spot Weakness"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        strength_gain = 3 if not self.is_upgraded else 4
        if target is None:
            target = state.get_random_enemy()
        if target:
            from sts2_sim.entities.monster import IntentType
            intent = getattr(target, "get_intent", lambda: None)()
            if intent and intent.intent_type in (
                IntentType.ATTACK, IntentType.ATTACK_BUFF, IntentType.ATTACK_DEBUFF
            ):
                from sts2_sim.models.power_model import Strength
                state.player.apply_power(Strength(), strength_gain, state.player.creature)


class BattleTrance(CardModel):
    """카드 3장 드로우. 이번 턴 카드 드로우 불가."""
    card_id = "battle_trance"
    name = "Battle Trance"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 0

    def use(self, state: "CombatState", target=None):
        draw = 3 if not self.is_upgraded else 4
        for _ in range(draw):
            state.draw_card()
        # 이번 턴 드로우 막기 (NoDrawPower)
        from sts2_sim.models.power_model import NoDraw
        state.player.apply_power(NoDraw(), 1, state.player.creature)


class Sentinel(CardModel):
    """블록. 소모 시 에너지 2 회복."""
    card_id = "sentinel"
    name = "Sentinel"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        block = 5 if not self.is_upgraded else 8
        ctx = {"amount": block, "source": state.player.creature}
        ctx = state.bus.fire("AfterModifyingBlockAmount", **ctx)
        state.player.creature.gain_block(max(0, int(ctx["amount"])))
        # 소모 시 에너지 회복은 AfterCardExhausted 훅으로 처리 (SentinelPower)


class Rage(CardModel):
    """이번 턴 공격 카드 플레이마다 블록 3 획득 파워."""
    card_id = "rage"
    name = "Rage"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 0

    def use(self, state: "CombatState", target=None):
        amount = 3 if not self.is_upgraded else 5
        from sts2_sim.models.power_model import RagePower
        state.player.apply_power(RagePower(), amount, state.player.creature)


class Pummel(CardModel):
    """4회 공격 2씩. 소모."""
    card_id = "pummel"
    name = "Pummel"
    card_type = CardType.ATTACK
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1
    exhausts = True

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        hits = 4 if not self.is_upgraded else 5
        if target is None:
            target = state.get_random_enemy()
        if target:
            for _ in range(hits):
                ctx = {"amount": 2, "source": state.player.creature, "target": target, "card": self}
                ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
                target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
                if target.is_dead:
                    break


class Disarm(CardModel):
    """적 Strength -2. 소모."""
    card_id = "disarm"
    name = "Disarm"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1
    exhausts = True

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        amount = 2 if not self.is_upgraded else 3
        if target is None:
            target = state.get_random_enemy()
        if target:
            from sts2_sim.models.power_model import Strength
            target.apply_power(Strength(), -amount, state.player.creature)


class Carnage(CardModel):
    """강타 20. Ethereal."""
    card_id = "carnage"
    name = "Carnage"
    card_type = CardType.ATTACK
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 2
    ethereal = True

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        damage = 20 if not self.is_upgraded else 28
        if target is None:
            target = state.get_random_enemy()
        if target:
            ctx = {"amount": damage, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)


class SeeingRed(CardModel):
    """에너지 2 획득. 소모."""
    card_id = "seeing_red"
    name = "Seeing Red"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 1
    exhausts = True

    def use(self, state: "CombatState", target=None):
        gain = 2
        state.player.energy += gain


class SecondWind(CardModel):
    """핸드의 비공격 카드 모두 소모 → 카드당 블록 5."""
    card_id = "second_wind"
    name = "Second Wind"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        block_per = 5 if not self.is_upgraded else 7
        non_attacks = [
            c for c in list(state.hand)
            if c is not self and c.card_type != CardType.ATTACK
        ]
        for card in non_attacks:
            state.move_card_to_exhaust(card)
            ctx = {"amount": block_per, "source": state.player.creature}
            ctx = state.bus.fire("AfterModifyingBlockAmount", **ctx)
            state.player.creature.gain_block(max(0, int(ctx["amount"])))


class Intimidate(CardModel):
    """전체 적 Weak 1. 소모."""
    card_id = "intimidate"
    name = "Intimidate"
    card_type = CardType.SKILL
    rarity = CardRarity.UNCOMMON
    target_type = TargetType.ALL_ENEMIES
    base_energy_cost = 0
    exhausts = True

    def use(self, state: "CombatState", target=None):
        stacks = 1 if not self.is_upgraded else 2
        from sts2_sim.models.power_model import Weak
        for enemy in list(state.living_enemies):
            enemy.apply_power(Weak(), stacks, state.player.creature)
