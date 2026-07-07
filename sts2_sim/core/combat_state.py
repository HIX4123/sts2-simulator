"""
CombatState — 전투 스냅샷.
sts2.dll MegaCrit.Sts2.Core.Combat.CombatState 대응.
"""
from __future__ import annotations
from collections import deque
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

from sts2_sim.hooks.hook_bus import HookBus

if TYPE_CHECKING:
    from sts2_sim.entities.player import Player
    from sts2_sim.entities.monster import Monster
    from sts2_sim.entities.creature import Creature
    from sts2_sim.models.card_model import CardModel
    from sts2_sim.rng.seeded_rng import SeededRng


class CombatSide(Enum):
    PLAYER = auto()
    ENEMY = auto()


class CombatState:
    """
    전투 내 모든 상태를 담는 컨테이너.
    CombatManager가 이 객체를 통해 전투를 진행한다.
    """

    def __init__(
        self,
        player: "Player",
        enemies: list["Monster"],
        combat_rng: "SeededRng",
    ):
        self.player = player
        self.enemies: list["Monster"] = enemies
        self.allies: list["Creature"] = []

        # 덱 파일 (전투 시작 시 player.populate_draw_pile()로 초기화)
        self.draw_pile: deque["CardModel"] = deque()
        self.hand: list["CardModel"] = []
        self.discard_pile: list["CardModel"] = []
        self.exhausted: list["CardModel"] = []
        self.limbo: list["CardModel"] = []   # 임시 보류

        # 전투 진행 상태
        self.round_number: int = 0
        self.current_side: CombatSide = CombatSide.PLAYER
        self.is_in_progress: bool = False

        # RNG
        self.combat_rng: "SeededRng" = combat_rng

        # 훅 버스
        self.bus: HookBus = HookBus()

        # 크리쳐 ↔ combat_state 연결
        player.creature.combat_state = self

    # ──────────────────────────────────────────
    # 상태 검사
    # ──────────────────────────────────────────

    @property
    def player_alive(self) -> bool:
        return self.player.is_alive()

    @property
    def all_enemies_dead(self) -> bool:
        return all(e.is_dead for e in self.enemies)

    @property
    def is_over(self) -> bool:
        return not self.player_alive or self.all_enemies_dead

    @property
    def living_enemies(self) -> list["Monster"]:
        return [e for e in self.enemies if not e.is_dead]

    # ──────────────────────────────────────────
    # 크리쳐 관리
    # ──────────────────────────────────────────

    def add_creature(self, creature: "Creature"):
        """소환물 등 추가."""
        creature.combat_state = self
        self.allies.append(creature)
        self.bus.fire("AfterCreatureAddedToCombat", creature=creature)

    def get_all_creatures(self) -> list["Creature"]:
        result = [self.player.creature]
        result.extend(e for e in self.enemies if not e.is_dead)
        result.extend(self.allies)
        return result

    # ──────────────────────────────────────────
    # 카드 파일 조작
    # ──────────────────────────────────────────

    def move_card_to_discard(self, card: "CardModel"):
        if card in self.hand:
            self.hand.remove(card)
        self.discard_pile.append(card)
        self.bus.fire("AfterCardDiscarded", card=card, state=self)

    def move_card_to_exhaust(self, card: "CardModel"):
        if card in self.hand:
            self.hand.remove(card)
        elif card in self.discard_pile:
            self.discard_pile.remove(card)
        self.exhausted.append(card)
        self.bus.fire("AfterCardExhausted", card=card, state=self)

    def shuffle_discard_into_draw(self):
        """버리기 파일을 섞어 드로우 파일로 이동."""
        cards = self.combat_rng.shuffle(self.discard_pile)
        self.discard_pile.clear()
        self.draw_pile.extend(cards)
        self.bus.fire("AfterShuffle", state=self)

    def flush_hand(self):
        """핸드 전체를 버리기 파일로. AfterFlush 훅 발동."""
        self.bus.fire("BeforeFlush", state=self)
        for card in list(self.hand):
            # Ethereal 카드는 소모
            if getattr(card, "ethereal", False):
                self.hand.remove(card)
                self.exhausted.append(card)
                self.bus.fire("AfterCardExhausted", card=card, state=self)
            else:
                self.hand.remove(card)
                self.discard_pile.append(card)
                self.bus.fire("AfterCardDiscarded", card=card, state=self)
        self.bus.fire("AfterFlush", state=self)
        self.bus.fire("AfterHandEmptied", state=self)

    def draw_card(self) -> Optional["CardModel"]:
        """드로우 파일에서 카드 1장 드로우. 없으면 셔플."""
        if not self.draw_pile:
            if not self.discard_pile:
                return None
            self.shuffle_discard_into_draw()
        if not self.draw_pile:
            return None

        ctx = {"prevented": False, "state": self}
        ctx = self.bus.fire("BeforeHandDraw", **ctx)
        if ctx.get("prevented"):
            return None

        card = self.draw_pile.popleft()
        self.hand.append(card)
        self.bus.fire("AfterCardDrawnEarly", card=card, state=self)
        self.bus.fire("AfterCardDrawn", card=card, state=self)
        return card

    # ──────────────────────────────────────────
    # 타겟 유틸
    # ──────────────────────────────────────────

    def get_random_enemy(self) -> Optional["Monster"]:
        living = self.living_enemies
        if not living:
            return None
        return self.combat_rng.choice(living)

    def __repr__(self):
        return (f"CombatState(round={self.round_number}, "
                f"player={self.player.current_hp}hp, "
                f"enemies={[str(e) for e in self.living_enemies]})")
