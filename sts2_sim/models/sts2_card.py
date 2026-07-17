"""
STS2 Card System — 디컴파일 MegaCrit.Sts2.Core.Models.Cards.* 이식.

모든 수치는 디컴파일 코드에서 추출한 실제값:
  Strike: 1코스트 6딜 (업글 +3)      | Defend: 1코스트 5블록 (업글 +3)
  Bash: 2코스트 8딜+취약2 (업글 +2/+1) | Shiv: 0코스트 4딜, 소모 (업글 +2)
  Deflect: 0코스트 4블록 (업글 +3)    | Acrobatics: 1코스트 3드로우+1버리기 (업글 +1)
  Neutralize: 0코스트 3딜+약화1       | Survivor: 1코스트 8블록+1버리기
  Zap: 1코스트 라이트닝 채널 (업글 0코스트)
  Dualcast: 1코스트 선두 오브 2회 이보크 (업글 0코스트)
  Bodyguard: 1코스트 Osty 5 소환 (업글 +2)
  Unleash: 1코스트 (6 + Osty HP)딜 (업글 +3)
  FallingStar: 0코스트/별 2 소모, 8딜+약화1+취약1 (업글 +4)
  Venerate: 1코스트 별 2 획득 (업글 +1)
"""
from __future__ import annotations
from enum import Enum, auto
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from sts2_sim.entities.creature import Creature


class CardType(Enum):
    """카드 타입."""
    ATTACK = auto()
    SKILL = auto()
    POWER = auto()
    CURSE = auto()
    STATUS = auto()


class Rarity(Enum):
    """카드 희귀도."""
    BASIC = auto()
    COMMON = auto()
    UNCOMMON = auto()
    RARE = auto()
    ANCIENT = auto()   # STS2 신규 등급 (Break/Corruption 등) — 일반 보상 풀 제외
    TOKEN = auto()


def _deal_attack(source, target, base_damage: int) -> dict:
    """공격 데미지 파이프라인: 공격자 수정(Strength/Weak) → 피격 처리.
    Tracking(약화 대상 +50%)/Envenom(비차단 피해 시 중독) 훅 포함.
    Necrobinder: Osty 공격 Calcify 보너스, Lethality(첫 공격 배수),
    ReaperForm/SicEm 사후 훅."""
    calc = getattr(source, "compute_attack_damage", None)
    dmg = calc(base_damage) if calc else base_damage
    # controller = 실제 시전자 (Osty면 그 주인 플레이어, 아니면 source 자신)
    is_osty = getattr(source, "owner", None) is not None
    controller = source.owner if is_osty else source
    # Calcify — Osty의 파워드 공격에 +amount (원본 CalcifyPower)
    if is_osty and hasattr(controller, "get_power_amount"):
        dmg += controller.get_power_amount("calcify")
    # Lethality — 이번 턴 첫 공격 카드 ×(1 + amount/100) (원본 LethalityPower)
    if getattr(controller, "_first_attack_this_turn", False):
        leth = controller.get_power_amount("lethality")
        if leth > 0:
            dmg = int(dmg * (1 + leth / 100))
    # Tracking — 약화 상태의 대상에게 주는 공격 데미지 +amount%
    if hasattr(source, "get_power_amount") and hasattr(target, "get_power_amount"):
        tracking = source.get_power_amount("tracking")
        if tracking > 0 and target.get_power_amount("weak") > 0:
            dmg = int(dmg * (1 + tracking / 100))
    result = target.take_damage(dmg, source=source)
    # BeatIntoShape — 이번 턴 이 대상이 받은 파워드 공격 히트 수 집계
    target._hits_taken_this_turn = getattr(target, "_hits_taken_this_turn", 0) + 1
    # MonarchsGaze — 내 파워드 공격이 명중할 때마다 대상 임시 힘 -amount
    # (원본 dealer == Owner — Osty 공격은 미발동)
    if (not is_osty and hasattr(controller, "get_power_amount")
            and hasattr(target, "apply_power")):
        mg = controller.get_power_amount("monarchs_gaze")
        if mg > 0 and not target.is_dead:
            from sts2_sim.models.sts2_power import TempStrength
            target.apply_power(TempStrength(-mg), applier=controller)
    # Envenom — 공격으로 비차단 피해를 주면 중독 부여
    if (result.get("hp_lost", 0) > 0 and hasattr(source, "get_power_amount")
            and hasattr(target, "apply_power")):
        envenom = source.get_power_amount("envenom")
        if envenom > 0 and not target.is_dead:
            from sts2_sim.models.sts2_power import Poison
            target.apply_power(Poison(envenom), applier=source)
    _necrobinder_after_attack(controller, source, target, result)
    return result


def _necrobinder_after_attack(controller, dealer, target, result) -> None:
    """플레이어/Osty의 파워드 공격 사후 훅: ReaperForm(Doom 부여), SicEm(Osty 소환)."""
    if not hasattr(controller, "get_power_amount"):
        return
    total = result.get("damage", 0)
    if total <= 0 or target.is_dead:
        return
    # ReaperForm — 준 피해만큼 대상에게 Doom 부여
    rf = controller.get_power_amount("reaper_form")
    if rf > 0 and hasattr(target, "apply_power"):
        from sts2_sim.models.sts2_power import Doom
        target.apply_power(Doom(total * rf), applier=controller)
    # SicEm — 당신의 Osty가 이 적을 공격하면 Osty 소환/강화
    if dealer is getattr(controller, "osty", None):
        se = target.get_power_amount("sic_em")
        if se > 0:
            summon = getattr(controller, "summon_osty", None)
            if summon:
                summon(se)


class STS2Card:
    """STS2 카드 베이스 클래스 (CardModel 대응)."""
    card_id: str = "unknown_card"
    name: str = "Unknown Card"
    card_type: CardType = CardType.ATTACK
    rarity: Rarity = Rarity.BASIC
    cost: int = 0
    star_cost: int = 0      # Regent 전용: 카드 플레이에 필요한 Stars
    exhausts: bool = False
    playable: bool = True   # Dazed 등 사용 불가 카드는 False
    target_all: bool = False  # TargetType.AllEnemies (전체 공격)
    is_innate: bool = False   # 선천성 — 전투 첫 손패에 포함
    x_cost: bool = False      # X 코스트 (Whirlwind/Cascade) — 플레이 시 에너지 전부 소비
    tags: frozenset = frozenset()  # CardTag (예: "strike" — PerfectedStrike/Hellraiser 참조)
    is_sly: bool = False      # Sly — 버려질 때(효과에 의한 버리기) 무료 자동 플레이
    retains: bool = False     # Retain — 턴 종료 시 손패에 유지

    def __init__(self):
        self.upgraded = False
        self.is_ethereal = False
        self.times_upgraded = 0
        self.cost = type(self).cost  # 인스턴스별 비용 (업그레이드로 변동 가능)
        self.x_value = 0             # X 코스트 카드가 소비한 에너지 (play_card가 설정)
        self.is_innate = type(self).is_innate  # 업그레이드로 Innate 부여 가능 (Aggression 등)
        self.is_sly = type(self).is_sly        # MasterPlanner가 인스턴스에 부여 가능
        self.retains = type(self).retains      # PhantomBlades가 Shiv에 부여 가능
        self._sly_this_turn = False    # HandTrick — 이번 턴만 Sly
        self._retain_this_turn = False  # WellLaidPlans — 이번 턴만 Retain
        self._free_this_turn = False    # BulletTime — 이번 턴 비용 0
        self._cost_this_combat: Optional[int] = None  # SetThisCombat (MomentumStrike 등)
        self._cost_add_this_combat = 0  # AddThisCombat (Modded 누진 비용)
        self._free_until_played = False  # SetUntilPlayed(0) (RocketPunch)
        self._last_paid = 0             # 직전 플레이에 지불한 에너지 (Feral 판정)
        self._extra_plays = 0           # Transfigure — 플레이 시 추가 발동 횟수(BaseReplayCount)

    def use(self, source, targets: List["Creature"], combat=None) -> None:
        """카드 사용. combat은 전투 컨텍스트 (드로우/오브 등 필요 시)."""
        pass

    def upgrade(self) -> None:
        self.upgraded = True
        self.times_upgraded += 1

    # ── 정책(GreedyPolicy)용 추정치 프로토콜 ──
    def damage_estimate(self, player, combat=None, target=None) -> int:
        """파워 수정 전 예상 총 데미지 (base × hits). 공격 카드가 오버라이드."""
        return 0

    def block_estimate(self, player, combat=None) -> int:
        """예상 블록량. 블록 카드가 오버라이드."""
        return 0

    def __repr__(self) -> str:
        plus = "+" if self.upgraded else ""
        return f"{self.name}{plus}[{self.cost}]"


# ══════════════════════════════════════════
# 공용 기본 카드 (캐릭터별 Strike/Defend 동일 수치)
# ══════════════════════════════════════════

class Strike(STS2Card):
    """타격 — 6딜 (업글 9)."""
    card_id = "strike"
    name = "Strike"
    card_type = CardType.ATTACK
    rarity = Rarity.BASIC
    cost = 1
    tags = frozenset({"strike"})

    def use(self, source, targets, combat=None) -> None:
        damage = 9 if self.upgraded else 6
        for target in targets:
            _deal_attack(source, target, damage)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return 9 if self.upgraded else 6


class Defend(STS2Card):
    """수비 — 5블록 (업글 8)."""
    card_id = "defend"
    name = "Defend"
    card_type = CardType.SKILL
    rarity = Rarity.BASIC
    cost = 1
    tags = frozenset({"defend"})  # Fasten(Colorless) 참조용 CardTag.Defend

    def use(self, source, targets, combat=None) -> None:
        block = 8 if self.upgraded else 5
        if hasattr(source, "get_power_amount"):
            block += source.get_power_amount("fasten")  # Fasten — Defend 태그 카드 가산
        source.gain_block(block)


# ══════════════════════════════════════════
# Ironclad
# ══════════════════════════════════════════

class Bash(STS2Card):
    """강타 — 8딜 + 취약 2 (업글 10딜 + 취약 3)."""
    card_id = "bash"
    name = "Bash"
    card_type = CardType.ATTACK
    rarity = Rarity.BASIC
    cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Vulnerable
        damage = 10 if self.upgraded else 8
        vuln = 3 if self.upgraded else 2
        for target in targets:
            _deal_attack(source, target, damage)
            if hasattr(target, "apply_power"):
                target.apply_power(Vulnerable(vuln), applier=source)

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return 10 if self.upgraded else 8


# ══════════════════════════════════════════
# Silent
# ══════════════════════════════════════════

class Neutralize(STS2Card):
    """무력화 — 0코스트 3딜 + 약화 1 (업글 4딜 + 약화 2)."""
    card_id = "neutralize"
    name = "Neutralize"
    card_type = CardType.ATTACK
    rarity = Rarity.BASIC
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Weak
        damage = 4 if self.upgraded else 3
        weak = 2 if self.upgraded else 1
        for target in targets:
            _deal_attack(source, target, damage)
            if hasattr(target, "apply_power"):
                target.apply_power(Weak(weak))


class Survivor(STS2Card):
    """생존자 — 8블록 + 카드 1 버리기 (업글 11블록)."""
    card_id = "survivor"
    name = "Survivor"
    card_type = CardType.SKILL
    rarity = Rarity.BASIC
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        block = 11 if self.upgraded else 8
        source.gain_block(block)
        if combat and hasattr(combat, "discard_from_hand"):
            combat.discard_from_hand(1)


class Shiv(STS2Card):
    """단검 — 0코스트 4딜, 소모 (업글 6딜). Token 카드.
    Accuracy(+amount딜), PhantomBlades(턴 첫 Shiv +amount딜),
    FanOfKnives(전체 공격화), Inky 인챈트(+1딜, 약화 1) 연동."""
    card_id = "shiv"
    name = "Shiv"
    card_type = CardType.ATTACK
    rarity = Rarity.TOKEN
    cost = 0
    exhausts = True
    tags = frozenset({"shiv"})

    def __init__(self):
        super().__init__()
        self.inky = False  # BladeOfInk 생성물

    def _damage(self, source, combat=None) -> int:
        damage = 6 if self.upgraded else 4
        if self.inky:
            damage += 1
        if hasattr(source, "get_power_amount"):
            damage += source.get_power_amount("accuracy")
            pb = source.get_power_amount("phantom_blades")
            if pb > 0 and combat is not None \
                    and getattr(combat, "shivs_played_this_turn", 0) == 0:
                damage += pb
        return damage

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Weak
        # FanOfKnives — Shiv가 전체 공격이 된다
        if (combat is not None and hasattr(source, "get_power_amount")
                and source.get_power_amount("fan_of_knives") > 0):
            targets = list(combat.alive_enemies)
        damage = self._damage(source, combat)
        for target in targets:
            if getattr(target, "is_dead", False) or getattr(target, "is_gone", False):
                continue
            _deal_attack(source, target, damage)
            if self.inky and hasattr(target, "apply_power") \
                    and not getattr(target, "is_dead", False):
                target.apply_power(Weak(1), applier=source)
        if combat is not None:
            combat.shivs_played_this_turn = \
                getattr(combat, "shivs_played_this_turn", 0) + 1

    def damage_estimate(self, player, combat=None, target=None) -> int:
        return self._damage(player, combat)


class Acrobatics(STS2Card):
    """곡예 — 3드로우 + 1버리기 (업글 4드로우). STS2에서 Uncommon."""
    card_id = "acrobatics"
    name = "Acrobatics"
    card_type = CardType.SKILL
    rarity = Rarity.UNCOMMON
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        draw = 4 if self.upgraded else 3
        if combat:
            if hasattr(combat, "draw_cards"):
                combat.draw_cards(draw)
            if hasattr(combat, "discard_from_hand"):
                combat.discard_from_hand(1)


class Deflect(STS2Card):
    """방향 전환 — 0코스트 4블록 (업글 7)."""
    card_id = "deflect"
    name = "Deflect"
    card_type = CardType.SKILL
    rarity = Rarity.COMMON
    cost = 0

    def use(self, source, targets, combat=None) -> None:
        block = 7 if self.upgraded else 4
        source.gain_block(block)


# ══════════════════════════════════════════
# Defect (Orb)
# ══════════════════════════════════════════

class Zap(STS2Card):
    """전격 — 라이트닝 오브 채널 (업글 0코스트)."""
    card_id = "zap"
    name = "Zap"
    card_type = CardType.SKILL
    rarity = Rarity.BASIC
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_orb import LightningOrb
        queue = getattr(source, "orb_queue", None)
        if queue is not None:
            queue.channel(LightningOrb(), source, combat)

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)


class Dualcast(STS2Card):
    """이중 시전 — 선두 오브를 2회 이보크 (업글 0코스트)."""
    card_id = "dualcast"
    name = "Dualcast"
    card_type = CardType.SKILL
    rarity = Rarity.BASIC
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        queue = getattr(source, "orb_queue", None)
        if queue is not None and len(queue) > 0:
            queue.evoke_next(combat, dequeue=False)
            queue.evoke_next(combat, dequeue=True)

    def upgrade(self) -> None:
        super().upgrade()
        self.cost = max(0, self.cost - 1)


# ══════════════════════════════════════════
# Necrobinder (Osty)
# ══════════════════════════════════════════

class Bodyguard(STS2Card):
    """경호원 — Osty 5 소환 (업글 +2)."""
    card_id = "bodyguard"
    name = "Bodyguard"
    card_type = CardType.SKILL
    rarity = Rarity.BASIC
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        amount = 7 if self.upgraded else 5
        summon = getattr(source, "summon_osty", None)
        if summon:
            summon(amount)


class Unleash(STS2Card):
    """해방 — Osty가 (6 + Osty 현재 HP)만큼 공격 (업글 기본 +3)."""
    card_id = "unleash"
    name = "Unleash"
    card_type = CardType.ATTACK
    rarity = Rarity.BASIC
    cost = 1
    is_osty_attack = True  # CardTag.OstyAttack (Squeeze 카운트 대상)

    def use(self, source, targets, combat=None) -> None:
        base = 9 if self.upgraded else 6
        osty = getattr(source, "osty", None)
        osty_hp = osty.current_hp if (osty and osty.is_alive) else 0
        damage = base + osty_hp
        attacker = osty if (osty and osty.is_alive) else source
        for target in targets:
            _deal_attack(attacker, target, damage)


# ══════════════════════════════════════════
# Regent (Stars)
# ══════════════════════════════════════════

class FallingStar(STS2Card):
    """유성 — 0코스트/별 2 소모, 8딜 + 약화 1 + 취약 1 (업글 12딜)."""
    card_id = "falling_star"
    name = "Falling Star"
    card_type = CardType.ATTACK
    rarity = Rarity.BASIC
    cost = 0
    star_cost = 2

    def use(self, source, targets, combat=None) -> None:
        from sts2_sim.models.sts2_power import Weak, Vulnerable
        damage = 12 if self.upgraded else 8
        for target in targets:
            _deal_attack(source, target, damage)
            if hasattr(target, "apply_power"):
                target.apply_power(Weak(1))
                target.apply_power(Vulnerable(1))


class Venerate(STS2Card):
    """숭배 — 별 2 획득 (업글 +1)."""
    card_id = "venerate"
    name = "Venerate"
    card_type = CardType.SKILL
    rarity = Rarity.BASIC
    cost = 1

    def use(self, source, targets, combat=None) -> None:
        stars = 3 if self.upgraded else 2
        gain = getattr(source, "gain_stars", None)
        if gain:
            gain(stars)


# ══════════════════════════════════════════
# 상태이상 카드 (몬스터가 덱에 삽입)
# ══════════════════════════════════════════

class Dazed(STS2Card):
    """멍함 — 사용 불가, 에테리얼 (Chomper SCREECH 등)."""
    card_id = "dazed"
    name = "Dazed"
    card_type = CardType.STATUS
    rarity = Rarity.TOKEN
    cost = 0
    playable = False

    def __init__(self):
        super().__init__()
        self.is_ethereal = True


class Slimed(STS2Card):
    """슬라임 범벅 — 1코스트, 효과 없음, 소모 (TwigSlimeM STICKY_SHOT 등)."""
    card_id = "slimed"
    name = "Slimed"
    card_type = CardType.STATUS
    rarity = Rarity.TOKEN
    cost = 1
    exhausts = True


class Wound(STS2Card):
    """상처 — 사용 불가, 효과 없음 (FightThrough 등)."""
    card_id = "wound"
    name = "Wound"
    card_type = CardType.STATUS
    rarity = Rarity.TOKEN
    cost = 0
    playable = False


class Burn(STS2Card):
    """화상 — 사용 불가, 턴 종료 시 손패에 있으면 2 피해 (Unpowered, 블록 적용)."""
    card_id = "burn"
    name = "Burn"
    card_type = CardType.STATUS
    rarity = Rarity.TOKEN
    cost = 0
    playable = False

    def on_turn_end_in_hand(self, source, combat) -> None:
        source.take_damage(2, source=None, powered=False)


class Void(STS2Card):
    """공허 — 사용 불가, 에테리얼, 드로우 시 에너지 -1 (Turbo)."""
    card_id = "void"
    name = "Void"
    card_type = CardType.STATUS
    rarity = Rarity.TOKEN
    cost = 0
    playable = False

    def __init__(self):
        super().__init__()
        self.is_ethereal = True

    def on_drawn(self, combat) -> None:
        combat.player.energy = max(0, combat.player.energy - 1)


# ══════════════════════════════════════════
# 카드 팩토리
# ══════════════════════════════════════════

CARD_REGISTRY = {
    # 공용 Basic
    "strike": Strike,
    "defend": Defend,
    # Ironclad
    "bash": Bash,
    # Silent
    "neutralize": Neutralize,
    "survivor": Survivor,
    "shiv": Shiv,
    "acrobatics": Acrobatics,
    "deflect": Deflect,
    # Defect
    "zap": Zap,
    "dualcast": Dualcast,
    # Necrobinder
    "bodyguard": Bodyguard,
    "unleash": Unleash,
    # Regent
    "falling_star": FallingStar,
    "venerate": Venerate,
    # 상태이상
    "dazed": Dazed,
    "slimed": Slimed,
    "wound": Wound,
    "burn": Burn,
    "void": Void,
}


def create_card(card_id: str) -> Optional[STS2Card]:
    """카드 생성."""
    card_class = CARD_REGISTRY.get(card_id)
    return card_class() if card_class else None
