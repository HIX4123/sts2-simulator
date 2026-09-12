#!/usr/bin/env python3
"""STS2 S1.M3.B19 회귀 — Crusher / Rocket / 카이저 크랩 보스 파워 4종 / 인카운터 1종."""
import random

import sts2_sim  # noqa: F401
from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import ENCOUNTERS, make_encounter
from sts2_sim.entities.monsters_batch19 import Crusher, Rocket
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import MONSTER_REGISTRY, create_monster
from sts2_sim.models.sts2_power import (
    BackAttackLeftPower, BackAttackRightPower,
    CrabRagePower, SurroundedPower,
    POWER_REGISTRY,
)


def make_combat(seed=42, player_hp=9999):
    monsters = make_encounter("kaiser_crab_boss", random.Random(seed))
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
    assert MONSTER_REGISTRY["crusher"] is Crusher
    assert MONSTER_REGISTRY["rocket"] is Rocket
    assert POWER_REGISTRY["back_attack_left"] is BackAttackLeftPower
    assert POWER_REGISTRY["back_attack_right"] is BackAttackRightPower
    assert POWER_REGISTRY["crab_rage"] is CrabRagePower
    assert POWER_REGISTRY["surrounded"] is SurroundedPower
    assert "kaiser_crab_boss" in ENCOUNTERS

    c = create_monster("crusher")
    r = create_monster("rocket")
    assert (c.min_initial_hp, c.max_initial_hp) == (209, 209)
    assert (r.min_initial_hp, r.max_initial_hp) == (199, 199)
    assert c.should_disappear_from_doom is False
    assert r.should_disappear_from_doom is False

    monsters = make_encounter("kaiser_crab_boss", random.Random(0))
    assert len(monsters) == 2
    assert [m.slot_name for m in monsters] == ["crusher", "rocket"]
    assert isinstance(monsters[0], Crusher)
    assert isinstance(monsters[1], Rocket)
    print("✅ 배치19 몬스터·파워 등록 + 인카운터 구성·슬롯 확인")


def test_opening_powers():
    """전투 시작 시 개전 파워가 올바르게 붙는다."""
    combat, player = make_combat()
    crusher, rocket = combat.monsters

    assert crusher.has_power("back_attack_left"), "Crusher에 BackAttackLeft"
    assert crusher.has_power("crab_rage"), "Crusher에 CrabRage"
    assert not crusher.has_power("back_attack_right")
    assert not crusher.has_power("surrounded")

    assert rocket.has_power("back_attack_right"), "Rocket에 BackAttackRight"
    assert rocket.has_power("crab_rage"), "Rocket에 CrabRage"
    assert not rocket.has_power("back_attack_left")

    assert player.has_power("surrounded"), "플레이어에 Surrounded"
    print("✅ 개전 파워 배치 확인")


def test_surrounded_power_1_5x():
    """SurroundedPower — facing=right 기본값: Crusher(back_attack_left) 파워드 공격 ×1.5.
    Rocket 공격과 비파워드(unpowered) 공격은 배율 없음."""
    combat, player = make_combat()
    crusher, rocket = combat.monsters

    result = player.take_damage(10, source=crusher, powered=True)
    assert result["hp_lost"] == 15, f"Crusher 파워드 10 → 15 기대, got {result['hp_lost']}"

    result_up = player.take_damage(10, source=crusher, powered=False)
    assert result_up["hp_lost"] == 10, "비파워드는 배율 미적용"

    result_rocket = player.take_damage(10, source=rocket, powered=True)
    assert result_rocket["hp_lost"] == 10, "Rocket은 facing=right 시 등이 아님"
    print("✅ SurroundedPower ×1.5 (Crusher 파워드만) 확인")


def test_crab_rage_on_ally_death():
    """CrabRagePower — 같은 편 사망 시 생존자에 힘+6, 블록99(unpowered), 본인은 제거."""
    combat, player = make_combat()
    crusher, rocket = combat.monsters

    # Crusher를 강제 사망 처리 후 _broadcast_death 트리거
    crusher._current_hp = 0
    crusher._is_dead = True
    combat._broadcast_death(crusher)

    assert rocket.get_power_amount("strength") == 6, "폭주 후 힘 +6"
    assert rocket._block == 99, "폭주 후 블록 99"
    assert "crab_rage" not in rocket._powers, "CrabRage는 1회 발동 후 제거"

    # Crusher의 CrabRage는 자신이 죽었으므로 발동하지 않음
    assert "crab_rage" not in crusher._powers or crusher._is_dead
    print("✅ CrabRage 사망 폭주 — 힘+6/블록99/파워 제거 확인")


def test_crab_rage_block_unpowered():
    """CrabRage로 얻는 블록 99는 unpowered — 허약(Frail) 배율 영향을 받지 않는다."""
    from sts2_sim.models.sts2_power import Frail
    combat, player = make_combat()
    crusher, rocket = combat.monsters

    rocket.apply_power(Frail(2))

    crusher._current_hp = 0
    crusher._is_dead = True
    combat._broadcast_death(crusher)

    assert rocket._block == 99, "unpowered 블록은 Frail 무시"
    print("✅ CrabRage 블록 99 — Frail 영향 없음(unpowered) 확인")


def test_crusher_move_cycle():
    """Crusher 5무브 고정 순환 — THRASH→ENLARGING→BUG_STING→ADAPT→GUARDED→THRASH."""
    combat, player = make_combat()
    crusher = combat.monsters[0]
    sm = crusher._move_state_machine

    sequence = [
        "THRASH_MOVE",
        "ENLARGING_STRIKE_MOVE",
        "BUG_STING_MOVE",
        "ADAPT_MOVE",
        "GUARDED_STRIKE_MOVE",
        "THRASH_MOVE",  # 두 번째 순환 진입 확인
    ]
    for i, expected in enumerate(sequence):
        assert sm.get_current_move_name() == expected, \
            f"step {i}: got {sm.get_current_move_name()!r}, expected {expected!r}"
        monster_turn(crusher, [player])
    print("✅ Crusher 5무브 고정 순환 확인")


def test_crusher_bug_sting_debuff():
    """BUG_STING_MOVE — 2히트(SurroundedPower ×1.5 포함) + 약화2 + 허약2."""
    combat, player = make_combat()
    crusher = combat.monsters[0]
    sm = crusher._move_state_machine

    # THRASH → ENLARGING 건너뛰기
    monster_turn(crusher, [player])  # THRASH
    monster_turn(crusher, [player])  # ENLARGING

    assert sm.get_current_move_name() == "BUG_STING_MOVE"
    hp_before = player.current_hp
    monster_turn(crusher, [player])  # BUG_STING

    assert player.get_power_amount("weak") == 2
    assert player.get_power_amount("frail") == 2
    # SurroundedPower(facing=right)가 Crusher 공격을 ×1.5 적용 — int(6*1.5)*2 = 18
    per_hit = int(crusher.bug_sting_damage * 1.5)
    assert player.current_hp == hp_before - per_hit * crusher.bug_sting_times
    print("✅ Crusher BUG_STING: 2히트(×1.5) + 약화2 + 허약2 확인")


def test_crusher_adapt_and_guarded():
    """ADAPT_MOVE — 힘+2; GUARDED_STRIKE_MOVE — 공격 + 블록18."""
    combat, player = make_combat()
    crusher = combat.monsters[0]

    for _ in range(3):  # THRASH, ENLARGING, BUG_STING
        monster_turn(crusher, [player])

    assert crusher._move_state_machine.get_current_move_name() == "ADAPT_MOVE"
    monster_turn(crusher, [player])
    assert crusher.get_power_amount("strength") == 2

    assert crusher._move_state_machine.get_current_move_name() == "GUARDED_STRIKE_MOVE"
    block_before = crusher._block
    monster_turn(crusher, [player])
    assert crusher._block == block_before + 18
    print("✅ Crusher ADAPT(힘+2) + GUARDED_STRIKE(블록18) 확인")


def test_rocket_move_cycle():
    """Rocket 5무브 고정 순환 — RETICLE→BEAM→CHARGE→LASER→RECHARGE→RETICLE."""
    combat, player = make_combat(seed=1)
    rocket = combat.monsters[1]
    sm = rocket._move_state_machine

    sequence = [
        "TARGETING_RETICLE_MOVE",
        "PRECISION_BEAM_MOVE",
        "CHARGE_UP_MOVE",
        "LASER_MOVE",
        "RECHARGE_MOVE",
        "TARGETING_RETICLE_MOVE",
    ]
    for i, expected in enumerate(sequence):
        assert sm.get_current_move_name() == expected, \
            f"step {i}: got {sm.get_current_move_name()!r}, expected {expected!r}"
        monster_turn(rocket, [player])
    print("✅ Rocket 5무브 고정 순환 확인")


def test_rocket_charge_and_recharge():
    """CHARGE_UP_MOVE — 힘+2; RECHARGE_MOVE — 무행동(HP/블록 변화 없음)."""
    combat, player = make_combat(seed=2)
    rocket = combat.monsters[1]

    for _ in range(2):  # RETICLE, BEAM
        monster_turn(rocket, [player])

    assert rocket._move_state_machine.get_current_move_name() == "CHARGE_UP_MOVE"
    monster_turn(rocket, [player])
    assert rocket.get_power_amount("strength") == 2

    assert rocket._move_state_machine.get_current_move_name() == "LASER_MOVE"
    monster_turn(rocket, [player])  # LASER

    assert rocket._move_state_machine.get_current_move_name() == "RECHARGE_MOVE"
    block_before = rocket._block
    hp_before = player.current_hp
    monster_turn(rocket, [player])  # RECHARGE — 무행동
    assert player.current_hp == hp_before, "RECHARGE는 피해 없음"
    assert rocket._block == block_before, "RECHARGE는 블록 없음"
    print("✅ Rocket CHARGE(힘+2) + RECHARGE(무행동) 확인")


def test_surrounded_crusher_death_keeps_facing():
    """SurroundedPower.on_any_death — Crusher(back_attack_left, 등 뒤) 사망 시.
    원본 UpdateDirection: facing=Right에서 대상이 back_attack_LEFT일 때만 Left로 돈다.
    남은 Rocket은 back_attack_RIGHT(정면)이므로 방향은 그대로 Right — Rocket은 정면이라
    ×1.5 대상이 아니다(등 뒤 팔이 없어졌으므로 이제 아무도 뒤를 못 친다)."""
    combat, player = make_combat()
    crusher, rocket = combat.monsters
    surrounded = player._powers["surrounded"]

    assert surrounded.facing == "right"  # 기본값

    crusher._current_hp = 0
    crusher._is_dead = True
    combat._broadcast_death(crusher)

    assert surrounded.facing == "right", "Crusher(정면 아님) 사망 후 facing 유지"
    result = player.take_damage(10, source=rocket, powered=True)
    assert result["hp_lost"] == 10, "Rocket은 facing=right에서 정면 — 배율 없음"
    print("✅ SurroundedPower — Crusher 사망 시 방향 유지(Rocket 정면) 확인")


def test_surrounded_rocket_death_flips_facing():
    """SurroundedPower.on_any_death — Rocket(back_attack_right, 정면) 사망 시.
    원본 UpdateDirection: facing=Right에서 남은 Crusher가 back_attack_LEFT이므로 Left로 돈다.
    방향이 Left로 바뀌면 이후 ×1.5는 back_attack_RIGHT 보유자에게만 적용되는데
    Rocket은 이미 죽었으니, 남은 Crusher(back_attack_left)는 정면이라 배율이 없다."""
    combat, player = make_combat()
    crusher, rocket = combat.monsters
    surrounded = player._powers["surrounded"]

    # 방향 전환 전 상태: Crusher(back_attack_left)는 등 뒤 → ×1.5
    pre = player.take_damage(10, source=crusher, powered=True)
    assert pre["hp_lost"] == 15, "전환 전 Crusher는 등 뒤 → ×1.5"

    rocket._current_hp = 0
    rocket._is_dead = True
    combat._broadcast_death(rocket)

    assert surrounded.facing == "left", "Rocket 사망 후 남은 Crusher를 향해 facing=left"
    post = player.take_damage(10, source=crusher, powered=True)
    assert post["hp_lost"] == 10, "전환 후 Crusher는 정면 → 배율 없음"
    print("✅ SurroundedPower — Rocket 사망 시 Crusher를 향해 방향 전환 확인")


def test_seeded_smoke():
    for seed in range(5):
        player = Player(create_character("ironclad"))
        combat = CombatState(
            player, make_encounter("kaiser_crab_boss", random.Random(seed)), seed=seed
        )
        result = combat.run(SimplePolicy(), max_turns=100)
        assert isinstance(result.victory, bool)
    print("✅ kaiser_crab_boss × 5시드 전투 스모크 통과")


def main():
    print("🧪 STS2 S1.M3.B19 회귀\n")
    test_registry_and_encounter()
    test_opening_powers()
    test_surrounded_power_1_5x()
    test_crab_rage_on_ally_death()
    test_crab_rage_block_unpowered()
    test_crusher_move_cycle()
    test_crusher_bug_sting_debuff()
    test_crusher_adapt_and_guarded()
    test_rocket_move_cycle()
    test_rocket_charge_and_recharge()
    test_surrounded_crusher_death_keeps_facing()
    test_surrounded_rocket_death_flips_facing()
    test_seeded_smoke()
    print("\n" + "=" * 60)
    print("✅ S1.M3.B19 전체 테스트 통과!")
    print("=" * 60)


if __name__ == "__main__":
    main()
