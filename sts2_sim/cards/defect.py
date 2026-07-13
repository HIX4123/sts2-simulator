"""
Defect 카드 풀 — 디컴파일 MegaCrit.Sts2.Core.Models.CardPools.DefectCardPool 이식.

원본 91종 중:
  - StrikeDefect/DefendDefect/Zap/Dualcast 4종은 models/sts2_card.py에 기존 구현
  - 멀티플레이 전용 5종 제외: EnergySurge, Hibernate, Ignition,
    ImitationLearning, OneForAll
  - 나머지 82종 + Fuel 토큰(Compact 변환물)을 여기서 구현

모든 수치는 디컴파일 .cs의 CanonicalVars/OnUpgrade 그대로.
단순화 표기: 원본이 카드 선택 UI를 요구하는 곳(Hologram/Scavenge)은
무작위 선택으로 대체하고 주석에 [선택→무작위] 표기.
"""
from __future__ import annotations

from sts2_sim.models.sts2_card import (
    STS2Card, CardType, Rarity, CARD_REGISTRY, _deal_attack, create_card,
)
from sts2_sim.cards.ironclad import (
    _Attack, _Block, _CostDownOnUpgrade, _alive, MAX_HAND_SIZE,
)


def _queue(source):
    return getattr(source, "orb_queue", None)


def _channel(source, combat, orb_cls, count: int = 1) -> None:
    queue = _queue(source)
    if queue is None:
        return
    for _ in range(count):
        queue.channel(orb_cls(), source, combat)


def _orb_kinds(source) -> int:
    """보유 중인 오브 종류 수 (CompileDriver/Synchronize/Coolant)."""
    queue = _queue(source)
    if queue is None:
        return 0
    return len({o.orb_id for o in queue.orbs})


_ATTACK_INTENTS = None


def _intends_to_attack(target) -> bool:
    """몬스터가 공격 인텐트인지 (GoForTheEyes)."""
    global _ATTACK_INTENTS
    get_intent = getattr(target, "get_current_intent", None)
    if get_intent is None:
        return False
    if _ATTACK_INTENTS is None:
        from sts2_sim.entities.sts2_monster import IntentType
        _ATTACK_INTENTS = {IntentType.ATTACK, IntentType.ATTACK_BUFF,
                           IntentType.ATTACK_DEBUFF, IntentType.ATTACK_DEFEND}
    return get_intent().intent_type in _ATTACK_INTENTS


# ══════════════════════════════════════════
# Common (20)
# ══════════════════════════════════════════

class BallLightning(_Attack):
    """볼 라이트닝 — 7딜(업글 10) + 라이트닝 채널."""
    card_id = "ball_lightning"
    name = "Ball Lightning"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 7, 10

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import LightningOrb
        super().use(source, targets, combat)
        _channel(source, combat, LightningOrb)


class Barrage(_Attack):
    """탄막 — 5딜(업글 7) × 보유 오브 수."""
    card_id = "barrage"
    name = "Barrage"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 5, 7

    def use(self, source, targets, combat=None) -> None:
        hits = len(_queue(source) or [])
        for _ in range(hits):
            for target in targets:
                if _alive(target):
                    _deal_attack(source, target, self._damage())

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage() * len(_queue(player) or [])


class BeamCell(_Attack):
    """빔 셀 — 0코스트 3딜(업글 4) + 취약 1(업글 2)."""
    card_id = "beam_cell"
    name = "Beam Cell"
    rarity = Rarity.COMMON
    cost = 0
    dmg, dmg_up = 3, 4

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Vulnerable
        super().use(source, targets, combat)
        for target in targets:
            if _alive(target):
                target.apply_power(Vulnerable(2 if self.upgraded else 1),
                                   applier=source)


class BoostAway(_Block):
    """부스터 이탈 — 0코스트 6블록(업글 9) + Dazed 1장 버림 더미 생성."""
    card_id = "boost_away"
    name = "Boost Away"
    rarity = Rarity.COMMON
    cost = 0
    blk, blk_up = 6, 9

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is not None:
            combat.generate_card("dazed")


class ChargeBattery(_Block):
    """배터리 충전 — 7블록(업글 10) + 다음 턴 에너지 +1."""
    card_id = "charge_battery"
    name = "Charge Battery"
    rarity = Rarity.COMMON
    cost = 1
    blk, blk_up = 7, 10

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import EnergyNextTurn
        super().use(source, targets, combat)
        source.apply_power(EnergyNextTurn(1))


class Claw(_Attack):
    """발톱 — 0코스트 3딜(업글 4); 플레이 시 전투 내 모든 Claw 데미지 +2(업글 +3)."""
    card_id = "claw"
    name = "Claw"
    rarity = Rarity.COMMON
    cost = 0
    dmg, dmg_up = 3, 4

    def __init__(self):
        super().__init__()
        self._extra_this_combat = 0  # BuffFromClawPlay — 전투 한정 누적

    def _damage(self) -> int:
        return super()._damage() + self._extra_this_combat

    def reset_combat_state(self) -> None:
        self._extra_this_combat = 0

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is None:
            return
        increase = 3 if self.upgraded else 2
        seen = set()
        piles = (combat.hand + combat.draw_pile + combat.discard_pile
                 + combat.exhaust_pile + [self])
        for card in piles:
            if isinstance(card, Claw) and id(card) not in seen:
                seen.add(id(card))
                card._extra_this_combat += increase


class ColdSnap(_Attack):
    """한파 — 6딜(업글 9) + 서리 채널."""
    card_id = "cold_snap"
    name = "Cold Snap"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 6, 9

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import FrostOrb
        super().use(source, targets, combat)
        _channel(source, combat, FrostOrb)


class CompileDriver(_Attack):
    """컴파일 드라이버 — 7딜(업글 10) + 보유 오브 종류 수만큼 드로우."""
    card_id = "compile_driver"
    name = "Compile Driver"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 7, 10

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is not None:
            combat.draw_cards(_orb_kinds(source))


class Coolheaded(STS2Card):
    """냉정 — 서리 채널 + 드로우 1(업글 2)."""
    card_id = "coolheaded"
    name = "Coolheaded"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import FrostOrb
        _channel(source, combat, FrostOrb)
        if combat is not None:
            combat.draw_cards(2 if self.upgraded else 1)


class FocusedStrike(_Attack):
    """집중 타격 — 9딜(업글 11) + 이번 턴 집중 +1(업글 +2)."""
    card_id = "focused_strike"
    name = "Focused Strike"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 9, 11
    tags = frozenset({"strike"})

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import TempFocus
        super().use(source, targets, combat)
        source.apply_power(TempFocus(2 if self.upgraded else 1))


class GoForTheEyes(_Attack):
    """눈을 노려라 — 0코스트 3딜(업글 4); 대상이 공격 인텐트면 약화 1(업글 2)."""
    card_id = "go_for_the_eyes"
    name = "Go for the Eyes"
    rarity = Rarity.COMMON
    cost = 0
    dmg, dmg_up = 3, 4

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Weak
        for target in targets:
            if not _alive(target):
                continue
            intends = _intends_to_attack(target)
            _deal_attack(source, target, self._damage())
            if intends and _alive(target):
                target.apply_power(Weak(2 if self.upgraded else 1),
                                   applier=source)


class GunkUp(_Attack):
    """오물 투척 — 4딜(업글 5)×3 + Slimed 1장 버림 더미 생성."""
    card_id = "gunk_up"
    name = "Gunk Up"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 4, 5
    hits = 3

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is not None:
            combat.generate_card("slimed")


class Hologram(_Block):
    """홀로그램 — 3블록(업글 5) + 버림 더미 카드 1장 회수 [선택→무작위].
    소모 (업글 시 소모 제거)."""
    card_id = "hologram"
    name = "Hologram"
    rarity = Rarity.COMMON
    cost = 1
    blk, blk_up = 3, 5
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.exhausts = False

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is None or not combat.discard_pile:
            return
        if len(combat.hand) < MAX_HAND_SIZE:
            card = combat.rng.choice(combat.discard_pile)
            combat.discard_pile.remove(card)
            combat.hand.append(card)


class Hotfix(STS2Card):
    """핫픽스 — 0코스트, 이번 턴 집중 +2. 소모 (업글 시 소모 제거)."""
    card_id = "hotfix"
    name = "Hotfix"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 0
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.exhausts = False

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import TempFocus
        source.apply_power(TempFocus(2))


class Leap(_Block):
    """도약 — 9블록 (업글 12)."""
    card_id = "leap"
    name = "Leap"
    rarity = Rarity.COMMON
    cost = 1
    blk, blk_up = 9, 12


class LightningRodCard(_Block):
    """피뢰침 — 4블록(업글 7) + 피뢰침 파워 2 (턴 시작마다 라이트닝 채널)."""
    card_id = "lightning_rod"
    name = "Lightning Rod"
    rarity = Rarity.COMMON
    cost = 1
    blk, blk_up = 4, 7

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import LightningRod
        super().use(source, targets, combat)
        source.apply_power(LightningRod(2))


class MomentumStrike(_Attack):
    """탄력 타격 — 11딜(업글 15); 플레이 후 이번 전투 동안 비용 0."""
    card_id = "momentum_strike"
    name = "Momentum Strike"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 11, 15
    tags = frozenset({"strike"})

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        self._cost_this_combat = 0  # EnergyCost.SetThisCombat(0)


class SweepingBeam(_Attack):
    """소인선 광선 — 전체 6딜(업글 9) + 드로우 1."""
    card_id = "sweeping_beam"
    name = "Sweeping Beam"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 6, 9
    target_all = True

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is not None:
            combat.draw_cards(1)


class Turbo(STS2Card):
    """터보 — 0코스트, 에너지 +2(업글 +3) + Void 1장 버림 더미 생성."""
    card_id = "turbo"
    name = "Turbo"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        source.gain_energy(3 if self.upgraded else 2)
        if combat is not None:
            combat.generate_card("void")


class Uproar(_Attack):
    """소란 — 6딜(업글 8)×2 + 드로우 더미의 무작위 공격 카드 자동 플레이."""
    card_id = "uproar"
    name = "Uproar"
    rarity = Rarity.COMMON
    cost = 2
    dmg, dmg_up = 6, 8
    hits = 2

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is None:
            return
        attacks = [c for c in combat.draw_pile
                   if c.card_type == CardType.ATTACK and c.playable]
        if not attacks:  # 원본: 플레이 가능 공격이 없으면 아무 공격이라도
            attacks = [c for c in combat.draw_pile
                       if c.card_type == CardType.ATTACK]
        if attacks:
            pick = combat.rng.choice(attacks)
            combat.draw_pile.remove(pick)
            combat.auto_play(pick)


# ══════════════════════════════════════════
# Uncommon (35)
# ══════════════════════════════════════════

class BootSequence(_Block):
    """부팅 시퀀스 — 0코스트 10블록(업글 13). 선천성, 소모."""
    card_id = "boot_sequence"
    name = "Boot Sequence"
    rarity = Rarity.UNCOMMON
    cost = 0
    blk, blk_up = 10, 13
    is_innate = True
    exhausts = True


class BulkUp(STS2Card):
    """벌크 업 — 파워: 오브 슬롯 1 제거, 힘 +2(업글 +3), 민첩 +2(업글 +3)."""
    card_id = "bulk_up"
    name = "Bulk Up"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Strength, Dexterity
        queue = _queue(source)
        if queue is not None:
            queue.remove_slots(1)
        n = 3 if self.upgraded else 2
        source.apply_power(Strength(n))
        source.apply_power(Dexterity(n))


class Capacitor(STS2Card):
    """축전기 — 파워: 오브 슬롯 +2 (업글 +3)."""
    card_id = "capacitor"
    name = "Capacitor"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        queue = _queue(source)
        if queue is not None:
            queue.gain_slots(3 if self.upgraded else 2)


class Chaos(STS2Card):
    """혼돈 — 무작위 오브 1개 채널 (업글 2개)."""
    card_id = "chaos"
    name = "Chaos"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import ORB_REGISTRY
        queue = _queue(source)
        if queue is None or combat is None:
            return
        orb_ids = sorted(ORB_REGISTRY)  # 원본 _validOrbs 5종 전체
        for _ in range(2 if self.upgraded else 1):
            orb_cls = ORB_REGISTRY[combat.rng.choice(orb_ids)]
            queue.channel(orb_cls(), source, combat)


class Chill(STS2Card):
    """오한 — 0코스트, 적 1명당 서리 채널. 소모 (업글 시 소모 제거)."""
    card_id = "chill"
    name = "Chill"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.exhausts = False

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import FrostOrb
        count = len(combat.alive_enemies) if combat is not None else 0
        _channel(source, combat, FrostOrb, count)


class Compact(_Block):
    """압축 — 6블록(업글 7) + 손패의 상태이상 카드를 전부 Fuel로 변환
    (업글 시 Fuel+)."""
    card_id = "compact"
    name = "Compact"
    rarity = Rarity.UNCOMMON
    cost = 1
    blk, blk_up = 6, 7

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is None:
            return
        for i, card in enumerate(list(combat.hand)):
            if card.card_type == CardType.STATUS:
                fuel = create_card("fuel")
                if self.upgraded:
                    fuel.upgrade()
                combat.hand[combat.hand.index(card)] = fuel


class Darkness(STS2Card):
    """어둠 — 어둠 오브 채널 + 모든 어둠 오브의 패시브 1회(업글 2회) 발동."""
    card_id = "darkness"
    name = "Darkness"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import DarkOrb
        _channel(source, combat, DarkOrb)
        queue = _queue(source)
        if queue is None:
            return
        triggers = 2 if self.upgraded else 1
        for orb in [o for o in queue.orbs if o.orb_id == "dark"]:
            for _ in range(triggers):
                orb.passive(combat)


class DoubleEnergy(_CostDownOnUpgrade, STS2Card):
    """에너지 2배 — 현재 에너지만큼 에너지 획득. 소모. (업글 0코스트)"""
    card_id = "double_energy"
    name = "Double Energy"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        source.gain_energy(getattr(source, "energy", 0))


class FeralCard(STS2Card):
    """야성 — 파워: 매 턴 처음 1장의 0코스트 공격이 손패로 복귀. (업글 1코스트)"""
    card_id = "feral"
    name = "Feral"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 2

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Feral
        source.apply_power(Feral(1))
        # 원본 AfterApplied: 이번 턴 이미 플레이한 0코스트 공격 수만큼 예산 차감
        feral = source._powers.get("feral")
        if feral is not None and combat is not None:
            feral.used_this_turn = getattr(combat, "zero_cost_attacks_this_turn", 0)


class FightThrough(_Block):
    """돌파 — 13블록(업글 17) + Wound 2장 버림 더미 생성."""
    card_id = "fight_through"
    name = "Fight Through"
    rarity = Rarity.UNCOMMON
    cost = 1
    blk, blk_up = 13, 17

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is not None:
            combat.generate_card("wound", count=2)


class Ftl(_Attack):
    """초광속 — 0코스트 5딜(업글 6); 이번 턴 플레이한 카드가 3장(업글 4장)
    미만이면 드로우 1."""
    card_id = "ftl"
    name = "FTL"
    rarity = Rarity.UNCOMMON
    cost = 0
    dmg, dmg_up = 5, 6

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is None:
            return
        play_max = 4 if self.upgraded else 3
        # 원본 CardPlaysFinished — 이 카드 이전에 완료된 플레이 수
        if combat.cards_played_this_turn - 1 < play_max:
            combat.draw_cards(1)


class Fusion(STS2Card):
    """융합 — 플라즈마 채널. 소모 (업글 시 소모 제거)."""
    card_id = "fusion"
    name = "Fusion"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.exhausts = False

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import PlasmaOrb
        _channel(source, combat, PlasmaOrb)


class Glacier(_Block):
    """빙하 — 6블록(업글 9) + 서리 2개 채널."""
    card_id = "glacier"
    name = "Glacier"
    rarity = Rarity.UNCOMMON
    cost = 2
    blk, blk_up = 6, 9

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import FrostOrb
        super().use(source, targets, combat)
        _channel(source, combat, FrostOrb, 2)


class Glasswork(_Block):
    """유리 세공 — 5블록(업글 8) + 유리 채널."""
    card_id = "glasswork"
    name = "Glasswork"
    rarity = Rarity.UNCOMMON
    cost = 1
    blk, blk_up = 5, 8

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import GlassOrb
        super().use(source, targets, combat)
        _channel(source, combat, GlassOrb)


class HailstormCard(STS2Card):
    """우박 폭풍 — 파워: 턴 종료 시 서리 오브 보유 중이면 전체 6딜 (업글 8)."""
    card_id = "hailstorm"
    name = "Hailstorm"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Hailstorm
        source.apply_power(Hailstorm(8 if self.upgraded else 6))


class IterationCard(STS2Card):
    """반복 — 파워: 매 턴 첫 상태이상 드로우 시 카드 2장(업글 3장) 드로우."""
    card_id = "iteration"
    name = "Iteration"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Iteration
        source.apply_power(Iteration(3 if self.upgraded else 2))


class LoopCard(STS2Card):
    """루프 — 파워: 턴 시작 시 선두 오브 패시브 1회(업글 2회) 발동."""
    card_id = "loop"
    name = "Loop"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Loop
        source.apply_power(Loop(2 if self.upgraded else 1))


class Null(_Attack):
    """널 — 10딜(업글 13) + 약화 2(업글 3) + 어둠 채널."""
    card_id = "null"
    name = "Null"
    rarity = Rarity.UNCOMMON
    cost = 2
    dmg, dmg_up = 10, 13

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Weak
        from sts2_sim.models.sts2_orb import DarkOrb
        super().use(source, targets, combat)
        for target in targets:
            if _alive(target):
                target.apply_power(Weak(3 if self.upgraded else 2),
                                   applier=source)
        _channel(source, combat, DarkOrb)


class Overclock(STS2Card):
    """오버클럭 — 0코스트, 드로우 2(업글 3) + Burn 1장 버림 더미 생성."""
    card_id = "overclock"
    name = "Overclock"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        if combat is not None:
            combat.draw_cards(3 if self.upgraded else 2)
            combat.generate_card("burn")


class Refract(_Attack):
    """굴절 — 9딜(업글 12)×2 + 유리 2개 채널."""
    card_id = "refract"
    name = "Refract"
    rarity = Rarity.UNCOMMON
    cost = 3
    dmg, dmg_up = 9, 12
    hits = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import GlassOrb
        super().use(source, targets, combat)
        _channel(source, combat, GlassOrb, 2)


class RocketPunch(_Attack):
    """로켓 펀치 — 13딜(업글 14) + 드로우 1(업글 2); 상태이상 카드가 생성되면
    플레이 전까지 비용 0 (AfterCardGeneratedForCombat)."""
    card_id = "rocket_punch"
    name = "Rocket Punch"
    rarity = Rarity.UNCOMMON
    cost = 2
    dmg, dmg_up = 13, 14

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is not None:
            combat.draw_cards(2 if self.upgraded else 1)

    def on_card_generated_combat(self, card, combat) -> None:
        if card.card_type == CardType.STATUS:
            self._free_until_played = True  # EnergyCost.SetUntilPlayed(0)


class Scavenge(STS2Card):
    """폐품 수집 — 손패 1장 소모 [선택→무작위], 다음 턴 에너지 +2(업글 +3)."""
    card_id = "scavenge"
    name = "Scavenge"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import EnergyNextTurn
        if combat is not None and combat.hand:
            card = combat.rng.choice(combat.hand)
            combat.hand.remove(card)
            combat._exhaust_card(card)
        source.apply_power(EnergyNextTurn(3 if self.upgraded else 2))


class Scrape(_Attack):
    """긁어내기 — 7딜(업글 10) + 드로우 4(업글 5), 그중 비용이 0이 아닌
    카드는 버린다."""
    card_id = "scrape"
    name = "Scrape"
    rarity = Rarity.UNCOMMON
    cost = 1
    dmg, dmg_up = 7, 10

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is None:
            return
        before = {id(c) for c in combat.hand}
        combat.draw_cards(5 if self.upgraded else 4)
        drawn = [c for c in combat.hand if id(c) not in before]
        for card in drawn:
            if card.x_cost or combat.get_card_cost(card) != 0:
                combat.discard_card(card)


class ShadowShield(_Block):
    """그림자 방패 — 11블록(업글 15) + 어둠 채널."""
    card_id = "shadow_shield"
    name = "Shadow Shield"
    rarity = Rarity.UNCOMMON
    cost = 2
    blk, blk_up = 11, 15

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import DarkOrb
        super().use(source, targets, combat)
        _channel(source, combat, DarkOrb)


class Skim(STS2Card):
    """훑어보기 — 드로우 3 (업글 4)."""
    card_id = "skim"
    name = "Skim"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat is not None:
            combat.draw_cards(4 if self.upgraded else 3)


class SmokestackCard(STS2Card):
    """굴뚝 — 파워: 상태이상 카드를 생성할 때마다 전체 5딜 (업글 7)."""
    card_id = "smokestack"
    name = "Smokestack"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Smokestack
        source.apply_power(Smokestack(7 if self.upgraded else 5))


class StormCard(STS2Card):
    """폭풍 — 파워: 파워 카드 플레이마다 라이트닝 1개(업글 2개) 채널."""
    card_id = "storm"
    name = "Storm"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Storm
        source.apply_power(Storm(2 if self.upgraded else 1))


class SubroutineCard(_CostDownOnUpgrade, STS2Card):
    """서브루틴 — 파워: 파워 카드 플레이마다 에너지 +1. (업글 0코스트)"""
    card_id = "subroutine"
    name = "Subroutine"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Subroutine
        source.apply_power(Subroutine(1))


class Sunder(_Attack):
    """분열 — 24딜(업글 32); 처치 시 에너지 +3."""
    card_id = "sunder"
    name = "Sunder"
    rarity = Rarity.UNCOMMON
    cost = 3
    dmg, dmg_up = 24, 32

    def use(self, source, targets, combat=None) -> None:
        for target in targets:
            if _alive(target):
                result = _deal_attack(source, target, self._damage())
                if result.get("killed"):
                    source.gain_energy(3)


class Synchronize(STS2Card):
    """동기화 — 보유 오브 종류 수 × 2만큼 이번 턴 집중 획득.
    소모 (업글 시 소모 제거)."""
    card_id = "synchronize"
    name = "Synchronize"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.exhausts = False

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import TempFocus
        amount = 2 * _orb_kinds(source)
        if amount > 0:
            source.apply_power(TempFocus(amount))


class Synthesis(_Attack):
    """합성 — 14딜(업글 20) + 다음 파워 카드 비용 0 (FreePowerPower)."""
    card_id = "synthesis"
    name = "Synthesis"
    rarity = Rarity.UNCOMMON
    cost = 2
    dmg, dmg_up = 14, 20

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import FreePower
        super().use(source, targets, combat)
        source.apply_power(FreePower(1))


class Tempest(STS2Card):
    """폭풍우 — X코스트: 라이트닝 X개(업글 X+1) 채널."""
    card_id = "tempest"
    name = "Tempest"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0
    x_cost = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import LightningOrb
        count = self.x_value + (1 if self.upgraded else 0)
        _channel(source, combat, LightningOrb, count)


class TeslaCoil(_Attack):
    """테슬라 코일 — 0코스트 3딜(업글 4) + 모든 라이트닝 오브의 패시브를
    대상에게 발동 (업글 시 2회)."""
    card_id = "tesla_coil"
    name = "Tesla Coil"
    rarity = Rarity.UNCOMMON
    cost = 0
    dmg, dmg_up = 3, 4

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        queue = _queue(source)
        if queue is None or not targets:
            return
        target = targets[0]
        for orb in [o for o in queue.orbs if o.orb_id == "lightning"]:
            orb.passive(combat, target)
            if self.upgraded:
                orb.passive(combat, target)


class ThunderCard(STS2Card):
    """천둥 — 파워: 라이트닝 이보크마다 대상에게 6딜(업글 8) 추가."""
    card_id = "thunder"
    name = "Thunder"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Thunder
        source.apply_power(Thunder(8 if self.upgraded else 6))


class WhiteNoise(_CostDownOnUpgrade, STS2Card):
    """백색 소음 — 무작위 파워 카드 1장을 손패에 생성 (이번 턴 비용 0).
    소모. (업글 0코스트)"""
    card_id = "white_noise"
    name = "White Noise"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        made = combat.generate_card(combat.rng.choice(DEFECT_POWER_CARD_IDS),
                                    to="hand")
        for card in made:
            card._free_this_turn = True  # SetToFreeThisTurn


# ══════════════════════════════════════════
# Rare (25)
# ══════════════════════════════════════════

class AdaptiveStrike(_Attack):
    """적응 타격 — 18딜(업글 23) + 이번 전투 비용 0인 사본을 버림 더미에 추가."""
    card_id = "adaptive_strike"
    name = "Adaptive Strike"
    rarity = Rarity.RARE
    cost = 2
    dmg, dmg_up = 18, 23
    tags = frozenset({"strike"})

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is not None:
            made = combat.generate_card(self.card_id, upgraded=self.upgraded)
            for clone in made:
                clone._cost_this_combat = 0  # EnergyCost.SetThisCombat(0)


class AllForOne(_Attack):
    """하나를 위한 전부 — 10딜(업글 14) + 버림 더미의 0코스트 카드를 전부
    손패로 (X코스트 제외)."""
    card_id = "all_for_one"
    name = "All for One"
    rarity = Rarity.RARE
    cost = 2
    dmg, dmg_up = 10, 14

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is None:
            return
        movable = [c for c in combat.discard_pile
                   if not c.x_cost and combat.get_card_cost(c) == 0
                   and c.card_type in (CardType.ATTACK, CardType.SKILL,
                                       CardType.POWER)]
        for card in movable:
            if len(combat.hand) >= MAX_HAND_SIZE:
                break
            combat.discard_pile.remove(card)
            combat.hand.append(card)


class BufferCard(STS2Card):
    """버퍼 — 파워: 다음 1회(업글 2회)의 HP 손실 무효."""
    card_id = "buffer"
    name = "Buffer"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Buffer
        source.apply_power(Buffer(2 if self.upgraded else 1))


class ConsumingShadowCard(STS2Card):
    """어둠 포식 — 파워: 어둠 2개(업글 3개) 채널 + 턴 종료 시 최신 오브 1회 이보크."""
    card_id = "consuming_shadow"
    name = "Consuming Shadow"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import DarkOrb
        from sts2_sim.models.sts2_power import ConsumingShadow
        _channel(source, combat, DarkOrb, 3 if self.upgraded else 2)
        source.apply_power(ConsumingShadow(1))


class CoolantCard(STS2Card):
    """냉각수 — 파워: 턴 시작마다 (오브 종류 수 × 2(업글 3)) 블록."""
    card_id = "coolant"
    name = "Coolant"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Coolant
        source.apply_power(Coolant(3 if self.upgraded else 2))


class CreativeAi(STS2Card):
    """창의적 AI — 파워: 매 턴 무작위 파워 카드 1장을 손패에 생성. (업글 2코스트)"""
    card_id = "creative_ai"
    name = "Creative AI"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 3

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import CreativeAI
        source.apply_power(CreativeAI(1))


class Defragment(STS2Card):
    """조각 모음 — 파워: 집중 +1 (업글 +2)."""
    card_id = "defragment"
    name = "Defragment"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Focus
        source.apply_power(Focus(2 if self.upgraded else 1))


class EchoFormCard(STS2Card):
    """메아리 형상 — 파워: 매 턴 첫 카드를 2회 발동. 에테리얼 (업글 시 제거)."""
    card_id = "echo_form"
    name = "Echo Form"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 3

    def __init__(self):
        super().__init__()
        self.is_ethereal = True

    def upgrade(self) -> None:
        super().upgrade()
        self.is_ethereal = False

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import EchoForm
        source.apply_power(EchoForm(1))


class FlakCannon(_Attack):
    """대공포 — 자신의 상태이상 카드를 전부 소모하고, 그 수만큼 무작위 적에게
    8딜(업글 11)."""
    card_id = "flak_cannon"
    name = "Flak Cannon"
    rarity = Rarity.RARE
    cost = 2
    dmg, dmg_up = 8, 11

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        hits = 0
        for pile in (combat.hand, combat.draw_pile, combat.discard_pile):
            for card in [c for c in pile if c.card_type == CardType.STATUS]:
                pile.remove(card)
                combat._exhaust_card(card)
                hits += 1
        for _ in range(hits):
            alive = [m for m in combat.alive_enemies if _alive(m)]
            if not alive:
                break
            _deal_attack(source, combat.rng.choice(alive), self._damage())

    def damage_estimate(self, player, combat=None, target=None) -> int:
        if combat is None:
            return 0
        statuses = sum(1 for pile in (combat.hand, combat.draw_pile,
                                      combat.discard_pile)
                       for c in pile if c.card_type == CardType.STATUS)
        return self._damage() * statuses


class GeneticAlgorithm(STS2Card):
    """유전 알고리즘 — 1(+누적)블록; 플레이할 때마다 영구히 블록 +3(업글 +4).
    소모. (덱 레벨 영구 성장 — 원본 SavedProperty)"""
    card_id = "genetic_algorithm"
    name = "Genetic Algorithm"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1
    exhausts = True

    def __init__(self):
        super().__init__()
        self.increased_block = 0  # 런 전체 누적 (전투 종료 후에도 유지)

    def _block(self) -> int:
        return 1 + self.increased_block

    def use(self, source, targets, combat=None) -> None:
        source.gain_block(self._block())
        self.increased_block += 4 if self.upgraded else 3

    def block_estimate(self, player, combat=None) -> int:
        return self._block()


class HelixDrill(_Attack):
    """나선 드릴 — 0코스트, 이번 턴 소비한 에너지 1당 3딜(업글 5)."""
    card_id = "helix_drill"
    name = "Helix Drill"
    rarity = Rarity.RARE
    cost = 0
    dmg, dmg_up = 3, 5

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        # 원본: 이번 턴 소비 에너지 합 − 이 카드 자신의 비용
        hits = max(0, combat.energy_spent_this_turn - self._last_paid)
        for _ in range(hits):
            for target in targets:
                if _alive(target):
                    _deal_attack(source, target, self._damage())

    def damage_estimate(self, player, combat=None, target=None) -> int:
        spent = getattr(combat, "energy_spent_this_turn", 0) if combat else 0
        return self._damage() * spent


class Hyperbeam(_Attack):
    """하이퍼빔 — 전체 28딜(업글 36); 집중 -3."""
    card_id = "hyperbeam"
    name = "Hyperbeam"
    rarity = Rarity.RARE
    cost = 2
    dmg, dmg_up = 28, 36
    target_all = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Focus
        super().use(source, targets, combat)
        source.apply_power(Focus(-3))


class IceLance(_Attack):
    """얼음 창 — 19딜(업글 24) + 서리 3개 채널."""
    card_id = "ice_lance"
    name = "Ice Lance"
    rarity = Rarity.RARE
    cost = 3
    dmg, dmg_up = 19, 24

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import FrostOrb
        super().use(source, targets, combat)
        _channel(source, combat, FrostOrb, 3)


class MachineLearningCard(STS2Card):
    """기계 학습 — 파워: 매 턴 드로우 +1. (업글 선천성)"""
    card_id = "machine_learning"
    name = "Machine Learning"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def upgrade(self) -> None:
        super().upgrade()
        self.is_innate = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import MachineLearning
        source.apply_power(MachineLearning(1))


class MeteorStrike(_Attack):
    """메테오 스트라이크 — 5코스트 24딜(업글 30) + 플라즈마 3개 채널."""
    card_id = "meteor_strike"
    name = "Meteor Strike"
    rarity = Rarity.RARE
    cost = 5
    dmg, dmg_up = 24, 30
    tags = frozenset({"strike"})

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import PlasmaOrb
        super().use(source, targets, combat)
        _channel(source, combat, PlasmaOrb, 3)


class Modded(STS2Card):
    """개조 — 0코스트: 오브 슬롯 +1, 드로우 1(업글 2); 플레이마다 이번 전투
    비용 +1 (AddThisCombat)."""
    card_id = "modded"
    name = "Modded"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        queue = _queue(source)
        if queue is not None:
            queue.gain_slots(1)
        if combat is not None:
            combat.draw_cards(2 if self.upgraded else 1)
        self._cost_add_this_combat += 1


class MultiCast(STS2Card):
    """멀티캐스트 — X코스트: 선두 오브를 X회(업글 X+1회) 이보크
    (마지막에만 제거)."""
    card_id = "multi_cast"
    name = "Multi-Cast"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 0
    x_cost = True

    def use(self, source, targets, combat=None) -> None:
        queue = _queue(source)
        if queue is None:
            return
        evokes = self.x_value + (1 if self.upgraded else 0)
        for i in range(evokes):
            if not queue.orbs:
                break
            queue.evoke_next(combat, dequeue=(i == evokes - 1))


class Rainbow(STS2Card):
    """무지개 — 라이트닝/서리/어둠 각 1개 채널. 소모 (업글 시 소모 제거)."""
    card_id = "rainbow"
    name = "Rainbow"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 2
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.exhausts = False

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import LightningOrb, FrostOrb, DarkOrb
        _channel(source, combat, LightningOrb)
        _channel(source, combat, FrostOrb)
        _channel(source, combat, DarkOrb)


class Reboot(STS2Card):
    """재부팅 — 0코스트: 손패 전체를 드로우 더미에 섞고 4장(업글 6장) 드로우.
    소모."""
    card_id = "reboot"
    name = "Reboot"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 0
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        combat.draw_pile.extend(combat.hand)
        combat.hand = []
        combat.rng.shuffle(combat.draw_pile)
        combat.draw_cards(6 if self.upgraded else 4)


class Shatter(_Attack):
    """산산조각 — 전체 7딜(업글 11); 모든 오브를 각각 2회 이보크 후 제거. 소모."""
    card_id = "shatter"
    name = "Shatter"
    rarity = Rarity.RARE
    cost = 1
    dmg, dmg_up = 7, 11
    target_all = True
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        queue = _queue(source)
        if queue is None:
            return
        orb_count = len(queue.orbs)
        for _ in range(orb_count):
            queue.evoke_next(combat, dequeue=False)
            queue.evoke_next(combat, dequeue=True)


class SignalBoostCard(_CostDownOnUpgrade, STS2Card):
    """신호 증폭 — 다음 파워 카드를 2회 발동. 소모. (업글 0코스트)"""
    card_id = "signal_boost"
    name = "Signal Boost"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import SignalBoost
        source.apply_power(SignalBoost(1))


class SpinnerCard(STS2Card):
    """물레 — 파워: 턴 시작마다 유리 1개 채널. (업글 시 즉시 유리 1개 채널)"""
    card_id = "spinner"
    name = "Spinner"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Spinner
        from sts2_sim.models.sts2_orb import GlassOrb
        if self.upgraded:
            _channel(source, combat, GlassOrb)
        source.apply_power(Spinner(1))


class Supercritical(STS2Card):
    """초임계 — 0코스트: 에너지 +4 (업글 +6). 소모."""
    card_id = "supercritical"
    name = "Supercritical"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 0
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        source.gain_energy(6 if self.upgraded else 4)


class TrashToTreasureCard(STS2Card):
    """쓰레기를 보물로 — 파워: 상태이상 카드를 생성할 때마다 무작위 오브 1개 채널.
    (업글 선천성)"""
    card_id = "trash_to_treasure"
    name = "Trash to Treasure"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def upgrade(self) -> None:
        super().upgrade()
        self.is_innate = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import TrashToTreasure
        source.apply_power(TrashToTreasure(1))


class Voltaic(STS2Card):
    """볼타 전지 — 이번 전투에 채널한 라이트닝 수만큼 라이트닝 채널.
    소모 (업글 시 소모 제거)."""
    card_id = "voltaic"
    name = "Voltaic"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 3
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.exhausts = False

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import LightningOrb
        if combat is None:
            return
        count = combat.lightning_channeled_this_combat  # 채널 전 스냅샷
        _channel(source, combat, LightningOrb, count)


# ══════════════════════════════════════════
# Ancient (2) — 일반 보상 풀 제외
# ══════════════════════════════════════════

class BiasedCognition(STS2Card):
    """편향된 인지 — 파워: 집중 +4(업글 +5); 매 턴 시작 집중 -1."""
    card_id = "biased_cognition"
    name = "Biased Cognition"
    card_type = CardType.POWER
    rarity = Rarity.ANCIENT
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Focus, BiasedCognition as BC
        source.apply_power(Focus(5 if self.upgraded else 4))
        source.apply_power(BC(1))


class Quadcast(_CostDownOnUpgrade, STS2Card):
    """쿼드캐스트 — 선두 오브를 4회 이보크 (마지막에만 제거). (업글 0코스트)"""
    card_id = "quadcast"
    name = "Quadcast"
    card_type = CardType.SKILL
    rarity = Rarity.ANCIENT
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        queue = _queue(source)
        if queue is None or not queue.orbs:
            return
        for i in range(4):
            if not queue.orbs:
                break
            queue.evoke_next(combat, dequeue=(i == 3))


# ══════════════════════════════════════════
# 토큰
# ══════════════════════════════════════════

class Fuel(STS2Card):
    """연료 — 0코스트: 에너지 +1 (업글 +2). 소모. (Compact 변환물)"""
    card_id = "fuel"
    name = "Fuel"
    card_type = CardType.SKILL
    rarity = Rarity.TOKEN
    cost = 0
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        source.gain_energy(2 if self.upgraded else 1)


# ══════════════════════════════════════════
# 등록 & 풀 정의
# ══════════════════════════════════════════

_DEFECT_CARDS = [
    # Common (20)
    BallLightning, Barrage, BeamCell, BoostAway, ChargeBattery, Claw, ColdSnap,
    CompileDriver, Coolheaded, FocusedStrike, GoForTheEyes, GunkUp, Hologram,
    Hotfix, Leap, LightningRodCard, MomentumStrike, SweepingBeam, Turbo, Uproar,
    # Uncommon (35)
    BootSequence, BulkUp, Capacitor, Chaos, Chill, Compact, Darkness,
    DoubleEnergy, FeralCard, FightThrough, Ftl, Fusion, Glacier, Glasswork,
    HailstormCard, IterationCard, LoopCard, Null, Overclock, Refract,
    RocketPunch, Scavenge, Scrape, ShadowShield, Skim, SmokestackCard,
    StormCard, SubroutineCard, Sunder, Synchronize, Synthesis, Tempest,
    TeslaCoil, ThunderCard, WhiteNoise,
    # Rare (25)
    AdaptiveStrike, AllForOne, BufferCard, ConsumingShadowCard, CoolantCard,
    CreativeAi, Defragment, EchoFormCard, FlakCannon, GeneticAlgorithm,
    HelixDrill, Hyperbeam, IceLance, MachineLearningCard, MeteorStrike, Modded,
    MultiCast, Rainbow, Reboot, Shatter, SignalBoostCard, SpinnerCard,
    Supercritical, TrashToTreasureCard, Voltaic,
    # Ancient (2)
    BiasedCognition, Quadcast,
    # Token
    Fuel,
]

CARD_REGISTRY.update({cls.card_id: cls for cls in _DEFECT_CARDS})

# WhiteNoise/CreativeAI가 뽑는 파워 카드 풀 (원본: CardPool에서 Type==Power)
DEFECT_POWER_CARD_IDS = sorted(
    cls.card_id for cls in _DEFECT_CARDS if cls.card_type == CardType.POWER)

# 보상 풀: Ancient/Token 제외
DEFECT_POOL_BY_RARITY = {
    Rarity.COMMON: sorted(
        [c.card_id for c in _DEFECT_CARDS if c.rarity == Rarity.COMMON]),
    Rarity.UNCOMMON: sorted(
        [c.card_id for c in _DEFECT_CARDS if c.rarity == Rarity.UNCOMMON]),
    Rarity.RARE: sorted(
        [c.card_id for c in _DEFECT_CARDS if c.rarity == Rarity.RARE]),
}
