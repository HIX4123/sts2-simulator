#!/usr/bin/env python3
"""
STS2 Phase 6u 통합 테스트 — Tunneler / SlumberingBeetle / OwlMagistrate.

- Tunneler: BITE(13) → BURROW(BurrowedPower+블록32) → BELOW(23반복)
  블록은 턴 시작에 사라지지 않고, 전부 깨지면 on_block_broken → stun(DIZZY) → BITE
- SlumberingBeetle: 개전 Plating15 + Slumber3 → SNORE 반복
  Slumber가 0이 되면 깨어나며 Plating을 잃는다. 피해로 깬 경우와 턴 종료로 깬
  경우의 결과가 다르다(아래 각 테스트의 docstring 참조) → ROLL_OUT(16딜+힘2 반복)
- OwlMagistrate: SCRUTINY(16) → PECK_ASSAULT(4×6) → FLIGHT(SoarPower) → VERDICT(33딜+취약4, Soar제거) → 순환
"""
import random

import sts2_sim  # noqa: F401
from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import make_encounter, ENCOUNTERS
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.monsters_batch16 import Tunneler, SlumberingBeetle, OwlMagistrate
from sts2_sim.entities.sts2_monster import MONSTER_REGISTRY, create_monster
from sts2_sim.models.sts2_power import (
    POWER_REGISTRY, BurrowedPower, SlumberPower, SoarPower,
)


def make_combat(monsters_or_id, seed=42, player_hp=9999):
    """str(인카운터 ID) 또는 list(MonsterModel) 모두 허용."""
    player = Player(create_character("ironclad"))
    player._max_hp = player._current_hp = player_hp
    if isinstance(monsters_or_id, str):
        monsters = make_encounter(monsters_or_id, random.Random(seed))
    else:
        monsters = monsters_or_id
    combat = CombatState(player, monsters, seed=seed)
    combat.start()
    return combat, player


def monster_turn(monster, targets):
    """엔진(core.combat)의 몬스터 턴 1회와 정확히 같은 순서로 구동한다 —
    start_of_turn → on_turn_start → take_turn → on_turn_end → tick_powers.

    take_turn만 호출하면 턴 종료 훅이 돌지 않아 SlumberPower(턴 종료마다 감소)나
    Plating(턴 종료 블록 지급) 같은 파워를 검증할 수 없고, start_of_turn을 빼면
    BurrowedPower의 '블록 유지' 자체가 테스트되지 않는다."""
    monster.start_of_turn()
    for p in list(monster._powers.values()):
        hook = getattr(p, "on_turn_start", None)
        if hook:
            hook()
    monster.take_turn(targets)
    for p in list(monster._powers.values()):
        hook = getattr(p, "on_turn_end", None)
        if hook:
            hook()
    monster.tick_powers()


def _find(combat, cls):
    return [m for m in combat.alive_enemies if isinstance(m, cls)][0]


def test_registry_and_encounters():
    assert MONSTER_REGISTRY["tunneler"] is Tunneler
    assert MONSTER_REGISTRY["slumbering_beetle"] is SlumberingBeetle
    assert MONSTER_REGISTRY["owl_magistrate"] is OwlMagistrate
    assert POWER_REGISTRY["burrowed"] is BurrowedPower
    assert POWER_REGISTRY["slumber"] is SlumberPower
    assert POWER_REGISTRY["soar"] is SoarPower

    for eid in ("tunneler_normal", "tunneler_weak",
                "slumbering_beetle_normal", "owl_magistrate_normal"):
        assert eid in ENCOUNTERS, f"{eid} 미등록"

    assert create_monster("tunneler").min_initial_hp == 87
    assert create_monster("slumbering_beetle").min_initial_hp == 86
    assert create_monster("owl_magistrate").min_initial_hp == 231

    # TunnelerNormal은 원본이 Chomper(ScreamFirst) + Tunneler 2마리다.
    from sts2_sim.entities.sts2_monster import Chomper
    tn = make_encounter("tunneler_normal", random.Random(0))
    assert len(tn) == 2
    assert isinstance(tn[0], Chomper) and tn[0].scream_first is True
    assert isinstance(tn[1], Tunneler)
    print("✅ 배치16 몬스터 3종 + 파워 3종 + 인카운터 4종 등록 확인")


def test_tunneler_burrow_cycle():
    """BITE → BURROW(블록32+Burrowed) → BELOW(23 무한 반복).
    굴에 든 뒤로는 턴 시작에도 블록이 초기화되지 않는다."""
    combat, player = make_combat("tunneler_weak", seed=1)
    tun = _find(combat, Tunneler)
    sm = tun._move_state_machine

    assert sm.get_current_move_name() == "BITE_MOVE"

    hp = player.current_hp
    monster_turn(tun, [player])  # BITE 13
    assert player.current_hp == hp - 13
    assert sm.get_current_move_name() == "BURROW_MOVE"

    monster_turn(tun, [player])  # BURROW → Burrowed + 블록 32
    assert tun.has_power("burrowed")
    assert tun.block == 32
    assert sm.get_current_move_name() == "BELOW_MOVE"

    # BELOW 반복 + 턴 시작 블록 유지 (BurrowedPower.ShouldClearBlock == false)
    hp = player.current_hp
    monster_turn(tun, [player])  # BELOW 23
    assert player.current_hp == hp - 23
    assert tun.block == 32, "굴에 든 동안 블록이 턴 시작에 초기화되면 안 된다"
    assert sm.get_current_move_name() == "BELOW_MOVE"

    hp = player.current_hp
    monster_turn(tun, [player])  # BELOW 반복
    assert player.current_hp == hp - 23
    assert tun.block == 32
    print("✅ Tunneler BITE→BURROW→BELOW(반복) + 블록 유지 확인")


def test_tunneler_burrowed_broken_stun():
    """블록 32를 전부 깨면 AfterBlockBroken → GetStunned → stun(DIZZY, BITE_MOVE)
    → BurrowedPower 제거(잔여 블록 소멸). 다음 턴은 무행동, 그 다음 턴부터 BITE."""
    combat, player = make_combat("tunneler_weak", seed=2)
    tun = _find(combat, Tunneler)
    sm = tun._move_state_machine

    sm.force_current_state(sm.states_by_name["BURROW_MOVE"])
    monster_turn(tun, [player])
    assert tun.has_power("burrowed") and tun.block == 32
    assert sm.get_current_move_name() == "BELOW_MOVE"

    # 32를 초과하는 피해로 블록을 완전히 소진 — 초과분 8만 HP로 들어간다.
    before_hp = tun.current_hp
    result = tun.take_damage(40, source=player, powered=True)
    assert result["hp_lost"] == 8
    assert tun.current_hp == before_hp - 8
    assert not tun.has_power("burrowed"), "블록이 전부 깨지면 BurrowedPower 제거"
    assert tun.block == 0, "AfterRemoved의 LoseBlock으로 잔여 블록도 사라진다"
    assert sm.get_current_move_name() == "STUNNED"

    # 기절 턴 = 무행동, 이후 BITE부터 재개
    hp = player.current_hp
    monster_turn(tun, [player])
    assert player.current_hp == hp, "기절 턴에는 피해를 주지 않는다"
    assert sm.get_current_move_name() == "BITE_MOVE"

    hp = player.current_hp
    monster_turn(tun, [player])
    assert player.current_hp == hp - 13
    print("✅ Tunneler 블록 전소진 → stun(DIZZY) → BITE 재개 확인")


def test_tunneler_partial_block_no_stun():
    """블록이 남으면 AfterBlockBroken은 발동하지 않는다 (전소진 시 1회 한정)."""
    combat, player = make_combat("tunneler_weak", seed=3)
    tun = _find(combat, Tunneler)
    sm = tun._move_state_machine

    sm.force_current_state(sm.states_by_name["BURROW_MOVE"])
    monster_turn(tun, [player])
    assert tun.block == 32

    tun.take_damage(20, source=player, powered=True)
    assert tun.block == 12
    assert tun.has_power("burrowed"), "블록이 남아 있으면 굴에서 끌려나오지 않는다"
    assert sm.get_current_move_name() == "BELOW_MOVE"
    print("✅ Tunneler 블록 부분 소진 시 stun 미발동 확인")


def test_slumbering_beetle_wake_by_turn_end():
    """턴 종료로 Slumber가 0이 되면 원본은 WakeUpMove를 그 자리에서 실행한다
    (상태머신은 건드리지 않음). 분기 SNORE_NEXT는 무브 직후에 이미 해석되므로
    3턴째에는 Slumber가 아직 1이라 SNORE가 한 번 더 예약되고, ROLL_OUT은
    4턴째 무브가 끝난 뒤에 예약된다."""
    combat, player = make_combat("slumbering_beetle_normal", seed=3)
    sb = _find(combat, SlumberingBeetle)
    sm = sb._move_state_machine

    assert sb.get_power_amount("plating") == 15
    assert sb.get_power_amount("slumber") == 3
    assert sm.get_current_move_name() == "SNORE_MOVE"
    assert not sb.is_awake

    monster_turn(sb, [player])  # 턴1 SNORE
    assert sb.get_power_amount("slumber") == 2
    assert sm.get_current_move_name() == "SNORE_MOVE"

    monster_turn(sb, [player])  # 턴2 SNORE
    assert sb.get_power_amount("slumber") == 1
    assert sm.get_current_move_name() == "SNORE_MOVE"

    monster_turn(sb, [player])  # 턴3 SNORE → 턴 종료에 Slumber 0 → 즉시 기상
    assert not sb.has_power("slumber"), "턴 종료 기상 시 Slumber 제거"
    assert not sb.has_power("plating"), "기상하면 Plating을 잃는다"
    assert sb.is_awake
    assert sm.get_current_move_name() == "SNORE_MOVE", \
        "분기는 무브 직후에 이미 해석됐으므로 SNORE가 한 번 더 남는다"

    monster_turn(sb, [player])  # 턴4 SNORE (마지막) → 분기 재평가 → ROLL_OUT
    assert sm.get_current_move_name() == "ROLL_OUT_MOVE"
    print("✅ SlumberingBeetle 턴 종료 기상(Plating 상실) → SNORE 1회 후 ROLL_OUT 확인")


def test_slumbering_beetle_wake_by_damage():
    """피해로 Slumber가 0이 되면 원본은 Stun(WakeUpMove, "ROLL_OUT_MOVE") —
    기상 자체가 '다음 턴의 행동'이 되므로 Plating은 그 턴에 바로 사라지지 않는다.
    또한 Plating 15 블록을 뚫지 못한 피해는 Slumber를 깎지 않는다
    (원본 UnblockedDamage != 0 게이트)."""
    combat, player = make_combat("slumbering_beetle_normal", seed=4)
    sb = _find(combat, SlumberingBeetle)
    sm = sb._move_state_machine

    assert sb.block == 15  # Plating이 부여 즉시 지급
    sb.take_damage(10, source=player, powered=True)
    assert sb.get_power_amount("slumber") == 3, "블록에 전부 막힌 피해는 Slumber를 깎지 않는다"

    sb.take_damage(20, source=player, powered=True)  # 블록 5 관통
    assert sb.get_power_amount("slumber") == 2

    sb._powers["slumber"].amount = 1
    sb.take_damage(20, source=player, powered=True)
    assert not sb.has_power("slumber"), "피해로 Slumber 소진 → 제거"
    assert sb.has_power("plating"), "기상은 다음 턴 행동이라 Plating은 아직 남는다"
    assert not sb.is_awake
    assert sm.get_current_move_name() == "STUNNED"

    monster_turn(sb, [player])  # 기상 턴 = WakeUpMove
    assert sb.is_awake
    assert not sb.has_power("plating")
    assert sm.get_current_move_name() == "ROLL_OUT_MOVE"
    print("✅ SlumberingBeetle 피해 기상(다음 턴 WakeUp) → ROLL_OUT 확인")


def test_slumbering_beetle_rollout_strength():
    """ROLL_OUT은 16딜 후 자기 힘 +2를 얻고 무한 반복 — 힘은 다음 타격부터 반영."""
    combat, player = make_combat("slumbering_beetle_normal", seed=5)
    sb = _find(combat, SlumberingBeetle)
    sm = sb._move_state_machine

    for _ in range(4):  # SNORE 3턴 + 기상 후 남은 SNORE 1턴
        monster_turn(sb, [player])
    assert sb.is_awake
    assert sm.get_current_move_name() == "ROLL_OUT_MOVE"
    assert sb.get_power_amount("strength") == 0

    hp = player.current_hp
    monster_turn(sb, [player])
    assert player.current_hp == hp - 16
    assert sb.get_power_amount("strength") == 2

    hp = player.current_hp
    monster_turn(sb, [player])
    assert player.current_hp == hp - 18
    assert sb.get_power_amount("strength") == 4
    assert sm.get_current_move_name() == "ROLL_OUT_MOVE"
    print("✅ SlumberingBeetle ROLL_OUT(16딜+힘+2 누적) 반복 확인")


def test_owl_magistrate_cycle():
    """SCRUTINY(16) → PECK_ASSAULT(4×6) → FLIGHT(Soar) → VERDICT(33+취약4, Soar제거) → 순환."""
    combat, player = make_combat("owl_magistrate_normal", seed=6)
    owl = _find(combat, OwlMagistrate)
    sm = owl._move_state_machine

    assert sm.get_current_move_name() == "MAGISTRATE_SCRUTINY"
    hp = player.current_hp
    monster_turn(owl, [player])
    assert player.current_hp == hp - 16
    assert sm.get_current_move_name() == "PECK_ASSAULT"

    hp = player.current_hp
    monster_turn(owl, [player])
    assert player.current_hp == hp - 24, "4딜 × 6히트"
    assert sm.get_current_move_name() == "JUDICIAL_FLIGHT"

    hp = player.current_hp
    monster_turn(owl, [player])
    assert player.current_hp == hp, "비행 턴은 공격하지 않는다"
    assert owl.has_power("soar")
    assert sm.get_current_move_name() == "VERDICT"

    hp = player.current_hp
    monster_turn(owl, [player])
    # 공격이 먼저, 취약 부여가 나중 — 자기 취약에 증폭되지 않는다
    assert player.current_hp == hp - 33
    assert player.get_power_amount("vulnerable") == 4
    assert not owl.has_power("soar"), "VERDICT로 착지하며 Soar 제거"
    assert sm.get_current_move_name() == "MAGISTRATE_SCRUTINY"
    print("✅ OwlMagistrate 4무브 순환 + Soar 1턴 유지 확인")


def test_soar_damage_reduction():
    """SoarPower: 파워드 공격 피해만 50% 감소 (원본 IsPoweredAttack 게이트)."""
    combat, player = make_combat("owl_magistrate_normal", seed=7)
    owl = _find(combat, OwlMagistrate)

    owl.apply_power(SoarPower(1))
    assert owl.take_damage(10, source=player, powered=True)["hp_lost"] == 5
    assert owl.take_damage(11, source=player, powered=True)["hp_lost"] == 5, "내림 처리"
    assert owl.take_damage(10, source=player, powered=False)["hp_lost"] == 10, \
        "언파워드(가시/오브 반격 등)는 감소하지 않는다"

    owl.remove_power("soar")
    assert owl.take_damage(10, source=player, powered=True)["hp_lost"] == 10
    print("✅ SoarPower 파워드 공격 50% 감소 확인")


def test_seeded_smoke():
    for eid in ("tunneler_normal", "tunneler_weak",
                "slumbering_beetle_normal", "owl_magistrate_normal"):
        for seed in range(3):
            player = Player(create_character("ironclad"))
            monsters = make_encounter(eid, random.Random(seed))
            combat = CombatState(player, monsters, seed=seed)
            result = combat.run(SimplePolicy(), max_turns=100)
            assert isinstance(result.victory, bool)
    print("✅ 배치16 4인카운터 × 3시드 전투 스모크 통과")


def main():
    print("🧪 STS2 Phase 6u 통합 테스트\n")
    test_registry_and_encounters()
    test_tunneler_burrow_cycle()
    test_tunneler_burrowed_broken_stun()
    test_tunneler_partial_block_no_stun()
    test_slumbering_beetle_wake_by_turn_end()
    test_slumbering_beetle_wake_by_damage()
    test_slumbering_beetle_rollout_strength()
    test_owl_magistrate_cycle()
    test_soar_damage_reduction()
    test_seeded_smoke()

    print("\n" + "=" * 60)
    print("✅ Phase 6u 전체 테스트 통과!")
    print("=" * 60)
    print("\n📊 Phase 6u 구현 현황:")
    print("  ✅ BurrowedPower — 블록 유지 + 전소진 시 stun, 제거 시 잔여 블록 소멸")
    print("  ✅ SlumberPower — 피해/턴 종료 기상 경로 분리, Plating 제거")
    print("  ✅ SoarPower — 파워드 공격 50% 감소")
    print("  ✅ Tunneler — BITE/BURROW/BELOW + stun 재개")
    print("  ✅ SlumberingBeetle — SNORE/ROLL_OUT + 힘 누적")
    print("  ✅ OwlMagistrate — 4무브 순환 + Soar 1턴")


if __name__ == "__main__":
    main()
