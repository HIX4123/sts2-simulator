#!/usr/bin/env python3
"""
STS2 Phase 6v 통합 테스트 — Entomancer / KinFollower / TorchHeadAmalgam.

- Entomancer: BEES(3×7)부터 시작 → SPEAR(18) → SPIT(벌집/힘) 순환.
  PersonalHivePower는 플레이어의 파워드 공격을 받을 때마다 뽑을 더미 무작위
  위치에 Dazed를 amount장 넣는다 — 블록에 전부 막혀도 발동한다.
- KinFollower: QUICK_SLASH(5) → BOOMERANG(2×2) → POWER_DANCE(힘+2) 순환.
  starts_with_dance면 POWER_DANCE부터 시작.
- TorchHeadAmalgam: TACKLE(18) ×2 후 BEAM(8×3) → 약태클(14) ×2 → BEAM 무한 루프.
"""
import random

import sts2_sim  # noqa: F401
from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import make_encounter, ENCOUNTERS
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.monsters_batch17 import Entomancer, KinFollower, TorchHeadAmalgam
from sts2_sim.entities.sts2_monster import MONSTER_REGISTRY, create_monster
from sts2_sim.models.sts2_power import POWER_REGISTRY, PersonalHivePower


def make_combat(monsters_or_id, seed=42, player_hp=9999):
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
    """엔진(core.combat)의 몬스터 턴 1회와 같은 순서 —
    start_of_turn → on_turn_start → take_turn → on_turn_end → tick_powers."""
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


def _dazed_in_draw(combat):
    return sum(1 for c in combat.draw_pile if c.card_id == "dazed")


def test_registry_and_encounters():
    assert MONSTER_REGISTRY["entomancer"] is Entomancer
    assert MONSTER_REGISTRY["kin_follower"] is KinFollower
    assert MONSTER_REGISTRY["torch_head_amalgam"] is TorchHeadAmalgam
    assert POWER_REGISTRY["personal_hive"] is PersonalHivePower

    for eid in ("entomancer_elite", "kin_followers_weak", "torch_head_amalgam_normal"):
        assert eid in ENCOUNTERS, f"{eid} 미등록"

    assert create_monster("entomancer").min_initial_hp == 145
    assert create_monster("kin_follower").min_initial_hp == 58
    assert create_monster("kin_follower").max_initial_hp == 59
    assert create_monster("torch_head_amalgam").min_initial_hp == 199

    kin = make_encounter("kin_followers_weak", random.Random(0))
    assert len(kin) == 2
    assert kin[0].starts_with_dance is True and kin[1].starts_with_dance is False
    print("✅ 배치17 몬스터 3종 + PersonalHivePower + 인카운터 3종 등록 확인")


def test_entomancer_cycle():
    """시작 무브는 SPIT이 아니라 BEES (원본 initialState = moveState2)."""
    combat, player = make_combat("entomancer_elite", seed=1)
    ent = _find(combat, Entomancer)
    sm = ent._move_state_machine

    assert ent.get_power_amount("personal_hive") == 1
    assert sm.get_current_move_name() == "BEES_MOVE"

    hp = player.current_hp
    monster_turn(ent, [player])
    assert player.current_hp == hp - 21, "3딜 × 7히트"
    assert sm.get_current_move_name() == "SPEAR_MOVE"

    hp = player.current_hp
    monster_turn(ent, [player])
    assert player.current_hp == hp - 18
    assert sm.get_current_move_name() == "PHEROMONE_SPIT_MOVE"

    hp = player.current_hp
    monster_turn(ent, [player])
    assert player.current_hp == hp, "SPIT은 공격하지 않는다"
    assert sm.get_current_move_name() == "BEES_MOVE"
    print("✅ Entomancer BEES→SPEAR→SPIT 순환(BEES 시작) 확인")


def test_entomancer_spit_hive_cap():
    """벌집 < 3이면 벌집+1 & 힘+1, 3 이상이면 힘+2만."""
    combat, player = make_combat("entomancer_elite", seed=2)
    ent = _find(combat, Entomancer)
    sm = ent._move_state_machine
    sm.force_current_state(sm.states_by_name["PHEROMONE_SPIT_MOVE"])

    monster_turn(ent, [player])  # 1 → 2, 힘 1
    assert ent.get_power_amount("personal_hive") == 2
    assert ent.get_power_amount("strength") == 1

    sm.force_current_state(sm.states_by_name["PHEROMONE_SPIT_MOVE"])
    monster_turn(ent, [player])  # 2 → 3, 힘 2
    assert ent.get_power_amount("personal_hive") == 3
    assert ent.get_power_amount("strength") == 2

    sm.force_current_state(sm.states_by_name["PHEROMONE_SPIT_MOVE"])
    monster_turn(ent, [player])  # 상한 도달 → 벌집 유지, 힘 +2
    assert ent.get_power_amount("personal_hive") == 3, "벌집은 3에서 멈춘다"
    assert ent.get_power_amount("strength") == 4
    print("✅ Entomancer SPIT 벌집 상한 3 / 초과 시 힘 +2 확인")


def test_personal_hive_dazed():
    """플레이어의 파워드 공격마다 Dazed를 amount장 뽑을 더미에 삽입.
    원본 AfterDamageReceived에 UnblockedDamage 게이트가 없으므로 블록에
    전부 막힌 공격도 카드를 준다."""
    combat, player = make_combat("entomancer_elite", seed=3)
    ent = _find(combat, Entomancer)

    assert _dazed_in_draw(combat) == 0
    ent.take_damage(10, source=player, powered=True)
    assert _dazed_in_draw(combat) == 1

    # 블록에 전부 막혀도 발동
    ent.gain_block(50)
    ent.take_damage(10, source=player, powered=True)
    assert _dazed_in_draw(combat) == 2, "블록에 막힌 파워드 공격도 벌집을 깨운다"

    # 언파워드(가시/오브 반격 등)는 발동하지 않는다
    ent.take_damage(10, source=player, powered=False)
    assert _dazed_in_draw(combat) == 2

    # 벌집이 쌓이면 한 번에 여러 장
    ent._powers["personal_hive"].amount = 3
    ent.take_damage(10, source=player, powered=True)
    assert _dazed_in_draw(combat) == 5
    print("✅ PersonalHivePower Dazed 삽입(블록 무관/언파워드 제외/스택) 확인")


def test_personal_hive_no_trigger_on_death():
    """이 피해로 죽으면 AfterDamageReceived를 건너뛴다
    (원본 !WasTargetKilled || !IsDead)."""
    combat, player = make_combat("entomancer_elite", seed=4)
    ent = _find(combat, Entomancer)

    ent.take_damage(9999, source=player, powered=True)
    assert ent.is_dead
    assert _dazed_in_draw(combat) == 0, "죽은 대상은 카드를 주지 않는다"
    print("✅ PersonalHivePower 치명타 사망 시 미발동 확인")


def test_kin_follower_cycle():
    """추종자 둘의 무브가 starts_with_dance로 한 칸 어긋난다."""
    combat, player = make_combat("kin_followers_weak", seed=5)
    dancer, slasher = combat.alive_enemies[0], combat.alive_enemies[1]
    assert dancer._move_state_machine.get_current_move_name() == "POWER_DANCE_MOVE"
    assert slasher._move_state_machine.get_current_move_name() == "QUICK_SLASH_MOVE"
    assert dancer.has_power("minion") and slasher.has_power("minion")

    sm = slasher._move_state_machine
    hp = player.current_hp
    monster_turn(slasher, [player])
    assert player.current_hp == hp - 5
    assert sm.get_current_move_name() == "BOOMERANG_MOVE"

    hp = player.current_hp
    monster_turn(slasher, [player])
    assert player.current_hp == hp - 4, "2딜 × 2히트"
    assert sm.get_current_move_name() == "POWER_DANCE_MOVE"

    hp = player.current_hp
    monster_turn(slasher, [player])
    assert player.current_hp == hp
    assert slasher.get_power_amount("strength") == 2
    assert sm.get_current_move_name() == "QUICK_SLASH_MOVE"

    # 힘은 다음 타격부터 반영
    hp = player.current_hp
    monster_turn(slasher, [player])
    assert player.current_hp == hp - 7
    print("✅ KinFollower 3무브 순환 + 힘 누적 + starts_with_dance 확인")


def test_torch_head_amalgam_cycle():
    """강태클 2연타는 개전 1회뿐 — 이후 BEAM→약태클×2 3턴 루프."""
    combat, player = make_combat("torch_head_amalgam_normal", seed=6)
    amg = _find(combat, TorchHeadAmalgam)
    sm = amg._move_state_machine
    assert amg.has_power("minion")

    expected = [
        ("TACKLE_MOVE", 18), ("TACKLE_2_MOVE", 18), ("BEAM_MOVE", 24),
        ("TACKLE_3_MOVE", 14), ("TACKLE_4_MOVE", 14),
        ("BEAM_MOVE", 24), ("TACKLE_3_MOVE", 14), ("TACKLE_4_MOVE", 14),
        ("BEAM_MOVE", 24),
    ]
    for name, dmg in expected:
        assert sm.get_current_move_name() == name, \
            f"{name} 기대, {sm.get_current_move_name()} 실제"
        hp = player.current_hp
        monster_turn(amg, [player])
        assert player.current_hp == hp - dmg, f"{name} 피해 {dmg} 불일치"
    print("✅ TorchHeadAmalgam 강태클 2연타 후 BEAM 3턴 루프 확인")


def test_seeded_smoke():
    for eid in ("entomancer_elite", "kin_followers_weak", "torch_head_amalgam_normal"):
        for seed in range(3):
            player = Player(create_character("ironclad"))
            monsters = make_encounter(eid, random.Random(seed))
            combat = CombatState(player, monsters, seed=seed)
            result = combat.run(SimplePolicy(), max_turns=100)
            assert isinstance(result.victory, bool)
    print("✅ 배치17 3인카운터 × 3시드 전투 스모크 통과")


def main():
    print("🧪 STS2 Phase 6v 통합 테스트\n")
    test_registry_and_encounters()
    test_entomancer_cycle()
    test_entomancer_spit_hive_cap()
    test_personal_hive_dazed()
    test_personal_hive_no_trigger_on_death()
    test_kin_follower_cycle()
    test_torch_head_amalgam_cycle()
    test_seeded_smoke()

    print("\n" + "=" * 60)
    print("✅ Phase 6v 전체 테스트 통과!")
    print("=" * 60)
    print("\n📊 Phase 6v 구현 현황:")
    print("  ✅ PersonalHivePower — 파워드 피격마다 Dazed(블록 무관), 사망 시 미발동")
    print("  ✅ Creature.on_damage_received — 원본 AfterDamageReceived 훅")
    print("  ✅ Entomancer — BEES 시작 3무브 순환 + 벌집 상한 3")
    print("  ✅ KinFollower — 3무브 순환 + starts_with_dance 초기 무브 전환")
    print("  ✅ TorchHeadAmalgam — 강태클 2연타 후 BEAM 3턴 루프")


if __name__ == "__main__":
    main()
