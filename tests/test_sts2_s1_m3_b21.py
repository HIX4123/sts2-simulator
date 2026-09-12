#!/usr/bin/env python3
"""STS2 S1.M3.B21 회귀 — KnowledgeDemon·선택 Status 4종·파워 4종·인카운터."""
import random

import sts2_sim  # noqa: F401
from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import ENCOUNTERS, make_encounter
from sts2_sim.entities.monsters_batch21 import KnowledgeDemon
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import MONSTER_REGISTRY, create_monster
from sts2_sim.models.sts2_card import CARD_REGISTRY, CardType, Rarity, create_card
from sts2_sim.models.sts2_power import (
    DisintegrationPower, MindRotPower, POWER_REGISTRY, SlothPower,
    Strength, WasteAwayPower,
)


def make_combat(seed=42, player_hp=9999):
    player = Player(create_character("ironclad"))
    player._max_hp = player._current_hp = player_hp
    combat = CombatState(
        player, make_encounter("knowledge_demon_boss", random.Random(seed)), seed=seed)
    combat.start()
    return combat, player, combat.monsters[0]


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


def force_move(monster, name):
    sm = monster._move_state_machine
    sm.force_current_state(sm.states_by_name[name])


def test_registry_cards_and_encounter():
    assert MONSTER_REGISTRY["knowledge_demon"] is KnowledgeDemon
    assert "knowledge_demon_boss" in ENCOUNTERS
    assert tuple(POWER_REGISTRY[c] for c in (
        "disintegration", "mind_rot", "sloth", "waste_away")) == (
        DisintegrationPower, MindRotPower, SlothPower, WasteAwayPower)
    for card_id in ("disintegration", "mind_rot", "sloth", "waste_away"):
        assert card_id in CARD_REGISTRY
        card = create_card(card_id)
        assert card.card_type is CardType.STATUS
        assert card.rarity is Rarity.TOKEN
        assert card.cost == -1 and not card.playable

    demon = create_monster("knowledge_demon")
    assert (demon.min_initial_hp, demon.max_initial_hp) == (379, 379)
    assert not demon.should_disappear_from_doom
    monsters = make_encounter("knowledge_demon_boss", random.Random(0))
    assert len(monsters) == 1 and isinstance(monsters[0], KnowledgeDemon)
    print("✅ 배치21 몬스터·카드·파워·인카운터 등록 확인")


def test_curse_sets_and_disintegration_values():
    expected_sets = (
        {"disintegration", "mind_rot"},
        {"disintegration", "sloth"},
        {"disintegration", "waste_away"},
    )
    seen = [set(), set(), set()]
    disintegration_amounts = set()
    for index in range(3):
        for seed in range(64):
            combat, player, demon = make_combat(seed)
            demon._curse_of_knowledge_counter = index
            force_move(demon, "CURSE_OF_KNOWLEDGE_MOVE")
            before = {card_id: player.get_power_amount(card_id)
                      for card_id in expected_sets[index]}
            monster_turn(demon, [player])
            changed = {
                card_id for card_id in expected_sets[index]
                if player.get_power_amount(card_id) > before[card_id]
            }
            assert len(changed) == 1
            seen[index].update(changed)
            if "disintegration" in changed:
                disintegration_amounts.add(
                    player.get_power_amount("disintegration")
                    - before["disintegration"])
    assert seen == [
        {"disintegration", "mind_rot"},
        {"disintegration", "sloth"},
        {"disintegration", "waste_away"},
    ]
    assert disintegration_amounts == {6, 7, 8}

    _, player, demon = make_combat()
    demon._curse_of_knowledge_counter = 2
    force_move(demon, "CURSE_OF_KNOWLEDGE_MOVE")
    monster_turn(demon, [player])
    assert demon._curse_of_knowledge_counter == 3
    force_move(demon, "PONDER_MOVE")
    monster_turn(demon, [player])
    assert demon._move_state_machine.get_current_move_name() == "SLAP_MOVE"

    # 각 회차 Disintegration 동적 값은 선택 카드 자체를 통해 정확히 적용된다.
    for amount in (6, 7, 8):
        _, player, _ = make_combat()
        create_card("disintegration").on_chosen(player, amount)
        assert player.get_power_amount("disintegration") == amount
    print("✅ 3개 저주 후보 세트·Disintegration 6/7/8·세 번째 이후 분기 확인")


def test_attack_cycle_and_ponder():
    _, player, demon = make_combat()
    demon.apply_power(Strength(2))

    force_move(demon, "SLAP_MOVE")
    hp = player.current_hp
    monster_turn(demon, [player])
    assert player.current_hp == hp - 19
    assert demon._move_state_machine.get_current_move_name() == \
        "KNOWLEDGE_OVERWHELMING_MOVE"

    hp = player.current_hp
    monster_turn(demon, [player])
    assert player.current_hp == hp - 10 * 3
    assert demon.is_burnt
    assert demon._move_state_machine.get_current_move_name() == "PONDER_MOVE"

    demon._current_hp = 300
    demon._curse_of_knowledge_counter = 3
    hp = player.current_hp
    monster_turn(demon, [player])
    assert player.current_hp == hp - 13
    assert demon.current_hp == 330
    assert demon.get_power_amount("strength") == 4
    assert not demon.is_burnt
    assert demon._move_state_machine.get_current_move_name() == "SLAP_MOVE"
    print("✅ 공용 공격 파이프라인·3연타·Ponder 회복/힘·조건 분기 확인")


def test_power_hooks():
    combat, player, demon = make_combat()
    combat.cards_played_this_turn = 0
    combat.attacks_played_this_turn = 0
    combat.skills_played_this_turn = 0

    player.gain_block(2)
    player.apply_power(DisintegrationPower(6), applier=player)
    hp = player.current_hp
    player._powers["disintegration"].on_turn_end()
    assert player.current_hp == hp - 4 and player.block == 0

    player.apply_power(MindRotPower(2), applier=player)
    assert player._powers["mind_rot"].modify_hand_draw(5) == 3
    assert player._powers["mind_rot"].modify_hand_draw(1) == 0

    player.apply_power(SlothPower(2), applier=player)
    player.energy = 9
    combat.hand = [create_card("defend"), create_card("defend"), create_card("strike")]
    assert combat.play_card(combat.hand[0])
    assert combat.play_card(combat.hand[0])
    assert not combat.is_card_playable(combat.hand[0])
    auto = create_card("strike")
    combat.auto_play(auto)
    assert auto in combat.discard_pile
    player._powers["sloth"].on_turn_start()
    assert combat.is_card_playable(combat.hand[0])

    player.apply_power(WasteAwayPower(1), applier=player)
    base_max = player.max_energy
    # 실제 run의 턴 에너지 reset과 같은 비파괴 계산을 두 번 수행한다.
    for _ in range(2):
        effective = player.max_energy
        for power in player._powers.values():
            modify = getattr(power, "modify_max_energy", None)
            if modify:
                effective = modify(effective)
        player.energy = max(0, effective)
        assert player.energy == base_max - 1
        assert player.max_energy == base_max
    print("✅ Disintegration/MindRot/Sloth/WasteAway 공용 hook 확인")


def test_seeded_smoke():
    for seed in range(5):
        player = Player(create_character("ironclad"))
        combat = CombatState(
            player,
            make_encounter("knowledge_demon_boss", random.Random(seed)),
            seed=seed,
        )
        result = combat.run(SimplePolicy(), max_turns=100)
        assert isinstance(result.victory, bool)
    print("✅ knowledge_demon_boss × 5시드 전투 스모크 통과")


def main():
    print("🧪 STS2 S1.M3.B21 회귀\n")
    test_registry_cards_and_encounter()
    test_curse_sets_and_disintegration_values()
    test_attack_cycle_and_ponder()
    test_power_hooks()
    test_seeded_smoke()
    print("\n" + "=" * 60)
    print("✅ S1.M3.B21 전체 테스트 통과!")
    print("=" * 60)


if __name__ == "__main__":
    main()
