"""
이벤트 시스템 (10개 이벤트 구현).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable
from sts2_sim.rng.seeded_rng import SeededRng

if TYPE_CHECKING:
    from sts2_sim.entities.player import Player


@dataclass
class EventResult:
    description: str
    hp_change: int = 0
    gold_change: int = 0
    card_added: str = ""
    relic_added: str = ""


def resolve_event(event_id: str, player: "Player", rng: SeededRng) -> EventResult:
    """이벤트 ID에 따라 결과 반환."""
    return EVENTS.get(event_id, _event_unknown)(player, rng)


def _event_unknown(player, rng) -> EventResult:
    return EventResult("알 수 없는 이벤트 (무시)")


def _event_dead_adventurer(player, rng) -> EventResult:
    """죽은 모험가: 랜덤 보상 (골드 or 카드)."""
    choice = rng.next_int(3)
    if choice == 0:
        gold = rng.next_int(20) + 20
        player.gain_gold(gold)
        return EventResult(f"죽은 모험가: 골드 +{gold}", gold_change=gold)
    elif choice == 1:
        hp = rng.next_int(10) + 5
        player.creature.heal(hp)
        return EventResult(f"죽은 모험가: HP +{hp}", hp_change=hp)
    else:
        return EventResult("죽은 모험가: 아무것도 없다")


def _event_shining_light(player, rng) -> EventResult:
    """빛나는 빛: HP 일부 잃고 카드 2장 업그레이드."""
    hp_cost = int(player.creature.max_hp * 0.1)
    player.creature.lose_hp(hp_cost)
    upgraded = 0
    for card in player.deck:
        if not card.is_upgraded and upgraded < 2:
            card.upgrade()
            upgraded += 1
    return EventResult(f"빛나는 빛: HP -{hp_cost}, 카드 {upgraded}장 업그레이드",
                       hp_change=-hp_cost)


def _event_the_cleric(player, rng) -> EventResult:
    """성직자: 골드 35 지불 → HP 회복, 또는 골드 50 → 저주 제거."""
    if player.gold >= 35:
        player.gain_gold(-35)
        heal = int(player.creature.max_hp * 0.25)
        player.creature.heal(heal)
        return EventResult(f"성직자: 골드 -35, HP +{heal}", hp_change=heal, gold_change=-35)
    return EventResult("성직자: 골드 부족 (무시)")


def _event_world_of_goop(player, rng) -> EventResult:
    """끈적한 세계: HP 3% ~ 10% 잃음."""
    hp_pct = (rng.next_int(8) + 3) / 100.0
    hp_lost = max(1, int(player.creature.max_hp * hp_pct))
    player.creature.lose_hp(hp_lost)
    return EventResult(f"끈적한 세계: HP -{hp_lost}", hp_change=-hp_lost)


def _event_big_fish(player, rng) -> EventResult:
    """큰 물고기: 3가지 선택지 중 랜덤."""
    choice = rng.next_int(3)
    if choice == 0:
        gold = 33
        player.gain_gold(gold)
        return EventResult(f"큰 물고기: 골드 +{gold}", gold_change=gold)
    elif choice == 1:
        heal = int(player.creature.max_hp * 0.33)
        player.creature.heal(heal)
        return EventResult(f"큰 물고기: HP +{heal}", hp_change=heal)
    else:
        player.creature.heal(player.creature.max_hp)  # 완전 회복
        return EventResult("큰 물고기: HP 완전 회복", hp_change=player.creature.max_hp)


def _event_golden_idol(player, rng) -> EventResult:
    """황금 우상: 골드 +250, HP -25%."""
    hp_cost = int(player.creature.max_hp * 0.25)
    player.gain_gold(250)
    player.creature.lose_hp(hp_cost)
    return EventResult(f"황금 우상: 골드 +250, HP -{hp_cost}",
                       hp_change=-hp_cost, gold_change=250)


def _event_fountain_of_cleansing(player, rng) -> EventResult:
    """정화의 샘: 저주 카드 제거."""
    from sts2_sim.models.card_model import CardType
    curses = [c for c in player.deck if c.card_type == CardType.CURSE]
    removed = 0
    for curse in curses[:1]:  # 1장만 제거
        player.remove_card_from_deck(curse)
        removed += 1
    if removed:
        return EventResult(f"정화의 샘: 저주 {removed}장 제거")
    return EventResult("정화의 샘: 제거할 저주 없음")


def _event_library(player, rng) -> EventResult:
    """도서관: 카드 1장 추가."""
    from sts2_sim.cards.ironclad.uncommon import Inflame
    card = Inflame()
    player.add_card_to_deck(card)
    return EventResult(f"도서관: '{card.name}' 획득", card_added=card.name)


def _event_noodle_shop(player, rng) -> EventResult:
    """국수 가게: 골드 50 지불 → 최대 HP +5."""
    if player.gold >= 50:
        player.gain_gold(-50)
        player.creature._max_hp += 5
        player.creature._current_hp = min(
            player.creature._current_hp + 5,
            player.creature._max_hp
        )
        return EventResult("국수 가게: 골드 -50, 최대 HP +5",
                           hp_change=5, gold_change=-50)
    return EventResult("국수 가게: 골드 부족 (무시)")


def _event_mushroom_grove(player, rng) -> EventResult:
    """버섯 숲: HP -5% 잃고 카드 3장 드로우 보너스 (런 효과는 간략화)."""
    hp_cost = max(1, int(player.creature.max_hp * 0.05))
    player.creature.lose_hp(hp_cost)
    heal_later = int(player.creature.max_hp * 0.10)
    player.creature.heal(heal_later)
    return EventResult(f"버섯 숲: HP -{hp_cost} 후 +{heal_later}",
                       hp_change=heal_later - hp_cost)


EVENTS = {
    "dead_adventurer": _event_dead_adventurer,
    "shining_light": _event_shining_light,
    "the_cleric": _event_the_cleric,
    "world_of_goop": _event_world_of_goop,
    "big_fish": _event_big_fish,
    "golden_idol": _event_golden_idol,
    "fountain_of_cleansing": _event_fountain_of_cleansing,
    "library": _event_library,
    "noodle_shop": _event_noodle_shop,
    "mushroom_grove": _event_mushroom_grove,
}

EVENT_POOL_BY_ACT = {
    1: ["dead_adventurer", "shining_light", "the_cleric",
        "world_of_goop", "big_fish", "library"],
    2: ["dead_adventurer", "shining_light", "fountain_of_cleansing",
        "golden_idol", "noodle_shop", "mushroom_grove"],
    3: ["shining_light", "big_fish", "fountain_of_cleansing",
        "noodle_shop", "mushroom_grove"],
}
