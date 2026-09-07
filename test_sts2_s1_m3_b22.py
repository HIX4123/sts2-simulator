#!/usr/bin/env python3
"""STS2 S1.M3.B22 회귀 — TheAdversary Mk1~Mk3 시험용 몬스터."""
import random

import sts2_sim  # noqa: F401
from sts2_sim.core.combat import CombatState
from sts2_sim.entities.monsters_batch22 import (
    TheAdversaryMkOne, TheAdversaryMkThree, TheAdversaryMkTwo,
)
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import MONSTER_REGISTRY, create_monster


CASES = (
    ("the_adversary_mk_one", TheAdversaryMkOne, 100, 0,
     ("SMASH_MOVE", "BEAM_MOVE", "BARRAGE_MOVE"), (12, 15, 8, 2, 2)),
    ("the_adversary_mk_two", TheAdversaryMkTwo, 200, 1,
     ("BASH_MOVE", "FLAME_BEAM_MOVE", "BARRAGE_MOVE"), (13, 16, 9, 3, 3)),
    ("the_adversary_mk_three", TheAdversaryMkThree, 300, 2,
     ("CRASH_MOVE", "FLAME_BEAM_MOVE", "BARRAGE_MOVE"), (15, 18, 10, 4, 4)),
)


def make_combat(monster_id):
    player = Player(create_character("ironclad"))
    player._max_hp = player._current_hp = 9999
    monster = create_monster(monster_id)
    combat = CombatState(player, [monster], seed=42)
    combat.start()
    return player, monster


def take_turn(monster, player):
    monster.take_turn([player])


def test_registry_setup_and_graphs():
    for monster_id, cls, hp, artifact, moves, _ in CASES:
        assert MONSTER_REGISTRY[monster_id] is cls
        player, monster = make_combat(monster_id)
        assert monster.max_hp == monster.current_hp == hp
        assert monster.get_power_amount("artifact") == artifact
        sm = monster._move_state_machine
        assert tuple(sm.states_by_name) == moves
        assert sm.get_current_move_name() == moves[0]
        for expected in moves[1:] + moves[:1]:
            take_turn(monster, player)
            assert sm.get_current_move_name() == expected
    print("✅ 배치22 registry·HP·Artifact·고정 3무브 순환 확인")


def test_attacks_and_barrage_strength():
    for monster_id, _, _, _, _, values in CASES:
        first_damage, second_damage, barrage_damage, barrage_hits, strength = values
        player, monster = make_combat(monster_id)

        hp = player.current_hp
        take_turn(monster, player)
        assert player.current_hp == hp - first_damage

        hp = player.current_hp
        take_turn(monster, player)
        assert player.current_hp == hp - second_damage

        hp = player.current_hp
        take_turn(monster, player)
        assert player.current_hp == hp - barrage_damage * barrage_hits
        assert monster.get_power_amount("strength") == strength

        # Barrage가 부여한 Strength도 다음 순환의 공용 attack 파이프라인에 반영된다.
        hp = player.current_hp
        take_turn(monster, player)
        assert player.current_hp == hp - first_damage - strength
    print("✅ 단일 공격·다단 공격·후속 Strength 공용 피해 파이프라인 확인")


def main():
    print("🧪 STS2 S1.M3.B22 회귀\n")
    test_registry_setup_and_graphs()
    test_attacks_and_barrage_strength()
    print("\n" + "=" * 60)
    print("✅ S1.M3.B22 전체 테스트 통과!")
    print("=" * 60)


if __name__ == "__main__":
    main()
