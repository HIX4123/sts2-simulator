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
            owner._powers[self.power_id].amount += self.amount

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
# 파워 팩토리
# ══════════════════════════════════════════

POWER_REGISTRY = {
    "strength": Strength,
    "focus": Focus,
    "artifact": Artifact,
    "plating": Plating,
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
