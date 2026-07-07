"""
상점 시스템.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from sts2_sim.rng.seeded_rng import SeededRng

if TYPE_CHECKING:
    from sts2_sim.entities.player import Player


def run_shop(player: "Player", rng: SeededRng, verbose: bool = False) -> dict:
    """상점: 카드 or 렐릭 구매 (간단한 자동 구매)."""
    result = {"bought": [], "spent": 0}

    # 카드 상점: 3개 카드 제공
    from sts2_sim.cards.ironclad.uncommon import Inflame, Shockwave, Disarm
    from sts2_sim.cards.ironclad.rare import Reaper, Bludgeon
    from sts2_sim.cards.silent.basic import DeadlyPoison, Catalyst

    card_pool = [
        (Inflame, 50), (Shockwave, 50), (Disarm, 50),
        (DeadlyPoison, 45), (Reaper, 90), (Bludgeon, 90), (Catalyst, 60),
    ]
    rng.shuffle(card_pool)
    shop_cards = card_pool[:3]

    if verbose:
        print(f"  상점 카드: {[c[0].__name__ for c in shop_cards]}")
        print(f"  현재 골드: {player.gold}")

    for card_cls, price in shop_cards:
        if player.gold >= price:
            card = card_cls()
            player.add_card_to_deck(card)
            player.gain_gold(-price)
            result["bought"].append(card.name)
            result["spent"] += price
            if verbose:
                print(f"  구매: '{card.name}' (-{price}골드, 잔여 {player.gold})")
            break  # 1장만 구매

    return result
