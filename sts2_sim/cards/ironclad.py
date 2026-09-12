"""
Ironclad 카드 풀 — 디컴파일 MegaCrit.Sts2.Core.Models.CardPools.IroncladCardPool 이식.

원본 90종 중:
  - Strike/Defend/Bash 3종은 models/sts2_card.py에 기존 구현
  - 멀티플레이 전용 5종 제외: Blaze, DemonicShield, Midnight, Outrage, Tank
  - 나머지 82종 + GiantRock 토큰(PrimalForce 생성물)을 여기서 구현

모든 수치는 디컴파일 .cs의 CanonicalVars/OnUpgrade 그대로.
단순화 표기: 원본이 카드 선택 UI를 요구하는 곳(Armaments/Brand/Headbutt 등)은
무작위 선택으로 대체하고 주석에 [선택→무작위] 표기.
"""
from __future__ import annotations

from sts2_sim.models.sts2_card import (
    STS2Card, CardType, Rarity, CARD_REGISTRY, _deal_attack, create_card,
)

MAX_HAND_SIZE = 10  # CardPile.MaxCardsInHand


def _alive(target) -> bool:
    return not getattr(target, "is_gone", False) and not target.is_dead


def _count_strikes(combat) -> int:
    """전투 내 모든 파일(핸드/드로우/버림/소모)의 Strike 태그 카드 수."""
    piles = combat.hand + combat.draw_pile + combat.discard_pile + combat.exhaust_pile
    return sum(1 for c in piles if "strike" in c.tags)


# ══════════════════════════════════════════
# 공용 베이스 (보일러플레이트 제거)
# ══════════════════════════════════════════

class _Attack(STS2Card):
    """단순 공격 베이스: dmg/dmg_up × hits(업글 시 hits_up)."""
    card_type = CardType.ATTACK
    dmg = 0
    dmg_up = 0
    hits = 1
    hits_up = 0  # 0이면 hits 유지

    def _damage(self) -> int:
        return self.dmg_up if self.upgraded else self.dmg

    def _hits(self) -> int:
        return self.hits_up if (self.upgraded and self.hits_up) else self.hits

    def use(self, source, targets, combat=None) -> None:
        for _ in range(self._hits()):
            for target in targets:
                if _alive(target):
                    _deal_attack(source, target, self._damage())

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage() * self._hits()


class _Block(STS2Card):
    """단순 블록 베이스: blk/blk_up."""
    card_type = CardType.SKILL
    blk = 0
    blk_up = 0

    def _block(self) -> int:
        return self.blk_up if self.upgraded else self.blk

    def use(self, source, targets, combat=None) -> None:
        source.gain_block(self._block())

    def block_estimate(self, player, combat=None) -> int:
        return self._block()


class _CostDownOnUpgrade:
    """업그레이드가 비용 -1인 카드용 믹스인."""

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)


# ══════════════════════════════════════════
# Common
# ══════════════════════════════════════════

class Anger(_Attack):
    """분노 — 0코스트 6딜(업글 8), 사본을 버림 더미에 추가."""
    card_id = "anger"
    name = "Anger"
    rarity = Rarity.COMMON
    cost = 0
    dmg, dmg_up = 6, 8

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is not None:
            clone = create_card(self.card_id)
            if self.upgraded:
                clone.upgrade()
            combat.discard_pile.append(clone)


class Armaments(_Block):
    """무장 — 5블록 + 핸드 카드 1장 업그레이드 [선택→무작위] (업글: 핸드 전체)."""
    card_id = "armaments"
    name = "Armaments"
    rarity = Rarity.COMMON
    cost = 1
    blk = blk_up = 5

    def use(self, source, targets, combat=None) -> None:
        source.gain_block(5)
        if combat is None:
            return
        upgradable = [c for c in combat.hand if c.is_upgradable]
        if self.upgraded:
            for card in upgradable:
                card.upgrade()
        elif upgradable:
            combat.rng.choice(upgradable).upgrade()


class BloodWall(_Block):
    """피의 벽 — HP 2 소모, 16블록 (업글 20)."""
    card_id = "blood_wall"
    name = "Blood Wall"
    rarity = Rarity.COMMON
    cost = 2
    blk, blk_up = 16, 20

    def use(self, source, targets, combat=None) -> None:
        source.lose_hp(2)
        source.gain_block(self._block())


class Bloodletting(STS2Card):
    """방혈 — 0코스트, HP 3 소모, 에너지 +2 (업글 +3)."""
    card_id = "bloodletting"
    name = "Bloodletting"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        source.lose_hp(3)
        source.gain_energy(3 if self.upgraded else 2)


class BodySlam(_CostDownOnUpgrade, STS2Card):
    """몸통 박치기 — 현재 블록만큼 데미지 (업글 0코스트)."""
    card_id = "body_slam"
    name = "Body Slam"
    card_type = CardType.ATTACK
    rarity = Rarity.COMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, source.block)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return player.block


class Breakthrough(_Attack):
    """돌파 — HP 1 소모, 모든 적에게 9딜 (업글 13)."""
    card_id = "breakthrough"
    name = "Breakthrough"
    rarity = Rarity.COMMON
    cost = 1
    target_all = True
    dmg, dmg_up = 9, 13

    def use(self, source, targets, combat=None) -> None:
        source.lose_hp(1)
        super().use(source, targets, combat)


class Cinder(_Attack):
    """잉걸불 — 18딜 (업글 24), 핸드에서 무작위 1장 소모."""
    card_id = "cinder"
    name = "Cinder"
    rarity = Rarity.COMMON
    cost = 2
    dmg, dmg_up = 18, 24

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is not None:
            combat.exhaust_from_hand(1)


class Havoc(_CostDownOnUpgrade, STS2Card):
    """대혼란 — 뽑을 카드 더미 맨 위 카드를 자동 플레이 후 소모 (업글 0코스트)."""
    card_id = "havoc"
    name = "Havoc"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        if not combat.draw_pile and combat.discard_pile:
            combat.draw_pile = combat.discard_pile
            combat.discard_pile = []
            combat.rng.shuffle(combat.draw_pile)
        if combat.draw_pile:
            top = combat.draw_pile.pop()
            combat.auto_play(top, force_exhaust=True)


class Headbutt(_Attack):
    """박치기 — 9딜 (업글 12), 버림 더미 카드 1장을 드로우 더미 맨 위로 [선택→무작위]."""
    card_id = "headbutt"
    name = "Headbutt"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 9, 12

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is not None and combat.discard_pile:
            card = combat.rng.choice(combat.discard_pile)
            combat.discard_pile.remove(card)
            combat.draw_pile.append(card)  # pop()이 맨 위 = 리스트 끝


class IronWave(_Attack):
    """무쇠 파도 — 5딜 + 5블록 (업글 7/7)."""
    card_id = "iron_wave"
    name = "Iron Wave"
    rarity = Rarity.COMMON
    cost = 1
    dmg, dmg_up = 5, 7

    def use(self, source, targets, combat=None) -> None:
        source.gain_block(7 if self.upgraded else 5)
        super().use(source, targets, combat)


class MoltenFist(_Attack):
    """용암 주먹 — 10딜 (업글 14), 소모. 대상이 취약이면 취약 2배."""
    card_id = "molten_fist"
    name = "Molten Fist"
    rarity = Rarity.COMMON
    cost = 1
    exhausts = True
    dmg, dmg_up = 10, 14

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Vulnerable
        super().use(source, targets, combat)
        for target in targets:
            if _alive(target):
                vuln = target.get_power_amount("vulnerable")
                if vuln > 0:
                    target.apply_power(Vulnerable(vuln), applier=source)


class PerfectedStrike(STS2Card):
    """완벽한 타격 — 6 + 2×(전투 내 Strike 카드 수) 딜 (업글 +3×)."""
    card_id = "perfected_strike"
    name = "Perfected Strike"
    card_type = CardType.ATTACK
    rarity = Rarity.COMMON
    cost = 2
    tags = frozenset({"strike"})

    def _damage(self, combat) -> int:
        extra = 3 if self.upgraded else 2
        strikes = _count_strikes(combat) if combat else 0
        return 6 + extra * strikes

    def use(self, source, targets, combat=None) -> None:
        # 자기 자신은 이미 핸드를 떠났으므로 +1 (원본 AllCards는 자신 포함)
        extra = 3 if self.upgraded else 2
        damage = 6 + extra * ((_count_strikes(combat) + 1) if combat else 1)
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, damage)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        # 추정 시점에는 자신이 핸드에 있어 _count_strikes에 이미 포함됨
        return self._damage(combat)


class PommelStrike(_Attack):
    """자루 치기 — 9딜 + 1드로우 (업글 10딜 + 2드로우)."""
    card_id = "pommel_strike"
    name = "Pommel Strike"
    rarity = Rarity.COMMON
    cost = 1
    tags = frozenset({"strike"})
    dmg, dmg_up = 9, 10

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is not None:
            combat.draw_cards(2 if self.upgraded else 1)


class SetupStrike(_Attack):
    """셋업 스트라이크 — 7딜 (업글 9) + 이번 턴 힘 +3 (업글 +4)."""
    card_id = "setup_strike"
    name = "Setup Strike"
    rarity = Rarity.COMMON
    cost = 1
    tags = frozenset({"strike"})
    dmg, dmg_up = 7, 9

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import TempStrength
        super().use(source, targets, combat)
        source.apply_power(TempStrength(4 if self.upgraded else 3))


class SwordBoomerang(_Attack):
    """검 부메랑 — 무작위 적에게 3딜 ×3회 (업글 ×4회)."""
    card_id = "sword_boomerang"
    name = "Sword Boomerang"
    rarity = Rarity.COMMON
    cost = 1
    dmg = dmg_up = 3
    hits, hits_up = 3, 4

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return super().use(source, targets, combat)
        for _ in range(self._hits()):
            enemies = [e for e in combat.alive_enemies if _alive(e)]
            if not enemies:
                return
            _deal_attack(source, combat.rng.choice(enemies), self._damage())


class Thunderclap(_Attack):
    """천둥소리 — 모든 적에게 4딜 (업글 7) + 취약 1."""
    card_id = "thunderclap"
    name = "Thunderclap"
    rarity = Rarity.COMMON
    cost = 1
    target_all = True
    dmg, dmg_up = 4, 7
    vuln_setup = 3

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Vulnerable
        super().use(source, targets, combat)
        for target in targets:
            if _alive(target):
                target.apply_power(Vulnerable(1), applier=source)


class Tremble(STS2Card):
    """전율 — 취약 3 (업글 4), 소모."""
    card_id = "tremble"
    name = "Tremble"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 1
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Vulnerable
        target = None
        if combat is not None and combat.alive_enemies:
            target = min(combat.alive_enemies, key=lambda m: m.current_hp)
        if target is not None:
            target.apply_power(Vulnerable(4 if self.upgraded else 3), applier=source)


class TrueGrit(_Block):
    """참된 투지 — 7블록 (업글 9) + 핸드 무작위 1장 소모 (업글은 원본 '선택')."""
    card_id = "true_grit"
    name = "True Grit"
    rarity = Rarity.COMMON
    cost = 1
    blk, blk_up = 7, 9

    def use(self, source, targets, combat=None) -> None:
        source.gain_block(self._block())
        if combat is not None:
            combat.exhaust_from_hand(1)


class TwinStrike(_Attack):
    """쌍둥이 타격 — 5딜 ×2 (업글 7×2)."""
    card_id = "twin_strike"
    name = "Twin Strike"
    rarity = Rarity.COMMON
    cost = 1
    tags = frozenset({"strike"})
    dmg, dmg_up = 5, 7
    hits = 2


# ══════════════════════════════════════════
# Uncommon
# ══════════════════════════════════════════

class AshenStrike(STS2Card):
    """잿빛 타격 — 6 + 3×(소모 더미 카드 수) 딜 (업글 +4×)."""
    card_id = "ashen_strike"
    name = "Ashen Strike"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 1
    tags = frozenset({"strike"})

    def _damage(self, combat) -> int:
        extra = 4 if self.upgraded else 3
        count = len(combat.exhaust_pile) if combat else 0
        return 6 + extra * count

    def use(self, source, targets, combat=None) -> None:
        damage = self._damage(combat)
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, damage)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage(combat)


class BattleTrance(STS2Card):
    """전투 무아지경 — 0코스트 3드로우 (업글 4), 이번 턴 추가 드로우 불가."""
    card_id = "battle_trance"
    name = "Battle Trance"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import NoDraw
        if combat is not None:
            combat.draw_cards(4 if self.upgraded else 3)
        source.apply_power(NoDraw(1))


class Bludgeon(_Attack):
    """몽둥이질 — 32딜 (업글 42)."""
    card_id = "bludgeon"
    name = "Bludgeon"
    rarity = Rarity.UNCOMMON
    cost = 3
    dmg, dmg_up = 32, 42


class Bully(STS2Card):
    """괴롭히기 — 0코스트, 4 + 2×(대상 취약 수치) 딜 (업글 +3×)."""
    card_id = "bully"
    name = "Bully"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 0

    def _damage(self, target) -> int:
        extra = 3 if self.upgraded else 2
        vuln = target.get_power_amount("vulnerable") if target is not None else 0
        return 4 + extra * max(0, vuln)

    def use(self, source, targets, combat=None) -> None:
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, self._damage(target))

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage(target)


class BurningPact(STS2Card):
    """불타는 계약 — 핸드 1장 소모 [선택→무작위], 2드로우 (업글 3)."""
    card_id = "burning_pact"
    name = "Burning Pact"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat is not None:
            combat.exhaust_from_hand(1)
            combat.draw_cards(3 if self.upgraded else 2)


class Colossus(_Block):
    """거상 — 4블록 (업글 7) + Colossus 1 (취약 공격자의 데미지 절반)."""
    card_id = "colossus"
    name = "Colossus"
    rarity = Rarity.UNCOMMON
    cost = 1
    blk, blk_up = 4, 7

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Colossus as ColossusPower
        source.gain_block(self._block())
        source.apply_power(ColossusPower(1))


class Dismantle(_Attack):
    """해체 — 8딜 (업글 10), 대상이 취약이면 2회 타격."""
    card_id = "dismantle"
    name = "Dismantle"
    rarity = Rarity.UNCOMMON
    cost = 1
    dmg, dmg_up = 8, 10

    def use(self, source, targets, combat=None) -> None:
        for target in targets:
            if not _alive(target):
                continue
            hits = 2 if target.get_power_amount("vulnerable") > 0 else 1
            for _ in range(hits):
                if _alive(target):
                    _deal_attack(source, target, self._damage())

    def damage_estimate(self, player, combat=None, target=None) -> int:
        hits = 2 if (target is not None
                     and target.get_power_amount("vulnerable") > 0) else 1
        return self._damage() * hits


class Dominate(STS2Card):
    """지배 — 취약 1 (업글 2) 부여 후, 대상의 취약 총량만큼 힘 획득. 소모."""
    card_id = "dominate"
    name = "Dominate"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Vulnerable, Strength
        target = None
        if combat is not None and combat.alive_enemies:
            target = min(combat.alive_enemies, key=lambda m: m.current_hp)
        if target is None:
            return
        target.apply_power(Vulnerable(2 if self.upgraded else 1), applier=source)
        vuln = target.get_power_amount("vulnerable")
        if vuln > 0:
            source.apply_power(Strength(vuln))


class DrumOfBattle(STS2Card):
    """전투의 북 — 2드로우. 이 카드가 소모되면 에너지 +2 (업글 +3)."""
    card_id = "drum_of_battle"
    name = "Drum of Battle"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat is not None:
            combat.draw_cards(2)

    def on_exhausted(self, combat) -> None:
        combat.player.gain_energy(3 if self.upgraded else 2)


class EvilEye(_Block):
    """사악한 눈 — 8블록 (업글 11). 이번 턴 카드를 소모했으면 2회 획득."""
    card_id = "evil_eye"
    name = "Evil Eye"
    rarity = Rarity.UNCOMMON
    cost = 1
    blk, blk_up = 8, 11

    def use(self, source, targets, combat=None) -> None:
        times = 2 if (combat is not None
                      and combat.cards_exhausted_this_turn > 0) else 1
        for _ in range(times):
            source.gain_block(self._block())


class ExpectAFight(_CostDownOnUpgrade, STS2Card):
    """싸움 예감 — 핸드의 공격 카드 수만큼 에너지 획득, 이후 이번 턴 에너지 획득 불가.
    (업글 1코스트)"""
    card_id = "expect_a_fight"
    name = "Expect a Fight"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import NoEnergyGain
        if combat is not None:
            attacks = sum(1 for c in combat.hand if c.card_type == CardType.ATTACK)
            source.gain_energy(attacks)
        source.apply_power(NoEnergyGain(1))


class FeelNoPain(STS2Card):
    """고통 감내 — 파워: 카드 소모 시마다 블록 +3 (업글 +4)."""
    card_id = "feel_no_pain"
    name = "Feel No Pain"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import FeelNoPain as FNP
        source.apply_power(FNP(4 if self.upgraded else 3))


class FightMe(_Attack):
    """덤벼라 — 5딜 ×2 (업글 6×2), 자신 힘 +3 (업글 +4), 대상 힘 +1."""
    card_id = "fight_me"
    name = "Fight Me"
    rarity = Rarity.UNCOMMON
    cost = 2
    dmg, dmg_up = 5, 6
    hits = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Strength
        super().use(source, targets, combat)
        source.apply_power(Strength(4 if self.upgraded else 3))
        for target in targets:
            if _alive(target):
                target.apply_power(Strength(1), applier=source)


class FlameBarrier(_Block):
    """화염 방벽 — 12블록 (업글 16) + 이번 턴 피격 시 4 반격 (업글 6)."""
    card_id = "flame_barrier"
    name = "Flame Barrier"
    rarity = Rarity.UNCOMMON
    cost = 2
    blk, blk_up = 12, 16

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import FlameBarrier as FB
        source.gain_block(self._block())
        source.apply_power(FB(6 if self.upgraded else 4))


class ForgottenRitual(STS2Card):
    """잊힌 의식 — 이번 턴 카드를 소모했으면 에너지 +3 (업글 +4). 소모."""
    card_id = "forgotten_ritual"
    name = "Forgotten Ritual"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat is not None and combat.cards_exhausted_this_turn > 0:
            source.gain_energy(4 if self.upgraded else 3)


class Hemokinesis(_Attack):
    """혈액 조작 — HP 2 소모, 15딜 (업글 20)."""
    card_id = "hemokinesis"
    name = "Hemokinesis"
    rarity = Rarity.UNCOMMON
    cost = 1
    dmg, dmg_up = 15, 20

    def use(self, source, targets, combat=None) -> None:
        source.lose_hp(2)
        super().use(source, targets, combat)


class HowlFromBeyond(_Attack):
    """저편의 울부짖음 — 모든 적에게 18딜 (업글 24). 소모되면 자동 재발동."""
    card_id = "howl_from_beyond"
    name = "Howl from Beyond"
    rarity = Rarity.UNCOMMON
    cost = 3
    target_all = True
    dmg, dmg_up = 18, 24

    def on_exhausted(self, combat) -> None:
        # 원본: 소모 더미에 들어가면 자동 플레이 (소모 더미에 유지)
        targets = [e for e in combat.alive_enemies if _alive(e)]
        if targets:
            self.use(combat.player, targets, combat)


class InfernalBlade(_CostDownOnUpgrade, STS2Card):
    """지옥 칼날 — 무작위 공격 카드를 핸드에 생성 (이번 턴 0코스트). 소모.
    (업글 0코스트)"""
    card_id = "infernal_blade"
    name = "Infernal Blade"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        pool = [cid for cid in IRONCLAD_ATTACK_IDS]
        card = create_card(combat.rng.choice(pool))
        if card is not None:
            card.cost = 0
            combat.hand.append(card)


class Inferno(STS2Card):
    """업화 — 파워: 자기 턴 HP 손실 시 모든 적에게 6 피해 (업글 9).
    플레이할 때마다 턴 시작 자해 +1 누적."""
    card_id = "inferno"
    name = "Inferno"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Inferno as InfernoPower
        source.apply_power(InfernoPower(9 if self.upgraded else 6))
        source._powers["inferno"].self_damage += 1


class Inflame(STS2Card):
    """타오르는 투지 — 파워: 힘 +2 (업글 +3)."""
    card_id = "inflame"
    name = "Inflame"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Strength
        source.apply_power(Strength(3 if self.upgraded else 2))


class Juggling(STS2Card):
    """저글링 — 파워: 매 턴 3번째 공격 카드의 사본 1장 획득 (업글: 선천성)."""
    card_id = "juggling"
    name = "Juggling"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Juggling as JugglingPower
        source.apply_power(JugglingPower(1))

    def upgrade(self) -> None:
        super().upgrade()
        self.is_innate = True


class Pillage(_Attack):
    """약탈 — 6딜 (업글 9), 공격 카드가 아닌 카드가 나올 때까지 드로우."""
    card_id = "pillage"
    name = "Pillage"
    rarity = Rarity.UNCOMMON
    cost = 1
    dmg, dmg_up = 6, 9

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is None:
            return
        while len(combat.hand) < MAX_HAND_SIZE:
            before = len(combat.hand)
            combat.draw_cards(1)
            if len(combat.hand) == before:  # 더 뽑을 카드 없음
                break
            if combat.hand[-1].card_type != CardType.ATTACK:
                break


class Rage(STS2Card):
    """분노의 격류 — 0코스트: 이번 턴 공격 카드 플레이마다 블록 +3 (업글 +5)."""
    card_id = "rage"
    name = "Rage"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Rage as RagePower
        source.apply_power(RagePower(5 if self.upgraded else 3))


class Rampage(STS2Card):
    """광란 — 9딜, 플레이할 때마다 이 카드 데미지 +5 (업글 +9). 런 전체 지속."""
    card_id = "rampage"
    name = "Rampage"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 1

    def __init__(self):
        super().__init__()
        self.bonus = 0

    def _damage(self) -> int:
        return 9 + self.bonus

    def use(self, source, targets, combat=None) -> None:
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, self._damage())
        self.bonus += 9 if self.upgraded else 5

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage()


class Rupture(STS2Card):
    """파열 — 파워: 카드로 HP를 잃을 때마다 힘 +1 (업글 +2)."""
    card_id = "rupture"
    name = "Rupture"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Rupture as RupturePower
        source.apply_power(RupturePower(2 if self.upgraded else 1))


class SecondWind(STS2Card):
    """재기의 바람 — 공격이 아닌 핸드 카드를 전부 소모, 1장당 5블록 (업글 7)."""
    card_id = "second_wind"
    name = "Second Wind"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        block = 7 if self.upgraded else 5
        non_attacks = [c for c in combat.hand if c.card_type != CardType.ATTACK]
        for card in non_attacks:
            combat.hand.remove(card)
            combat._exhaust_card(card)
            source.gain_block(block)

    def block_estimate(self, player, combat=None) -> int:
        if combat is None:
            return 0
        block = 7 if self.upgraded else 5
        return block * sum(1 for c in combat.hand
                           if c.card_type != CardType.ATTACK and c is not self)


class Spite(_Attack):
    """앙심 — 0코스트 5딜. 이번 턴 HP를 잃었으면 2회 (업글 3회) 타격."""
    card_id = "spite"
    name = "Spite"
    rarity = Rarity.UNCOMMON
    cost = 0
    dmg = dmg_up = 5

    def _spite_hits(self, player) -> int:
        if player.hp_lost_this_turn > 0:
            return 3 if self.upgraded else 2
        return 1

    def use(self, source, targets, combat=None) -> None:
        for _ in range(self._spite_hits(source)):
            for target in targets:
                if _alive(target):
                    _deal_attack(source, target, self._damage())

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage() * self._spite_hits(player)


class Stampede(_CostDownOnUpgrade, STS2Card):
    """쇄도 — 파워: 턴 종료 시 손패의 무작위 공격 카드 1장 자동 플레이 (업글 1코스트)."""
    card_id = "stampede"
    name = "Stampede"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Stampede as StampedePower
        source.apply_power(StampedePower(1))


class Stomp(_Attack):
    """짓밟기 — 모든 적에게 12딜 (업글 15). 이번 턴 공격 플레이당 비용 -1."""
    card_id = "stomp"
    name = "Stomp"
    rarity = Rarity.UNCOMMON
    cost = 3
    target_all = True
    dmg, dmg_up = 12, 15

    def dynamic_cost(self, combat) -> int:
        return max(0, self.cost - combat.attacks_played_this_turn)


class StoneArmor(STS2Card):
    """돌 갑옷 — 파워: Plating 4 (업글 6)."""
    card_id = "stone_armor"
    name = "Stone Armor"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Plating
        source.apply_power(Plating(6 if self.upgraded else 4))


class Taunt(_Block):
    """도발 — 7블록 (업글 8) + 대상에게 취약 1 (업글 2)."""
    card_id = "taunt"
    name = "Taunt"
    rarity = Rarity.UNCOMMON
    cost = 1
    blk, blk_up = 7, 8

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Vulnerable
        source.gain_block(self._block())
        if combat is not None and combat.alive_enemies:
            target = min(combat.alive_enemies, key=lambda m: m.current_hp)
            target.apply_power(Vulnerable(2 if self.upgraded else 1), applier=source)


class Unrelenting(_Attack):
    """끈질김 — 14딜 (업글 20), 다음 공격 카드 비용 0."""
    card_id = "unrelenting"
    name = "Unrelenting"
    rarity = Rarity.UNCOMMON
    cost = 2
    dmg, dmg_up = 14, 20

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import FreeAttack
        super().use(source, targets, combat)
        source.apply_power(FreeAttack(1))


class Uppercut(_Attack):
    """어퍼컷 — 13딜 + 약화 1 + 취약 1 (업글 2/2)."""
    card_id = "uppercut"
    name = "Uppercut"
    rarity = Rarity.UNCOMMON
    cost = 2
    dmg = dmg_up = 13
    vuln_setup = 4

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Weak, Vulnerable
        super().use(source, targets, combat)
        amount = 2 if self.upgraded else 1
        for target in targets:
            if _alive(target):
                target.apply_power(Weak(amount), applier=source)
                target.apply_power(Vulnerable(amount), applier=source)


class Vicious(STS2Card):
    """악랄함 — 파워: 적에게 취약을 걸 때마다 1드로우 (업글 2)."""
    card_id = "vicious"
    name = "Vicious"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Vicious as ViciousPower
        source.apply_power(ViciousPower(2 if self.upgraded else 1))


class Whirlwind(_Attack):
    """회오리 — X코스트: 모든 적에게 5딜 (업글 8) ×X회."""
    card_id = "whirlwind"
    name = "Whirlwind"
    rarity = Rarity.UNCOMMON
    cost = 0
    x_cost = True
    target_all = True
    dmg, dmg_up = 5, 8

    def use(self, source, targets, combat=None) -> None:
        for _ in range(self.x_value):
            for target in targets:
                if _alive(target):
                    _deal_attack(source, target, self._damage())

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage() * player.energy


# ══════════════════════════════════════════
# Rare
# ══════════════════════════════════════════

class Aggression(STS2Card):
    """호전성 — 파워: 턴 시작 시 버림 더미의 공격 1장을 손패로 + 업그레이드
    (업글: 선천성)."""
    card_id = "aggression"
    name = "Aggression"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Aggression as AggressionPower
        source.apply_power(AggressionPower(1))

    def upgrade(self) -> None:
        super().upgrade()
        self.is_innate = True


class Barricade(_CostDownOnUpgrade, STS2Card):
    """바리케이드 — 파워: 블록이 턴 시작에 사라지지 않음 (업글 2코스트)."""
    card_id = "barricade"
    name = "Barricade"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 3

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Barricade as BarricadePower
        source.apply_power(BarricadePower(1))


class Brand(STS2Card):
    """낙인 — 0코스트: HP 1 소모, 핸드 1장 소모 [선택→무작위], 힘 +1 (업글 +2)."""
    card_id = "brand"
    name = "Brand"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Strength
        source.lose_hp(1)
        if combat is not None:
            combat.exhaust_from_hand(1)
        source.apply_power(Strength(2 if self.upgraded else 1))


class Cascade(STS2Card):
    """폭포수 — X코스트: 뽑을 카드 더미 맨 위에서 X장 (업글 X+1) 자동 플레이."""
    card_id = "cascade"
    name = "Cascade"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 0
    x_cost = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        count = self.x_value + (1 if self.upgraded else 0)
        for _ in range(count):
            if not combat.draw_pile and combat.discard_pile:
                combat.draw_pile = combat.discard_pile
                combat.discard_pile = []
                combat.rng.shuffle(combat.draw_pile)
            if not combat.draw_pile or not combat.alive_enemies:
                return
            combat.auto_play(combat.draw_pile.pop())


class Conflagration(_Attack):
    """대화재 — 모든 적에게 2딜 ×4회 (업글 ×5회)."""
    card_id = "conflagration"
    name = "Conflagration"
    rarity = Rarity.RARE
    cost = 1
    target_all = True
    dmg = dmg_up = 2
    hits, hits_up = 4, 5


class CrimsonMantle(STS2Card):
    """진홍 망토 — 파워: 턴 시작마다 블록 +7 (업글 +10).
    플레이할 때마다 턴 시작 자해 +1 누적."""
    card_id = "crimson_mantle"
    name = "Crimson Mantle"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import CrimsonMantle as CM
        source.apply_power(CM(10 if self.upgraded else 7))
        source._powers["crimson_mantle"].self_damage += 1


class Cruelty(STS2Card):
    """잔혹함 — 파워: 취약 배율 +25% (업글 +50%)."""
    card_id = "cruelty"
    name = "Cruelty"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Cruelty as CrueltyPower
        source.apply_power(CrueltyPower(50 if self.upgraded else 25))


class DarkEmbrace(_CostDownOnUpgrade, STS2Card):
    """어둠의 포옹 — 파워: 카드 소모 시마다 1드로우 (업글 1코스트)."""
    card_id = "dark_embrace"
    name = "Dark Embrace"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import DarkEmbrace as DE
        source.apply_power(DE(1))


class DemonForm(STS2Card):
    """악마의 형상 — 파워: 매 턴 시작 힘 +2 (업글 +3)."""
    card_id = "demon_form"
    name = "Demon Form"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 3

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import DemonForm as DF
        source.apply_power(DF(3 if self.upgraded else 2))


class Feed(_Attack):
    """포식 — 10딜 (업글 12), 처치 시 최대 HP +3 (업글 +4). 소모."""
    card_id = "feed"
    name = "Feed"
    rarity = Rarity.RARE
    cost = 1
    exhausts = True
    dmg, dmg_up = 10, 12

    def use(self, source, targets, combat=None) -> None:
        gain = 4 if self.upgraded else 3
        for target in targets:
            if not _alive(target):
                continue
            _deal_attack(source, target, self._damage())
            if target.is_dead:
                source.gain_max_hp(gain)
                character = getattr(source, "character", None)
                if character is not None:
                    character.max_hp = source.max_hp


class FiendFire(_Attack):
    """악귀의 불꽃 — 핸드 전체 소모, 1장당 7딜 (업글 10). 소모."""
    card_id = "fiend_fire"
    name = "Fiend Fire"
    rarity = Rarity.RARE
    cost = 2
    exhausts = True
    dmg, dmg_up = 7, 10

    def use(self, source, targets, combat=None) -> None:
        count = combat.exhaust_all_hand() if combat is not None else 0
        for _ in range(count):
            for target in targets:
                if _alive(target):
                    _deal_attack(source, target, self._damage())

    def damage_estimate(self, player, combat=None, target=None) -> int:
        count = max(0, len(combat.hand) - 1) if combat is not None else 0
        return self._damage() * count


class Hellraiser(_CostDownOnUpgrade, STS2Card):
    """헬레이저 — 파워: Strike 카드를 뽑으면 즉시 자동 플레이 (업글 1코스트)."""
    card_id = "hellraiser"
    name = "Hellraiser"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Hellraiser as HR
        source.apply_power(HR(1))


class Impervious(_Block):
    """철벽 — 30블록 (업글 40). 소모."""
    card_id = "impervious"
    name = "Impervious"
    rarity = Rarity.RARE
    cost = 2
    exhausts = True
    blk, blk_up = 30, 40


class Juggernaut(STS2Card):
    """저거너트 — 파워: 블록 획득 시 무작위 적에게 6 피해 (업글 8)."""
    card_id = "juggernaut"
    name = "Juggernaut"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Juggernaut as JuggernautPower
        source.apply_power(JuggernautPower(8 if self.upgraded else 6))


class Mangle(_Attack):
    """짓이기기 — 15딜 (업글 20), 대상 이번 턴 힘 -10 (업글 -15)."""
    card_id = "mangle"
    name = "Mangle"
    rarity = Rarity.RARE
    cost = 3
    dmg, dmg_up = 15, 20

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import TempStrength
        super().use(source, targets, combat)
        loss = 15 if self.upgraded else 10
        for target in targets:
            if _alive(target):
                target.apply_power(TempStrength(-loss), applier=source)


class NotYet(STS2Card):
    """아직은 아니야 — HP 10 회복 (업글 13). 소모."""
    card_id = "not_yet"
    name = "Not Yet"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 2
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        source.heal(13 if self.upgraded else 10)


class Offering(STS2Card):
    """제물 — 0코스트: HP 6 소모, 에너지 +2, 3드로우 (업글 5). 소모."""
    card_id = "offering"
    name = "Offering"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 0
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        source.lose_hp(6)
        source.gain_energy(2)
        if combat is not None:
            combat.draw_cards(5 if self.upgraded else 3)


class OneTwoPunch(STS2Card):
    """원투 펀치 — 다음 공격 카드 1장 (업글 2장)이 2회 발동."""
    card_id = "one_two_punch"
    name = "One-Two Punch"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import OneTwoPunch as OTP
        source.apply_power(OTP(2 if self.upgraded else 1))


class PactsEnd(_Attack):
    """계약의 끝 — 0코스트: 소모 더미가 3장 이상이면 모든 적에게 17딜 (업글 23)."""
    card_id = "pacts_end"
    name = "Pact's End"
    rarity = Rarity.RARE
    cost = 0
    target_all = True
    dmg, dmg_up = 17, 23

    def use(self, source, targets, combat=None) -> None:
        if combat is not None and len(combat.exhaust_pile) >= 3:
            super().use(source, targets, combat)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        if combat is not None and len(combat.exhaust_pile) >= 3:
            return self._damage()
        return 0


class PrimalForce(STS2Card):
    """원시의 힘 — 0코스트: 핸드의 모든 공격 카드를 GiantRock으로 변환
    (업글: GiantRock+)."""
    card_id = "primal_force"
    name = "Primal Force"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        for i, card in enumerate(combat.hand):
            if card.card_type == CardType.ATTACK:
                rock = GiantRock()
                if self.upgraded:
                    rock.upgrade()
                combat.hand[i] = rock


class Pyre(STS2Card):
    """장작불 — 파워: 최대 에너지 +1 (업글 +2)."""
    card_id = "pyre"
    name = "Pyre"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Pyre as PyrePower
        amount = 2 if self.upgraded else 1
        source.apply_power(PyrePower(amount))
        source.max_energy += amount


class TearAsunder(STS2Card):
    """찢어발기기 — 5딜 (업글 7) × (1 + 이번 전투에서 HP를 잃은 횟수)회."""
    card_id = "tear_asunder"
    name = "Tear Asunder"
    card_type = CardType.ATTACK
    rarity = Rarity.RARE
    cost = 2

    def _damage(self) -> int:
        return 7 if self.upgraded else 5

    def use(self, source, targets, combat=None) -> None:
        hits = 1 + source.times_hp_lost
        for _ in range(hits):
            for target in targets:
                if _alive(target):
                    _deal_attack(source, target, self._damage())

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage() * (1 + player.times_hp_lost)


class Thrash(STS2Card):
    """맹타 — 4딜 ×2 (업글 6×2). 핸드의 무작위 공격 카드를 소모하고
    그 데미지를 이 카드에 영구 누적."""
    card_id = "thrash"
    name = "Thrash"
    card_type = CardType.ATTACK
    rarity = Rarity.RARE
    cost = 1

    def __init__(self):
        super().__init__()
        self.bonus = 0

    def _damage(self) -> int:
        return (6 if self.upgraded else 4) + self.bonus

    def use(self, source, targets, combat=None) -> None:
        for _ in range(2):
            for target in targets:
                if _alive(target):
                    _deal_attack(source, target, self._damage())
        if combat is None:
            return
        attacks = [c for c in combat.hand if c.card_type == CardType.ATTACK]
        if attacks:
            card = combat.rng.choice(attacks)
            self.bonus += card.damage_estimate(source, combat)
            combat.hand.remove(card)
            combat._exhaust_card(card)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage() * 2


class Unmovable(_CostDownOnUpgrade, STS2Card):
    """부동 — 파워: 매 턴 첫 블록 획득이 2배 (업글 1코스트)."""
    card_id = "unmovable"
    name = "Unmovable"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Unmovable as UnmovablePower
        source.apply_power(UnmovablePower(1))


# ══════════════════════════════════════════
# Ancient (일반 보상 풀 제외)
# ══════════════════════════════════════════

class Break(_Attack):
    """브레이크 — 20딜 (업글 30) + 취약 5 (업글 7). Ancient."""
    card_id = "break"
    name = "Break"
    rarity = Rarity.ANCIENT
    cost = 1
    dmg, dmg_up = 20, 30
    vuln_setup = 8

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Vulnerable
        super().use(source, targets, combat)
        for target in targets:
            if _alive(target):
                target.apply_power(Vulnerable(7 if self.upgraded else 5),
                                   applier=source)


class Corruption(_CostDownOnUpgrade, STS2Card):
    """부패 — 파워: 스킬 비용 0, 플레이한 스킬은 소모 (업글 2코스트). Ancient."""
    card_id = "corruption"
    name = "Corruption"
    card_type = CardType.POWER
    rarity = Rarity.ANCIENT
    cost = 3

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Corruption as CorruptionPower
        source.apply_power(CorruptionPower(1))


# ══════════════════════════════════════════
# Token
# ══════════════════════════════════════════

class GiantRock(_Attack):
    """거대한 바위 — 16딜 (업글 20). PrimalForce 생성 토큰."""
    card_id = "giant_rock"
    name = "Giant Rock"
    rarity = Rarity.TOKEN
    cost = 1
    dmg, dmg_up = 16, 20


class Stoke(STS2Card):
    """불지피기 — 핸드 전체 소모, 소모한 수만큼 풀의 무작위 카드를 핸드에 생성
    (업글: 생성 카드 업그레이드)."""
    card_id = "stoke"
    name = "Stoke"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        count = combat.exhaust_all_hand()
        for _ in range(count):
            card = create_card(combat.rng.choice(IRONCLAD_ALL_POOL_IDS))
            if card is not None:
                if self.upgraded:
                    card.upgrade()
                combat.hand.append(card)


# ══════════════════════════════════════════
# 풀 등록
# ══════════════════════════════════════════

_IRONCLAD_CARDS = [
    # Common
    Anger, Armaments, BloodWall, Bloodletting, BodySlam, Breakthrough, Cinder,
    Havoc, Headbutt, IronWave, MoltenFist, PerfectedStrike, PommelStrike,
    SetupStrike, SwordBoomerang, Thunderclap, Tremble, TrueGrit, TwinStrike,
    # Uncommon
    AshenStrike, BattleTrance, Bludgeon, Bully, BurningPact, Colossus,
    Dismantle, Dominate, DrumOfBattle, EvilEye, ExpectAFight, FeelNoPain,
    FightMe, FlameBarrier, ForgottenRitual, Hemokinesis, HowlFromBeyond,
    InfernalBlade, Inferno, Inflame, Juggling, Pillage, Rage, Rampage,
    Rupture, SecondWind, Spite, Stampede, Stomp, StoneArmor, Taunt,
    Unrelenting, Uppercut, Vicious, Whirlwind,
    # Rare
    Aggression, Barricade, Brand, Cascade, Conflagration, CrimsonMantle,
    Cruelty, DarkEmbrace, DemonForm, Feed, FiendFire, Hellraiser, Impervious,
    Juggernaut, Mangle, NotYet, Offering, OneTwoPunch, PactsEnd, PrimalForce,
    Pyre, Stoke, TearAsunder, Thrash, Unmovable,
    # Ancient / Token
    Break, Corruption, GiantRock,
]

CARD_REGISTRY.update({cls.card_id: cls for cls in _IRONCLAD_CARDS})

# 보상 풀 (Ancient/Token 제외, 기존 구현 bash 포함)
IRONCLAD_POOL_BY_RARITY = {
    Rarity.COMMON: [cls.card_id for cls in _IRONCLAD_CARDS
                    if cls.rarity == Rarity.COMMON],
    Rarity.UNCOMMON: [cls.card_id for cls in _IRONCLAD_CARDS
                      if cls.rarity == Rarity.UNCOMMON],
    Rarity.RARE: [cls.card_id for cls in _IRONCLAD_CARDS
                  if cls.rarity == Rarity.RARE],
}

# InfernalBlade용 — 생성 가능한 공격 카드 (Feed 제외: CanBeGeneratedInCombat=false)
IRONCLAD_ATTACK_IDS = [cls.card_id for cls in _IRONCLAD_CARDS
                       if cls.card_type == CardType.ATTACK
                       and cls.rarity in (Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE)
                       and cls.card_id != "feed"] + ["bash"]

# Stoke용 — 전체 풀 (Ancient/Token 제외)
IRONCLAD_ALL_POOL_IDS = (IRONCLAD_POOL_BY_RARITY[Rarity.COMMON]
                         + IRONCLAD_POOL_BY_RARITY[Rarity.UNCOMMON]
                         + IRONCLAD_POOL_BY_RARITY[Rarity.RARE])
