"""
RunFactory — 캐릭터별 플레이어 생성.
"""
from __future__ import annotations
from sts2_sim.entities.player import Player


def make_ironclad_player(seed: int = 42) -> Player:
    player = Player(name="Ironclad", max_hp=80, max_energy=3)
    from sts2_sim.cards.ironclad.basic import make_ironclad_starter_deck
    for card in make_ironclad_starter_deck():
        player.add_card_to_deck(card)
    from sts2_sim.relics.ironclad import BurningBlood
    bb = BurningBlood()
    bb.owner = player
    player.add_relic(bb)
    return player


def make_silent_player(seed: int = 42) -> Player:
    player = Player(name="Silent", max_hp=70, max_energy=3)
    from sts2_sim.cards.silent.basic import make_silent_starter_deck
    for card in make_silent_starter_deck():
        player.add_card_to_deck(card)
    from sts2_sim.relics.ironclad import BurningBlood
    # Silent 스타터 렐릭: Ring of the Snake (드로우 +2) → BurningBlood 대체
    from sts2_sim.models.relic_model import RelicModel
    class RingOfSnake(RelicModel):
        relic_id = "ring_of_snake"
        name = "Ring of the Snake"
        def AfterPlayerTurnStart(self, ctx):
            state = ctx.get("state")
            if state and state.round_number == 1:
                state.draw_card()
                state.draw_card()
        def subscribed_hooks(self): return ["AfterPlayerTurnStart"]
        def AfterCombatVictory(self, ctx):
            if self.owner: self.owner.creature.heal(5)
        # also override subscribed_hooks to include AfterCombatVictory
        def subscribed_hooks(self):
            return ["AfterPlayerTurnStart", "AfterCombatVictory"]
    ring = RingOfSnake()
    ring.owner = player
    player.add_relic(ring)
    return player
