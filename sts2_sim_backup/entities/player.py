"""
Player — 플레이어 엔티티.
sts2.dll MegaCrit.Sts2.Core.Entities.Players.Player 대응.
"""
from __future__ import annotations
from collections import deque
from typing import TYPE_CHECKING, Optional

from sts2_sim.entities.creature import Creature

if TYPE_CHECKING:
    from sts2_sim.models.card_model import CardModel
    from sts2_sim.models.relic_model import RelicModel
    from sts2_sim.core.combat_state import CombatState


class Player:
    """
    플레이어 상태 관리.
    전투 외 상태(gold, deck, relics)와 전투 중 상태(hand, draw_pile 등)를 모두 포함.
    """

    def __init__(
        self,
        name: str,
        max_hp: int,
        max_energy: int = 3,
        starting_gold: int = 99,
    ):
        self.creature = Creature(name, max_hp)
        self.name = name

        # 런 상태
        self._gold: int = starting_gold
        self._max_energy: int = max_energy
        self._relics: list["RelicModel"] = []
        self._deck: list["CardModel"] = []  # 마스터 덱

        # STS2 Stars 시스템
        self._stars: int = 0

        # 전투 중 상태 (CombatState에서 관리하지만 Player 참조용)
        self.energy: int = max_energy

        # 포션 슬롯 (기본 3)
        self._potion_slots: list[Optional[object]] = [None, None, None]
        self._max_potion_slots: int = 3

    # ──────────────────────────────────────────
    # 프로퍼티 위임 (Creature)
    # ──────────────────────────────────────────

    @property
    def current_hp(self) -> int:
        return self.creature.current_hp

    @property
    def max_hp(self) -> int:
        return self.creature.max_hp

    @property
    def block(self) -> int:
        return self.creature.block

    def take_damage(self, amount: int, source=None, bypass_block=False):
        return self.creature.take_damage(amount, source, bypass_block)

    def gain_block(self, amount: int, source=None):
        return self.creature.gain_block(amount, source)

    def apply_power(self, power, amount: int, applier=None):
        return self.creature.apply_power(power, amount, applier)

    def has_power(self, power_id: str) -> bool:
        return self.creature.has_power(power_id)

    def get_power_amount(self, power_id: str) -> int:
        return self.creature.get_power_amount(power_id)

    def is_alive(self) -> bool:
        return self.creature.is_alive()

    # ──────────────────────────────────────────
    # 에너지
    # ──────────────────────────────────────────

    @property
    def max_energy(self) -> int:
        return self._max_energy

    def reset_energy(self, state: "CombatState"):
        """턴 시작 시 에너지 리셋. AfterEnergyReset 훅 발동."""
        ctx = {"amount": self._max_energy, "player": self}
        ctx = state.bus.fire("AfterModifyingEnergyGain", **ctx)
        self.energy = max(0, int(ctx["amount"]))
        state.bus.fire("AfterEnergyReset", player=self, amount=self.energy)
        state.bus.fire("AfterEnergyResetLate", player=self, amount=self.energy)

    def spend_energy(self, amount: int, state: "CombatState"):
        self.energy = max(0, self.energy - amount)
        state.bus.fire("AfterEnergySpent", player=self, amount=amount)

    # ──────────────────────────────────────────
    # Stars (STS2 신규)
    # ──────────────────────────────────────────

    @property
    def stars(self) -> int:
        return self._stars

    def gain_stars(self, amount: int, state: "CombatState"):
        self._stars += amount
        state.bus.fire("AfterStarsGained", player=self, amount=amount)

    def spend_stars(self, amount: int, state: "CombatState"):
        self._stars = max(0, self._stars - amount)
        state.bus.fire("AfterStarsSpent", player=self, amount=amount)

    # ──────────────────────────────────────────
    # 골드
    # ──────────────────────────────────────────

    @property
    def gold(self) -> int:
        return self._gold

    def gain_gold(self, amount: int, bus=None):
        ctx = {"amount": amount, "player": self}
        if bus:
            ctx = bus.fire("AfterModifyingGoldGained", **ctx)
        self._gold += max(0, int(ctx["amount"]))
        if bus:
            bus.fire("AfterGoldGained", player=self)

    def spend_gold(self, amount: int) -> bool:
        if self._gold < amount:
            return False
        self._gold -= amount
        return True

    # ──────────────────────────────────────────
    # 렐릭
    # ──────────────────────────────────────────

    @property
    def relics(self) -> list["RelicModel"]:
        return list(self._relics)

    def add_relic(self, relic: "RelicModel", bus=None):
        relic.owner = self
        self._relics.append(relic)
        if bus:
            bus.register(relic, priority=0)  # 렐릭 priority=0

    def has_relic(self, relic_id: str) -> bool:
        return any(r.relic_id == relic_id for r in self._relics)

    def get_relic(self, relic_id: str) -> Optional["RelicModel"]:
        for r in self._relics:
            if r.relic_id == relic_id:
                return r
        return None

    # ──────────────────────────────────────────
    # 덱
    # ──────────────────────────────────────────

    @property
    def deck(self) -> list["CardModel"]:
        return list(self._deck)

    def add_card_to_deck(self, card: "CardModel"):
        card.owner = self
        self._deck.append(card)

    def remove_card_from_deck(self, card: "CardModel"):
        self._deck.remove(card)

    # ──────────────────────────────────────────
    # 전투 초기화
    # ──────────────────────────────────────────

    def populate_draw_pile(self, rng) -> deque["CardModel"]:
        """마스터 덱을 복사·셔플해 드로우 파일 생성."""
        import copy
        cards = [copy.deepcopy(c) for c in self._deck]
        shuffled = rng.shuffle(cards)
        return deque(shuffled)

    def reset_combat_state(self):
        """전투 종료 후 임시 효과 초기화."""
        self.creature.clear_block()
        self.creature.remove_all_powers()
        self.energy = self._max_energy
        self._stars = 0

    def __repr__(self):
        return (f"Player({self.name!r}, "
                f"hp={self.current_hp}/{self.max_hp}, "
                f"energy={self.energy}/{self._max_energy}, "
                f"gold={self._gold})")
