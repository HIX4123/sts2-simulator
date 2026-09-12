#!/usr/bin/env python3
"""
STS2 Phase 6s 통합 테스트 — 환영(Illusion) 계열.

- IllusionPower: 사망 후 전투에서 사라지지 않고 다음 턴 최대 HP로 부활
- 스텁이던 Parafright / EyeWithTeeth를 원본대로 재이식
- 이들을 소환하는 Fogmog / TheObscura (배치14)
"""
import random

import sts2_sim  # noqa: F401
from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import ENCOUNTER_SLOTS, ENCOUNTERS, make_encounter
from sts2_sim.entities.monsters_batch14 import Fogmog, TheObscura
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import (
    EyeWithTeeth, MONSTER_REGISTRY, Parafright, create_monster,
)
from sts2_sim.models.sts2_power import IllusionPower, POWER_REGISTRY, Weak


def make_combat(monsters, seed=42, player_hp=500):
    player = Player(create_character("ironclad"))
    player._max_hp = player._current_hp = player_hp
    combat = CombatState(player, monsters, seed=seed)
    combat.start()
    return combat, player


def test_registry_and_encounters():
    assert MONSTER_REGISTRY["fogmog"] is Fogmog
    assert MONSTER_REGISTRY["the_obscura"] is TheObscura
    assert POWER_REGISTRY["illusion"] is IllusionPower
    for eid in ("fogmog_normal", "the_obscura_normal"):
        assert eid in ENCOUNTERS, f"미등록 인카운터: {eid}"
    assert ENCOUNTER_SLOTS["fogmog_normal"] == ["illusion", "fogmog"]
    assert ENCOUNTER_SLOTS["the_obscura_normal"] == ["illusion", "obscura"]

    assert create_monster("fogmog").min_initial_hp == 74
    assert create_monster("the_obscura").min_initial_hp == 123
    print("✅ Fogmog/TheObscura + IllusionPower + 인카운터 2종 등록 확인")


def test_stub_monsters_now_match_original():
    """Parafright/EyeWithTeeth가 원본 수치·동작으로 교체됐다."""
    pf = create_monster("parafright")
    assert (pf.min_initial_hp, pf.max_initial_hp) == (21, 21)
    assert pf.slam_damage == 16, "Parafright는 16딜 SLAM (기존 스텁은 3딜)"
    assert pf.should_disappear_from_doom is False

    eye = create_monster("eye_with_teeth")
    assert (eye.min_initial_hp, eye.max_initial_hp) == (6, 6)
    assert eye.distract_amount == 3
    assert eye.should_disappear_from_doom is False

    combat, player = make_combat([eye], seed=1)
    hp = player.current_hp
    eye.take_turn([player])
    assert player.current_hp == hp, "EyeWithTeeth는 공격하지 않는다 (기존 스텁은 2딜)"
    dazed = [c for c in combat.discard_pile if c.card_id == "dazed"]
    assert len(dazed) == 3, f"Dazed 3장이 아님: {len(dazed)}"
    print("✅ Parafright 16딜 SLAM / EyeWithTeeth Dazed 3장 — 원본 동작 복원 확인")


def test_illusion_revives_at_full_hp_next_turn():
    pf = create_monster("parafright")
    combat, player = make_combat([pf], seed=2)
    assert pf.has_power("illusion")
    assert pf.has_power("minion"), "IllusionPower 적용 시 MinionPower 자동 부여"

    pf.lose_hp(pf.current_hp)
    assert not combat._combat_is_won(), "부활 대기 중인데 승리 처리됨"
    assert pf._move_state_machine.get_current_move_name() == "REVIVE_MOVE"
    assert pf._powers["illusion"].is_reviving

    pf.take_turn([player])
    assert pf.current_hp == pf.max_hp, "최대 HP로 부활하지 않음"
    assert not pf._powers["illusion"].is_reviving
    assert pf._move_state_machine.get_current_move_name() == "SLAM_MOVE", \
        "부활 후 원래 무브로 복귀하지 않음"

    hp = player.current_hp
    pf.take_turn([player])
    assert player.current_hp == hp - 16, "부활 후 정상 공격 실패"
    print("✅ Illusion 사망→다음 턴 최대 HP 부활→원래 무브 복귀 확인")


def test_illusion_clears_debuffs_but_keeps_buffs_on_death():
    """사망 시 디버프만 제거되고 버프는 유지된다 (원본 ShouldPowerBeRemovedOnDeath)."""
    pf = create_monster("parafright")
    combat, player = make_combat([pf], seed=3)
    from sts2_sim.models.sts2_power import Strength
    pf.apply_power(Strength(4))
    pf.apply_power(Weak(2), applier=player)
    assert pf.has_power("weak")

    pf.lose_hp(pf.current_hp)
    combat.reap_deaths()
    assert not pf.has_power("weak"), "사망 후 디버프가 남음"
    assert pf.get_power_amount("strength") == 4, "사망 후 버프가 사라짐"
    assert pf.has_power("illusion"), "IllusionPower 자체가 제거됨"
    print("✅ 사망 시 디버프만 제거 + 버프/Illusion 유지 확인")


def test_fogmog_summons_eye_and_move_cycle():
    fog = Fogmog()
    combat, player = make_combat([fog], seed=4)
    sm = fog._move_state_machine
    assert sm.get_current_move_name() == "ILLUSION_MOVE"

    fog.take_turn([player])
    eyes = [m for m in combat.alive_enemies if isinstance(m, EyeWithTeeth)]
    assert len(eyes) == 1, "EyeWithTeeth가 소환되지 않음"
    assert eyes[0].slot_name == "illusion"
    assert eyes[0].has_power("illusion")
    assert sm.get_current_move_name() == "SWIPE_MOVE"

    hp = player.current_hp
    fog.take_turn([player])
    assert player.current_hp == hp - 8, "SWIPE 8딜 불일치"
    assert fog.get_power_amount("strength") == 1, "SWIPE 힘 +1 미적용"
    assert sm.get_current_move_name() in ("SWIPE_RANDOM_MOVE", "HEADBUTT_MOVE")
    print("✅ Fogmog EyeWithTeeth 소환 + SWIPE(8딜+힘1) → 분기 확인")


def test_fogmog_branch_weights_and_follow_ups():
    """BRANCH는 SWIPE_RANDOM 0.4 / HEADBUTT 0.6, 각 분기의 복귀처가 다르다."""
    fog = Fogmog()
    combat, player = make_combat([fog], seed=5, player_hp=5000)
    branch = fog._move_state_machine.states_by_name["BRANCH"]
    weights = {b[0].name: b[1] for b in branch.branches}
    assert weights == {"SWIPE_RANDOM_MOVE": 0.4, "HEADBUTT_MOVE": 0.6}, weights
    assert all(b[2] for b in branch.branches), "두 분기 모두 CannotRepeat여야 함"

    sm = fog._move_state_machine
    sm.force_current_state(sm.states_by_name["SWIPE_RANDOM_MOVE"])
    fog.take_turn([player])
    assert sm.get_current_move_name() == "HEADBUTT_MOVE", \
        "SWIPE_RANDOM 다음은 HEADBUTT 고정"

    hp = player.current_hp
    fog.take_turn([player])
    assert player.current_hp == hp - (14 + fog.get_power_amount("strength")), \
        "HEADBUTT 14딜 불일치"
    assert sm.get_current_move_name() == "SWIPE_MOVE", "HEADBUTT 다음은 SWIPE 고정"
    print("✅ Fogmog BRANCH 가중치 0.4/0.6 + 분기별 복귀처 확인")


def test_obscura_summons_parafright_and_wail_buffs_all():
    obscura = TheObscura()
    combat, player = make_combat([obscura], seed=6, player_hp=5000)
    sm = obscura._move_state_machine
    assert sm.get_current_move_name() == "ILLUSION_MOVE"

    obscura.take_turn([player])
    summoned = [m for m in combat.alive_enemies if isinstance(m, Parafright)]
    assert len(summoned) == 1 and summoned[0].slot_name == "illusion"

    # SAIL_MOVE는 같은 편 전체에 힘 +3 (자신 + 소환한 Parafright)
    sm.force_current_state(sm.states_by_name["SAIL_MOVE"])
    obscura.take_turn([player])
    assert obscura.get_power_amount("strength") == 3, "본체 힘 +3 미적용"
    assert summoned[0].get_power_amount("strength") == 3, \
        "SAIL_MOVE가 같은 편 전체를 강화하지 않음"

    sm.force_current_state(sm.states_by_name["HARDENING_STRIKE_MOVE"])
    hp, block = player.current_hp, obscura.block
    obscura.take_turn([player])
    assert player.current_hp == hp - (6 + 3), "HARDENING_STRIKE 6딜 + 힘3 불일치"
    assert obscura.block == block + 6, "HARDENING_STRIKE 블록 6 불일치"
    print("✅ TheObscura Parafright 소환 + SAIL 전체 힘+3 + HARDENING 6딜/블록6 확인")


def test_obscura_branches_cannot_repeat():
    obscura = TheObscura()
    combat, player = make_combat([obscura], seed=7, player_hp=9999)
    sm = obscura._move_state_machine
    obscura.take_turn([player])  # ILLUSION → RAND

    seen = []
    for _ in range(40):
        seen.append(sm.get_current_move_name())
        obscura.take_turn([player])
    assert set(seen) == {"PIERCING_GAZE_MOVE", "SAIL_MOVE", "HARDENING_STRIKE_MOVE"}
    for i in range(len(seen) - 1):
        assert seen[i] != seen[i + 1], f"CannotRepeat 위반: {seen}"
    print("✅ TheObscura 3분기 전부 등장 + CannotRepeat 확인")


def test_seeded_smoke():
    for eid in ("fogmog_normal", "the_obscura_normal"):
        for seed in range(3):
            player = Player(create_character("ironclad"))
            monsters = make_encounter(eid, random.Random(seed))
            combat = CombatState(player, monsters, seed=seed)
            result = combat.run(SimplePolicy(), max_turns=100)
            assert isinstance(result.victory, bool)
    print("✅ 신규 인카운터 2종 × 3시드 전투 스모크 통과")


def main():
    print("🧪 STS2 Phase 6s 통합 테스트\n")
    test_registry_and_encounters()
    test_stub_monsters_now_match_original()
    test_illusion_revives_at_full_hp_next_turn()
    test_illusion_clears_debuffs_but_keeps_buffs_on_death()
    test_fogmog_summons_eye_and_move_cycle()
    test_fogmog_branch_weights_and_follow_ups()
    test_obscura_summons_parafright_and_wail_buffs_all()
    test_obscura_branches_cannot_repeat()
    test_seeded_smoke()

    print("\n" + "=" * 60)
    print("✅ Phase 6s 전체 테스트 통과!")
    print("=" * 60)
    print("\n📊 Phase 6s 구현 현황:")
    print("  ✅ IllusionPower — 사망 후 다음 턴 최대 HP 부활 (디버프만 제거)")
    print("  ✅ Parafright/EyeWithTeeth 스텁을 원본 동작으로 교체")
    print("  ✅ Fogmog / TheObscura — 환영 소환 + 인카운터 2종")


if __name__ == "__main__":
    main()
