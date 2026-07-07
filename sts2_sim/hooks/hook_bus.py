"""
HookBus — AbstractModel의 97개 Before/After 훅을 이벤트 버스로 구현.

등록 우선순위: 렐릭 → 파워 → 카드 (sts2.dll 분석 기준)
AfterModifying* 훅은 context dict를 in-place로 수정해 값을 변경한다.
"""
from __future__ import annotations
from collections import defaultdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sts2_sim.models.abstract_model import AbstractModel


# sts2.dll AbstractModel에서 추출한 전체 훅 목록
ALL_HOOKS: frozenset[str] = frozenset([
    # 데미지
    "BeforeAttack", "AfterAttack",
    "BeforeDamageReceived", "AfterDamageReceived", "AfterDamageReceivedLate",
    "AfterDamageGiven", "AfterModifyingDamageAmount",
    # 블록
    "BeforeBlockGained", "AfterBlockGained",
    "AfterBlockBroken", "AfterBlockCleared", "AfterModifyingBlockAmount",
    "AfterPreventingBlockClear",
    # 카드
    "AfterCardDrawn", "AfterCardDrawnEarly",
    "AfterCardPlayed", "AfterCardPlayedLate",
    "BeforeCardPlayed", "BeforeCardAutoPlayed",
    "AfterCardDiscarded", "AfterCardExhausted",
    "AfterCardChangedPiles", "AfterCardChangedPilesLate",
    "AfterCardEnteredCombat", "AfterCardGeneratedForCombat",
    "BeforeCardRemoved", "AfterAddToDeckPrevented",
    "AfterModifyingCardPlayCount", "AfterModifyingCardPlayResultPileOrPosition",
    # 핸드/셔플
    "BeforeHandDraw", "BeforeHandDrawLate",
    "AfterHandEmptied", "AfterFlush", "BeforeFlush", "BeforeFlushLate",
    "AfterShuffle", "AfterPreventingDraw",
    # 턴
    "AfterPlayerTurnStart", "AfterPlayerTurnStartEarly", "AfterPlayerTurnStartLate",
    "AfterSideTurnStart", "AfterSideTurnStartLate",
    "AfterSideTurnEnd", "AfterSideTurnEndLate",
    "BeforeSideTurnEnd", "BeforeSideTurnEndEarly", "BeforeSideTurnEndVeryEarly",
    "AfterTakingExtraTurn",
    # 에너지
    "AfterEnergyReset", "AfterEnergyResetLate",
    "AfterEnergySpent", "AfterModifyingEnergyGain",
    # HP/사망
    "AfterCurrentHpChanged",
    "BeforeDeath", "AfterDeath", "AfterDiedToDoom",
    "AfterPreventingDeath", "AfterOstyRevived",
    "AfterModifyingHpLostBeforeOsty", "AfterModifyingHpLostAfterOsty",
    # 파워
    "AfterPowerAmountChanged", "BeforePowerAmountChanged",
    "AfterModifyingPowerAmountGiven", "AfterModifyingPowerAmountReceived",
    # 전투
    "BeforeCombatStart", "BeforeCombatStartLate",
    "AfterCombatEnd", "AfterCombatVictory", "AfterCombatVictoryEarly",
    "AfterCreatureAddedToCombat",
    # 렐릭/포션/골드
    "AfterItemPurchased", "AfterGoldGained", "AfterModifyingGoldGained",
    "AfterPotionProcured", "AfterPotionDiscarded", "AfterPotionUsed",
    "BeforePotionUsed",
    # 렐릭 보상
    "AfterModifyingRewards", "BeforeCombatRewardOffered",
    "AfterRewardTaken", "AfterModifyingCardRewardOptions",
    # Stars
    "AfterStarsGained", "AfterStarsSpent",
    # 오브 (Defect)
    "AfterOrbChanneled", "AfterOrbEvoked",
    "AfterModifyingOrbPassiveTriggerCount",
    # 맵/룸
    "BeforeRoomEntered", "AfterRoomEntered",
    "AfterActEntered", "AfterMapGenerated",
    # 기타
    "AfterForge", "AfterRestSiteHeal", "AfterRestSiteSmith",
    "AfterSummon", "AfterTargetingBlockedVfx",
    "BeforeAutoPrePlayPhaseEntered",
    "AfterAutoPrePlayPhaseEntered", "AfterAutoPrePlayPhaseEnteredEarly",
    "AfterAutoPrePlayPhaseEnteredLate", "AfterAutoPostPlayPhaseEntered",
])


class HookBus:
    """
    전투 내 모든 게임 객체(카드·파워·렐릭)의 훅을 중앙 관리한다.
    각 객체는 전투 시작 시 register(), 제거 시 unregister()를 호출한다.
    """

    def __init__(self):
        # hook_name → 리스너 목록 (등록 순서 유지)
        self._listeners: dict[str, list["AbstractModel"]] = defaultdict(list)

    def register(self, model: "AbstractModel", priority: int = 0):
        """
        모델을 훅 버스에 등록한다.
        priority: 낮을수록 먼저 발동 (렐릭=0, 파워=1, 카드=2)
        """
        model._hook_priority = priority
        for hook_name in model.subscribed_hooks():
            listeners = self._listeners[hook_name]
            # 우선순위 순서로 삽입
            insert_idx = len(listeners)
            for i, existing in enumerate(listeners):
                if getattr(existing, "_hook_priority", 1) > priority:
                    insert_idx = i
                    break
            listeners.insert(insert_idx, model)

    def unregister(self, model: "AbstractModel"):
        """모델을 모든 훅에서 제거한다."""
        for hook_name in list(self._listeners.keys()):
            try:
                self._listeners[hook_name].remove(model)
            except ValueError:
                pass

    def fire(self, hook_name: str, **kwargs) -> dict[str, Any]:
        """
        훅을 발동한다.
        AfterModifying* 훅은 context를 수정할 수 있으며, 수정된 context를 반환한다.
        """
        context = dict(kwargs)
        for listener in list(self._listeners.get(hook_name, [])):
            handler = getattr(listener, hook_name, None)
            if handler is not None:
                result = handler(context)
                # 핸들러가 dict를 반환하면 context 갱신
                if isinstance(result, dict):
                    context.update(result)
        return context

    def listener_count(self, hook_name: str) -> int:
        return len(self._listeners.get(hook_name, []))

    def clear(self):
        self._listeners.clear()
