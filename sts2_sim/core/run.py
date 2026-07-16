"""
STS2 런 루프 — 단순화된 층 진행 (전투/휴식/엘리트) + 덱 성장.
실제 STS2 맵 그래프는 미이식 (Phase 6): 난이도 단계별 고정 층 시퀀스로 대체.

진행 요소:
  - 전투 승리 시 캐릭터 풀에서 카드 1장 보상 (덱에 추가)
  - 휴식: HP 60% 미만이면 회복, 아니면 무작위 미업그레이드 카드 업그레이드
  - 층 구성: 쉬움(E1) → 중간(E2) → 엘리트 순 난이도 상승
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import List, Optional

from sts2_sim.core.combat import CombatState, SimplePolicy
from sts2_sim.core.encounters import (
    EASY_POOL, MEDIUM_POOL, ELITE_POOL, random_encounter_from,
)
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.models.sts2_card import Rarity, create_card
from sts2_sim.cards.ironclad import IRONCLAD_POOL_BY_RARITY
from sts2_sim.cards.silent import SILENT_POOL_BY_RARITY
from sts2_sim.cards.defect import DEFECT_POOL_BY_RARITY
from sts2_sim.cards.necrobinder import NECROBINDER_POOL_BY_RARITY
from sts2_sim.cards.regent import REGENT_POOL_BY_RARITY


# 층 시퀀스: N1=쉬운 전투, N2=중간 전투, R=휴식, E=엘리트
DEFAULT_FLOOR_PLAN = ["N1", "N1", "R", "N2", "N2", "R", "E"]

# 전투 보상 카드 풀 (캐릭터별 — 이식된 카드 한정)
REWARD_POOLS = {
    "Necrobinder": ["bodyguard", "unleash", "strike", "defend"],
    "Regent": ["venerate", "falling_star", "strike", "defend"],
}

# 희귀도 가중치 (STS 표준 일반 전투 보상 분포)
_RARITY_WEIGHTS = [(Rarity.COMMON, 60), (Rarity.UNCOMMON, 37), (Rarity.RARE, 3)]

# 캐릭터별 희귀도 풀 (Phase 6b: Ironclad 전체 이식)
RARITY_POOLS = {
    "Ironclad": {
        # Basic(bash/strike/defend)은 원본과 동일하게 보상 풀 제외
        Rarity.COMMON: IRONCLAD_POOL_BY_RARITY[Rarity.COMMON],
        Rarity.UNCOMMON: IRONCLAD_POOL_BY_RARITY[Rarity.UNCOMMON],
        Rarity.RARE: IRONCLAD_POOL_BY_RARITY[Rarity.RARE],
    },
    "Silent": SILENT_POOL_BY_RARITY,
    "Defect": DEFECT_POOL_BY_RARITY,
    "Necrobinder": NECROBINDER_POOL_BY_RARITY,
    "Regent": REGENT_POOL_BY_RARITY,
}


@dataclass
class RunResult:
    victory: bool
    floors_cleared: int
    total_floors: int
    final_hp: int
    gold: int
    deck_size: int = 0
    combat_log: List[str] = field(default_factory=list)


class RunState:
    """한 번의 런 (시드 고정). 덱은 런 전체에서 유지/성장한다."""

    REST_HEAL_RATIO = 0.30
    REST_HEAL_THRESHOLD = 0.60   # HP가 이 비율 미만이면 휴식 시 회복 선택
    REWARD_GOLD_MIN = 10
    REWARD_GOLD_MAX = 20

    POOL_BY_ROOM = {"N1": EASY_POOL, "N2": MEDIUM_POOL, "E": ELITE_POOL}

    def __init__(self, character_id: str = "ironclad", seed: int = 0):
        self.rng = random.Random(seed)
        self.seed = seed
        character = create_character(character_id)
        if character is None:
            raise ValueError(f"알 수 없는 캐릭터: {character_id}")
        self.character = character
        self.deck = [create_card(cid) for cid in character.get_start_deck()]
        self.deck = [c for c in self.deck if c is not None]

    def _rest(self, floor_num: int, log: List[str]) -> None:
        """휴식: 회복 또는 업그레이드."""
        hp_ratio = self.character.current_hp / self.character.max_hp
        upgradable = [c for c in self.deck if not c.upgraded]
        if hp_ratio < self.REST_HEAL_THRESHOLD or not upgradable:
            heal = int(self.character.max_hp * self.REST_HEAL_RATIO)
            self.character.heal(heal)
            log.append(f"F{floor_num} 휴식(회복): +{heal} HP → {self.character.current_hp}")
        else:
            card = self.rng.choice(upgradable)
            card.upgrade()
            log.append(f"F{floor_num} 휴식(업그레이드): {card.name}+")

    @staticmethod
    def _reward_score(card, player) -> float:
        """보상 후보 가치: 코스트당 데미지/블록, 파워는 고정 가치."""
        from sts2_sim.models.sts2_card import CardType
        if card.card_type == CardType.POWER:
            return 5.0
        cost = max(1, card.cost)
        damage = card.damage_estimate(player, None, None)
        block = card.block_estimate(player, None)
        return max(damage, block, 2.0) / cost  # 유틸 스킬 최소 가치 2

    def _card_reward(self, log: List[str]) -> None:
        """전투 보상: 희귀도 가중(60/37/3)으로 3장 제시 → 휴리스틱 최고 가치 선택.
        (원본 STS 보상 구조 — 3장 중 1장 선택)"""
        rarity_pool = RARITY_POOLS.get(self.character.name)
        if rarity_pool:
            rarities = [r for r, _ in _RARITY_WEIGHTS]
            weights = [w for _, w in _RARITY_WEIGHTS]
            offers = []
            while len(offers) < 3:
                rarity = self.rng.choices(rarities, weights=weights, k=1)[0]
                card = create_card(self.rng.choice(rarity_pool[rarity]))
                if card and card.card_id not in {c.card_id for c in offers}:
                    offers.append(card)
            player = Player(self.character, deck=self.deck)
            card = max(offers, key=lambda c: self._reward_score(c, player))
        else:
            pool = REWARD_POOLS.get(self.character.name, ["strike", "defend"])
            card = create_card(self.rng.choice(pool))
        if card:
            self.deck.append(card)

    def play(self, policy=None, floor_plan: Optional[List[str]] = None) -> RunResult:
        policy = policy or SimplePolicy()
        plan = floor_plan or DEFAULT_FLOOR_PLAN
        log: List[str] = []

        for floor_num, room in enumerate(plan, start=1):
            if room == "R":
                self._rest(floor_num, log)
                continue

            pool = self.POOL_BY_ROOM.get(room, EASY_POOL)
            monsters = random_encounter_from(self.rng, pool)
            names = ", ".join(m.title for m in monsters)
            player = Player(self.character, deck=self.deck)
            combat = CombatState(player, monsters, seed=self.rng.randrange(1 << 30))
            result = combat.run(policy)

            if not result.victory:
                log.append(f"F{floor_num} 패배: [{names}] {result.turns}턴, HP {result.player_hp}")
                return RunResult(False, floor_num - 1, len(plan),
                                 self.character.current_hp, self.character.gold,
                                 len(self.deck), log)

            gold = self.rng.randint(self.REWARD_GOLD_MIN, self.REWARD_GOLD_MAX)
            self.character.gain_gold(gold)
            self._card_reward(log)
            for _ in range(getattr(combat, "extra_card_rewards", 0)):  # TheHunt
                self._card_reward(log)
            log.append(f"F{floor_num} 승리: [{names}] {result.turns}턴, "
                       f"HP {result.player_hp}, +{gold}G")

        return RunResult(True, len(plan), len(plan),
                         self.character.current_hp, self.character.gold,
                         len(self.deck), log)
