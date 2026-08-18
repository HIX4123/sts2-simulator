#!/usr/bin/env python3
"""
STS2 Phase 6l 통합 테스트 — Act1(Underdocks) 완결 배치.
몬스터 5종 (CorpseSlug/SkulkingColony/TerrorEel/PhantasmalGardener/
LagavulinMatriarch) + 신규 파워 6종 (Ravenous/Shriek/Asleep/HardenedShell/
Skittish, Plating은 기존 클래스 재사용+수정) + 엔진 확장
(ConditionalBranchState, force_current_state, MonsterModel.stun, slot_name,
combat.reap_deaths의 on_any_death 브로드캐스트).
"""
import random

import sts2_sim  # noqa: F401 — CARD_REGISTRY 등록
from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import ENCOUNTERS, make_encounter
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import create_monster, MONSTER_REGISTRY
from sts2_sim.entities.monsters_batch9 import (
    CorpseSlug, SkulkingColony, TerrorEel, PhantasmalGardener, LagavulinMatriarch,
)


def make_combat(character_id="ironclad", monster_ids=("big_dummy",), seed=42):
    player = Player(create_character(character_id))
    monsters = [create_monster(mid) for mid in monster_ids]
    combat = CombatState(player, monsters, seed=seed)
    combat.start()
    player.energy = player.max_energy
    return combat, player, monsters


def test_registry_and_encounters():
    """5종 전부 MONSTER_REGISTRY + ENCOUNTERS 등록."""
    for mid in ("corpse_slug", "skulking_colony", "terror_eel",
                "phantasmal_gardener", "lagavulin_matriarch"):
        assert mid in MONSTER_REGISTRY, f"미등록: {mid}"
    for eid in ("corpse_slugs_normal", "corpse_slugs_weak", "skulking_colony_elite",
                "terror_eel_elite", "phantasmal_gardeners_elite", "lagavulin_matriarch_boss"):
        assert eid in ENCOUNTERS, f"미등록 인카운터: {eid}"
    print("✅ 몬스터 5종 + 인카운터 6종 등록 확인")


def test_hp_ranges():
    """디컴파일 MinInitialHp/MaxInitialHp(Ascension 미적용) 정확히 일치."""
    expected = {
        "corpse_slug": (25, 27),
        "skulking_colony": (75, 75),
        "terror_eel": (140, 140),
        "phantasmal_gardener": (26, 31),
        "lagavulin_matriarch": (222, 222),
    }
    for mid, (lo, hi) in expected.items():
        m = create_monster(mid)
        assert m.min_initial_hp == lo and m.max_initial_hp == hi, \
            f"{mid} HP 범위 불일치: {m.min_initial_hp}~{m.max_initial_hp} (기대 {lo}~{hi})"
    print("✅ HP 범위 5종 전부 디컴파일 기준값과 일치")


def test_corpse_slug_fixed_cycle_and_starter_index():
    """CorpseSlug: WHIP_SLAP→GLOMP→GOOP 고정 3순환, starter_move_idx로 시작 위치 결정."""
    combat, player, monsters = make_combat(monster_ids=("corpse_slug",), seed=1)
    slug = monsters[0]
    names = []
    for _ in range(6):
        names.append(slug._move_state_machine.get_current_move_name())
        slug.take_turn([player])
    assert names == ["WHIP_SLAP_MOVE", "GLOMP_MOVE", "GOOP_MOVE"] * 2, names

    s1 = CorpseSlug(starter_move_idx=1)
    combat2 = CombatState(player, [s1], seed=1)
    combat2.start()
    assert s1._move_state_machine.get_current_move_name() == "GLOMP_MOVE"
    s2 = CorpseSlug(starter_move_idx=2)
    combat3 = CombatState(player, [s2], seed=1)
    combat3.start()
    assert s2._move_state_machine.get_current_move_name() == "GOOP_MOVE"
    print("✅ CorpseSlug 고정 3순환 + starter_move_idx 시작 위치 지정 확인")


def test_corpse_slug_ravenous_on_ally_death():
    """RavenousPower: 같은 편 슬러그가 죽으면 자신을 스턴시키고 힘+4."""
    player = Player(create_character("ironclad"))
    s1 = CorpseSlug(starter_move_idx=0)
    s2 = CorpseSlug(starter_move_idx=1)
    combat = CombatState(player, [s1, s2], seed=1)
    combat.start()
    prev_move = s2._move_state_machine.get_current_move_name()
    s1._current_hp = 1
    player.energy = player.max_energy
    combat.draw_cards(5)
    strikes = [c for c in combat.hand if c.card_id == "strike"]
    combat.play_card(strikes[0], s1)
    assert s1.is_dead
    assert s2.get_power_amount("strength") == 4, "Ravenous 힘 획득 실패"
    assert s2._move_state_machine.get_current_move_name() == "STUNNED", "Ravenous 스턴 실패"
    # 스턴 후 원래 위치(prev_move)로 복귀해야 함
    s2.take_turn([player])
    assert s2._move_state_machine.get_current_move_name() != "STUNNED"
    print(f"✅ CorpseSlug Ravenous: 동료 사망 시 힘+4, 1턴 스턴 후 {prev_move} 로 복귀")


def test_skulking_colony_fixed_cycle_and_hardened_shell_caps_burst():
    """SkulkingColony: ZOOM→ZOOM_2→INERTIA→PIERCING_STABS 고정 4순환.
    HardenedShellPower(20): 한 턴 총 HP 손실을 20으로 제한."""
    combat, player, monsters = make_combat(monster_ids=("skulking_colony",), seed=1)
    colony = monsters[0]
    names = []
    for _ in range(4):
        names.append(colony._move_state_machine.get_current_move_name())
        colony.take_turn([player])
    assert names == ["ZOOM_MOVE", "ZOOM_MOVE_2", "INERTIA_MOVE", "PIERCING_STABS_MOVE"], names

    hp0 = colony.current_hp
    colony.take_damage(15, source=player)
    colony.take_damage(15, source=player)  # 누적 30 -> 20으로 캡
    lost = hp0 - colony.current_hp
    assert lost == 20, f"HardenedShell 캡 실패: {lost}"
    print("✅ SkulkingColony 고정 4순환 + HardenedShell 한 턴 20 HP 손실 캡 확인")


def test_hardened_shell_resets_each_turn():
    """HardenedShellPower 누적치는 자신의 턴 시작마다 초기화."""
    combat, player, monsters = make_combat(monster_ids=("skulking_colony",), seed=1)
    colony = monsters[0]
    colony.take_damage(20, source=player)
    assert colony._powers["hardened_shell"]._damage_this_turn == 20
    for power in list(colony._powers.values()):
        on_start = getattr(power, "on_turn_start", None)
        if on_start:
            on_start()
    assert colony._powers["hardened_shell"]._damage_this_turn == 0
    hp0 = colony.current_hp
    colony.take_damage(20, source=player)
    assert hp0 - colony.current_hp == 20, "리셋 후 새 턴 캡 재적용 실패"
    print("✅ HardenedShell 턴 시작 시 누적치 초기화 확인")


def test_terror_eel_fixed_cycle_and_shriek_trigger():
    """TerrorEel: CRASH↔THRASH 고정 2교대. HP<=70(Shriek)이면 1턴 스턴 후
    TERROR_MOVE(취약+99)로 강제 전환, 이후 CRASH로 복귀."""
    combat, player, monsters = make_combat(monster_ids=("terror_eel",), seed=1)
    eel = monsters[0]
    names = []
    for _ in range(4):
        names.append(eel._move_state_machine.get_current_move_name())
        eel.take_turn([player])
    assert names == ["CRASH_MOVE", "THRASH_MOVE", "CRASH_MOVE", "THRASH_MOVE"], names

    eel._current_hp = 65  # <= shriek_amount(70)
    eel.take_damage(1, source=player)
    assert eel._move_state_machine.get_current_move_name() == "STUNNED"
    assert not eel.has_power("shriek"), "Shriek 자가 제거 실패"
    eel.take_turn([player])  # STUNNED 수행
    assert eel._move_state_machine.get_current_move_name() == "TERROR_MOVE"
    eel.take_turn([player])  # TERROR_MOVE 수행 -> 취약 부여
    assert player.get_power_amount("vulnerable") >= 99
    assert eel._move_state_machine.get_current_move_name() == "CRASH_MOVE"
    print("✅ TerrorEel 고정 2교대 + Shriek 임계값 스턴→TERROR_MOVE(취약+99)→CRASH 복귀")


def test_phantasmal_gardener_slot_determines_starting_move():
    """PhantasmalGardener: 배치 슬롯(first/second/third/fourth)이 시작 무브를 결정."""
    expected = {"first": "FLAIL_MOVE", "second": "BITE_MOVE",
                "third": "LASH_MOVE", "fourth": "ENLARGE_MOVE"}
    player = Player(create_character("ironclad"))
    for slot, move in expected.items():
        g = PhantasmalGardener()
        g.slot_name = slot
        combat = CombatState(player, [g], seed=1)
        combat.start()
        assert g._move_state_machine.get_current_move_name() == move, \
            f"슬롯 {slot} 시작 무브 불일치: {g._move_state_machine.get_current_move_name()}"
    print("✅ PhantasmalGardener 슬롯별 시작 무브 (first/second/third/fourth) 확인")


def test_phantasmal_gardeners_elite_encounter_assigns_four_slots():
    """phantasmal_gardeners_elite 인카운터: 4마리에 슬롯 고정 배정."""
    monsters = make_encounter("phantasmal_gardeners_elite", random.Random(1))
    assert [m.slot_name for m in monsters] == ["first", "second", "third", "fourth"]
    print("✅ phantasmal_gardeners_elite 인카운터 4마리 슬롯 배정 확인")


def test_skittish_power_gains_block_once_per_turn_on_card_attack():
    """SkittishPower: 카드 공격에 맞으면 턴당 1회만 블록 획득."""
    player = Player(create_character("ironclad"))
    g = PhantasmalGardener()
    g.slot_name = "second"
    combat = CombatState(player, [g], seed=1)
    combat.start()
    player.energy = player.max_energy
    combat.draw_cards(5)
    strikes = [c for c in combat.hand if c.card_id == "strike"]
    assert len(strikes) >= 2
    combat.play_card(strikes[0], g)
    assert g.block == g.skittish_amount, f"Skittish 블록 획득 실패: {g.block}"
    hp_after_first = g.current_hp
    combat.play_card(strikes[1], g)  # 직전 블록(6)이 두번째 공격(6딜)을 전부 흡수
    assert g.current_hp == hp_after_first, "블록이 두번째 공격을 흡수하지 못함"
    assert g.block == 0, "Skittish 턴당 1회 제한 실패 — 블록이 중복 발동으로 재충전됨"
    print("✅ SkittishPower 카드 공격 시 턴당 1회 블록 획득 확인")


def test_lagavulin_matriarch_starts_asleep_with_plating_block():
    """LagavulinMatriarch: 개전 즉시 Plating(12) 블록 + Asleep(3), SLEEP_MOVE로 시작."""
    combat, player, monsters = make_combat(monster_ids=("lagavulin_matriarch",), seed=1)
    lag = monsters[0]
    assert lag.block == 12, f"개전 Plating 블록 미지급: {lag.block}"
    assert lag.get_power_amount("asleep") == 3
    assert lag._move_state_machine.get_current_move_name() == "SLEEP_MOVE"
    print("✅ LagavulinMatriarch 개전 Plating(12) 즉시 블록 + Asleep(3) + SLEEP_MOVE 시작")


def test_lagavulin_matriarch_wakes_immediately_on_damage_with_stun_penalty():
    """피격으로 깨어나면: Plating 제거 + Asleep 제거 + 1턴 스턴 후 SLASH_MOVE."""
    combat, player, monsters = make_combat(monster_ids=("lagavulin_matriarch",), seed=1)
    lag = monsters[0]
    lag.take_damage(20, source=player)  # 블록12 초과 -> hp_lost>0 -> 즉시 각성
    assert not lag.has_power("asleep")
    assert not lag.has_power("plating")
    assert lag._move_state_machine.get_current_move_name() == "STUNNED"
    lag.take_turn([player])
    assert lag._move_state_machine.get_current_move_name() == "SLASH_MOVE"
    print("✅ LagavulinMatriarch 피격 각성: Plating/Asleep 제거 + 1턴 스턴 패널티 후 SLASH_MOVE")


def test_lagavulin_matriarch_wakes_directly_without_stun_after_natural_decay():
    """자연 감쇠(3턴 무피해 생존)로 깨어나면 스턴 없이 바로 SLASH_MOVE 진입."""
    combat, player, monsters = make_combat(monster_ids=("lagavulin_matriarch",), seed=1)
    lag = monsters[0]
    seen = []
    for _ in range(4):
        seen.append(lag._move_state_machine.get_current_move_name())
        lag.take_turn([player])
        for power in list(lag._powers.values()):
            on_end = getattr(power, "on_turn_end", None)
            if on_end:
                on_end()
    assert seen == ["SLEEP_MOVE", "SLEEP_MOVE", "SLEEP_MOVE", "SLASH_MOVE"], seen
    print("✅ LagavulinMatriarch 자연 감쇠 시 스턴 없이 SLEEP_MOVE→SLEEP_MOVE→SLEEP_MOVE→SLASH_MOVE")


def test_lagavulin_matriarch_awake_fixed_cycle_and_soul_siphon_debuffs():
    """각성 후 SLASH→DISEMBOWEL→SLASH2(+블록)→SOUL_SIPHON(대상 힘-2/민첩-2, 자기 힘+2)→SLASH."""
    combat, player, monsters = make_combat(monster_ids=("lagavulin_matriarch",), seed=1)
    lag = monsters[0]
    lag.take_damage(20, source=player)  # 각성
    lag.take_turn([player])  # STUNNED 소비 -> SLASH_MOVE 진입
    names = []
    for _ in range(4):
        names.append(lag._move_state_machine.get_current_move_name())
        lag.take_turn([player])
    assert names == ["SLASH_MOVE", "DISEMBOWEL_MOVE", "SLASH2_MOVE", "SOUL_SIPHON_MOVE"], names
    assert player.get_power_amount("strength") == -2
    assert player.get_power_amount("dexterity") == -2
    assert lag.get_power_amount("strength") == 2
    assert lag._move_state_machine.get_current_move_name() == "SLASH_MOVE"
    print("✅ LagavulinMatriarch 각성 후 고정 4순환 + SOUL_SIPHON 상호 스탯 조정 확인")


def test_full_combats_batch9_smoke():
    """5종 전부 정책 기반 전투가 예외 없이 완주 (승/패 무관, 크래시 없음)."""
    for enc in ("corpse_slugs_normal", "corpse_slugs_weak", "skulking_colony_elite",
                "terror_eel_elite", "phantasmal_gardeners_elite", "lagavulin_matriarch_boss"):
        for seed in range(5):
            player = Player(create_character("ironclad"))
            monsters = make_encounter(enc, random.Random(seed))
            combat = CombatState(player, monsters, seed=seed)
            result = combat.run(SimplePolicy(), max_turns=60)
            assert isinstance(result.victory, bool)
    print("✅ 6개 인카운터 × 5시드 전투 스모크 테스트 통과 (크래시 없음)")


def main():
    print("🧪 STS2 Phase 6l 통합 테스트\n")
    test_registry_and_encounters()
    test_hp_ranges()
    test_corpse_slug_fixed_cycle_and_starter_index()
    test_corpse_slug_ravenous_on_ally_death()
    test_skulking_colony_fixed_cycle_and_hardened_shell_caps_burst()
    test_hardened_shell_resets_each_turn()
    test_terror_eel_fixed_cycle_and_shriek_trigger()
    test_phantasmal_gardener_slot_determines_starting_move()
    test_phantasmal_gardeners_elite_encounter_assigns_four_slots()
    test_skittish_power_gains_block_once_per_turn_on_card_attack()
    test_lagavulin_matriarch_starts_asleep_with_plating_block()
    test_lagavulin_matriarch_wakes_immediately_on_damage_with_stun_penalty()
    test_lagavulin_matriarch_wakes_directly_without_stun_after_natural_decay()
    test_lagavulin_matriarch_awake_fixed_cycle_and_soul_siphon_debuffs()
    test_full_combats_batch9_smoke()

    print("\n" + "=" * 60)
    print("✅ Phase 6l 전체 테스트 통과!")
    print("=" * 60)
    print("\n📊 Phase 6l 구현 현황:")
    print("  ✅ Act1(Underdocks) 완결: CorpseSlug/SkulkingColony/TerrorEel/")
    print("     PhantasmalGardener/LagavulinMatriarch(보스)")
    print("  ✅ 신규 파워 5종 (Ravenous/Shriek/Asleep/HardenedShell/Skittish)")
    print("     + 기존 Plating에 개전 즉시 블록 지급 버그 수정")
    print("  ✅ 엔진 확장: ConditionalBranchState, force_current_state, ")
    print("     MonsterModel.stun, slot_name, on_any_death 브로드캐스트")
    print("  ✅ 신규 인카운터 6종 등록")


if __name__ == "__main__":
    main()
