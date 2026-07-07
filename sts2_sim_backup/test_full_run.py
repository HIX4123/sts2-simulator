"""
풀 런 통합 테스트.
시드 27로 승리 재현 + 100회 시뮬레이션 승률 계산.
"""
import sys
sys.path.insert(0, '.')

from sts2_sim.core.run_factory import make_ironclad_player
from sts2_sim.core.runner import RunConfig, run_full_playthrough


def test_seed27_win():
    """시드 27: 결정론적 승리 재현."""
    player = make_ironclad_player(seed=27)
    config = RunConfig(seed=27, verbose=False)
    result = run_full_playthrough(player, config)
    assert result.won, f"시드 27 실패: {result.cause_of_death}"
    assert result.floors_cleared == 16
    assert result.final_hp > 0
    print(f"✓ 시드 27 승리: {result.final_hp}HP, {result.final_gold}골드")


def test_determinism():
    """동일 시드는 항상 동일한 결과를 낸다."""
    def run(seed):
        player = make_ironclad_player(seed=seed)
        config = RunConfig(seed=seed, verbose=False)
        return run_full_playthrough(player, config)

    r1 = run(27)
    r2 = run(27)
    assert r1.won == r2.won
    assert r1.final_hp == r2.final_hp
    assert r1.final_gold == r2.final_gold
    print(f"✓ 결정론적 재현 확인 (시드 27 × 2회)")


def test_100_runs():
    """100회 시뮬레이션 승률 집계."""
    wins = 0
    deaths_by_floor = {}
    total = 100

    for seed in range(1, total + 1):
        player = make_ironclad_player(seed=seed)
        config = RunConfig(seed=seed, verbose=False)
        result = run_full_playthrough(player, config)
        if result.won:
            wins += 1
        else:
            f = result.floors_cleared
            deaths_by_floor[f] = deaths_by_floor.get(f, 0) + 1

    win_rate = wins / total * 100
    print(f"✓ 100회 시뮬레이션: 승리 {wins}/{total} ({win_rate:.1f}%)")
    if deaths_by_floor:
        top_deaths = sorted(deaths_by_floor.items(), key=lambda x: -x[1])[:3]
        print(f"  주요 사망 층: {top_deaths}")
    return win_rate


if __name__ == "__main__":
    print("=== STS2 시뮬레이터 풀 런 테스트 ===\n")
    test_seed27_win()
    test_determinism()
    win_rate = test_100_runs()
    print(f"\n모든 테스트 통과. 승률: {win_rate:.1f}%")
