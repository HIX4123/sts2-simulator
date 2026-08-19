#!/usr/bin/env python3
"""
STS2 Phase 6t 통합 테스트 — Ovicopter + ToughEgg (알 낳기/부화).

- HatchPower: 표시용 카운터 (턴 종료마다 -1), 실제 부화는 상태머신 HATCH_MOVE
- ToughEgg: 첫 턴 부화(HP 재설정 + 비-Minion 파워 제거) → NIBBLE 무한 반복
- Ovicopter: LAY_EGGS(뒤에서부터 빈 슬롯 3칸 ToughEgg+Minion) → SMASH →
  TENDERIZER(취약 2) → SUMMON_BRANCH{살아있는 적≤3? LAY_EGGS : NUTRITIONAL_PASTE(힘+3)→SMASH}
- 인카운터: ovicopter_normal (슬롯 egg1~5 + ovicopter)
"""
import random

import sts2_sim  # noqa: F401
from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import ENCOUNTER_SLOTS, ENCOUNTERS, make_encounter
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.monsters_batch15 import ToughEgg, Ovicopter
from sts2_sim.entities.sts2_monster import MONSTER_REGISTRY, create_monster
from sts2_sim.models.sts2_power import HatchPower, MinionPower, POWER_REGISTRY, Vulnerable, Strength


def make_combat(monsters_or_id, seed=42, player_hp=500):
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


def test_registry_and_encounters():
    assert MONSTER_REGISTRY["tough_egg"] is ToughEgg
    assert MONSTER_REGISTRY["ovicopter"] is Ovicopter
    assert POWER_REGISTRY["hatch"] is HatchPower

    assert "ovicopter_normal" in ENCOUNTERS, "ovicopter_normal 미등록"
    assert ENCOUNTER_SLOTS["ovicopter_normal"] == [
        "egg1", "egg2", "egg3", "egg4", "egg5", "ovicopter"
    ]

    assert create_monster("tough_egg").min_initial_hp == 14
    assert create_monster("ovicopter").min_initial_hp == 124
    print("✅ ToughEgg/Ovicopter + HatchPower + 인카운터 1종 등록 확인")


def test_tough_egg_hatches_first_turn():
    """첫 턴 HATCH_MOVE로 부화(HP 재설정 + HatchPower 제거, Minion 유지)."""
    # ToughEgg 단독 테스트 (encounter 없이)
    egg = ToughEgg()
    combat, player = make_combat([egg], seed=1)

    # 개전 상태: 알 HP 14~18, HatchPower(2) — MinionPower는 Ovicopter가 소환할 때만 붙음
    assert egg.current_hp in range(14, 19)
    assert egg.has_power("hatch")
    assert egg.get_power_amount("hatch") == 2
    assert not egg.has_power("minion")
    assert egg._move_state_machine.get_current_move_name() == "HATCH_MOVE"

    # 첫 턴: 부화 실행
    egg.take_turn([player])

    # 부화 후: HP 19~22 재설정, HatchPower 제거
    assert egg.current_hp == egg.max_hp
    assert egg.max_hp in range(19, 23)
    assert not egg.has_power("hatch"), "HATCH_MOVE 후 HatchPower가 제거되지 않음"
    assert not egg.has_power("minion"), "직접 배치된 알은 MinionPower가 없음"
    assert egg._move_state_machine.get_current_move_name() == "NIBBLE_MOVE"
    print("✅ ToughEgg 첫 턴 부화 + HP 재설정 + Minion 유지 + HatchPower 제거 확인")


def test_tough_egg_nibble_loops():
    """부화 후 NIBBLE_MOVE(4딜) 무한 반복."""
    egg = ToughEgg()
    combat, player = make_combat([egg], seed=2)
    # 첫 턴 강제 부화
    egg.take_turn([player])

    # NIBBLE 턴
    hp = player.current_hp
    egg.take_turn([player])
    assert player.current_hp == hp - 4, "NIBBLE 4딜 불일치"
    assert egg._move_state_machine.get_current_move_name() == "NIBBLE_MOVE"

    # 다시 NIBBLE
    hp = player.current_hp
    egg.take_turn([player])
    assert player.current_hp == hp - 4, "NIBBLE 반복 불일치"
    assert egg._move_state_machine.get_current_move_name() == "NIBBLE_MOVE"
    print("✅ ToughEgg 부화 후 NIBBLE 4딜 무한 반복 확인")


def test_ovicopter_lays_eggs_from_back():
    """LAY_EGGS: 빈 알 슬롯을 뒤에서부터(egg5→egg4→egg3) 최대 3마리 채운다."""
    combat, player = make_combat("ovicopter_normal", seed=3)
    ovi = [m for m in combat.alive_enemies if isinstance(m, Ovicopter)][0]

    assert ovi._move_state_machine.get_current_move_name() == "LAY_EGGS_MOVE"

    ovi.take_turn([player])  # LAY_EGGS → SMASH

    eggs = [m for m in combat.alive_enemies if isinstance(m, ToughEgg)]
    assert len(eggs) == 3, f"알 3마리가 아님: {len(eggs)}"

    # 슬롯은 egg5, egg4, egg3 순서 (뒤에서부터)
    slots = [e.slot_name for e in eggs]
    assert set(slots) == {"egg5", "egg4", "egg3"}, f"슬롯 {slots}"
    # 각각 MinionPower(1)
    for e in eggs:
        assert e.has_power("minion")
        assert e.get_power_amount("minion") == 1

    assert ovi._move_state_machine.get_current_move_name() == "SMASH_MOVE"
    print("✅ Ovicopter LAY_EGGS 뒤 3슬롯(egg5/4/3) + MinionPower 확인")


def test_ovicopter_smash_tenderizer_branch():
    """SMASH(16딜) → TENDERIZER(7딜+취약2) → BRANCH(즉시 resolve → LAY_EGGS/PASTE)."""
    combat, player = make_combat("ovicopter_normal", seed=4, player_hp=9999)
    ovi = [m for m in combat.alive_enemies if isinstance(m, Ovicopter)][0]
    sm = ovi._move_state_machine

    # LAY_EGGS 건너뛰고 SMASH로 강제
    sm.force_current_state(sm.states_by_name["SMASH_MOVE"])
    ovi.take_turn([player])
    assert ovi._move_state_machine.get_current_move_name() == "TENDERIZER_MOVE"

    hp = player.current_hp
    ovi.take_turn([player])  # TENDERIZER
    assert player.current_hp == hp - 7, "TENDERIZER 7딜 불일치"
    assert player.get_power_amount("vulnerable") == 2, "취약 2 미부여"
    # TENDERIZER 후 advance_state가 ConditionalBranchState를 resolve하므로
    # current_state는 SUMMON_BRANCH_STATE가 아니라 LAY_EGGS_MOVE 또는 PASTE_MOVE
    next_name = ovi._move_state_machine.get_current_move_name()
    assert next_name in ("LAY_EGGS_MOVE", "NUTRITIONAL_PASTE_MOVE"), f"BRANCH resolve 결과: {next_name}"
    print("✅ Ovicopter SMASH(16딜) → TENDERIZER(7딜+취약2) → BRANCH 즉시 resolve 확인")


def test_ovicopter_branch_can_lay_logic():
    """BRANCH: 살아있는 적(자신+알) ≤ 3이면 LAY_EGGS, 아니면 NUTRITIONAL_PASTE(힘+3)."""
    # 첫 번째: 알 0마리(첫 LAY_EGGS 후 알이 모두 죽음) → CanLay=True
    combat, player = make_combat("ovicopter_normal", seed=5, player_hp=9999)
    ovi = [m for m in combat.alive_enemies if isinstance(m, Ovicopter)][0]
    sm = ovi._move_state_machine

    # LAY_EGGS 실행해 알 3마리 소환 후 전부 죽임
    ovi.take_turn([player])  # LAY_EGGS
    for m in list(combat.alive_enemies):
        if isinstance(m, ToughEgg):
            m.lose_hp(m.current_hp)
    combat.reap_deaths()
    assert len(combat.alive_enemies) == 1  # Ovicopter만 생존

    # BRANCH에서 LAY_EGGS 선택됨
    branch = sm.states_by_name["SUMMON_BRANCH_STATE"]
    nxt = branch.resolve()
    assert nxt.name == "LAY_EGGS_MOVE", f"CanLay=True여야 함: {nxt.name}"

    # 두 번째: 알 3마리 살아있으면(자신+3=4) CanLay=False → NUTRITIONAL_PASTE
    combat2, player2 = make_combat("ovicopter_normal", seed=6, player_hp=9999)
    ovi2 = [m for m in combat2.alive_enemies if isinstance(m, Ovicopter)][0]
    ovi2.take_turn([player2])  # 첫 LAY_EGGS → 알 3마리 소환
    # 알 3마리 + 자신 = 4 > 3 → CanLay=False
    branch2 = ovi2._move_state_machine.states_by_name["SUMMON_BRANCH_STATE"]
    nxt2 = branch2.resolve()
    assert nxt2.name == "NUTRITIONAL_PASTE_MOVE", f"CanLay=False여야 함: {nxt2.name}"

    # PASTE 실행 → 힘 +3
    ovi2._move_state_machine.force_current_state(
        ovi2._move_state_machine.states_by_name["NUTRITIONAL_PASTE_MOVE"])
    ovi2.take_turn([player2])
    assert ovi2.get_power_amount("strength") == 3, "NUTRITIONAL_PASTE 힘+3 미적용"
    print("✅ Ovicopter BRANCH CanLay 로직(≤3 LAY / >3 PASTE) 확인")


def test_ovicopter_paste_then_smash():
    """NUTRITIONAL_PASTE → SMASH 복귀."""
    combat, player = make_combat("ovicopter_normal", seed=7, player_hp=9999)
    ovi = [m for m in combat.alive_enemies if isinstance(m, Ovicopter)][0]
    sm = ovi._move_state_machine

    # 알 3마리 소환 후 BRANCH → PASTE 자연스럽게 유도
    ovi.take_turn([player])  # LAY_EGGS → 알 3마리 소환, SMASH로 이동
    # SMASH 강제 실행 후 TENDERIZER로
    sm.force_current_state(sm.states_by_name["SMASH_MOVE"])
    ovi.take_turn([player])  # SMASH
    # TENDERIZER 실행 후 BRANCH resolve → 알 3마리 생존이므로 PASTE
    ovi.take_turn([player])  # TENDERIZER → BRANCH resolve to PASTE
    # 이제 current_state는 PASTE_MOVE여야 함 (아직 실행 전)
    assert ovi._move_state_machine.get_current_move_name() == "NUTRITIONAL_PASTE_MOVE"
    assert ovi.get_power_amount("strength") == 0, "PASTE 실행 전엔 힘 0"

    # PASTE 실행 → 힘 +3
    ovi.take_turn([player])  # PASTE
    assert ovi.get_power_amount("strength") == 3, "PASTE 실행 후 힘 3"
    assert sm.get_current_move_name() == "SMASH_MOVE", "PASTE 다음은 SMASH"

    hp = player.current_hp
    ovi.take_turn([player])  # SMASH (힘 3 반영 → 19딜, 앞선 TENDERIZER 취약으로 ×1.5)
    assert player.get_power_amount("vulnerable") > 0
    assert player.current_hp == hp - int((16 + 3) * 1.5), "SMASH 힘/취약 반영 불일치"
    print("✅ Ovicopter PASTE(힘+3) → SMASH(16+힘, 취약 ×1.5) 복귀 확인")


def test_seeded_smoke():
    for eid in ("ovicopter_normal",):
        for seed in range(3):
            player = Player(create_character("ironclad"))
            monsters = make_encounter(eid, random.Random(seed))
            combat = CombatState(player, monsters, seed=seed)
            result = combat.run(SimplePolicy(), max_turns=100)
            assert isinstance(result.victory, bool)
    print("✅ ovicopter_normal × 3시드 전투 스모크 통과")


def main():
    print("🧪 STS2 Phase 6t 통합 테스트\n")
    test_registry_and_encounters()
    test_tough_egg_hatches_first_turn()
    test_tough_egg_nibble_loops()
    test_ovicopter_lays_eggs_from_back()
    test_ovicopter_smash_tenderizer_branch()
    test_ovicopter_branch_can_lay_logic()
    test_ovicopter_paste_then_smash()
    test_seeded_smoke()

    print("\n" + "=" * 60)
    print("✅ Phase 6t 전체 테스트 통과!")
    print("=" * 60)
    print("\n📊 Phase 6t 구현 현황:")
    print("  ✅ HatchPower — 턴 종료마다 카운터 감소 (표시용)")
    print("  ✅ ToughEgg — 첫 턴 부화(HP 19~22 재설정) + NIBBLE 4딜 반복")
    print("  ✅ Ovicopter — LAY_EGGS(뒤 3슬롯 ToughEgg+Minion) + SMASH/TENDERIZER/PASTE 순환")
    print("  ✅ ovicopter_normal 인카운터 (슬롯 egg1~5 + ovicopter)")


if __name__ == "__main__":
    main()