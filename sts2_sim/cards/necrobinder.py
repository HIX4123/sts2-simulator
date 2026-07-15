"""
Necrobinder 카드 풀 — 디컴파일 MegaCrit.Sts2.Core.Models.CardPools.NecrobinderCardPool 이식.

원본 91종 중:
  - StrikeNecrobinder/DefendNecrobinder(스타터), Bodyguard/Unleash(Basic, 스타터 덱)는
    models/sts2_card.py에 기존 구현
  - 멀티플레이 전용 5종 제외: Cacophony, GlimpseBeyond, LegionOfBone, Soulbound, Underworld
  - 나머지 82종 + Soul/SweepingGaze 토큰을 여기서 구현

모든 수치는 디컴파일 .cs의 CanonicalVars/OnUpgrade 그대로.
카드 선택 UI가 필요한 효과는 무작위 선택으로 대체하고 주석에 [선택→무작위] 표기.

Osty(소환수) 메커니즘:
  - Summon(n): Osty 생존 시 최대HP +n, 사망 시 부활, 부재 시 생성
  - Osty 공격(CardTag.OstyAttack): Osty가 데미지 딜러 — Osty 부재 시 무효
    (Calcify/ReaperForm/SicEm 훅은 sts2_card._deal_attack에서 처리)
  - Doom: HP ≤ Doom 수치이면 적 턴 종료 시 즉사
  - Soul: 0코스트 토큰 — 2장(업글 3) 드로우, 소모
"""
from __future__ import annotations

from sts2_sim.models.sts2_card import (
    STS2Card, CardType, Rarity, CARD_REGISTRY, _deal_attack, create_card,
)
from sts2_sim.cards.ironclad import _Attack, _Block, _CostDownOnUpgrade, _alive

MAX_HAND_SIZE = 10  # CardPile.MaxCardsInHand


# ══════════════════════════════════════════
# Osty / Soul 공용 헬퍼
# ══════════════════════════════════════════

def _osty_alive(player) -> bool:
    osty = getattr(player, "osty", None)
    return osty is not None and osty.is_alive


def _osty_attack(player, targets, base: int, combat) -> None:
    """Osty가 대상들을 공격 (Osty 부재 시 무효). osty_attacks_this_turn 1 증가.
    Calcify/Lethality/ReaperForm/SicEm 훅은 _deal_attack(osty, ...)에서 처리."""
    osty = getattr(player, "osty", None)
    if osty is None or osty.is_dead:
        return
    for t in targets:
        if _alive(t):
            _deal_attack(osty, t, base)
    if combat is not None:
        combat.osty_attacks_this_turn += 1


def _make_soul(upgraded: bool = False) -> "STS2Card":
    s = create_card("soul")
    if upgraded and s is not None:
        s.upgrade()
    return s


def _souls_to_draw(combat, count: int, upgraded: bool = False) -> None:
    """Soul을 뽑을 더미의 무작위 위치에 추가 (원본 CardPilePosition.Random)."""
    for _ in range(count):
        s = _make_soul(upgraded)
        if s is not None:
            idx = combat.rng.randint(0, len(combat.draw_pile))
            combat.draw_pile.insert(idx, s)


def _count_osty_attack_cards(combat, exclude) -> int:
    """전투 내 모든 더미의 OstyAttack 태그 카드 수 (자신 제외)."""
    piles = combat.hand + combat.draw_pile + combat.discard_pile + combat.exhaust_pile
    return sum(1 for c in piles
               if c is not exclude and getattr(c, "is_osty_attack", False))


class _EtherealCard:
    """Ethereal 키워드를 상시 보유하는 카드용 믹스인 (턴 종료 시 손에 있으면 소모)."""

    def __init__(self):
        super().__init__()
        self.is_ethereal = True


class _OstyAttack(STS2Card):
    """단순 Osty 단일 공격 베이스 (Osty 부재 시 무효)."""
    card_type = CardType.ATTACK
    is_osty_attack = True
    dmg = 0
    dmg_up = 0

    def _damage(self) -> int:
        return self.dmg_up if self.upgraded else self.dmg

    def use(self, source, targets, combat=None) -> None:
        _osty_attack(source, targets, self._damage(), combat)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage() if _osty_alive(player) else 0


# ══════════════════════════════════════════
# 토큰
# ══════════════════════════════════════════

class Soul(STS2Card):
    """소울 — 0코스트 토큰: 2장 드로우(업글 3), 소모."""
    card_id = "soul"
    name = "Soul"
    card_type = CardType.SKILL
    rarity = Rarity.TOKEN
    cost = 0
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat is not None:
            combat.draw_cards(3 if self.upgraded else 2)


class SweepingGaze(STS2Card):
    """휩쓰는 시선 — 0코스트 Osty 토큰: 무작위 적에게 10 공격(업글 15), Ethereal+Exhaust."""
    card_id = "sweeping_gaze"
    name = "Sweeping Gaze"
    card_type = CardType.ATTACK
    rarity = Rarity.TOKEN
    cost = 0
    exhausts = True
    is_osty_attack = True

    def __init__(self):
        super().__init__()
        self.is_ethereal = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None or not _osty_alive(source):
            return
        enemies = combat.alive_enemies
        if enemies:
            dmg = 15 if self.upgraded else 10
            _osty_attack(source, [combat.rng.choice(enemies)], dmg, combat)


# ══════════════════════════════════════════
# Common (20)
# ══════════════════════════════════════════

class Afterlife(STS2Card):
    """사후세계 — Osty 6 소환(업글 8... 9), 소모."""
    card_id = "afterlife"
    name = "Afterlife"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 1
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        source.summon_osty(9 if self.upgraded else 6)


class BlightStrike(STS2Card):
    """역병 일격 — 8딜(업글 10), 입힌 피해만큼 대상에게 Doom 부여. (strike 태그)"""
    card_id = "blight_strike"
    name = "Blight Strike"
    card_type = CardType.ATTACK
    rarity = Rarity.COMMON
    cost = 1
    tags = frozenset({"strike"})

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Doom
        dmg = 10 if self.upgraded else 8
        for target in targets:
            if _alive(target):
                result = _deal_attack(source, target, dmg)
                dealt = result.get("damage", 0)
                if dealt > 0 and not target.is_dead:
                    target.apply_power(Doom(dealt), applier=source)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return 10 if self.upgraded else 8


class Defile(_EtherealCard, _Attack):
    """더럽히기 — 13딜(업글 17), Ethereal."""
    card_id = "defile"
    name = "Defile"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 13, 17


class Defy(_EtherealCard, STS2Card):
    """반항 — 6블록(업글 9) + 대상에게 약화 1, Ethereal. (대상 지정 스킬)"""
    card_id = "defy"
    name = "Defy"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 1
    needs_target = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Weak
        source.gain_block(9 if self.upgraded else 6)
        for target in targets:
            if _alive(target):
                target.apply_power(Weak(1), applier=source)

    def block_estimate(self, player, combat=None) -> int:
        return 9 if self.upgraded else 6


class DrainPower(STS2Card):
    """힘 흡수 — 10딜(업글 12) + 버림 더미의 강화 가능 카드 2장(업글 3) 무작위 강화."""
    card_id = "drain_power"
    name = "Drain Power"
    card_type = CardType.ATTACK
    rarity = Rarity.COMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        dmg = 12 if self.upgraded else 10
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, dmg)
        if combat is None:
            return
        n = 3 if self.upgraded else 2
        for _ in range(n):
            upgradable = [c for c in combat.discard_pile if not c.upgraded]
            if not upgradable:
                break
            combat.rng.choice(upgradable).upgrade()

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return 12 if self.upgraded else 10


class Fear(_EtherealCard, STS2Card):
    """공포 — 7딜(업글 8) + 취약 1(업글 2), Ethereal."""
    card_id = "fear"
    name = "Fear"
    card_type = CardType.ATTACK
    rarity = Rarity.COMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Vulnerable
        dmg = 8 if self.upgraded else 7
        vuln = 2 if self.upgraded else 1
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, dmg)
                if not target.is_dead:
                    target.apply_power(Vulnerable(vuln), applier=source)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return 8 if self.upgraded else 7


class Flatten(_OstyAttack):
    """짓밟기 — Osty 12딜(업글 16). 이번 턴 Osty가 공격했으면 0코스트."""
    card_id = "flatten"
    name = "Flatten"
    rarity = Rarity.COMMON
    cost = 2
    dmg, dmg_up = 12, 16

    def dynamic_cost(self, combat) -> int:
        if combat is not None and combat.osty_attacks_this_turn > 0:
            return 0
        return self.cost


class GraveWarden(_Block):
    """무덤지기 — 8블록(업글 11) + Soul 1장을 뽑을 더미에 추가."""
    card_id = "grave_warden"
    name = "Grave Warden"
    rarity = Rarity.COMMON
    cost = 1
    blk, blk_up = 8, 11

    def use(self, source, targets, combat=None) -> None:
        source.gain_block(self._block())
        if combat is not None:
            _souls_to_draw(combat, 1)


class Graveblast(STS2Card):
    """무덤폭발 — 4딜(업글 6), 버림 더미에서 1장 손패로 회수[선택→무작위]. 소모(업글 소모 제거)."""
    card_id = "graveblast"
    name = "Graveblast"
    card_type = CardType.ATTACK
    rarity = Rarity.COMMON
    cost = 1
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        dmg = 6 if self.upgraded else 4
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, dmg)
        if combat is not None and combat.discard_pile and len(combat.hand) < MAX_HAND_SIZE:
            c = combat.rng.choice(combat.discard_pile)
            combat.discard_pile.remove(c)
            combat.hand.append(c)

    def upgrade(self) -> None:
        super().upgrade()
        self.exhausts = False

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return 6 if self.upgraded else 4


class Invoke(STS2Card):
    """소환술 — 다음 턴 시작 시 Osty 2 소환(업글 3) + 다음 턴 에너지 2(업글 3)."""
    card_id = "invoke"
    name = "Invoke"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import SummonNextTurn, EnergyNextTurn
        n = 3 if self.upgraded else 2
        source.apply_power(SummonNextTurn(n))
        source.apply_power(EnergyNextTurn(n))


class NegativePulse(STS2Card):
    """음의 파동 — 5블록(업글 6) + 모든 적에게 Doom 7(업글 11)."""
    card_id = "negative_pulse"
    name = "Negative Pulse"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Doom
        source.gain_block(6 if self.upgraded else 5)
        doom = 11 if self.upgraded else 7
        if combat is not None:
            for enemy in list(combat.alive_enemies):
                enemy.apply_power(Doom(doom), applier=source)

    def block_estimate(self, player, combat=None) -> int:
        return 6 if self.upgraded else 5


class Poke(_OstyAttack):
    """찌르기 — 0코스트 Osty 6딜(업글 9)."""
    card_id = "poke"
    name = "Poke"
    rarity = Rarity.COMMON
    cost = 0
    dmg, dmg_up = 6, 9


class PullAggro(STS2Card):
    """어그로 끌기 — Osty 4 소환(업글 5) + 7블록(업글 9)."""
    card_id = "pull_aggro"
    name = "Pull Aggro"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        source.summon_osty(5 if self.upgraded else 4)
        source.gain_block(9 if self.upgraded else 7)

    def block_estimate(self, player, combat=None) -> int:
        return 9 if self.upgraded else 7


class Reap(_Attack):
    """수확 — 27딜(업글 33), Retain."""
    card_id = "reap"
    name = "Reap"
    rarity = Rarity.COMMON
    cost = 3
    dmg, dmg_up = 27, 33
    retains = True


class Reave(STS2Card):
    """약탈 — 10딜(업글 13) + Soul 1장을 뽑을 더미에(업글 강화 Soul)."""
    card_id = "reave"
    name = "Reave"
    card_type = CardType.ATTACK
    rarity = Rarity.COMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        dmg = 13 if self.upgraded else 10
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, dmg)
        if combat is not None:
            _souls_to_draw(combat, 1, upgraded=self.upgraded)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return 13 if self.upgraded else 10


class Scourge(STS2Card):
    """재앙 — 대상에게 Doom 13(업글 16) + 1장 드로우(업글 2). (대상 지정 스킬)"""
    card_id = "scourge"
    name = "Scourge"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 1
    needs_target = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Doom
        doom = 16 if self.upgraded else 13
        for target in targets:
            if _alive(target):
                target.apply_power(Doom(doom), applier=source)
        if combat is not None:
            combat.draw_cards(2 if self.upgraded else 1)


class SculptingStrike(STS2Card):
    """조각 일격 — 9딜(업글 12) + 손패 카드 1장에 Ethereal 부여[선택→무작위]. (strike 태그)"""
    card_id = "sculpting_strike"
    name = "Sculpting Strike"
    card_type = CardType.ATTACK
    rarity = Rarity.COMMON
    cost = 1
    tags = frozenset({"strike"})

    def use(self, source, targets, combat=None) -> None:
        dmg = 12 if self.upgraded else 9
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, dmg)
        if combat is not None:
            options = [c for c in combat.hand if not c.is_ethereal]
            if options:
                combat.rng.choice(options).is_ethereal = True

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return 12 if self.upgraded else 9


class Snap(_OstyAttack):
    """스냅 — Osty 7딜(업글 10) + 손패 카드 1장에 Retain 부여[선택→무작위], Retain."""
    card_id = "snap"
    name = "Snap"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 7, 10
    retains = True

    def use(self, source, targets, combat=None) -> None:
        _osty_attack(source, targets, self._damage(), combat)
        if combat is not None:
            options = [c for c in combat.hand if not c.retains and not c._retain_this_turn]
            if options:
                combat.rng.choice(options).retains = True


class Sow(_Attack):
    """씨뿌리기 — 모든 적에게 8딜(업글 11), Retain."""
    card_id = "sow"
    name = "Sow"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 8, 11
    target_all = True
    retains = True


class Wisp(STS2Card):
    """도깨비불 — 0코스트: 에너지 1 획득, 소모(업글 Retain)."""
    card_id = "wisp"
    name = "Wisp"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 0
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        source.gain_energy(1)

    def upgrade(self) -> None:
        super().upgrade()
        self.retains = True


# ══════════════════════════════════════════
# Uncommon (35)
# ══════════════════════════════════════════

class BoneShards(STS2Card):
    """뼈 파편 — Osty가 모든 적에게 9딜(업글 12) + 9블록(업글 12) + Osty 사망."""
    card_id = "bone_shards"
    name = "Bone Shards"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 1
    target_all = True
    is_osty_attack = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None or not _osty_alive(source):
            return
        amount = 12 if self.upgraded else 9
        _osty_attack(source, list(combat.alive_enemies), amount, combat)
        source.gain_block(amount)
        source.osty.kill()

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return (12 if self.upgraded else 9) if _osty_alive(player) else 0


class BorrowedTime(STS2Card):
    """빌린 시간 — 에너지 4 획득(업글 6) + 이번 턴 모든 카드 코스트 +1."""
    card_id = "borrowed_time"
    name = "Borrowed Time"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import BorrowedTime as BT
        source.gain_energy(6 if self.upgraded else 4)
        source.apply_power(BT(1))


class Bury(_Attack):
    """매장 — 52딜(업글 63)."""
    card_id = "bury"
    name = "Bury"
    rarity = Rarity.UNCOMMON
    cost = 4
    dmg, dmg_up = 52, 63


class Calcify(STS2Card):
    """석회화 — 파워: Osty 파워드 공격 +4(업글 +6)."""
    card_id = "calcify"
    name = "Calcify"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Calcify as CalcifyP
        source.apply_power(CalcifyP(6 if self.upgraded else 4))


class CaptureSpirit(STS2Card):
    """영혼 포획 — 3딜(업글 4, 방어·힘 무시) + Soul 3장(업글 4)을 뽑을 더미에. (대상 지정)"""
    card_id = "capture_spirit"
    name = "Capture Spirit"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    needs_target = True

    def use(self, source, targets, combat=None) -> None:
        dmg = 4 if self.upgraded else 3
        for target in targets:
            if _alive(target):
                target.lose_hp(dmg)  # 원본 Unblockable|Unpowered
        if combat is not None:
            _souls_to_draw(combat, 4 if self.upgraded else 3)


class Cleanse(STS2Card):
    """정화 — Osty 3 소환(업글 5) + 뽑을 더미에서 1장 소모[선택→무작위]."""
    card_id = "cleanse"
    name = "Cleanse"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        source.summon_osty(5 if self.upgraded else 3)
        if combat is not None and combat.draw_pile:
            c = combat.rng.choice(combat.draw_pile)
            combat.draw_pile.remove(c)
            combat._exhaust_card(c)


class Countdown(STS2Card):
    """카운트다운 — 파워: 매 턴 시작 무작위 적에게 Doom 6(업글 9)."""
    card_id = "countdown"
    name = "Countdown"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Countdown as CountdownP
        source.apply_power(CountdownP(9 if self.upgraded else 6))


class DanseMacabre(STS2Card):
    """죽음의 무도 — 파워: 코스트 2 이상 카드를 낼 때마다 4블록(업글 6)."""
    card_id = "danse_macabre"
    name = "Danse Macabre"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import DanseMacabre as DanseP
        source.apply_power(DanseP(6 if self.upgraded else 4))


class DeathMarch(STS2Card):
    """죽음의 행군 — 8딜(업글 9) + 이번 턴 (손패 드로우 제외) 뽑은 카드당 4딜(업글 6)."""
    card_id = "death_march"
    name = "Death March"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        base = 9 if self.upgraded else 8
        per = 6 if self.upgraded else 4
        drawn = combat.cards_drawn_this_turn if combat is not None else 0
        dmg = base + per * drawn
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, dmg)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        base = 9 if self.upgraded else 8
        per = 6 if self.upgraded else 4
        drawn = combat.cards_drawn_this_turn if combat is not None else 0
        return base + per * drawn


class Deathbringer(STS2Card):
    """죽음의 전령 — 모든 적에게 Doom 21(업글 26) + 약화 1."""
    card_id = "deathbringer"
    name = "Deathbringer"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Doom, Weak
        doom = 26 if self.upgraded else 21
        if combat is not None:
            for enemy in list(combat.alive_enemies):
                enemy.apply_power(Doom(doom), applier=source)
                enemy.apply_power(Weak(1), applier=source)


class DeathsDoor(STS2Card):
    """죽음의 문 — 6블록(업글 7). 이번 턴 Doom을 부여했다면 총 3회(=18/21)."""
    card_id = "deaths_door"
    name = "Death's Door"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        blk = 7 if self.upgraded else 6
        times = 3 if (combat is not None and combat.doom_applied_this_turn) else 1
        for _ in range(times):
            source.gain_block(blk)

    def block_estimate(self, player, combat=None) -> int:
        blk = 7 if self.upgraded else 6
        times = 3 if (combat is not None and combat.doom_applied_this_turn) else 1
        return blk * times


class Debilitate(STS2Card):
    """쇠약화 — 10딜(업글 12) + 대상에게 Debilitate 2(업글 3)."""
    card_id = "debilitate"
    name = "Debilitate"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Debilitate as DebP
        dmg = 12 if self.upgraded else 10
        deb = 3 if self.upgraded else 2
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, dmg)
                if not target.is_dead:
                    target.apply_power(DebP(deb), applier=source)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return 12 if self.upgraded else 10


class Delay(STS2Card):
    """지연 — 11블록(업글 13) + 다음 턴 에너지 1(업글 2)."""
    card_id = "delay"
    name = "Delay"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import EnergyNextTurn
        source.gain_block(13 if self.upgraded else 11)
        source.apply_power(EnergyNextTurn(2 if self.upgraded else 1))

    def block_estimate(self, player, combat=None) -> int:
        return 13 if self.upgraded else 11


class Dirge(STS2Card):
    """만가 — X코스트: X회 Osty 3 소환(업글 4) + Soul X장을 뽑을 더미에, 소모."""
    card_id = "dirge"
    name = "Dirge"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0
    x_cost = True
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        x = self.x_value
        amount = 4 if self.upgraded else 3
        for _ in range(x):
            source.summon_osty(amount)
        if combat is not None:
            _souls_to_draw(combat, x, upgraded=self.upgraded)


class Dredge(STS2Card):
    """준설 — 버림 더미에서 최대 3장을 손패로 회수[선택→무작위], 소모(업글 Retain)."""
    card_id = "dredge"
    name = "Dredge"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        n = min(3, MAX_HAND_SIZE - len(combat.hand))
        for _ in range(n):
            if not combat.discard_pile:
                break
            c = combat.rng.choice(combat.discard_pile)
            combat.discard_pile.remove(c)
            combat.hand.append(c)

    def upgrade(self) -> None:
        super().upgrade()
        self.retains = True


class EnfeeblingTouch(_EtherealCard, STS2Card):
    """약화의 손길 — 대상 적이 이번 턴 힘 8 감소(업글 11), Ethereal. (대상 지정)"""
    card_id = "enfeebling_touch"
    name = "Enfeebling Touch"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    needs_target = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import EnfeeblingTouch as ETP
        amount = 11 if self.upgraded else 8
        for target in targets:
            if _alive(target):
                target.apply_power(ETP(amount), applier=source)


class Fetch(_OstyAttack):
    """물어오기 — 0코스트 Osty 3딜(업글 6), 이번 턴 첫 플레이 시 1장 드로우."""
    card_id = "fetch"
    name = "Fetch"
    rarity = Rarity.UNCOMMON
    cost = 0
    dmg, dmg_up = 3, 6

    def use(self, source, targets, combat=None) -> None:
        if not _osty_alive(source):
            return
        _osty_attack(source, targets, self._damage(), combat)
        if combat is not None:
            first = (getattr(self, "_fetch_c", None) is not combat
                     or getattr(self, "_fetch_t", -1) != combat.turn)
            if first:
                self._fetch_c = combat
                self._fetch_t = combat.turn
                combat.draw_cards(1)


class Friendship(STS2Card):
    """우정 — 파워: 힘 2 감소(업글 1 감소) + 최대 에너지 +1."""
    card_id = "friendship"
    name = "Friendship"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Strength, Friendship as FriendP
        loss = 1 if self.upgraded else 2
        source.apply_power(Strength(-loss))
        source.apply_power(FriendP(1))


class Haunt(STS2Card):
    """출몰 — 파워: Soul을 낼 때마다 무작위 적에게 7 관통 피해(업글 9)."""
    card_id = "haunt"
    name = "Haunt"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Haunt as HauntP
        source.apply_power(HauntP(9 if self.upgraded else 7))


class HighFive(STS2Card):
    """하이파이브 — Osty가 모든 적에게 11딜(업글 13) + 취약 2(업글 3). Osty 부재 시 사용 불가."""
    card_id = "high_five"
    name = "High Five"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 2
    target_all = True
    is_osty_attack = True

    def dynamic_playable(self, combat) -> bool:
        return _osty_alive(combat.player)

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Vulnerable
        if combat is None or not _osty_alive(source):
            return
        dmg = 13 if self.upgraded else 11
        vuln = 3 if self.upgraded else 2
        _osty_attack(source, list(combat.alive_enemies), dmg, combat)
        for enemy in list(combat.alive_enemies):
            enemy.apply_power(Vulnerable(vuln), applier=source)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return (13 if self.upgraded else 11) if _osty_alive(player) else 0


class Lethality(_EtherealCard, STS2Card):
    """치명 — 파워: 매 턴 첫 공격 카드 피해 +50%(업글 +75%), Ethereal."""
    card_id = "lethality"
    name = "Lethality"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Lethality as LethP
        source.apply_power(LethP(75 if self.upgraded else 50))


class Melancholy(STS2Card):
    """우울 — 13블록(업글 17). 전투 중 적이 죽을 때마다 이 카드 코스트 -1(영구)."""
    card_id = "melancholy"
    name = "Melancholy"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 3

    def use(self, source, targets, combat=None) -> None:
        source.gain_block(17 if self.upgraded else 13)

    def dynamic_cost(self, combat) -> int:
        deaths = combat.deaths_this_combat if combat is not None else 0
        return max(0, self.cost - deaths)

    def block_estimate(self, player, combat=None) -> int:
        return 17 if self.upgraded else 13


class NoEscape(STS2Card):
    """도피 불가 — 대상에게 Doom 10(업글 15) + 대상의 기존 Doom 10당 추가 5. (대상 지정)"""
    card_id = "no_escape"
    name = "No Escape"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    needs_target = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Doom
        base = 15 if self.upgraded else 10
        for target in targets:
            if _alive(target):
                cur = target.get_power_amount("doom")
                doom = base + 5 * (cur // 10)
                target.apply_power(Doom(doom), applier=source)


class Pagestorm(STS2Card):
    """책장 폭풍 — 파워: Ethereal 카드를 뽑을 때마다 1장 추가 드로우(업글 0코스트)."""
    card_id = "pagestorm"
    name = "Pagestorm"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Pagestorm as PageP
        source.apply_power(PageP(1))

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)


class Parse(_EtherealCard, STS2Card):
    """해석 — 3장 드로우(업글 4), Ethereal."""
    card_id = "parse"
    name = "Parse"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat is not None:
            combat.draw_cards(4 if self.upgraded else 3)


class PullFromBelow(STS2Card):
    """아래에서 끌어올리기 — 이번 전투 앞서 플레이한 Ethereal 카드 수만큼 5딜(업글 7) 연타.
    (원본: 자신은 Ethereal 키워드가 아님 — 히트 수에도 자기 미포함)."""
    card_id = "pull_from_below"
    name = "Pull From Below"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        dmg = 7 if self.upgraded else 5
        hits = combat.ethereal_played_this_combat  # 자신은 Ethereal 아님 → 선행 Ethereal 수만 집계
        for _ in range(hits):
            for target in targets:
                if _alive(target):
                    _deal_attack(source, target, dmg)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        dmg = 7 if self.upgraded else 5
        hits = combat.ethereal_played_this_combat if combat is not None else 0
        return dmg * hits


class Putrefy(STS2Card):
    """부패 — 대상에게 약화 2 + 취약 2(업글 3/3), 소모. (대상 지정)"""
    card_id = "putrefy"
    name = "Putrefy"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    exhausts = True
    needs_target = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Weak, Vulnerable
        amount = 3 if self.upgraded else 2
        for target in targets:
            if _alive(target):
                target.apply_power(Weak(amount), applier=source)
                target.apply_power(Vulnerable(amount), applier=source)


class Rattle(_OstyAttack):
    """딸랑이 — Osty 7딜(업글 9)을 (1 + 이번 턴 Osty 공격 수)회 타격."""
    card_id = "rattle"
    name = "Rattle"
    rarity = Rarity.UNCOMMON
    cost = 1
    dmg, dmg_up = 7, 9

    def use(self, source, targets, combat=None) -> None:
        if not _osty_alive(source):
            return
        hits = 1 + (combat.osty_attacks_this_turn if combat is not None else 0)
        dmg = self._damage()
        for _ in range(hits):
            for target in targets:
                if _alive(target):
                    _deal_attack(source.osty, target, dmg)
        if combat is not None:
            combat.osty_attacks_this_turn += 1

    def damage_estimate(self, player, combat=None, target=None) -> int:
        hits = 1 + (combat.osty_attacks_this_turn if combat is not None else 0)
        return self._damage() * hits if _osty_alive(player) else 0


class RightHandHand(_OstyAttack):
    """오른손잡이 — 0코스트 Osty 4딜(업글 6). 코스트 2 이상 카드를 내면 버림 더미에서 손패로 복귀."""
    card_id = "right_hand_hand"
    name = "Right Hand Hand"
    rarity = Rarity.UNCOMMON
    cost = 0
    dmg, dmg_up = 4, 6

    def on_ally_card_played(self, card, paid, combat) -> None:
        if paid >= 2 and self in combat.discard_pile and len(combat.hand) < MAX_HAND_SIZE:
            combat.discard_pile.remove(self)
            combat.hand.append(self)


class Severance(STS2Card):
    """단절 — 13딜(업글 18) + Soul 3장(뽑을 더미/버림/손패 각 1)."""
    card_id = "severance"
    name = "Severance"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        dmg = 18 if self.upgraded else 13
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, dmg)
        if combat is not None:
            _souls_to_draw(combat, 1)
            combat.discard_pile.append(_make_soul())
            # 원본은 세 번째 Soul을 무조건 손패에 추가(엔진 오버플로 위임).
            # 손패가 가득 차면 소실 대신 버림 더미로(카드 소실 방지).
            if len(combat.hand) < MAX_HAND_SIZE:
                combat.hand.append(_make_soul())
            else:
                combat.discard_pile.append(_make_soul())

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return 18 if self.upgraded else 13


class Shroud(STS2Card):
    """장막 — 파워: Doom을 부여할 때마다 2블록(업글 3)."""
    card_id = "shroud"
    name = "Shroud"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Shroud as ShroudP
        source.apply_power(ShroudP(3 if self.upgraded else 2))


class SicEm(_OstyAttack):
    """공격 명령 — Osty 5딜(업글 6) + 대상에게 SicEm 3(업글 4): Osty가 그 적을 치면 Osty 소환."""
    card_id = "sic_em"
    name = "Sic Em"
    rarity = Rarity.UNCOMMON
    cost = 1
    dmg, dmg_up = 5, 6

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import SicEm as SicEmP
        amount = 4 if self.upgraded else 3
        # 원본 순서: Osty 공격 먼저(이 공격은 아직 파워가 없어 소환 미발동)
        # → 그 다음 SicEm 파워 부여 → 이후 Osty 공격부터 소환 발동
        _osty_attack(source, targets, self._damage(), combat)
        for target in targets:
            if _alive(target):
                target.apply_power(SicEmP(amount), applier=source)


class SleightOfFlesh(STS2Card):
    """육체의 술책 — 파워: 적에게 디버프를 부여할 때마다 그 적에게 9 피해(업글 13)."""
    card_id = "sleight_of_flesh"
    name = "Sleight of Flesh"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import SleightOfFlesh as SoFP
        source.apply_power(SoFP(13 if self.upgraded else 9))


class Spur(STS2Card):
    """박차 — Osty 3 소환(업글 5) + Osty 5 회복(업글 7), Retain."""
    card_id = "spur"
    name = "Spur"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    retains = True

    def use(self, source, targets, combat=None) -> None:
        source.summon_osty(5 if self.upgraded else 3)
        source.heal_osty(7 if self.upgraded else 5)


class Veilpiercer(STS2Card):
    """장막 관통 — 10딜(업글 13) + Veilpiercer 1(다음 Ethereal 카드 0코스트)."""
    card_id = "veilpiercer"
    name = "Veilpiercer"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Veilpiercer as VeilP
        dmg = 13 if self.upgraded else 10
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, dmg)
        source.apply_power(VeilP(1))

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return 13 if self.upgraded else 10


# ══════════════════════════════════════════
# Rare (25)
# ══════════════════════════════════════════

class BansheesCry(STS2Card):
    """밴시의 비명 — 모든 적에게 33딜. 이번 전투 플레이한 Ethereal 카드당 코스트 -2."""
    card_id = "banshees_cry"
    name = "Banshee's Cry"
    card_type = CardType.ATTACK
    rarity = Rarity.RARE
    cost = 9
    target_all = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        for enemy in list(combat.alive_enemies):
            _deal_attack(source, enemy, 33)

    def dynamic_cost(self, combat) -> int:
        eth = combat.ethereal_played_this_combat if combat is not None else 0
        return max(0, self.cost - 2 * eth)

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 2)  # 9 → 7

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return 33


class CallOfTheVoid(STS2Card):
    """공허의 부름 — 파워: 매 턴 무작위 Necrobinder 카드 1장을 Ethereal로 손패에(업글 Innate)."""
    card_id = "call_of_the_void"
    name = "Call of the Void"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import CallOfTheVoid as CotVP
        source.apply_power(CotVP(1))

    def upgrade(self) -> None:
        super().upgrade()
        self.is_innate = True


class Demesne(_EtherealCard, STS2Card):
    """영지 — 파워: 매 턴 드로우 +1, 최대 에너지 +1, Ethereal(업글 2코스트)."""
    card_id = "demesne"
    name = "Demesne"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 3

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Demesne as DemesneP
        source.apply_power(DemesneP(1))

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)


class DevourLife(STS2Card):
    """생명 포식 — 파워: Soul을 낼 때마다 Osty 1 소환(업글 2)."""
    card_id = "devour_life"
    name = "Devour Life"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import DevourLife as DevourP
        source.apply_power(DevourP(2 if self.upgraded else 1))


class Eidolon(STS2Card):
    """환영 — 나머지 손패 전체를 소모. 9장 이상 소모 시 Intangible 1 획득.
    (원본: 카드 자신은 Exhaust 키워드가 아님 — 사용 후 버림 더미로)."""
    card_id = "eidolon"
    name = "Eidolon"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Intangible
        if combat is None:
            return
        n = combat.exhaust_all_hand()
        if n >= 9:
            source.apply_power(Intangible(1))

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)


class EndOfDays(STS2Card):
    """최후의 날 — 모든 적에게 Doom 29(업글 37) + 즉시 Doom 처치."""
    card_id = "end_of_days"
    name = "End of Days"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 3

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Doom
        if combat is None:
            return
        doom = 37 if self.upgraded else 29
        for enemy in list(combat.alive_enemies):
            enemy.apply_power(Doom(doom), applier=source)
        # 즉시 DoomKill
        for enemy in list(combat.alive_enemies):
            d = enemy._powers.get("doom")
            if d is not None and d.is_owner_doomed():
                enemy._current_hp = 0
        combat.reap_deaths()


class Eradicate(STS2Card):
    """근절 — X코스트: 11딜(업글 14)을 X회 타격, Retain."""
    card_id = "eradicate"
    name = "Eradicate"
    card_type = CardType.ATTACK
    rarity = Rarity.RARE
    cost = 0
    x_cost = True
    retains = True

    def use(self, source, targets, combat=None) -> None:
        dmg = 14 if self.upgraded else 11
        for _ in range(self.x_value):
            for target in targets:
                if _alive(target):
                    _deal_attack(source, target, dmg)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return (14 if self.upgraded else 11) * max(1, player.energy)


class Hang(STS2Card):
    """교수형 — 10딜(업글 13). 대상의 Hang 스택만큼 피해 배가 후 Hang max(2,스택) 부여."""
    card_id = "hang"
    name = "Hang"
    card_type = CardType.ATTACK
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Hang as HangP
        base = 13 if self.upgraded else 10
        for target in targets:
            if not _alive(target):
                continue
            stacks = target.get_power_amount("hang")
            mult = stacks if stacks > 0 else 1
            _deal_attack(source, target, base * mult)
            if not target.is_dead:
                target.apply_power(HangP(max(2, stacks)), applier=source)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        base = 13 if self.upgraded else 10
        if target is not None:
            stacks = target.get_power_amount("hang")
            return base * (stacks if stacks > 0 else 1)
        return base


class Misery(STS2Card):
    """비참 — 7딜(업글 9). 대상의 모든 디버프를 다른 모든 적에게 복사(업글 Retain)."""
    card_id = "misery"
    name = "Misery"
    card_type = CardType.ATTACK
    rarity = Rarity.RARE
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import POWER_REGISTRY
        if combat is None or not targets:
            return
        target = targets[0]
        debuffs = [(pid, p.amount) for pid, p in list(target._powers.items())
                   if getattr(p, "is_debuff", False)]
        dmg = 9 if self.upgraded else 7
        if _alive(target):
            _deal_attack(source, target, dmg)
        for enemy in list(combat.alive_enemies):
            if enemy is target:
                continue
            for pid, amt in debuffs:
                cls = POWER_REGISTRY.get(pid)
                if cls is not None and amt != 0:
                    enemy.apply_power(cls(amt), applier=source)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return 9 if self.upgraded else 7


class NecroMastery(STS2Card):
    """강령술 숙련 — Osty 5 소환(업글 8) + 파워: Osty가 HP를 잃으면 그만큼 모든 적에게 반사."""
    card_id = "necro_mastery"
    name = "Necro Mastery"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import NecroMastery as NMP
        source.summon_osty(8 if self.upgraded else 5)
        source.apply_power(NMP(1))


class Neurosurge(STS2Card):
    """신경 급증 — 에너지 3 획득(업글 4) + 2장 드로우 + 파워: 매 턴 자신에게 Doom 3."""
    card_id = "neurosurge"
    name = "Neurosurge"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Neurosurge as NeuroP
        source.gain_energy(4 if self.upgraded else 3)
        if combat is not None:
            combat.draw_cards(2)
        source.apply_power(NeuroP(3))


class Oblivion(STS2Card):
    """망각 — 이번 턴 카드를 낼 때마다 대상에게 Doom 3(업글 4). (대상 지정)"""
    card_id = "oblivion"
    name = "Oblivion"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 0
    needs_target = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Oblivion as OblivionP
        amount = 4 if self.upgraded else 3
        target = targets[0] if targets else None
        if target is not None:
            source.apply_power(OblivionP(amount, target=target, source_card=self))


class Reanimate(STS2Card):
    """소생 — Osty 20 소환(업글 25), 소모."""
    card_id = "reanimate"
    name = "Reanimate"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 3
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        source.summon_osty(25 if self.upgraded else 20)


class ReaperForm(STS2Card):
    """사신의 형상 — 파워: 플레이어/Osty가 준 피해만큼 대상에게 Doom 부여(업글 Retain)."""
    card_id = "reaper_form"
    name = "Reaper Form"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 3

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import ReaperForm as RFP
        source.apply_power(RFP(1))

    def upgrade(self) -> None:
        super().upgrade()
        self.retains = True


class Sacrifice(STS2Card):
    """희생 — Osty를 죽이고 Osty 최대HP의 2배만큼 블록 획득, Retain(업글 0코스트)."""
    card_id = "sacrifice"
    name = "Sacrifice"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1
    retains = True

    def use(self, source, targets, combat=None) -> None:
        osty = getattr(source, "osty", None)
        if osty is None or osty.is_dead:
            return
        block = osty.max_hp * 2
        osty.kill()
        source.gain_block(block)

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)

    def block_estimate(self, player, combat=None) -> int:
        osty = getattr(player, "osty", None)
        return osty.max_hp * 2 if (osty is not None and osty.is_alive) else 0


class Seance(_EtherealCard, STS2Card):
    """강령회 — 뽑을 더미의 카드 1장을 Soul로 변형[선택→무작위], Ethereal(업글 0코스트)."""
    card_id = "seance"
    name = "Seance"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat is not None and combat.draw_pile:
            idx = combat.rng.randrange(len(combat.draw_pile))
            combat.draw_pile[idx] = _make_soul()

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)


class SentryMode(STS2Card):
    """감시 모드 — 파워: 매 턴 SweepingGaze 1장을 손패에(업글 1코스트)."""
    card_id = "sentry_mode"
    name = "Sentry Mode"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import SentryMode as SentryP
        source.apply_power(SentryP(1))

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)


class SharedFate(STS2Card):
    """공유된 운명 — 자신 힘 -2 + 대상 힘 -2(업글 -3), 소모. (대상 지정)"""
    card_id = "shared_fate"
    name = "Shared Fate"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 0
    exhausts = True
    needs_target = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Strength
        source.apply_power(Strength(-2))
        enemy_loss = 3 if self.upgraded else 2
        for target in targets:
            if _alive(target):
                target.apply_power(Strength(-enemy_loss), applier=source)


class SoulStorm(STS2Card):
    """영혼 폭풍 — 9딜 + 소모 더미의 Soul당 4딜(업글 6)."""
    card_id = "soul_storm"
    name = "Soul Storm"
    card_type = CardType.ATTACK
    rarity = Rarity.RARE
    cost = 1

    def _damage(self, combat) -> int:
        souls = sum(1 for c in combat.exhaust_pile if c.card_id == "soul") if combat else 0
        return 9 + (6 if self.upgraded else 4) * souls

    def use(self, source, targets, combat=None) -> None:
        dmg = self._damage(combat)
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, dmg)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage(combat)


class SpiritOfAsh(STS2Card):
    """재의 정령 — 파워: Ethereal 카드를 낼 때마다 4블록(업글 5)."""
    card_id = "spirit_of_ash"
    name = "Spirit of Ash"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import SpiritOfAsh as SoAP
        source.apply_power(SoAP(5 if self.upgraded else 4))


class Squeeze(_OstyAttack):
    """쥐어짜기 — Osty 25딜(업글 30) + (자신 외 OstyAttack 카드당) 5딜(업글 6)."""
    card_id = "squeeze"
    name = "Squeeze"
    rarity = Rarity.RARE
    cost = 3

    def _damage_dyn(self, combat) -> int:
        base = 30 if self.upgraded else 25
        per = 6 if self.upgraded else 5
        count = _count_osty_attack_cards(combat, self) if combat is not None else 0
        return base + per * count

    def use(self, source, targets, combat=None) -> None:
        _osty_attack(source, targets, self._damage_dyn(combat), combat)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage_dyn(combat) if _osty_alive(player) else 0


class TheScythe(STS2Card):
    """대낫 — 13딜(플레이할수록 영구 +4, 업글 +5), 소모."""
    card_id = "the_scythe"
    name = "The Scythe"
    card_type = CardType.ATTACK
    rarity = Rarity.RARE
    cost = 2
    exhausts = True

    def __init__(self):
        super().__init__()
        self._current_damage = 13  # 런 전체 지속 (SavedProperty)

    def _increase(self) -> int:
        return 5 if self.upgraded else 4

    def use(self, source, targets, combat=None) -> None:
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, self._current_damage)
        self._current_damage += self._increase()

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._current_damage


class TimesUp(STS2Card):
    """시간 종료 — 대상의 Doom 수치만큼 피해, 소모(업글 Retain)."""
    card_id = "times_up"
    name = "Time's Up"
    card_type = CardType.ATTACK
    rarity = Rarity.RARE
    cost = 2
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        for target in targets:
            if _alive(target):
                dmg = target.get_power_amount("doom")
                if dmg > 0:
                    _deal_attack(source, target, dmg)

    def upgrade(self) -> None:
        super().upgrade()
        self.retains = True

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return target.get_power_amount("doom") if target is not None else 0


class Transfigure(STS2Card):
    """변형 — 손패 카드 1장에 코스트 +1(이번 전투) 및 재발동 +1 부여[선택→무작위],
    소모(업글 소모 제거)."""
    card_id = "transfigure"
    name = "Transfigure"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None or not combat.hand:
            return
        c = combat.rng.choice(combat.hand)
        if not c.x_cost:
            c._cost_add_this_combat += 1
        c._extra_plays += 1

    def upgrade(self) -> None:
        super().upgrade()
        self.exhausts = False


class Undeath(STS2Card):
    """언데스 — 7블록(업글 9) + 자기 복제본을 버림 더미에 추가(소모 안 됨)."""
    card_id = "undeath"
    name = "Undeath"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        source.gain_block(9 if self.upgraded else 7)
        if combat is not None:
            clone = create_card("undeath")
            if self.upgraded:
                clone.upgrade()
            combat.discard_pile.append(clone)

    def block_estimate(self, player, combat=None) -> int:
        return 9 if self.upgraded else 7


# ══════════════════════════════════════════
# Ancient (2) — 일반 보상 풀 제외
# ══════════════════════════════════════════

class ForbiddenGrimoire(STS2Card):
    """금단의 마도서 — 파워: 전투 종료 시 카드 제거 보상 +1(보상 미모델링), Eternal."""
    card_id = "forbidden_grimoire"
    name = "Forbidden Grimoire"
    card_type = CardType.POWER
    rarity = Rarity.ANCIENT
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import ForbiddenGrimoire as FGP
        source.apply_power(FGP(1))

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)


class Protector(_OstyAttack):
    """수호자 — Osty가 (10 + Osty 최대HP)딜(업글 15 + 최대HP), 업글 0코스트."""
    card_id = "protector"
    name = "Protector"
    rarity = Rarity.ANCIENT
    cost = 1

    def _base(self) -> int:
        return 15 if self.upgraded else 10

    def use(self, source, targets, combat=None) -> None:
        if not _osty_alive(source):
            return
        dmg = self._base() + source.osty.max_hp
        _osty_attack(source, targets, dmg, combat)

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        osty = getattr(player, "osty", None)
        return self._base() + osty.max_hp if (osty is not None and osty.is_alive) else 0


# ══════════════════════════════════════════
# 등록 & 풀 정의
# ══════════════════════════════════════════

_NECROBINDER_CARDS = [
    # Common (20)
    Afterlife, BlightStrike, Defile, Defy, DrainPower, Fear, Flatten, GraveWarden,
    Graveblast, Invoke, NegativePulse, Poke, PullAggro, Reap, Reave, Scourge,
    SculptingStrike, Snap, Sow, Wisp,
    # Uncommon (35)
    BoneShards, BorrowedTime, Bury, Calcify, CaptureSpirit, Cleanse, Countdown,
    DanseMacabre, DeathMarch, Deathbringer, DeathsDoor, Debilitate, Delay, Dirge,
    Dredge, EnfeeblingTouch, Fetch, Friendship, Haunt, HighFive, Lethality,
    Melancholy, NoEscape, Pagestorm, Parse, PullFromBelow, Putrefy, Rattle,
    RightHandHand, Severance, Shroud, SicEm, SleightOfFlesh, Spur, Veilpiercer,
    # Rare (25)
    BansheesCry, CallOfTheVoid, Demesne, DevourLife, Eidolon, EndOfDays, Eradicate,
    Hang, Misery, NecroMastery, Neurosurge, Oblivion, Reanimate, ReaperForm,
    Sacrifice, Seance, SentryMode, SharedFate, SoulStorm, SpiritOfAsh, Squeeze,
    TheScythe, TimesUp, Transfigure, Undeath,
    # Ancient (2)
    ForbiddenGrimoire, Protector,
    # 토큰
    Soul, SweepingGaze,
]

CARD_REGISTRY.update({cls.card_id: cls for cls in _NECROBINDER_CARDS})

# 보상 풀: Ancient/Token 제외
NECROBINDER_POOL_BY_RARITY = {
    Rarity.COMMON: sorted(
        [c.card_id for c in _NECROBINDER_CARDS if c.rarity == Rarity.COMMON]),
    Rarity.UNCOMMON: sorted(
        [c.card_id for c in _NECROBINDER_CARDS if c.rarity == Rarity.UNCOMMON]),
    Rarity.RARE: sorted(
        [c.card_id for c in _NECROBINDER_CARDS if c.rarity == Rarity.RARE]),
}

# CallOfTheVoid가 뽑는 카드 풀 (원본: 비-Basic/Ancient 잠금 해제 카드)
NECROBINDER_ETHEREAL_POOL = (
    NECROBINDER_POOL_BY_RARITY[Rarity.COMMON]
    + NECROBINDER_POOL_BY_RARITY[Rarity.UNCOMMON]
    + NECROBINDER_POOL_BY_RARITY[Rarity.RARE]
)
