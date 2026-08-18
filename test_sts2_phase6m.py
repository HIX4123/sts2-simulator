#!/usr/bin/env python3
"""
STS2 Phase 6m 통합 테스트 — Waterfall Giant 보스.
정상 무브 순환, Steam Eruption의 2단계 사망 lifecycle, Doom 예외를 검증한다.
"""
import random

import sts2_sim  # noqa: F401 — registry 등록
from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import ENCOUNTERS, make_encounter
from sts2_sim.entities.monsters_batch10 import WaterfallGiant
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import IntentType, MONSTER_REGISTRY, create_monster
from sts2_sim.models.sts2_power import (
    Doom, POWER_REGISTRY, STS2Power, SteamEruptionPower, Strength,
)


def make_combat(seed=42):
    player = Player(create_character("ironclad"))
    giant = create_monster("waterfall_giant")
    combat = CombatState(player, [giant], seed=seed)
    combat.start()
    return combat, player, giant


def test_registry_encounter_and_hp():
    assert MONSTER_REGISTRY["waterfall_giant"] is WaterfallGiant
    assert POWER_REGISTRY["steam_eruption"] is SteamEruptionPower
    assert "waterfall_giant_boss" in ENCOUNTERS

    monsters = make_encounter("waterfall_giant_boss", random.Random(1))
    assert len(monsters) == 1 and isinstance(monsters[0], WaterfallGiant)
    assert monsters[0].min_initial_hp == 240
    assert monsters[0].max_initial_hp == 240
    print("✅ Waterfall Giant 몬스터·파워·인카운터 등록 + HP 240 확인")


def test_fixed_cycle_move_effects_and_pressure_gun_growth():
    combat, player, giant = make_combat(seed=1)
    player._max_hp = player._current_hp = 500
    sm = giant._move_state_machine

    assert sm.get_current_move_name() == "PRESSURIZE_MOVE"
    giant.take_turn([player])
    assert giant.get_power_amount("steam_eruption") == 15
    assert sm.get_current_move_name() == "STOMP_MOVE"

    hp = player.current_hp
    giant.take_turn([player])
    assert player.current_hp == hp - 15
    assert player.get_power_amount("weak") == 1
    assert giant.get_power_amount("steam_eruption") == 18
    assert sm.get_current_move_name() == "RAM_MOVE"

    hp = player.current_hp
    giant.take_turn([player])
    assert player.current_hp == hp - 10
    assert giant.get_power_amount("steam_eruption") == 21
    assert sm.get_current_move_name() == "SIPHON_MOVE"

    giant._current_hp = 200
    giant.take_turn([player])
    assert giant.current_hp == 210
    assert giant.get_power_amount("steam_eruption") == 24
    assert sm.get_current_move_name() == "PRESSURE_GUN_MOVE"
    assert giant.get_current_intent().damage == 20

    hp = player.current_hp
    giant.take_turn([player])
    assert player.current_hp == hp - 20
    assert giant.get_power_amount("steam_eruption") == 27
    assert sm.states_by_name["PRESSURE_GUN_MOVE"].intent.damage == 25
    assert sm.get_current_move_name() == "PRESSURE_UP_MOVE"

    hp = player.current_hp
    giant.take_turn([player])
    assert player.current_hp == hp - 13
    assert giant.get_power_amount("steam_eruption") == 30
    assert sm.get_current_move_name() == "STOMP_MOVE"

    for expected in ("STOMP_MOVE", "RAM_MOVE", "SIPHON_MOVE"):
        assert sm.get_current_move_name() == expected
        giant.take_turn([player])
    assert sm.get_current_move_name() == "PRESSURE_GUN_MOVE"
    assert giant.get_current_intent().damage == 25

    hp = player.current_hp
    giant.take_turn([player])
    assert player.current_hp == hp - 25
    assert sm.states_by_name["PRESSURE_GUN_MOVE"].intent.damage == 30
    assert giant.get_power_amount("steam_eruption") == 42
    print("✅ 고정 무브 순환 + 피해/Weak/회복/Steam + Pressure Gun 20→25→30 확인")


def test_steam_eruption_two_death_lifecycle():
    combat, player, giant = make_combat(seed=2)
    giant.apply_power(SteamEruptionPower(42))
    giant.apply_power(Strength(7))

    result = giant.take_damage(giant.current_hp, source=player,
                               powered=False, unblockable=True)
    assert result["killed"]
    assert not combat._combat_is_won(), "첫 사망을 전투 승리로 오판함"
    assert combat.deaths_this_combat == 1
    assert giant.max_hp == 999_999_999 and giant.current_hp == 999_999_999
    assert giant in combat.alive_enemies
    assert giant._move_state_machine.get_current_move_name() == "ABOUT_TO_BLOW_MOVE"
    assert giant.get_power_amount("steam_eruption") == 42
    assert not giant.has_power("strength"), "첫 사망 뒤 일반 owner 파워가 남음"

    hp = player.current_hp
    giant.take_turn([player])
    assert player.current_hp == hp
    assert not giant.has_power("steam_eruption")
    assert giant._move_state_machine.get_current_move_name() == "EXPLODE_MOVE"
    assert giant.get_current_intent().intent_type == IntentType.ATTACK
    assert giant.get_current_intent().damage == 42

    giant.take_turn([player])
    assert player.current_hp == hp - 42
    assert giant.is_dead
    assert combat._combat_is_won()
    assert combat.deaths_this_combat == 2
    assert not combat.alive_enemies
    combat.reap_deaths()
    assert combat.deaths_this_combat == 2, "최종 사망이 중복 집계됨"
    print("✅ 첫 사망 부활→Steam snapshot→42 폭발→최종 사망 lifecycle 확인")


def test_plain_death_and_doom_guard():
    combat, player, giant = make_combat(seed=3)
    giant.take_damage(giant.current_hp, source=player, powered=False, unblockable=True)
    assert combat._combat_is_won()
    assert combat.deaths_this_combat == 1
    assert giant.max_hp == 240, "Steam 없는 일반 사망에서 부활함"
    combat.reap_deaths()
    assert combat.deaths_this_combat == 1

    combat, player, giant = make_combat(seed=4)
    giant.take_turn([player])  # PRESSURIZE_MOVE: Steam 15
    giant.apply_power(Doom(999))
    combat._trigger_doom()
    assert giant.is_alive, "Steam 보유 중 Doom이 Waterfall Giant를 제거함"
    giant.remove_power("steam_eruption")
    combat._trigger_doom()
    assert giant.is_dead, "Steam 제거 뒤 Doom 처치가 적용되지 않음"
    assert combat._combat_is_won()
    print("✅ Steam 없는 일반 사망 + Steam 보유 중 Doom 제거 방지 확인")


def test_player_turn_end_death_does_not_end_combat_early():
    combat, player, giant = make_combat(seed=5)
    giant.apply_power(SteamEruptionPower(9))

    class KillGiantAtTurnEnd(STS2Power):
        power_id = "test_kill_giant_at_turn_end"

        def on_turn_end(self):
            giant.lose_hp(giant.current_hp)
            player.remove_power(self.power_id)

    class EndTurnPolicy:
        def choose(self, state):
            return None

    player.apply_power(KillGiantAtTurnEnd())
    result = combat.run(EndTurnPolicy(), max_turns=1)

    assert not result.victory
    assert combat.deaths_this_combat == 1
    assert giant.current_hp == 999_999_999
    assert giant._move_state_machine.get_current_move_name() == "ABOUT_TO_BLOW_MOVE"
    assert giant._move_state_machine.history == []
    assert giant in combat.alive_enemies
    print("✅ 플레이어 턴 종료 사망의 조기 승리 방지 + 다음 턴 특수 무브 대기 확인")


def test_waterfall_giant_seeded_smoke():
    for seed in range(5):
        player = Player(create_character("ironclad"))
        monsters = make_encounter("waterfall_giant_boss", random.Random(seed))
        combat = CombatState(player, monsters, seed=seed)
        result = combat.run(SimplePolicy(), max_turns=60)
        assert isinstance(result.victory, bool)
    print("✅ Waterfall Giant 보스 5시드 전투 스모크 테스트 통과")


def main():
    print("🧪 STS2 Phase 6m 통합 테스트\n")
    test_registry_encounter_and_hp()
    test_fixed_cycle_move_effects_and_pressure_gun_growth()
    test_steam_eruption_two_death_lifecycle()
    test_plain_death_and_doom_guard()
    test_player_turn_end_death_does_not_end_combat_early()
    test_waterfall_giant_seeded_smoke()

    print("\n" + "=" * 60)
    print("✅ Phase 6m 전체 테스트 통과!")
    print("=" * 60)


if __name__ == "__main__":
    main()
