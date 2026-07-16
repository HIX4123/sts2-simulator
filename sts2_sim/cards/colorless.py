"""
Colorless 카드 풀 — 디컴파일 MegaCrit.Sts2.Core.Models.CardPools.ColorlessCardPool 이식.

원본 65종 전부(Common 등급 없음 — Colorless는 Uncommon/Rare만 존재, 원본 그대로) +
스타터/토큰 없음(원본에 없음)을 여기서 구현.

모든 수치는 디컴파일 .cs의 CanonicalVars/OnUpgrade 그대로.
카드 선택 UI가 필요한 효과는 무작위 선택으로 대체하고 주석에 [선택→무작위] 표기.

Colorless는 독립 캐릭터가 아니라 어느 캐릭터든 편입 가능한 카드 풀이므로,
"소유 캐릭터의 카드풀"을 참조하는 카드(Calamity/Discovery/Entropy/Jackpot/
JackOfAllTrades/Splash)는 `player.character.name` → 해당 캐릭터의
`*_POOL_BY_RARITY`로 해석한다 (원본 Owner.Character.CardPool 대응).

멀티플레이 전용 카드(BeaconOfHope/BelieveInYou/Coordinate/GangUp/HuddleUp/
Intercept/Knockdown/Lift/Mimic/Rally/TagTeam/TheBall — 12종)는 원본 목록에
그대로 포함하되, "다른 플레이어/팀원" 대상 효과는 싱글플레이 환경에 맞게
단순화(대상=자기 자신, 또는 발동 조건이 자기 자신 외 공격자가 없어 항상
무발동)했다. 세부 사항은 IMPLEMENTATION_STATUS.md 참조.

포션 시스템은 미이식 — Alchemize는 생성 로직 생략(마커, [포션 미이식]).
"""
from __future__ import annotations

from sts2_sim.models.sts2_card import (
    STS2Card, CardType, Rarity, CARD_REGISTRY, create_card, _deal_attack,
)
from sts2_sim.models.sts2_power import _unpowered_hit
from sts2_sim.cards.ironclad import _Attack, _Block, _alive
from sts2_sim.cards.ironclad import IRONCLAD_POOL_BY_RARITY
from sts2_sim.cards.silent import SILENT_POOL_BY_RARITY
from sts2_sim.cards.defect import DEFECT_POOL_BY_RARITY
from sts2_sim.cards.necrobinder import NECROBINDER_POOL_BY_RARITY
from sts2_sim.cards.regent import REGENT_POOL_BY_RARITY

MAX_HAND_SIZE = 10  # CardPile.MaxCardsInHand

_CHAR_POOLS = {
    "Ironclad": IRONCLAD_POOL_BY_RARITY,
    "Silent": SILENT_POOL_BY_RARITY,
    "Defect": DEFECT_POOL_BY_RARITY,
    "Necrobinder": NECROBINDER_POOL_BY_RARITY,
    "Regent": REGENT_POOL_BY_RARITY,
}

_TEMP_DEBUFF_IDS = {"temp_strength", "temp_dexterity", "temp_focus"}

# 원본 CardModel.CanBeGeneratedInCombat=false — 전투 중 카드 생성 효과(Discovery/
# Calamity/Entropy/Splash/Jackpot/Quasar/BundleOfJoy/SpectrumShift/JackOfAllTrades)의
# 후보 풀에서 항상 제외해야 하는 카드 (CardFactory.FilterForCombat 대응).
_NOT_GENERATABLE_IN_COMBAT = frozenset({
    "feed", "not_yet", "the_hunt", "royalties",       # 캐릭터 풀 소속
    "hand_of_greed", "hidden_gem",                    # Colorless 자체 풀 소속
    "nightmare", "transfigure",
})


# ══════════════════════════════════════════
# 공용 헬퍼
# ══════════════════════════════════════════

def _apply_to_targets(source, targets, power_factory) -> None:
    for target in targets:
        if _alive(target) and hasattr(target, "apply_power"):
            target.apply_power(power_factory(), applier=source)


def _character_pool_ids(source) -> list:
    """원본 Owner.Character.CardPool 대응 — 소유 캐릭터 카드풀(전 희귀도, Basic/
    Token 제외) id 목록. 캐릭터 식별 불가 시 Colorless 자체 풀로 대체(단순화).
    CanBeGeneratedInCombat=false 카드(원본 CardFactory.FilterForCombat)는 제외."""
    char = getattr(source, "character", None)
    pool = _CHAR_POOLS.get(getattr(char, "name", None))
    if pool is None:
        return [cid for cid in _COLORLESS_IDS
                if cid != "discovery" and cid not in _NOT_GENERATABLE_IN_COMBAT]
    ids: list = []
    for rarity_ids in pool.values():
        ids.extend(rarity_ids)
    return [cid for cid in ids if cid not in _NOT_GENERATABLE_IN_COMBAT]


def _character_attack_ids(source) -> list:
    """소유 캐릭터 카드풀 중 Attack 타입만 (Calamity)."""
    return [cid for cid in _character_pool_ids(source)
            if CARD_REGISTRY[cid].card_type == CardType.ATTACK]


def _character_zero_cost_ids(source) -> list:
    """소유 캐릭터 카드풀 중 0코스트(비-X코스트)만 (Jackpot)."""
    ids = []
    for cid in _character_pool_ids(source):
        cls = CARD_REGISTRY[cid]
        if cls.cost == 0 and not cls.x_cost:
            ids.append(cid)
    return ids


def _other_character_attack_ids(source) -> list:
    """Splash 전용 — 소유 캐릭터를 제외한 나머지 캐릭터 풀의 Attack 카드 id 목록."""
    char = getattr(source, "character", None)
    my_name = getattr(char, "name", None)
    ids: list = []
    for name, pool in _CHAR_POOLS.items():
        if name == my_name:
            continue
        for rarity_ids in pool.values():
            for cid in rarity_ids:
                if cid in _NOT_GENERATABLE_IN_COMBAT:
                    continue
                cls = CARD_REGISTRY.get(cid)
                if cls is not None and cls.card_type == CardType.ATTACK:
                    ids.append(cid)
    return ids


def _persistent_debuff_count(target) -> int:
    """Rend — 대상의 "일시적이지 않은" 디버프 파워 수(원본 ITemporaryPower 제외).
    이 프로젝트는 ITemporaryPower 마커가 없어 temp_strength/dexterity/focus를
    이름으로 제외하는 것으로 근사(단순화)."""
    return sum(1 for pid, p in target._powers.items()
               if p.is_debuff and pid not in _TEMP_DEBUFF_IDS)


# ══════════════════════════════════════════
# Uncommon (40)
# ══════════════════════════════════════════

class Automation(STS2Card):
    """오토메이션 — 파워: 10장 뽑을 때마다 에너지 +1 (업글: 코스트 -1)."""
    card_id = "automation"
    name = "Automation"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import AutomationP
        source.apply_power(AutomationP(1))


class BelieveInYou(STS2Card):
    """믿음 — 0코스트, 대상 아군 에너지 +2 (업글 +3). MultiplayerOnly —
    싱글플레이는 대상=자기 자신."""
    card_id = "believe_in_you"
    name = "Believe in You"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        source.gain_energy(3 if self.upgraded else 2)


class Catastrophe(STS2Card):
    """대참사 — 2코스트: 뽑을 더미 무작위 카드 2장(업글 3장)을 자동 플레이.
    [선택→무작위](원본은 셔플 후 첫 유효 카드)."""
    card_id = "catastrophe"
    name = "Catastrophe"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        n = 3 if self.upgraded else 2
        for _ in range(n):
            if not combat.alive_enemies:
                break
            candidates = [c for c in combat.draw_pile if c.playable]
            pool = candidates if candidates else list(combat.draw_pile)
            if not pool:
                break
            card = combat.rng.choice(pool)
            combat.draw_pile.remove(card)
            combat.auto_play(card)


class Coordinate(STS2Card):
    """조율 — 1코스트, 대상 아군 임시 힘 +5 (업글 +8). MultiplayerOnly —
    싱글플레이는 대상=자기 자신."""
    card_id = "coordinate"
    name = "Coordinate"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import TempStrength
        source.apply_power(TempStrength(8 if self.upgraded else 5))


class DarkShackles(STS2Card):
    """어둠의 족쇄 — 0코스트, 대상 임시 힘 -9 (업글 -15), 소모."""
    card_id = "dark_shackles"
    name = "Dark Shackles"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0
    exhausts = True
    needs_target = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import TempStrength
        loss = 15 if self.upgraded else 9
        for target in targets[:1]:
            if _alive(target) and hasattr(target, "apply_power"):
                target.apply_power(TempStrength(-loss), applier=source)


class Discovery(STS2Card):
    """발견 — 1코스트: 소유 캐릭터 카드풀에서 무작위 카드 1장을 손패에
    생성해 이번 턴 무료, 소모(업글: 소모 제거). [선택→무작위](원본은 3장 중 선택)."""
    card_id = "discovery"
    name = "Discovery"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.exhausts = False

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        pool = _character_pool_ids(source)
        if not pool:
            return
        cid = combat.rng.choice(pool)
        made = combat.generate_card(cid, to="hand")
        for card in made:
            card._free_this_turn = True


class DramaticEntrance(_Attack):
    """드라마틱한 등장 — 0코스트, 전체 11딜 (업글 15), 소모+선천성."""
    card_id = "dramatic_entrance"
    name = "Dramatic Entrance"
    rarity = Rarity.UNCOMMON
    cost = 0
    target_all = True
    exhausts = True
    is_innate = True
    dmg, dmg_up = 11, 15


class Equilibrium(_Block):
    """평형 — 2코스트 13블록 (업글 16) + 손패 유지 1턴."""
    card_id = "equilibrium"
    name = "Equilibrium"
    rarity = Rarity.UNCOMMON
    cost = 2
    blk, blk_up = 13, 16

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import RetainHandP
        super().use(source, targets, combat)
        source.apply_power(RetainHandP(1))


class Fasten(STS2Card):
    """고정 — 파워: Defend 태그 카드 블록 획득 시 +4 (업글 +6) 고정 가산."""
    card_id = "fasten"
    name = "Fasten"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import FastenP
        source.apply_power(FastenP(6 if self.upgraded else 4))


class Finesse(STS2Card):
    """기교 — 0코스트 4블록 (업글 7) + 드로우 1."""
    card_id = "finesse"
    name = "Finesse"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0
    blk, blk_up = 4, 7

    def use(self, source, targets, combat=None) -> None:
        source.gain_block(self.blk_up if self.upgraded else self.blk)
        if combat:
            combat.draw_cards(1)

    def block_estimate(self, player, combat=None) -> int:
        return self.blk_up if self.upgraded else self.blk


class Fisticuffs(STS2Card):
    """주먹다짐 — 1코스트 7딜 (업글 9) + 준 피해만큼 블록."""
    card_id = "fisticuffs"
    name = "Fisticuffs"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 1
    dmg, dmg_up = 7, 9

    def _damage(self) -> int:
        return self.dmg_up if self.upgraded else self.dmg

    def use(self, source, targets, combat=None) -> None:
        for target in targets:
            if _alive(target):
                result = _deal_attack(source, target, self._damage())
                source.gain_block(result.get("damage", 0))

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage()

    def block_estimate(self, player, combat=None) -> int:
        return self._damage()


class FlashOfSteel(_Attack):
    """강철의 섬광 — 0코스트 5딜 (업글 8) + 드로우 1."""
    card_id = "flash_of_steel"
    name = "Flash of Steel"
    rarity = Rarity.UNCOMMON
    cost = 0
    dmg, dmg_up = 5, 8

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat:
            combat.draw_cards(1)


class GangUp(STS2Card):
    """협공 — 1코스트 5딜, MultiplayerOnly(아군 공격 수만큼 추가 피해 — 싱글플레이는
    아군이 없어 항상 기본 5딜 고정, 단순화)."""
    card_id = "gang_up"
    name = "Gang Up"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 1
    BASE_DAMAGE = 5

    def use(self, source, targets, combat=None) -> None:
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, self.BASE_DAMAGE)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self.BASE_DAMAGE


class HuddleUp(STS2Card):
    """단결 — 1코스트: 모든 아군 드로우 2 (업글 3), 소모. MultiplayerOnly —
    싱글플레이는 자기 자신만 드로우."""
    card_id = "huddle_up"
    name = "Huddle Up"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat:
            combat.draw_cards(3 if self.upgraded else 2)


class Impatience(STS2Card):
    """조바심 — 0코스트: 손패에 공격 카드가 없으면 드로우 2 (업글 3)."""
    card_id = "impatience"
    name = "Impatience"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        if not any(c.card_type == CardType.ATTACK for c in combat.hand):
            combat.draw_cards(3 if self.upgraded else 2)


class Intercept(STS2Card):
    """가로채기 — 1코스트, 대상 아군 9블록 (업글 13). MultiplayerOnly —
    싱글플레이는 대상=자기 자신, Covered(팀원 피해 대신 받기)는 다인용
    메카닉이라 생략(단순화)."""
    card_id = "intercept"
    name = "Intercept"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    blk, blk_up = 9, 13

    def use(self, source, targets, combat=None) -> None:
        source.gain_block(self.blk_up if self.upgraded else self.blk)

    def block_estimate(self, player, combat=None) -> int:
        return self.blk_up if self.upgraded else self.blk


class JackOfAllTrades(STS2Card):
    """팔방미인 — 0코스트: Colorless 카드풀에서 서로 다른 무작위 카드 1장
    (업글 2장)을 손패에 생성, 소모."""
    card_id = "jack_of_all_trades"
    name = "Jack of All Trades"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        n = 2 if self.upgraded else 1
        pool = [cid for cid in _COLORLESS_GENERATABLE_IDS if cid != self.card_id]
        chosen = combat.rng.sample(pool, min(n, len(pool)))
        for cid in chosen:
            combat.generate_card(cid, to="hand")


class Lift(STS2Card):
    """들어올리기 — 1코스트, 대상 아군 11블록 (업글 16). MultiplayerOnly —
    싱글플레이는 대상=자기 자신."""
    card_id = "lift"
    name = "Lift"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    blk, blk_up = 11, 16

    def use(self, source, targets, combat=None) -> None:
        source.gain_block(self.blk_up if self.upgraded else self.blk)

    def block_estimate(self, player, combat=None) -> int:
        return self.blk_up if self.upgraded else self.blk


class MindBlast(STS2Card):
    """정신 강타 — 1코스트(업글 0), 뽑을 더미 장수만큼 딜, 선천성."""
    card_id = "mind_blast"
    name = "Mind Blast"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 1
    is_innate = True

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)

    def _damage(self, combat) -> int:
        return len(combat.draw_pile) if combat else 0

    def use(self, source, targets, combat=None) -> None:
        dmg = self._damage(combat)
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, dmg)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage(combat)


class Omnislice(STS2Card):
    """전방위 절단 — 0코스트 8딜 (업글 11), 준 피해만큼 다른 모든 적에게
    Unpowered 피해."""
    card_id = "omnislice"
    name = "Omnislice"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 0
    dmg, dmg_up = 8, 11

    def _damage(self) -> int:
        return self.dmg_up if self.upgraded else self.dmg

    def use(self, source, targets, combat=None) -> None:
        for target in targets[:1]:
            if not _alive(target):
                continue
            result = _deal_attack(source, target, self._damage())
            total = result.get("damage", 0)
            if combat is not None and total > 0:
                for enemy in combat.alive_enemies:
                    if enemy is not target:
                        _unpowered_hit(enemy, total)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage()


class Panache(STS2Card):
    """패기 — 파워: 5장째 카드 플레이마다 전체 10 피해 (업글 14)."""
    card_id = "panache"
    name = "Panache"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import PanacheP
        source.apply_power(PanacheP(14 if self.upgraded else 10))


class PanicButton(STS2Card):
    """비상 버튼 — 0코스트 30블록 (업글 40) + 2턴간 블록 획득 불가, 소모."""
    card_id = "panic_button"
    name = "Panic Button"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0
    exhausts = True
    blk, blk_up = 30, 40

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import NoBlockP
        source.gain_block(self.blk_up if self.upgraded else self.blk)
        source.apply_power(NoBlockP(2))

    def block_estimate(self, player, combat=None) -> int:
        return self.blk_up if self.upgraded else self.blk


class PrepTime(STS2Card):
    """준비 시간 — 파워: 매 내 턴 시작 Vigor +4 (업글 +6)."""
    card_id = "prep_time"
    name = "Prep Time"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import PrepTimeP
        source.apply_power(PrepTimeP(6 if self.upgraded else 4))


class Production(STS2Card):
    """생산 — 0코스트 에너지 +2 (업글 +3), 소모."""
    card_id = "production"
    name = "Production"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        source.gain_energy(3 if self.upgraded else 2)


class Prolong(STS2Card):
    """지연 — 0코스트: 다음 턴 현재 블록만큼 블록, 소모(업글: 소모 제거)."""
    card_id = "prolong"
    name = "Prolong"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.exhausts = False

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import BlockNextTurn
        source.apply_power(BlockNextTurn(source.block))


class Prowess(STS2Card):
    """용맹 — 파워: 힘 +1 (업글 +2) + 민첩 +1 (업글 +2)."""
    card_id = "prowess"
    name = "Prowess"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Strength, Dexterity
        n = 2 if self.upgraded else 1
        source.apply_power(Strength(n))
        source.apply_power(Dexterity(n))


class Purity(STS2Card):
    """순수 — 0코스트: 손패 카드 3장(업글 5장) 소모, Retain. [선택→무작위]"""
    card_id = "purity"
    name = "Purity"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0
    retains = True
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        n = min(5 if self.upgraded else 3, len(combat.hand))
        if n <= 0:
            return
        chosen = combat.rng.sample(combat.hand, n)
        for card in chosen:
            combat.hand.remove(card)
            combat._exhaust_card(card)


class Restlessness(STS2Card):
    """안절부절 — 0코스트: 손패가 이 카드뿐이었다면 드로우 2(업글 3) +
    에너지 +2(업글 +3), Retain."""
    card_id = "restlessness"
    name = "Restlessness"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0
    retains = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None or combat.hand:
            return
        n = 3 if self.upgraded else 2
        combat.draw_cards(n)
        source.gain_energy(n)


class SeekerStrike(_Attack):
    """탐색자의 일격 — 1코스트 9딜 (업글 12) + 뽑을 더미 최대 3장 중
    무작위 1장을 손패로. Strike 태그. [선택→무작위]"""
    card_id = "seeker_strike"
    name = "Seeker Strike"
    rarity = Rarity.UNCOMMON
    cost = 1
    tags = frozenset({"strike"})
    dmg, dmg_up = 9, 12

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        if combat is None or not combat.draw_pile:
            return
        sample = list(combat.draw_pile)
        combat.rng.shuffle(sample)
        sample = sample[:3]
        card = combat.rng.choice(sample)
        combat.draw_pile.remove(card)
        if len(combat.hand) < MAX_HAND_SIZE:
            combat.hand.append(card)
        else:
            combat.draw_pile.append(card)


class Shockwave(STS2Card):
    """충격파 — 2코스트: 전체 약화 3 + 취약 3 (업글 5), 소모."""
    card_id = "shockwave"
    name = "Shockwave"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 2
    exhausts = True
    needs_target = True
    target_all = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Weak, Vulnerable
        amount = 5 if self.upgraded else 3
        _apply_to_targets(source, targets, lambda: Weak(amount))
        _apply_to_targets(source, targets, lambda: Vulnerable(amount))


class Splash(STS2Card):
    """스플래시 — 1코스트: 다른 캐릭터 카드풀의 무작위 공격 카드 1장을
    손패에 생성해 이번 턴 무료(업글: 강화 상태로 생성). [선택→무작위]"""
    card_id = "splash"
    name = "Splash"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        pool = _other_character_attack_ids(source)
        if not pool:
            return
        cid = combat.rng.choice(pool)
        made = combat.generate_card(cid, upgraded=self.upgraded, to="hand")
        for card in made:
            card._free_this_turn = True


class Stratagem(STS2Card):
    """책략 — 파워(1코스트, 업글 0): 셔플될 때마다 무작위 카드 1장을 손패로.
    [선택→무작위]"""
    card_id = "stratagem"
    name = "Stratagem"
    card_type = CardType.POWER
    rarity = Rarity.UNCOMMON
    cost = 1

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import StratagemP
        source.apply_power(StratagemP(1))


class TagTeam(_Attack):
    """태그 팀 — 2코스트 11딜 (업글 15) + 대상에게 TagTeam 1. MultiplayerOnly —
    다른 공격자가 없어 파워 자체는 싱글플레이에서 항상 무발동(단순화)."""
    card_id = "tag_team"
    name = "Tag Team"
    rarity = Rarity.UNCOMMON
    cost = 2
    dmg, dmg_up = 11, 15

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import TagTeamP
        super().use(source, targets, combat)
        _apply_to_targets(source, targets, lambda: TagTeamP(1))


class TheBall(STS2Card):
    """더 볼 — 1코스트 10딜, 플레이마다 이번 카드의 데미지 영구 +15(업글 +25).
    버림 대신 뽑을 더미 무작위 위치로. MultiplayerOnly(팀원에게 전달 — 싱글
    플레이는 항상 자기 덱에 남음, 단순화)."""
    card_id = "the_ball"
    name = "The Ball"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 1
    settle_to = "draw_random"
    INCREASE, INCREASE_UP = 15, 25

    def __init__(self) -> None:
        super().__init__()
        self._current_damage = 10

    def _increase(self) -> int:
        return self.INCREASE_UP if self.upgraded else self.INCREASE

    def use(self, source, targets, combat=None) -> None:
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, self._current_damage)
        self._current_damage += self._increase()

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._current_damage


class TheBomb(STS2Card):
    """폭탄 — 2코스트: 3턴 후 전체 40 피해(업글 50 피해)."""
    card_id = "the_bomb"
    name = "The Bomb"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 2
    dmg, dmg_up = 40, 50

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import TheBombP
        source.apply_power(TheBombP(3))
        power = source._powers.get("the_bomb")
        if power is not None:
            power.set_damage(self.dmg_up if self.upgraded else self.dmg)


class ThinkingAhead(STS2Card):
    """미리 생각하기 — 0코스트: 드로우 2 + 손패 1장을 뽑을 더미 맨 위로,
    소모(업글: 소모 제거). [선택→무작위]"""
    card_id = "thinking_ahead"
    name = "Thinking Ahead"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 0
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.exhausts = False

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        combat.draw_cards(2)
        if combat.hand:
            card = combat.rng.choice(combat.hand)
            combat.hand.remove(card)
            combat.draw_pile.append(card)


class ThrummingHatchet(_Attack):
    """웅웅거리는 손도끼 — 1코스트 11딜 (업글 14). 직전 턴에 플레이됐다면
    손패로 복귀."""
    card_id = "thrumming_hatchet"
    name = "Thrumming Hatchet"
    rarity = Rarity.UNCOMMON
    cost = 1
    dmg, dmg_up = 11, 14

    def __init__(self) -> None:
        super().__init__()
        self._played_last_turn = False

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        self._played_last_turn = True

    def on_before_hand_draw(self, combat) -> None:
        if not self._played_last_turn:
            return
        self._played_last_turn = False
        for pile in (combat.discard_pile, combat.draw_pile):
            if self in pile and len(combat.hand) < MAX_HAND_SIZE:
                pile.remove(self)
                combat.hand.append(self)
                return

    def reset_combat_state(self) -> None:
        self._played_last_turn = False


class UltimateDefend(STS2Card):
    """궁극의 수비 — 1코스트 11블록 (업글 15). Defend 태그(Fasten 대상)."""
    card_id = "ultimate_defend"
    name = "Ultimate Defend"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1
    tags = frozenset({"defend"})
    blk, blk_up = 11, 15

    def use(self, source, targets, combat=None) -> None:
        block = self.blk_up if self.upgraded else self.blk
        if hasattr(source, "get_power_amount"):
            block += source.get_power_amount("fasten")
        source.gain_block(block)

    def block_estimate(self, player, combat=None) -> int:
        return self.blk_up if self.upgraded else self.blk


class UltimateStrike(_Attack):
    """궁극의 타격 — 1코스트 14딜 (업글 20). Strike 태그."""
    card_id = "ultimate_strike"
    name = "Ultimate Strike"
    rarity = Rarity.UNCOMMON
    cost = 1
    tags = frozenset({"strike"})
    dmg, dmg_up = 14, 20


class Volley(STS2Card):
    """일제 사격 — X코스트, 무작위 적에게 10딜(업글 14) × X."""
    card_id = "volley"
    name = "Volley"
    card_type = CardType.ATTACK
    rarity = Rarity.UNCOMMON
    cost = 0
    x_cost = True
    dmg, dmg_up = 10, 14

    def use(self, source, targets, combat=None) -> None:
        dmg = self.dmg_up if self.upgraded else self.dmg
        for _ in range(self.x_value):
            enemies = combat.alive_enemies if combat else [t for t in targets if _alive(t)]
            if not enemies:
                break
            target = combat.rng.choice(enemies) if combat else enemies[0]
            _deal_attack(source, target, dmg)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        energy = getattr(player, "energy", 0)
        return (self.dmg_up if self.upgraded else self.dmg) * energy


# ══════════════════════════════════════════
# Rare (25)
# ══════════════════════════════════════════

class Alchemize(STS2Card):
    """연금술 — 1코스트(업글 0): 전투 중 무작위 포션 획득, 소모.
    [포션 미이식 — 생성 생략]"""
    card_id = "alchemize"
    name = "Alchemize"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)

    def use(self, source, targets, combat=None) -> None:
        pass  # 포션 시스템 미이식


class Anointed(STS2Card):
    """축성받은 자 — 1코스트: 뽑을 더미의 Rare 카드로 손패를 가득 채움,
    소모(업글: Retain)."""
    card_id = "anointed"
    name = "Anointed"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.retains = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        space = MAX_HAND_SIZE - len(combat.hand)
        if space <= 0:
            return
        candidates = [c for c in combat.draw_pile if c.rarity == Rarity.RARE]
        combat.rng.shuffle(candidates)
        for card in candidates[:space]:
            combat.draw_pile.remove(card)
            combat.hand.append(card)


class BeaconOfHope(STS2Card):
    """받은 축복 — 2코스트 파워: 블록 획득 시 50%를 팀원에게 분배
    (업글: 선천성). MultiplayerOnly — 싱글플레이는 팀원이 없어 항상 무발동."""
    card_id = "beacon_of_hope"
    name = "Beacon of Hope"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def upgrade(self) -> None:
        super().upgrade()
        self.is_innate = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import BeaconOfHopeP
        source.apply_power(BeaconOfHopeP(1))


class BeatDown(STS2Card):
    """두들겨 패기 — 3코스트: 버림 더미 무작위 공격 카드 3장(업글 4장)을
    자동 플레이."""
    card_id = "beat_down"
    name = "Beat Down"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 3

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        n = 4 if self.upgraded else 3
        candidates = [c for c in combat.discard_pile
                      if c.card_type == CardType.ATTACK and c.playable]
        combat.rng.shuffle(candidates)
        for card in candidates[:n]:
            if not combat.alive_enemies:
                break
            combat.discard_pile.remove(card)
            combat.auto_play(card)


class Bolas(_Attack):
    """볼라 — 0코스트 3딜 (업글 4). 직전 턴에 플레이됐다면 손패로 복귀."""
    card_id = "bolas"
    name = "Bolas"
    rarity = Rarity.RARE
    cost = 0
    dmg, dmg_up = 3, 4

    def __init__(self) -> None:
        super().__init__()
        self._played_last_turn = False

    def use(self, source, targets, combat=None) -> None:
        super().use(source, targets, combat)
        self._played_last_turn = True

    def on_before_hand_draw(self, combat) -> None:
        if not self._played_last_turn:
            return
        self._played_last_turn = False
        for pile in (combat.discard_pile, combat.draw_pile):
            if self in pile and len(combat.hand) < MAX_HAND_SIZE:
                pile.remove(self)
                combat.hand.append(self)
                return

    def reset_combat_state(self) -> None:
        self._played_last_turn = False


class Calamity(STS2Card):
    """대재앙 — 3코스트(업글 2) 파워: 공격 카드 플레이마다 소유 캐릭터
    카드풀의 무작위 공격 카드 1장을 손패에 생성."""
    card_id = "calamity"
    name = "Calamity"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 3

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import CalamityP
        source.apply_power(CalamityP(1))


class Entropy(STS2Card):
    """엔트로피 — 1코스트 파워(업글: 선천성): 내 턴 시작마다 손패 무작위
    1장을 소유 캐릭터 카드풀의 다른 카드로 변환. [선택→무작위]"""
    card_id = "entropy"
    name = "Entropy"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def upgrade(self) -> None:
        super().upgrade()
        self.is_innate = True

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import EntropyP
        source.apply_power(EntropyP(1))


class EternalArmor(STS2Card):
    """영원한 갑옷 — 3코스트 파워: Plating 9 (업글 12)."""
    card_id = "eternal_armor"
    name = "Eternal Armor"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 3

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Plating
        source.apply_power(Plating(12 if self.upgraded else 9))


class GoldAxe(STS2Card):
    """황금 도끼 — 1코스트: (이번 전투에서 이미 끝난 카드 플레이 수) 만큼 딜.
    업글: Retain."""
    card_id = "gold_axe"
    name = "Gold Axe"
    card_type = CardType.ATTACK
    rarity = Rarity.RARE
    cost = 1

    def upgrade(self) -> None:
        super().upgrade()
        self.retains = True

    def _damage(self, combat) -> int:
        if combat is None:
            return 0
        return max(0, combat.cards_played_this_combat - 1)  # 자기 자신 제외

    def use(self, source, targets, combat=None) -> None:
        dmg = self._damage(combat)
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, dmg)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage(combat)


class HandOfGreed(STS2Card):
    """탐욕의 손 — 2코스트 20딜 (업글 25). 처치 시 골드 +20 (업글 +25)."""
    card_id = "hand_of_greed"
    name = "Hand of Greed"
    card_type = CardType.ATTACK
    rarity = Rarity.RARE
    cost = 2
    dmg, dmg_up = 20, 25
    gold, gold_up = 20, 25

    def _damage(self) -> int:
        return self.dmg_up if self.upgraded else self.dmg

    def use(self, source, targets, combat=None) -> None:
        for target in targets:
            if _alive(target):
                result = _deal_attack(source, target, self._damage())
                if result.get("killed"):
                    character = getattr(source, "character", None)
                    if character is not None:
                        character.gain_gold(
                            self.gold_up if self.upgraded else self.gold)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage()


class HiddenGem(STS2Card):
    """숨겨진 보석 — 1코스트: 뽑을 더미 무작위 카드에 Replay +2 (업글 +3).
    [선택→무작위]"""
    card_id = "hidden_gem"
    name = "Hidden Gem"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        if combat is None or not combat.draw_pile:
            return
        # 원본 list2(재생 미보유 & 플레이 가능) → list3(list2 중 Attack/Skill/Power)로
        # 좁히되, list3가 비면 list2로 폴백 — 폴백 시에도 "재생 미보유" 조건은 유지.
        replayable = [c for c in combat.draw_pile
                      if c.playable and getattr(c, "_extra_plays", 0) < 1]
        candidates = [c for c in replayable
                      if c.card_type in (CardType.ATTACK, CardType.SKILL, CardType.POWER)]
        pool = candidates if candidates else replayable
        if not pool:
            return
        card = combat.rng.choice(pool)
        card._extra_plays += 3 if self.upgraded else 2


class Jackpot(STS2Card):
    """잭팟 — 3코스트 25딜 (업글 30) + 소유 캐릭터 카드풀의 0코스트 카드
    3장을 손패에 생성(업글: 강화 상태로 생성)."""
    card_id = "jackpot"
    name = "Jackpot"
    card_type = CardType.ATTACK
    rarity = Rarity.RARE
    cost = 3
    dmg, dmg_up = 25, 30

    def _damage(self) -> int:
        return self.dmg_up if self.upgraded else self.dmg

    def use(self, source, targets, combat=None) -> None:
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, self._damage())
        if combat is None:
            return
        pool = _character_zero_cost_ids(source)
        for _ in range(3):
            if not pool:
                break
            cid = combat.rng.choice(pool)
            combat.generate_card(cid, upgraded=self.upgraded, to="hand")

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage()


class Knockdown(_Attack):
    """넘어뜨리기 — 3코스트 10딜 (업글 14) + 대상에게 Knockdown 2 (업글 3).
    MultiplayerOnly — 다른 공격자가 없어 파워는 싱글플레이에서 항상 무발동."""
    card_id = "knockdown"
    name = "Knockdown"
    rarity = Rarity.RARE
    cost = 3
    dmg, dmg_up = 10, 14

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import KnockdownP
        super().use(source, targets, combat)
        amount = 3 if self.upgraded else 2
        _apply_to_targets(source, targets, lambda: KnockdownP(amount))


class MasterOfStrategy(STS2Card):
    """전략의 대가 — 0코스트: 드로우 3 (업글 4), 소모."""
    card_id = "master_of_strategy"
    name = "Master of Strategy"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 0
    exhausts = True

    def use(self, source, targets, combat=None) -> None:
        if combat:
            combat.draw_cards(4 if self.upgraded else 3)


class Mayhem(STS2Card):
    """혼돈 — 2코스트(업글 1) 파워: 매 카드 플레이 시작 전 뽑을 더미 맨 위
    1장을 자동 플레이."""
    card_id = "mayhem"
    name = "Mayhem"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 2

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import MayhemP
        source.apply_power(MayhemP(1))


class Mimic(STS2Card):
    """흉내 — 1코스트: 대상 아군의 현재 블록만큼 자신도 블록, 소모
    (업글: 소모 제거). MultiplayerOnly — 싱글플레이는 대상=자기 자신
    (자기 블록을 그대로 복제 → 실질 2배)."""
    card_id = "mimic"
    name = "Mimic"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.exhausts = False

    def use(self, source, targets, combat=None) -> None:
        source.gain_block(source.block)


class Nostalgia(STS2Card):
    """향수 — 1코스트(업글 0) 파워: 이번 턴 첫 1장의 공격/스킬 카드는
    버림 대신 뽑을 더미 맨 위로."""
    card_id = "nostalgia"
    name = "Nostalgia"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 1

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import NostalgiaP
        source.apply_power(NostalgiaP(1))


class Rally(STS2Card):
    """집결 — 2코스트: 모든 아군 12블록 (업글 17). MultiplayerOnly —
    싱글플레이는 자기 자신만 블록."""
    card_id = "rally"
    name = "Rally"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 2
    blk, blk_up = 12, 17

    def use(self, source, targets, combat=None) -> None:
        source.gain_block(self.blk_up if self.upgraded else self.blk)

    def block_estimate(self, player, combat=None) -> int:
        return self.blk_up if self.upgraded else self.blk


class Rend(STS2Card):
    """찢기 — 2코스트: (15 + 5×대상의 지속 디버프 수)딜 (업글 18+8×)."""
    card_id = "rend"
    name = "Rend"
    card_type = CardType.ATTACK
    rarity = Rarity.RARE
    cost = 2

    def _damage(self, target) -> int:
        base = 18 if self.upgraded else 15
        extra = 8 if self.upgraded else 5
        count = _persistent_debuff_count(target) if target is not None else 0
        return base + extra * count

    def use(self, source, targets, combat=None) -> None:
        for target in targets:
            if _alive(target):
                _deal_attack(source, target, self._damage(target))

    def damage_estimate(self, player, combat=None, target=None) -> int:
        if target is not None:
            return self._damage(target)
        return 18 if self.upgraded else 15


class RollingBoulder(STS2Card):
    """구르는 바위 — 3코스트 파워: 매 내 턴 시작 전체 5 피해 (업글 10),
    턴마다 +5 누적."""
    card_id = "rolling_boulder"
    name = "Rolling Boulder"
    card_type = CardType.POWER
    rarity = Rarity.RARE
    cost = 3

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import RollingBoulderP
        source.apply_power(RollingBoulderP(10 if self.upgraded else 5))


class Salvo(_Attack):
    """일제 사격 — 1코스트 12딜 (업글 16) + 손패 유지 1턴."""
    card_id = "salvo"
    name = "Salvo"
    rarity = Rarity.RARE
    cost = 1
    dmg, dmg_up = 12, 16

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import RetainHandP
        super().use(source, targets, combat)
        source.apply_power(RetainHandP(1))


class Scrawl(STS2Card):
    """휘갈겨 쓰기 — 1코스트: 손패가 가득 찰 때까지 드로우, 소모
    (업글: Retain 추가, 소모 유지)."""
    card_id = "scrawl"
    name = "Scrawl"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 1
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.retains = True

    def use(self, source, targets, combat=None) -> None:
        if combat is None:
            return
        need = MAX_HAND_SIZE - len(combat.hand)
        if need > 0:
            combat.draw_cards(need)


class SecretTechnique(STS2Card):
    """비전의 기술 — 0코스트: 뽑을 더미 무작위 스킬 카드 1장을 손패로,
    소모(업글: 소모 제거). [선택→무작위]"""
    card_id = "secret_technique"
    name = "Secret Technique"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 0
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.exhausts = False

    def use(self, source, targets, combat=None) -> None:
        if combat is None or not combat.draw_pile:
            return
        candidates = [c for c in combat.draw_pile if c.card_type == CardType.SKILL]
        if not candidates:
            return
        card = combat.rng.choice(candidates)
        combat.draw_pile.remove(card)
        if len(combat.hand) < MAX_HAND_SIZE:
            combat.hand.append(card)
        else:
            combat.draw_pile.append(card)


class SecretWeapon(STS2Card):
    """비밀 병기 — 0코스트: 뽑을 더미 무작위 공격 카드 1장을 손패로,
    소모(업글: 소모 제거). [선택→무작위]"""
    card_id = "secret_weapon"
    name = "Secret Weapon"
    card_type = CardType.SKILL
    rarity = Rarity.RARE
    cost = 0
    exhausts = True

    def upgrade(self) -> None:
        super().upgrade()
        self.exhausts = False

    def use(self, source, targets, combat=None) -> None:
        if combat is None or not combat.draw_pile:
            return
        candidates = [c for c in combat.draw_pile if c.card_type == CardType.ATTACK]
        if not candidates:
            return
        card = combat.rng.choice(candidates)
        combat.draw_pile.remove(card)
        if len(combat.hand) < MAX_HAND_SIZE:
            combat.hand.append(card)
        else:
            combat.draw_pile.append(card)


class TheGambit(_Block):
    """도박 — 0코스트 50블록 (업글 75). 다음 파워드 공격 비차단 피해를
    받으면 즉사."""
    card_id = "the_gambit"
    name = "The Gambit"
    rarity = Rarity.RARE
    cost = 0
    blk, blk_up = 50, 75

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import TheGambitP
        super().use(source, targets, combat)
        source.apply_power(TheGambitP(1))


# ══════════════════════════════════════════
# 등록
# ══════════════════════════════════════════

_COLORLESS_CARDS = [
    # Uncommon (40)
    Automation, BelieveInYou, Catastrophe, Coordinate, DarkShackles, Discovery,
    DramaticEntrance, Equilibrium, Fasten, Finesse, Fisticuffs, FlashOfSteel,
    GangUp, HuddleUp, Impatience, Intercept, JackOfAllTrades, Lift, MindBlast,
    Omnislice, Panache, PanicButton, PrepTime, Production, Prolong, Prowess,
    Purity, Restlessness, SeekerStrike, Shockwave, Splash, Stratagem, TagTeam,
    TheBall, TheBomb, ThinkingAhead, ThrummingHatchet, UltimateDefend,
    UltimateStrike, Volley,
    # Rare (25)
    Alchemize, Anointed, BeaconOfHope, BeatDown, Bolas, Calamity, Entropy,
    EternalArmor, GoldAxe, HandOfGreed, HiddenGem, Jackpot, Knockdown,
    MasterOfStrategy, Mayhem, Mimic, Nostalgia, Rally, Rend, RollingBoulder,
    Salvo, Scrawl, SecretTechnique, SecretWeapon, TheGambit,
]

CARD_REGISTRY.update({cls.card_id: cls for cls in _COLORLESS_CARDS})

_COLORLESS_IDS = [cls.card_id for cls in _COLORLESS_CARDS]

# 전투 중 카드 생성 효과(Quasar/BundleOfJoy/SpectrumShift/JackOfAllTrades) 전용 —
# CanBeGeneratedInCombat=false인 HandOfGreed/HiddenGem 제외. 손패의 기존 Colorless
# 카드를 식별하는 용도(예: HeirloomHammer)에는 여전히 _COLORLESS_IDS(원본 65종 전체)를 쓴다.
_COLORLESS_GENERATABLE_IDS = [cid for cid in _COLORLESS_IDS
                              if cid not in _NOT_GENERATABLE_IN_COMBAT]

# 보상 풀: Colorless는 Common 등급이 원본부터 없음
COLORLESS_POOL_BY_RARITY = {
    Rarity.UNCOMMON: sorted(
        [c.card_id for c in _COLORLESS_CARDS if c.rarity == Rarity.UNCOMMON]),
    Rarity.RARE: sorted(
        [c.card_id for c in _COLORLESS_CARDS if c.rarity == Rarity.RARE]),
}
