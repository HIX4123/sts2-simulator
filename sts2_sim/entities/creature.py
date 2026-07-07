"""
Creature — HP·블록·파워 목록을 관리하는 전투 엔티티 기반 클래스.
sts2.dll MegaCrit.Sts2.Core.Entities.Creatures.Creature 대응.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from sts2_sim.models.power_model import PowerModel
    from sts2_sim.core.combat_state import CombatState
    from sts2_sim.hooks.hook_bus import HookBus


@dataclass
class DamageResult:
    """take_damage() 결과."""
    hp_lost: int
    block_absorbed: int
    killed: bool


class Creature:
    """
    전투 참여자 (플레이어·몬스터·소환물) 공통 베이스.
    HP, 블록, 파워 목록을 관리하고, 데미지/힐/블록 게인 연산을 담당한다.
    """

    def __init__(
        self,
        name: str,
        max_hp: int,
        current_hp: Optional[int] = None,
    ):
        self.name = name
        self._max_hp: int = max_hp
        self._current_hp: int = current_hp if current_hp is not None else max_hp
        self._block: int = 0
        self._powers: dict[str, "PowerModel"] = {}  # power_id → PowerModel
        self.combat_state: Optional["CombatState"] = None
        self.is_dead: bool = False

    # ──────────────────────────────────────────
    # 프로퍼티
    # ──────────────────────────────────────────

    @property
    def current_hp(self) -> int:
        return self._current_hp

    @property
    def max_hp(self) -> int:
        return self._max_hp

    @property
    def block(self) -> int:
        return self._block

    @property
    def bus(self) -> Optional["HookBus"]:
        return self.combat_state.bus if self.combat_state else None

    # ──────────────────────────────────────────
    # HP
    # ──────────────────────────────────────────

    def lose_hp(self, amount: int, source=None) -> int:
        """순수 HP 감소 (블록 무시). 실제 감소량 반환."""
        if amount <= 0:
            return 0
        actual = min(amount, self._current_hp)
        self._current_hp -= actual
        if self.bus:
            self.bus.fire("AfterCurrentHpChanged",
                          creature=self, delta=-actual, source=source)
        if self._current_hp <= 0:
            self._on_death(source)
        return actual

    def heal(self, amount: int) -> int:
        """HP 회복. 실제 회복량 반환."""
        if amount <= 0 or self.is_dead:
            return 0
        before = self._current_hp
        self._current_hp = min(self._current_hp + amount, self._max_hp)
        healed = self._current_hp - before
        if self.bus:
            self.bus.fire("AfterCurrentHpChanged",
                          creature=self, delta=healed, source=None)
        return healed

    def set_max_hp(self, new_max: int):
        self._max_hp = max(1, new_max)
        self._current_hp = min(self._current_hp, self._max_hp)

    # ──────────────────────────────────────────
    # 블록
    # ──────────────────────────────────────────

    def gain_block(self, amount: int, source=None) -> int:
        """블록 획득. AfterModifyingBlockAmount 훅 적용 후 추가."""
        if amount <= 0:
            return 0
        ctx = {"amount": amount, "source": source, "target": self}
        if self.bus:
            ctx = self.bus.fire("AfterModifyingBlockAmount", **ctx)
        final = max(0, int(ctx["amount"]))
        self._block += final
        if self.bus:
            self.bus.fire("AfterBlockGained", creature=self, amount=final)
        return final

    def clear_block(self):
        if self._block > 0:
            self._block = 0

    def _damage_block(self, amount: int) -> tuple[int, int]:
        """블록을 먼저 소모하고 남은 데미지 반환. (block_absorbed, remaining)"""
        absorbed = min(self._block, amount)
        self._block -= absorbed
        remaining = amount - absorbed
        if absorbed > 0 and self._block == 0 and self.bus:
            self.bus.fire("AfterBlockBroken", creature=self)
        return absorbed, remaining

    # ──────────────────────────────────────────
    # 데미지
    # ──────────────────────────────────────────

    def take_damage(self, amount: int, source=None, bypass_block: bool = False) -> DamageResult:
        """
        데미지 수신 전체 파이프라인.
        1. BeforeDamageReceived 훅
        2. 블록 소모
        3. HP 감소
        4. AfterDamageReceived 훅
        """
        if amount <= 0:
            return DamageResult(0, 0, False)

        # 훅: 수신 전
        ctx = {"amount": amount, "source": source, "target": self}
        if self.bus:
            ctx = self.bus.fire("BeforeDamageReceived", **ctx)
        amount = max(0, int(ctx["amount"]))

        if bypass_block:
            block_absorbed = 0
            hp_damage = amount
        else:
            block_absorbed, hp_damage = self._damage_block(amount)

        hp_lost = self.lose_hp(hp_damage, source) if hp_damage > 0 else 0

        if self.bus:
            self.bus.fire("AfterDamageReceived",
                          creature=self, hp_lost=hp_lost,
                          block_absorbed=block_absorbed, source=source)
            self.bus.fire("AfterDamageReceivedLate",
                          creature=self, hp_lost=hp_lost, source=source)

        return DamageResult(
            hp_lost=hp_lost,
            block_absorbed=block_absorbed,
            killed=self.is_dead,
        )

    # ──────────────────────────────────────────
    # 파워
    # ──────────────────────────────────────────

    def has_power(self, power_id: str) -> bool:
        return power_id in self._powers

    def get_power(self, power_id: str) -> Optional["PowerModel"]:
        return self._powers.get(power_id)

    def get_power_amount(self, power_id: str) -> int:
        p = self._powers.get(power_id)
        return p.amount if p else 0

    def apply_power(self, power: "PowerModel", amount: int, applier: "Creature" = None):
        """파워 부여. 이미 있으면 스택, 없으면 새로 등록."""
        existing = self._powers.get(power.power_id)
        if existing:
            existing.apply(self, applier or self, amount)
        else:
            power.owner = self
            power.applier = applier or self
            self._powers[power.power_id] = power
            if self.combat_state:
                self.combat_state.bus.register(power, priority=1)  # 파워 priority=1
            power.apply(self, applier or self, amount)

    def remove_power(self, power_id: str):
        p = self._powers.pop(power_id, None)
        if p and self.combat_state:
            self.combat_state.bus.unregister(p)
            p.remove_internal(self)

    def remove_all_powers(self):
        for pid in list(self._powers.keys()):
            self.remove_power(pid)

    def tick_all_powers(self):
        """턴 종료 시 모든 파워의 지속시간 감소."""
        for pid in list(self._powers.keys()):
            p = self._powers.get(pid)
            if p and hasattr(p, "tick_duration"):
                p.tick_duration()

    # ──────────────────────────────────────────
    # 사망
    # ──────────────────────────────────────────

    def _on_death(self, source=None):
        ctx = {"creature": self, "source": source, "prevented": False}
        if self.bus:
            ctx = self.bus.fire("BeforeDeath", **ctx)
        if ctx.get("prevented"):
            self._current_hp = max(1, self._current_hp)
            return
        self.is_dead = True
        self.remove_all_powers()
        if self.bus:
            self.bus.fire("AfterDeath", creature=self, source=source)

    # ──────────────────────────────────────────
    # 턴 처리
    # ──────────────────────────────────────────

    def before_turn_start(self):
        """턴 시작 전 처리 (몬스터: clear block 등)."""
        pass

    def after_turn_start(self):
        """턴 시작 후 처리."""
        pass

    def prepare_for_next_turn(self):
        """턴 종료 후 다음 턴 준비."""
        self.tick_all_powers()

    # ──────────────────────────────────────────
    # 유틸
    # ──────────────────────────────────────────

    @property
    def hp_percent(self) -> float:
        return self._current_hp / self._max_hp if self._max_hp > 0 else 0.0

    def is_alive(self) -> bool:
        return not self.is_dead and self._current_hp > 0

    def __repr__(self):
        return (f"{self.__class__.__name__}({self.name!r}, "
                f"hp={self._current_hp}/{self._max_hp}, block={self._block})")
