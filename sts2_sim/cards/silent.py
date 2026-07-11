"""
Silent 카드 풀 — 디컴파일 MegaCrit.Sts2.Core.Models.CardPools.SilentCardPool 이식.

원본 91종 중:
  - StrikeSilent/DefendSilent/Neutralize/Survivor 4종(Basic)과 Acrobatics/Deflect는
    models/sts2_card.py에 기존 구현
  - 멀티플레이 전용 5종 제외: BladeSymphony, Concoct, Fade, Flanking, Sneaky
  - 나머지 80종을 여기서 구현 (Shiv 토큰은 models/sts2_card.py에서 확장)

모든 수치는 디컴파일 .cs의 CanonicalVars/OnUpgrade 그대로.
원본이 카드 선택 UI를 요구하는 곳(DaggerThrow/Prepared/HandTrick/Nightmare/
WellLaidPlans/ToolsOfTheTrade)은 무작위 선택으로 대체하고 [선택→무작위] 표기.
"""
from __future__ import annotations

from sts2_sim.models.sts2_card import (
    STS2Card, CardType, Rarity, CARD_REGISTRY, _deal_attack,
)
from sts2_sim.cards.ironclad import _Attack, _Block, _CostDownOnUpgrade, _alive
from sts2_sim.models.sts2_power import (
    Poison, Weak, Vulnerable, Dexterity, Thorns, TempStrength, TempDexterity,
    NoDraw, Strength,
    Accelerant as AccelerantPower, Accuracy as AccuracyPower,
    Afterimage as AfterimagePower, Blur as BlurPower, Burst as BurstPower,
    CorrosiveWave as CorrosiveWavePower, Envenom as EnvenomPower,
    FanOfKnives as FanOfKnivesPower, InfiniteBlades as InfiniteBladesPower,
    MasterPlanner as MasterPlannerPower, Nightmare as NightmarePower,
    NoxiousFumes as NoxiousFumesPower, Outbreak as OutbreakPower,
    PhantomBlades as PhantomBladesPower, SerpentForm as SerpentFormPower,
    ShadowStep as ShadowStepPower, Shadowmeld as ShadowmeldPower,
    Speedster as SpeedsterPower, Strangle as StranglePower,
    TheHunt as TheHuntPower, ToolsOfTheTrade as ToolsOfTheTradePower,
    Tracking as TrackingPower, WellLaidPlans as WellLaidPlansPower,
    WraithFormPower, Intangible, BlockNextTurn, DrawCardsNextTurn, FreeSkill,
)


class _PoisonSkill(STS2Card):
    """단일 대상 중독 스킬 베이스: psn/psn_up."""
    card_type = CardType.SKILL
    needs_target = True  # 대상 지정 스킬 (_resolve_targets 사용)
    psn = 0
    psn_up = 0

    def _poison(self) -> int:
        return self.psn_up if self.upgraded else self.psn

    def use(self, source, targets, combat=None) -> None:
        for target in targets:
            if _alive(target):
                target.apply_power(Poison(self._poison()), applier=source)


# ══════════════════════════════════════════
# Common
# ══════════════════════════════════════════

class Anticipate(STS2Card):
    """예측 — 0코스트, 이번 턴 임시 민첩 +2 (업글 +4)."""
    card_id = "anticipate"
    name = "Anticipate"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(TempDexterity(4 if self.upgraded else 2))


class Backflip(_Block):
    """백플립 — 5블록 (업글 8) + 2드로우."""
    card_id = "backflip"
    name = "Backflip"
    rarity = Rarity.COMMON
    cost = 1
    blk, blk_up = 5, 8

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat:
            combat.draw_cards(2)


class BladeDance(STS2Card):
    """칼춤 — Shiv 3장 생성 (업글 4), 소모."""
    card_id = "blade_dance"
    name = "Blade Dance"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 1
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat:
            combat.create_shivs(4 if self.upgraded else 3)


class CloakAndDagger(_Block):
    """망토와 단검 — 6블록 + Shiv 1장 (업글 2장)."""
    card_id = "cloak_and_dagger"
    name = "Cloak and Dagger"
    rarity = Rarity.COMMON
    cost = 1
    blk = blk_up = 6

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat:
            combat.create_shivs(2 if self.upgraded else 1)


class DaggerSpray(_Attack):
    """단검 살포 — 모든 적에게 4딜 ×2회 (업글 6×2)."""
    card_id = "dagger_spray"
    name = "Dagger Spray"
    rarity = Rarity.COMMON
    cost = 1
    target_all = True
    dmg, dmg_up = 4, 6
    hits = 2


class DaggerThrow(_Attack):
    """단검 투척 — 9딜 (업글 12) + 1드로우 + 1버리기 [선택→무작위]."""
    card_id = "dagger_throw"
    name = "Dagger Throw"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 9, 12

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat:
            combat.draw_cards(1)
            combat.discard_from_hand(1)


class DeadlyPoison(_PoisonSkill):
    """맹독 — 중독 5 (업글 7)."""
    card_id = "deadly_poison"
    name = "Deadly Poison"
    rarity = Rarity.COMMON
    cost = 1
    psn, psn_up = 5, 7


class DodgeAndRoll(_Block):
    """회피 구르기 — 4블록 (업글 6), 다음 턴에도 같은 양의 블록."""
    card_id = "dodge_and_roll"
    name = "Dodge and Roll"
    rarity = Rarity.COMMON
    cost = 1
    blk, blk_up = 4, 6

    def use(self, source, targets, combat=None) -> None:
        before = source.block
        source.gain_block(self._block())
        gained = source.block - before  # 원본: 실제 획득량(민첩 포함)만큼 이월
        source.apply_power(BlockNextTurn(gained))


class FlickFlack(_Attack):
    """플릭플락 — 모든 적에게 7딜 (업글 9). Sly."""
    card_id = "flick_flack"
    name = "Flick Flack"
    rarity = Rarity.COMMON
    cost = 1
    target_all = True
    is_sly = True
    dmg, dmg_up = 7, 9


class LeadingStrike(_Attack):
    """선제 타격 — 3딜 (업글 6) + Shiv 2장. Strike 태그."""
    card_id = "leading_strike"
    name = "Leading Strike"
    rarity = Rarity.COMMON
    cost = 1
    tags = frozenset({"strike"})
    dmg, dmg_up = 3, 6

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat:
            combat.create_shivs(2)


class PiercingWail(STS2Card):
    """꿰뚫는 울음 — 모든 적 임시 힘 -6 (업글 -8), 소모."""
    card_id = "piercing_wail"
    name = "Piercing Wail"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 1
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        loss = 8 if self.upgraded else 6
        if combat:
            for enemy in list(combat.alive_enemies):
                enemy.apply_power(TempStrength(-loss), applier=source)


class PoisonedStab(_Attack):
    """독 찌르기 — 6딜 + 중독 3 (업글 8딜 + 중독 4)."""
    card_id = "poisoned_stab"
    name = "Poisoned Stab"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 6, 8

    def use(self, source, targets, combat=None) -> None:
        poison = 4 if self.upgraded else 3
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, self._damage())
                if _alive(target):
                    target.apply_power(Poison(poison), applier=source)


class Predator(_Attack):
    """포식자 — 15딜 (업글 20), 다음 턴 드로우 +2."""
    card_id = "predator"
    name = "Predator"
    rarity = Rarity.COMMON
    cost = 2
    dmg, dmg_up = 15, 20

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        source.apply_power(DrawCardsNextTurn(2))


class Prepared(STS2Card):
    """준비 완료 — 0코스트, 1드로우 + 1버리기 [선택→무작위] (업글 2/2)."""
    card_id = "prepared"
    name = "Prepared"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        count = 2 if self.upgraded else 1
        if combat:
            combat.draw_cards(count)
            combat.discard_from_hand(count)


class Ricochet(_Attack):
    """도탄 — 무작위 적에게 3딜 ×4회 (업글 ×5). Sly."""
    card_id = "ricochet"
    name = "Ricochet"
    rarity = Rarity.COMMON
    cost = 2
    is_sly = True
    dmg = dmg_up = 3
    hits, hits_up = 4, 5

    def use(self, source, targets, combat=None) -> None:
        for _ in range(self._hits()):
            pool = [t for t in (combat.alive_enemies if combat else targets)
                    if _alive(t)]
            if not pool:
                return
            target = combat.rng.choice(pool) if combat else pool[0]
            _deal_attack(source, target, self._damage())


class Slice(_Attack):
    """베기 — 0코스트 6딜 (업글 9)."""
    card_id = "slice"
    name = "Slice"
    rarity = Rarity.COMMON
    cost = 0
    dmg, dmg_up = 6, 9


class Snakebite(_PoisonSkill):
    """뱀물기 — 중독 7 (업글 10). Retain."""
    card_id = "snakebite"
    name = "Snakebite"
    rarity = Rarity.COMMON
    cost = 2
    retains = True
    psn, psn_up = 7, 10


class SuckerPunch(_Attack):
    """기습 공격 — 8딜 + 약화 1 (업글 10딜 + 약화 2)."""
    card_id = "sucker_punch"
    name = "Sucker Punch"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 8, 10

    def use(self, source, targets, combat=None) -> None:
        weak = 2 if self.upgraded else 1
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, self._damage())
                if _alive(target):
                    target.apply_power(Weak(weak), applier=source)


class Untouchable(_Block):
    """언터처블 — 6블록 (업글 9). Sly."""
    card_id = "untouchable"
    name = "Untouchable"
    rarity = Rarity.COMMON
    cost = 2
    is_sly = True
    blk, blk_up = 6, 9


# ══════════════════════════════════════════
# Uncommon
# ══════════════════════════════════════════

class Accuracy(STS2Card):
    """정확성 — 파워: Shiv 데미지 +4 (업글 +6)."""
    card_id = "accuracy"
    name = "Accuracy"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(AccuracyPower(6 if self.upgraded else 4))


class Backstab(_Attack):
    """기습 — 0코스트 11딜 (업글 15). 선천성, 소모."""
    card_id = "backstab"
    name = "Backstab"
    rarity = Rarity.UNCOMMON
    cost = 0
    is_innate = True
    exhausts = True
    dmg, dmg_up = 11, 15


class Blur(_Block):
    """흐릿함 — 5블록 (업글 8), 다음 턴 블록 유지."""
    card_id = "blur"
    name = "Blur"
    rarity = Rarity.UNCOMMON
    cost = 1
    blk, blk_up = 5, 8

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        source.apply_power(BlurPower(1))


class BouncingFlask(STS2Card):
    """튕기는 플라스크 — 무작위 적에게 중독 3을 3회 (업글 4회)."""
    card_id = "bouncing_flask"
    name = "Bouncing Flask"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        repeats = 4 if self.upgraded else 3
        if combat is None:
            return
        for _ in range(repeats):
            pool = [e for e in combat.alive_enemies if _alive(e)]
            if not pool:
                return
            combat.rng.choice(pool).apply_power(Poison(3), applier=source)


class BubbleBubble(_PoisonSkill):
    """부글부글 — 대상이 중독 상태면 중독 9 (업글 12)."""
    card_id = "bubble_bubble"
    name = "Bubble Bubble"
    rarity = Rarity.UNCOMMON
    cost = 1
    psn, psn_up = 9, 12

    def use(self, source, targets, combat=None) -> None:
        for target in targets:
            if _alive(target) and target.get_power_amount("poison") > 0:
                target.apply_power(Poison(self._poison()), applier=source)


class CalculatedGamble(STS2Card):
    """계산된 도박 — 손패 전부 버리고 같은 수만큼 드로우. 소모 (업글: Retain)."""
    card_id = "calculated_gamble"
    name = "Calculated Gamble"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        count = combat.discard_all_hand()
        combat.draw_cards(count)

    def upgrade(self) -> None:
        super().upgrade()
        self.retains = True


class Dash(_Attack):
    """돌진 — 10블록 + 10딜 (업글 13/13)."""
    card_id = "dash"
    name = "Dash"
    rarity = Rarity.UNCOMMON
    cost = 2
    dmg, dmg_up = 10, 13

    def use(self, source, targets, combat=None) -> None:
        source.gain_block(13 if self.upgraded else 10)
        super().use(source, targets, combat)

    def block_estimate(self, player, combat=None) -> int:
        return 13 if self.upgraded else 10


class EscapePlan(STS2Card):
    """탈출 계획 — 0코스트 1드로우, 스킬이면 3블록 (업글 5)."""
    card_id = "escape_plan"
    name = "Escape Plan"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        before = len(combat.hand)
        combat.draw_cards(1)
        drawn = combat.hand[before:] if len(combat.hand) > before else []
        if drawn and drawn[0].card_type == CardType.SKILL:
            source.gain_block(5 if self.upgraded else 3)


class Expertise(STS2Card):
    """전문 기술 — 손패가 6장(업글 7)이 될 때까지 드로우."""
    card_id = "expertise"
    name = "Expertise"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        target_size = 7 if self.upgraded else 6
        combat.draw_cards(max(0, target_size - len(combat.hand)))


class Expose(STS2Card):
    """노출 — 0코스트, 대상 블록/아티팩트 제거 + 취약 2 (업글 3). 소모."""
    card_id = "expose"
    name = "Expose"
    card_type = CardType.SKILL
    needs_target = True  # 대상 지정 스킬 (원본 TargetType.AnyEnemy)
    rarity = Rarity.UNCOMMON
    cost = 0
    exhausts = True
    vuln_setup = True

    def use(self, source, targets, combat=None) -> None:
        vuln = 3 if self.upgraded else 2
        for target in targets:
            if not _alive(target):
                continue
            target._block = 0
            target.remove_power("artifact")
            target.apply_power(Vulnerable(vuln), applier=source)


class Finisher(_Attack):
    """마무리 일격 — 이번 턴 플레이한 공격 카드 수만큼 6딜 (업글 8딜)."""
    card_id = "finisher"
    name = "Finisher"
    rarity = Rarity.UNCOMMON
    cost = 1
    dmg, dmg_up = 6, 8

    def use(self, source, targets, combat=None) -> None:
        # 자기 자신 제외 (원본은 종료된 카드 플레이만 집계)
        hits = max(0, (combat.attacks_played_this_turn - 1) if combat else 0)
        for _ in range(hits):
            for target in targets:
                if _alive(target):
                    _deal_attack(source, target, self._damage())

    def damage_estimate(self, player, combat=None, target=None) -> int:
        hits = getattr(combat, "attacks_played_this_turn", 0) if combat else 0
        return self._damage() * hits


class Flechettes(_Attack):
    """수리검 — 손패의 스킬 카드 수만큼 5딜 (업글 7딜)."""
    card_id = "flechettes"
    name = "Flechettes"
    rarity = Rarity.UNCOMMON
    cost = 1
    dmg, dmg_up = 5, 7

    def _skill_count(self, combat) -> int:
        if combat is None:
            return 0
        return sum(1 for c in combat.hand if c.card_type == CardType.SKILL)

    def use(self, source, targets, combat=None) -> None:
        for _ in range(self._skill_count(combat)):
            for target in targets:
                if _alive(target):
                    _deal_attack(source, target, self._damage())

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage() * self._skill_count(combat)


class Scare(STS2Card):
    """겁주기 — 0코스트, 모든 적 약화 1. 소모 (업글: 소모 제거)."""
    card_id = "scare"
    name = "Scare"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat:
            for enemy in list(combat.alive_enemies):
                enemy.apply_power(Weak(1), applier=source)

    def upgrade(self) -> None:
        super().upgrade()
        self.exhausts = False


class Footwork(STS2Card):
    """발놀림 — 파워: 민첩 +2 (업글 +3)."""
    card_id = "footwork"
    name = "Footwork"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(Dexterity(3 if self.upgraded else 2))


class HandTrick(_Block):
    """손재주 — 7블록 (업글 10) + 스킬 1장에 이번 턴 Sly 부여 [선택→무작위]."""
    card_id = "hand_trick"
    name = "Hand Trick"
    rarity = Rarity.UNCOMMON
    cost = 1
    blk, blk_up = 7, 10

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is None:
            return
        candidates = [c for c in combat.hand
                      if c.card_type == CardType.SKILL
                      and not c.is_sly and not c._sly_this_turn]
        if candidates:
            combat.rng.choice(candidates)._sly_this_turn = True


class Haze(STS2Card):
    """실안개 — 모든 적에게 중독 4 (업글 6). Sly."""
    card_id = "haze"
    name = "Haze"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 3
    is_sly = True

    def use(self, source, targets, combat=None) -> None:
        poison = 6 if self.upgraded else 4
        if combat:
            for enemy in list(combat.alive_enemies):
                enemy.apply_power(Poison(poison), applier=source)


class HiddenDaggers(STS2Card):
    """숨겨둔 단검 — 0코스트, 2버리기 [선택→무작위] + Shiv 2장 (업글: 업그레이드된 Shiv)."""
    card_id = "hidden_daggers"
    name = "Hidden Daggers"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        if combat:
            combat.discard_from_hand(2)
            combat.create_shivs(2, upgraded=self.upgraded)


class InfiniteBlades(STS2Card):
    """무한의 칼날 — 파워: 턴 시작마다 Shiv 1장 (업글: 선천성)."""
    card_id = "infinite_blades"
    name = "Infinite Blades"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(InfiniteBladesPower(1))

    def upgrade(self) -> None:
        super().upgrade()
        self.is_innate = True


class LegSweep(_Block):
    """다리 걸기 — 11블록 (업글 14) + 약화 2 (업글 3)."""
    card_id = "leg_sweep"
    name = "Leg Sweep"
    card_type = CardType.SKILL
    needs_target = True  # 대상 지정 스킬 (원본 TargetType.AnyEnemy)
    rarity = Rarity.UNCOMMON
    cost = 2
    blk, blk_up = 11, 14

    def use(self, source, targets, combat=None) -> None:
        source.gain_block(self._block())
        weak = 3 if self.upgraded else 2
        for target in targets:
            if _alive(target):
                target.apply_power(Weak(weak), applier=source)


class MementoMori(_Attack):
    """메멘토 모리 — (9 + 4×이번 턴 버린 카드 수)딜 (업글 11 + 5×)."""
    card_id = "memento_mori"
    name = "Memento Mori"
    rarity = Rarity.UNCOMMON
    cost = 1

    def _calc(self, combat) -> int:
        base, extra = (11, 5) if self.upgraded else (9, 4)
        discards = getattr(combat, "cards_discarded_this_turn", 0) if combat else 0
        return base + extra * discards

    def use(self, source, targets, combat=None) -> None:
        damage = self._calc(combat)
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, damage)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._calc(combat)


class Mirage(STS2Card):
    """신기루 — 모든 적 중독 합만큼 블록. 소모 (업글 0코스트)."""
    card_id = "mirage"
    name = "Mirage"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat:
            source.gain_block(sum(e.get_power_amount("poison")
                                  for e in combat.alive_enemies))

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)

    def block_estimate(self, player, combat=None) -> int:
        if combat is None:
            return 0
        return sum(e.get_power_amount("poison") for e in combat.alive_enemies)


class NoxiousFumes(STS2Card):
    """유독가스 — 파워: 턴 시작마다 모든 적 중독 2 (업글 3)."""
    card_id = "noxious_fumes"
    name = "Noxious Fumes"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(NoxiousFumesPower(3 if self.upgraded else 2))


class Outbreak(STS2Card):
    """창궐 — 파워: 적에게 중독을 걸 때마다 모든 적 3딜 (업글 4)."""
    card_id = "outbreak"
    name = "Outbreak"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(OutbreakPower(4 if self.upgraded else 3))


class PhantomBlades(STS2Card):
    """환영 칼날 — 파워: Shiv에 Retain, 턴 첫 Shiv +9딜 (업글 +12)."""
    card_id = "phantom_blades"
    name = "Phantom Blades"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(PhantomBladesPower(12 if self.upgraded else 9))
        if combat:  # AfterApplied — 기존 Shiv에도 Retain 부여
            for pile in (combat.hand, combat.draw_pile, combat.discard_pile):
                for card in pile:
                    if "shiv" in card.tags:
                        card.retains = True


class Pinpoint(_Attack):
    """핀포인트 — 15딜 (업글 19). 이번 턴 스킬 플레이당 비용 -1."""
    card_id = "pinpoint"
    name = "Pinpoint"
    rarity = Rarity.UNCOMMON
    cost = 3
    dmg, dmg_up = 15, 19

    def dynamic_cost(self, combat) -> int:
        return max(0, self.cost - getattr(combat, "skills_played_this_turn", 0))


class Pounce(_Attack):
    """급습 — 14딜 (업글 20), 다음 스킬 카드 비용 0."""
    card_id = "pounce"
    name = "Pounce"
    rarity = Rarity.UNCOMMON
    cost = 2
    dmg, dmg_up = 14, 20

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        source.apply_power(FreeSkill(1))


class PreciseCut(_Attack):
    """정밀 절단 — 0코스트, (13 - 2×손패 수)딜 (업글 16)."""
    card_id = "precise_cut"
    name = "Precise Cut"
    rarity = Rarity.UNCOMMON
    cost = 0

    def _calc(self, combat, in_hand: bool = False) -> int:
        base = 16 if self.upgraded else 13
        hand = len(combat.hand) if combat else 0
        if in_hand:  # 추정 시 자기 자신 제외 (원본 CalculatedVar 동일)
            hand = max(0, hand - 1)
        return max(0, base - 2 * hand)

    def use(self, source, targets, combat=None) -> None:
        damage = self._calc(combat)  # play_card가 이미 손패에서 제거함
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, damage)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._calc(combat, in_hand=True)


class Reflex(STS2Card):
    """반사신경 — 2드로우 (업글 3). Sly."""
    card_id = "reflex"
    name = "Reflex"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 3
    is_sly = True

    def use(self, source, targets, combat=None) -> None:
        if combat:
            combat.draw_cards(3 if self.upgraded else 2)


class Skewer(_Attack):
    """꼬치 꿰기 — X코스트: 8딜 ×X회 (업글 11딜)."""
    card_id = "skewer"
    name = "Skewer"
    rarity = Rarity.UNCOMMON
    cost = 0
    x_cost = True
    dmg, dmg_up = 8, 11

    def use(self, source, targets, combat=None) -> None:
        for _ in range(self.x_value):
            for target in targets:
                if _alive(target):
                    _deal_attack(source, target, self._damage())

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage() * player.energy


class Speedster(STS2Card):
    """스피드스터 — 파워: 추가 드로우마다 모든 적 2딜 (업글: 선천성)."""
    card_id = "speedster"
    name = "Speedster"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(SpeedsterPower(2))

    def upgrade(self) -> None:
        super().upgrade()
        self.is_innate = True


class Strangle(_Attack):
    """교살 — 8딜 (업글 10) + Strangle 2 (업글 3): 카드 플레이마다 비차단 피해."""
    card_id = "strangle"
    name = "Strangle"
    rarity = Rarity.UNCOMMON
    cost = 1
    dmg, dmg_up = 8, 10

    def use(self, source, targets, combat=None) -> None:
        stacks = 3 if self.upgraded else 2
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, self._damage())
                if _alive(target):
                    target.apply_power(StranglePower(stacks), applier=source)


class Tactician(STS2Card):
    """전술가 — 에너지 +1 (업글 +2). Sly."""
    card_id = "tactician"
    name = "Tactician"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 3
    is_sly = True

    def use(self, source, targets, combat=None) -> None:
        source.gain_energy(2 if self.upgraded else 1)


class UpMySleeve(STS2Card):
    """소매 속 무기 — Shiv 3장 (업글 4), 플레이할 때마다 이번 전투 비용 -1."""
    card_id = "up_my_sleeve"
    name = "Up My Sleeve"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        if combat:
            combat.create_shivs(4 if self.upgraded else 3)
        self.cost = max(0, self.cost - 1)


class WellLaidPlans(STS2Card):
    """치밀한 계획 — 파워: 턴 종료 시 카드 1장 유지 (업글 2장) [선택→무작위]."""
    card_id = "well_laid_plans"
    name = "Well-Laid Plans"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(WellLaidPlansPower(2 if self.upgraded else 1))


# ══════════════════════════════════════════
# Rare
# ══════════════════════════════════════════

class Abrasive(STS2Card):
    """거친 피부 — 파워: 가시 4 (업글 6) + 민첩 1. Sly."""
    card_id = "abrasive"
    name = "Abrasive"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 3
    is_sly = True

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(Dexterity(1))
        source.apply_power(Thorns(6 if self.upgraded else 4))


class AccelerantCard(STS2Card):
    """촉진제 — 파워: 중독이 추가로 1회 발동 (업글 2회)."""
    card_id = "accelerant"
    name = "Accelerant"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(AccelerantPower(2 if self.upgraded else 1))


class Adrenaline(STS2Card):
    """아드레날린 — 0코스트, 에너지 +1 (업글 +2) + 2드로우. 소모."""
    card_id = "adrenaline"
    name = "Adrenaline"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 0
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        source.gain_energy(2 if self.upgraded else 1)
        if combat:
            combat.draw_cards(2)


class Afterimage(STS2Card):
    """잔상 — 파워: 카드 플레이마다 1블록 (업글: 선천성)."""
    card_id = "afterimage"
    name = "Afterimage"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(AfterimagePower(1))

    def upgrade(self) -> None:
        super().upgrade()
        self.is_innate = True


class Assassinate(_Attack):
    """암살 — 0코스트 10딜 (업글 13) + 취약 1 (업글 2). 선천성, 소모."""
    card_id = "assassinate"
    name = "Assassinate"
    rarity = Rarity.RARE
    cost = 0
    is_innate = True
    exhausts = True
    vuln_setup = True
    dmg, dmg_up = 10, 13

    def use(self, source, targets, combat=None) -> None:
        vuln = 2 if self.upgraded else 1
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, self._damage())
                if _alive(target):
                    target.apply_power(Vulnerable(vuln), applier=source)


class BladeOfInk(STS2Card):
    """잉크의 칼날 — Inky Shiv 2장 (업글 3): +1딜, 약화 1 부여."""
    card_id = "blade_of_ink"
    name = "Blade of Ink"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat:
            combat.create_shivs(3 if self.upgraded else 2, inky=True)


class BulletTime(_CostDownOnUpgrade, STS2Card):
    """총알 시간 — 손패 전부 이번 턴 비용 0, 드로우 불가 1 (업글 2코스트)."""
    card_id = "bullet_time"
    name = "Bullet Time"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 3

    def use(self, source, targets, combat=None) -> None:
        if combat:
            for card in combat.hand:
                if not card.x_cost:
                    card._free_this_turn = True
        source.apply_power(NoDraw(1))


class Burst(STS2Card):
    """폭발 — 다음 스킬 1장이 2회 발동 (업글 2장)."""
    card_id = "burst"
    name = "Burst"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(BurstPower(2 if self.upgraded else 1))


class CorrosiveWave(STS2Card):
    """부식의 파도 — 이번 턴 드로우마다 모든 적 중독 2 (업글 3)."""
    card_id = "corrosive_wave"
    name = "Corrosive Wave"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(CorrosiveWavePower(3 if self.upgraded else 2))


class EchoingSlash(_Attack):
    """메아리 베기 — 모든 적 10딜 (업글 13), 적 처치 시 반복."""
    card_id = "echoing_slash"
    name = "Echoing Slash"
    rarity = Rarity.RARE
    cost = 1
    target_all = True
    dmg, dmg_up = 10, 13

    def use(self, source, targets, combat=None) -> None:
        attack_count = 1
        while attack_count > 0:
            attack_count -= 1
            pool = [e for e in (combat.alive_enemies if combat else targets)
                    if _alive(e)]
            if not pool:
                return
            for target in pool:
                result = _deal_attack(source, target, self._damage())
                if result.get("killed"):
                    attack_count += 1


class Envenom(STS2Card):
    """독살 — 파워: 공격으로 비차단 피해마다 중독 1 (업글 2)."""
    card_id = "envenom"
    name = "Envenom"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(EnvenomPower(2 if self.upgraded else 1))


class FanOfKnives(STS2Card):
    """칼날의 부채 — 파워: Shiv 전체 공격화 + Shiv 4장 (업글 5장)."""
    card_id = "fan_of_knives"
    name = "Fan of Knives"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(FanOfKnivesPower(1))
        if combat:
            combat.create_shivs(5 if self.upgraded else 4)


class GrandFinale(_Attack):
    """그랜드 피날레 — 0코스트, 모든 적 60딜 (업글 75). 뽑을 카드가 없을 때만."""
    card_id = "grand_finale"
    name = "Grand Finale"
    rarity = Rarity.RARE
    cost = 0
    target_all = True
    dmg, dmg_up = 60, 75

    def dynamic_playable(self, combat) -> bool:
        return len(combat.draw_pile) == 0


class KnifeTrap(STS2Card):
    """칼날 함정 — 소모 더미의 Shiv를 전부 대상에게 자동 플레이 (업글: 업그레이드 후)."""
    card_id = "knife_trap"
    name = "Knife Trap"
    card_type = CardType.SKILL
    needs_target = True  # 대상 지정 스킬 (원본 TargetType.AnyEnemy)
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        shivs = [c for c in combat.exhaust_pile if "shiv" in c.tags]
        for shiv in shivs:
            combat.exhaust_pile.remove(shiv)
            if self.upgraded and not shiv.upgraded:
                shiv.upgrade()
            combat.auto_play(shiv)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        if combat is None:
            return 0
        return sum(c.damage_estimate(player, combat)
                   for c in combat.exhaust_pile if "shiv" in c.tags)


class Malaise(STS2Card):
    """무기력 — X코스트: 힘 -X, 약화 X (업글 X+1). 소모."""
    card_id = "malaise"
    name = "Malaise"
    card_type = CardType.SKILL
    needs_target = True  # 대상 지정 스킬 (원본 TargetType.AnyEnemy)
    rarity = Rarity.RARE
    cost = 0
    x_cost = True
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        amount = self.x_value + (1 if self.upgraded else 0)
        if amount <= 0:
            return
        for target in targets:
            if _alive(target):
                target.apply_power(Strength(-amount), applier=source)
                target.apply_power(Weak(amount), applier=source)


class MasterPlanner(_CostDownOnUpgrade, STS2Card):
    """책략가 — 파워: 플레이한 스킬에 Sly 부여 (업글 1코스트)."""
    card_id = "master_planner"
    name = "Master Planner"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(MasterPlannerPower(1))


class Murder(_CostDownOnUpgrade, _Attack):
    """살인 — (1 + 이번 전투 드로우 수)딜 (업글 2코스트)."""
    card_id = "murder"
    name = "Murder"
    rarity = Rarity.RARE
    cost = 3

    def _calc(self, combat) -> int:
        drawn = getattr(combat, "cards_drawn_this_combat", 0) if combat else 0
        return 1 + drawn

    def use(self, source, targets, combat=None) -> None:
        damage = self._calc(combat)
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, damage)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._calc(combat)


class Nightmare(_CostDownOnUpgrade, STS2Card):
    """악몽 — 손패 카드 1장 [선택→무작위]의 사본 3장을 다음 턴 손패에. 소모."""
    card_id = "nightmare"
    name = "Nightmare"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 3
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None or not combat.hand:
            return
        power = NightmarePower(3)
        power.selected_card = combat.rng.choice(combat.hand)
        source.apply_power(power)


class SerpentForm(STS2Card):
    """뱀의 형상 — 파워: 카드 플레이마다 무작위 적 4딜 (업글 6)."""
    card_id = "serpent_form"
    name = "Serpent Form"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 3

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(SerpentFormPower(6 if self.upgraded else 4))


class ShadowStep(_CostDownOnUpgrade, STS2Card):
    """그림자 밟기 — 손패 전부 버리고, 다음 턴 공격 데미지 2배 (업글 0코스트)."""
    card_id = "shadow_step"
    name = "Shadow Step"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat:
            combat.discard_all_hand()
        source.apply_power(ShadowStepPower(1))


class Shadowmeld(_CostDownOnUpgrade, STS2Card):
    """그림자 융화 — 이번 턴 블록 획득 2배 (업글 0코스트)."""
    card_id = "shadowmeld"
    name = "Shadowmeld"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(ShadowmeldPower(1))


class StormOfSteel(STS2Card):
    """강철 폭풍 — 손패 전부 버리고 그 수만큼 Shiv (업글: 업그레이드된 Shiv)."""
    card_id = "storm_of_steel"
    name = "Storm of Steel"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        count = combat.discard_all_hand()
        combat.create_shivs(count, upgraded=self.upgraded)


class TheHunt(_Attack):
    """사냥 — 10딜 (업글 15). 처치 시 추가 카드 보상. 소모."""
    card_id = "the_hunt"
    name = "The Hunt"
    rarity = Rarity.RARE
    cost = 1
    exhausts = True
    dmg, dmg_up = 10, 15

    def use(self, source, targets, combat=None) -> None:
        for target in targets:
            if not _alive(target):
                continue
            result = _deal_attack(source, target, self._damage())
            if result.get("killed") and combat is not None:
                combat.extra_card_rewards += 1
                source.apply_power(TheHuntPower(1))


class ToolsOfTheTrade(_CostDownOnUpgrade, STS2Card):
    """장인의 도구 — 파워: 턴마다 드로우 +1, 1버리기 [선택→무작위] (업글 0코스트)."""
    card_id = "tools_of_the_trade"
    name = "Tools of the Trade"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(ToolsOfTheTradePower(1))


class Tracking(_CostDownOnUpgrade, STS2Card):
    """추적 — 파워: 약화된 적에게 공격 데미지 +50% (업글 1코스트)."""
    card_id = "tracking"
    name = "Tracking"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(TrackingPower(50))


# ══════════════════════════════════════════
# Ancient
# ══════════════════════════════════════════

class Suppress(_Attack):
    """제압 — 0코스트 11딜 (업글 17) + 약화 3 (업글 5). 선천성."""
    card_id = "suppress"
    name = "Suppress"
    rarity = Rarity.ANCIENT
    cost = 0
    is_innate = True
    dmg, dmg_up = 11, 17

    def use(self, source, targets, combat=None) -> None:
        weak = 5 if self.upgraded else 3
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, self._damage())
                if _alive(target):
                    target.apply_power(Weak(weak), applier=source)


class WraithForm(STS2Card):
    """망령의 형상 — 파워: 비실체 2 (업글 3), 턴마다 민첩 -1."""
    card_id = "wraith_form"
    name = "Wraith Form"
    card_type = CardType.POWER
    rarity = Rarity.ANCIENT
    cost = 3

    def use(self, source, targets, combat=None) -> None:
        source.apply_power(Intangible(3 if self.upgraded else 2))
        source.apply_power(WraithFormPower(1))


# ══════════════════════════════════════════
# 등록 & 풀 정의
# ══════════════════════════════════════════

_SILENT_CARDS = [
    # Common (19)
    Anticipate, Backflip, BladeDance, CloakAndDagger, DaggerSpray, DaggerThrow,
    DeadlyPoison, DodgeAndRoll, FlickFlack, LeadingStrike, PiercingWail,
    PoisonedStab, Predator, Prepared, Ricochet, Slice, Snakebite, SuckerPunch,
    Untouchable,
    # Uncommon (34)
    Accuracy, Backstab, Blur, BouncingFlask, BubbleBubble, CalculatedGamble,
    Dash, EscapePlan, Expertise, Expose, Finisher, Flechettes, Scare, Footwork,
    HandTrick, Haze, HiddenDaggers, InfiniteBlades, LegSweep, MementoMori,
    Mirage, NoxiousFumes, Outbreak, PhantomBlades, Pinpoint, Pounce, PreciseCut,
    Reflex, Skewer, Speedster, Strangle, Tactician, UpMySleeve, WellLaidPlans,
    # Rare (25)
    Abrasive, AccelerantCard, Adrenaline, Afterimage, Assassinate, BladeOfInk,
    BulletTime, Burst, CorrosiveWave, EchoingSlash, Envenom, FanOfKnives,
    GrandFinale, KnifeTrap, Malaise, MasterPlanner, Murder, Nightmare,
    SerpentForm, ShadowStep, Shadowmeld, StormOfSteel, TheHunt, ToolsOfTheTrade,
    Tracking,
    # Ancient (2)
    Suppress, WraithForm,
]

CARD_REGISTRY.update({cls.card_id: cls for cls in _SILENT_CARDS})

# 보상 풀: 기존 구현(deflect=Common, acrobatics=Uncommon) 포함, Ancient 제외
SILENT_POOL_BY_RARITY = {
    Rarity.COMMON: sorted(
        [c.card_id for c in _SILENT_CARDS if c.rarity == Rarity.COMMON]
        + ["deflect"]),
    Rarity.UNCOMMON: sorted(
        [c.card_id for c in _SILENT_CARDS if c.rarity == Rarity.UNCOMMON]
        + ["acrobatics"]),
    Rarity.RARE: sorted(
        [c.card_id for c in _SILENT_CARDS if c.rarity == Rarity.RARE]),
}
