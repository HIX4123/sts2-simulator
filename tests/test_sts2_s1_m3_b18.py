#!/usr/bin/env python3
"""STS2 S1.M3.B18 회귀 — Bowlbug 4종 / ImbalancedPower / 인카운터 2종."""
import random

import sts2_sim  # noqa: F401
from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import ENCOUNTERS, make_encounter
from sts2_sim.entities.monsters_batch16 import SlumberingBeetle
from sts2_sim.entities.monsters_batch18 import (
    BowlbugEgg, BowlbugNectar, BowlbugRock, BowlbugSilk,
)
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import MONSTER_REGISTRY, create_monster
from sts2_sim.models.sts2_power import Buffer, ImbalancedPower, POWER_REGISTRY, SuckPower


def make_combat(monsters_or_id, seed=42, player_hp=9999):
    player = Player(create_character("ironclad"))
    player._max_hp = player._current_hp = player_hp
    monsters = (make_encounter(monsters_or_id, random.Random(seed))
                if isinstance(monsters_or_id, str) else monsters_or_id)
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


def test_registry_and_encounters():
    expected = {
        "bowlbug_egg": (BowlbugEgg, 21, 22),
        "bowlbug_nectar": (BowlbugNectar, 35, 38),
        "bowlbug_rock": (BowlbugRock, 45, 48),
        "bowlbug_silk": (BowlbugSilk, 40, 43),
    }
    for monster_id, (cls, min_hp, max_hp) in expected.items():
        assert MONSTER_REGISTRY[monster_id] is cls
        monster = create_monster(monster_id)
        assert (monster.min_initial_hp, monster.max_initial_hp) == (min_hp, max_hp)
    assert POWER_REGISTRY["imbalanced"] is ImbalancedPower
    assert "bowlbugs_weak" in ENCOUNTERS and "bowlbugs_normal" in ENCOUNTERS

    for seed in range(8):
        weak = make_encounter("bowlbugs_weak", random.Random(seed))
        assert [monster.slot_name for monster in weak] == ["odd", "even"]
        assert isinstance(weak[0], BowlbugRock)
        assert isinstance(weak[1], (BowlbugEgg, BowlbugNectar))

        normal = make_encounter("bowlbugs_normal", random.Random(seed))
        assert [monster.slot_name for monster in normal] == ["first", "middle", "last"]
        assert isinstance(normal[0], BowlbugRock)
        assert len({type(normal[1]), type(normal[2])}) == 2
        assert all(isinstance(monster, (BowlbugEgg, BowlbugSilk, BowlbugNectar))
                   for monster in normal[1:])

    beetles = make_encounter("slumbering_beetle_normal", random.Random(0))
    assert [monster.slot_name for monster in beetles] == ["first", "second", "third"]
    assert [type(monster) for monster in beetles] == [
        BowlbugRock, BowlbugSilk, SlumberingBeetle,
    ]
    print("✅ 배치18 몬스터·파워 등록 + 인카운터 구성·슬롯 확인")


def test_egg_and_nectar_cycles():
    combat, player = make_combat([BowlbugEgg()], seed=1)
    egg = combat.alive_enemies[0]
    hp = player.current_hp
    monster_turn(egg, [player])
    assert player.current_hp == hp - 7 and egg.block == 7
    assert egg._move_state_machine.get_current_move_name() == "BITE_MOVE"

    combat, player = make_combat([BowlbugNectar()], seed=2)
    nectar = combat.alive_enemies[0]
    sm = nectar._move_state_machine
    assert sm.get_current_move_name() == "THRASH_MOVE"
    hp = player.current_hp
    monster_turn(nectar, [player])
    assert player.current_hp == hp - 3 and sm.get_current_move_name() == "BUFF_MOVE"
    monster_turn(nectar, [player])
    assert nectar.get_power_amount("strength") == 15
    assert sm.get_current_move_name() == "THRASH2_MOVE"
    hp = player.current_hp
    monster_turn(nectar, [player])
    assert player.current_hp == hp - 18 and sm.get_current_move_name() == "THRASH2_MOVE"
    print("✅ BowlbugEgg 반복 / BowlbugNectar 버프 후 고정 루프 확인")


def test_silk_cycle():
    combat, player = make_combat([BowlbugSilk()], seed=3)
    silk = combat.alive_enemies[0]
    sm = silk._move_state_machine
    assert sm.get_current_move_name() == "TOXIC_SPIT_MOVE"
    monster_turn(silk, [player])
    assert player.get_power_amount("weak") == 1
    assert sm.get_current_move_name() == "THRASH_MOVE"
    hp = player.current_hp
    monster_turn(silk, [player])
    assert player.current_hp == hp - 8, "Silk의 4딜 × 2히트"
    assert sm.get_current_move_name() == "TOXIC_SPIT_MOVE"
    print("✅ BowlbugSilk 독침 시작 + Weak + 2연타 순환 확인")


def test_rock_imbalanced_boundaries():
    combat, player = make_combat([BowlbugRock()], seed=4)
    rock = combat.alive_enemies[0]
    sm = rock._move_state_machine
    assert rock.get_power_amount("imbalanced") == 1
    player.gain_block(15)
    monster_turn(rock, [player])
    assert player.current_hp == player.max_hp
    assert rock.is_off_balance and sm.get_current_move_name() == "DIZZY_MOVE"
    monster_turn(rock, [player])
    assert not rock.is_off_balance and sm.get_current_move_name() == "HEADBUTT_MOVE"

    combat, player = make_combat([BowlbugRock()], seed=5)
    rock = combat.alive_enemies[0]
    player.gain_block(14)
    monster_turn(rock, [player])
    assert player.current_hp == player.max_hp - 1
    assert not rock.is_off_balance

    combat, player = make_combat([BowlbugRock()], seed=6)
    rock = combat.alive_enemies[0]
    player.gain_block(5)
    player.apply_power(Buffer(1))
    monster_turn(rock, [player])
    assert player.current_hp == player.max_hp
    assert not rock.is_off_balance, "Buffer의 HP 손실 0은 완전 블록이 아니다"
    print("✅ BowlbugRock 완전 블록만 off-balance / DIZZY 전환 확인")


def test_generic_imbalanced_stun_and_landed_attack_boundary():
    combat, player = make_combat([BowlbugEgg()], seed=7)
    egg = combat.alive_enemies[0]
    egg.apply_power(ImbalancedPower(1))
    player.gain_block(7)
    monster_turn(egg, [player])
    sm = egg._move_state_machine
    assert sm.get_current_move_name() == "STUNNED"
    assert sm.history[-1] == "BITE_MOVE", "실제로 실행한 무브를 history에 기록해야 한다"
    hp = player.current_hp
    monster_turn(egg, [player])
    assert player.current_hp == hp and sm.get_current_move_name() == "BITE_MOVE"

    combat, player = make_combat([BowlbugEgg()], seed=8)
    egg = combat.alive_enemies[0]
    egg.apply_power(SuckPower(2))
    player.gain_block(7)
    monster_turn(egg, [player])
    assert egg.get_power_amount("strength") == 0, \
        "완전 블록은 기존 on_landed_attack 훅을 발동하면 안 된다"
    print("✅ 일반 Imbalanced 다음 턴 기절 + on_landed_attack 경계 확인")


def test_seeded_smoke():
    for encounter_id in ("bowlbugs_weak", "bowlbugs_normal", "slumbering_beetle_normal"):
        for seed in range(3):
            player = Player(create_character("ironclad"))
            combat = CombatState(player, make_encounter(encounter_id, random.Random(seed)), seed=seed)
            result = combat.run(SimplePolicy(), max_turns=100)
            assert isinstance(result.victory, bool)
    print("✅ 배치18 관련 3인카운터 × 3시드 전투 스모크 통과")


def main():
    print("🧪 STS2 S1.M3.B18 회귀\n")
    test_registry_and_encounters()
    test_egg_and_nectar_cycles()
    test_silk_cycle()
    test_rock_imbalanced_boundaries()
    test_generic_imbalanced_stun_and_landed_attack_boundary()
    test_seeded_smoke()
    print("\n" + "=" * 60)
    print("✅ S1.M3.B18 전체 테스트 통과!")
    print("=" * 60)


if __name__ == "__main__":
    main()
