"""
PowerModel — 파워(버프/디버프) 기반 클래스.
sts2.dll MegaCrit.Sts2.Core.Models.PowerModel 대응.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from sts2_sim.models.abstract_model import AbstractModel

if TYPE_CHECKING:
    from sts2_sim.entities.creature import Creature


class PowerModel(AbstractModel):
    """
    버프/디버프 기반 클래스.
    amount 기반 스태킹 지원, 지속시간 감소, 제거 조건 구현.
    """

    power_id: str = "unknown_power"
    name: str = "Unknown Power"
    is_debuff: bool = False
    has_duration: bool = False       # True면 턴마다 amount 감소
    allow_negative: bool = False     # 음수 amount 허용 여부

    def __init__(self):
        super().__init__()
        self._amount: int = 0
        self._amount_on_turn_start: int = 0
        self.owner: Optional["Creature"] = None
        self.applier: Optional["Creature"] = None
        self._skip_next_duration_tick: bool = False

    @property
    def amount(self) -> int:
        return self._amount

    # ──────────────────────────────────────────
    # 적용 / 제거
    # ──────────────────────────────────────────

    def apply(self, owner, applier, amount: int):
        """파워 부여. owner에 이미 존재하면 스택."""
        ctx = {"power": self, "amount": amount, "owner": owner, "applier": applier}
        bus = getattr(owner, "bus", None)
        if bus is None:
            cs = getattr(owner, "combat_state", None)
            bus = getattr(cs, "bus", None) if cs else None
        if bus:
            ctx = bus.fire("BeforePowerAmountChanged", **ctx)
        self.apply_internal(owner, applier, ctx["amount"])
        if bus:
            bus.fire("AfterPowerAmountChanged", power=self, owner=owner)

    def apply_internal(self, owner: "Creature", applier: "Creature", amount: int):
        """실제 amount 변경. 서브클래스에서 override 가능."""
        self._amount += amount
        if self.should_remove_due_to_amount():
            self.remove()

    def remove(self):
        """파워 제거."""
        if self.owner:
            self.owner.remove_power(self.power_id)

    def remove_internal(self, owner: "Creature"):
        """remove_power()에서 호출됨. 정리 작업."""
        pass

    def should_remove_due_to_amount(self) -> bool:
        """amount가 0 이하일 때 제거 여부."""
        if self.allow_negative:
            return False
        return self._amount <= 0

    # ──────────────────────────────────────────
    # 지속시간 틱 (AfterSideTurnEnd)
    # ──────────────────────────────────────────

    def tick_duration(self):
        """
        턴 종료 시 호출. has_duration=True인 파워는 amount 감소.
        Weak, Vulnerable, Frail 등이 해당.
        """
        if not self.has_duration:
            return
        if self._skip_next_duration_tick:
            self._skip_next_duration_tick = False
            return
        self._amount -= 1
        if self.should_remove_due_to_amount():
            self.remove()

    # ──────────────────────────────────────────
    # 턴 시작 시 스냅샷 (AfterPlayerTurnStart)
    # ──────────────────────────────────────────

    def snapshot_amount_on_turn_start(self):
        self._amount_on_turn_start = self._amount

    @property
    def amount_on_turn_start(self) -> int:
        return self._amount_on_turn_start

    def __repr__(self):
        return f"{self.name}({self._amount})"


# ──────────────────────────────────────────
# 공통 파워 구현 (Phase 1 필수 5개)
# ──────────────────────────────────────────

class Strength(PowerModel):
    power_id = "strength"
    name = "Strength"
    is_debuff = False
    allow_negative = True

    def AfterModifyingDamageAmount(self, ctx: dict):
        """공격 카드 데미지에 Strength 추가."""
        from sts2_sim.models.card_model import CardType
        card = ctx.get("card")
        if card and getattr(card, "card_type", None) == CardType.ATTACK:
            if ctx.get("source") is self.owner:
                ctx["amount"] = max(0, ctx["amount"] + self._amount)

    def subscribed_hooks(self):
        return ["AfterModifyingDamageAmount"]


class Dexterity(PowerModel):
    power_id = "dexterity"
    name = "Dexterity"
    is_debuff = False
    allow_negative = True

    def AfterModifyingBlockAmount(self, ctx: dict):
        """블록 획득량에 Dexterity 추가."""
        if ctx.get("source") is self.owner:
            ctx["amount"] = max(0, ctx["amount"] + self._amount)

    def subscribed_hooks(self):
        return ["AfterModifyingBlockAmount"]


class Vulnerable(PowerModel):
    power_id = "vulnerable"
    name = "Vulnerable"
    is_debuff = True
    has_duration = True

    def AfterModifyingDamageAmount(self, ctx: dict):
        """취약한 대상에게 데미지 1.5배."""
        if ctx.get("target") is self.owner and self._amount > 0:
            ctx["amount"] = int(ctx["amount"] * 1.5)

    def subscribed_hooks(self):
        return ["AfterModifyingDamageAmount"]


class Weak(PowerModel):
    power_id = "weak"
    name = "Weak"
    is_debuff = True
    has_duration = True

    def AfterModifyingDamageAmount(self, ctx: dict):
        """약화된 공격자의 데미지 0.75배."""
        if ctx.get("source") is self.owner and self._amount > 0:
            from sts2_sim.models.card_model import CardType
            card = ctx.get("card")
            if card and getattr(card, "card_type", None) == CardType.ATTACK:
                ctx["amount"] = int(ctx["amount"] * 0.75)

    def subscribed_hooks(self):
        return ["AfterModifyingDamageAmount"]


class Frail(PowerModel):
    power_id = "frail"
    name = "Frail"
    is_debuff = True
    has_duration = True

    def AfterModifyingBlockAmount(self, ctx: dict):
        """허약한 대상의 블록 0.75배."""
        if ctx.get("source") is self.owner and self._amount > 0:
            ctx["amount"] = int(ctx["amount"] * 0.75)

    def subscribed_hooks(self):
        return ["AfterModifyingBlockAmount"]


class Ritual(PowerModel):
    """턴 시작마다 Strength 획득."""
    power_id = "ritual"
    name = "Ritual"
    is_debuff = False

    def AfterSideTurnStart(self, ctx: dict):
        if self.owner and self._amount > 0:
            from sts2_sim.models.power_model import Strength
            self.owner.apply_power(Strength(), self._amount, self.owner)

    def subscribed_hooks(self):
        return ["AfterSideTurnStart"]


class Metallicize(PowerModel):
    """턴 종료마다 블록 획득."""
    power_id = "metallicize"
    name = "Metallicize"
    is_debuff = False

    def BeforeSideTurnEnd(self, ctx: dict):
        if self.owner and self._amount > 0:
            self.owner.gain_block(self._amount, self.owner)

    def subscribed_hooks(self):
        return ["BeforeSideTurnEnd"]


class Burning(PowerModel):
    """턴 종료마다 HP 감소 (저주)."""
    power_id = "burning"
    name = "Burning"
    is_debuff = True

    def AfterSideTurnEnd(self, ctx: dict):
        if self.owner and self._amount > 0:
            self.owner.lose_hp(self._amount)

    def subscribed_hooks(self):
        return ["AfterSideTurnEnd"]


class Thorns(PowerModel):
    """공격받으면 반격 데미지."""
    power_id = "thorns"
    name = "Thorns"
    is_debuff = False

    def AfterDamageReceived(self, ctx: dict):
        source = ctx.get("source")
        if source and self.owner and ctx.get("hp_lost", 0) > 0:
            if source is not self.owner:
                source.lose_hp(self._amount)

    def subscribed_hooks(self):
        return ["AfterDamageReceived"]


class NoDraw(PowerModel):
    """이번 턴 카드 드로우 불가. 1턴 지속."""
    power_id = "no_draw"
    name = "No Draw"
    is_debuff = False
    has_duration = True

    def BeforeHandDraw(self, ctx: dict):
        ctx["prevented"] = True

    def subscribed_hooks(self):
        return ["BeforeHandDraw"]


class RagePower(PowerModel):
    """공격 카드 플레이마다 블록 획득."""
    power_id = "rage"
    name = "Rage"
    is_debuff = False

    def AfterCardPlayed(self, ctx: dict):
        from sts2_sim.models.card_model import CardType
        card = ctx.get("card")
        if card and getattr(card, "card_type", None) == CardType.ATTACK:
            if self.owner:
                self.owner.gain_block(self._amount)

    def subscribed_hooks(self):
        return ["AfterCardPlayed"]


class DemonForm(PowerModel):
    """매 턴 시작마다 Strength +amount 영구 획득."""
    power_id = "demon_form"
    name = "Demon Form"
    is_debuff = False

    def AfterPlayerTurnStart(self, ctx: dict):
        if self.owner and self._amount > 0:
            self.owner.apply_power(Strength(), self._amount, self.owner)

    def subscribed_hooks(self):
        return ["AfterPlayerTurnStart"]


class Barricade(PowerModel):
    """턴 종료 시 블록 제거 안 됨."""
    power_id = "barricade"
    name = "Barricade"
    is_debuff = False

    def subscribed_hooks(self):
        return []


class Corruption(PowerModel):
    """스킬 카드 비용 0. 스킬 카드 플레이 후 소모."""
    power_id = "corruption"
    name = "Corruption"
    is_debuff = False

    def subscribed_hooks(self):
        return []


class Juggernaut(PowerModel):
    """블록 획득 시 무작위 적에게 데미지."""
    power_id = "juggernaut"
    name = "Juggernaut"
    is_debuff = False

    def AfterBlockGained(self, ctx: dict):
        if ctx.get("creature") is self.owner and self._amount > 0:
            state = getattr(self.owner, "combat_state", None)
            if state:
                enemy = state.get_random_enemy()
                if enemy:
                    enemy.take_damage(self._amount, source=self.owner)

    def subscribed_hooks(self):
        return ["AfterBlockGained"]


class LimitBreak(PowerModel):
    """Strength 배가. 소모."""
    power_id = "limit_break"
    name = "Limit Break"
    is_debuff = False

    def subscribed_hooks(self):
        return []


class Poison(PowerModel):
    """턴 종료마다 amount HP 감소 후 amount 1 감소."""
    power_id = "poison"
    name = "Poison"
    is_debuff = True

    def AfterSideTurnEnd(self, ctx: dict):
        if self.owner and self._amount > 0:
            self.owner.lose_hp(self._amount)
            self._amount -= 1
            if self._amount <= 0:
                self.remove()

    def should_remove_due_to_amount(self): return False

    def subscribed_hooks(self):
        return ["AfterSideTurnEnd"]


class ToolsOfTradePower(PowerModel):
    """매 턴 시작: 카드 1 드로우 + 1 버리기."""
    power_id = "tools_of_the_trade"
    name = "Tools of the Trade"

    def AfterPlayerTurnStart(self, ctx: dict):
        state = ctx.get("state")
        if state:
            state.draw_card()
            hand_others = list(state.hand)
            if hand_others:
                discard_c = state.combat_rng.choice(hand_others)
                state.move_card_to_discard(discard_c)

    def subscribed_hooks(self):
        return ["AfterPlayerTurnStart"]
