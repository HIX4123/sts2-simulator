"""
STS2 Power System — STS2 디컴파일 데이터 기반 파워 구현.
기존 PowerModel과 호환되는 구조.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from sts2_sim.entities.creature import Creature


class STS2Power:
    """STS2 파워 베이스 클래스."""
    power_id: str = "unknown_power"
    name: str = "Unknown Power"
    is_debuff: bool = False
    # 데미지 수정 방향: "outgoing"(공격자 측) / "incoming"(피격자 측) / None
    damage_side: Optional[str] = None

    def __init__(self, amount: int = 0):
        self.amount = amount
        self.owner: Optional[Creature] = None
        self.applier: Optional[Creature] = None

    def apply(self, owner: Creature, applier: Optional[Creature] = None) -> None:
        """파워 적용."""
        self.owner = owner
        self.applier = applier
        if self.power_id not in owner._powers:
            owner._powers[self.power_id] = self
        else:
            existing = owner._powers[self.power_id]
            existing.amount += self.amount
            # 지속시간형 파워(Vulnerable/Weak 등)는 재적용 시 지속시간도 누적
            if hasattr(existing, "duration") and hasattr(self, "duration"):
                existing.duration += self.duration

    def remove(self) -> None:
        """파워 제거."""
        if self.owner and self.power_id in self.owner._powers:
            del self.owner._powers[self.power_id]

    def tick_duration(self) -> None:
        """지속시간 틱 (턴 종료 시)."""
        pass

    def modify_damage(self, amount: int, is_attack: bool = True) -> int:
        """데미지 수정 (기본: 수정 없음)."""
        return amount

    def modify_block(self, amount: int) -> int:
        """블록 수정 (기본: 수정 없음)."""
        return amount

    def __repr__(self) -> str:
        return f"{self.name}({self.amount})"


# ══════════════════════════════════════════
# 공통 파워
# ══════════════════════════════════════════

class Strength(STS2Power):
    """강화 — 공격 데미지 증가."""
    power_id = "strength"
    name = "Strength"
    is_debuff = False
    damage_side = "outgoing"

    def modify_damage(self, amount: int, is_attack: bool = True) -> int:
        """공격 데미지에 strength 추가."""
        if is_attack:
            return max(0, amount + self.amount)
        return amount


class Dexterity(STS2Power):
    """민첩성 — 블록 증가."""
    power_id = "dexterity"
    name = "Dexterity"
    is_debuff = False

    def modify_block(self, amount: int) -> int:
        """블록에 dexterity 추가."""
        return max(0, amount + self.amount)


class Vulnerable(STS2Power):
    """취약성 — 받는 데미지 1.5배."""
    power_id = "vulnerable"
    name = "Vulnerable"
    is_debuff = True
    damage_side = "incoming"

    def __init__(self, amount: int = 0):
        super().__init__(amount)
        self.duration = amount

    def modify_damage(self, amount: int, is_attack: bool = True) -> int:
        """받는 데미지 1.5배."""
        if self.duration > 0:
            return int(amount * 1.5)
        return amount

    def tick_duration(self) -> None:
        """지속시간 감소."""
        self.duration -= 1
        self.amount = self.duration
        if self.duration <= 0:
            self.remove()


class Weak(STS2Power):
    """약화 — 주는 데미지 0.75배."""
    power_id = "weak"
    name = "Weak"
    is_debuff = True
    damage_side = "outgoing"

    def __init__(self, amount: int = 0):
        super().__init__(amount)
        self.duration = amount

    def modify_damage(self, amount: int, is_attack: bool = True) -> int:
        """주는 데미지 0.75배."""
        if self.duration > 0 and is_attack:
            return int(amount * 0.75)
        return amount

    def tick_duration(self) -> None:
        """지속시간 감소."""
        self.duration -= 1
        self.amount = self.duration
        if self.duration <= 0:
            self.remove()


class Frail(STS2Power):
    """허약성 — 블록 0.75배."""
    power_id = "frail"
    name = "Frail"
    is_debuff = True

    def __init__(self, amount: int = 0):
        super().__init__(amount)
        self.duration = amount

    def modify_block(self, amount: int) -> int:
        """블록 0.75배."""
        if self.duration > 0:
            return int(amount * 0.75)
        return amount

    def tick_duration(self) -> None:
        """지속시간 감소."""
        self.duration -= 1
        self.amount = self.duration
        if self.duration <= 0:
            self.remove()


class Burning(STS2Power):
    """화상 — 턴 종료 시 HP 손실."""
    power_id = "burning"
    name = "Burning"
    is_debuff = True

    def tick_duration(self) -> None:
        """턴 종료 시 HP 손실."""
        if self.owner and self.amount > 0:
            self.owner.lose_hp(self.amount)
            # 화상은 지속시간이 없음, 영구적


class Poison(STS2Power):
    """중독 — 턴 종료 시 HP 손실, amount 감소."""
    power_id = "poison"
    name = "Poison"
    is_debuff = True

    def tick_duration(self) -> None:
        """턴 종료 시 HP 손실."""
        if self.owner and self.amount > 0:
            self.owner.lose_hp(self.amount)
            self.amount -= 1
            if self.amount <= 0:
                self.remove()


class Thorns(STS2Power):
    """가시 — 공격받으면 반격 데미지."""
    power_id = "thorns"
    name = "Thorns"
    is_debuff = False

    def on_take_damage(self, attacker: Optional[Creature], hp_lost: int) -> None:
        """피격 시 반격."""
        if self.owner and attacker and attacker != self.owner and hp_lost > 0:
            attacker.take_damage(self.amount, source=self.owner)


class Ritual(STS2Power):
    """의식 — 턴 시작마다 Strength 획득."""
    power_id = "ritual"
    name = "Ritual"
    is_debuff = False

    def on_turn_start(self) -> None:
        """턴 시작 시 Strength 부여."""
        if self.owner and self.amount > 0:
            strength = Strength(self.amount)
            strength.apply(self.owner, self.owner)


class Metallicize(STS2Power):
    """금속화 — 턴 종료마다 블록 획득."""
    power_id = "metallicize"
    name = "Metallicize"
    is_debuff = False

    def on_turn_end(self) -> None:
        """턴 종료 시 블록 획득."""
        if self.owner and self.amount > 0:
            self.owner.gain_block(self.amount)


# ══════════════════════════════════════════
# Phase 3 미구현 파워들
# ══════════════════════════════════════════

class HexPower(STS2Power):
    """헥스 — 플레이어 카드에 Ethereal 부여."""
    power_id = "hex"
    name = "Hex"
    is_debuff = True

    def __init__(self, amount: int = 0):
        super().__init__(amount)
        self.duration = amount

    def tick_duration(self) -> None:
        """지속시간 감소."""
        self.duration -= 1
        self.amount = self.duration
        if self.duration <= 0:
            self.remove()


class TangledPower(STS2Power):
    """얽힘 (Entangle) — 공격 카드 플레이 차단."""
    power_id = "tangled"
    name = "Entangle"
    is_debuff = True

    def __init__(self, amount: int = 0):
        super().__init__(amount)
        self.duration = amount

    def tick_duration(self) -> None:
        """지속시간 감소."""
        self.duration -= 1
        self.amount = self.duration
        if self.duration <= 0:
            self.remove()


class ShackledPower(STS2Power):
    """쇠사슬 (Shackled) — 이번 턴 카드 플레이 전체 불가."""
    power_id = "shackled"
    name = "Shackled"
    is_debuff = True

    def __init__(self, amount: int = 0):
        super().__init__(amount)
        self.duration = amount

    def tick_duration(self) -> None:
        """지속시간 감소."""
        self.duration -= 1
        self.amount = self.duration
        if self.duration <= 0:
            self.remove()


class CurlUpPower(STS2Power):
    """웅크리기 (Curl Up) — 첫 피격 시 블록 획득."""
    power_id = "curl_up"
    name = "Curl Up"
    is_debuff = False

    def on_take_damage(self, attacker: Optional[Creature], hp_lost: int) -> None:
        """첫 피격 시 블록 획득 후 제거."""
        if self.owner and hp_lost > 0:
            self.owner.gain_block(self.amount)
            self.remove()


class Focus(STS2Power):
    """집중 — 오브 패시브/이보크 값 증가 (Defect). 음수 가능."""
    power_id = "focus"
    name = "Focus"
    is_debuff = False


class Artifact(STS2Power):
    """아티팩트 — 디버프를 1회 무효화 (스택 소모). Creature.apply_power에서 처리."""
    power_id = "artifact"
    name = "Artifact"
    is_debuff = False


class Plating(STS2Power):
    """도금 — 턴 종료마다 스택만큼 블록 획득, 비차단 피해를 받으면 스택 1 감소.
    (디컴파일 PlatingPower — SewerClam 등)"""
    power_id = "plating"
    name = "Plating"
    is_debuff = False

    def on_turn_end(self) -> None:
        if self.owner and self.amount > 0:
            self.owner.gain_block(self.amount)

    def on_take_damage(self, attacker, hp_lost: int) -> None:
        if hp_lost > 0 and self.amount > 0:
            self.amount -= 1
            if self.amount <= 0:
                self.remove()


# ══════════════════════════════════════════
# 카드 유래 파워 (Ironclad 카드 풀이 요구)
# ══════════════════════════════════════════

class Barricade(STS2Power):
    """바리케이드 — 턴 시작 시 블록이 사라지지 않음 (Creature.start_of_turn에서 검사)."""
    power_id = "barricade"
    name = "Barricade"
    is_debuff = False


class NoDraw(STS2Power):
    """드로우 불가 — 이번 턴 카드 드로우 차단 (CombatState.draw_cards에서 검사)."""
    power_id = "no_draw"
    name = "No Draw"
    is_debuff = True

    def __init__(self, amount: int = 1):
        super().__init__(amount)
        self.duration = amount

    def tick_duration(self) -> None:
        self.duration -= 1
        self.amount = self.duration
        if self.duration <= 0:
            self.remove()


class DemonForm(STS2Power):
    """악마의 형상 — 매 턴 시작 시 힘 +amount."""
    power_id = "demon_form"
    name = "Demon Form"
    is_debuff = False

    def on_turn_start(self) -> None:
        if self.owner and self.amount > 0:
            self.owner.apply_power(Strength(self.amount))


class FeelNoPain(STS2Power):
    """고통 감내 — 카드가 소모될 때마다 블록 +amount."""
    power_id = "feel_no_pain"
    name = "Feel No Pain"
    is_debuff = False

    def on_card_exhausted(self, card, combat) -> None:
        if self.owner and self.amount > 0:
            self.owner.gain_block(self.amount)


class DarkEmbrace(STS2Power):
    """어둠의 포옹 — 카드가 소모될 때마다 amount장 드로우."""
    power_id = "dark_embrace"
    name = "Dark Embrace"
    is_debuff = False

    def on_card_exhausted(self, card, combat) -> None:
        if combat is not None and self.amount > 0:
            combat.draw_cards(self.amount)


class Rage(STS2Power):
    """분노 — 이번 턴 공격 카드 플레이마다 블록 +amount (턴 종료 시 제거)."""
    power_id = "rage"
    name = "Rage"
    is_debuff = False

    def on_card_played(self, card, combat) -> None:
        from sts2_sim.models.sts2_card import CardType
        if self.owner and card.card_type == CardType.ATTACK and self.amount > 0:
            self.owner.gain_block(self.amount)

    def tick_duration(self) -> None:
        self.remove()


class FlameBarrier(STS2Power):
    """화염 방벽 — 이번 라운드 피격 시 공격자에게 amount 반격.
    몬스터 턴이 끝난 뒤 제거 (플레이어 턴 종료 tick에서 지우면 반격 불가)."""
    power_id = "flame_barrier"
    name = "Flame Barrier"
    is_debuff = False

    def on_take_damage(self, attacker, hp_lost: int) -> None:
        if attacker is not None and attacker is not self.owner and self.amount > 0:
            attacker.take_damage(self.amount, source=self.owner)

    def on_enemy_turn_end(self) -> None:
        self.remove()


class Juggernaut(STS2Power):
    """저거너트 — 블록 획득 시 무작위 적에게 amount 피해."""
    power_id = "juggernaut"
    name = "Juggernaut"
    is_debuff = False

    def on_block_gained(self, gained: int) -> None:
        if self.amount <= 0 or gained <= 0 or self.owner is None:
            return
        combat = getattr(self.owner, "combat", None)
        if combat is None:
            return
        enemies = [e for e in combat.alive_enemies if not e.is_dead]
        if enemies:
            target = combat.rng.choice(enemies)
            target.take_damage(self.amount, source=self.owner)


class Rupture(STS2Power):
    """파열 — 카드로 HP를 잃을 때마다 힘 +amount (lose_hp 훅)."""
    power_id = "rupture"
    name = "Rupture"
    is_debuff = False

    def on_hp_lost(self, amount_lost: int) -> None:
        if self.owner and amount_lost > 0 and self.amount > 0:
            self.owner.apply_power(Strength(self.amount))


class Vigor(STS2Power):
    """기세 — 다음 공격 카드 데미지 +amount (1회 소모)."""
    power_id = "vigor"
    name = "Vigor"
    is_debuff = False
    damage_side = "outgoing"

    def modify_damage(self, amount: int, is_attack: bool = True) -> int:
        if is_attack and self.amount > 0:
            bonus = self.amount
            self.amount = 0
            self.remove()
            return amount + bonus
        return amount


class TempStrength(STS2Power):
    """임시 힘 (TemporaryStrengthPower) — 이번 턴만 힘 ±amount (SetupStrike/Mangle).
    음수 가능. 소유자 턴 종료 tick에서 제거."""
    power_id = "temp_strength"
    name = "Temporary Strength"
    is_debuff = False
    damage_side = "outgoing"

    def modify_damage(self, amount: int, is_attack: bool = True) -> int:
        if is_attack:
            return max(0, amount + self.amount)
        return amount

    def tick_duration(self) -> None:
        self.remove()


class Aggression(STS2Power):
    """호전성 — 턴 시작 시 버림 더미의 공격 카드 amount장을 손패로 + 업그레이드."""
    power_id = "aggression"
    name = "Aggression"
    is_debuff = False

    def on_turn_start(self) -> None:
        from sts2_sim.models.sts2_card import CardType
        combat = getattr(self.owner, "combat", None)
        if combat is None:
            return
        attacks = [c for c in combat.discard_pile if c.card_type == CardType.ATTACK]
        combat.rng.shuffle(attacks)
        for card in attacks[:self.amount]:
            combat.discard_pile.remove(card)
            combat.hand.append(card)
            if not card.upgraded:
                card.upgrade()


class Colossus(STS2Power):
    """거상 — 취약 상태인 공격자의 공격 데미지 절반. 적 턴 종료마다 1 감소."""
    power_id = "colossus"
    name = "Colossus"
    is_debuff = False
    damage_side = "incoming"

    def modify_incoming(self, amount: int, source) -> int:
        if (source is not None and hasattr(source, "get_power_amount")
                and source.get_power_amount("vulnerable") > 0):
            return amount // 2
        return amount

    def on_enemy_turn_end(self) -> None:
        self.amount -= 1
        if self.amount <= 0:
            self.remove()


class CrimsonMantle(STS2Power):
    """진홍 망토 — 턴 시작마다 블록 +amount. 카드 플레이마다 자해 1 누적."""
    power_id = "crimson_mantle"
    name = "Crimson Mantle"
    is_debuff = False

    def __init__(self, amount: int = 0):
        super().__init__(amount)
        self.self_damage = 0

    def on_turn_start(self) -> None:
        if self.owner is None:
            return
        if self.self_damage > 0:
            self.owner.lose_hp(self.self_damage)
        # 원본은 Unpowered 블록 (Dexterity 미적용)
        self.owner._block += self.amount


class Cruelty(STS2Power):
    """잔혹함 — 취약 배율 +amount% (Creature.take_damage에서 공격자 측 검사)."""
    power_id = "cruelty"
    name = "Cruelty"
    is_debuff = False


class Hellraiser(STS2Power):
    """헬레이저 — Strike 태그 카드를 뽑으면 즉시 자동 플레이."""
    power_id = "hellraiser"
    name = "Hellraiser"
    is_debuff = False

    def on_card_drawn(self, card, combat) -> None:
        if "strike" in card.tags and card in combat.hand:
            combat.auto_play(card)


class Inferno(STS2Power):
    """업화 — 턴 시작 시 자해(플레이 횟수만큼 누적), 자기 턴 HP 손실 시
    모든 적에게 amount 피해. (원본은 카드/자해 출처만 — lose_hp 훅으로 근사)"""
    power_id = "inferno"
    name = "Inferno"
    is_debuff = False

    def __init__(self, amount: int = 0):
        super().__init__(amount)
        self.self_damage = 0

    def on_turn_start(self) -> None:
        if self.owner and self.self_damage > 0:
            self.owner.lose_hp(self.self_damage)

    def on_hp_lost(self, amount_lost: int) -> None:
        combat = getattr(self.owner, "combat", None)
        if combat is None or self.amount <= 0:
            return
        for enemy in list(combat.alive_enemies):
            enemy.take_damage(self.amount, source=self.owner)


class Juggling(STS2Power):
    """저글링 — 매 턴 3번째 공격 카드 플레이 시 그 카드의 사본 amount장을 손패에."""
    power_id = "juggling"
    name = "Juggling"
    is_debuff = False

    def __init__(self, amount: int = 0):
        super().__init__(amount)
        self.attacks_this_turn = 0

    def on_card_played(self, card, combat) -> None:
        from sts2_sim.models.sts2_card import CardType, create_card
        if card.card_type != CardType.ATTACK:
            return
        self.attacks_this_turn += 1
        if self.attacks_this_turn == 3:
            for _ in range(self.amount):
                clone = create_card(card.card_id)
                if clone:
                    if card.upgraded:
                        clone.upgrade()
                    combat.hand.append(clone)

    def on_turn_end(self) -> None:
        self.attacks_this_turn = 0


class NoEnergyGain(STS2Power):
    """에너지 획득 불가 — 이번 턴 추가 에너지 획득 차단 (ExpectAFight)."""
    power_id = "no_energy_gain"
    name = "No Energy Gain"
    is_debuff = True

    def tick_duration(self) -> None:
        self.remove()


class OneTwoPunch(STS2Power):
    """원투 펀치 — 다음 amount장의 공격 카드가 2회 발동 (combat.play_card에서 처리)."""
    power_id = "one_two_punch"
    name = "One-Two Punch"
    is_debuff = False

    def tick_duration(self) -> None:
        self.remove()  # 턴 종료 시 제거


class Pyre(STS2Power):
    """장작불 — 최대 에너지 +amount (적용 시 즉시 반영)."""
    power_id = "pyre"
    name = "Pyre"
    is_debuff = False


class Stampede(STS2Power):
    """쇄도 — 턴 종료 시 손패의 무작위 공격 카드 amount장을 자동 플레이."""
    power_id = "stampede"
    name = "Stampede"
    is_debuff = False

    def on_turn_end(self) -> None:
        from sts2_sim.models.sts2_card import CardType
        combat = getattr(self.owner, "combat", None)
        if combat is None:
            return
        for _ in range(self.amount):
            attacks = [c for c in combat.hand
                       if c.card_type == CardType.ATTACK and c.playable]
            if not attacks or not combat.alive_enemies:
                return
            combat.auto_play(combat.rng.choice(attacks))


class Unmovable(STS2Power):
    """부동 — 매 턴 처음 amount회의 블록 획득이 2배 (원본은 카드/무브 블록 한정)."""
    power_id = "unmovable"
    name = "Unmovable"
    is_debuff = False

    def __init__(self, amount: int = 0):
        super().__init__(amount)
        self.used_this_turn = 0

    def on_turn_start(self) -> None:
        self.used_this_turn = 0

    def modify_block(self, amount: int) -> int:
        if amount > 0 and self.used_this_turn < self.amount:
            self.used_this_turn += 1
            return amount * 2
        return amount


class Vicious(STS2Power):
    """악랄함 — 적에게 취약을 걸 때마다 amount장 드로우 (Creature.apply_power에서 트리거)."""
    power_id = "vicious"
    name = "Vicious"
    is_debuff = False


class FreeAttack(STS2Power):
    """공짜 공격 — 다음 amount장의 공격 카드 비용 0 (Unrelenting).
    차감은 비용 지불 시점(combat.play_card)에 처리 — 효과 후 차감하면
    Unrelenting 자신이 방금 부여한 스택을 소모해버린다 (원본 BeforeCardPlayed 대응)."""
    power_id = "free_attack"
    name = "Free Attack"
    is_debuff = False

    def modify_card_cost(self, card, cost: int) -> int:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type == CardType.ATTACK:
            return 0
        return cost


class Corruption(STS2Power):
    """부패 — 스킬 카드 비용 0, 플레이 시 소모 (combat.play_card에서 소모 처리)."""
    power_id = "corruption"
    name = "Corruption"
    is_debuff = False

    def modify_card_cost(self, card, cost: int) -> int:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type == CardType.SKILL:
            return 0
        return cost


# ══════════════════════════════════════════
# 파워 팩토리
# ══════════════════════════════════════════

POWER_REGISTRY = {
    "strength": Strength,
    "focus": Focus,
    "artifact": Artifact,
    "plating": Plating,
    "barricade": Barricade,
    "no_draw": NoDraw,
    "demon_form": DemonForm,
    "feel_no_pain": FeelNoPain,
    "dark_embrace": DarkEmbrace,
    "rage": Rage,
    "flame_barrier": FlameBarrier,
    "juggernaut": Juggernaut,
    "rupture": Rupture,
    "vigor": Vigor,
    "temp_strength": TempStrength,
    "aggression": Aggression,
    "colossus": Colossus,
    "crimson_mantle": CrimsonMantle,
    "cruelty": Cruelty,
    "hellraiser": Hellraiser,
    "inferno": Inferno,
    "juggling": Juggling,
    "no_energy_gain": NoEnergyGain,
    "one_two_punch": OneTwoPunch,
    "pyre": Pyre,
    "stampede": Stampede,
    "unmovable": Unmovable,
    "vicious": Vicious,
    "free_attack": FreeAttack,
    "corruption": Corruption,
    "dexterity": Dexterity,
    "vulnerable": Vulnerable,
    "weak": Weak,
    "frail": Frail,
    "burning": Burning,
    "poison": Poison,
    "thorns": Thorns,
    "ritual": Ritual,
    "metallicize": Metallicize,
    "hex": HexPower,
    "tangled": TangledPower,
    "shackled": ShackledPower,
    "curl_up": CurlUpPower,
}


def create_power(power_id: str, amount: int = 0) -> Optional[STS2Power]:
    """파워 생성."""
    power_class = POWER_REGISTRY.get(power_id)
    if power_class:
        return power_class(amount)
    return None
