"""
Regent 카드 풀 — 디컴파일 MegaCrit.Sts2.Core.Models.CardPools.RegentCardPool 이식.

원본 90종 중:
  - StrikeRegent/DefendRegent(스타터), FallingStar/Venerate(Basic, 스타터 덱)는
    models/sts2_card.py에 기존 구현
  - 멀티플레이 전용 4종 제외: Constellation, HammerTime, Largesse, Plot
  - 나머지 82종 + SovereignBlade/MinionStrike/MinionDiveBomb/MinionSacrifice/
    Debris 토큰을 여기서 구현

모든 수치는 디컴파일 .cs의 CanonicalVars/OnUpgrade 그대로.
카드 선택 UI가 필요한 효과는 무작위 선택으로 대체하고 주석에 [선택→무작위] 표기.
Colorless 카드풀 참조(Quasar/BundleOfJoy/ManifestAuthority/HeirloomHammer)는
Phase 6g에서 sts2_sim.cards.colorless._COLORLESS_IDS로 배선 완료.

Regent 메커니즘:
  - Stars: 카드 플레이의 별 비용 자원 (턴 간 지속, DivineRight 전투 시작 +3)
  - Forge(n): 소모되지 않은 SovereignBlade가 없으면 손패에 생성,
    모든 SovereignBlade(소모 더미 포함) 데미지 +n (원본 ForgeCmd.Forge)
  - SovereignBlade: 2코스트(업글 1) Retain 토큰 공격 10+Forge 누적.
    Parry(파워 수치만큼 블록), SeekingEdge(전체 공격화),
    Conqueror(대상 피해 2배), SwordSage(Replay +n) 연동
  - Replay: 플레이 시 카드 로직 추가 발동 (combat._extra_plays 재사용)
"""
from __future__ import annotations

from sts2_sim.models.sts2_card import (
    STS2Card, CardType, Rarity, CARD_REGISTRY, _deal_attack,
)
from sts2_sim.cards.ironclad import _Attack, _Block, _CostDownOnUpgrade, _alive

MAX_HAND_SIZE = 10  # CardPile.MaxCardsInHand


# ══════════════════════════════════════════
# Forge / SovereignBlade 공용 헬퍼
# ══════════════════════════════════════════

def _all_pile_cards(combat):
    return combat.hand + combat.draw_pile + combat.discard_pile + combat.exhaust_pile


def _forge(source, combat, amount: int) -> None:
    """Forge (원본 ForgeCmd.Forge): 소모되지 않은 SovereignBlade가 없으면
    손패에 생성 후, 모든 SovereignBlade(소모 더미 포함)의 데미지 +amount."""
    if combat is None:
        return
    non_exhaust = combat.hand + combat.draw_pile + combat.discard_pile
    if not any(isinstance(c, SovereignBlade) for c in non_exhaust):
        combat.generate_card("sovereign_blade", to="hand")
    for card in _all_pile_cards(combat):
        if isinstance(card, SovereignBlade):
            card._forged_damage += amount


def _count_star_cards(combat) -> int:
    """별 비용이 있는 전투 내 카드 수 (원본 CanonicalStarCost >= 0 || HasStarCostX)."""
    return sum(1 for c in _all_pile_cards(combat)
               if c.star_cost > 0 or getattr(c, "star_x_cost", False))


def _apply_to_targets(source, targets, power_factory) -> None:
    for target in targets:
        if _alive(target) and hasattr(target, "apply_power"):
            target.apply_power(power_factory(), applier=source)


def _notify_card_generated(combat, card) -> None:
    """제자리 치환(Guards) 등 combat.generate_card를 쓸 수 없는 카드 생성 경로에서
    생성 훅을 동일하게 발화 (원본 CardCmd.Transform → Hook.AfterCardGeneratedForCombat)."""
    combat.cards_generated_this_combat += 1  # Supermassive 집계
    combat.notify_player_powers("on_card_generated", card, combat)  # Arsenal/PillarOfCreation
    for pile in (combat.hand, combat.draw_pile, combat.discard_pile):
        for c in pile:
            hook = getattr(c, "on_card_generated_combat", None)
            if hook:
                hook(card, combat)


# ══════════════════════════════════════════
# 토큰 카드
# ══════════════════════════════════════════

class SovereignBlade(STS2Card):
    """군주의 검 — 2코스트(업글 1) Retain 토큰. 10+Forge 데미지.
    SeekingEdge 보유 시 전체 공격, Parry 보유 시 파워 수치만큼 블록,
    Conqueror 대상에 피해 2배 (원본 SovereignBlade)."""
    card_id = "sovereign_blade"
    name = "Sovereign Blade"
    card_type = CardType.ATTACK
    rarity = Rarity.TOKEN
    cost = 2
    retains = True

    def __init__(self):
        super().__init__()
        self._forged_damage = 0  # Forge 누적 (전투 한정)
        self._repeat_hits = 1    # RepeatVar (SetRepeats — 현재 변경원 없음)

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)

    def _damage(self) -> int:
        return 10 + self._forged_damage

    def use(self, source, targets, combat=None) -> None:
        seeking = source.get_power_amount("seeking_edge") > 0
        if seeking and combat is not None:
            targets = list(combat.alive_enemies)
        source._playing_sovereign_blade = True  # Conqueror 2배 판정
        try:
            for _ in range(self._repeat_hits):
                for target in targets:
                    if _alive(target):
                        _deal_attack(source, target, self._damage())
        finally:
            source._playing_sovereign_blade = False
        parry = source.get_power_amount("parry")
        if parry > 0:
            # 원본 CalculatedBlock = 0 + 1 × Parry (Move 블록 — 민첩 적용)
            source.gain_block(parry)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage() * self._repeat_hits

    def reset_combat_state(self) -> None:
        self._forged_damage = 0
        self._repeat_hits = 1


class MinionStrike(_Attack):
    """부하의 일격 — 0코스트 6딜(업글 9) + 드로우 1, 소모 (Begone 변환 토큰)."""
    card_id = "minion_strike"
    name = "Minion Strike"
    rarity = Rarity.TOKEN
    cost = 0
    exhausts = True
    tags = frozenset({"strike", "minion"})
    dmg, dmg_up = 6, 9

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat:
            combat.draw_cards(1)


class MinionDiveBomb(_Attack):
    """부하의 급강하 — 0코스트 13딜(업글 16), 소모 (Charge 변환 토큰)."""
    card_id = "minion_dive_bomb"
    name = "Minion Dive Bomb"
    rarity = Rarity.TOKEN
    cost = 0
    exhausts = True
    tags = frozenset({"minion"})
    dmg, dmg_up = 13, 16


class MinionSacrifice(_Block):
    """부하의 희생 — 0코스트 7블록(업글 10), 소모 (Guards 변환 토큰)."""
    card_id = "minion_sacrifice"
    name = "Minion Sacrifice"
    rarity = Rarity.TOKEN
    cost = 0
    exhausts = True
    tags = frozenset({"minion"})
    blk, blk_up = 7, 10


class Debris(STS2Card):
    """잔해 — 1코스트 상태이상, 효과 없음, 소모. 업그레이드 불가
    (CollisionCourse/CrashLanding — 원본 MaxUpgradeLevel 0)."""
    card_id = "debris"
    name = "Debris"
    card_type = CardType.STATUS
    rarity = Rarity.TOKEN
    cost = 1
    exhausts = True

    def upgrade(self) -> None:
        pass  # MaxUpgradeLevel 0


# ══════════════════════════════════════════
# Common (20)
# ══════════════════════════════════════════

class AstralPulse(_Attack):
    """성진 파동 — 0코스트/별 3, 전체 6딜×2 (업글 8딜)."""
    card_id = "astral_pulse"
    name = "Astral Pulse"
    rarity = Rarity.COMMON
    cost = 0
    star_cost = 3
    target_all = True
    dmg, dmg_up = 6, 8
    hits = 2


class Begone(STS2Card):
    """물렀거라 — 손패 카드 1장을 MinionStrike로 변환 (업글: 강화된 MinionStrike).
    [선택→무작위]"""
    card_id = "begone"
    name = "Begone"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat is None or not combat.hand:
            return
        victim = combat.rng.choice(combat.hand)
        combat.hand.remove(victim)
        minion = MinionStrike()
        if self.upgraded:
            minion.upgrade()
        combat.hand.append(minion)


class CelestialMight(_Attack):
    """천상의 위력 — 2코스트 6딜×3 (업글 ×4)."""
    card_id = "celestial_might"
    name = "Celestial Might"
    rarity = Rarity.COMMON
    cost = 2
    dmg, dmg_up = 6, 6
    hits, hits_up = 3, 4


class CloakOfStars(_Block):
    """별의 망토 — 0코스트/별 1, 7블록 (업글 10)."""
    card_id = "cloak_of_stars"
    name = "Cloak of Stars"
    rarity = Rarity.COMMON
    cost = 0
    star_cost = 1
    blk, blk_up = 7, 10


class CollisionCourse(_Attack):
    """충돌 궤도 — 0코스트 11딜 (업글 15) + Debris 1장 손패 생성."""
    card_id = "collision_course"
    name = "Collision Course"
    rarity = Rarity.COMMON
    cost = 0
    dmg, dmg_up = 11, 15

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat:
            combat.generate_card("debris", to="hand")


class CosmicIndifference(_Block):
    """우주적 무관심 — 6블록 (업글 9) + 버림 더미 카드 1장을 뽑을 더미 맨 위로.
    [선택→무작위]"""
    card_id = "cosmic_indifference"
    name = "Cosmic Indifference"
    rarity = Rarity.COMMON
    cost = 1
    blk, blk_up = 6, 9

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat and combat.discard_pile:
            card = combat.rng.choice(combat.discard_pile)
            combat.discard_pile.remove(card)
            combat.draw_pile.append(card)  # 리스트 끝 = 맨 위


class CrescentSpear(STS2Card):
    """초승달 창 — 1코스트/별 1, (8 + 2×별 비용 카드 수)딜 (업글 8+3×)."""
    card_id = "crescent_spear"
    name = "Crescent Spear"
    card_type = CardType.ATTACK
    rarity = Rarity.COMMON
    cost = 1
    star_cost = 1

    def _damage(self, combat) -> int:
        extra = 3 if self.upgraded else 2
        # 플레이 중인 자신도 집계 (원본 AllCards는 Play 파일 포함)
        count = (_count_star_cards(combat) + 1) if combat else 0
        return 8 + extra * count

    def use(self, source, targets, combat=None) -> None:
        dmg = self._damage(combat)
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, dmg)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage(combat) if combat else 8


class CrushUnder(STS2Card):
    """짓밟기 — 전체 7딜 (업글 8) + 임시 힘 -1 (업글 -2)."""
    card_id = "crush_under"
    name = "Crush Under"
    card_type = CardType.ATTACK
    rarity = Rarity.COMMON
    cost = 1
    target_all = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import TempStrength
        dmg = 8 if self.upgraded else 7
        loss = 2 if self.upgraded else 1
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, dmg)
        _apply_to_targets(source, targets, lambda: TempStrength(-loss))

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return 8 if self.upgraded else 7


class GatherLight(_Block):
    """빛 모으기 — 8블록 (업글 11) + 별 1."""
    card_id = "gather_light"
    name = "Gather Light"
    rarity = Rarity.COMMON
    cost = 1
    blk, blk_up = 8, 11

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        source.gain_stars(1)


class Glitterstream(_Block):
    """반짝임의 물결 — 2코스트 11블록 (업글 13) + 다음 턴 블록 5 (업글 7)."""
    card_id = "glitterstream"
    name = "Glitterstream"
    rarity = Rarity.COMMON
    cost = 2
    blk, blk_up = 11, 13

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import BlockNextTurn
        super().use(source, targets, combat)
        # 원본: 이월 블록도 시전 시점의 블록 수정자(민첩/Frail 등)를 미리 반영
        base = 7 if self.upgraded else 5
        source.apply_power(BlockNextTurn(source.compute_modified_block(base)))


class Glow(STS2Card):
    """발광 — 별 1 (업글 2) + 드로우 1 + 다음 턴 드로우 +1."""
    card_id = "glow"
    name = "Glow"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import DrawCardsNextTurn
        source.gain_stars(2 if self.upgraded else 1)
        if combat:
            combat.draw_cards(1)
        source.apply_power(DrawCardsNextTurn(1))


class GuidingStar(_Attack):
    """길잡이 별 — 1코스트/별 2, 12딜 (업글 13) + 드로우 2 (업글 3)."""
    card_id = "guiding_star"
    name = "Guiding Star"
    rarity = Rarity.COMMON
    cost = 1
    star_cost = 2
    dmg, dmg_up = 12, 13

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat:
            combat.draw_cards(3 if self.upgraded else 2)


class HiddenCache(STS2Card):
    """숨겨진 보고 — 별 1 + 다음 턴 별 3 (업글 4)."""
    card_id = "hidden_cache"
    name = "Hidden Cache"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import StarNextTurn
        source.gain_stars(1)
        source.apply_power(StarNextTurn(4 if self.upgraded else 3))


class KnowThyPlace(STS2Card):
    """분수를 알라 — 0코스트, 약화 1 + 취약 1, 소모 (업글: 소모 제거)."""
    card_id = "know_thy_place"
    name = "Know Thy Place"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 0
    exhausts = True
    needs_target = True

    def upgrade(self) -> None:
        super().upgrade()
        self.exhausts = False  # RemoveKeyword(Exhaust)

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Weak, Vulnerable
        for target in targets[:1]:
            if _alive(target) and hasattr(target, "apply_power"):
                target.apply_power(Weak(1), applier=source)
                target.apply_power(Vulnerable(1), applier=source)


class Patter(_Block):
    """재잘거림 — 8블록 (업글 10) + Vigor 2 (업글 3)."""
    card_id = "patter"
    name = "Patter"
    rarity = Rarity.COMMON
    cost = 1
    blk, blk_up = 8, 10

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Vigor
        super().use(source, targets, combat)
        source.apply_power(Vigor(3 if self.upgraded else 2))


class PhotonCut(_Attack):
    """광자 절단 — 10딜 (업글 13) + 드로우 1 (업글 2) + 1장을 뽑을 더미 맨 위로.
    [선택→무작위]"""
    card_id = "photon_cut"
    name = "Photon Cut"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 10, 13

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is None:
            return
        combat.draw_cards(2 if self.upgraded else 1)
        if combat.hand:
            card = combat.rng.choice(combat.hand)
            combat.hand.remove(card)
            combat.draw_pile.append(card)


class RefineBlade(STS2Card):
    """검 연마 — Forge 9 (업글 13) + 다음 턴 에너지 +1."""
    card_id = "refine_blade"
    name = "Refine Blade"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import EnergyNextTurn
        _forge(source, combat, 13 if self.upgraded else 9)
        source.apply_power(EnergyNextTurn(1))


class SolarStrike(_Attack):
    """태양의 일격 — 9딜 (업글 10) + 별 1 (업글 2). Strike 태그."""
    card_id = "solar_strike"
    name = "Solar Strike"
    rarity = Rarity.COMMON
    cost = 1
    tags = frozenset({"strike"})
    dmg, dmg_up = 9, 10

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        source.gain_stars(2 if self.upgraded else 1)


class SpoilsOfBattle(STS2Card):
    """전리품 — Forge 5 (업글 8) + 드로우 2."""
    card_id = "spoils_of_battle"
    name = "Spoils of Battle"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        _forge(source, combat, 8 if self.upgraded else 5)
        if combat:
            combat.draw_cards(2)


class WroughtInWar(_Attack):
    """전쟁의 산물 — 7딜 (업글 9) + Forge 7 (업글 9)."""
    card_id = "wrought_in_war"
    name = "Wrought in War"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 7, 9

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        _forge(source, combat, 9 if self.upgraded else 7)


# ══════════════════════════════════════════
# Uncommon (35)
# ══════════════════════════════════════════

class Alignment(STS2Card):
    """정렬 — 0코스트/별 3, 에너지 +2 (업글 +3)."""
    card_id = "alignment"
    name = "Alignment"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0
    star_cost = 3

    def use(self, source, targets, combat=None) -> None:
        source.gain_energy(3 if self.upgraded else 2)


class BlackHole(STS2Card):
    """블랙홀 — 파워: 별 소모/획득 시 전체 3 피해 (업글 4)."""
    card_id = "black_hole"
    name = "Black Hole"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import BlackHoleP
        source.apply_power(BlackHoleP(4 if self.upgraded else 3))


class Bulwark(_Block):
    """보루 — 2코스트 12블록 (업글 15) + Forge 10 (업글 13)."""
    card_id = "bulwark"
    name = "Bulwark"
    rarity = Rarity.UNCOMMON
    cost = 2
    blk, blk_up = 12, 15

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        _forge(source, combat, 13 if self.upgraded else 10)


class Charge(STS2Card):
    """돌격 명령 — 뽑을 더미 카드 2장을 MinionDiveBomb로 변환
    (업글: 강화된 MinionDiveBomb). [선택→무작위]"""
    card_id = "charge"
    name = "Charge"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat is None or not combat.draw_pile:
            return
        # 원본 CardSelectCmd — 서로 다른 카드 2장 선택 (중복 선택 불가)
        count = min(2, len(combat.draw_pile))
        for idx in combat.rng.sample(range(len(combat.draw_pile)), count):
            minion = MinionDiveBomb()
            if self.upgraded:
                minion.upgrade()
            combat.draw_pile[idx] = minion


class ChildOfTheStars(STS2Card):
    """별의 아이 — 파워: 별 소모마다 (2 × 소모량) 블록 (업글 3×)."""
    card_id = "child_of_the_stars"
    name = "Child of the Stars"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import ChildOfTheStarsP
        source.apply_power(ChildOfTheStarsP(3 if self.upgraded else 2))


class Conqueror(STS2Card):
    """정복자 — Forge 3 (업글 5) + 대상에게 Conqueror 1 (SovereignBlade 피해 2배)."""
    card_id = "conqueror"
    name = "Conqueror"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    needs_target = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import ConquerorP
        _forge(source, combat, 5 if self.upgraded else 3)
        for target in targets[:1]:
            if _alive(target) and hasattr(target, "apply_power"):
                target.apply_power(ConquerorP(1), applier=source)


class Convergence(STS2Card):
    """수렴 — 이번 턴 손패 유지 + 다음 턴 에너지 +1, 별 +1 (업글 +2)."""
    card_id = "convergence"
    name = "Convergence"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import (
            RetainHandP, EnergyNextTurn, StarNextTurn)
        source.apply_power(RetainHandP(1))
        source.apply_power(EnergyNextTurn(1))
        source.apply_power(StarNextTurn(2 if self.upgraded else 1))


class Devastate(_Attack):
    """유린 — 1코스트/별 4, 35딜 (업글 45)."""
    card_id = "devastate"
    name = "Devastate"
    rarity = Rarity.UNCOMMON
    cost = 1
    star_cost = 4
    dmg, dmg_up = 35, 45


class Furnace(STS2Card):
    """용광로 — 파워: 매 턴 시작 Forge 5 (업글 7)."""
    card_id = "furnace"
    name = "Furnace"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import FurnaceP
        source.apply_power(FurnaceP(7 if self.upgraded else 5))


class GammaBlast(_Attack):
    """감마 폭발 — 0코스트/별 3, 13딜 (업글 18) + 약화 2 + 취약 2."""
    card_id = "gamma_blast"
    name = "Gamma Blast"
    rarity = Rarity.UNCOMMON
    cost = 0
    star_cost = 3
    dmg, dmg_up = 13, 18

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Weak, Vulnerable
        super().use(source, targets, combat)
        for target in targets[:1]:
            if _alive(target) and hasattr(target, "apply_power"):
                target.apply_power(Weak(2), applier=source)
                target.apply_power(Vulnerable(2), applier=source)


class Glimmer(STS2Card):
    """희미한 빛 — 드로우 3 (업글 4) 후 1장을 뽑을 더미 맨 위로. [선택→무작위]"""
    card_id = "glimmer"
    name = "Glimmer"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        combat.draw_cards(4 if self.upgraded else 3)
        if combat.hand:
            card = combat.rng.choice(combat.hand)
            combat.hand.remove(card)
            combat.draw_pile.append(card)


class Hegemony(_Attack):
    """패권 — 2코스트 15딜 (업글 18) + 다음 턴 에너지 +2 (업글 +3)."""
    card_id = "hegemony"
    name = "Hegemony"
    rarity = Rarity.UNCOMMON
    cost = 2
    dmg, dmg_up = 15, 18

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import EnergyNextTurn
        super().use(source, targets, combat)
        source.apply_power(EnergyNextTurn(3 if self.upgraded else 2))


class KinglyKick(_Attack):
    """왕의 발차기 — 4코스트 27딜 (업글 35). 드로우할 때마다 이번 전투 비용 -1."""
    card_id = "kingly_kick"
    name = "Kingly Kick"
    rarity = Rarity.UNCOMMON
    cost = 4
    dmg, dmg_up = 27, 35

    def on_drawn(self, combat) -> None:
        self._cost_add_this_combat -= 1  # 원본 EnergyCost.AddThisCombat(-1)


class KinglyPunch(STS2Card):
    """왕의 주먹 — 8딜 (업글 10). 드로우할 때마다 이번 전투 데미지 +4 (업글 +6)."""
    card_id = "kingly_punch"
    name = "Kingly Punch"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 1

    def __init__(self):
        super().__init__()
        self._bonus_damage = 0  # 이번 전투 누적 (원본 ExtraDamage)

    def _damage(self) -> int:
        return (10 if self.upgraded else 8) + self._bonus_damage

    def on_drawn(self, combat) -> None:
        self._bonus_damage += 6 if self.upgraded else 4

    def use(self, source, targets, combat=None) -> None:
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, self._damage())

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage()

    def reset_combat_state(self) -> None:
        self._bonus_damage = 0


class KnockoutBlow(_Attack):
    """결정타 — 3코스트 30딜 (업글 38). 처치 시 별 +5."""
    card_id = "knockout_blow"
    name = "Knockout Blow"
    rarity = Rarity.UNCOMMON
    cost = 3
    dmg, dmg_up = 30, 38

    def use(self, source, targets, combat=None) -> None:
        killed = False
        for target in targets:
            if _alive(target):
                result = _deal_attack(source, target, self._damage())
                if result.get("killed"):
                    killed = True
        if killed:
            source.gain_stars(5)


class LunarBlast(STS2Card):
    """달의 폭발 — 0코스트, 4딜 (업글 5) × 이번 턴 플레이한 스킬 수."""
    card_id = "lunar_blast"
    name = "Lunar Blast"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        hits = combat.skills_played_this_turn if combat else 0
        dmg = 5 if self.upgraded else 4
        for _ in range(hits):
            for target in targets:
                if _alive(target):
                    _deal_attack(source, target, dmg)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        hits = combat.skills_played_this_turn if combat else 0
        return (5 if self.upgraded else 4) * hits


class ManifestAuthority(_Block):
    """권위 현현 — 7블록 (업글 8) + Colorless 카드풀 무작위 1장 손패 생성
    (업글: 강화 상태로 생성)."""
    card_id = "manifest_authority"
    name = "Manifest Authority"
    rarity = Rarity.UNCOMMON
    cost = 1
    blk, blk_up = 7, 8

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is None:
            return
        from sts2_sim.cards.colorless import _COLORLESS_GENERATABLE_IDS
        if not _COLORLESS_GENERATABLE_IDS:
            return
        cid = combat.rng.choice(_COLORLESS_GENERATABLE_IDS)
        combat.generate_card(cid, upgraded=self.upgraded, to="hand")


class Monologue(STS2Card):
    """독백 — 0코스트: 이후 카드 플레이마다 힘 +1, 턴 종료 시 전부 회수
    (업글: Retain)."""
    card_id = "monologue"
    name = "Monologue"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0

    def upgrade(self) -> None:
        super().upgrade()
        self.retains = True  # AddKeyword(Retain)
        self._retains_permanent = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import MonologueP
        source.apply_power(MonologueP(1, source_card=self))


class Orbit(_CostDownOnUpgrade, STS2Card):
    """궤도 — 2코스트(업글 1) 파워: 에너지 누적 4 소모마다 에너지 +1."""
    card_id = "orbit"
    name = "Orbit"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import OrbitP
        source.apply_power(OrbitP(1))


class PaleBlueDot(STS2Card):
    """창백한 푸른 점 — 파워: 한 턴 5장 플레이 시 다음 턴 드로우 +1 (업글 +2)."""
    card_id = "pale_blue_dot"
    name = "Pale Blue Dot"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import PaleBlueDotP
        source.apply_power(PaleBlueDotP(2 if self.upgraded else 1))


class Parry(STS2Card):
    """받아넘기기 — 파워: SovereignBlade 플레이 시 블록 10 (업글 14)."""
    card_id = "parry"
    name = "Parry"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import ParryP
        source.apply_power(ParryP(14 if self.upgraded else 10))


class ParticleWall(_Block):
    """입자 방벽 — 0코스트/별 2, 9블록 (업글 12). 버려지지 않고 손패로."""
    card_id = "particle_wall"
    name = "Particle Wall"
    rarity = Rarity.UNCOMMON
    cost = 0
    star_cost = 2
    settle_to = "hand"  # 원본 GetResultPileTypeAndPosition → Hand/Bottom
    blk, blk_up = 9, 12


class Prophesize(STS2Card):
    """예언 — 2코스트 드로우 6 (업글 9)."""
    card_id = "prophesize"
    name = "Prophesize"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        if combat:
            combat.draw_cards(9 if self.upgraded else 6)


class Quasar(STS2Card):
    """퀘이사 — 0코스트/별 2, Colorless 카드풀에서 서로 다른 무작위 3장 중
    1장을 손패에 생성(업글: 3장 모두 강화 상태로 뽑음). [선택→무작위]
    (원본 Quasar — CardSelectCmd.FromChooseACardScreen, canSkip)."""
    card_id = "quasar"
    name = "Quasar"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0
    star_cost = 2

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        from sts2_sim.cards.colorless import _COLORLESS_GENERATABLE_IDS
        n = min(3, len(_COLORLESS_GENERATABLE_IDS))
        if n <= 0:
            return
        cid = combat.rng.choice(combat.rng.sample(_COLORLESS_GENERATABLE_IDS, n))
        combat.generate_card(cid, upgraded=self.upgraded, to="hand")


class Radiate(STS2Card):
    """방사 — 0코스트, 전체 3딜 (업글 4) × 이번 턴 획득한 별 수."""
    card_id = "radiate"
    name = "Radiate"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 0
    target_all = True

    def use(self, source, targets, combat=None) -> None:
        hits = combat.stars_gained_this_turn if combat else 0
        dmg = 4 if self.upgraded else 3
        for _ in range(hits):
            for target in targets:
                if _alive(target):
                    _deal_attack(source, target, dmg)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        hits = combat.stars_gained_this_turn if combat else 0
        return (4 if self.upgraded else 3) * hits


class Reflect(_Block):
    """반사 — 1코스트/별 3, 15블록 (업글 20) + 이번 턴 막은 공격 피해 반사."""
    card_id = "reflect"
    name = "Reflect"
    rarity = Rarity.UNCOMMON
    cost = 1
    star_cost = 3
    blk, blk_up = 15, 20

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import ReflectP
        super().use(source, targets, combat)
        source.apply_power(ReflectP(1))


class Resonance(STS2Card):
    """공명 — 1코스트/별 2, 힘 +1 (업글 +2) + 모든 적 힘 -1."""
    card_id = "resonance"
    name = "Resonance"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    star_cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Strength
        source.apply_power(Strength(2 if self.upgraded else 1))
        if combat:
            for enemy in combat.alive_enemies:
                enemy.apply_power(Strength(-1), applier=source)


class RoyalGamble(STS2Card):
    """왕의 도박 — 0코스트/별 5, 별 +9, 소모 (업글: Retain)."""
    card_id = "royal_gamble"
    name = "Royal Gamble"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0
    star_cost = 5
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.retains = True  # AddKeyword(Retain)
        self._retains_permanent = True

    def use(self, source, targets, combat=None) -> None:
        source.gain_stars(9)


class ShiningStrike(_Attack):
    """빛나는 일격 — 8딜 (업글 11) + 별 +2. 버림 대신 뽑을 더미 맨 위로.
    Strike 태그."""
    card_id = "shining_strike"
    name = "Shining Strike"
    rarity = Rarity.UNCOMMON
    cost = 1
    tags = frozenset({"strike"})
    settle_to = "draw_top"  # 원본 GetResultPileTypeAndPosition → Draw/Top
    dmg, dmg_up = 8, 11

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        source.gain_stars(2)


class SpectrumShift(_CostDownOnUpgrade, STS2Card):
    """스펙트럼 변이 — 2코스트(업글 1) 파워: 매 턴 드로우 전 Colorless 1장 손패 생성."""
    card_id = "spectrum_shift"
    name = "Spectrum Shift"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import SpectrumShiftP
        source.apply_power(SpectrumShiftP(1))


class Stardust(STS2Card):
    """별먼지 — 0코스트/별 X: 무작위 적에게 5딜 (업글 7) × X."""
    card_id = "stardust"
    name = "Stardust"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 0
    star_x_cost = True  # HasStarCostX — 플레이 시 별 전부 소비

    def __init__(self):
        super().__init__()
        self.star_x_value = 0

    def use(self, source, targets, combat=None) -> None:
        dmg = 7 if self.upgraded else 5
        for _ in range(self.star_x_value):
            enemies = combat.alive_enemies if combat else [t for t in targets if _alive(t)]
            if not enemies:
                break
            target = combat.rng.choice(enemies) if combat else enemies[0]
            _deal_attack(source, target, dmg)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        stars = getattr(player, "stars", 0)
        return (7 if self.upgraded else 5) * stars


class SummonForth(STS2Card):
    """소환 — 손패 밖의 모든 SovereignBlade를 손패로 + Forge 8 (업글 11)."""
    card_id = "summon_forth"
    name = "Summon Forth"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        for pile in (combat.draw_pile, combat.discard_pile, combat.exhaust_pile):
            for card in [c for c in pile if isinstance(c, SovereignBlade)]:
                if len(combat.hand) >= MAX_HAND_SIZE:
                    break
                pile.remove(card)
                combat.hand.append(card)
        _forge(source, combat, 11 if self.upgraded else 8)


class Supermassive(STS2Card):
    """초대질량 — (5 + 3×전투 중 생성된 카드 수)딜 (업글 5+4×)."""
    card_id = "supermassive"
    name = "Supermassive"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 1

    def _damage(self, combat) -> int:
        extra = 4 if self.upgraded else 3
        count = combat.cards_generated_this_combat if combat else 0
        return 5 + extra * count

    def use(self, source, targets, combat=None) -> None:
        dmg = self._damage(combat)
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, dmg)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage(combat)


class Terraforming(STS2Card):
    """지형 개조 — Vigor 6 (업글 8)."""
    card_id = "terraforming"
    name = "Terraforming"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Vigor
        source.apply_power(Vigor(8 if self.upgraded else 6))


# ══════════════════════════════════════════
# Rare (25)
# ══════════════════════════════════════════

class Arsenal(STS2Card):
    """무기고 — 파워: 카드가 생성될 때마다 힘 +1 (업글: Innate)."""
    card_id = "arsenal"
    name = "Arsenal"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def upgrade(self) -> None:
        super().upgrade()
        self.is_innate = True  # AddKeyword(Innate)

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import ArsenalP
        source.apply_power(ArsenalP(1))


class BeatIntoShape(STS2Card):
    """두들겨 만들기 — 5딜 (업글 7) + Forge (5 + 5×대상이 이번 턴 이미 받은
    파워드 히트 수) (업글 7+7×)."""
    card_id = "beat_into_shape"
    name = "Beat into Shape"
    card_type = CardType.ATTACK
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        base = 7 if self.upgraded else 5
        for target in targets[:1]:
            if not _alive(target):
                continue
            prior_hits = getattr(target, "_hits_taken_this_turn", 0)
            _deal_attack(source, target, base)
            # 원본: Calculate(공격 후 히트 수) - 방금 히트 수 = base + extra×이전 히트
            _forge(source, combat, base + base * prior_hits)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return 7 if self.upgraded else 5


class BigBang(STS2Card):
    """빅뱅 — 0코스트: 드로우 1 + 별 +1 + 에너지 +1 + Forge 5, 소모
    (업글: Innate)."""
    card_id = "big_bang"
    name = "Big Bang"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 0
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.is_innate = True  # AddKeyword(Innate)

    def use(self, source, targets, combat=None) -> None:
        if combat:
            combat.draw_cards(1)
        source.gain_stars(1)
        source.gain_energy(1)
        _forge(source, combat, 5)


class Bombardment(_Attack):
    """폭격 — 3코스트 18딜 (업글 24), 소모. 소모 더미에 있으면 매 턴
    시작 시 자동 플레이 (원본 AfterAutoPrePlayPhaseEnteredEarly)."""
    card_id = "bombardment"
    name = "Bombardment"
    rarity = Rarity.RARE
    cost = 3
    exhausts = True
    dmg, dmg_up = 18, 24

    def on_pre_play_phase(self, combat) -> None:
        if self in combat.exhaust_pile:
            combat.exhaust_pile.remove(self)
            combat.auto_play(self)  # exhausts=True — 다시 소모 더미로


class BundleOfJoy(STS2Card):
    """기쁨 꾸러미 — Colorless 카드풀에서 서로 다른 무작위 3장(업글 4장)을
    손패에 생성, 소모."""
    card_id = "bundle_of_joy"
    name = "Bundle of Joy"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        from sts2_sim.cards.colorless import _COLORLESS_GENERATABLE_IDS
        n = min(4 if self.upgraded else 3, len(_COLORLESS_GENERATABLE_IDS))
        for cid in combat.rng.sample(_COLORLESS_GENERATABLE_IDS, n):
            combat.generate_card(cid, to="hand")


class Comet(_Attack):
    """혜성 — 0코스트/별 5, 33딜 (업글 44) + 약화 3 + 취약 3."""
    card_id = "comet"
    name = "Comet"
    rarity = Rarity.RARE
    cost = 0
    star_cost = 5
    dmg, dmg_up = 33, 44

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Weak, Vulnerable
        super().use(source, targets, combat)
        for target in targets[:1]:
            if _alive(target) and hasattr(target, "apply_power"):
                target.apply_power(Weak(3), applier=source)
                target.apply_power(Vulnerable(3), applier=source)


class CrashLanding(_Attack):
    """불시착 — 전체 21딜 (업글 26) + 손패가 가득 찰 때까지 Debris 생성."""
    card_id = "crash_landing"
    name = "Crash Landing"
    rarity = Rarity.RARE
    cost = 1
    target_all = True
    dmg, dmg_up = 21, 26

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat:
            need = MAX_HAND_SIZE - len(combat.hand)
            if need > 0:
                combat.generate_card("debris", count=need, to="hand")


class DecisionsDecisions(STS2Card):
    """결정, 결정 — 0코스트/별 6: 드로우 3 (업글 5), 손패 스킬 1장을
    3회 자동 플레이, 소모. [선택→무작위]"""
    card_id = "decisions_decisions"
    name = "Decisions Decisions"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 0
    star_cost = 6
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        combat.draw_cards(5 if self.upgraded else 3)
        skills = [c for c in combat.hand
                  if c.card_type == CardType.SKILL and c.playable]
        if not skills:
            return
        card = combat.rng.choice(skills)
        for _ in range(3):
            if card in combat.hand:
                combat.hand.remove(card)
            elif card in combat.discard_pile:
                combat.discard_pile.remove(card)
            elif card in combat.exhaust_pile:
                combat.exhaust_pile.remove(card)  # 소모된 카드도 강제 재플레이(원본 AutoPlay)
            combat.auto_play(card)


class DyingStar(STS2Card):
    """죽어가는 별 — 1코스트/별 3, Ethereal: 전체 9딜 (업글 11) +
    임시 힘 -9 (업글 -11)."""
    card_id = "dying_star"
    name = "Dying Star"
    card_type = CardType.ATTACK
    rarity = Rarity.RARE
    cost = 1
    star_cost = 3
    target_all = True

    def __init__(self):
        super().__init__()
        self.is_ethereal = True  # CanonicalKeywords: Ethereal

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import TempStrength
        dmg = 11 if self.upgraded else 9
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, dmg)
        _apply_to_targets(source, targets, lambda: TempStrength(-dmg))

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return 11 if self.upgraded else 9


class ForegoneConclusion(STS2Card):
    """예정된 결말 — 다음 턴 드로우 전 뽑을 더미에서 2장 (업글 3장)을
    손패로. [선택→무작위]"""
    card_id = "foregone_conclusion"
    name = "Foregone Conclusion"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import ForegoneConclusionP
        source.apply_power(ForegoneConclusionP(3 if self.upgraded else 2))


class Genesis(STS2Card):
    """창세 — 2코스트 파워: 매 턴 별 +2 (업글 +3)."""
    card_id = "genesis"
    name = "Genesis"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import GenesisP
        source.apply_power(GenesisP(3 if self.upgraded else 2))


class Guards(STS2Card):
    """근위병 — 2코스트: 손패의 카드들을 MinionSacrifice로 변환, 소모
    (업글: 강화된 MinionSacrifice). [선택(임의 수)→전체 변환]"""
    card_id = "guards"
    name = "Guards"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 2
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        for i, _ in enumerate(combat.hand):
            minion = MinionSacrifice()
            if self.upgraded:
                minion.upgrade()
            combat.hand[i] = minion
            _notify_card_generated(combat, minion)  # 원본 CardCmd.Transform


class HeavenlyDrill(STS2Card):
    """천상의 드릴 — X코스트: 8딜 (업글 10) × X (X ≥ 4이면 ×2X)."""
    card_id = "heavenly_drill"
    name = "Heavenly Drill"
    card_type = CardType.ATTACK
    rarity = Rarity.RARE
    cost = 0
    x_cost = True
    ENERGY_THRESHOLD = 4  # 원본 EnergyVar(4)

    def use(self, source, targets, combat=None) -> None:
        hits = self.x_value
        if hits >= self.ENERGY_THRESHOLD:
            hits *= 2
        dmg = 10 if self.upgraded else 8
        for _ in range(hits):
            for target in targets:
                if _alive(target):
                    _deal_attack(source, target, dmg)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        energy = getattr(player, "energy", 0)
        hits = energy * 2 if energy >= self.ENERGY_THRESHOLD else energy
        return (10 if self.upgraded else 8) * hits


class HeirloomHammer(_Attack):
    """가보 망치 — 2코스트 20딜 (업글 25) + 손패의 Colorless 카드 1장을 복제해
    손패에 추가 (원본 CardSelectCmd.FromHand filter VisualCardPool.IsColorless).
    [선택→무작위](대상 카드가 여럿이면 무작위 1장)."""
    card_id = "heirloom_hammer"
    name = "Heirloom Hammer"
    rarity = Rarity.RARE
    cost = 2
    dmg, dmg_up = 20, 25

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is None:
            return
        from sts2_sim.cards.colorless import _COLORLESS_IDS
        candidates = [c for c in combat.hand if c.card_id in _COLORLESS_IDS]
        if not candidates:
            return
        chosen = combat.rng.choice(candidates)
        combat.generate_card(chosen.card_id, upgraded=chosen.upgraded, to="hand")


class IAmInvincible(_Block):
    """나는 무적이다 — 10블록 (업글 13). 턴 종료 시 뽑을 더미 맨 위면
    자동 플레이 (원본 AfterAutoPostPlayPhaseEntered)."""
    card_id = "i_am_invincible"
    name = "I Am Invincible"
    rarity = Rarity.RARE
    cost = 1
    blk, blk_up = 10, 13

    def on_post_play_phase(self, combat) -> None:
        if combat.draw_pile and combat.draw_pile[-1] is self:
            combat.draw_pile.pop()
            combat.auto_play(self)


class MakeItSo(_Attack):
    """그리 하라 — 0코스트 6딜 (업글 9). 손패 밖에서, 이번 턴 스킬을
    3장 플레이할 때마다 손패로 돌아온다 (원본 AfterCardPlayedLate)."""
    card_id = "make_it_so"
    name = "Make It So"
    rarity = Rarity.RARE
    cost = 0
    SKILL_INTERVAL = 3  # 원본 CardsVar(3)
    dmg, dmg_up = 6, 9

    def on_ally_card_played(self, card, paid, combat) -> None:
        if card.card_type != CardType.SKILL or self in combat.hand:
            return
        if combat.skills_played_this_turn % self.SKILL_INTERVAL != 0:
            return
        for pile in (combat.discard_pile, combat.draw_pile):
            if self in pile:
                if len(combat.hand) < MAX_HAND_SIZE:
                    pile.remove(self)
                    combat.hand.append(self)
                elif pile is not combat.discard_pile:
                    # 원본 CardPileCmd.Add: 손패가 가득 차면 대상 파일이 Discard로
                    # 리다이렉트되고, 원래 파일(뽑을더미 포함)에서 무조건 빠져나온다.
                    pile.remove(self)
                    combat.discard_pile.append(self)
                return


class MonarchsGaze(_CostDownOnUpgrade, STS2Card):
    """군주의 시선 — 2코스트(업글 1) 파워: 내 파워드 공격 명중마다
    대상 임시 힘 -1."""
    card_id = "monarchs_gaze"
    name = "Monarch's Gaze"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import MonarchsGazeP
        source.apply_power(MonarchsGazeP(1))


class NeutronAegis(STS2Card):
    """중성자 방패 — 1코스트/별 5 파워: Plating 8 (업글 11)."""
    card_id = "neutron_aegis"
    name = "Neutron Aegis"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1
    star_cost = 5

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Plating
        source.apply_power(Plating(11 if self.upgraded else 8))


class PillarOfCreation(STS2Card):
    """창조의 기둥 — 파워: 카드가 생성될 때마다 블록 +3 (업글 +4)."""
    card_id = "pillar_of_creation"
    name = "Pillar of Creation"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import PillarOfCreationP
        source.apply_power(PillarOfCreationP(4 if self.upgraded else 3))


class Royalties(STS2Card):
    """인세 — 파워: 전투 승리 시 골드 +30 (업글 +40)."""
    card_id = "royalties"
    name = "Royalties"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import RoyaltiesP
        source.apply_power(RoyaltiesP(40 if self.upgraded else 30))


class SeekingEdge(STS2Card):
    """추적하는 칼날 — 파워: SovereignBlade가 전체 공격이 된다 + Forge 7
    (업글 11)."""
    card_id = "seeking_edge"
    name = "Seeking Edge"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import SeekingEdgeP
        source.apply_power(SeekingEdgeP(1))
        _forge(source, combat, 11 if self.upgraded else 7)


class SevenStars(_CostDownOnUpgrade, _Attack):
    """일곱 별 — 2코스트(업글 1)/별 7, 전체 7딜×7."""
    card_id = "seven_stars"
    name = "Seven Stars"
    rarity = Rarity.RARE
    cost = 2
    star_cost = 7
    target_all = True
    dmg, dmg_up = 7, 7
    hits = 7


class SwordSage(_CostDownOnUpgrade, STS2Card):
    """검성 — 2코스트(업글 1) 파워: 모든 SovereignBlade Replay +1."""
    card_id = "sword_sage"
    name = "Sword Sage"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import SwordSageP
        source.apply_power(SwordSageP(1))


class TheSmith(STS2Card):
    """대장장이 — 1코스트/별 4: Forge 30 (업글 40)."""
    card_id = "the_smith"
    name = "The Smith"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1
    star_cost = 4

    def use(self, source, targets, combat=None) -> None:
        _forge(source, combat, 40 if self.upgraded else 30)


class Tyranny(STS2Card):
    """폭정 — 파워: 드로우 +1, 턴 시작마다 손패 1장 소모 (업글: Innate).
    [선택→무작위]"""
    card_id = "tyranny"
    name = "Tyranny"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def upgrade(self) -> None:
        super().upgrade()
        self.is_innate = True  # AddKeyword(Innate)

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import TyrannyP
        source.apply_power(TyrannyP(1))


class VoidForm(STS2Card):
    """공허의 형상 — 3코스트 파워, Ethereal (업글: Ethereal 제거):
    매 턴 처음 2장의 카드 비용(에너지/별) 0. 플레이 시 턴 종료."""
    card_id = "void_form"
    name = "Void Form"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 3

    def __init__(self):
        super().__init__()
        self.is_ethereal = True  # CanonicalKeywords: Ethereal

    def upgrade(self) -> None:
        super().upgrade()
        self.is_ethereal = False  # RemoveKeyword(Ethereal)

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import VoidFormP
        source.apply_power(VoidFormP(2))
        # 플레이한 턴에는 할인 없음 (원본 HideTemporaryZeroCostVisual —
        # 다음 턴 시작 시 0으로 리셋)
        power = source._powers.get("void_form")
        if power is not None:
            power._plays_this_turn = 999999999
        if combat is not None:
            combat.end_turn_requested = True  # 원본 PlayerCmd.EndTurn


# ══════════════════════════════════════════
# Ancient (2)
# ══════════════════════════════════════════

class MeteorShower(_Attack):
    """유성우 — 0코스트/별 2, 전체 14딜 (업글 21) + 약화 2 + 취약 2."""
    card_id = "meteor_shower"
    name = "Meteor Shower"
    rarity = Rarity.ANCIENT
    cost = 0
    star_cost = 2
    target_all = True
    dmg, dmg_up = 14, 21

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Weak, Vulnerable
        super().use(source, targets, combat)
        _apply_to_targets(source, targets, lambda: Weak(2))
        _apply_to_targets(source, targets, lambda: Vulnerable(2))


class TheSealedThrone(_CostDownOnUpgrade, STS2Card):
    """봉인된 왕좌 — 1코스트(업글 0)/별 3 파워: 카드 플레이마다 별 +1."""
    card_id = "the_sealed_throne"
    name = "The Sealed Throne"
    card_type = CardType.POWER
    rarity = Rarity.ANCIENT
    cost = 1
    star_cost = 3

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import SealedThroneP
        source.apply_power(SealedThroneP(1))


# ══════════════════════════════════════════
# 등록
# ══════════════════════════════════════════

_REGENT_CARDS = [
    # Common (20)
    AstralPulse, Begone, CelestialMight, CloakOfStars, CollisionCourse,
    CosmicIndifference, CrescentSpear, CrushUnder, GatherLight, Glitterstream,
    Glow, GuidingStar, HiddenCache, KnowThyPlace, Patter, PhotonCut,
    RefineBlade, SolarStrike, SpoilsOfBattle, WroughtInWar,
    # Uncommon (35)
    Alignment, BlackHole, Bulwark, Charge, ChildOfTheStars, Conqueror,
    Convergence, Devastate, Furnace, GammaBlast, Glimmer, Hegemony,
    KinglyKick, KinglyPunch, KnockoutBlow, LunarBlast, ManifestAuthority,
    Monologue, Orbit, PaleBlueDot, Parry, ParticleWall, PillarOfCreation,
    Prophesize, Quasar, Radiate, Reflect, Resonance, RoyalGamble,
    ShiningStrike, SpectrumShift, Stardust, SummonForth, Supermassive,
    Terraforming,
    # Rare (25)
    Arsenal, BeatIntoShape, BigBang, Bombardment, BundleOfJoy, Comet,
    CrashLanding, DecisionsDecisions, DyingStar, ForegoneConclusion, Genesis,
    Guards, HeavenlyDrill, HeirloomHammer, IAmInvincible, MakeItSo,
    MonarchsGaze, NeutronAegis, Royalties, SeekingEdge, SevenStars, SwordSage,
    TheSmith, Tyranny, VoidForm,
    # Ancient (2)
    MeteorShower, TheSealedThrone,
    # 토큰
    SovereignBlade, MinionStrike, MinionDiveBomb, MinionSacrifice, Debris,
]

CARD_REGISTRY.update({cls.card_id: cls for cls in _REGENT_CARDS})

# 보상 풀: Ancient/Token 제외
REGENT_POOL_BY_RARITY = {
    Rarity.COMMON: sorted(
        [c.card_id for c in _REGENT_CARDS if c.rarity == Rarity.COMMON]),
    Rarity.UNCOMMON: sorted(
        [c.card_id for c in _REGENT_CARDS if c.rarity == Rarity.UNCOMMON]),
    Rarity.RARE: sorted(
        [c.card_id for c in _REGENT_CARDS if c.rarity == Rarity.RARE]),
}
