#!/usr/bin/env python3
"""
STS2 Phase 6r 통합 테스트 — 배치13 (CubexConstruct / SoulNexus) + MinionPower.
"""
import random

import sts2_sim  # noqa: F401
from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import ENCOUNTERS, make_encounter
from sts2_sim.entities.monsters_batch13 import CubexConstruct, SoulNexus
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import MONSTER_REGISTRY, create_monster
from sts2_sim.models.sts2_power import MinionPower, POWER_REGISTRY, Vulnerable


def make_combat(monsters, seed=42, player_hp=500):
    player = Player(create_character("ironclad"))
    player._max_hp = player._current_hp = player_hp
    combat = CombatState(player, monsters, seed=seed)
    combat.start()
    return combat, player


def test_registry_and_encounters():
    assert MONSTER_REGISTRY["cubex_construct"] is CubexConstruct
    assert MONSTER_REGISTRY["soul_nexus"] is SoulNexus
    assert POWER_REGISTRY["minion"] is MinionPower
    for eid in ("cubex_construct_normal", "soul_nexus_elite"):
        assert eid in ENCOUNTERS, f"미등록 인카운터: {eid}"

    assert create_monster("cubex_construct").min_initial_hp == 65
    nexus = create_monster("soul_nexus")
    assert nexus.min_initial_hp == 234 and nexus.max_initial_hp == 234
    print("✅ 몬스터 2종 + MinionPower + 인카운터 2종 등록 + HP 확인")


def test_minion_power_persists_after_death():
    """MinionPower는 소유자 사망 후에도 제거되지 않는다
    (원본 ShouldPowerBeRemovedAfterOwnerDeath()=false)."""
    monster = create_monster("cubex_construct")
    combat, player = make_combat([monster], seed=1)
    monster.apply_power(MinionPower(1))
    monster.apply_power(Vulnerable(2), applier=player)  # Artifact가 막는다
    assert monster.has_power("minion")

    monster.lose_hp(monster.current_hp)
    combat.reap_deaths()
    assert monster.has_power("minion"), "사망 후 MinionPower가 제거됨"
    print("✅ MinionPower 사망 후 유지 확인")


def test_cubex_opening_block_artifact_and_cycle():
    """개전 블록 13 + Artifact 1, CHARGE_UP → BLAST → BLAST_2 → EXPEL → BLAST."""
    cubex = CubexConstruct()
    combat, player = make_combat([cubex], seed=2)
    sm = cubex._move_state_machine
    assert cubex.block == 13, f"개전 블록 13 불일치: {cubex.block}"
    assert cubex.get_power_amount("artifact") == 1

    cubex.apply_power(Vulnerable(2), applier=player)
    assert not cubex.has_power("vulnerable"), "Artifact가 디버프를 막지 못함"
    assert cubex.get_power_amount("artifact") == 0

    assert sm.get_current_move_name() == "CHARGE_UP_MOVE"
    hp = player.current_hp
    cubex.take_turn([player])
    assert player.current_hp == hp, "CHARGE_UP이 피해를 줌"
    assert cubex.get_power_amount("strength") == 2
    assert sm.get_current_move_name() == "REPEATER_BLAST_MOVE"

    hp = player.current_hp
    cubex.take_turn([player])
    assert player.current_hp == hp - (7 + 2), "BLAST 7딜 + 힘2 불일치"
    assert cubex.get_power_amount("strength") == 4, "BLAST 후 힘 +2 미적용"
    assert sm.get_current_move_name() == "REPEATER_BLAST_MOVE_2"

    hp = player.current_hp
    cubex.take_turn([player])
    assert player.current_hp == hp - (7 + 4)
    assert cubex.get_power_amount("strength") == 6
    assert sm.get_current_move_name() == "EXPEL_MOVE"

    hp = player.current_hp
    cubex.take_turn([player])
    assert player.current_hp == hp - (5 + 6) * 2, "EXPEL 5딜×2 + 힘6 불일치"
    assert cubex.get_power_amount("strength") == 6, "EXPEL은 힘을 올리지 않는다"
    assert sm.get_current_move_name() == "REPEATER_BLAST_MOVE", \
        "EXPEL 이후 BLAST로 복귀하지 않음 (CHARGE_UP은 1회만)"
    print("✅ CubexConstruct 개전 블록13/Artifact1 + 4무브 순환 + 힘 누적 확인")


def test_soul_nexus_branches_and_effects():
    """SOUL_BURN(29) / MAELSTROM(6×4) / DRAIN_LIFE(18 + 취약2 + 약화2),
    세 분기 모두 CannotRepeat."""
    nexus = SoulNexus()
    combat, player = make_combat([nexus], seed=3, player_hp=5000)
    sm = nexus._move_state_machine
    assert sm.get_current_move_name() == "SOUL_BURN_MOVE"

    hp = player.current_hp
    nexus.take_turn([player])
    assert player.current_hp == hp - 29, "SOUL_BURN 29딜 불일치"

    seen = []
    for _ in range(40):
        seen.append(sm.get_current_move_name())
        nexus.take_turn([player])
    assert set(seen) == {"SOUL_BURN_MOVE", "MAELSTROM_MOVE", "DRAIN_LIFE_MOVE"}
    for i in range(len(seen) - 1):
        assert seen[i] != seen[i + 1], f"CannotRepeat 위반: {seen}"
    print("✅ SoulNexus 3분기 전부 등장 + CannotRepeat 확인")


def test_soul_nexus_move_damage_and_debuffs():
    nexus = SoulNexus()
    combat, player = make_combat([nexus], seed=4, player_hp=5000)
    sm = nexus._move_state_machine

    maelstrom = sm.states_by_name["MAELSTROM_MOVE"]
    sm.force_current_state(maelstrom)
    hp = player.current_hp
    nexus.take_turn([player])
    assert player.current_hp == hp - 6 * 4, "MAELSTROM 6딜×4 불일치"

    drain = sm.states_by_name["DRAIN_LIFE_MOVE"]
    sm.force_current_state(drain)
    hp = player.current_hp
    nexus.take_turn([player])
    assert player.current_hp == hp - 18, "DRAIN_LIFE 18딜 불일치"
    assert player.get_power_amount("vulnerable") == 2
    assert player.get_power_amount("weak") == 2
    print("✅ MAELSTROM 6x4 / DRAIN_LIFE 18딜+취약2+약화2 확인")


def test_seeded_smoke():
    for eid in ("cubex_construct_normal", "soul_nexus_elite"):
        for seed in range(3):
            player = Player(create_character("ironclad"))
            monsters = make_encounter(eid, random.Random(seed))
            combat = CombatState(player, monsters, seed=seed)
            result = combat.run(SimplePolicy(), max_turns=80)
            assert isinstance(result.victory, bool)
    print("✅ 신규 인카운터 2종 × 3시드 전투 스모크 통과")


def main():
    print("🧪 STS2 Phase 6r 통합 테스트\n")
    test_registry_and_encounters()
    test_minion_power_persists_after_death()
    test_cubex_opening_block_artifact_and_cycle()
    test_soul_nexus_branches_and_effects()
    test_soul_nexus_move_damage_and_debuffs()
    test_seeded_smoke()

    print("\n" + "=" * 60)
    print("✅ Phase 6r 전체 테스트 통과!")
    print("=" * 60)
    print("\n📊 Phase 6r 구현 현황:")
    print("  ✅ CubexConstruct (개전 블록13+Artifact1, 힘 누적 4무브 순환)")
    print("  ✅ SoulNexus (엘리트, 3분기 CannotRepeat)")
    print("  ✅ MinionPower — 하수인 표식 (사망 후에도 유지)")


if __name__ == "__main__":
    main()
