#!/usr/bin/env python3
"""
STS2 Phase 5 통합 테스트.
인텐트 인지 그리디 정책 + 통계 러너 + 재현성.
"""
from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.policy import GreedyPolicy, estimate_incoming_damage
from sts2_sim.core.encounters import make_encounter
from sts2_sim.core.run import RunState
from sts2_sim.core.stats import run_stats
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import TwigSlimeS, Chomper, FlailKnight
from sts2_sim.models.sts2_card import Strike, Defend, create_card
from sts2_sim.models.sts2_power import Strength


def make_combat(monsters, hand_ids, seed=1):
    """지정 핸드로 전투 상태 구성."""
    player = Player(create_character("ironclad"))
    combat = CombatState(player, monsters, seed=seed)
    combat.start()
    player.energy = player.max_energy
    combat.hand = [create_card(cid) for cid in hand_ids]
    return combat, player


def test_greedy_lethal():
    """막타 우선: 죽일 수 있는 적이 있으면 공격 선택."""
    print("=== 그리디: 막타 우선 ===\n")

    slime = TwigSlimeS()
    combat, player = make_combat([slime], ["defend", "strike", "defend"])
    slime._current_hp = 5  # Strike 6딜로 처치 가능

    card, target = GreedyPolicy().choose(combat)
    assert card.card_id == "strike", f"막타 실패: {card.card_id}"
    assert target is slime
    print(f"✅ 적 HP 5 → Strike(6딜) 막타 선택")


def test_greedy_defense():
    """방어 판단: 공격 없이 큰 피해 예상 시 블록."""
    print("\n=== 그리디: 방어 판단 ===\n")

    chomper = Chomper()  # CLAMP 8×2 = 16 예상
    combat, player = make_combat([chomper], ["defend", "defend"])

    incoming = estimate_incoming_damage(combat)
    assert incoming == 16, f"예상 피해 계산 실패: {incoming}"

    card, target = GreedyPolicy().choose(combat)
    assert card.card_id == "defend"
    print(f"✅ 예상 피해 16, 공격 카드 없음 → Defend 선택")


def test_incoming_estimation():
    """예상 피해: 힘/다중 히트 반영."""
    print("\n=== 예상 피해 계산 ===\n")

    knight = FlailKnight()
    combat, player = make_combat([knight], ["strike"])
    # FLAIL 상태로 강제 전환 (9딜 ×2)
    sm = knight._move_state_machine
    flail = next(s for s in sm.states if s.name == "FLAIL_MOVE")
    sm.current_state = flail

    assert estimate_incoming_damage(combat) == 18
    knight.apply_power(Strength(3))
    assert estimate_incoming_damage(combat) == 24, "힘 반영 실패 (9+3)×2"
    print(f"✅ FLAIL 9×2=18, 힘+3 → (9+3)×2=24")


def test_policy_comparison():
    """그리디 ≥ 단순 정책 (고정 시드 → 결정적)."""
    print("\n=== 정책 비교 (knights_elite, 시드 0~19) ===\n")

    wins = {}
    for name, pol_cls in [("simple", SimplePolicy), ("greedy", GreedyPolicy)]:
        w = 0
        for seed in range(20):
            player = Player(create_character("ironclad"))
            combat = CombatState(player, make_encounter("knights_elite"), seed=seed)
            w += combat.run(pol_cls()).victory
        wins[name] = w

    assert wins["greedy"] >= wins["simple"], f"그리디 열세: {wins}"
    print(f"✅ simple {wins['simple']}/20 vs greedy {wins['greedy']}/20")


def test_stats_runner():
    """통계 러너: 집계 및 시드 재현성."""
    print("\n=== 통계 러너 ===\n")

    s1 = run_stats("ironclad", n_runs=10, policy_name="greedy", base_seed=0)
    assert s1.n_runs == 10 and len(s1.results) == 10
    assert 0.0 <= s1.win_rate <= 1.0
    print(s1.report())

    # 동일 시드 재현성
    s2 = run_stats("ironclad", n_runs=10, policy_name="greedy", base_seed=0)
    v1 = [r.victory for r in s1.results]
    v2 = [r.victory for r in s2.results]
    f1 = [r.floors_cleared for r in s1.results]
    f2 = [r.floors_cleared for r in s2.results]
    assert v1 == v2 and f1 == f2, "시드 재현성 실패"
    print(f"\n✅ 동일 시드 10회 재실행 → 결과 완전 일치 (재현성)")


def test_run_progression():
    """런 진행 요소: 카드 보상으로 덱 성장, 휴식 업그레이드."""
    print("\n=== 런 진행 요소 ===\n")

    run = RunState("ironclad", seed=2)
    initial_deck = len(run.deck)
    result = run.play(policy=GreedyPolicy())

    if result.floors_cleared >= 1:
        assert result.deck_size > initial_deck, "카드 보상 미반영"
        print(f"✅ 덱 성장: {initial_deck} → {result.deck_size}장 ({result.floors_cleared}층 도달)")
    upgraded = [c for c in run.deck if c.upgraded]
    print(f"✅ 업그레이드된 카드: {len(upgraded)}장")


def main():
    print("🧪 STS2 Phase 5 통합 테스트\n")
    test_greedy_lethal()
    test_greedy_defense()
    test_incoming_estimation()
    test_policy_comparison()
    test_stats_runner()
    test_run_progression()

    print("\n" + "=" * 60)
    print("✅ Phase 5 모든 테스트 통과!")
    print("=" * 60)
    print("\n📊 Phase 5 구현 현황:")
    print("  ✅ GreedyPolicy: 막타 → 공격/방어 가치 비교 → 취약 셋업 보너스")
    print("  ✅ 예상 피해 계산 (인텐트 + 힘/약화/취약)")
    print("  ✅ 통계 러너 (승률/평균 층/HP/골드, 시드 재현성)")
    print("  ✅ 런 진행: 카드 보상, 휴식 회복/업그레이드, 난이도 티어")


if __name__ == "__main__":
    main()
