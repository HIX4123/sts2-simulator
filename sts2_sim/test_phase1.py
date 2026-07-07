"""
Phase 1 통합 테스트.
기본 전투 루프가 올바르게 동작하는지 검증한다.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sts2_sim.rng.seeded_rng import SeededRng
from sts2_sim.entities.player import Player
from sts2_sim.entities.monster import Jawworm, Cultist, AcidSlimeSmall
from sts2_sim.core.combat_state import CombatState
from sts2_sim.core.combat_manager import CombatManager, apply_play_card, apply_end_turn
from sts2_sim.cards.ironclad.basic import make_ironclad_starter_deck, Strike, Defend, Bash
from sts2_sim.models.power_model import Vulnerable, Weak, Strength


def make_test_player(seed: int = 42) -> Player:
    player = Player("Ironclad", max_hp=80, max_energy=3)
    for card in make_ironclad_starter_deck():
        player.add_card_to_deck(card)
    return player


def test_rng():
    print("=== RNG 테스트 ===")
    rng = SeededRng(42)
    vals = [rng.next_int(100) for _ in range(5)]
    print(f"  next_int(100) × 5: {vals}")
    rng2 = SeededRng(42)
    vals2 = [rng2.next_int(100) for _ in range(5)]
    assert vals == vals2, "같은 씨드는 같은 결과를 내야 함"
    print("  ✓ 결정론적 재현 확인")

    lst = list(range(10))
    shuffled = rng.shuffle(lst)
    print(f"  shuffle([0..9]): {shuffled}")
    assert sorted(shuffled) == list(range(10)), "셔플 후 원소 보존"
    print("  ✓ 셔플 원소 보존 확인")


def test_vulnerable_damage():
    print("\n=== Vulnerable 데미지 배율 테스트 ===")
    rng = SeededRng(1)
    player = make_test_player()
    jawworm = Jawworm(hp=40)
    state = CombatState(player, [jawworm], rng)

    # 수동으로 드로우 파일 초기화
    state.draw_pile = player.populate_draw_pile(rng)

    # 몬스터 초기화
    jawworm.combat_state = state
    jawworm.setup_for_combat(state)

    # Vulnerable 부여 (apply_power가 bus.register 포함)
    vuln = Vulnerable()
    jawworm.apply_power(vuln, 2, player.creature)

    # 데미지 10 → 15 예상
    hp_before = jawworm.current_hp
    ctx = {"amount": 10, "source": player.creature, "target": jawworm, "card": None}
    ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
    final = ctx["amount"]
    print(f"  Vulnerable(2) 적에게 데미지 10 → {final}")
    assert final == 15, f"Expected 15, got {final}"
    print("  ✓ Vulnerable 1.5배 확인")


def test_combat_loop_greedy():
    """탐욕적 정책(항상 공격 카드 우선 플레이)으로 전투."""
    print("\n=== 전투 루프 테스트 (탐욕 정책) ===")
    rng = SeededRng(123)
    player = make_test_player()
    jawworm = Jawworm(hp=40)
    state = CombatState(player, [jawworm], rng)
    manager = CombatManager()

    cards_played_total = 0
    gen = manager.run_combat(state)

    try:
        while True:
            cs = next(gen)
            # 탐욕 정책: 플레이 가능한 카드를 모두 플레이
            played_this_turn = True
            while played_this_turn and not cs.is_over:
                played_this_turn = False
                for card in list(cs.hand):
                    if card.can_play(cs):
                        target = None
                        from sts2_sim.models.card_model import TargetType
                        if card.target_type == TargetType.SINGLE_ENEMY:
                            target = cs.living_enemies[0] if cs.living_enemies else None
                        if apply_play_card(cs, card, target):
                            cards_played_total += 1
                            played_this_turn = True
                            break  # 핸드 리스트가 변경됐으므로 재시작
    except StopIteration as e:
        result = e.value

    print(f"  전투 결과: {'승리' if result.won else '패배'}")
    print(f"  턴 수: {result.turns}")
    print(f"  남은 HP: {result.player_hp_remaining}")
    print(f"  플레이한 카드 수: {cards_played_total}")
    assert result.won or not result.won  # 승패 무관, 크래시 없이 완료
    print("  ✓ 전투 루프 크래시 없이 완료")
    return result


def test_reproducibility():
    print("\n=== 결정론적 재현 테스트 ===")

    def run_one(seed: int):
        rng = SeededRng(seed)
        player = make_test_player(seed)
        jawworm = Jawworm(hp=40)
        state = CombatState(player, [jawworm], rng)
        manager = CombatManager()
        gen = manager.run_combat(state)
        try:
            while True:
                cs = next(gen)
                from sts2_sim.models.card_model import TargetType
                for card in list(cs.hand):
                    if card.can_play(cs):
                        t = cs.living_enemies[0] if (
                            card.target_type == TargetType.SINGLE_ENEMY and cs.living_enemies
                        ) else None
                        apply_play_card(cs, card, t)
                        break
        except StopIteration as e:
            return e.value

    r1 = run_one(999)
    r2 = run_one(999)
    assert r1.won == r2.won and r1.turns == r2.turns and r1.player_hp_remaining == r2.player_hp_remaining
    print(f"  씨드 999: won={r1.won}, turns={r1.turns}, hp={r1.player_hp_remaining}")
    print("  ✓ 동일 씨드 → 동일 결과")


def test_power_duration():
    print("\n=== 파워 지속시간 틱 테스트 ===")
    from sts2_sim.models.power_model import Vulnerable, Weak

    vuln = Vulnerable()
    vuln._amount = 2
    vuln.tick_duration()
    assert vuln.amount == 1, f"Expected 1, got {vuln.amount}"
    vuln.tick_duration()
    assert vuln.amount == 0, f"Expected 0, got {vuln.amount}"
    print("  ✓ Vulnerable 지속시간 2→1→0 확인")


if __name__ == "__main__":
    print("STS2 Simulator Phase 1 테스트 시작\n" + "="*40)
    try:
        test_rng()
        test_vulnerable_damage()
        test_power_duration()
        test_combat_loop_greedy()
        test_reproducibility()
        print("\n" + "="*40)
        print("✓ 모든 테스트 통과!")
    except Exception as e:
        import traceback
        print(f"\n✗ 테스트 실패: {e}")
        traceback.print_exc()
        sys.exit(1)
