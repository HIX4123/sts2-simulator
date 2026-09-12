#!/usr/bin/env python3
"""S1.M3.B24 — 렐릭 확장(전투 훅 완전 재현 가능한 15종) 회귀 테스트."""
from sts2_sim.core.combat import CombatState
from sts2_sim.entities.creature import Creature
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import Ironclad
from sts2_sim.entities.sts2_monster import BigDummy
from sts2_sim.models.sts2_card import CardType, STS2Card
from sts2_sim.models.sts2_relic import (
    BagOfMarbles, Brimstone, Candelabra, Chandelier, DataDisk, FestivePopper,
    Kunai, LetterOpener, OrnamentalFan, RainbowRing, RedMask, RunicCapacitor,
    Shuriken, SymbioticVirus, TwistedFunnel, create_relic,
)


class FakeAttack(STS2Card):
    card_type = CardType.ATTACK


class FakeSkill(STS2Card):
    card_type = CardType.SKILL


class FakePower(STS2Card):
    card_type = CardType.POWER


def make_combat(*relics):
    player = Player(Ironclad(), deck=[])
    player.relics = []
    for relic in relics:
        relic.on_equip(player)
        player.relics.append(relic)
    combat = CombatState(player, [BigDummy(), BigDummy()], seed=1)
    return player, combat


def test_bag_of_marbles_and_red_mask_first_turn_only():
    player, combat = make_combat(BagOfMarbles(), RedMask())
    combat.start()
    player.relics[0].on_turn_start(combat, 1)
    player.relics[1].on_turn_start(combat, 1)
    for enemy in combat.alive_enemies:
        assert enemy.get_power_amount("vulnerable") == 1
        assert enemy.get_power_amount("weak") == 1

    player2, combat2 = make_combat(BagOfMarbles())
    combat2.start()
    player2.relics[0].on_turn_start(combat2, 2)  # 2턴째는 미발동
    for enemy in combat2.alive_enemies:
        assert enemy.get_power_amount("vulnerable") == 0


def test_festive_popper_unpowered_damage_first_turn():
    player, combat = make_combat(FestivePopper())
    combat.start()
    player.apply_power(__import__("sts2_sim.models.sts2_power", fromlist=["Strength"]).Strength(5))
    player.relics[0].on_turn_start(combat, 1)
    for enemy in combat.alive_enemies:
        assert enemy.current_hp == enemy.max_hp - 9  # Strength 미반영 = unpowered


def test_data_disk_focus_on_combat_start():
    player, combat = make_combat(DataDisk())
    combat.start()
    assert player.get_power_amount("focus") == 1


def test_candelabra_and_chandelier_exact_turn():
    player, combat = make_combat(Candelabra(), Chandelier())
    combat.start()
    player.energy = 0
    for turn in (1, 2, 3, 4):
        player.relics[0].on_turn_start(combat, turn)
        player.relics[1].on_turn_start(combat, turn)
    assert player.energy == 5  # turn2: +2(Candelabra), turn3: +3(Chandelier)


def test_twisted_funnel_and_symbiotic_virus_first_turn():
    player, combat = make_combat(TwistedFunnel(), SymbioticVirus())
    combat.start()
    player.relics[0].on_turn_start(combat, 1)
    player.relics[1].on_turn_start(combat, 1)
    for enemy in combat.alive_enemies:
        assert enemy.get_power_amount("poison") == 4
    assert len(player.orb_queue.orbs) == 1
    assert player.orb_queue.orbs[0].orb_id == "dark"


def test_runic_capacitor_first_turn_slots():
    player, combat = make_combat(RunicCapacitor())
    combat.start()
    base_slots = player.orb_queue.slot_count
    player.relics[0].on_turn_start(combat, 1)
    assert player.orb_queue.slot_count == base_slots + 3
    player.relics[0].on_turn_start(combat, 2)  # 2턴째 미발동
    assert player.orb_queue.slot_count == base_slots + 3


def test_brimstone_every_turn():
    player, combat = make_combat(Brimstone())
    combat.start()
    player.relics[0].on_turn_start(combat, 1)
    assert player.get_power_amount("strength") == 2
    for enemy in combat.alive_enemies:
        assert enemy.get_power_amount("strength") == 1
    player.relics[0].on_turn_start(combat, 2)
    assert player.get_power_amount("strength") == 4


def test_ornamental_fan_and_letter_opener_and_kunai_and_shuriken_counters():
    player, combat = make_combat(
        OrnamentalFan(), LetterOpener(), Kunai(), Shuriken())
    fan, opener, kunai, shuriken = player.relics
    combat.start()
    for relic in player.relics:
        relic.on_turn_start(combat, 1)

    for _ in range(2):
        card = FakeAttack()
        for relic in player.relics:
            relic.on_card_played(card, combat)
    assert player.block == 0
    assert player.get_power_amount("dexterity") == 0
    assert player.get_power_amount("strength") == 0

    card = FakeAttack()
    for relic in player.relics:
        relic.on_card_played(card, combat)
    assert player.block == 4          # OrnamentalFan 3번째 공격
    assert player.get_power_amount("dexterity") == 1  # Kunai
    assert player.get_power_amount("strength") == 1   # Shuriken

    dummy = combat.alive_enemies[0]
    start_hp = dummy.current_hp
    for _ in range(3):
        skill = FakeSkill()
        opener.on_card_played(skill, combat)
    assert dummy.current_hp == start_hp - 5  # LetterOpener 3번째 스킬


def test_rainbow_ring_requires_all_three_types_once_per_turn():
    player, combat = make_combat(RainbowRing())
    ring = player.relics[0]
    combat.start()
    ring.on_turn_start(combat, 1)

    ring.on_card_played(FakeAttack(), combat)
    ring.on_card_played(FakeSkill(), combat)
    assert player.get_power_amount("strength") == 0
    ring.on_card_played(FakePower(), combat)
    assert player.get_power_amount("strength") == 1
    assert player.get_power_amount("dexterity") == 1

    # 같은 턴에 재발동 없음
    ring.on_card_played(FakeAttack(), combat)
    ring.on_card_played(FakeSkill(), combat)
    ring.on_card_played(FakePower(), combat)
    assert player.get_power_amount("strength") == 1


def test_registry_new_relics():
    expected_common = ("bag_of_marbles", "data_disk", "festive_popper", "red_mask")
    expected_uncommon = ("candelabra", "letter_opener", "ornamental_fan",
                          "symbiotic_virus", "twisted_funnel")
    expected_rare = ("chandelier", "kunai", "rainbow_ring", "shuriken")
    expected_shop = ("brimstone", "runic_capacitor")
    for relic_id in expected_common + expected_uncommon + expected_rare + expected_shop:
        assert create_relic(relic_id) is not None, relic_id


def main():
    tests = [
        test_bag_of_marbles_and_red_mask_first_turn_only,
        test_festive_popper_unpowered_damage_first_turn,
        test_data_disk_focus_on_combat_start,
        test_candelabra_and_chandelier_exact_turn,
        test_twisted_funnel_and_symbiotic_virus_first_turn,
        test_runic_capacitor_first_turn_slots,
        test_brimstone_every_turn,
        test_ornamental_fan_and_letter_opener_and_kunai_and_shuriken_counters,
        test_rainbow_ring_requires_all_three_types_once_per_turn,
        test_registry_new_relics,
    ]
    for test in tests:
        test()
        print(f"✅ {test.__name__}")
    print("\n✅ S1.M3.B24 전체 테스트 통과!")


if __name__ == "__main__":
    main()
