#!/usr/bin/env python3
"""S1.M3.B27 — 디컴파일 원본 기준 렐릭 19종 회귀 테스트."""
from sts2_sim.core.combat import CombatState
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import Ironclad
from sts2_sim.entities.sts2_monster import BigDummy
from sts2_sim.models.sts2_card import (
    CardType, Defend, Shiv, Strike, STS2Card,
)
from sts2_sim.models.sts2_relic import (
    RELIC_REGISTRY, DaughterOfTheWind, DivineDestiny, FakeAnchor,
    FakeBloodVial, FakeHappyFlower, FakeLeesWaffle, FakeMango, GamePiece,
    LeesWaffle, Mango, MeatOnTheBone, NutritiousOyster, PaelsBlood, Pear,
    PowerCell, PhylacteryUnbound, RingOfTheDrake, Strawberry, SwordOfJade,
)


class FakePower(STS2Card):
    card_type = CardType.POWER


def make_combat(relic, deck=None, seed=1):
    player = Player(Ironclad(), deck=deck or [])
    relic.on_equip(player)
    player.relics = [relic]
    return player, CombatState(player, [BigDummy()], seed=seed)


def test_registry_has_69_relics():
    assert len(RELIC_REGISTRY) == 69
    for relic_id in (
        "fake_anchor", "sword_of_jade", "phylactery_unbound", "meat_on_the_bone",
        "fake_blood_vial", "divine_destiny", "fake_happy_flower", "power_cell",
        "daughter_of_the_wind", "game_piece", "ring_of_the_drake", "paels_blood",
        "mango", "pear", "strawberry", "nutritious_oyster", "fake_mango",
        "lees_waffle", "fake_lees_waffle",
    ):
        assert relic_id in RELIC_REGISTRY


def test_fake_anchor_gains_4_combat_block():
    player, combat = make_combat(FakeAnchor())
    combat.start()
    assert player.block == 4


def test_sword_of_jade_gives_3_strength():
    player, combat = make_combat(SwordOfJade())
    combat.start()
    assert player.get_power_amount("strength") == 3


def test_phylactery_unbound_summons_osty():
    player, combat = make_combat(PhylacteryUnbound())
    relic = player.relics[0]
    combat.start()
    assert player.osty is not None and player.osty.current_hp == 5
    relic.on_turn_start(combat, 2)
    assert player.osty.current_hp == 7
    relic.on_turn_start(combat, 3)
    assert player.osty.current_hp == 9


def test_meat_on_the_bone_heals_12_on_victory():
    player, combat = make_combat(MeatOnTheBone())
    relic = player.relics[0]
    player._current_hp = 40  # Ironclad 최대 80의 50% 이하
    relic.on_combat_end(True)
    assert player.current_hp == 52
    relic.on_combat_end(False)
    assert player.current_hp == 52


def test_fake_blood_vial_heals_1_first_turn_only():
    player, combat = make_combat(FakeBloodVial())
    relic = player.relics[0]
    player._current_hp = 70
    relic.on_turn_start(combat, 1)
    assert player.current_hp == 71
    relic.on_turn_start(combat, 2)
    assert player.current_hp == 71


def test_divine_destiny_gains_7_stars_first_turn():
    player, combat = make_combat(DivineDestiny())
    relic = player.relics[0]
    relic.on_turn_start(combat, 1)
    assert player.stars == 7
    relic.on_turn_start(combat, 2)
    assert player.stars == 7


def test_fake_happy_flower_energy_every_5_turns():
    player, combat = make_combat(FakeHappyFlower())
    relic = player.relics[0]
    for _ in range(4):
        relic.on_turn_start(combat)
    assert player.energy == 0
    relic.on_turn_start(combat)  # 5번째 턴 시작
    assert player.energy == 1
    for _ in range(5):
        relic.on_turn_start(combat)
    assert player.energy == 2


def test_ring_of_the_drake_draw_2_until_turn_3():
    player, combat = make_combat(RingOfTheDrake())
    relic = player.relics[0]
    assert relic.modify_hand_draw(5, 1) == 7
    assert relic.modify_hand_draw(5, 3) == 7
    assert relic.modify_hand_draw(5, 4) == 5


def test_paels_blood_draw_1_always():
    player, combat = make_combat(PaelsBlood())
    relic = player.relics[0]
    assert relic.modify_hand_draw(5, 1) == 6
    assert relic.modify_hand_draw(5, 9) == 6


def test_daughter_of_the_wind_block_on_attack():
    player, combat = make_combat(DaughterOfTheWind())
    relic = player.relics[0]
    relic.on_card_played(Strike(), combat)
    assert player.block == 1
    relic.on_card_played(Defend(), combat)
    assert player.block == 1


def test_game_piece_draws_on_power_play():
    player, combat = make_combat(GamePiece(), deck=[Strike()])
    relic = player.relics[0]
    relic.on_card_played(FakePower(), combat)
    assert len(combat.hand) == 1 and isinstance(combat.hand[0], Strike)


def test_power_cell_pulls_two_zero_cost_cards():
    deck = [Strike(), Defend(), Shiv(), Shiv()]
    player, combat = make_combat(PowerCell(), deck=deck, seed=3)
    relic = player.relics[0]
    relic.on_turn_start(combat, 1)
    drawn = [c for c in combat.hand if c.cost == 0]
    assert len(drawn) == 2 and len(combat.draw_pile) == len(deck) - 2


def test_max_hp_relics_increase_on_equip():
    player = Player(Ironclad(), deck=[Strike()])
    Mango().on_equip(player)
    Pear().on_equip(player)
    Strawberry().on_equip(player)
    NutritiousOyster().on_equip(player)
    FakeMango().on_equip(player)
    assert player.max_hp == 80 + 14 + 10 + 7 + 11 + 3
    assert player.current_hp == player.max_hp


def test_lees_waffle_heals_to_full():
    player = Player(Ironclad(), deck=[Strike()])
    player._current_hp = 30
    LeesWaffle().on_equip(player)
    assert player.max_hp == 87 and player.current_hp == 87


def test_fake_lees_waffle_heals_10_percent():
    player = Player(Ironclad(), deck=[Strike()])
    player._current_hp = 50
    FakeLeesWaffle().on_equip(player)
    assert player.current_hp == 50 + 8  # 80의 10% = 8


_TESTS = [
    test_registry_has_69_relics,
    test_fake_anchor_gains_4_combat_block,
    test_sword_of_jade_gives_3_strength,
    test_phylactery_unbound_summons_osty,
    test_meat_on_the_bone_heals_12_on_victory,
    test_fake_blood_vial_heals_1_first_turn_only,
    test_divine_destiny_gains_7_stars_first_turn,
    test_fake_happy_flower_energy_every_5_turns,
    test_ring_of_the_drake_draw_2_until_turn_3,
    test_paels_blood_draw_1_always,
    test_daughter_of_the_wind_block_on_attack,
    test_game_piece_draws_on_power_play,
    test_power_cell_pulls_two_zero_cost_cards,
    test_max_hp_relics_increase_on_equip,
    test_lees_waffle_heals_to_full,
    test_fake_lees_waffle_heals_10_percent,
]


def main():
    for test in _TESTS:
        test()
        print(f"✅ {test.__name__}")
    print(f"\n✅ S1.M3.B27 전체 테스트 통과! ({len(_TESTS)}개)")


if __name__ == "__main__":
    main()