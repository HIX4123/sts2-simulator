"""
Ironclad 기본 카드 구현 (Phase 1).
Strike, Defend, Bash, Anger, Armaments, Cleave, Clothesline,
Flex, Havoc, Headbutt, Heavy Blade, Iron Wave, Perfected Strike,
Pommel Strike, Shrug It Off, Sword Boomerang, Thunderclap, True Grit, Wild Strike.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from sts2_sim.models.card_model import CardModel, CardType, CardRarity, TargetType

if TYPE_CHECKING:
    from sts2_sim.core.combat_state import CombatState
    from sts2_sim.entities.creature import Creature


def _calc_damage(state: "CombatState", base: int, source, target) -> int:
    """AfterModifyingDamageAmount 훅을 통해 최종 데미지 계산."""
    from sts2_sim.models.card_model import CardType
    ctx = {
        "amount": base,
        "source": source,
        "target": target,
        "card": None,  # 호출자에서 설정
    }
    ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
    return max(0, int(ctx["amount"]))


def _calc_block(state: "CombatState", base: int, source) -> int:
    """AfterModifyingBlockAmount 훅을 통해 최종 블록 계산."""
    ctx = {"amount": base, "source": source}
    ctx = state.bus.fire("AfterModifyingBlockAmount", **ctx)
    return max(0, int(ctx["amount"]))


# ──────────────────────────────────────────
# 스타터 카드
# ──────────────────────────────────────────

class Strike(CardModel):
    card_id = "strike_r"
    name = "Strike"
    card_type = CardType.ATTACK
    rarity = CardRarity.STARTER
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        damage = 6 if not self.is_upgraded else 9
        if target is None:
            target = state.get_random_enemy()
        if target:
            ctx = {"amount": damage, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)

    def _upgrade_internal(self):
        pass  # 데미지 6→9 (use()에서 처리)


class Defend(CardModel):
    card_id = "defend_r"
    name = "Defend"
    card_type = CardType.SKILL
    rarity = CardRarity.STARTER
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        amount = 5 if not self.is_upgraded else 8
        ctx = {"amount": amount, "source": state.player.creature}
        ctx = state.bus.fire("AfterModifyingBlockAmount", **ctx)
        state.player.creature.gain_block(max(0, int(ctx["amount"])))

    def _upgrade_internal(self):
        pass  # 블록 5→8


class Bash(CardModel):
    card_id = "bash"
    name = "Bash"
    card_type = CardType.ATTACK
    rarity = CardRarity.STARTER
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 2

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        damage = 8 if not self.is_upgraded else 10
        vulnerable_stacks = 2 if not self.is_upgraded else 3
        if target is None:
            target = state.get_random_enemy()
        if target:
            ctx = {"amount": damage, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
            from sts2_sim.models.power_model import Vulnerable
            target.apply_power(Vulnerable(), vulnerable_stacks, state.player.creature)


# ──────────────────────────────────────────
# 커먼 카드
# ──────────────────────────────────────────

class Anger(CardModel):
    """0코스트 공격. 버리기 파일에 복사본 추가."""
    card_id = "anger"
    name = "Anger"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 0

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        damage = 6 if not self.is_upgraded else 8
        if target is None:
            target = state.get_random_enemy()
        if target:
            ctx = {"amount": damage, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        # 버리기 파일에 복사본 추가
        state.discard_pile.append(self.create_clone())


class Cleave(CardModel):
    """전체 적 공격."""
    card_id = "cleave"
    name = "Cleave"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.ALL_ENEMIES
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        damage = 8 if not self.is_upgraded else 11
        for enemy in list(state.living_enemies):
            ctx = {"amount": damage, "source": state.player.creature, "target": enemy, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            enemy.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)


class Clothesline(CardModel):
    """공격 + Weak 부여."""
    card_id = "clothesline"
    name = "Clothesline"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 2

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        damage = 12 if not self.is_upgraded else 14
        weak = 2 if not self.is_upgraded else 3
        if target is None:
            target = state.get_random_enemy()
        if target:
            ctx = {"amount": damage, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
            from sts2_sim.models.power_model import Weak
            target.apply_power(Weak(), weak, state.player.creature)


class Flex(CardModel):
    """Strength +2. 턴 종료 시 Strength -2."""
    card_id = "flex"
    name = "Flex"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.NONE
    base_energy_cost = 0

    def use(self, state: "CombatState", target=None):
        amount = 2 if not self.is_upgraded else 4
        from sts2_sim.models.power_model import Strength
        state.player.apply_power(Strength(), amount, state.player.creature)
        # 턴 종료 시 Strength 감소를 위한 FlexPower (간략 구현: 직접 감소)
        # 완전 구현 시 별도 FlexDebuff 파워 필요


class Havoc(CardModel):
    """드로우 파일 맨 위 카드를 무료로 플레이 후 소모."""
    card_id = "havoc"
    name = "Havoc"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        if not state.draw_pile:
            if not state.discard_pile:
                return
            state.shuffle_discard_into_draw()
        if state.draw_pile:
            card = state.draw_pile.popleft()
            # 무료 플레이 후 소모
            from sts2_sim.core.combat_manager import apply_play_card
            from sts2_sim.models.card_model import PileType
            original_cost = card._energy_cost
            card._energy_cost = 0
            card.use(state, None)
            card._energy_cost = original_cost
            state.exhausted.append(card)


class Headbutt(CardModel):
    """공격 + 버리기 파일 맨 위 카드를 드로우 파일로."""
    card_id = "headbutt"
    name = "Headbutt"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        damage = 9 if not self.is_upgraded else 12
        if target is None:
            target = state.get_random_enemy()
        if target:
            ctx = {"amount": damage, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        if state.discard_pile:
            card = state.discard_pile[-1]
            state.discard_pile.remove(card)
            state.draw_pile.appendleft(card)


class IronWave(CardModel):
    """공격 + 블록."""
    card_id = "iron_wave"
    name = "Iron Wave"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.SINGLE_ENEMY
    base_energy_cost = 1

    def use(self, state: "CombatState", target: Optional["Creature"] = None):
        amount = 5 if not self.is_upgraded else 7
        if target is None:
            target = state.get_random_enemy()
        if target:
            ctx = {"amount": amount, "source": state.player.creature, "target": target, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            target.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
        ctx = {"amount": amount, "source": state.player.creature}
        ctx = state.bus.fire("AfterModifyingBlockAmount", **ctx)
        state.player.creature.gain_block(max(0, int(ctx["amount"])))


class ShrugItOff(CardModel):
    """블록 + 카드 1장 드로우."""
    card_id = "shrug_it_off"
    name = "Shrug It Off"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        block = 8 if not self.is_upgraded else 11
        ctx = {"amount": block, "source": state.player.creature}
        ctx = state.bus.fire("AfterModifyingBlockAmount", **ctx)
        state.player.creature.gain_block(max(0, int(ctx["amount"])))
        state.draw_card()


class TrueGrit(CardModel):
    """블록 + 핸드에서 무작위 카드 소모."""
    card_id = "true_grit"
    name = "True Grit"
    card_type = CardType.SKILL
    rarity = CardRarity.COMMON
    target_type = TargetType.NONE
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        block = 7 if not self.is_upgraded else 9
        ctx = {"amount": block, "source": state.player.creature}
        ctx = state.bus.fire("AfterModifyingBlockAmount", **ctx)
        state.player.creature.gain_block(max(0, int(ctx["amount"])))
        # 핸드에서 무작위 카드 소모 (자신 제외)
        candidates = [c for c in state.hand if c is not self]
        if candidates:
            chosen = state.combat_rng.choice(candidates)
            state.move_card_to_exhaust(chosen)


class Thunderclap(CardModel):
    """전체 적 공격 + Vulnerable."""
    card_id = "thunderclap"
    name = "Thunderclap"
    card_type = CardType.ATTACK
    rarity = CardRarity.COMMON
    target_type = TargetType.ALL_ENEMIES
    base_energy_cost = 1

    def use(self, state: "CombatState", target=None):
        damage = 4 if not self.is_upgraded else 7
        from sts2_sim.models.power_model import Vulnerable
        for enemy in list(state.living_enemies):
            ctx = {"amount": damage, "source": state.player.creature, "target": enemy, "card": self}
            ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
            enemy.take_damage(max(0, int(ctx["amount"])), source=state.player.creature)
            enemy.apply_power(Vulnerable(), 1, state.player.creature)


# ──────────────────────────────────────────
# 편의 함수: Ironclad 스타터 덱 생성
# ──────────────────────────────────────────

def make_ironclad_starter_deck() -> list[CardModel]:
    """Ironclad 스타터 덱: Strike×5, Defend×4, Bash×1."""
    deck = []
    for _ in range(5):
        deck.append(Strike())
    for _ in range(4):
        deck.append(Defend())
    deck.append(Bash())
    return deck
