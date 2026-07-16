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
        """받는 데미지 1.5배 (Debilitate 보유 시 2.0배)."""
        if self.duration > 0:
            mult = 1.5
            if (self.owner is not None and hasattr(self.owner, "get_power_amount")
                    and self.owner.get_power_amount("debilitate") > 0):
                mult = mult + (mult - 1)  # 원본 DebilitatePower: 1.5 → 2.0
            return int(amount * mult)
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
        """주는 데미지 0.75배 (Debilitate 보유 시 0.5배)."""
        if self.duration > 0 and is_attack:
            mult = 0.75
            if (self.owner is not None and hasattr(self.owner, "get_power_amount")
                    and self.owner.get_power_amount("debilitate") > 0):
                mult = mult - (1 - mult)  # 원본 DebilitatePower: 0.75 → 0.5
            return int(amount * mult)
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
    """중독 — 턴마다 amount만큼 HP 손실 후 1 감소.
    상대가 Accelerant를 갖고 있으면 추가 발동 (min(amount, 1+Accelerant)회)."""
    power_id = "poison"
    name = "Poison"
    is_debuff = True

    def _accelerant(self) -> int:
        """상대 진영의 Accelerant 스택 합."""
        combat = (getattr(self.owner, "combat", None)
                  or getattr(self.owner, "combat_state", None))
        if combat is None:
            return 0
        if self.owner is getattr(combat, "player", None):
            return sum(e.get_power_amount("accelerant") for e in combat.alive_enemies)
        return combat.player.get_power_amount("accelerant")

    def tick_duration(self) -> None:
        if not (self.owner and self.amount > 0):
            return
        triggers = min(self.amount, 1 + self._accelerant())
        for _ in range(triggers):
            if self.amount <= 0 or self.owner.is_dead:
                break
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
    """도금 — 턴 종료마다 스택만큼 블록 획득, 소유자의 매 턴 시작마다 스택 1 감소
    (피격 여부 무관). 단, 파워가 이미 존재한 채로 맞이하는 라운드 1 시작은 예외
    (원본 PlatingPower.AfterSideTurnStart — TurnNumber/RoundNumber != 1)."""
    power_id = "plating"
    name = "Plating"
    is_debuff = False

    def on_turn_end(self) -> None:
        if self.owner and self.amount > 0:
            self.owner.gain_block(self.amount)

    def on_turn_start(self) -> None:
        combat = getattr(self.owner, "combat", None) or getattr(self.owner, "combat_state", None)
        if combat is not None and getattr(combat, "turn", 0) <= 1:
            return  # 라운드 1은 감소 제외 (개전 Plating 보유 몬스터 대응)
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
# 카드 유래 파워 (Silent 카드 풀이 요구 — Phase 6c)
# ══════════════════════════════════════════

class Accelerant(STS2Power):
    """촉진제 — 마커. Poison이 이 파워를 보고 추가 발동 (Poison.tick_duration)."""
    power_id = "accelerant"
    name = "Accelerant"
    is_debuff = False


class Accuracy(STS2Power):
    """정확성 — Shiv 데미지 +amount (Shiv._damage에서 참조)."""
    power_id = "accuracy"
    name = "Accuracy"
    is_debuff = False


class Afterimage(STS2Power):
    """잔상 — 카드 플레이마다 블록 +amount."""
    power_id = "afterimage"
    name = "Afterimage"
    is_debuff = False

    def on_card_played(self, card, combat) -> None:
        if self.owner and self.amount > 0:
            self.owner.gain_block(self.amount)


class TempDexterity(STS2Power):
    """임시 민첩 (AnticipatePower 등) — 이번 턴만 블록 +amount."""
    power_id = "temp_dexterity"
    name = "Temporary Dexterity"
    is_debuff = False

    def modify_block(self, amount: int) -> int:
        return max(0, amount + self.amount)

    def tick_duration(self) -> None:
        self.remove()


class Blur(STS2Power):
    """흐릿함 — 턴 시작 시 블록이 사라지지 않음 (스택 1 감소).
    블록 유지는 Creature.start_of_turn에서 검사."""
    power_id = "blur"
    name = "Blur"
    is_debuff = False

    def on_turn_start(self) -> None:
        self.amount -= 1
        if self.amount <= 0:
            self.remove()


class Burst(STS2Power):
    """연속 발동 — 다음 amount장의 스킬 카드가 2회 발동 (combat.play_card 처리).
    턴 종료 시 제거."""
    power_id = "burst"
    name = "Burst"
    is_debuff = False

    def tick_duration(self) -> None:
        self.remove()


class CorrosiveWave(STS2Power):
    """부식의 파도 — 이번 턴 카드를 뽑을 때마다 모든 적에게 중독 amount. 턴 종료 시 제거."""
    power_id = "corrosive_wave"
    name = "Corrosive Wave"
    is_debuff = False

    def on_card_drawn(self, card, combat) -> None:
        if self.amount <= 0:
            return
        for enemy in list(combat.alive_enemies):
            enemy.apply_power(Poison(self.amount), applier=self.owner)

    def tick_duration(self) -> None:
        self.remove()


class Envenom(STS2Power):
    """독살 — 공격으로 비차단 피해를 줄 때마다 중독 amount (_deal_attack에서 처리)."""
    power_id = "envenom"
    name = "Envenom"
    is_debuff = False


class FanOfKnives(STS2Power):
    """칼날의 부채 — Shiv가 전체 공격이 된다 (Shiv.use에서 참조)."""
    power_id = "fan_of_knives"
    name = "Fan of Knives"
    is_debuff = False


class InfiniteBlades(STS2Power):
    """무한의 칼날 — 턴 시작마다 Shiv amount장 생성."""
    power_id = "infinite_blades"
    name = "Infinite Blades"
    is_debuff = False

    def on_turn_start(self) -> None:
        combat = getattr(self.owner, "combat", None)
        if combat is not None and self.amount > 0:
            combat.create_shivs(self.amount)


class MasterPlanner(STS2Power):
    """책략가 — 플레이한 스킬 카드에 Sly 부여 (영구)."""
    power_id = "master_planner"
    name = "Master Planner"
    is_debuff = False

    def on_card_played(self, card, combat) -> None:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type == CardType.SKILL:
            card.is_sly = True


class Nightmare(STS2Power):
    """악몽 — 다음 턴 시작 시 선택한 카드의 사본 amount장을 손패에."""
    power_id = "nightmare"
    name = "Nightmare"
    is_debuff = False

    def __init__(self, amount: int = 0):
        super().__init__(amount)
        self.selected_card = None

    def on_turn_start(self) -> None:
        from sts2_sim.models.sts2_card import create_card
        combat = getattr(self.owner, "combat", None)
        if combat is not None and self.selected_card is not None:
            for _ in range(self.amount):
                clone = create_card(self.selected_card.card_id)
                if clone:
                    if self.selected_card.upgraded:
                        clone.upgrade()
                    combat.hand.append(clone)
        self.remove()


class NoxiousFumes(STS2Power):
    """유독가스 — 턴 시작마다 모든 적에게 중독 amount."""
    power_id = "noxious_fumes"
    name = "Noxious Fumes"
    is_debuff = False

    def on_turn_start(self) -> None:
        combat = getattr(self.owner, "combat", None)
        if combat is None or self.amount <= 0:
            return
        for enemy in list(combat.alive_enemies):
            enemy.apply_power(Poison(self.amount), applier=self.owner)


class Outbreak(STS2Power):
    """창궐 — 적에게 중독을 걸 때마다 모든 적에게 amount 피해
    (Creature.apply_power에서 트리거)."""
    power_id = "outbreak"
    name = "Outbreak"
    is_debuff = False


class PhantomBlades(STS2Power):
    """환영 칼날 — Shiv에 Retain 부여, 매 턴 첫 Shiv 데미지 +amount."""
    power_id = "phantom_blades"
    name = "Phantom Blades"
    is_debuff = False


class SerpentForm(STS2Power):
    """뱀의 형상 — 카드 플레이마다 무작위 적에게 amount 피해."""
    power_id = "serpent_form"
    name = "Serpent Form"
    is_debuff = False

    def on_card_played(self, card, combat) -> None:
        if self.amount <= 0 or not combat.alive_enemies:
            return
        target = combat.rng.choice(combat.alive_enemies)
        target.take_damage(self.amount, source=self.owner)


class DoubleDamage(STS2Power):
    """더블 데미지 — 이번 턴 공격 데미지 2배 (ShadowStep이 부여)."""
    power_id = "double_damage"
    name = "Double Damage"
    is_debuff = False
    damage_side = "outgoing"

    def modify_damage(self, amount: int, is_attack: bool = True) -> int:
        if is_attack and self.amount > 0:
            return amount * 2
        return amount

    def tick_duration(self) -> None:
        self.remove()


class ShadowStep(STS2Power):
    """그림자 밟기 — 다음 턴 시작 시 더블 데미지 amount 부여."""
    power_id = "shadow_step"
    name = "Shadow Step"
    is_debuff = False

    def on_turn_start(self) -> None:
        if self.owner:
            self.owner.apply_power(DoubleDamage(self.amount))
        self.remove()


class Shadowmeld(STS2Power):
    """그림자 융화 — 이번 턴 블록 획득량 2^amount배."""
    power_id = "shadowmeld"
    name = "Shadowmeld"
    is_debuff = False

    def modify_block(self, amount: int) -> int:
        if amount > 0 and self.amount > 0:
            return amount * (2 ** self.amount)
        return amount

    def tick_duration(self) -> None:
        self.remove()


class Speedster(STS2Power):
    """스피드스터 — 턴 시작 드로우 외 추가 드로우마다 모든 적에게 amount 피해."""
    power_id = "speedster"
    name = "Speedster"
    is_debuff = False

    def on_card_drawn(self, card, combat) -> None:
        if self.amount <= 0 or getattr(combat, "in_hand_draw", False):
            return
        for enemy in list(combat.alive_enemies):
            enemy.take_damage(self.amount, source=self.owner)


class Strangle(STS2Power):
    """교살 — (적에게 적용) 시전자가 카드를 플레이할 때마다 amount 비차단 피해.
    combat.play_card에서 트리거, 적 턴 종료 tick에서 제거."""
    power_id = "strangle"
    name = "Strangle"
    is_debuff = True

    def tick_duration(self) -> None:
        self.remove()


class TheHunt(STS2Power):
    """사냥 — 성공 표식 (실제 추가 보상은 TheHunt 카드/런 루프가 처리)."""
    power_id = "the_hunt"
    name = "The Hunt"
    is_debuff = False


class ToolsOfTheTrade(STS2Power):
    """장인의 도구 — 턴 시작 드로우 +amount, 드로우 후 amount장 버리기."""
    power_id = "tools_of_the_trade"
    name = "Tools of the Trade"
    is_debuff = False

    def modify_hand_draw(self, count: int) -> int:
        return count + self.amount

    def after_hand_draw(self, combat) -> None:
        combat.discard_from_hand(self.amount)


class Tracking(STS2Power):
    """추적 — 약화 상태의 적에게 주는 공격 데미지 +amount% (_deal_attack에서 처리)."""
    power_id = "tracking"
    name = "Tracking"
    is_debuff = False


class WellLaidPlans(STS2Power):
    """치밀한 계획 — 턴 종료 시 카드 amount장을 유지 [선택→무작위]."""
    power_id = "well_laid_plans"
    name = "Well-Laid Plans"
    is_debuff = False

    def on_before_hand_discard(self, combat) -> None:
        candidates = [c for c in combat.hand
                      if not c.retains and not c._retain_this_turn
                      and not c.is_ethereal]
        combat.rng.shuffle(candidates)
        for card in candidates[:self.amount]:
            card._retain_this_turn = True


class WraithFormPower(STS2Power):
    """망령의 형상 (디버프) — 턴 시작마다 민첩 -amount."""
    power_id = "wraith_form"
    name = "Wraith Form"
    is_debuff = True

    def on_turn_start(self) -> None:
        if self.owner and self.amount > 0:
            self.owner.apply_power(Dexterity(-self.amount))


class Intangible(STS2Power):
    """비실체 — 받는 피해를 1로 제한. 적 턴 종료마다 1 감소."""
    power_id = "intangible"
    name = "Intangible"
    is_debuff = False
    damage_side = "incoming"

    def modify_incoming(self, amount: int, source) -> int:
        if self.amount > 0 and amount > 1:
            return 1
        return amount

    def on_enemy_turn_end(self) -> None:
        self.amount -= 1
        if self.amount <= 0:
            self.remove()


class BlockNextTurn(STS2Power):
    """다음 턴 블록 (DodgeAndRoll) — 턴 시작 시 amount 블록 획득 후 제거."""
    power_id = "block_next_turn"
    name = "Block Next Turn"
    is_debuff = False

    def on_turn_start(self) -> None:
        if self.owner and self.amount > 0:
            # 원본은 Unpowered 블록 (Dexterity 미적용)
            self.owner._block += self.amount
        self.remove()


class DrawCardsNextTurn(STS2Power):
    """다음 턴 드로우 +amount (Predator)."""
    power_id = "draw_next_turn"
    name = "Draw Cards Next Turn"
    is_debuff = False

    def modify_hand_draw(self, count: int) -> int:
        bonus = self.amount
        self.remove()
        return count + bonus


class FreeSkill(STS2Power):
    """공짜 스킬 — 다음 amount장의 스킬 카드 비용 0 (Pounce).
    차감은 combat.play_card에서 비용 지불 시점에 처리."""
    power_id = "free_skill"
    name = "Free Skill"
    is_debuff = False

    def modify_card_cost(self, card, cost: int) -> int:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type == CardType.SKILL:
            return 0
        return cost


# ══════════════════════════════════════════
# Defect 카드 파워 (Phase 6d)
# ══════════════════════════════════════════

class TempFocus(STS2Power):
    """임시 집중 (TemporaryFocusPower) — 이번 턴만 Focus +amount.
    FocusedStrike/Hotfix/Synchronize. 오브 _focus()가 focus+temp_focus를 합산."""
    power_id = "temp_focus"
    name = "Temporary Focus"
    is_debuff = False

    def tick_duration(self) -> None:
        self.remove()


class BiasedCognition(STS2Power):
    """편향된 인지 (디버프) — 턴 시작마다 Focus -amount."""
    power_id = "biased_cognition"
    name = "Biased Cognition"
    is_debuff = True

    def on_turn_start(self) -> None:
        if self.owner and self.amount > 0:
            self.owner.apply_power(Focus(-self.amount))


class Buffer(STS2Power):
    """버퍼 — 다음 amount회의 HP 손실을 무효화 (원본 ModifyHpLostAfterOstyLate)."""
    power_id = "buffer"
    name = "Buffer"
    is_debuff = False

    def modify_hp_lost(self, amount: int) -> int:
        if amount > 0 and self.amount > 0:
            self.amount -= 1
            if self.amount <= 0:
                self.remove()
            return 0
        return amount


class EnergyNextTurn(STS2Power):
    """다음 턴 에너지 +amount (ChargeBattery/Scavenge — EnergyNextTurnPower)."""
    power_id = "energy_next_turn"
    name = "Energy Next Turn"
    is_debuff = False

    def after_energy_reset(self) -> None:
        if self.owner:
            self.owner.gain_energy(self.amount)
        self.remove()


class Coolant(STS2Power):
    """냉각수 — 턴 시작마다 (보유 오브 종류 수 × amount) 블록 (Unpowered)."""
    power_id = "coolant"
    name = "Coolant"
    is_debuff = False

    def on_turn_start(self) -> None:
        queue = getattr(self.owner, "orb_queue", None)
        if queue is None:
            return
        kinds = len({o.orb_id for o in queue.orbs})
        if kinds > 0:
            self.owner._block += kinds * self.amount  # 원본 Unpowered — 민첩 미적용


class ConsumingShadow(STS2Power):
    """어둠 포식 — 턴 종료 시 가장 최근 오브를 amount회 이보크 (OrbCmd.EvokeLast)."""
    power_id = "consuming_shadow"
    name = "Consuming Shadow"
    is_debuff = False

    def on_turn_end(self) -> None:
        combat = getattr(self.owner, "combat", None)
        queue = getattr(self.owner, "orb_queue", None)
        if combat is None or queue is None or len(queue) == 0:
            return
        for _ in range(self.amount):
            queue.evoke_last(combat)


class CreativeAI(STS2Power):
    """창의적 AI — 매 턴 드로우 전에 무작위 파워 카드 amount장을 손패에 생성."""
    power_id = "creative_ai"
    name = "Creative AI"
    is_debuff = False

    def before_hand_draw(self, combat) -> None:
        from sts2_sim.cards.defect import DEFECT_POWER_CARD_IDS
        from sts2_sim.models.sts2_card import create_card
        for _ in range(self.amount):
            if len(combat.hand) >= 10:
                break
            card = create_card(combat.rng.choice(DEFECT_POWER_CARD_IDS))
            if card:
                combat.hand.append(card)


class EchoForm(STS2Power):
    """메아리 형상 — 매 턴 처음 amount장의 카드를 2회 발동 (원본 ModifyCardPlayCount).
    발동 판정은 combat.play_card에서 처리."""
    power_id = "echo_form"
    name = "Echo Form"
    is_debuff = False


class Feral(STS2Power):
    """야성 — 매 턴 처음 amount장의 0코스트 공격 카드가 손패로 되돌아온다.
    (원본 ModifyCardPlayResultPileTypeAndPosition — 판정은 combat._settle_card)
    적용 시 used_this_turn은 이번 턴 이미 플레이한 0코스트 공격 수로 초기화된다
    (원본 AfterApplied — FeralCard.use에서 배선)."""
    power_id = "feral"
    name = "Feral"
    is_debuff = False

    def __init__(self, amount: int = 0):
        super().__init__(amount)
        self.used_this_turn = 0

    def on_turn_start(self) -> None:
        self.used_this_turn = 0


class Hailstorm(STS2Power):
    """우박 폭풍 — 턴 종료 시 서리 오브를 1개 이상 보유하면 전체 적에게 amount 피해."""
    power_id = "hailstorm"
    name = "Hailstorm"
    is_debuff = False

    def on_turn_end(self) -> None:
        combat = getattr(self.owner, "combat", None)
        queue = getattr(self.owner, "orb_queue", None)
        if combat is None or queue is None:
            return
        if any(o.orb_id == "frost" for o in queue.orbs):
            for enemy in list(combat.alive_enemies):
                enemy.take_damage(self.amount, source=self.owner)  # Unpowered


class Iteration(STS2Power):
    """반복 — 매 턴 첫 상태이상 카드를 드로우하면 카드 amount장 드로우."""
    power_id = "iteration"
    name = "Iteration"
    is_debuff = False

    def __init__(self, amount: int = 0):
        super().__init__(amount)
        self._statuses_drawn_this_turn = 0

    def on_turn_start(self) -> None:
        self._statuses_drawn_this_turn = 0

    def on_card_drawn(self, card, combat) -> None:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type != CardType.STATUS:
            return
        self._statuses_drawn_this_turn += 1
        if self._statuses_drawn_this_turn == 1:
            combat.draw_cards(self.amount)


class LightningRod(STS2Power):
    """피뢰침 — 에너지 리셋 직후 라이트닝 오브 채널, 스택 1 감소."""
    power_id = "lightning_rod"
    name = "Lightning Rod"
    is_debuff = False

    def after_energy_reset(self) -> None:
        from sts2_sim.models.sts2_orb import LightningOrb
        combat = getattr(self.owner, "combat", None)
        queue = getattr(self.owner, "orb_queue", None)
        if queue is not None:
            queue.channel(LightningOrb(), self.owner, combat)
        self.amount -= 1
        if self.amount <= 0:
            self.remove()


class Loop(STS2Power):
    """루프 — 턴 시작 시 선두 오브의 패시브를 amount회 발동."""
    power_id = "loop"
    name = "Loop"
    is_debuff = False

    def on_turn_start(self) -> None:
        combat = getattr(self.owner, "combat", None)
        queue = getattr(self.owner, "orb_queue", None)
        if combat is None or queue is None or len(queue) == 0:
            return
        for _ in range(self.amount):
            if not queue.orbs:
                break
            queue.orbs[0].passive(combat)


class MachineLearning(STS2Power):
    """기계 학습 — 매 턴 드로우 +amount."""
    power_id = "machine_learning"
    name = "Machine Learning"
    is_debuff = False

    def modify_hand_draw(self, count: int) -> int:
        return count + self.amount


class SignalBoost(STS2Power):
    """신호 증폭 — 다음 amount장의 파워 카드를 2회 발동 (combat.play_card에서 차감)."""
    power_id = "signal_boost"
    name = "Signal Boost"
    is_debuff = False


class Smokestack(STS2Power):
    """굴뚝 — 내가 상태이상 카드를 생성할 때마다 전체 적에게 amount 피해 (Unpowered)."""
    power_id = "smokestack"
    name = "Smokestack"
    is_debuff = False

    def on_card_generated(self, card, combat) -> None:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type != CardType.STATUS:
            return
        for enemy in list(combat.alive_enemies):
            enemy.take_damage(self.amount, source=self.owner)


class Spinner(STS2Power):
    """물레 — 에너지 리셋 직후 유리 오브 amount개 채널."""
    power_id = "spinner"
    name = "Spinner"
    is_debuff = False

    def after_energy_reset(self) -> None:
        from sts2_sim.models.sts2_orb import GlassOrb
        combat = getattr(self.owner, "combat", None)
        queue = getattr(self.owner, "orb_queue", None)
        if queue is None:
            return
        for _ in range(self.amount):
            queue.channel(GlassOrb(), self.owner, combat)


class _PowerCardTrigger(STS2Power):
    """파워 카드 플레이 트리거 공통 — 자신을 부여한 그 플레이에는 미발동
    (원본 Storm/Subroutine의 BeforeCardPlayed 기록 방식 대응)."""

    def __init__(self, amount: int = 0):
        super().__init__(amount)
        self._skip_next = False

    def apply(self, owner, applier=None) -> None:
        fresh = self.power_id not in owner._powers
        super().apply(owner, applier)
        if fresh:
            owner._powers[self.power_id]._skip_next = True

    def on_card_played(self, card, combat) -> None:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type != CardType.POWER:
            return
        if self._skip_next:
            self._skip_next = False
            return
        self._trigger(combat)

    def _trigger(self, combat) -> None:
        pass


class Storm(_PowerCardTrigger):
    """폭풍 — 파워 카드를 플레이할 때마다 라이트닝 오브 amount개 채널."""
    power_id = "storm"
    name = "Storm"
    is_debuff = False

    def _trigger(self, combat) -> None:
        from sts2_sim.models.sts2_orb import LightningOrb
        queue = getattr(self.owner, "orb_queue", None)
        if queue is None:
            return
        for _ in range(self.amount):
            queue.channel(LightningOrb(), self.owner, combat)


class Subroutine(_PowerCardTrigger):
    """서브루틴 — 파워 카드를 플레이할 때마다 에너지 +amount."""
    power_id = "subroutine"
    name = "Subroutine"
    is_debuff = False

    def _trigger(self, combat) -> None:
        if self.owner:
            self.owner.gain_energy(self.amount)


class Thunder(STS2Power):
    """천둥 — 라이트닝 오브가 이보크될 때마다 그 대상에게 amount 추가 피해."""
    power_id = "thunder"
    name = "Thunder"
    is_debuff = False

    def after_orb_evoked(self, orb, targets, combat) -> None:
        if orb.orb_id != "lightning":
            return
        for target in targets:
            if not getattr(target, "is_dead", False):
                target.take_damage(self.amount, source=self.owner)  # Unpowered


class TrashToTreasure(STS2Power):
    """쓰레기를 보물로 — 내가 상태이상 카드를 생성할 때마다 무작위 오브 amount개 채널."""
    power_id = "trash_to_treasure"
    name = "Trash to Treasure"
    is_debuff = False

    def on_card_generated(self, card, combat) -> None:
        from sts2_sim.models.sts2_card import CardType
        from sts2_sim.models.sts2_orb import ORB_REGISTRY
        if card.card_type != CardType.STATUS:
            return
        queue = getattr(self.owner, "orb_queue", None)
        if queue is None:
            return
        orb_ids = sorted(ORB_REGISTRY)  # 원본 _validOrbs 5종 전체
        for _ in range(self.amount):
            orb_cls = ORB_REGISTRY[combat.rng.choice(orb_ids)]
            queue.channel(orb_cls(), self.owner, combat)


class FreePower(STS2Power):
    """공짜 파워 (Synthesis — FreePowerPower) — 다음 amount장의 파워 카드 비용 0.
    차감은 combat.play_card에서 비용 지불 시점에 처리."""
    power_id = "free_power"
    name = "Free Power"
    is_debuff = False

    def modify_card_cost(self, card, cost: int) -> int:
        from sts2_sim.models.sts2_card import CardType
        if card.card_type == CardType.POWER:
            return 0
        return cost


# ══════════════════════════════════════════
# Necrobinder 공유 파워
# ══════════════════════════════════════════

class Doom(STS2Power):
    """운명 — 카운터 디버프. 소유자의 턴 종료 시 HP가 amount 이하이면 즉사한다.
    (원본 DoomPower: IsOwnerDoomed = CurrentHp <= Amount, BeforeSideTurnEnd에서 DoomKill)"""
    power_id = "doom"
    name = "Doom"
    is_debuff = True

    def is_owner_doomed(self) -> bool:
        return self.owner is not None and self.owner.current_hp <= self.amount


# ══════════════════════════════════════════
# Necrobinder 카드 파워 (Phase 6e)
# ══════════════════════════════════════════

class Calcify(STS2Power):
    """석회화 — Osty의 파워드 공격에 +amount 피해 (원본 CalcifyPower.ModifyDamageAdditive).
    실제 가산은 sts2_card._deal_attack에서 Osty 공격 판정 시 처리."""
    power_id = "calcify"
    name = "Calcify"
    is_debuff = False


class CalcifyPower(Calcify):
    pass


class CallOfTheVoid(STS2Power):
    """공허의 부름 — 매 턴 드로우 전 무작위 비-Basic/Ancient Necrobinder 카드
    amount장을 Ethereal 부여해 손패에 추가 (원본 CallOfTheVoidPower.BeforeHandDraw)."""
    power_id = "call_of_the_void"
    name = "Call of the Void"
    is_debuff = False

    def before_hand_draw(self, combat) -> None:
        from sts2_sim.cards.necrobinder import NECROBINDER_ETHEREAL_POOL
        from sts2_sim.models.sts2_card import create_card
        for _ in range(self.amount):
            if len(combat.hand) >= 10:
                break
            card = create_card(combat.rng.choice(NECROBINDER_ETHEREAL_POOL))
            if card:
                card.is_ethereal = True
                combat.hand.append(card)


class Countdown(STS2Power):
    """카운트다운 — 매 턴 시작 시 무작위 적 1명에게 Doom amount 부여
    (원본 CountdownPower.AfterSideTurnStart). 소모되지 않고 매턴 반복."""
    power_id = "countdown"
    name = "Countdown"
    is_debuff = False

    def on_turn_start(self) -> None:
        combat = getattr(self.owner, "combat", None)
        if combat is None:
            return
        enemies = combat.alive_enemies
        if enemies:
            combat.rng.choice(enemies).apply_power(Doom(self.amount), applier=self.owner)


class DanseMacabre(STS2Power):
    """죽음의 무도 — 코스트 2 이상 카드를 낼 때마다 amount 블록 (Unpowered).
    (원본 DanseMacabrePower.BeforeCardPlayed, EnergyCost.GetResolved() >= 2)"""
    power_id = "danse_macabre"
    name = "Danse Macabre"
    is_debuff = False

    def on_card_played(self, card, combat) -> None:
        if getattr(card, "_last_paid", 0) >= 2 and self.owner is not None:
            self.owner._block += self.amount  # 원본 Unpowered — 민첩 미적용


class BorrowedTime(STS2Power):
    """빌린 시간 — 이번 턴 동안 모든 카드 코스트 +amount (원본 BorrowedTimePower).
    소유자 턴 종료 시 제거."""
    power_id = "borrowed_time"
    name = "Borrowed Time"
    is_debuff = True

    def modify_card_cost(self, card, cost: int) -> int:
        return cost + self.amount

    def on_turn_end(self) -> None:
        self.remove()


class Demesne(STS2Power):
    """영지 — 매 턴 손패 드로우 +amount, 최대 에너지 +amount (지속)
    (원본 DemesnePower.ModifyHandDraw/ModifyMaxEnergy)."""
    power_id = "demesne"
    name = "Demesne"
    is_debuff = False

    def apply(self, owner, applier=None) -> None:
        delta = self.amount
        super().apply(owner, applier)
        owner.max_energy = getattr(owner, "max_energy", 0) + delta

    def modify_hand_draw(self, count: int) -> int:
        return count + self.amount


class DevourLife(STS2Power):
    """생명 포식 — Soul 카드를 플레이할 때마다 Osty를 amount만큼 소환/강화
    (원본 DevourLifePower.AfterCardPlayed)."""
    power_id = "devour_life"
    name = "Devour Life"
    is_debuff = False

    def on_card_played(self, card, combat) -> None:
        if getattr(card, "card_id", None) == "soul":
            summon = getattr(self.owner, "summon_osty", None)
            if summon:
                summon(self.amount)


class EnfeeblingTouch(STS2Power):
    """쇠약의 손길 — 대상 적이 이번 턴 힘 amount 감소, 적 턴 종료 시 복구
    (원본 EnfeeblingTouchPower : TemporaryStrengthPower)."""
    power_id = "enfeebling_touch"
    name = "Enfeebling Touch"
    is_debuff = True

    def apply(self, owner, applier=None) -> None:
        first = self.power_id not in owner._powers
        super().apply(owner, applier)
        # 최초 적용 시에만 힘 감소 (임시 파워 — 턴 종료에 복구)
        if first:
            owner.apply_power(Strength(-self.amount))

    def on_turn_end(self) -> None:
        if self.owner is not None:
            self.owner.apply_power(Strength(self.amount))
        self.remove()


class Friendship(STS2Power):
    """우정 — 최대 에너지 +amount (지속) (원본 FriendshipPower.ModifyMaxEnergy)."""
    power_id = "friendship"
    name = "Friendship"
    is_debuff = False

    def apply(self, owner, applier=None) -> None:
        delta = self.amount
        super().apply(owner, applier)
        owner.max_energy = getattr(owner, "max_energy", 0) + delta


class Hang(STS2Power):
    """교수 — Hang 카드가 이 적을 칠 때 피해 ×amount배 (원본 HangPower).
    실제 배수는 Hang 카드에서 처리, 여기선 스택만 저장."""
    power_id = "hang"
    name = "Hang"
    is_debuff = True


class Haunt(STS2Power):
    """출몰 — Soul 카드를 플레이할 때마다 무작위 적 1명에게 amount 관통 피해
    (원본 HauntPower.AfterCardPlayed, Unblockable|Unpowered)."""
    power_id = "haunt"
    name = "Haunt"
    is_debuff = False

    def on_card_played(self, card, combat) -> None:
        if getattr(card, "card_id", None) == "soul":
            enemies = combat.alive_enemies
            if enemies:
                combat.rng.choice(enemies).lose_hp(self.amount)  # 관통·무보정


class Lethality(STS2Power):
    """치명 — 매 턴 첫 공격 카드의 피해 ×(1 + amount/100) (원본 LethalityPower).
    실제 배수는 sts2_card._deal_attack에서 combat 첫 공격 플래그로 처리."""
    power_id = "lethality"
    name = "Lethality"
    is_debuff = False


class NecroMastery(STS2Power):
    """강령술 숙련 — Osty가 HP를 잃을 때마다 (잃은 HP × amount)를 모든 적에게 관통 피해
    (원본 NecroMasteryPower.AfterCurrentHpChanged). 반사는 Osty.lose_hp에서 처리."""
    power_id = "necro_mastery"
    name = "Necro Mastery"
    is_debuff = False


class Neurosurge(STS2Power):
    """신경 급증 — 매 턴 시작 시 자신(플레이어)에게 Doom amount 누적
    (원본 NeurosurgePower.AfterSideTurnStart, 자해 Doom)."""
    power_id = "neurosurge"
    name = "Neurosurge"
    is_debuff = True

    def on_turn_start(self) -> None:
        if self.owner is not None:
            self.owner.apply_power(Doom(self.amount), applier=self.owner)


class Oblivion(STS2Power):
    """망각 — 이번 플레이어 턴 동안 카드를 낼 때마다 대상 적에게 Doom amount 부여,
    턴 종료 시 제거 (원본 OblivionPower). 대상은 적용 시점의 지정 적."""
    power_id = "oblivion"
    name = "Oblivion"
    is_debuff = False

    def __init__(self, amount: int = 0, target=None, source_card=None):
        super().__init__(amount)
        self.target = target
        # 이 파워를 부여한 Oblivion 카드 — 그 카드 자신의 플레이는 Doom 미부여.
        # (원본: OblivionPower.BeforeCardPlayed가 파워 부여 전에 이미 지나가 미기록)
        self._source_card = source_card

    def apply(self, owner, applier=None) -> None:
        tgt = self.target
        src = self._source_card
        super().apply(owner, applier)
        existing = owner._powers.get(self.power_id)
        if existing is not None:
            if tgt is not None:
                existing.target = tgt
            existing._source_card = src

    def on_card_played(self, card, combat) -> None:
        if card is self._source_card:
            self._source_card = None  # 자기 적용 카드는 1회만 무시
            return
        if self.target is not None and not self.target.is_dead:
            self.target.apply_power(Doom(self.amount), applier=self.owner)

    def on_turn_end(self) -> None:
        self.remove()


class Pagestorm(STS2Power):
    """책장 폭풍 — Ethereal 카드를 뽑을 때마다 amount장 추가 드로우
    (원본 PagestormPower.AfterCardDrawn)."""
    power_id = "pagestorm"
    name = "Pagestorm"
    is_debuff = False

    def on_card_drawn(self, card, combat) -> None:
        if getattr(card, "is_ethereal", False):
            combat.draw_cards(self.amount)


class ReaperForm(STS2Power):
    """사신의 형상 — 플레이어/Osty의 파워드 공격으로 준 피해만큼 대상에게 Doom 부여
    (원본 ReaperFormPower.AfterDamageGiven). 실제 적용은 _deal_attack에서 처리."""
    power_id = "reaper_form"
    name = "Reaper Form"
    is_debuff = False


class SentryMode(STS2Power):
    """감시 모드 — 매 턴 드로우 전 SweepingGaze amount장을 손패에 추가
    (원본 SentryModePower.BeforeHandDraw)."""
    power_id = "sentry_mode"
    name = "Sentry Mode"
    is_debuff = False

    def before_hand_draw(self, combat) -> None:
        from sts2_sim.models.sts2_card import create_card
        for _ in range(self.amount):
            if len(combat.hand) >= 10:
                break
            card = create_card("sweeping_gaze")
            if card:
                combat.hand.append(card)


class SicEm(STS2Power):
    """공격 명령 — 당신의 Osty가 이 적을 공격하면 Osty를 amount만큼 소환/강화
    (원본 SicEmPower.AfterDamageGiven). 적 턴 종료 시 제거. 발동은 _deal_attack."""
    power_id = "sic_em"
    name = "Sic Em"
    is_debuff = True

    def on_turn_end(self) -> None:
        self.remove()


class SleightOfFlesh(STS2Power):
    """육체의 술책 — 적에게 디버프를 부여할 때마다 그 적에게 amount 피해
    (원본 SleightOfFleshPower.AfterPowerAmountChanged). 발동은 Creature.apply_power."""
    power_id = "sleight_of_flesh"
    name = "Sleight of Flesh"
    is_debuff = False


class Shroud(STS2Power):
    """장막 — 자신이 Doom을 부여할 때마다 amount 블록 (Unpowered)
    (원본 ShroudPower.AfterPowerAmountChanged). 발동은 Creature.apply_power."""
    power_id = "shroud"
    name = "Shroud"
    is_debuff = False


class SpiritOfAsh(STS2Power):
    """재의 정령 — Ethereal 카드를 낼 때마다 amount 블록 (Unpowered)
    (원본 SpiritOfAshPower.BeforeCardPlayed)."""
    power_id = "spirit_of_ash"
    name = "Spirit of Ash"
    is_debuff = False

    def on_card_played(self, card, combat) -> None:
        if getattr(card, "is_ethereal", False) and self.owner is not None:
            self.owner._block += self.amount  # 원본 Unpowered


class Veilpiercer(STS2Power):
    """장막 관통 — 스택 수만큼 Ethereal 카드를 0코스트로 낼 수 있음
    (원본 VeilpiercerPower). Ethereal 카드 코스트를 0으로, 낼 때마다 1 차감."""
    power_id = "veilpiercer"
    name = "Veilpiercer"
    is_debuff = False

    def modify_card_cost(self, card, cost: int) -> int:
        if self.amount > 0 and getattr(card, "is_ethereal", False):
            return 0
        return cost

    def on_card_played(self, card, combat) -> None:
        if self.amount > 0 and getattr(card, "is_ethereal", False):
            self.amount -= 1
            if self.amount <= 0:
                self.remove()


class SummonNextTurn(STS2Power):
    """다음 턴 소환 — 다음 턴 시작 시 Osty를 amount만큼 소환/강화 후 제거
    (원본 SummonNextTurnPower.AfterPlayerTurnStart)."""
    power_id = "summon_next_turn"
    name = "Summon Next Turn"
    is_debuff = False

    def on_turn_start(self) -> None:
        summon = getattr(self.owner, "summon_osty", None)
        if summon:
            summon(self.amount)
        self.remove()


class Debilitate(STS2Power):
    """쇠약 — 이 적의 취약 배수 1.5→2.0, 약화 배수 0.75→0.5 강화 (원본 DebilitatePower).
    적 턴 종료 시 1 감소. 실제 배수 강화는 Vulnerable/Weak.modify_damage에서 처리."""
    power_id = "debilitate"
    name = "Debilitate"
    is_debuff = True

    def tick_duration(self) -> None:
        self.amount -= 1
        if self.amount <= 0:
            self.remove()


class ForbiddenGrimoire(STS2Power):
    """금단의 마도서 — 전투 종료 시 카드 제거 보상 +amount (원본 ForbiddenGrimoirePower).
    보상 시스템 미모델링 — 전투 내 효과 없음(마커)."""
    power_id = "forbidden_grimoire"
    name = "Forbidden Grimoire"
    is_debuff = False


# ══════════════════════════════════════════
# Regent 카드 파워 (Phase 6f)
# ══════════════════════════════════════════

def _unpowered_hit(target, amount: int) -> None:
    """Unpowered 피해 (원본 ValueProp.Unpowered): Strength/Vulnerable 미적용,
    블록은 소모한다 (BlackHole/Reflect 등)."""
    if amount <= 0 or target is None or target.is_dead:
        return
    blocked = min(getattr(target, "_block", 0), amount)
    target._block -= blocked
    target.lose_hp(amount - blocked, from_damage=True)


class StarNextTurn(STS2Power):
    """다음 턴 별 +amount (원본 StarNextTurnPower — AfterEnergyReset 후 제거)."""
    power_id = "star_next_turn"
    name = "Star Next Turn"
    is_debuff = False

    def after_energy_reset(self) -> None:
        gain = getattr(self.owner, "gain_stars", None)
        if gain:
            gain(self.amount)
        self.remove()


class GenesisP(STS2Power):
    """창세 — 매 턴 에너지 리셋 시 별 +amount (원본 GenesisPower)."""
    power_id = "genesis"
    name = "Genesis"
    is_debuff = False

    def after_energy_reset(self) -> None:
        gain = getattr(self.owner, "gain_stars", None)
        if gain:
            gain(self.amount)


class ParryP(STS2Power):
    """받아넘기기 — 자체 효과 없음. SovereignBlade가 플레이 시
    이 파워 수치만큼 블록 획득 (원본 ParryPower 마커)."""
    power_id = "parry"
    name = "Parry"
    is_debuff = False


class SeekingEdgeP(STS2Power):
    """추적하는 칼날 — 자체 효과 없음. SovereignBlade가 전체 공격이 된다
    (원본 SeekingEdgePower 마커, StackType.Single)."""
    power_id = "seeking_edge"
    name = "Seeking Edge"
    is_debuff = False

    def apply(self, owner, applier=None) -> None:
        # 원본 StackType.Single — 중첩 없음
        self.owner = owner
        self.applier = applier
        if self.power_id not in owner._powers:
            owner._powers[self.power_id] = self


class BlackHoleP(STS2Power):
    """블랙홀 — 별을 소모한 카드 플레이 후 / 별 획득 시
    모든 적에게 amount Unpowered 피해 (원본 BlackHolePower)."""
    power_id = "black_hole"
    name = "Black Hole"
    is_debuff = False

    def _damage_all(self) -> None:
        combat = getattr(self.owner, "combat", None)
        if combat is None:
            return
        for enemy in list(combat.alive_enemies):
            _unpowered_hit(enemy, self.amount)

    def on_card_played(self, card, combat) -> None:
        # 원본 AfterCardPlayed: StarsSpent > 0인 플레이가 끝난 뒤 발동
        if combat.last_star_paid > 0:
            self._damage_all()

    def after_stars_gained(self, amount: int) -> None:
        if amount > 0:
            self._damage_all()


class ChildOfTheStarsP(STS2Power):
    """별의 아이 — 별을 소모할 때마다 (amount × 소모량) 블록
    (원본 ChildOfTheStarsPower — Unpowered 블록)."""
    power_id = "child_of_the_stars"
    name = "Child of the Stars"
    is_debuff = False

    def after_stars_spent(self, spent: int) -> None:
        if spent > 0 and self.owner is not None:
            self.owner._block += self.amount * spent  # Unpowered — 민첩 미적용


class ConquerorP(STS2Power):
    """정복자 (적 디버프) — SovereignBlade가 이 적에게 주는 피해 2배.
    적 턴 종료마다 1 감소 (원본 ConquerorPower)."""
    power_id = "conqueror"
    name = "Conqueror"
    is_debuff = True
    damage_side = "incoming"

    def modify_incoming(self, amount: int, source) -> int:
        # SovereignBlade 플레이 중에만 2배 (원본 cardSource is SovereignBlade)
        if getattr(source, "_playing_sovereign_blade", False):
            return amount * 2
        return amount

    def on_turn_end(self) -> None:
        self.amount -= 1
        if self.amount <= 0:
            self.remove()


class MonarchsGazeP(STS2Power):
    """군주의 시선 — 내 파워드 공격이 명중할 때마다 대상에게
    임시 힘 -amount (원본 MonarchsGazePower → MonarchsGazeStrengthDownPower)."""
    power_id = "monarchs_gaze"
    name = "Monarch's Gaze"
    is_debuff = False


class MonologueP(STS2Power):
    """독백 — 이후 카드를 플레이할 때마다 힘 +strength_per (자기 플레이 제외),
    턴 종료 시 파워 제거 + 부여한 힘 전부 회수 (원본 MonologuePower)."""
    power_id = "monologue"
    name = "Monologue"
    is_debuff = False

    def __init__(self, amount: int = 0, source_card=None):
        super().__init__(amount)
        self.strength_per = amount   # 카드 플레이당 힘 (원본 PowerVar<StrengthPower>)
        self.strength_applied = 0    # 이번 턴 부여 누계 (원본 StrengthApplied)
        self._source_card = source_card

    def apply(self, owner, applier=None) -> None:
        self.owner = owner
        self.applier = applier
        existing = owner._powers.get(self.power_id)
        if existing is None:
            owner._powers[self.power_id] = self
            return
        # 재플레이 병합: 기존 인스턴스는 이 Monologue 플레이 자체에도 발동
        # (원본 — 새 인스턴스만 자기 플레이를 기록하지 않음)
        existing.owner.apply_power(Strength(existing.strength_per))
        existing.strength_applied += existing.strength_per
        existing.strength_per += self.strength_per
        existing.amount = existing.strength_per
        existing._source_card = self._source_card

    def on_card_played(self, card, combat) -> None:
        if card is self._source_card:
            self._source_card = None  # 자기 자신의 플레이 1회 무시
            return
        if self.owner is not None and self.strength_per != 0:
            self.owner.apply_power(Strength(self.strength_per))
            self.strength_applied += self.strength_per

    def on_turn_end(self) -> None:
        if self.owner is not None:
            applied = self.strength_applied
            self.remove()
            if applied:
                self.owner.apply_power(Strength(-applied))


class PaleBlueDotP(STS2Power):
    """창백한 푸른 점 — 한 턴에 카드 5장 플레이 시 다음 턴 드로우 +amount
    (턴당 1회, 원본 PaleBlueDotPower — CardPlay 5)."""
    power_id = "pale_blue_dot"
    name = "Pale Blue Dot"
    is_debuff = False
    THRESHOLD = 5  # 원본 cardPlayThresholdValue

    def __init__(self, amount: int = 0):
        super().__init__(amount)
        self._activated_this_turn = False

    def on_card_played(self, card, combat) -> None:
        if self._activated_this_turn:
            return
        if combat.cards_played_this_turn >= self.THRESHOLD:
            self._activated_this_turn = True
            self.owner.apply_power(DrawCardsNextTurn(self.amount))

    def on_turn_end(self) -> None:
        self._activated_this_turn = False


class OrbitP(STS2Power):
    """궤도 — 카드로 에너지를 누적 4 소모할 때마다 에너지 +amount
    (원본 OrbitPower — 전투 누적, _energyIncrement=4)."""
    power_id = "orbit"
    name = "Orbit"
    is_debuff = False
    INCREMENT = 4

    def __init__(self, amount: int = 0):
        super().__init__(amount)
        self._energy_spent = 0
        self._trigger_count = 0

    def after_energy_spent(self, card, amount: int) -> None:
        if amount <= 0:
            return
        self._energy_spent += amount
        triggers = self._energy_spent // self.INCREMENT - self._trigger_count
        if triggers > 0:
            self.owner.gain_energy(self.amount * triggers)
            self._trigger_count += triggers


class ReflectP(STS2Power):
    """반사 — 파워드 공격을 블록으로 막으면 막은 만큼 공격자에게
    Unpowered 피해. 내 턴 시작마다 1 감소 (원본 ReflectPower)."""
    power_id = "reflect"
    name = "Reflect"
    is_debuff = False

    def on_damage_blocked(self, source, blocked: int) -> None:
        if blocked > 0 and source is not None and source is not self.owner:
            _unpowered_hit(source, blocked)

    def on_turn_start(self) -> None:
        self.amount -= 1
        if self.amount <= 0:
            self.remove()


class RetainHandP(STS2Power):
    """손패 유지 — 턴 종료 시 손패를 버리지 않는다 (Ethereal 소모는 그대로).
    턴 종료마다 1 감소 (원본 RetainHandPower — ShouldFlush=false).
    차감은 combat._discard_hand에서 처리."""
    power_id = "retain_hand"
    name = "Retain Hand"
    is_debuff = False


class ForegoneConclusionP(STS2Power):
    """예정된 결말 — 다음 턴 드로우 전에 뽑을 더미에서 amount장을 손패로
    가져온 뒤 제거 (원본 ForegoneConclusionPower). [선택→무작위]"""
    power_id = "foregone_conclusion"
    name = "Foregone Conclusion"
    is_debuff = False

    def before_hand_draw(self, combat) -> None:
        # 원본 ShuffleIfNecessary — 뽑을 더미가 비면 버림 더미 셔플
        if not combat.draw_pile and combat.discard_pile:
            combat.draw_pile = combat.discard_pile
            combat.discard_pile = []
            combat.rng.shuffle(combat.draw_pile)
        for _ in range(self.amount):
            if not combat.draw_pile or len(combat.hand) >= 10:
                break
            card = combat.rng.choice(combat.draw_pile)
            combat.draw_pile.remove(card)
            combat.hand.append(card)
        self.remove()


class SpectrumShiftP(STS2Power):
    """스펙트럼 변이 — 매 턴 드로우 전에 무작위 Colorless 카드 amount장을
    손패에 생성 (원본 SpectrumShiftPower).
    Colorless 풀 미이식 — 전투 내 효과 없음(마커, 문서화)."""
    power_id = "spectrum_shift"
    name = "Spectrum Shift"
    is_debuff = False


class TyrannyP(STS2Power):
    """폭정 — 드로우 +amount, 턴 시작(드로우 후) 손패에서 amount장 소모
    (원본 TyrannyPower — ModifyHandDraw + AfterPlayerTurnStart). [선택→무작위]"""
    power_id = "tyranny"
    name = "Tyranny"
    is_debuff = False

    def modify_hand_draw(self, count: int) -> int:
        return count + self.amount

    def after_hand_draw(self, combat) -> None:
        combat.exhaust_from_hand(self.amount)


class SealedThroneP(STS2Power):
    """봉인된 왕좌 — 카드를 플레이할 때마다(효과 처리 전) 별 +amount
    (원본 TheSealedThronePower — BeforeCardPlayed. 자기 플레이는 파워 적용
    전에 시작되어 미발동)."""
    power_id = "sealed_throne"
    name = "The Sealed Throne"
    is_debuff = False

    def before_card_played(self, card, combat) -> None:
        gain = getattr(self.owner, "gain_stars", None)
        if gain:
            gain(self.amount)


class ArsenalP(STS2Power):
    """무기고 — 전투 중 카드가 생성될 때마다 힘 +amount
    (원본 ArsenalPower — AfterCardGeneratedForCombat)."""
    power_id = "arsenal"
    name = "Arsenal"
    is_debuff = False

    def on_card_generated(self, card, combat) -> None:
        if self.owner is not None:
            self.owner.apply_power(Strength(self.amount))


class PillarOfCreationP(STS2Power):
    """창조의 기둥 — 전투 중 카드가 생성될 때마다 블록 +amount
    (원본 PillarOfCreationPower — Unpowered 블록)."""
    power_id = "pillar_of_creation"
    name = "Pillar of Creation"
    is_debuff = False

    def on_card_generated(self, card, combat) -> None:
        if self.owner is not None:
            self.owner._block += self.amount  # Unpowered — 민첩 미적용


class RoyaltiesP(STS2Power):
    """인세 — 전투 종료 시 골드 +amount 추가 보상
    (원본 RoyaltiesPower — AfterCombatEnd GoldReward)."""
    power_id = "royalties"
    name = "Royalties"
    is_debuff = False

    def on_combat_end(self, victory: bool) -> None:
        if victory and self.owner is not None:
            character = getattr(self.owner, "character", None)
            if character is not None:
                character.gain_gold(self.amount)


class SwordSageP(STS2Power):
    """검성 — 모든 SovereignBlade에 Replay +amount (플레이 시 추가 발동).
    이후 생성되는 SovereignBlade에도 적용 (원본 SwordSagePower)."""
    power_id = "sword_sage"
    name = "Sword Sage"
    is_debuff = False

    def _blades(self):
        from sts2_sim.cards.regent import SovereignBlade
        combat = getattr(self.owner, "combat", None)
        if combat is None:
            return []
        piles = combat.hand + combat.draw_pile + combat.discard_pile + combat.exhaust_pile
        return [c for c in piles if isinstance(c, SovereignBlade)]

    def apply(self, owner, applier=None) -> None:
        self.owner = owner
        delta = self.amount
        super().apply(owner, applier)
        # 기존 블레이드 전부에 Replay +delta (원본 AfterPowerAmountChanged)
        for blade in owner._powers[self.power_id]._blades():
            blade._extra_plays += delta

    def on_card_generated(self, card, combat) -> None:
        from sts2_sim.cards.regent import SovereignBlade
        if isinstance(card, SovereignBlade):
            card._extra_plays += self.amount

    def remove(self) -> None:
        # 원본 AfterRemoved — 블레이드의 Replay 회수
        for blade in self._blades():
            blade._extra_plays = max(0, blade._extra_plays - self.amount)
        super().remove()


class VoidFormP(STS2Power):
    """공허의 형상 — 매 턴 처음 amount장의 카드는 에너지/별 비용 0
    (원본 VoidFormPower — 자동 플레이 제외)."""
    power_id = "void_form"
    name = "Void Form"
    is_debuff = False

    def __init__(self, amount: int = 0):
        super().__init__(amount)
        self._plays_this_turn = 0

    def _active(self, combat) -> bool:
        return self._plays_this_turn < self.amount and not getattr(
            combat, "_auto_playing", False)

    def modify_card_cost(self, card, cost: int) -> int:
        combat = getattr(self.owner, "combat", None)
        if combat is not None and self._active(combat):
            return 0
        return cost

    def modify_card_star_cost(self, card, star_cost: int) -> int:
        combat = getattr(self.owner, "combat", None)
        if combat is not None and self._active(combat):
            return 0
        return star_cost

    def on_card_played(self, card, combat) -> None:
        if not getattr(combat, "_auto_playing", False):
            self._plays_this_turn += 1

    def on_turn_start(self) -> None:
        self._plays_this_turn = 0


class FurnaceP(STS2Power):
    """용광로 — 내 턴 시작마다 Forge amount (원본 FurnacePower)."""
    power_id = "furnace"
    name = "Furnace"
    is_debuff = False

    def on_turn_start(self) -> None:
        combat = getattr(self.owner, "combat", None)
        if combat is not None:
            from sts2_sim.cards.regent import _forge
            _forge(self.owner, combat, self.amount)


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
    # Silent (Phase 6c)
    "accelerant": Accelerant,
    "accuracy": Accuracy,
    "afterimage": Afterimage,
    "temp_dexterity": TempDexterity,
    "blur": Blur,
    "burst": Burst,
    "corrosive_wave": CorrosiveWave,
    "envenom": Envenom,
    "fan_of_knives": FanOfKnives,
    "infinite_blades": InfiniteBlades,
    "master_planner": MasterPlanner,
    "nightmare": Nightmare,
    "noxious_fumes": NoxiousFumes,
    "outbreak": Outbreak,
    "phantom_blades": PhantomBlades,
    "serpent_form": SerpentForm,
    "double_damage": DoubleDamage,
    "shadow_step": ShadowStep,
    "shadowmeld": Shadowmeld,
    "speedster": Speedster,
    "strangle": Strangle,
    "the_hunt": TheHunt,
    "tools_of_the_trade": ToolsOfTheTrade,
    "tracking": Tracking,
    "well_laid_plans": WellLaidPlans,
    "wraith_form": WraithFormPower,
    "intangible": Intangible,
    "block_next_turn": BlockNextTurn,
    "draw_next_turn": DrawCardsNextTurn,
    "free_skill": FreeSkill,
    # Defect (Phase 6d)
    "temp_focus": TempFocus,
    "biased_cognition": BiasedCognition,
    "buffer": Buffer,
    "energy_next_turn": EnergyNextTurn,
    "coolant": Coolant,
    "consuming_shadow": ConsumingShadow,
    "creative_ai": CreativeAI,
    "echo_form": EchoForm,
    "feral": Feral,
    "hailstorm": Hailstorm,
    "iteration": Iteration,
    "lightning_rod": LightningRod,
    "loop": Loop,
    "machine_learning": MachineLearning,
    "signal_boost": SignalBoost,
    "smokestack": Smokestack,
    "spinner": Spinner,
    "storm": Storm,
    "subroutine": Subroutine,
    "thunder": Thunder,
    "trash_to_treasure": TrashToTreasure,
    "free_power": FreePower,
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
    "doom": Doom,
    # Necrobinder (Phase 6e)
    "calcify": Calcify,
    "call_of_the_void": CallOfTheVoid,
    "countdown": Countdown,
    "danse_macabre": DanseMacabre,
    "borrowed_time": BorrowedTime,
    "demesne": Demesne,
    "devour_life": DevourLife,
    "enfeebling_touch": EnfeeblingTouch,
    "friendship": Friendship,
    "hang": Hang,
    "haunt": Haunt,
    "lethality": Lethality,
    "necro_mastery": NecroMastery,
    "neurosurge": Neurosurge,
    "oblivion": Oblivion,
    "pagestorm": Pagestorm,
    "reaper_form": ReaperForm,
    "sentry_mode": SentryMode,
    "sic_em": SicEm,
    "sleight_of_flesh": SleightOfFlesh,
    "shroud": Shroud,
    "spirit_of_ash": SpiritOfAsh,
    "veilpiercer": Veilpiercer,
    "summon_next_turn": SummonNextTurn,
    "debilitate": Debilitate,
    "forbidden_grimoire": ForbiddenGrimoire,
    # Regent (Phase 6f)
    "star_next_turn": StarNextTurn,
    "genesis": GenesisP,
    "parry": ParryP,
    "seeking_edge": SeekingEdgeP,
    "black_hole": BlackHoleP,
    "child_of_the_stars": ChildOfTheStarsP,
    "conqueror": ConquerorP,
    "monarchs_gaze": MonarchsGazeP,
    "monologue": MonologueP,
    "pale_blue_dot": PaleBlueDotP,
    "orbit": OrbitP,
    "reflect": ReflectP,
    "retain_hand": RetainHandP,
    "foregone_conclusion": ForegoneConclusionP,
    "spectrum_shift": SpectrumShiftP,
    "tyranny": TyrannyP,
    "sealed_throne": SealedThroneP,
    "arsenal": ArsenalP,
    "pillar_of_creation": PillarOfCreationP,
    "royalties": RoyaltiesP,
    "sword_sage": SwordSageP,
    "void_form": VoidFormP,
    "furnace": FurnaceP,
}


def create_power(power_id: str, amount: int = 0) -> Optional[STS2Power]:
    """파워 생성."""
    power_class = POWER_REGISTRY.get(power_id)
    if power_class:
        return power_class(amount)
    return None
