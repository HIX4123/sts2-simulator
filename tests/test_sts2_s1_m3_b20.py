#!/usr/bin/env python3
"""STS2 S1.M3.B20 회귀 — CeremonialBeast / PlowPower / RingingPower / 인카운터 1종."""
import random

import sts2_sim  # noqa: F401
from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import ENCOUNTERS, make_encounter
from sts2_sim.entities.monsters_batch20 import CeremonialBeast
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import MONSTER_REGISTRY, create_monster
from sts2_sim.models.sts2_card import create_card
from sts2_sim.models.sts2_power import (
    PlowPower, RingingPower, Strength, TempStrength, POWER_REGISTRY,
)


def make_combat(seed=42, player_hp=9999):
    monsters = make_encounter("ceremonial_beast_boss", random.Random(seed))
    player = Player(create_character("ironclad"))
    player._max_hp = player._current_hp = player_hp
    combat = CombatState(player, monsters, seed=seed)
    combat.start()
    return combat, player


def monster_turn(monster, targets):
    monster.start_of_turn()
    for power in list(monster._powers.values()):
        hook = getattr(power, "on_turn_start", None)
        if hook:
            hook()
    monster.take_turn(targets)
    for power in list(monster._powers.values()):
        hook = getattr(power, "on_turn_end", None)
        if hook:
            hook()
    monster.tick_powers()


def test_registry_and_encounter():
    assert MONSTER_REGISTRY["ceremonial_beast"] is CeremonialBeast
    assert POWER_REGISTRY["plow"] is PlowPower
    assert POWER_REGISTRY["ringing"] is RingingPower
    assert "ceremonial_beast_boss" in ENCOUNTERS

    beast = create_monster("ceremonial_beast")
    assert (beast.min_initial_hp, beast.max_initial_hp) == (252, 252)
    assert beast.should_disappear_from_doom is False

    monsters = make_encounter("ceremonial_beast_boss", random.Random(0))
    assert len(monsters) == 1
    assert isinstance(monsters[0], CeremonialBeast)
    assert monsters[0].slot_name is None
    print("✅ 배치20 몬스터·파워 등록 + 보스 인카운터 확인")


def test_first_phase_and_plow_transition():
    combat, player = make_combat()
    beast = combat.monsters[0]
    sm = beast._move_state_machine

    assert beast.current_hp == 252
    assert sm.get_current_move_name() == "STAMP_MOVE"
    monster_turn(beast, [player])
    assert beast.get_power_amount("plow") == 150
    assert sm.get_current_move_name() == "PLOW_MOVE"

    hp_before = player.current_hp
    monster_turn(beast, [player])
    assert player.current_hp == hp_before - 18
    assert beast.get_power_amount("strength") == 2
    assert sm.get_current_move_name() == "PLOW_MOVE"

    # 블록에 전부 막힌 피해는 임계 HP여도 2단계 전이를 일으키지 않는다.
    beast._current_hp = 150
    beast.gain_block(1)
    beast.take_damage(1, source=player)
    assert not beast.is_in_second_phase
    assert sm.get_current_move_name() == "PLOW_MOVE"

    beast._current_hp = 151
    beast._block = 0
    beast.apply_power(Strength(4))
    beast.apply_power(TempStrength(3))
    beast.take_damage(1, source=player)

    assert beast.current_hp == 150
    assert beast.is_in_second_phase
    assert beast.is_stunned_by_plow
    assert sm.get_current_move_name() == "STUNNED"
    assert not beast.has_power("plow")
    assert not beast.has_power("strength")
    assert not beast.has_power("temp_strength")
    print("✅ STAMP→PLOW 반복 + HP 150 Plow 전이·힘 제거·기절 확인")


def test_second_phase_cycle_and_ringing():
    combat, player = make_combat()
    beast = combat.monsters[0]
    monster_turn(beast, [player])  # STAMP
    beast._current_hp = 151
    beast.take_damage(1, source=player)

    assert beast._move_state_machine.get_current_move_name() == "STUNNED"
    hp_before = player.current_hp
    monster_turn(beast, [player])
    assert not beast.is_stunned_by_plow
    assert beast._move_state_machine.get_current_move_name() == "BEAST_CRY_MOVE"
    assert player.current_hp == hp_before

    monster_turn(beast, [player])
    assert player.has_power("ringing")
    assert all(card.ringing for card in combat.draw_pile)
    assert beast._move_state_machine.get_current_move_name() == "STOMP_MOVE"

    hp_before = player.current_hp
    monster_turn(beast, [player])
    assert player.current_hp == hp_before - 15
    assert beast._move_state_machine.get_current_move_name() == "CRUSH_MOVE"

    hp_before = player.current_hp
    monster_turn(beast, [player])
    assert player.current_hp == hp_before - 17
    assert beast.get_power_amount("strength") == 3
    assert beast._move_state_machine.get_current_move_name() == "BEAST_CRY_MOVE"
    print("✅ STUNNED→BEAST_CRY→STOMP→CRUSH 순환과 Ringing 부여 확인")


def test_ringing_card_entry_and_play_limits():
    combat, player = make_combat()
    beast = combat.monsters[0]
    hand_card = create_card("defend")
    draw_card = create_card("strike")
    discard_card = create_card("dazed")
    exhaust_card = create_card("slimed")
    combat.hand = [hand_card]
    combat.draw_pile = [draw_card]
    combat.discard_pile = [discard_card]
    combat.exhaust_pile = [exhaust_card]

    player.apply_power(RingingPower(1), applier=beast)
    assert all(card.ringing for card in (
        hand_card, draw_card, discard_card, exhaust_card))

    generated = combat.generate_card("defend", to="hand")[0]
    shiv = combat.create_shivs(1)[0]
    status = combat.generate_card(
        "burn", creator_is_player=False, to="draw")[0]
    assert generated.ringing and shiv.ringing and status.ringing

    combat.hand = [hand_card, draw_card]
    combat.draw_pile = []
    player.energy = 3
    assert combat.play_card(hand_card)
    assert combat.cards_played_this_turn == 1
    assert not combat.is_card_playable(draw_card)
    assert not combat.play_card(draw_card, beast)

    auto = create_card("strike")
    auto.ringing = True
    combat.auto_play(auto)
    assert auto in combat.discard_pile
    assert combat.cards_played_this_turn == 1
    print("✅ 기존·신규·Shiv·몬스터 Status Ringing + 일반/자동 플레이 차단 확인")


def test_ringing_cleanup():
    combat, player = make_combat()
    beast = combat.monsters[0]
    cards = [create_card("defend"), create_card("strike"),
             create_card("dazed"), create_card("slimed")]
    combat.hand, combat.draw_pile = [cards[0]], [cards[1]]
    combat.discard_pile, combat.exhaust_pile = [cards[2]], [cards[3]]

    power = RingingPower(1)
    player.apply_power(power, applier=beast)
    power.on_turn_end()
    assert not player.has_power("ringing")
    assert not any(card.ringing for card in cards)

    power = RingingPower(1)
    player.apply_power(power, applier=beast)
    power.remove()
    assert not player.has_power("ringing")
    assert not any(card.ringing for card in cards)
    print("✅ Ringing 턴 종료·명시적 제거 시 네 pile 표식 정리 확인")


def test_seeded_smoke():
    for seed in range(5):
        player = Player(create_character("ironclad"))
        combat = CombatState(
            player,
            make_encounter("ceremonial_beast_boss", random.Random(seed)),
            seed=seed,
        )
        result = combat.run(SimplePolicy(), max_turns=100)
        assert isinstance(result.victory, bool)
    print("✅ ceremonial_beast_boss × 5시드 전투 스모크 통과")


def main():
    print("🧪 STS2 S1.M3.B20 회귀\n")
    test_registry_and_encounter()
    test_first_phase_and_plow_transition()
    test_second_phase_cycle_and_ringing()
    test_ringing_card_entry_and_play_limits()
    test_ringing_cleanup()
    test_seeded_smoke()
    print("\n" + "=" * 60)
    print("✅ S1.M3.B20 전체 테스트 통과!")
    print("=" * 60)


if __name__ == "__main__":
    main()
