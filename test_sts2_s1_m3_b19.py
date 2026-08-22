#!/usr/bin/env python3
"""STS2 S1.M3.B19 회귀 — Kaiser Crab 보스 / 전용 파워 4종."""
import random
import subprocess
import sys

import sts2_sim  # noqa: F401
from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import ENCOUNTERS, ENCOUNTER_SLOTS, make_encounter
from sts2_sim.entities.monsters_batch19 import Crusher, Rocket
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import MONSTER_REGISTRY, create_monster
from sts2_sim.models.sts2_power import (
    BackAttackLeftPower,
    BackAttackRightPower,
    CrabRagePower,
    Doom,
    Frail,
    POWER_REGISTRY,
    SurroundedPower,
)


def make_combat(monsters_or_id="kaiser_crab_boss", seed=42, player_hp=9999):
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


def test_registry_encounter_and_opening_state():
    registry_probe = subprocess.run(
        [sys.executable, "-c", (
            "import sts2_sim; "
            "from sts2_sim.entities.sts2_monster import MONSTER_REGISTRY; "
            "assert 'crusher' in MONSTER_REGISTRY and 'rocket' in MONSTER_REGISTRY"
        )],
        check=False,
        capture_output=True,
        text=True,
    )
    assert registry_probe.returncode == 0, registry_probe.stderr

    expected_monsters = {
        "crusher": (Crusher, 209),
        "rocket": (Rocket, 199),
    }
    for monster_id, (cls, hp) in expected_monsters.items():
        assert MONSTER_REGISTRY[monster_id] is cls
        monster = create_monster(monster_id)
        assert (monster.min_initial_hp, monster.max_initial_hp) == (hp, hp)

    expected_powers = {
        "back_attack_left": BackAttackLeftPower,
        "back_attack_right": BackAttackRightPower,
        "crab_rage": CrabRagePower,
        "surrounded": SurroundedPower,
    }
    for power_id, cls in expected_powers.items():
        assert POWER_REGISTRY[power_id] is cls

    assert "kaiser_crab_boss" in ENCOUNTERS
    assert ENCOUNTER_SLOTS["kaiser_crab_boss"] == ["crusher", "rocket"]
    combat, player = make_combat(seed=1)
    crusher, rocket = combat.monsters
    assert [type(crusher), type(rocket)] == [Crusher, Rocket]
    assert [crusher.slot_name, rocket.slot_name] == ["crusher", "rocket"]
    assert [crusher.current_hp, rocket.current_hp] == [209, 199]
    assert crusher.has_power("back_attack_left") and crusher.has_power("crab_rage")
    assert rocket.has_power("back_attack_right") and rocket.has_power("crab_rage")
    surrounded = player._powers["surrounded"]
    assert surrounded.facing == "right"
    print("✅ Kaiser Crab 등록·슬롯·HP·개전 파워 확인")


def test_fixed_move_cycles():
    combat, player = make_combat(seed=2)
    crusher = combat.monsters[0]
    crusher_moves = [
        "THRASH_MOVE",
        "ENLARGING_STRIKE_MOVE",
        "BUG_STING_MOVE",
        "ADAPT_MOVE",
        "GUARDED_STRIKE_MOVE",
        "THRASH_MOVE",
    ]
    assert crusher._move_state_machine.get_current_move_name() == crusher_moves[0]
    hp = player.current_hp
    expected_losses = [18, 6, 18, 0, 21]
    for expected_loss, next_move in zip(expected_losses, crusher_moves[1:]):
        before = player.current_hp
        monster_turn(crusher, [player])
        assert before - player.current_hp == expected_loss
        assert crusher._move_state_machine.get_current_move_name() == next_move
    assert hp - player.current_hp == sum(expected_losses)
    assert player.get_power_amount("weak") == 2
    assert player.get_power_amount("frail") == 2
    assert crusher.get_power_amount("strength") == 2
    assert crusher.block == 18

    combat, player = make_combat(seed=3)
    rocket = combat.monsters[1]
    rocket_moves = [
        "TARGETING_RETICLE_MOVE",
        "PRECISION_BEAM_MOVE",
        "CHARGE_UP_MOVE",
        "LASER_MOVE",
        "RECHARGE_MOVE",
        "TARGETING_RETICLE_MOVE",
    ]
    assert rocket._move_state_machine.get_current_move_name() == rocket_moves[0]
    expected_losses = [3, 18, 0, 33, 0]
    for expected_loss, next_move in zip(expected_losses, rocket_moves[1:]):
        before = player.current_hp
        monster_turn(rocket, [player])
        assert before - player.current_hp == expected_loss
        assert rocket._move_state_machine.get_current_move_name() == next_move
    assert rocket.get_power_amount("strength") == 2
    print("✅ Crusher/Rocket 고정 5무브 순환과 수치 확인")


def test_surrounded_powered_and_unpowered_damage():
    combat, player = make_combat(seed=4)
    crusher, rocket = combat.monsters

    hp = player.current_hp
    player.take_damage(12, source=crusher, powered=True)
    assert hp - player.current_hp == 18
    hp = player.current_hp
    player.take_damage(12, source=crusher, powered=False)
    assert hp - player.current_hp == 18, "원본 Surrounded에는 IsPoweredAttack 게이트가 없다"
    hp = player.current_hp
    player.take_damage(12, source=rocket, powered=True)
    assert hp - player.current_hp == 12
    print("✅ Surrounded 기본 방향 + powered/unpowered 1.5배 경계 확인")


def test_crab_rage_and_direction_after_death():
    combat, player = make_combat(seed=5)
    crusher, rocket = combat.monsters
    crusher.apply_power(Frail(2))
    rocket._current_hp = 0
    combat.reap_deaths()

    assert crusher.get_power_amount("strength") == 6
    assert crusher.block == 99, "Crab Rage 블록은 Unpowered라 Frail의 영향을 받지 않는다"
    assert not crusher.has_power("crab_rage")
    assert player._powers["surrounded"].facing == "left"
    hp = player.current_hp
    player.take_damage(12, source=crusher)
    assert hp - player.current_hp == 12, "남은 Crusher를 바라보면 back-attack 배율이 해제된다"

    combat, player = make_combat(seed=6)
    crusher, rocket = combat.monsters
    crusher._current_hp = 0
    combat.reap_deaths()
    assert rocket.get_power_amount("strength") == 6
    assert rocket.block == 99 and not rocket.has_power("crab_rage")
    assert player._powers["surrounded"].facing == "right"
    print("✅ 동료 사망 Crab Rage + Surrounded 방향 갱신 확인")


def test_doom_immunity():
    combat, _ = make_combat(seed=7)
    for monster in combat.monsters:
        monster.apply_power(Doom(999))
    combat._trigger_doom()
    assert all(not monster.is_dead for monster in combat.monsters)
    print("✅ Crusher/Rocket ShouldDisappearFromDoom=false 확인")


def test_seeded_smoke():
    for seed in range(3):
        player = Player(create_character("ironclad"))
        combat = CombatState(
            player,
            make_encounter("kaiser_crab_boss", random.Random(seed)),
            seed=seed,
        )
        result = combat.run(SimplePolicy(), max_turns=100)
        assert isinstance(result.victory, bool)
    print("✅ Kaiser Crab 보스 3시드 전투 스모크 통과")


def main():
    print("🧪 STS2 S1.M3.B19 회귀\n")
    test_registry_encounter_and_opening_state()
    test_fixed_move_cycles()
    test_surrounded_powered_and_unpowered_damage()
    test_crab_rage_and_direction_after_death()
    test_doom_immunity()
    test_seeded_smoke()
    print("\n" + "=" * 60)
    print("✅ S1.M3.B19 전체 테스트 통과!")
    print("=" * 60)


if __name__ == "__main__":
    main()
