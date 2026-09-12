#!/usr/bin/env python3
"""
STS2 Phase 4 통합 테스트.
전투 턴 루프 + 몬스터 통합(Creature 기반) + 인카운터 + 런 시스템.
"""
import random

from sts2_sim.core.combat import CombatState, SimplePolicy, CombatResult
from sts2_sim.core.encounters import make_encounter, random_encounter, NORMAL_POOL
from sts2_sim.core.run import RunState
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import (
    TwigSlimeS, TwigSlimeM, Chomper, FatGremlin, FlailKnight, DampCultist,
)
from sts2_sim.models.sts2_card import Bash
from sts2_sim.models.sts2_power import Vulnerable


def make_player(char_id="ironclad"):
    return Player(create_character(char_id))


def test_scripted_combat():
    """수동 스크립트 전투: Strike 2방으로 TwigSlimeS 처치."""
    print("=== 스크립트 전투 ===\n")

    player = make_player()
    slime = TwigSlimeS()
    combat = CombatState(player, [slime], seed=1)
    combat.start()

    assert slime.current_hp == 11
    player.energy = 3
    combat.draw_cards(5)

    strikes = [c for c in combat.hand if c.card_id == "strike"]
    assert len(strikes) >= 2, f"핸드에 Strike 부족: {[c.card_id for c in combat.hand]}"
    combat.play_card(strikes[0], slime)
    assert slime.current_hp == 5
    combat.play_card(strikes[1], slime)
    assert slime.is_dead
    print(f"✅ Strike 6딜 ×2 → TwigSlimeS(11) 처치")

    # 에너지 소모 확인
    assert player.energy == 1
    print(f"✅ 에너지 소모: 3 → {player.energy}")


def test_full_combat_policy():
    """정책 기반 전체 전투: Ironclad vs slimes_weak은 안정적으로 승리해야 함."""
    print("\n=== 정책 전투 (SimplePolicy) ===\n")

    wins = 0
    for seed in range(10):
        player = make_player()
        monsters = make_encounter("slimes_weak", random.Random(seed))
        combat = CombatState(player, monsters, seed=seed)
        result = combat.run(SimplePolicy())
        wins += result.victory
    assert wins >= 8, f"slimes_weak 승률 이상: {wins}/10"
    print(f"✅ Ironclad vs slimes_weak(실제 3마리 구성): {wins}/10 승리")

    # BurningBlood: 승리 후 6 회복 확인
    player = make_player()
    player.lose_hp(20)
    hp_before = player.current_hp
    combat = CombatState(player, [TwigSlimeS()], seed=3)
    result = combat.run(SimplePolicy())
    assert result.victory
    assert player.current_hp > hp_before, "BurningBlood 회복 미적용"
    print(f"✅ BurningBlood: 승리 후 HP {hp_before} → {player.current_hp}")


def test_status_insertion():
    """Chomper SCREECH: 플레이어 버림 더미에 Dazed 3장."""
    print("\n=== 상태이상 삽입 ===\n")

    player = make_player()
    chomper = Chomper(scream_first=True)
    combat = CombatState(player, [chomper], seed=1)
    combat.start()

    assert chomper.get_power_amount("artifact") == 2
    chomper.take_turn([player])  # SCREECH
    dazed = [c for c in combat.discard_pile if c.card_id == "dazed"]
    assert len(dazed) == 3, f"Dazed 삽입 실패: {len(dazed)}"
    assert all(c.is_ethereal and not c.playable for c in dazed)
    print(f"✅ Chomper SCREECH: Dazed 3장 삽입 (에테리얼, 사용 불가)")

    # TwigSlimeM STICKY_SHOT: Slimed 1장
    player = make_player()
    slime = TwigSlimeM()
    combat = CombatState(player, [slime], seed=1)
    combat.start()
    slime.take_turn([player])  # 초기 상태 = STICKY_SHOT
    slimed = [c for c in combat.discard_pile if c.card_id == "slimed"]
    assert len(slimed) == 1
    print(f"✅ TwigSlimeM STICKY_SHOT: Slimed 1장 삽입")


def test_artifact_blocks_debuff():
    """Artifact: 디버프 2회 무효 후 3번째부터 적용."""
    print("\n=== Artifact 디버프 차단 ===\n")

    player = make_player()
    chomper = Chomper()
    chomper.setup_for_combat(None)

    assert chomper.apply_power(Vulnerable(2)) is False
    assert chomper.get_power_amount("vulnerable") == 0
    assert chomper.get_power_amount("artifact") == 1
    assert chomper.apply_power(Vulnerable(2)) is False
    assert chomper.get_power_amount("artifact") == 0
    assert chomper.apply_power(Vulnerable(2)) is True
    assert chomper.get_power_amount("vulnerable") == 2
    print(f"✅ Artifact 2 → 취약 2회 무효, 3번째 적용")


def test_escape():
    """FatGremlin: 대기 → 도주 → 전투 승리 처리."""
    print("\n=== 도주 메카닉 ===\n")

    player = make_player()
    gremlin = FatGremlin()
    combat = CombatState(player, [gremlin], seed=1)
    result = combat.run(SimplePolicy(), max_turns=10)
    # 그렘린이 죽거나 도주하면 전투 종료 — 어느 쪽이든 승리
    assert result.victory
    print(f"✅ FatGremlin 전투 {result.turns}턴 내 종료 (처치 또는 도주)")


def test_random_branch():
    """FlailKnight RandomBranchState: WAR_CHANT는 연속 선택 불가."""
    print("\n=== 무작위 분기 상태 머신 ===\n")

    knight = FlailKnight()
    knight.setup_for_combat(None, rng=random.Random(42))
    sm = knight._move_state_machine

    moves = []
    for _ in range(60):
        moves.append(sm.get_current_move_name())
        sm._last_move_name = sm.get_current_move_name()
        sm.advance_state()

    for a, b in zip(moves, moves[1:]):
        assert not (a == "WAR_CHANT" and b == "WAR_CHANT"), "WAR_CHANT 연속 발생"
    assert "FLAIL_MOVE" in moves and "RAM_MOVE" in moves
    print(f"✅ 60턴 시뮬레이션: WAR_CHANT 연속 없음, 3종 행동 혼합 ({moves[:6]}...)")


def test_ritual_scaling():
    """DampCultist: Ritual 적용 다음 턴은 첫 틱 스킵(힘 0), 그 다음 턴부터 강해짐
    (원본 RitualPower.WasJustAppliedByEnemy)."""
    print("\n=== Ritual 스케일링 ===\n")

    player = make_player()
    cultist = DampCultist()
    combat = CombatState(player, [cultist], seed=1)
    combat.start()

    def monster_turn_start():
        # 몬스터 턴 시작 훅 시뮬레이션 (combat.run 내부와 동일)
        for power in list(cultist._powers.values()):
            if hasattr(power, "on_turn_start"):
                power.on_turn_start()

    monster_turn_start()          # 턴1 시작 (Ritual 아직 없음)
    cultist.take_turn([player])   # 턴1: INCANTATION → Ritual(5) 부여

    monster_turn_start()          # 턴2 시작 — 첫 틱 스킵, 힘 여전히 0
    hp0 = player.current_hp
    cultist.take_turn([player])   # 턴2: DARK_STRIKE 1딜 (힘 0)
    assert hp0 - player.current_hp == 1, f"Ritual 첫 틱 스킵 실패: {hp0 - player.current_hp}"

    monster_turn_start()          # 턴3 시작 — 힘 +5 발동
    hp1 = player.current_hp
    cultist.take_turn([player])   # 턴3: DARK_STRIKE 1 + 힘5 = 6
    assert hp1 - player.current_hp == 6, f"Ritual 스케일 실패: {hp1 - player.current_hp}"
    print("✅ DARK_STRIKE: 부여 다음 턴 1딜(첫 틱 스킵) → 그 다음 턴부터 6딜(기본 1 + 힘 5)")


def test_run_loop():
    """전체 런 루프: 시드 고정 실행이 예외 없이 완료."""
    print("\n=== 런 루프 ===\n")

    results = []
    for seed in range(5):
        run = RunState("ironclad", seed=seed)
        result = run.play()
        results.append(result)
        status = "🏆 완주" if result.victory else f"💀 {result.floors_cleared}층"
        print(f"  시드 {seed}: {status}, HP {result.final_hp}, {result.gold}G")

    assert all(isinstance(r.floors_cleared, int) for r in results)
    assert any(r.floors_cleared > 0 for r in results), "모든 런이 1층에서 실패"
    print(f"✅ 런 5회 실행 완료 (완주 {sum(r.victory for r in results)}/5)")

    # 다른 캐릭터도 런 가능해야 함
    for char_id in ["silent", "defect", "necrobinder", "regent"]:
        result = RunState(char_id, seed=1).play()
        print(f"  {char_id}: {'완주' if result.victory else str(result.floors_cleared) + '층'}")
    print(f"✅ 5개 캐릭터 전부 런 실행 가능")


def main():
    print("🧪 STS2 Phase 4 통합 테스트\n")
    test_scripted_combat()
    test_full_combat_policy()
    test_status_insertion()
    test_artifact_blocks_debuff()
    test_escape()
    test_random_branch()
    test_ritual_scaling()
    test_run_loop()

    print("\n" + "=" * 60)
    print("✅ Phase 4 모든 테스트 통과!")
    print("=" * 60)
    print("\n📊 Phase 4 구현 현황:")
    print("  ✅ CombatState 턴 루프 (에너지/드로우/카드/오브/파워 틱)")
    print("  ✅ MonsterModel = Creature 통합 (파워/블록 공유)")
    print("  ✅ RandomBranchState (가중치 분기 + 연속 제한)")
    print("  ✅ 상태이상 삽입 (Dazed/Slimed), Artifact, 도주, Ritual 스케일링")
    print("  ✅ 인카운터 풀 6종 + 런 루프 (5캐릭터)")


if __name__ == "__main__":
    main()
