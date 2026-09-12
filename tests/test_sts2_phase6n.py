#!/usr/bin/env python3
"""
STS2 Phase 6n 통합 테스트 — 배치11.
몬스터 9종 (SlimedBerserker/SlitheringStrangler/Exoskeleton/HunterKiller/
MechaKnight/BygoneEffigy/Inklet/ScrollOfBiting/Vantom) + 신규 파워 6종
(Constrict/HardToKill/Tender/Slow/Slippery/PaperCuts) + 엔진 확장
(Creature.lose_max_hp, on_landed_attack의 target 인자, 몬스터 파워에도
카드 플레이를 통지하는 CombatState.notify_card_played).
"""
import random

import sts2_sim  # noqa: F401 — CARD_REGISTRY 등록
from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import ENCOUNTERS, make_encounter
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import MONSTER_REGISTRY, create_monster
from sts2_sim.entities.monsters_batch11 import (
    SlimedBerserker, SlitheringStrangler, Exoskeleton, HunterKiller,
    MechaKnight, BygoneEffigy, Inklet, ScrollOfBiting, Vantom,
)
from sts2_sim.models.sts2_card import create_card
from sts2_sim.models.sts2_power import (
    POWER_REGISTRY, ConstrictPower, HardToKillPower, TenderPower, SlowPower,
    SlipperyPower, PaperCutsPower, Doom, Intangible, Strength, Vulnerable,
)

NEW_MONSTERS = ("slimed_berserker", "slithering_strangler", "exoskeleton",
                "hunter_killer", "mecha_knight", "bygone_effigy", "inklet",
                "scroll_of_biting", "vantom")
NEW_ENCOUNTERS = ("slimed_berserker_normal", "slithering_strangler_normal",
                  "exoskeletons_normal", "exoskeletons_weak", "hunter_killer_normal",
                  "mecha_knight_elite", "bygone_effigy_elite", "inklets_normal",
                  "scrolls_of_biting_normal", "scrolls_of_biting_weak",
                  "vantom_boss")


def make_combat(monsters, seed=42, player_hp=None):
    player = Player(create_character("ironclad"))
    if player_hp is not None:
        player._max_hp = player._current_hp = player_hp
    combat = CombatState(player, monsters, seed=seed)
    combat.start()
    player.energy = player.max_energy
    return combat, player


def test_registry_and_encounters():
    """몬스터 8종 + 파워 6종 + 인카운터 10종 등록."""
    for mid in NEW_MONSTERS:
        assert mid in MONSTER_REGISTRY, f"미등록 몬스터: {mid}"
    for pid, cls in (("constrict", ConstrictPower), ("hard_to_kill", HardToKillPower),
                     ("tender", TenderPower), ("slow", SlowPower),
                     ("slippery", SlipperyPower), ("paper_cuts", PaperCutsPower)):
        assert POWER_REGISTRY[pid] is cls, f"미등록/불일치 파워: {pid}"
    for eid in NEW_ENCOUNTERS:
        assert eid in ENCOUNTERS, f"미등록 인카운터: {eid}"
    print("✅ 몬스터 9종 + 파워 6종 + 인카운터 11종 등록 확인")


def test_package_import_alone_populates_monster_registry():
    """`import sts2_sim`만으로 몬스터 배치가 MONSTER_REGISTRY에 등록되어야 한다.

    이 스위트의 다른 테스트는 core.encounters를 임포트하므로 배치 모듈이
    간접 로드되어 문제를 가리지만, encounters를 거치지 않는 소비자
    (create_monster 직접 호출)는 조용히 None을 받는다 — 실제로 배치 모듈이
    어디서도 임포트되지 않아 기본 17종만 등록돼 있던 버그의 재발 방지."""
    import subprocess
    import sys

    code = (
        "import sts2_sim;"
        "from sts2_sim.entities.sts2_monster import MONSTER_REGISTRY, create_monster;"
        "print(len(MONSTER_REGISTRY), type(create_monster('exoskeleton')).__name__)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, f"임포트 실패: {out.stderr}"
    count, name = out.stdout.split()
    assert int(count) >= 70, f"패키지 임포트만으로 등록된 몬스터가 부족: {count}"
    assert name == "Exoskeleton", f"create_monster('exoskeleton') 실패: {name}"
    print("✅ import sts2_sim 단독으로 몬스터 배치 등록 확인")


def test_hp_ranges():
    """디컴파일 MinInitialHp/MaxInitialHp(Ascension 미적용) 정확히 일치."""
    expected = {
        "slimed_berserker": (261, 261),
        "slithering_strangler": (53, 55),
        "exoskeleton": (24, 28),
        "hunter_killer": (121, 121),
        "mecha_knight": (300, 300),
        "bygone_effigy": (127, 127),
        "inklet": (11, 17),
        "scroll_of_biting": (30, 37),
        "vantom": (173, 173),
    }
    for mid, (lo, hi) in expected.items():
        m = create_monster(mid)
        assert m.min_initial_hp == lo and m.max_initial_hp == hi, \
            f"{mid} HP 범위 불일치: {m.min_initial_hp}~{m.max_initial_hp} (기대 {lo}~{hi})"
    print("✅ HP 범위 9종 전부 디컴파일 기준값과 일치")


def test_slimed_berserker_fixed_cycle():
    """고정 4순환 + 각 무브 효과 (Slimed 10장 / 4딜×4 / 약화3+힘3 / 30딜)."""
    berserker = SlimedBerserker()
    combat, player = make_combat([berserker], seed=1, player_hp=500)
    sm = berserker._move_state_machine

    assert sm.get_current_move_name() == "VOMIT_ICHOR_MOVE"
    berserker.take_turn([player])
    slimed = [c for c in combat.discard_pile if c.card_id == "slimed"]
    assert len(slimed) == 10, f"Slimed 10장이 아님: {len(slimed)}"
    assert sm.get_current_move_name() == "FURIOUS_PUMMELING_MOVE"

    hp = player.current_hp
    berserker.take_turn([player])
    assert player.current_hp == hp - 4 * 4, "FURIOUS_PUMMELING 4딜×4회 불일치"
    assert sm.get_current_move_name() == "LEECHING_HUG_MOVE"

    hp = player.current_hp
    berserker.take_turn([player])
    assert player.current_hp == hp, "LEECHING_HUG는 피해를 주지 않아야 함"
    assert player.get_power_amount("weak") == 3
    assert berserker.get_power_amount("strength") == 3
    assert sm.get_current_move_name() == "SMOTHER_MOVE"

    hp = player.current_hp
    berserker.take_turn([player])
    # 힘 +3 반영 → 30 + 3 = 33
    assert player.current_hp == hp - 33, "SMOTHER 30딜 + 힘3 불일치"
    assert sm.get_current_move_name() == "VOMIT_ICHOR_MOVE", "4순환 복귀 실패"
    print("✅ SlimedBerserker 고정 4순환 + Slimed10/4x4/약화3+힘3/30딜 확인")


def test_constrict_self_damage_and_applier_death_removal():
    """Constrict: 보유자 턴 종료마다 자해, 부여한 적이 죽으면 제거."""
    strangler = SlitheringStrangler()
    combat, player = make_combat([strangler], seed=2, player_hp=200)
    sm = strangler._move_state_machine

    assert sm.get_current_move_name() == "CONSTRICT"
    strangler.take_turn([player])
    assert player.get_power_amount("constrict") == 3
    assert player._powers["constrict"].applier is strangler

    # 플레이어 턴 종료 시 3 자해 (블록으로 막힌다 — Unblockable 아님)
    hp = player.current_hp
    player._powers["constrict"].on_turn_end()
    assert player.current_hp == hp - 3, "Constrict 자해 3 불일치"

    player.gain_block(10)
    hp = player.current_hp
    player._powers["constrict"].on_turn_end()
    assert player.current_hp == hp, "Constrict 자해가 블록을 무시함"
    assert player.block == 7

    # 부여한 적이 죽으면 제거
    strangler.lose_hp(strangler.current_hp)
    combat.reap_deaths()
    assert not player.has_power("constrict"), "applier 사망 후에도 Constrict가 남음"
    print("✅ Constrict 턴 종료 자해(블록 적용) + applier 사망 시 제거 확인")


def test_slithering_strangler_branch_returns_to_constrict():
    """CONSTRICT → rand{THWACK, LASH} → 다시 CONSTRICT (양 분기 모두 복귀)."""
    for seed in range(6):
        strangler = SlitheringStrangler()
        combat, player = make_combat([strangler], seed=seed, player_hp=500)
        sm = strangler._move_state_machine
        strangler.take_turn([player])  # CONSTRICT
        branch = sm.get_current_move_name()
        assert branch in ("THWACK", "LASH"), f"예상 밖 분기: {branch}"
        hp, block = player.current_hp, strangler.block
        strangler.take_turn([player])
        if branch == "THWACK":
            assert player.current_hp == hp - 7
            assert strangler.block == block + 5, "THWACK 블록 5 불일치"
        else:
            assert player.current_hp == hp - 12
        assert sm.get_current_move_name() == "CONSTRICT", "분기 후 CONSTRICT 복귀 실패"
    print("✅ SlitheringStrangler CONSTRICT→{THWACK 7딜+블록5 / LASH 12딜}→CONSTRICT 확인")


def test_hard_to_kill_caps_damage_after_multipliers():
    """HardToKill(9): 취약 배율이 전부 적용된 뒤 Cap 단계에서 9로 제한."""
    roach = Exoskeleton()
    roach.slot_name = "first"
    combat, player = make_combat([roach], seed=3)
    assert roach.get_power_amount("hard_to_kill") == 9

    result = roach.take_damage(100, source=player)
    assert result["damage"] == 9, f"Cap 미적용: {result['damage']}"

    roach.apply_power(Vulnerable(2), applier=player)
    result = roach.take_damage(100, source=player)
    assert result["damage"] == 9, "취약 배율이 Cap보다 뒤에 적용됨"

    result = roach.take_damage(5, source=player)
    assert result["damage"] == int(5 * 1.5), "Cap 미만 피해가 잘못 제한됨"
    print("✅ HardToKill 9: 배율 적용 후 Cap 단계 제한 + Cap 미만은 그대로 확인")


def test_exoskeleton_slot_determines_starting_move():
    """슬롯(first/second/third/fourth)이 시작 무브를 결정."""
    expected = {"first": "SKITTER_MOVE", "second": "MANDIBLES_MOVE",
                "third": "ENRAGE_MOVE"}
    for slot, move in expected.items():
        roach = Exoskeleton()
        roach.slot_name = slot
        combat, player = make_combat([roach], seed=4)
        assert roach._move_state_machine.get_current_move_name() == move, \
            f"{slot} 시작 무브 불일치"
    # fourth는 RAND로 시작 — 두 분기 중 하나로 해석된다
    roach = Exoskeleton()
    roach.slot_name = "fourth"
    combat, player = make_combat([roach], seed=4)
    assert roach._move_state_machine.get_current_move_name() in (
        "SKITTER_MOVE", "MANDIBLES_MOVE")

    # MANDIBLES → ENRAGE → RAND 고정 전환
    roach = Exoskeleton()
    roach.slot_name = "second"
    combat, player = make_combat([roach], seed=5, player_hp=200)
    hp = player.current_hp
    roach.take_turn([player])
    assert player.current_hp == hp - 8, "MANDIBLES 8딜 불일치"
    assert roach._move_state_machine.get_current_move_name() == "ENRAGE_MOVE"
    roach.take_turn([player])
    assert roach.get_power_amount("strength") == 2, "ENRAGE 힘 +2 불일치"
    assert roach._move_state_machine.get_current_move_name() in (
        "SKITTER_MOVE", "MANDIBLES_MOVE")
    print("✅ Exoskeleton 슬롯별 시작 무브 + MANDIBLES→ENRAGE→RAND 확인")


def test_exoskeletons_encounter_assigns_slots():
    """exoskeletons_normal(4)/weak(3) 슬롯 배정 — Weak는 fourth가 없다."""
    normal = make_encounter("exoskeletons_normal", random.Random(1))
    assert [m.slot_name for m in normal] == ["first", "second", "third", "fourth"]
    weak = make_encounter("exoskeletons_weak", random.Random(1))
    assert [m.slot_name for m in weak] == ["first", "second", "third"]
    print("✅ exoskeletons_normal 4슬롯 / weak 3슬롯 배정 확인")


def test_tender_reduces_str_dex_per_card_and_restores_at_turn_end():
    """Tender: 카드 플레이마다 힘·민첩 -1, 자신의 턴 종료 시 전량 복구."""
    killer = HunterKiller()
    combat, player = make_combat([killer], seed=6, player_hp=300)
    assert killer._move_state_machine.get_current_move_name() == "TENDERIZING_GOOP_MOVE"
    killer.take_turn([player])
    assert player.has_power("tender")

    player.apply_power(Strength(5))
    combat.hand = [create_card("strike"), create_card("defend")]
    player.energy = 5
    combat.play_card(combat.hand[0], killer)
    assert player.get_power_amount("strength") == 4, "카드 1장 후 힘 -1 미적용"
    assert player.get_power_amount("dexterity") == -1
    combat.play_card(combat.hand[0], killer)
    assert player.get_power_amount("strength") == 3, "카드 2장 후 힘 -2 미적용"
    assert player.get_power_amount("dexterity") == -2

    player._powers["tender"].on_turn_end()
    assert player.get_power_amount("strength") == 5, "턴 종료 힘 복구 실패"
    assert player.get_power_amount("dexterity") == 0, "턴 종료 민첩 복구 실패"
    assert player._powers["tender"].cards_played_this_turn == 0
    print("✅ Tender 카드당 힘·민첩 -1 + 자신 턴 종료 시 전량 복구 확인")


def test_hunter_killer_puncture_max_repeats():
    """RAND의 PUNCTURE는 maxRepeats 2 — 3연속으로는 나오지 않는다."""
    killer = HunterKiller()
    combat, player = make_combat([killer], seed=7, player_hp=5000)
    sm = killer._move_state_machine
    killer.take_turn([player])  # GOOP → RAND
    seen = []
    for _ in range(40):
        seen.append(sm.get_current_move_name())
        killer.take_turn([player])
    assert set(seen) <= {"BITE_MOVE", "PUNCTURE_MOVE"}
    for i in range(len(seen) - 2):
        assert seen[i:i + 3] != ["PUNCTURE_MOVE"] * 3, \
            f"PUNCTURE 3연속 발생 (maxRepeats 2 위반): {seen}"
        assert seen[i:i + 2] != ["BITE_MOVE"] * 2, \
            f"BITE 연속 발생 (CannotRepeat 위반): {seen}"
    assert "BITE_MOVE" in seen and "PUNCTURE_MOVE" in seen
    print("✅ HunterKiller RAND: PUNCTURE maxRepeats 2 + BITE CannotRepeat 확인")


def test_mecha_knight_cycle_artifact_and_burn_to_hand():
    """개전 Artifact 3, CHARGE→FLAMETHROWER(화상 4장 손패)→WINDUP→CLEAVE→FLAMETHROWER."""
    knight = MechaKnight()
    combat, player = make_combat([knight], seed=8, player_hp=500)
    sm = knight._move_state_machine
    assert knight.get_power_amount("artifact") == 3
    knight.apply_power(Vulnerable(2), applier=player)
    assert not knight.has_power("vulnerable"), "Artifact가 디버프를 막지 못함"
    assert knight.get_power_amount("artifact") == 2

    assert sm.get_current_move_name() == "CHARGE_MOVE"
    hp = player.current_hp
    knight.take_turn([player])
    assert player.current_hp == hp - 25, "CHARGE 25딜 불일치"
    assert sm.get_current_move_name() == "FLAMETHROWER_MOVE"

    combat.hand = []
    knight.take_turn([player])
    burns = [c for c in combat.hand if c.card_id == "burn"]
    assert len(burns) == 4, f"화상 4장이 손패에 없음: {len(burns)}"
    assert not [c for c in combat.discard_pile if c.card_id == "burn"], \
        "화상이 버림 더미로 감 (원본은 PileType.Hand)"
    assert sm.get_current_move_name() == "WINDUP_MOVE"

    knight.take_turn([player])
    assert knight.block == 15, "WINDUP 블록 15 불일치"
    assert knight.get_power_amount("strength") == 5
    assert sm.get_current_move_name() == "HEAVY_CLEAVE_MOVE"

    hp = player.current_hp
    knight.take_turn([player])
    assert player.current_hp == hp - (35 + 5), "HEAVY_CLEAVE 35딜 + 힘5 불일치"
    assert sm.get_current_move_name() == "FLAMETHROWER_MOVE", \
        "CLEAVE 이후 FLAMETHROWER로 복귀하지 않음 (CHARGE는 1회만)"
    print("✅ MechaKnight Artifact3 + CHARGE→화상4(손패)→WINDUP→CLEAVE→FLAMETHROWER 확인")


def test_flamethrower_hand_overflow_goes_to_discard():
    """손패가 가득 차면 화상 초과분이 사라지지 않고 버림 더미로 간다
    (원본 CardPileCmd.Add의 isFullHandAdd → targetPile = Discard)."""
    knight = MechaKnight()
    combat, player = make_combat([knight], seed=22, player_hp=500)
    sm = knight._move_state_machine
    knight.take_turn([player])  # CHARGE
    assert sm.get_current_move_name() == "FLAMETHROWER_MOVE"

    combat.hand = [create_card("strike") for _ in range(8)]
    combat.discard_pile = []
    knight.take_turn([player])
    in_hand = [c for c in combat.hand if c.card_id == "burn"]
    in_discard = [c for c in combat.discard_pile if c.card_id == "burn"]
    assert len(combat.hand) == 10, f"손패 상한 10 초과/미달: {len(combat.hand)}"
    assert len(in_hand) == 2, f"손패에 들어간 화상이 2장이 아님: {len(in_hand)}"
    assert len(in_discard) == 2, f"초과분 2장이 버림 더미로 가지 않음: {len(in_discard)}"
    print("✅ MechaKnight 화상: 손패 상한 초과분이 버림 더미로 이동 확인")


def test_slow_scales_incoming_damage_with_cards_played():
    """Slow: 플레이어가 이번 턴 낸 카드 수만큼 받는 파워드 피해 +10%/장,
    보유자 턴 시작 시 초기화. 몬스터 파워도 카드 플레이를 통지받아야 한다."""
    effigy = BygoneEffigy()
    combat, player = make_combat([effigy], seed=9)
    slow = effigy._powers["slow"]
    assert slow.slow_amount == 0

    combat.hand = [create_card("defend") for _ in range(3)]
    player.energy = 5
    combat.play_card(combat.hand[0])
    assert slow.slow_amount == 1, "몬스터 파워가 카드 플레이를 통지받지 못함"
    combat.play_card(combat.hand[0])
    assert slow.slow_amount == 2

    # 100 피해 → ×1.2 = 120
    result = effigy.take_damage(100, source=player)
    assert result["damage"] == 120, f"Slow 배율 불일치: {result['damage']}"
    # Unpowered 피해는 IsPoweredAttack 게이트에 걸려 배율 미적용
    result = effigy.take_damage(100, source=player, powered=False)
    assert result["damage"] == 100, "Unpowered 피해에 Slow 배율이 적용됨"

    slow.on_turn_start()
    assert slow.slow_amount == 0
    result = effigy.take_damage(100, source=player)
    assert result["damage"] == 100, "턴 시작 후에도 Slow가 남음"
    print("✅ Slow 카드 1장당 +10%(파워드 한정) + 보유자 턴 시작 초기화 확인")


def test_bygone_effigy_sleep_wake_slash():
    """SLEEP(무행동) → WAKE(힘 +10) → SLASHES(13딜) → SLASHES 반복."""
    effigy = BygoneEffigy()
    combat, player = make_combat([effigy], seed=10, player_hp=500)
    sm = effigy._move_state_machine

    assert sm.get_current_move_name() == "SLEEP_MOVE"
    hp = player.current_hp
    effigy.take_turn([player])
    assert player.current_hp == hp, "SLEEP이 피해를 줌"
    assert sm.get_current_move_name() == "WAKE_MOVE"

    effigy.take_turn([player])
    assert effigy.get_power_amount("strength") == 10, "WAKE 힘 +10 불일치"
    assert sm.get_current_move_name() == "SLASHES_MOVE"

    for _ in range(3):
        hp = player.current_hp
        effigy.take_turn([player])
        assert player.current_hp == hp - (13 + 10), "SLASHES 13딜 + 힘10 불일치"
        assert sm.get_current_move_name() == "SLASHES_MOVE", "SLASHES 자기 반복 실패"
    print("✅ BygoneEffigy SLEEP→WAKE(힘10)→SLASHES(13딜) 반복 확인")


def test_slippery_caps_hp_loss_and_decrements():
    """Slippery: HP 손실을 1로 제한하고, 관통 피해마다 스택 1 감소."""
    inklet = Inklet()
    combat, player = make_combat([inklet], seed=11)
    assert inklet.get_power_amount("slippery") == 1
    hp = inklet.current_hp

    result = inklet.take_damage(100, source=player)
    assert result["hp_lost"] == 1, f"HP 손실이 1로 제한되지 않음: {result['hp_lost']}"
    assert inklet.current_hp == hp - 1
    assert not inklet.has_power("slippery"), "관통 피해 후 스택이 감소하지 않음"

    result = inklet.take_damage(100, source=player)
    assert result["hp_lost"] == 100 or inklet.is_dead, "스택 소진 후에도 제한이 남음"

    # 블록으로 전부 막히면 스택이 줄지 않는다 (UnblockedDamage >= 1 게이트)
    inklet2 = Inklet()
    combat2, player2 = make_combat([inklet2], seed=12)
    inklet2.gain_block(50)
    inklet2.take_damage(10, source=player2)
    assert inklet2.get_power_amount("slippery") == 1, "막힌 피해로 스택이 감소함"
    print("✅ Slippery HP 손실 1 제한 + 관통 시에만 스택 감소 확인")


def test_inklet_middle_starts_with_whirlwind():
    """가운데 잉클렛만 WHIRLWIND로 시작, 나머지는 JAB. WHIRLWIND/GAZE→JAB 복귀."""
    monsters = make_encounter("inklets_normal", random.Random(1))
    assert [m.middle_inklet for m in monsters] == [False, True, False]
    combat, player = make_combat(monsters, seed=13, player_hp=500)
    assert monsters[0]._move_state_machine.get_current_move_name() == "JAB_MOVE"
    assert monsters[1]._move_state_machine.get_current_move_name() == "WHIRLWIND_MOVE"

    hp = player.current_hp
    monsters[1].take_turn([player])
    assert player.current_hp == hp - 2 * 3, "WHIRLWIND 2딜×3 불일치"
    assert monsters[1]._move_state_machine.get_current_move_name() == "JAB_MOVE"

    inklet = monsters[0]
    hp = player.current_hp
    inklet.take_turn([player])  # JAB
    assert player.current_hp == hp - 3
    branch = inklet._move_state_machine.get_current_move_name()
    assert branch in ("PIERCING_GAZE_MOVE", "WHIRLWIND_MOVE")
    inklet.take_turn([player])
    assert inklet._move_state_machine.get_current_move_name() == "JAB_MOVE", \
        "분기 무브 후 JAB 복귀 실패"
    print("✅ Inklet 가운데 WHIRLWIND 시작 + 분기 후 JAB 복귀 확인")


def test_paper_cuts_reduces_player_max_hp_on_unblocked_hit():
    """PaperCuts(2): 플레이어 블록을 뚫은 히트마다 최대 HP -2. 다단히트는 히트 수만큼."""
    scroll = ScrollOfBiting(starter_move_idx=0)
    combat, player = make_combat([scroll], seed=14, player_hp=200)
    assert scroll.get_power_amount("paper_cuts") == 2

    max_hp = player.max_hp
    scroll.take_turn([player])  # CHOMP 14딜 (단일 히트)
    assert player.max_hp == max_hp - 2, "CHOMP 적중 후 최대 HP -2 미적용"

    # CHEW(5딜×2)는 히트 2회 → -4 (원본 AfterDamageGiven은 피해 인스턴스 단위)
    scroll2 = ScrollOfBiting(starter_move_idx=1)
    combat2, player2 = make_combat([scroll2], seed=15, player_hp=200)
    max_hp = player2.max_hp
    scroll2.take_turn([player2])
    assert player2.max_hp == max_hp - 4, "CHEW 2히트에 대해 최대 HP -4 미적용"

    # 블록으로 전부 막히면 발동하지 않는다
    scroll3 = ScrollOfBiting(starter_move_idx=0)
    combat3, player3 = make_combat([scroll3], seed=16, player_hp=200)
    player3.gain_block(50)
    max_hp = player3.max_hp
    scroll3.take_turn([player3])
    assert player3.max_hp == max_hp, "막힌 공격으로 최대 HP가 깎임"
    print("✅ PaperCuts 관통 히트당 최대 HP -2 (다단히트는 히트 수만큼) 확인")


def test_lose_max_hp_routes_overflow_through_damage():
    """lose_max_hp: 새 최대 HP가 현재 HP보다 낮으면 초과분을 피해로 처리하고,
    최대 HP는 최소 1로 유지된다 (원본 CreatureCmd.LoseMaxHp)."""
    combat, player = make_combat([create_monster("big_dummy")], seed=17, player_hp=80)
    player._current_hp = 80
    player.lose_max_hp(10)
    assert player.max_hp == 70 and player.current_hp == 70, "초과분 피해 처리 실패"
    assert player.hp_lost_this_turn == 10, "HP 손실 집계 누락"

    player._current_hp = 30
    player.lose_max_hp(10)
    assert player.max_hp == 60 and player.current_hp == 30, \
        "현재 HP보다 높은 최대 HP 감소가 현재 HP를 건드림"

    # 최대 HP 전량 손실 → 사망하고 최대 HP는 1로 고정
    player.lose_max_hp(999)
    assert player.max_hp == 1
    assert player.is_dead, "최대 HP 전량 손실에도 생존함"
    print("✅ lose_max_hp 초과분 피해 경유 + 최소 1 고정 + 사망 처리 확인")


def test_scroll_starter_moves_and_chew_max_repeats():
    """StarterMoveIdx % 3 → CHOMP/CHEW/MORE_TEETH, rand의 CHEW는 maxRepeats 2."""
    expected = {0: "CHOMP", 1: "CHEW", 2: "MORE_TEETH", 3: "CHOMP"}
    for idx, move in expected.items():
        scroll = ScrollOfBiting(starter_move_idx=idx)
        combat, player = make_combat([scroll], seed=18, player_hp=500)
        assert scroll._move_state_machine.get_current_move_name() == move, \
            f"starter_move_idx={idx} 시작 무브 불일치"

    # 고정 전환: CHOMP → MORE_TEETH → CHEW → rand
    scroll = ScrollOfBiting(starter_move_idx=0)
    combat, player = make_combat([scroll], seed=19, player_hp=5000)
    sm = scroll._move_state_machine
    scroll.take_turn([player])
    assert sm.get_current_move_name() == "MORE_TEETH"
    scroll.take_turn([player])
    assert scroll.get_power_amount("strength") == 2
    assert sm.get_current_move_name() == "CHEW"
    scroll.take_turn([player])
    seen = []
    for _ in range(40):
        seen.append(sm.get_current_move_name())
        scroll.take_turn([player])
    assert set(seen) <= {"CHOMP", "CHEW", "MORE_TEETH"}
    chew_runs = 0
    for move in seen:
        chew_runs = chew_runs + 1 if move == "CHEW" else 0
        assert chew_runs <= 2, f"CHEW 3연속 발생 (maxRepeats 2 위반): {seen}"
    print("✅ ScrollOfBiting 시작 무브 3종 + CHOMP→MORE_TEETH→CHEW + CHEW maxRepeats 2 확인")


def test_scrolls_encounter_starter_indices():
    """scrolls_of_biting_normal: 앞 3마리는 서로 다른 인덱스, 4번째는 2 고정."""
    for seed in range(5):
        normal = make_encounter("scrolls_of_biting_normal", random.Random(seed))
        idxs = [m.starter_move_idx for m in normal]
        assert len(set(idxs[:3])) == 3, f"앞 3마리 시작 인덱스 중복: {idxs}"
        assert idxs[3] == 2, f"4번째 스크롤 인덱스가 2 고정이 아님: {idxs}"
        weak = make_encounter("scrolls_of_biting_weak", random.Random(seed))
        assert len(set(m.starter_move_idx for m in weak)) == 3
    print("✅ scrolls_of_biting 시작 인덱스 배정 (앞 3종 회전 + 4번째 2 고정) 확인")


def test_slithering_strangler_encounter_composition():
    """보조 적 3종 구성 전부 등장 + Strangler는 항상 마지막."""
    kinds = set()
    for seed in range(30):
        monsters = make_encounter("slithering_strangler_normal", random.Random(seed))
        assert isinstance(monsters[-1], SlitheringStrangler), "Strangler가 마지막이 아님"
        kinds.add(len(monsters))
    assert kinds == {2, 3}, f"구성 크기가 2(잭스프루트/중형)와 3(소형2)이 아님: {kinds}"
    print("✅ slithering_strangler_normal 보조 적 구성 + Strangler 마지막 배치 확인")


def test_vantom_boss_cycle_slippery_and_doom_immunity():
    """Vantom: 개전 Slippery 8, 고정 4순환(7딜 / 6딜×2 / 26딜+상처3 / 힘+2),
    Doom 즉사 면역."""
    vantom = Vantom()
    combat, player = make_combat([vantom], seed=20, player_hp=500)
    sm = vantom._move_state_machine
    assert vantom.get_power_amount("slippery") == 8

    assert sm.get_current_move_name() == "INK_BLOT_MOVE"
    hp = player.current_hp
    vantom.take_turn([player])
    assert player.current_hp == hp - 7, "INK_BLOT 7딜 불일치"
    assert sm.get_current_move_name() == "INKY_LANCE_MOVE"

    hp = player.current_hp
    vantom.take_turn([player])
    assert player.current_hp == hp - 6 * 2, "INKY_LANCE 6딜×2 불일치"
    assert sm.get_current_move_name() == "DISMEMBER_MOVE"

    hp = player.current_hp
    vantom.take_turn([player])
    assert player.current_hp == hp - 26, "DISMEMBER 26딜 불일치"
    wounds = [c for c in combat.discard_pile if c.card_id == "wound"]
    assert len(wounds) == 3, f"상처 3장이 버림 더미에 없음: {len(wounds)}"
    assert sm.get_current_move_name() == "PREPARE_MOVE"

    vantom.take_turn([player])
    assert vantom.get_power_amount("strength") == 2, "PREPARE 힘 +2 불일치"
    assert sm.get_current_move_name() == "INK_BLOT_MOVE", "4순환 복귀 실패"

    # Doom 즉사 면역 (원본 ShouldDisappearFromDoom => false)
    assert vantom.should_disappear_from_doom is False
    vantom.apply_power(Doom(999))
    combat._trigger_doom()
    assert vantom.is_alive, "Doom이 Vantom을 제거함"
    print("✅ Vantom 보스 Slippery8 + 4순환(7/6x2/26+상처3/힘2) + Doom 면역 확인")


def test_lose_max_hp_with_damage_cap_keeps_current_hp_within_max():
    """Intangible 등 Cap이 초과분 피해를 1로 막아도 현재 HP가 새 최대 HP를
    넘지 않아야 한다 (원본 SetMaxHpInternal의 CurrentHp = Min(CurrentHp, MaxHp))."""
    combat, player = make_combat([create_monster("big_dummy")], seed=21, player_hp=80)
    player._current_hp = 80
    player.apply_power(Intangible(5))
    player.lose_max_hp(20)
    assert player.max_hp == 60, f"최대 HP 60이 아님: {player.max_hp}"
    assert player.current_hp <= player.max_hp, \
        f"Cap이 개입해 현재 HP({player.current_hp})가 최대 HP({player.max_hp})를 초과함"
    print("✅ lose_max_hp: 피해 Cap 개입 시에도 현재 HP ≤ 최대 HP 유지 확인")


def test_seeded_smoke():
    """신규 인카운터 11종 × 3시드 전투 스모크."""
    for eid in NEW_ENCOUNTERS:
        for seed in range(3):
            player = Player(create_character("ironclad"))
            monsters = make_encounter(eid, random.Random(seed))
            combat = CombatState(player, monsters, seed=seed)
            result = combat.run(SimplePolicy(), max_turns=80)
            assert isinstance(result.victory, bool)
    print("✅ 신규 인카운터 11종 × 3시드 전투 스모크 통과")


def main():
    print("🧪 STS2 Phase 6n 통합 테스트\n")
    test_registry_and_encounters()
    test_package_import_alone_populates_monster_registry()
    test_hp_ranges()
    test_slimed_berserker_fixed_cycle()
    test_constrict_self_damage_and_applier_death_removal()
    test_slithering_strangler_branch_returns_to_constrict()
    test_hard_to_kill_caps_damage_after_multipliers()
    test_exoskeleton_slot_determines_starting_move()
    test_exoskeletons_encounter_assigns_slots()
    test_tender_reduces_str_dex_per_card_and_restores_at_turn_end()
    test_hunter_killer_puncture_max_repeats()
    test_mecha_knight_cycle_artifact_and_burn_to_hand()
    test_flamethrower_hand_overflow_goes_to_discard()
    test_slow_scales_incoming_damage_with_cards_played()
    test_bygone_effigy_sleep_wake_slash()
    test_slippery_caps_hp_loss_and_decrements()
    test_inklet_middle_starts_with_whirlwind()
    test_paper_cuts_reduces_player_max_hp_on_unblocked_hit()
    test_lose_max_hp_routes_overflow_through_damage()
    test_scroll_starter_moves_and_chew_max_repeats()
    test_scrolls_encounter_starter_indices()
    test_slithering_strangler_encounter_composition()
    test_vantom_boss_cycle_slippery_and_doom_immunity()
    test_lose_max_hp_with_damage_cap_keeps_current_hp_within_max()
    test_seeded_smoke()

    print("\n" + "=" * 60)
    print("✅ Phase 6n 전체 테스트 통과!")
    print("=" * 60)
    print("\n📊 Phase 6n 구현 현황:")
    print("  ✅ 몬스터 9종 (SlimedBerserker/SlitheringStrangler/Exoskeleton/")
    print("     HunterKiller/MechaKnight/BygoneEffigy/Inklet/ScrollOfBiting/")
    print("     Vantom(보스))")
    print("  ✅ 신규 파워 6종 (Constrict/HardToKill/Tender/Slow/Slippery/PaperCuts)")
    print("  ✅ 엔진 확장: Creature.lose_max_hp, on_landed_attack(target),")
    print("     몬스터 파워에도 카드 플레이 통지 (notify_card_played)")
    print("  ✅ 신규 인카운터 11종 등록")


if __name__ == "__main__":
    main()
