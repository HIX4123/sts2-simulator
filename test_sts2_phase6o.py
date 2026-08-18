#!/usr/bin/env python3
"""
STS2 Phase 6o 통합 테스트 — 전투 중 소환 엔진 + 배치12.

엔진 확장: CombatState.add_monster(원본 CreatureCmd.Add),
PowerModel.ShouldStopCombatFromEnding 대응, 사망 훅 중 소환에 대한
reap_deaths 순회 안전성.
몬스터: PhrogParasite(엘리트) — 사망 시 InfestedPower가 Wriggler 4마리 소환.
"""
import random

import sts2_sim  # noqa: F401 — 레지스트리 등록
from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import ENCOUNTERS, make_encounter
from sts2_sim.entities.monsters_batch7c import Wriggler
from sts2_sim.entities.monsters_batch12 import PhrogParasite
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import MONSTER_REGISTRY, create_monster
from sts2_sim.models.sts2_power import InfestedPower, POWER_REGISTRY


def make_combat(monsters, seed=42, player_hp=None):
    player = Player(create_character("ironclad"))
    if player_hp is not None:
        player._max_hp = player._current_hp = player_hp
    combat = CombatState(player, monsters, seed=seed)
    combat.start()
    player.energy = player.max_energy
    return combat, player


def test_registry_and_encounter():
    assert MONSTER_REGISTRY["phrog_parasite"] is PhrogParasite
    assert POWER_REGISTRY["infested"] is InfestedPower
    assert "phrog_parasite_elite" in ENCOUNTERS

    monsters = make_encounter("phrog_parasite_elite", random.Random(1))
    assert len(monsters) == 1 and isinstance(monsters[0], PhrogParasite)
    assert monsters[0].slot_name == "phrog", "phrog 슬롯 미배정"
    assert monsters[0].min_initial_hp == 61 and monsters[0].max_initial_hp == 64
    print("✅ PhrogParasite 몬스터·InfestedPower·인카운터 등록 + HP 61~64 확인")


def test_move_cycle_infect_and_lash():
    """INFECT(감염 3장) ↔ LASH(4딜×4) 고정 교대."""
    phrog = PhrogParasite()
    combat, player = make_combat([phrog], seed=2, player_hp=300)
    sm = phrog._move_state_machine
    assert phrog.get_power_amount("infested") == 4

    assert sm.get_current_move_name() == "INFECT_MOVE"
    phrog.take_turn([player])
    infections = [c for c in combat.discard_pile if c.card_id == "infection"]
    assert len(infections) == 3, f"감염 3장이 아님: {len(infections)}"
    assert sm.get_current_move_name() == "LASH_MOVE"

    hp = player.current_hp
    phrog.take_turn([player])
    assert player.current_hp == hp - 4 * 4, "LASH 4딜×4 불일치"
    assert sm.get_current_move_name() == "INFECT_MOVE", "고정 교대 복귀 실패"
    print("✅ PhrogParasite INFECT(감염3) ↔ LASH(4딜×4) 교대 확인")


def test_death_spawns_four_stunned_wrigglers():
    """사망 시 Wriggler 4마리가 wriggler1~4 슬롯에 스턴 상태로 소환된다."""
    phrog = PhrogParasite()
    combat, player = make_combat([phrog], seed=3, player_hp=300)

    assert not combat._combat_is_won()
    phrog.lose_hp(phrog.current_hp)
    assert not combat._combat_is_won(), "소환 전에 승리로 오판함"

    spawned = combat.alive_enemies
    assert len(spawned) == 4, f"Wriggler 4마리가 아님: {len(spawned)}"
    assert all(isinstance(m, Wriggler) for m in spawned)
    assert [m.slot_name for m in spawned] == [
        "wriggler1", "wriggler2", "wriggler3", "wriggler4"]
    # StartStunned — 소환 당한 턴은 SPAWNED_MOVE(무행동)
    assert all(m._move_state_machine.get_current_move_name() == "SPAWNED_MOVE"
               for m in spawned), "소환된 Wriggler가 스턴 상태가 아님"
    # 홀수 슬롯 → NASTY_BITE, 짝수 슬롯 → WRIGGLE 로 갈린다
    assert [m.starts_with_wriggle for m in spawned] == [False, True, False, True]
    assert all(m.current_hp > 0 and m.max_hp >= 17 for m in spawned), "HP 미초기화"
    assert not phrog.has_power("infested"), "소환 후 Infested가 남아 승리를 영구 차단함"
    print("✅ 사망 시 Wriggler 4마리 스턴 소환 + 슬롯/시작무브 배정 확인")


def test_spawned_wrigglers_act_after_stun_and_combat_can_end():
    """소환된 Wriggler는 1턴 대기 후 행동하고, 전부 잡으면 전투가 끝난다."""
    phrog = PhrogParasite()
    combat, player = make_combat([phrog], seed=4, player_hp=300)
    phrog.lose_hp(phrog.current_hp)
    combat.reap_deaths()
    spawned = list(combat.alive_enemies)

    hp = player.current_hp
    for w in spawned:
        w.take_turn([player])
    assert player.current_hp == hp, "스턴 턴에 행동함"

    hp = player.current_hp
    for w in spawned:
        w.take_turn([player])
    assert player.current_hp < hp, "스턴 해제 후에도 행동하지 않음"

    for w in spawned:
        w.lose_hp(w.current_hp)
    assert combat._combat_is_won(), "소환체 전멸 후에도 전투가 끝나지 않음"
    print("✅ 소환 Wriggler 1턴 대기 → 행동 → 전멸 시 정상 종료 확인")


def test_add_monster_blocked_after_combat_over():
    """전투 종료 후 소환은 무시된다 (원본 IsLiveCombat 가드)."""
    phrog = PhrogParasite()
    combat, player = make_combat([phrog], seed=5, player_hp=300)
    combat._combat_over = True
    before = len(combat.monsters)
    combat.add_monster(Wriggler(), slot_name="wriggler1")
    assert len(combat.monsters) == before, "종료 후에도 소환이 수행됨"
    print("✅ 전투 종료 후 add_monster 차단 확인")


def test_spawn_during_player_turn_does_not_end_combat_early():
    """플레이어가 막타를 내도 소환이 일어나 전투가 계속된다 (전체 루프).

    턴 시작 드로우 이후 첫 공격 카드로 HP를 1로 만든 Phrog를 처치한다 —
    승리 판정은 카드 플레이 직후 경로(play_card → reap_deaths)를 탄다."""
    for seed in range(3):
        phrog = PhrogParasite()
        combat, player = make_combat([phrog], seed=seed, player_hp=400)

        class KillThenEnd:
            def __init__(self):
                self.done = False

            def choose(self, state):
                if self.done:
                    return None
                for card in state.hand:
                    if card.card_type.name == "ATTACK" and state.is_card_playable(card):
                        self.done = True
                        target = state.alive_enemies[0]
                        target._current_hp = 1  # 이 카드가 확실히 막타가 되도록
                        return (card, target)
                return None

        result = combat.run(KillThenEnd(), max_turns=1)
        assert not result.victory, "소환 몬스터가 있는데 승리 처리됨"
        assert len(combat.alive_enemies) == 4, \
            f"소환 후 적이 4마리가 아님: {len(combat.alive_enemies)}"
        assert all(isinstance(m, Wriggler) for m in combat.alive_enemies)
    print("✅ 플레이어 막타 → 소환 → 전투 계속 (조기 승리 방지) 확인")


def test_seeded_smoke():
    for seed in range(5):
        player = Player(create_character("ironclad"))
        monsters = make_encounter("phrog_parasite_elite", random.Random(seed))
        combat = CombatState(player, monsters, seed=seed)
        result = combat.run(SimplePolicy(), max_turns=80)
        assert isinstance(result.victory, bool)
    print("✅ phrog_parasite_elite 5시드 전투 스모크 통과")


def main():
    print("🧪 STS2 Phase 6o 통합 테스트\n")
    test_registry_and_encounter()
    test_move_cycle_infect_and_lash()
    test_death_spawns_four_stunned_wrigglers()
    test_spawned_wrigglers_act_after_stun_and_combat_can_end()
    test_add_monster_blocked_after_combat_over()
    test_spawn_during_player_turn_does_not_end_combat_early()
    test_seeded_smoke()

    print("\n" + "=" * 60)
    print("✅ Phase 6o 전체 테스트 통과!")
    print("=" * 60)
    print("\n📊 Phase 6o 구현 현황:")
    print("  ✅ 엔진: CombatState.add_monster (전투 중 소환)")
    print("     + ShouldStopCombatFromEnding + reap_deaths 순회 안전성")
    print("  ✅ 신규 파워 InfestedPower (사망 시 Wriggler 4마리 소환)")
    print("  ✅ PhrogParasite(엘리트) + phrog_parasite_elite 인카운터")


if __name__ == "__main__":
    main()
