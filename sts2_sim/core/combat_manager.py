"""
CombatManager — 전투 루프 오케스트레이터.
sts2.dll MegaCrit.Sts2.Core.Combat.CombatManager 대응.

yield 기반 제너레이터: 외부 정책(AI)이 플레이어 액션을 결정한다.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generator, Optional

from sts2_sim.core.combat_state import CombatState, CombatSide

if TYPE_CHECKING:
    from sts2_sim.entities.player import Player
    from sts2_sim.entities.monster import Monster
    from sts2_sim.models.card_model import CardModel, PileType


BASE_HAND_DRAW_COUNT = 5  # CombatManager.baseHandDrawCount


@dataclass
class CombatResult:
    won: bool
    turns: int
    player_hp_remaining: int
    cards_played: int = 0


class CombatManager:
    """
    전투 진행 루프.

    사용법:
        manager = CombatManager()
        gen = manager.run_combat(state)
        for cs in gen:                    # cs = CombatState (플레이어 턴)
            action = policy(cs)
            apply_action(cs, action)
        result = gen.return_value          # 또는 StopIteration.value
    """

    def setup_combat(self, state: CombatState):
        """
        전투 초기화. SetUpCombat() 대응.
        1. 드로우 파일 생성 (마스터 덱 셔플)
        2. 몬스터 전투 설정 (SetupForCombat, 첫 인텐트 결정)
        3. 렐릭·파워 훅 버스 등록
        4. BeforeCombatStart 훅
        """
        player = state.player

        # 드로우 파일 초기화
        state.draw_pile = player.populate_draw_pile(state.combat_rng)

        # 몬스터 초기화
        for monster in state.enemies:
            monster.combat_state = state
            monster.setup_for_combat(state)

        # 렐릭 훅 등록
        for relic in player.relics:
            state.bus.register(relic, priority=0)

        # BeforeCombatStart
        state.bus.fire("BeforeCombatStart", state=state)
        state.bus.fire("BeforeCombatStartLate", state=state)

        state.is_in_progress = True

    def setup_player_turn(self, state: CombatState):
        """
        플레이어 턴 시작. SetupPlayerTurn() 대응.
        에너지 리셋 → 드로우 → 훅 발동.
        """
        state.round_number += 1
        state.current_side = CombatSide.PLAYER

        # 에너지 리셋
        state.player.reset_energy(state)

        # 파워 턴 시작 스냅샷
        for p in state.player.creature._powers.values():
            if hasattr(p, "snapshot_amount_on_turn_start"):
                p.snapshot_amount_on_turn_start()

        # 훅: 플레이어 턴 시작
        state.bus.fire("AfterPlayerTurnStartEarly", state=state)
        state.bus.fire("AfterPlayerTurnStart", state=state)
        state.bus.fire("AfterSideTurnStart", state=state)
        state.bus.fire("AfterSideTurnStartLate", state=state)

        # 핸드 드로우
        draw_count = BASE_HAND_DRAW_COUNT
        ctx = {"count": draw_count, "state": state}
        ctx = state.bus.fire("AfterModifyingHandDraw", **ctx) if hasattr(state.bus, "fire") else ctx
        for _ in range(ctx.get("count", draw_count)):
            state.draw_card()

        state.bus.fire("AfterPlayerTurnStartLate", state=state)

    def end_player_turn(self, state: CombatState):
        """
        플레이어 턴 종료. EndPlayerTurnPhaseOne/Two() 대응.
        핸드 버리기 → 파워 틱 → 훅 발동.
        """
        # Phase 1: 핸드 정리
        state.bus.fire("BeforeSideTurnEndVeryEarly", state=state)
        state.bus.fire("BeforeSideTurnEndEarly", state=state)
        state.bus.fire("BeforeSideTurnEnd", state=state)

        # 핸드 버리기 (FlushPlayerHand)
        state.flush_hand()

        # 카드 임시 비용 초기화
        for card in list(state.discard_pile) + list(state.draw_pile):
            if hasattr(card, "end_of_turn_cleanup"):
                card.end_of_turn_cleanup(state)

        # Phase 2: 파워 틱
        state.player.creature.tick_all_powers()

        state.bus.fire("AfterSideTurnEnd", state=state)
        state.bus.fire("AfterSideTurnEndLate", state=state)

    def execute_enemy_turn(self, state: CombatState):
        """
        몬스터 턴. ExecuteEnemyTurn() 대응.
        살아있는 몬스터가 순서대로 행동한다.
        """
        state.current_side = CombatSide.ENEMY

        state.bus.fire("AfterSideTurnStart", state=state)

        for monster in list(state.living_enemies):
            if not monster.is_dead:
                state.bus.fire("BeforeAttack",
                               source=monster, state=state)
                monster.take_turn(state)

        # 몬스터 파워 틱
        for monster in state.enemies:
            if not monster.is_dead:
                monster.prepare_for_next_turn()

        state.bus.fire("BeforeSideTurnEnd", state=state)
        state.bus.fire("AfterSideTurnEnd", state=state)

    def check_win_condition(self, state: CombatState) -> bool:
        """승/패 조건 확인. CheckWinCondition() 대응."""
        return state.is_over

    def end_combat(self, state: CombatState, won: bool):
        """전투 종료 처리."""
        state.is_in_progress = False
        if won:
            state.bus.fire("AfterCombatVictoryEarly", state=state)
            state.bus.fire("AfterCombatVictory", state=state)
        state.bus.fire("AfterCombatEnd", state=state, won=won)

        # 전투 후 플레이어 상태 정리 (블록, 임시 파워는 유지되지 않음)
        # HP는 유지됨
        state.player.creature.clear_block()

    def run_combat(self, state: CombatState) -> Generator[CombatState, None, CombatResult]:
        """
        전투 루프 제너레이터.

        플레이어 턴마다 CombatState를 yield한다.
        외부에서 apply_action()으로 액션을 수행한 뒤 next()를 호출한다.

        예:
            gen = manager.run_combat(state)
            try:
                while True:
                    cs = next(gen)
                    action = policy(cs)
                    apply_action(cs, action)
            except StopIteration as e:
                result = e.value
        """
        self.setup_combat(state)

        cards_played = 0
        turns = 0

        while not state.is_over:
            # ── 플레이어 턴 ──
            self.setup_player_turn(state)
            turns += 1

            # 외부 정책에 제어권 위임
            # 정책은 apply_action()으로 카드 플레이/포션 사용/턴 종료를 수행
            yield state

            if state.is_over:
                break

            # ── 플레이어 턴 종료 ──
            self.end_player_turn(state)

            if state.is_over:
                break

            # ── 몬스터 턴 ──
            self.execute_enemy_turn(state)

        won = state.all_enemies_dead
        self.end_combat(state, won)

        return CombatResult(
            won=won,
            turns=turns,
            player_hp_remaining=state.player.current_hp,
            cards_played=cards_played,
        )


# ──────────────────────────────────────────
# 액션 적용 헬퍼
# ──────────────────────────────────────────

def apply_play_card(
    state: CombatState,
    card: "CardModel",
    target: Optional[object] = None,
):
    """
    카드 플레이. PlayCardAction.execute() 대응.
    훅 순서: BeforeCardPlayed → use() → AfterCardPlayed → 파일 이동.
    """
    from sts2_sim.models.card_model import PileType

    if not card.can_play(state):
        return False

    # 비용 차감
    state.player.spend_energy(card.energy_cost, state)

    # 훅: 카드 플레이 전
    ctx = {"card": card, "target": target, "state": state}
    state.bus.fire("BeforeCardPlayed", **ctx)

    # 카드 효과 실행
    card.use(state, target)

    # 훅: 카드 플레이 후
    state.bus.fire("AfterCardPlayed", card=card, state=state)
    state.bus.fire("AfterCardPlayedLate", card=card, state=state)

    # 파일 이동
    pile = card.get_result_pile(state)
    if pile == PileType.EXHAUST:
        state.move_card_to_exhaust(card)
    else:
        state.move_card_to_discard(card)

    return True


def apply_end_turn(state: CombatState):
    """플레이어가 턴 종료를 선택. EndPlayerTurnAction 대응."""
    # CombatManager.run_combat()의 yield 이후 루프가 자동으로 end_player_turn 호출
    # 여기서는 외부 정책이 "턴 종료" 신호를 보내는 것을 기록만 함
    pass
