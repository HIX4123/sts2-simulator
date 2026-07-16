#!/usr/bin/env python3
"""
STS2 Phase 6a 통합 테스트.
신규 몬스터 17종 (디컴파일 수치) + Plating/Tangled 배선 + 실제 인카운터 구성.
"""
import random

from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.policy import GreedyPolicy
from sts2_sim.core.encounters import make_encounter, ENCOUNTERS
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import create_monster, RandomBranchState
from sts2_sim.entities.monsters_extra import (
    EXTRA_MONSTERS, LeafSlimeS, LeafSlimeM, CalcifiedCultist,
    SpectralKnight, MagiKnight, CrossbowRubyRaider, TrackerRubyRaider,
    SewerClam, Mawler, GlobeHead, VineShambler,
)
from sts2_sim.models.sts2_card import Strike
from sts2_sim.models.sts2_power import Plating, TangledPower


def make_player(char_id="ironclad"):
    return Player(create_character(char_id))


def test_new_monster_stats():
    """디컴파일 수치 스팟 체크 (Ascension 미적용 기본값)."""
    print("=== 신규 몬스터 수치 (디컴파일 대조) ===\n")

    expected = {
        "leaf_slime_s": (11, 15), "leaf_slime_m": (32, 35),
        "calcified_cultist": (38, 41), "spectral_knight": (93, 93),
        "magi_knight": (82, 82), "assassin_ruby_raider": (18, 23),
        "brute_ruby_raider": (30, 33), "tracker_ruby_raider": (21, 25),
        "crossbow_ruby_raider": (18, 21), "sewer_clam": (56, 56),
        "snapping_jaxfruit": (31, 33), "sneaky_gremlin": (10, 14),
        "noisebot": (18, 23), "living_shield": (55, 55),
        "mawler": (72, 72), "globe_head": (148, 148), "vine_shambler": (61, 61),
    }
    for mid, (lo, hi) in expected.items():
        m = create_monster(mid)
        assert m is not None, f"레지스트리 누락: {mid}"
        assert m.min_initial_hp == lo and m.max_initial_hp == hi, \
            f"{mid} HP 불일치: {m.min_initial_hp}-{m.max_initial_hp} != {lo}-{hi}"
    print(f"✅ 17종 전부 레지스트리 등록 + HP 일치")

    # 이동 수치 스팟 체크
    assert CalcifiedCultist().dark_strike_damage == 9
    assert SpectralKnight().soul_slash_damage == 15
    assert MagiKnight().bomb_damage == 35
    assert Mawler().rip_and_tear_damage == 14
    assert GlobeHead().galvanic_burst_damage == 16
    print(f"✅ 데미지 수치 스팟 체크 통과")


def test_plating_power():
    """Plating: 턴 종료 블록 획득, 소유자 턴 시작마다 스택 감소(피해 무관, 라운드1 제외)
    (디컴파일 PlatingPower.AfterSideTurnStart — TurnNumber/RoundNumber != 1)."""
    print("\n=== Plating 파워 ===\n")

    class _FakeCombat:
        turn = 1

    clam = SewerClam()
    clam.setup_for_combat(None)
    assert clam.get_power_amount("plating") == 8, "개전 Plating 8 미적용"
    fake_combat = _FakeCombat()
    clam.combat_state = fake_combat

    plating = clam._powers["plating"]
    plating.on_turn_end()
    assert clam.block == 8, f"턴 종료 블록 실패: {clam.block}"

    # 라운드 1(개전 시 이미 보유)은 감소 제외
    plating.on_turn_start()
    assert clam.get_power_amount("plating") == 8, "라운드1 감소 제외 실패"

    # 피해는 스택에 영향 없음 (원본은 피격 기반 감소가 아님)
    clam.take_damage(10, source=None)  # 8 블록 + 2 관통
    assert clam.get_power_amount("plating") == 8, "피해로 감소해선 안 됨"

    # 다음 턴(라운드2) 시작 시 1 감소
    fake_combat.turn = 2
    plating.on_turn_start()
    assert clam.get_power_amount("plating") == 7, \
        f"턴 시작 감소 실패: {clam.get_power_amount('plating')}"
    print("✅ SewerClam: Plating 8 → 8블록 → 라운드1 제외 → 다음 턴 시작마다 1 감소(피해 무관)")


def test_tangled_blocks_attacks():
    """Tangled(얽힘): 공격 카드 플레이 차단 (VineShambler)."""
    print("\n=== Tangled 카드 차단 ===\n")

    player = make_player()
    shambler = VineShambler()
    combat = CombatState(player, [shambler], seed=1)
    combat.start()
    player.energy = 3
    combat.hand = [Strike()]

    strike = combat.hand[0]
    assert combat.is_card_playable(strike), "차단 전엔 플레이 가능해야 함"
    player.apply_power(TangledPower(1))
    assert not combat.is_card_playable(strike), "Tangled 중 공격 차단 실패"
    assert combat.play_card(strike, shambler) is False
    player.tick_powers()  # 지속시간 만료
    assert combat.is_card_playable(strike), "Tangled 만료 후 차단 해제 실패"
    print(f"✅ Tangled 1턴: 공격 차단 → 만료 후 해제")


def test_real_encounters():
    """실제 인카운터 구성 검증."""
    print("\n=== 실제 인카운터 구성 ===\n")

    rng = random.Random(7)

    # SlimesWeak: 소형 2 + 중형 1 (3마리)
    slimes = make_encounter("slimes_weak", rng)
    assert len(slimes) == 3
    smalls = [m for m in slimes if m.monster_id.endswith("_slime_s")]
    mediums = [m for m in slimes if m.monster_id.endswith("_slime_m")]
    assert len(smalls) == 2 and len(mediums) == 1
    assert slimes[1].monster_id.endswith("_slime_m"), "중형이 가운데여야 함"
    print(f"✅ slimes_weak: {[m.title for m in slimes]}")

    # CultistsNormal: Calcified + Damp
    cultists = make_encounter("cultists_normal", rng)
    assert [m.monster_id for m in cultists] == ["calcified_cultist", "damp_cultist"]
    print(f"✅ cultists_normal: {[m.title for m in cultists]}")

    # KnightsElite: 3기사
    knights = make_encounter("knights_elite", rng)
    assert [m.monster_id for m in knights] == ["flail_knight", "spectral_knight", "magi_knight"]
    print(f"✅ knights_elite: {[m.title for m in knights]} (총 HP {sum(m.max_initial_hp for m in knights)})")

    # RaidersNormal: 5종 중 중복 없이 3종
    for seed in range(5):
        raiders = make_encounter("raiders_normal", random.Random(seed))
        ids = [m.monster_id for m in raiders]
        assert len(ids) == 3 and len(set(ids)) == 3, f"레이더 중복: {ids}"
    print(f"✅ raiders_normal: 5시드 전부 중복 없는 3종")


def test_mawler_use_only_once():
    """Mawler ROAR: 전투당 1회만 (UseOnlyOnce)."""
    print("\n=== Mawler UseOnlyOnce ===\n")

    mawler = Mawler()
    mawler.setup_for_combat(None, rng=random.Random(3))
    player = make_player()

    roar_count = 0
    for _ in range(40):
        if mawler._move_state_machine.get_current_move_name() == "ROAR_MOVE":
            roar_count += 1
        mawler.take_turn([player])
    assert roar_count <= 1, f"ROAR {roar_count}회 발생 (1회 한정이어야 함)"
    print(f"✅ 40턴 동안 ROAR {roar_count}회 (≤1)")


def test_spectral_knight_pattern():
    """SpectralKnight: HEX 시작, SLASH 3연속 금지, FLAME 연속 금지."""
    print("\n=== SpectralKnight 행동 패턴 ===\n")

    knight = SpectralKnight()
    knight.setup_for_combat(None, rng=random.Random(11))
    player = make_player()

    moves = []
    for _ in range(50):
        moves.append(knight._move_state_machine.get_current_move_name())
        knight.take_turn([player])

    assert moves[0] == "HEX", f"첫 행동이 HEX 아님: {moves[0]}"
    for i in range(len(moves) - 2):
        assert not (moves[i] == moves[i+1] == moves[i+2] == "SOUL_SLASH"), "SLASH 3연속 발생"
    for a, b in zip(moves, moves[1:]):
        assert not (a == b == "SOUL_FLAME"), "FLAME 연속 발생"
    print(f"✅ 50턴: HEX 시작, SLASH ≤2연속, FLAME 비연속 ({moves[:6]}...)")


def test_full_combat_new_monsters():
    """신규 인카운터 전투가 예외 없이 완료."""
    print("\n=== 신규 인카운터 전투 스모크 ===\n")

    for enc in ENCOUNTERS:
        player = make_player()
        combat = CombatState(player, make_encounter(enc, random.Random(1)), seed=1)
        result = combat.run(GreedyPolicy())
        status = "승" if result.victory else "패"
        print(f"  {enc:22s} {status} ({result.turns}턴, HP {result.player_hp})")
    print(f"✅ 인카운터 {len(ENCOUNTERS)}종 전부 전투 루프 정상 완료")


def main():
    print("🧪 STS2 Phase 6a 통합 테스트\n")
    test_new_monster_stats()
    test_plating_power()
    test_tangled_blocks_attacks()
    test_real_encounters()
    test_mawler_use_only_once()
    test_spectral_knight_pattern()
    test_full_combat_new_monsters()

    print("\n" + "=" * 60)
    print("✅ Phase 6a 모든 테스트 통과!")
    print("=" * 60)
    print("\n📊 Phase 6a 구현 현황:")
    print("  ✅ 신규 몬스터 17종 (총 34종) — 멀티에이전트 이식 + 수치 검증")
    print("  ✅ Plating 파워 + 턴 종료 파워 훅 배선")
    print("  ✅ Tangled/Shackled 카드 차단 전투 배선")
    print("  ✅ 실제 인카운터 구성 12종 (SlimesWeak 3마리, KnightsElite 3기사 등)")


if __name__ == "__main__":
    main()
