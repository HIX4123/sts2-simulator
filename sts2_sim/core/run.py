"""
STS2 런 루프 — 단순화된 층 진행 (전투/휴식/엘리트).
실제 STS2 맵 그래프는 미이식 (Phase 6): 고정 층 시퀀스로 대체.
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import List, Optional

from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import random_encounter
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character


# 층 시퀀스: N=일반 전투, R=휴식, E=엘리트
DEFAULT_FLOOR_PLAN = ["N", "N", "N", "R", "N", "N", "R", "E"]


@dataclass
class RunResult:
    victory: bool
    floors_cleared: int
    total_floors: int
    final_hp: int
    gold: int
    combat_log: List[str] = field(default_factory=list)


class RunState:
    """한 번의 런 (시드 고정)."""

    REST_HEAL_RATIO = 0.30
    REWARD_GOLD_MIN = 10
    REWARD_GOLD_MAX = 20

    def __init__(self, character_id: str = "ironclad", seed: int = 0):
        self.rng = random.Random(seed)
        self.seed = seed
        character = create_character(character_id)
        if character is None:
            raise ValueError(f"알 수 없는 캐릭터: {character_id}")
        self.character = character

    def play(self, policy=None, floor_plan: Optional[List[str]] = None) -> RunResult:
        policy = policy or SimplePolicy()
        plan = floor_plan or DEFAULT_FLOOR_PLAN
        log: List[str] = []

        for floor_num, room in enumerate(plan, start=1):
            if room == "R":
                heal = int(self.character.max_hp * self.REST_HEAL_RATIO)
                self.character.heal(heal)
                log.append(f"F{floor_num} 휴식: +{heal} HP → {self.character.current_hp}")
                continue

            monsters = random_encounter(self.rng, elite=(room == "E"))
            names = ", ".join(m.title for m in monsters)
            player = Player(self.character)
            combat = CombatState(player, monsters, seed=self.rng.randrange(1 << 30))
            result = combat.run(policy)

            if not result.victory:
                log.append(f"F{floor_num} 패배: [{names}] {result.turns}턴, HP {result.player_hp}")
                return RunResult(False, floor_num - 1, len(plan),
                                 self.character.current_hp, self.character.gold, log)

            gold = self.rng.randint(self.REWARD_GOLD_MIN, self.REWARD_GOLD_MAX)
            self.character.gain_gold(gold)
            log.append(f"F{floor_num} 승리: [{names}] {result.turns}턴, "
                       f"HP {result.player_hp}, +{gold}G")

        return RunResult(True, len(plan), len(plan),
                         self.character.current_hp, self.character.gold, log)
