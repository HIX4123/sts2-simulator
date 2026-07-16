"""
STS2 통계 러너 — 시드별 다중 런 실행 및 요약.

사용:
  python3 -m sts2_sim.core.stats [character_id] [n_runs] [--policy greedy|simple] [--verbose]

--verbose: 턴/카드/피격 단위 전투 로그(RunResult.combat_log)를 함께 출력한다.
런당 로그량이 많아지므로, 처음 VERBOSE_RUN_CAP개 런만 전체 로그를 출력하고
그 이후 런은 한 줄 요약만 출력한다 (예: `--verbose`로 n_runs=50을 실행해도
콘솔이 넘치지 않도록).
"""
from __future__ import annotations
import sys
from dataclasses import dataclass, field
from typing import List

from sts2_sim.core.combat import SimplePolicy
from sts2_sim.core.policy import GreedyPolicy
from sts2_sim.core.run import RunState, RunResult


POLICIES = {
    "simple": SimplePolicy,
    "greedy": GreedyPolicy,
}

VERBOSE_RUN_CAP = 5  # --verbose일 때 전체 전투 로그를 출력할 최대 런 수


@dataclass
class StatsSummary:
    character_id: str
    policy_name: str
    n_runs: int
    wins: int = 0
    total_floors: int = 0
    total_final_hp: int = 0
    total_gold: int = 0
    results: List[RunResult] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        return self.wins / self.n_runs if self.n_runs else 0.0

    @property
    def avg_floors(self) -> float:
        return self.total_floors / self.n_runs if self.n_runs else 0.0

    @property
    def avg_final_hp(self) -> float:
        return self.total_final_hp / self.n_runs if self.n_runs else 0.0

    @property
    def avg_gold(self) -> float:
        return self.total_gold / self.n_runs if self.n_runs else 0.0

    def report(self) -> str:
        return (
            f"캐릭터: {self.character_id} | 정책: {self.policy_name} | 런: {self.n_runs}회\n"
            f"  승률: {self.win_rate:.1%} ({self.wins}/{self.n_runs})\n"
            f"  평균 도달 층: {self.avg_floors:.2f}\n"
            f"  평균 최종 HP: {self.avg_final_hp:.1f}\n"
            f"  평균 골드: {self.avg_gold:.1f}"
        )


def run_stats(character_id: str = "ironclad", n_runs: int = 50,
              policy_name: str = "greedy", base_seed: int = 0,
              verbose: bool = False) -> StatsSummary:
    """동일 조건으로 n회 런 실행 후 통계 집계 (시드 = base_seed + i).
    verbose=True면 처음 VERBOSE_RUN_CAP개 런에 한해 RunResult.combat_log를 채운다
    (그 이후 런은 기존과 동일하게 조용히 실행 — 대량 실행 시 로그 폭주 방지)."""
    policy_cls = POLICIES[policy_name]
    summary = StatsSummary(character_id, policy_name, n_runs)

    for i in range(n_runs):
        run = RunState(character_id, seed=base_seed + i)
        run_verbose = verbose and i < VERBOSE_RUN_CAP
        result = run.play(policy=policy_cls(), verbose=run_verbose)
        summary.results.append(result)
        summary.wins += result.victory
        summary.total_floors += result.floors_cleared
        summary.total_final_hp += result.final_hp
        summary.total_gold += result.gold

    return summary


def main(argv: List[str]) -> None:
    character_id = argv[1] if len(argv) > 1 else "ironclad"
    n_runs = int(argv[2]) if len(argv) > 2 else 50
    policy_name = "greedy"
    if "--policy" in argv:
        policy_name = argv[argv.index("--policy") + 1]
    verbose = "--verbose" in argv

    summary = run_stats(character_id, n_runs, policy_name, verbose=verbose)

    if verbose:
        for i, result in enumerate(summary.results):
            if i < VERBOSE_RUN_CAP:
                print(f"\n===== Run {i} (seed={i}) =====")
                for line in result.combat_log:
                    print(line)
            outcome = "승리" if result.victory else "패배"
            print(f"[Run {i}] {outcome} — 층 {result.floors_cleared}, "
                  f"HP {result.final_hp}, 골드 {result.gold}")
        print()

    print(summary.report())


if __name__ == "__main__":
    main(sys.argv)
