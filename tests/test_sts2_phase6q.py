#!/usr/bin/env python3
"""
STS2 Phase 6q 통합 테스트 — GremlinMerc(골드 절취 + 사망 시 동료 소환).

신규 파워 3종: ThieveryPower(골드 절취 누적), SurprisePower(사망 시
SneakyGremlin/FatGremlin 소환 + 훔친 골드 이관), HeistPower(보유자 사망 시 환수).
"""
import random

import sts2_sim  # noqa: F401
from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import ENCOUNTER_SLOTS, ENCOUNTERS, make_encounter
from sts2_sim.entities.monsters_batch12 import GremlinMerc
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import FatGremlin, MONSTER_REGISTRY
from sts2_sim.entities.monsters_extra import SneakyGremlin
from sts2_sim.models.sts2_power import (
    HeistPower, POWER_REGISTRY, SurprisePower, ThieveryPower,
)


def make_combat(monsters, seed=42, player_hp=500):
    character = create_character("ironclad")
    player = Player(character)
    player._max_hp = player._current_hp = player_hp
    combat = CombatState(player, monsters, seed=seed)
    combat.start()
    return combat, player, character


def test_registry_and_encounter():
    assert MONSTER_REGISTRY["gremlin_merc"] is GremlinMerc
    for pid, cls in (("thievery", ThieveryPower), ("surprise", SurprisePower),
                     ("heist", HeistPower)):
        assert POWER_REGISTRY[pid] is cls, f"미등록 파워: {pid}"
    assert "gremlin_merc_normal" in ENCOUNTERS
    assert ENCOUNTER_SLOTS["gremlin_merc_normal"] == ["merc", "sneaky", "fat"]

    monsters = make_encounter("gremlin_merc_normal", random.Random(1))
    assert len(monsters) == 1 and isinstance(monsters[0], GremlinMerc)
    assert monsters[0].slot_name == "merc"
    assert monsters[0].min_initial_hp == 47 and monsters[0].max_initial_hp == 49
    print("✅ GremlinMerc + 파워 3종 + gremlin_merc_normal 인카운터 등록 확인")


def test_opening_powers():
    merc = GremlinMerc()
    combat, player, _ = make_combat([merc], seed=2)
    assert merc.has_power("surprise")
    thievery = merc._powers["thievery"]
    assert thievery.amount == 20
    assert thievery.target is player, "Thievery 대상이 플레이어가 아님"
    print("✅ 개전 SurprisePower + ThieveryPower(20, 대상=플레이어) 확인")


def test_move_cycle_damage_and_steal():
    """GIMME(7×2) → DOUBLE_SMASH(6×2 + 약화2) → HEHE(8 + 힘2), 매 무브마다 절취."""
    merc = GremlinMerc()
    combat, player, character = make_combat([merc], seed=3)
    character.gold = 200
    sm = merc._move_state_machine

    assert sm.get_current_move_name() == "GIMME_MOVE"
    hp = player.current_hp
    merc.take_turn([player])
    assert player.current_hp == hp - 7 * 2, "GIMME 7딜×2 불일치"
    assert character.gold == 180, f"GIMME 절취 20 불일치: {character.gold}"
    assert sm.get_current_move_name() == "DOUBLE_SMASH_MOVE"

    hp = player.current_hp
    merc.take_turn([player])
    assert player.current_hp == hp - 6 * 2, "DOUBLE_SMASH 6딜×2 불일치"
    assert player.get_power_amount("weak") == 2
    assert character.gold == 160
    assert sm.get_current_move_name() == "HEHE_MOVE"

    hp = player.current_hp
    merc.take_turn([player])
    assert player.current_hp == hp - 8, "HEHE 8딜 불일치"
    assert merc.get_power_amount("strength") == 2
    assert character.gold == 140
    assert sm.get_current_move_name() == "GIMME_MOVE", "3순환 복귀 실패"
    assert merc._powers["thievery"].stolen_gold == 60
    print("✅ GIMME/DOUBLE_SMASH/HEHE 3순환 + 무브마다 골드 20 절취 확인")


def test_steal_capped_by_player_gold():
    """보유 골드보다 많이 훔치지 못한다 (원본 Min(Amount, Gold))."""
    merc = GremlinMerc()
    combat, player, character = make_combat([merc], seed=4)
    character.gold = 5
    merc.take_turn([player])
    assert character.gold == 0, f"골드가 음수로 내려감: {character.gold}"
    assert merc._powers["thievery"].stolen_gold == 5

    merc.take_turn([player])
    assert character.gold == 0
    assert merc._powers["thievery"].stolen_gold == 5, "골드 0인데 추가 절취됨"
    print("✅ 절취량이 보유 골드로 제한 + 0일 때 미발동 확인")


def test_death_spawns_two_gremlins_and_transfers_gold():
    merc = GremlinMerc()
    combat, player, character = make_combat([merc], seed=5)
    character.gold = 200
    merc.take_turn([player])  # 20 절취
    merc.take_turn([player])  # 20 절취
    assert character.gold == 160

    assert not combat._combat_is_won()
    merc.lose_hp(merc.current_hp)
    assert not combat._combat_is_won(), "소환 전에 승리로 오판함"

    spawned = combat.alive_enemies
    assert len(spawned) == 2, f"소환된 그렘린이 2마리가 아님: {len(spawned)}"
    assert isinstance(spawned[0], SneakyGremlin) and spawned[0].slot_name == "sneaky"
    assert isinstance(spawned[1], FatGremlin) and spawned[1].slot_name == "fat"
    assert spawned[1].get_power_amount("heist") == 40, "훔친 골드가 이관되지 않음"
    assert not merc.has_power("surprise"), "소환 후 Surprise가 남아 승리를 영구 차단함"
    print("✅ 사망 시 Sneaky/Fat 소환 + 훔친 골드 40 이관 확인")


def test_killing_fat_gremlin_returns_gold():
    merc = GremlinMerc()
    combat, player, character = make_combat([merc], seed=6)
    character.gold = 200
    merc.take_turn([player])
    merc.lose_hp(merc.current_hp)
    combat.reap_deaths()
    fat = next(m for m in combat.alive_enemies if isinstance(m, FatGremlin))

    assert character.gold == 180
    fat.lose_hp(fat.current_hp)
    combat.reap_deaths()
    assert character.gold == 200, f"골드가 환수되지 않음: {character.gold}"
    print("✅ FatGremlin 처치 시 훔친 골드 환수 확인")


def test_fat_gremlin_escape_keeps_gold_lost():
    """도주하면 골드는 돌아오지 않는다 (원본 CalculateGoldProportion의 핵심)."""
    merc = GremlinMerc()
    combat, player, character = make_combat([merc], seed=7)
    character.gold = 200
    merc.take_turn([player])
    merc.lose_hp(merc.current_hp)
    combat.reap_deaths()
    fat = next(m for m in combat.alive_enemies if isinstance(m, FatGremlin))

    fat.take_turn([player])  # SPAWNED_MOVE (대기)
    fat.take_turn([player])  # FLEE_MOVE
    assert fat.escaped, "FatGremlin이 도주하지 않음"
    combat.reap_deaths()
    assert character.gold == 180, "도주했는데 골드가 환수됨"
    print("✅ FatGremlin 도주 시 골드 미환수 확인")


def test_seeded_smoke():
    for seed in range(5):
        player = Player(create_character("ironclad"))
        monsters = make_encounter("gremlin_merc_normal", random.Random(seed))
        combat = CombatState(player, monsters, seed=seed)
        result = combat.run(SimplePolicy(), max_turns=80)
        assert isinstance(result.victory, bool)
        assert player.character.gold >= 0, "골드가 음수"
    print("✅ gremlin_merc_normal 5시드 전투 스모크 통과")


def main():
    print("🧪 STS2 Phase 6q 통합 테스트\n")
    test_registry_and_encounter()
    test_opening_powers()
    test_move_cycle_damage_and_steal()
    test_steal_capped_by_player_gold()
    test_death_spawns_two_gremlins_and_transfers_gold()
    test_killing_fat_gremlin_returns_gold()
    test_fat_gremlin_escape_keeps_gold_lost()
    test_seeded_smoke()

    print("\n" + "=" * 60)
    print("✅ Phase 6q 전체 테스트 통과!")
    print("=" * 60)
    print("\n📊 Phase 6q 구현 현황:")
    print("  ✅ GremlinMerc — 무브마다 골드 절취, 사망 시 동료 2종 소환")
    print("  ✅ 신규 파워 3종 (Thievery/Surprise/Heist)")
    print("  ✅ gremlin_merc_normal 인카운터 (원본 구성 복원)")


if __name__ == "__main__":
    main()
