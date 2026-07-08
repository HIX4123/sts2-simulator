"""
STS2 CombatState — 헤드리스 전투 턴 루프.

턴 구조 (STS2 대응 단순화):
  플레이어 턴: 블록 초기화 → 에너지 리셋 → 렐릭/오브 턴 시작 훅
             → 드로우(기본 5, 렐릭 수정) → 정책이 카드 플레이 → 턴 종료
             (오브 턴 종료 패시브 → 파워 틱 → 핸드 버리기, 에테리얼은 소모)
  몬스터 턴: 블록 초기화 → 파워 턴 시작 훅(Ritual 등) → 행동 실행 → 파워 틱
"""
from __future__ import annotations
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Tuple

from sts2_sim.models.sts2_card import CardType, create_card

if TYPE_CHECKING:
    from sts2_sim.entities.player import Player
    from sts2_sim.entities.sts2_monster import MonsterModel
    from sts2_sim.models.sts2_card import STS2Card


@dataclass
class CombatResult:
    victory: bool
    turns: int
    player_hp: int


class CombatState:
    """단일 전투 상태 및 턴 루프."""

    BASE_DRAW = 5

    def __init__(self, player: "Player", monsters: List["MonsterModel"], seed: int = 0):
        self.player = player
        self.monsters = monsters
        self.rng = random.Random(seed)
        self.turn = 0

        self.draw_pile: List["STS2Card"] = list(player.master_deck)
        self.rng.shuffle(self.draw_pile)
        self.hand: List["STS2Card"] = []
        self.discard_pile: List["STS2Card"] = []
        self.exhaust_pile: List["STS2Card"] = []

    # ──────────────────────────────────────────
    # 오브/카드가 참조하는 컨텍스트 프로토콜
    # ──────────────────────────────────────────

    @property
    def alive_enemies(self) -> List["MonsterModel"]:
        return [m for m in self.monsters if not m.is_gone]

    def draw_cards(self, count: int) -> None:
        for _ in range(count):
            if not self.draw_pile:
                if not self.discard_pile:
                    return
                self.draw_pile = self.discard_pile
                self.discard_pile = []
                self.rng.shuffle(self.draw_pile)
            self.hand.append(self.draw_pile.pop())

    def discard_from_hand(self, count: int) -> None:
        for _ in range(count):
            if not self.hand:
                return
            card = self.rng.choice(self.hand)
            self.hand.remove(card)
            self.discard_pile.append(card)

    def add_status_to_discard(self, card_id: str, count: int) -> None:
        """몬스터가 상태이상 카드를 버림 더미에 삽입 (Dazed/Slimed)."""
        for _ in range(count):
            card = create_card(card_id)
            if card:
                self.discard_pile.append(card)

    # ──────────────────────────────────────────
    # 전투 루프
    # ──────────────────────────────────────────

    def start(self) -> None:
        """전투 개시: 몬스터 배치 → 렐릭 전투 시작 훅."""
        for i, monster in enumerate(self.monsters):
            monster.setup_for_combat(self, rng=random.Random(self.rng.random()))
        for relic in self.player.relics:
            relic.on_combat_start(self)

    def run(self, policy, max_turns: int = 100) -> CombatResult:
        """정책(policy.choose)이 카드를 고르는 전투 루프 실행."""
        self.start()

        while True:
            self.turn += 1
            if self.turn > max_turns:
                return self._finish(False)

            # ── 플레이어 턴 ──
            self.player.start_of_turn()
            self.player.energy = self.player.max_energy
            for relic in self.player.relics:
                relic.on_turn_start(self, self.turn)
            self.player.orb_queue.trigger_turn_start(self)

            draw_count = self.BASE_DRAW
            for relic in self.player.relics:
                draw_count = relic.modify_hand_draw(draw_count, self.turn)
            self.draw_cards(draw_count)

            while True:
                choice = policy.choose(self)
                if choice is None:
                    break
                card, target = choice
                self.play_card(card, target)
                if not self.alive_enemies:
                    break

            if not self.alive_enemies:
                return self._finish(True)

            # 턴 종료
            self.player.orb_queue.trigger_turn_end(self)
            if not self.alive_enemies:
                return self._finish(True)
            self.player.tick_powers()
            self._discard_hand()
            if self.player.is_dead:  # Poison/Burning 자해
                return self._finish(False)

            # ── 몬스터 턴 ──
            for monster in list(self.alive_enemies):
                monster.start_of_turn()
                for power in list(monster._powers.values()):
                    on_start = getattr(power, "on_turn_start", None)
                    if on_start:
                        on_start()
                monster.take_turn([self.player])
                monster.tick_powers()
                if self.player.is_dead:
                    return self._finish(False)

            if not self.alive_enemies:
                return self._finish(True)

    def play_card(self, card: "STS2Card", target: Optional["MonsterModel"] = None) -> bool:
        """카드 플레이: 비용 지불 → 효과 → 버림/소모 이동 → 렐릭 훅."""
        if card not in self.hand or not card.playable:
            return False
        if card.cost > self.player.energy or card.star_cost > self.player.stars:
            return False

        self.player.energy -= card.cost
        self.player.stars -= card.star_cost

        # 카드는 효과 처리 전에 핸드를 떠난다 (효과 중 핸드 버리기가 자신을 버리지 않도록)
        self.hand.remove(card)

        if card.card_type == CardType.ATTACK:
            targets = [target] if target is not None else self.alive_enemies[:1]
        else:
            targets = []
        card.use(self.player, targets, self)

        if card.exhausts:
            self.exhaust_pile.append(card)
        else:
            self.discard_pile.append(card)

        for relic in self.player.relics:
            relic.on_card_played(card)
        return True

    def _discard_hand(self) -> None:
        """턴 종료 핸드 정리. 에테리얼 카드는 소모."""
        for card in self.hand:
            if card.is_ethereal:
                self.exhaust_pile.append(card)
            else:
                self.discard_pile.append(card)
        self.hand = []

    def _finish(self, victory: bool) -> CombatResult:
        for relic in self.player.relics:
            relic.on_combat_end(victory)
        self.player.sync_to_character()
        return CombatResult(victory=victory, turns=self.turn, player_hp=self.player.current_hp)


class SimplePolicy:
    """기본 그리디 정책: 공격 우선, 남는 에너지로 스킬. 최저 HP 적 우선 타격."""

    def choose(self, combat: CombatState) -> Optional[Tuple["STS2Card", Optional["MonsterModel"]]]:
        player = combat.player
        enemies = combat.alive_enemies
        if not enemies:
            return None

        playable = [
            c for c in combat.hand
            if c.playable and c.cost <= player.energy and c.star_cost <= player.stars
        ]
        if not playable:
            return None

        target = min(enemies, key=lambda m: m.current_hp)

        attacks = [c for c in playable if c.card_type == CardType.ATTACK]
        if attacks:
            best = max(attacks, key=lambda c: c.cost)
            return (best, target)

        skills = [c for c in playable if c.card_type != CardType.ATTACK]
        if skills:
            return (skills[0], None)
        return None
