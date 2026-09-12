#!/usr/bin/env python3
"""S1.M3.B23 — STS2 렐릭 정합성 회귀 테스트."""
from sts2_sim.core.combat import CombatState
from sts2_sim.entities.creature import Creature, Osty
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import Ironclad
from sts2_sim.entities.sts2_monster import BigDummy, SingleAttackMoveMonster
from sts2_sim.models.sts2_power import STS2Power, Thorns
from sts2_sim.models.sts2_relic import (
    Akabeko, Anchor, BagOfPreparation, BloodVial, BronzeScales, Gorget,
    Lantern, MercuryHourglass, OddlySmoothStone, RelicRarity, TungstenRod,
    Vajra, create_relic,
)


class EndTurnPolicy:
    def choose(self, combat):
        return None


class ThreeHpDummy(BigDummy):
    @property
    def min_initial_hp(self):
        return 3

    @property
    def max_initial_hp(self):
        return 3


class TripleHpLoss(STS2Power):
    """TungstenRod보다 늦은 파워 훅 단계 검증용."""
    power_id = "triple_hp_loss"

    def modify_hp_lost(self, amount: int) -> int:
        return amount * 3


def make_combat(*relics, monster=None):
    player = Player(Ironclad(), deck=[])
    player.relics = []
    for relic in relics:
        relic.on_equip(player)
        player.relics.append(relic)
    combat = CombatState(player, [monster or BigDummy()], seed=1)
    return player, combat


def test_tungsten_rod_stage_and_owner_scope():
    player, _ = make_combat(TungstenRod())
    player.apply_power(TripleHpLoss(1))
    assert player.lose_hp(5) == 12  # (5 - 1) × 3: 렐릭이 Late 파워보다 먼저
    assert player.lose_hp(1) == 0

    enemy = Creature("Enemy", 20)
    assert enemy.lose_hp(5) == 5
    osty = Osty(20, owner=player)
    assert osty.lose_hp(5) == 5


def test_anchor_and_gorget_block_timing():
    player, combat = make_combat(Anchor())
    combat.start()
    assert player.block == 10
    player.start_of_turn(clear_block=False)
    assert player.block == 10
    player.start_of_turn(clear_block=True)
    assert player.block == 0

    player, combat = make_combat(Gorget())
    combat.start()
    assert player.block == 0
    player._powers["plating"].on_turn_end()
    assert player.block == 4


def test_combat_loop_preserves_first_turn_block():
    player, combat = make_combat(Anchor())
    result = combat.run(EndTurnPolicy(), max_turns=1)
    assert not result.victory
    assert player.block == 10


def test_common_combat_start_relics():
    player, combat = make_combat(OddlySmoothStone(), Anchor(), Vajra())
    combat.start()
    assert player.get_power_amount("dexterity") == 1
    assert player.get_power_amount("strength") == 1
    assert player.block == 10  # 렐릭의 언파워드 블록에는 Dexterity 미적용
    assert player.compute_attack_damage(6) == 7


def test_first_turn_relics():
    assert BagOfPreparation().modify_hand_draw(5, 1) == 7
    assert BagOfPreparation().modify_hand_draw(5, 2) == 5

    player, combat = make_combat(BloodVial(), Lantern(), Akabeko())
    player._current_hp -= 1
    player.energy = 3
    for relic in player.relics:
        relic.on_turn_start(combat, 1)
    assert player.current_hp == player.max_hp
    assert player.energy == 4
    assert player.get_power_amount("vigor") == 8

    enemy = Creature("Enemy", 30)
    enemy.take_damage(player.compute_attack_damage(6), source=player)
    assert enemy.current_hp == 16
    assert player.get_power_amount("vigor") == 0

    player.energy = 3
    player._current_hp -= 3
    for relic in player.relics:
        relic.on_turn_start(combat, 2)
    assert player.current_hp == player.max_hp - 3
    assert player.energy == 3
    assert player.get_power_amount("vigor") == 0


def test_mercury_hourglass_is_unpowered_and_can_win():
    enemy = ThreeHpDummy()
    enemy.apply_power(Thorns(9))
    player, combat = make_combat(MercuryHourglass(), monster=enemy)
    result = combat.run(EndTurnPolicy(), max_turns=1)
    assert result.victory
    assert player.current_hp == player.max_hp


def test_bronze_scales_only_reflects_powered_attacks():
    player, combat = make_combat(BronzeScales())
    combat.start()
    assert player.get_power_amount("thorns") == 3

    powered = SingleAttackMoveMonster()
    powered._max_hp = powered._current_hp = 10
    powered.attack(player, 1)
    assert powered.current_hp == 7

    unpowered = Creature("Unpowered", 20)
    player.take_damage(1, source=unpowered, powered=False)
    assert unpowered.current_hp == 20


def test_registry_removes_fabricated_relics():
    expected = {
        "anchor": RelicRarity.COMMON,
        "bag_of_preparation": RelicRarity.COMMON,
        "blood_vial": RelicRarity.COMMON,
        "bronze_scales": RelicRarity.COMMON,
        "gorget": RelicRarity.COMMON,
        "lantern": RelicRarity.COMMON,
        "oddly_smooth_stone": RelicRarity.COMMON,
        "vajra": RelicRarity.COMMON,
        "akabeko": RelicRarity.UNCOMMON,
        "mercury_hourglass": RelicRarity.UNCOMMON,
        "tungsten_rod": RelicRarity.RARE,
    }
    for relic_id, rarity in expected.items():
        relic = create_relic(relic_id)
        assert relic is not None and relic.rarity == rarity

    removed = (
        "bronze_scale", "burning_skull", "centipede", "cloak", "courier",
        "dream_catcher", "enchanter_mask", "fossilized_helix", "matryoshka",
        "ornithopter", "runic", "spiked_defense",
    )
    for relic_id in removed:
        assert create_relic(relic_id) is None


def main():
    tests = [
        test_tungsten_rod_stage_and_owner_scope,
        test_anchor_and_gorget_block_timing,
        test_combat_loop_preserves_first_turn_block,
        test_common_combat_start_relics,
        test_first_turn_relics,
        test_mercury_hourglass_is_unpowered_and_can_win,
        test_bronze_scales_only_reflects_powered_attacks,
        test_registry_removes_fabricated_relics,
    ]
    for test in tests:
        test()
        print(f"✅ {test.__name__}")
    print("\n✅ S1.M3.B23 전체 테스트 통과!")


if __name__ == "__main__":
    main()
