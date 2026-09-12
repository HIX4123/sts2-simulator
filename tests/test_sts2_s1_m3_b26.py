#!/usr/bin/env python3
"""S1.M3.B26 — 기존 전투 훅으로 완전 재현 가능한 렐릭 4종 회귀 테스트."""
from sts2_sim.core.combat import CombatState
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import Ironclad
from sts2_sim.entities.sts2_monster import BigDummy
from sts2_sim.models.sts2_card import CardType, Defend, Slimed, Strike, STS2Card, Wound
from sts2_sim.models.sts2_relic import (
    RELIC_REGISTRY, ArtOfWar, Permafrost, RazorTooth, StoneCracker,
)


class FakePower(STS2Card):
    card_type = CardType.POWER


def make_combat(relic, deck=None, seed=1):
    player = Player(Ironclad(), deck=deck or [])
    relic.on_equip(player)
    player.relics = [relic]
    return player, CombatState(player, [BigDummy()], seed=seed)


def test_registry_has_50_relics():
    assert len(RELIC_REGISTRY) == 50
    for relic_id in ("art_of_war", "permafrost", "razor_tooth", "stone_cracker"):
        assert relic_id in RELIC_REGISTRY


def test_permafrost_first_power_each_combat_only():
    player, combat = make_combat(Permafrost())
    relic = player.relics[0]
    combat.start()
    relic.on_card_played(FakePower(), combat)
    assert player.block == 7
    relic.on_card_played(FakePower(), combat)
    assert player.block == 7
    relic.on_card_played(Defend(), combat)
    assert player.block == 7
    relic.on_combat_start(combat)
    relic.on_card_played(FakePower(), combat)
    assert player.block == 14


def test_art_of_war_tracks_previous_turn_attacks():
    player, combat = make_combat(ArtOfWar())
    relic = player.relics[0]
    combat.start()
    player.energy = 0
    relic.on_turn_start(combat, 1)
    relic.on_card_played(Strike(), combat)
    relic.on_turn_start(combat, 2)
    assert player.energy == 0
    relic.on_turn_start(combat, 3)
    assert player.energy == 1


def test_razor_tooth_upgrades_attacks_and_skills_once():
    player, combat = make_combat(RazorTooth())
    relic = player.relics[0]
    attack, skill, power = Strike(), Defend(), FakePower()
    relic.on_card_played(attack, combat)
    relic.on_card_played(skill, combat)
    relic.on_card_played(power, combat)
    assert attack.upgraded and attack.times_upgraded == 1
    assert skill.upgraded and skill.times_upgraded == 1
    assert not power.upgraded
    relic.on_card_played(attack, combat)
    assert attack.times_upgraded == 1


def test_stone_cracker_upgrades_two_seeded_draw_pile_cards():
    deck = [Strike(), Strike(), Defend(), Defend()]
    player, combat = make_combat(StoneCracker(), deck=deck, seed=7)
    combat.start()
    assert sum(card.upgraded for card in combat.draw_pile) == 2


def test_non_upgradable_status_and_slimed_draw():
    wound, slimed = Wound(), Slimed()
    assert not wound.is_upgradable and not slimed.is_upgradable
    wound.upgrade()
    assert not wound.upgraded and wound.times_upgraded == 0
    player, combat = make_combat(StoneCracker(), deck=[Strike()])
    combat.draw_pile = [Defend()]
    slimed.use(player, [], combat)
    assert len(combat.hand) == 1 and isinstance(combat.hand[0], Defend)


def test_stone_cracker_skips_non_upgradable_cards():
    deck = [Strike(), Strike(), Wound()]
    deck[0].upgrade()
    player, combat = make_combat(StoneCracker(), deck=deck, seed=7)
    combat.start()
    assert deck[0].times_upgraded == 1
    assert deck[1].upgraded
    assert not deck[2].upgraded and deck[2].times_upgraded == 0


_TESTS = [
    test_registry_has_50_relics,
    test_permafrost_first_power_each_combat_only,
    test_art_of_war_tracks_previous_turn_attacks,
    test_razor_tooth_upgrades_attacks_and_skills_once,
    test_stone_cracker_upgrades_two_seeded_draw_pile_cards,
    test_non_upgradable_status_and_slimed_draw,
    test_stone_cracker_skips_non_upgradable_cards,
]


def main():
    for test in _TESTS:
        test()
        print(f"✅ {test.__name__}")
    print(f"\n✅ S1.M3.B26 전체 테스트 통과! ({len(_TESTS)}개)")


if __name__ == "__main__":
    main()
