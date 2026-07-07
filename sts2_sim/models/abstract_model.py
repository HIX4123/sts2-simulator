"""
AbstractModel — 모든 게임 객체(카드·파워·렐릭·몬스터)의 공통 훅 베이스.
sts2.dll MegaCrit.Sts2.Core.Models.AbstractModel 대응.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_sim.hooks.hook_bus import HookBus


class AbstractModel:
    """
    훅 핸들러를 선언하는 기반 클래스.
    서브클래스는 관심 있는 훅 메서드만 override하면 된다.

    등록은 HookBus.register(self)로 이루어진다.
    """

    _hook_priority: int = 1  # 렐릭=0, 파워=1, 카드=2 (기본: 파워)

    def subscribed_hooks(self) -> list[str]:
        """
        이 모델이 구독하는 훅 이름 목록.
        기본: 오버라이드된 훅 메서드 이름을 자동 감지.
        """
        from sts2_sim.hooks.hook_bus import ALL_HOOKS
        hooks = []
        for hook in ALL_HOOKS:
            # 이 클래스(또는 서브클래스)에서 메서드를 실제로 override했는지 확인
            if type(self).__dict__.get(hook) is not None:
                hooks.append(hook)
            else:
                # MRO 탐색: AbstractModel 자신이 아닌 서브클래스에서 정의됐는지
                for cls in type(self).__mro__[:-1]:
                    if cls is AbstractModel:
                        break
                    if hook in cls.__dict__:
                        hooks.append(hook)
                        break
        return hooks

    # ──────────────────────────────────────────
    # 아래 메서드들은 서브클래스에서 필요한 것만 override한다.
    # 모든 메서드는 context: dict를 받고, 수정 시 context를 반환한다.
    # ──────────────────────────────────────────

    # 데미지
    def BeforeAttack(self, ctx: dict): pass
    def AfterAttack(self, ctx: dict): pass
    def BeforeDamageReceived(self, ctx: dict): pass
    def AfterDamageReceived(self, ctx: dict): pass
    def AfterDamageReceivedLate(self, ctx: dict): pass
    def AfterDamageGiven(self, ctx: dict): pass
    def AfterModifyingDamageAmount(self, ctx: dict): pass

    # 블록
    def BeforeBlockGained(self, ctx: dict): pass
    def AfterBlockGained(self, ctx: dict): pass
    def AfterBlockBroken(self, ctx: dict): pass
    def AfterBlockCleared(self, ctx: dict): pass
    def AfterModifyingBlockAmount(self, ctx: dict): pass

    # 카드
    def AfterCardDrawn(self, ctx: dict): pass
    def AfterCardDrawnEarly(self, ctx: dict): pass
    def AfterCardPlayed(self, ctx: dict): pass
    def AfterCardPlayedLate(self, ctx: dict): pass
    def BeforeCardPlayed(self, ctx: dict): pass
    def AfterCardDiscarded(self, ctx: dict): pass
    def AfterCardExhausted(self, ctx: dict): pass
    def AfterCardChangedPiles(self, ctx: dict): pass
    def AfterShuffle(self, ctx: dict): pass

    # 핸드
    def BeforeHandDraw(self, ctx: dict): pass
    def AfterHandEmptied(self, ctx: dict): pass
    def AfterFlush(self, ctx: dict): pass
    def BeforeFlush(self, ctx: dict): pass

    # 턴
    def AfterPlayerTurnStart(self, ctx: dict): pass
    def AfterPlayerTurnStartEarly(self, ctx: dict): pass
    def AfterSideTurnStart(self, ctx: dict): pass
    def AfterSideTurnEnd(self, ctx: dict): pass
    def BeforeSideTurnEnd(self, ctx: dict): pass
    def BeforeSideTurnEndEarly(self, ctx: dict): pass
    def BeforeSideTurnEndVeryEarly(self, ctx: dict): pass

    # 에너지
    def AfterEnergyReset(self, ctx: dict): pass
    def AfterEnergySpent(self, ctx: dict): pass
    def AfterModifyingEnergyGain(self, ctx: dict): pass

    # HP/사망
    def AfterCurrentHpChanged(self, ctx: dict): pass
    def BeforeDeath(self, ctx: dict): pass
    def AfterDeath(self, ctx: dict): pass
    def AfterPreventingDeath(self, ctx: dict): pass

    # 파워
    def AfterPowerAmountChanged(self, ctx: dict): pass
    def BeforePowerAmountChanged(self, ctx: dict): pass
    def AfterModifyingPowerAmountGiven(self, ctx: dict): pass
    def AfterModifyingPowerAmountReceived(self, ctx: dict): pass

    # 전투
    def BeforeCombatStart(self, ctx: dict): pass
    def AfterCombatEnd(self, ctx: dict): pass
    def AfterCombatVictory(self, ctx: dict): pass

    # 보상/아이템
    def AfterGoldGained(self, ctx: dict): pass
    def AfterModifyingGoldGained(self, ctx: dict): pass
    def AfterPotionUsed(self, ctx: dict): pass
    def BeforePotionUsed(self, ctx: dict): pass

    # 맵
    def BeforeRoomEntered(self, ctx: dict): pass
    def AfterRoomEntered(self, ctx: dict): pass
    def AfterActEntered(self, ctx: dict): pass

    # 기타
    def AfterForge(self, ctx: dict): pass
    def AfterRestSiteHeal(self, ctx: dict): pass
    def AfterRestSiteSmith(self, ctx: dict): pass
    def AfterStarsGained(self, ctx: dict): pass
    def AfterStarsSpent(self, ctx: dict): pass
    def AfterOrbChanneled(self, ctx: dict): pass
    def AfterOrbEvoked(self, ctx: dict): pass
