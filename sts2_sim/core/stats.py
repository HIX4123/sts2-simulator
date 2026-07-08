"""
STS2 통계 러너 — 시드별 다중 런 실행 및 요약.

사용:
  python3 -m sts2_sim.core.stats [character_id] [n_runs] [--policy greedy|simple]
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
              policy_name: str = "greedy", base_seed: int = 0) -> StatsSummary:
    """동일 조건으로 n회 런 실행 후 통계 집계 (시드 = base_seed + i)."""
    policy_cls = POLICIES[policy_name]
    summary = StatsSummary(character_id, policy_name, n_runs)

    for i in range(n_runs):
        run = RunState(character_id, seed=base_seed + i)
        result = run.play(policy=policy_cls())
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

    summary = run_stats(character_id, n_runs, policy_name)
    print(summary.report())


if __name__ == "__main__":
    main(sys.argv)
