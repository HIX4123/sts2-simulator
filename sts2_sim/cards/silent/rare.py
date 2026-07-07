"""
Silent 희귀(Rare) 카드.
sts2.dll MegaCrit.Sts2.Core.Models.Cards.Silent 대응.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from sts2_sim.models.card_model import CardModel, CardType, CardRarity, TargetType

if TYPE_CHECKING:
    from sts2_sim.core.combat_state import CombatState
    from sts2_sim.entities.creature import Creature


class Adrenaline(CardModel):
    """0 에너지 : 에너지 +2, 드로우 2. 소모."""
    card_id = "adrenaline"
    name = "Adrenaline"
    card_type = CardType.SKILL
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = 0

    def use(self, state: "CombatState", target=None):
        energy = 3 if self.is_upgraded else 2
        state.player.gain_energy(energy)
        state.draw_card()
        state.draw_card()

    def get_result_pile(self, state):
        from sts2_sim.models.card_model import PileType
        return PileType.EXHAUST

    def _upgrade_internal(self): pass


class AlchemizeCard(CardModel):
    """1 에너지 : 랜덤 포션 획득. 소모."""
    card_id = "alchemize"
    name = "Alchemize"
    card_type = CardType.SKILL
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        # 간략화: HP 소량 회복
        state.player.creature.heal(5)

    def get_result_pile(self, state):
        from sts2_sim.models.card_model import PileType
        return PileType.EXHAUST

    def _upgrade_internal(self):
        self.base_energy_cost = 0


class BulletTime(CardModel):
    """3 에너지 : 이번 턴 에너지 소모 없이 카드 플레이. 드로우 없음."""
    card_id = "bullet_time"
    name = "Bullet Time"
    card_type = CardType.SKILL
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = 3

    def use(self, state: "CombatState", target=None):
        # 간략화: 모든 핸드 카드 비용 0
        for card in state.hand:
            card.base_energy_cost = 0

    def _upgrade_internal(self):
        self.base_energy_cost = 2


class CorpseExplosion(CardModel):
    """2 에너지 : 독에 걸린 적 처치 + 독 수치만큼 전체 적 데미지."""
    card_id = "corpse_explosion"
    name = "Corpse Explosion"
    card_type = CardType.SKILL
    rarity = CardRarity.RARE
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 2

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        poison_amount = target.get_power_amount("poison")
        target.take_damage(target.current_hp, source=state.player.creature, bypass_block=True)
        if poison_amount > 0:
            for enemy in list(state.living_enemies):
                enemy.take_damage(poison_amount * 2, source=state.player.creature)

    def _upgrade_internal(self): pass


class DieDieDie(CardModel):
    """1 에너지 : 전체 적 데미지 13 × 1. 소모."""
    card_id = "die_die_die"
    name = "Die Die Die"
    card_type = CardType.ATTACK
    rarity = CardRarity.RARE
    target_type = TargetType.ALL_ENEMIES
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        dmg = 17 if self.is_upgraded else 13
        for enemy in list(state.living_enemies):
            ctx = {"amount": dmg, "source": state.player.creature, "target": enemy, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            enemy.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)

    def get_result_pile(self, state):
        from sts2_sim.models.card_model import PileType
        return PileType.EXHAUST

    def _upgrade_internal(self): pass


class DoppelgängerCard(CardModel):
    """X 에너지 : X 에너지와 드로우를 얻음. 소모."""
    card_id = "doppelganger"
    name = "Doppelganger"
    card_type = CardType.SKILL
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = -1  # X cost

    def use(self, state: "CombatState", target=None):
        x = state.player.current_energy
        state.player.gain_energy(x)
        for _ in range(x):
            state.draw_card()

    def get_result_pile(self, state):
        from sts2_sim.models.card_model import PileType
        return PileType.EXHAUST

    def _upgrade_internal(self): pass


class EnvenomCard(CardModel):
    """2 에너지 : 파워. 공격 카드 플레이마다 적에게 독 1."""
    card_id = "envenom"
    name = "Envenom"
    card_type = CardType.POWER
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = 2

    def use(self, state: "CombatState", target=None):
        # 간략화: 즉시 독 3 부여
        from sts2_sim.models.power_model import Poison
        for enemy in list(state.living_enemies):
            enemy.apply_power(Poison(), 3, state.player.creature)

    def _upgrade_internal(self):
        self.base_energy_cost = 1


class GlassKnife(CardModel):
    """1 에너지 : 데미지 8 × 2. 사용할 때마다 데미지 -2."""
    card_id = "glass_knife"
    name = "Glass Knife"
    card_type = CardType.ATTACK
    rarity = CardRarity.RARE
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def __init__(self):
        super().__init__()
        self._current_damage = 8

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        dmg = self._current_damage
        for _ in range(2):
            ctx = {"amount": dmg, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        self._current_damage = max(0, self._current_damage - 2)

    def _upgrade_internal(self):
        self._current_damage = 12


class GrandFinale(CardModel):
    """0 에너지 : 드로우 파일이 비어있으면 전체 적 50 데미지."""
    card_id = "grand_finale"
    name = "Grand Finale"
    card_type = CardType.ATTACK
    rarity = CardRarity.RARE
    target_type = TargetType.ALL_ENEMIES
    base_energy_cost = 0

    def can_play(self, state) -> bool:
        return len(state.draw_pile) == 0

    def use(self, state: "CombatState", target=None):
        dmg = 60 if self.is_upgraded else 50
        for enemy in list(state.living_enemies):
            ctx = {"amount": dmg, "source": state.player.creature, "target": enemy, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            enemy.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)

    def _upgrade_internal(self): pass


class Malaise(CardModel):
    """X 에너지 : 적 Strength -X, Weak X."""
    card_id = "malaise"
    name = "Malaise"
    card_type = CardType.SKILL
    rarity = CardRarity.RARE
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = -1  # X cost

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        if target is None:
            target = state.get_random_enemy()
        if not target:
            return
        x = state.player.current_energy
        from sts2_sim.models.power_model import Strength, Weak
        target.apply_power(Strength(), -x, state.player.creature)
        target.apply_power(Weak(), x, state.player.creature)

    def get_result_pile(self, state):
        from sts2_sim.models.card_model import PileType
        return PileType.EXHAUST

    def _upgrade_internal(self): pass


class Nightmare(CardModel):
    """3 에너지 : 핸드에서 카드 선택, 드로우에 복사 3장 추가. 소모."""
    card_id = "nightmare"
    name = "Nightmare"
    card_type = CardType.SKILL
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = 3

    def use(self, state: "CombatState", target=None):
        count = 4 if self.is_upgraded else 3
        others = [c for c in state.hand if c is not self]
        if others:
            chosen = state.combat_rng.choice(others)
            for _ in range(count):
                import copy
                state.draw_pile.append(copy.copy(chosen))

    def get_result_pile(self, state):
        from sts2_sim.models.card_model import PileType
        return PileType.EXHAUST

    def _upgrade_internal(self):
        self.base_energy_cost = 2


class PhantasmalKiller(CardModel):
    """1 에너지 : 다음 공격 데미지 2배. 소모."""
    card_id = "phantasmal_killer"
    name = "Phantasmal Killer"
    card_type = CardType.SKILL
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        # 간략화: 에너지 +2
        state.player.gain_energy(2)

    def get_result_pile(self, state):
        from sts2_sim.models.card_model import PileType
        return PileType.EXHAUST

    def _upgrade_internal(self):
        self.base_energy_cost = 0


class StormOfSteel(CardModel):
    """1 에너지 : 핸드 버리고 상처 카드로 대체. 소모."""
    card_id = "storm_of_steel"
    name = "Storm of Steel"
    card_type = CardType.SKILL
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        from sts2_sim.cards.silent.basic import Shiv
        count = len([c for c in state.hand if c is not self])
        for card in [c for c in state.hand if c is not self]:
            state.move_card_to_discard(card)
        for _ in range(count):
            shiv = Shiv()
            if self.is_upgraded:
                shiv.upgrade()
            state.hand.append(shiv)

    def get_result_pile(self, state):
        from sts2_sim.models.card_model import PileType
        return PileType.EXHAUST

    def _upgrade_internal(self): pass


class WraithForm(CardModel):
    """3 에너지 : 무형 획득 (이번 턴 데미지 절반). 매 턴 Dexterity -1."""
    card_id = "wraith_form_v2"
    name = "Wraith Form"
    card_type = CardType.POWER
    rarity = CardRarity.RARE
    target_type = TargetType.NONE
    base_energy_cost = 3

    def use(self, state: "CombatState", target=None):
        # 간략화: 블록 획득
        state.player.creature.gain_block(16, source=state.player.creature)

    def _upgrade_internal(self):
        self.base_energy_cost = 2
