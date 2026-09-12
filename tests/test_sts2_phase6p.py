#!/usr/bin/env python3
"""
STS2 Phase 6p 통합 테스트 — 슬롯 기반 소환 + TwoTailedRat.

엔진 확장: 인카운터 슬롯 목록(EncounterModel.Slots) + CombatState.next_free_slot
(원본 GetNextSlot), RandomBranchState의 동적 가중치(Func<float> 오버로드)와
UseOnlyOnce 지원.
"""
import random

import sts2_sim  # noqa: F401
from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import (
    ENCOUNTER_SLOTS, ENCOUNTERS, get_next_slot, make_encounter,
)
from sts2_sim.entities.monsters_batch12 import TwoTailedRat
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import MONSTER_REGISTRY


def make_combat(monsters, seed=42, player_hp=999):
    player = Player(create_character("ironclad"))
    player._max_hp = player._current_hp = player_hp
    combat = CombatState(player, monsters, seed=seed)
    combat.start()
    return combat, player


def test_registry_and_encounter():
    assert MONSTER_REGISTRY["two_tailed_rat"] is TwoTailedRat
    assert "two_tailed_rats_normal" in ENCOUNTERS
    assert ENCOUNTER_SLOTS["two_tailed_rats_normal"] == [
        "first", "second", "third", "fourth", "fifth"]

    rats = make_encounter("two_tailed_rats_normal", random.Random(1))
    assert len(rats) == 3
    assert [r.slot_name for r in rats] == ["third", "fourth", "fifth"], \
        "원본은 뒤 3칸(Slots[2..4])에 배치한다"
    assert all(r.encounter_id == "two_tailed_rats_normal" for r in rats)
    assert rats[0].min_initial_hp == 17 and rats[0].max_initial_hp == 21
    # 시작 무브 인덱스는 서로 다르게 회전
    assert len({r.starter_move_index for r in rats}) == 3
    print("✅ TwoTailedRat 등록 + 뒤 3슬롯 배치 + 시작 인덱스 회전 확인")


def test_get_next_slot():
    """빈 슬롯을 앞에서부터 찾고, 전부 차면 None."""
    rats = make_encounter("two_tailed_rats_normal", random.Random(2))
    eid = "two_tailed_rats_normal"
    assert get_next_slot(eid, rats) == "first"
    rats[0].slot_name = "first"
    assert get_next_slot(eid, rats) == "second"
    # 죽은 몬스터의 슬롯은 다시 비는 것으로 친다 (원본 Enemies는 생존만 포함)
    rats[0]._current_hp = 0
    assert get_next_slot(eid, rats) == "first"
    # 슬롯 정의가 없는 인카운터는 항상 None
    assert get_next_slot("slimes_weak", rats) is None
    assert get_next_slot(None, rats) is None
    print("✅ get_next_slot: 앞에서부터 탐색 + 사망 슬롯 회수 + 미정의 인카운터 None")


def test_summon_delay_and_slot_exhaustion():
    """개전 2턴은 소환 불가, 이후 빈 슬롯이 있는 동안만 소환한다."""
    rats = make_encounter("two_tailed_rats_normal", random.Random(3))
    combat, player = make_combat(rats, seed=3)
    assert all(not r.can_summon() for r in rats), "개전 직후 소환 가능 상태"
    assert all(r.turns_until_summonable == 2 for r in rats)

    for _ in range(2):
        for m in list(combat.alive_enemies):
            m.take_turn([player])
    assert len(combat.alive_enemies) == 3, "2턴 안에 소환이 일어남"

    for _ in range(8):
        for m in list(combat.alive_enemies):
            m.take_turn([player])
    slots = [m.slot_name for m in combat.alive_enemies]
    assert len(combat.alive_enemies) == 5, f"슬롯 5칸이 안 찼음: {slots}"
    assert set(slots) == {"first", "second", "third", "fourth", "fifth"}
    assert combat.next_free_slot() is None
    assert all(not r.can_summon() for r in combat.alive_enemies), \
        "슬롯이 다 찼는데 소환 가능 상태"
    print("✅ 소환 2턴 지연 + 빈 슬롯 소진 시 중단 확인")


def test_call_for_backup_count_is_shared():
    """소환 카운터는 같은 편 쥐 전체가 공유하고 3회에서 멈춘다."""
    rats = make_encounter("two_tailed_rats_normal", random.Random(4))
    combat, player = make_combat(rats, seed=4)
    for r in combat.alive_enemies:
        r.turns_until_summonable = 0

    summoner = rats[0]
    summoner._call_for_backup_move([player])
    counts = [r.call_for_backup_count for r in combat.alive_enemies
              if isinstance(r, TwoTailedRat)]
    assert set(counts) == {1}, f"카운터가 공유되지 않음: {counts}"

    summoner._call_for_backup_move([player])
    counts = {r.call_for_backup_count for r in combat.alive_enemies}
    assert counts == {2}, f"두 번째 소환 후 카운터 불일치: {counts}"

    # 3회 상한 — 카운터를 3으로 올리면 슬롯이 남아도 소환 불가
    for r in combat.alive_enemies:
        r.call_for_backup_count = 3
        r.turns_until_summonable = 0
    assert all(not r.can_summon() for r in combat.alive_enemies), "3회 상한 미적용"
    print("✅ CALL_FOR_BACKUP 카운터 공유 + 3회 상한 확인")


def test_can_summon_blocked_by_ally_already_calling():
    """같은 편이 이미 CALL_FOR_BACKUP을 예약했으면 중복 소환하지 않는다."""
    rats = make_encounter("two_tailed_rats_normal", random.Random(5))
    combat, player = make_combat(rats, seed=5)
    for r in rats:
        r.turns_until_summonable = 0
    assert rats[0].can_summon(), "선행 조건이 이미 막혀 테스트 무의미"

    backup = rats[1]._move_state_machine.states_by_name["CALL_FOR_BACKUP_MOVE"]
    rats[1]._move_state_machine.force_current_state(backup)
    assert not rats[0].can_summon(), "동료가 소환 예약 중인데 중복 소환 가능"
    print("✅ 동료가 CALL_FOR_BACKUP 예약 중이면 소환 차단 확인")


def test_dynamic_branch_weight_and_use_only_once():
    """소환 가능 여부로 분기 가중치가 갈리고, CALL_FOR_BACKUP은 1회용."""
    rat = TwoTailedRat(starter_move_index=0)
    combat, player = make_combat([rat], seed=6)
    rand = rat._move_state_machine.states_by_name["RAND"]
    weights = {b[0].name: b[1] for b in rand.branches}
    backup_w = weights["CALL_FOR_BACKUP_MOVE"]
    attack_w = weights["SCRATCH_MOVE"]

    # 소환 불가 상태: 공격 1.0, 소환 0.0 (후보에서 제외)
    assert not rat.can_summon()
    assert attack_w() == 1.0 and backup_w() == 0.0

    # 소환 가능 상태: 공격 1/12, 소환 0.75
    rat.turns_until_summonable = 0
    rat.encounter_id = "two_tailed_rats_normal"
    assert rat.can_summon(), "슬롯이 있는데 소환 불가"
    assert abs(attack_w() - 1 / 12) < 1e-9
    assert backup_w() == 0.75

    once = {b[0].name: b[5] for b in rand.branches}
    assert once["CALL_FOR_BACKUP_MOVE"] is True, "UseOnlyOnce 미설정"
    assert once["SCRATCH_MOVE"] is False
    print("✅ 동적 가중치(1.0/0.0 ↔ 1/12/0.75) + UseOnlyOnce 확인")


def test_zero_weight_branch_is_excluded():
    """가중치 0인 분기는 뽑히지 않는다 (소환 불가 시 CALL_FOR_BACKUP 제외)."""
    rats = make_encounter("two_tailed_rats_normal", random.Random(7))
    combat, player = make_combat(rats, seed=7)
    rat = rats[0]
    sm = rat._move_state_machine
    seen = set()
    for _ in range(60):
        rat.turns_until_summonable = 2  # 항상 소환 불가로 고정
        seen.add(sm.get_current_move_name())
        rat.take_turn([player])
    assert "CALL_FOR_BACKUP_MOVE" not in seen, \
        f"소환 불가인데 CALL_FOR_BACKUP이 선택됨: {seen}"
    assert {"SCRATCH_MOVE", "DISEASE_BITE_MOVE"} <= seen
    print("✅ 가중치 0 분기 제외 확인")


def test_seeded_smoke():
    for seed in range(5):
        player = Player(create_character("ironclad"))
        monsters = make_encounter("two_tailed_rats_normal", random.Random(seed))
        combat = CombatState(player, monsters, seed=seed)
        result = combat.run(SimplePolicy(), max_turns=80)
        assert isinstance(result.victory, bool)
        # 동시에 살아있는 쥐는 슬롯 수를 넘지 않는다. combat.monsters는 사망분까지
        # 누적하는 이력 리스트라 총합은 5를 넘을 수 있다 — 죽은 쥐의 슬롯이 비면
        # 원본도 그 자리를 다시 채운다 (GetNextSlot이 생존 Enemies만 보므로).
        alive_slots = [m.slot_name for m in combat.alive_enemies]
        assert len(alive_slots) <= 5, f"동시 생존이 슬롯 상한 초과: {alive_slots}"
        assert len(set(alive_slots)) == len(alive_slots), \
            f"같은 슬롯에 둘 이상 생존: {alive_slots}"
    print("✅ two_tailed_rats_normal 5시드 전투 스모크 + 슬롯 중복 없음 확인")


def main():
    print("🧪 STS2 Phase 6p 통합 테스트\n")
    test_registry_and_encounter()
    test_get_next_slot()
    test_summon_delay_and_slot_exhaustion()
    test_call_for_backup_count_is_shared()
    test_can_summon_blocked_by_ally_already_calling()
    test_dynamic_branch_weight_and_use_only_once()
    test_zero_weight_branch_is_excluded()
    test_seeded_smoke()

    print("\n" + "=" * 60)
    print("✅ Phase 6p 전체 테스트 통과!")
    print("=" * 60)
    print("\n📊 Phase 6p 구현 현황:")
    print("  ✅ 엔진: 인카운터 슬롯 목록 + next_free_slot (GetNextSlot)")
    print("     + RandomBranchState 동적 가중치/UseOnlyOnce")
    print("  ✅ TwoTailedRat — 슬롯 기반 동족 소환 (2턴 지연/3회 상한/카운터 공유)")


if __name__ == "__main__":
    main()
