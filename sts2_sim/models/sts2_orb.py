"""
STS2 Orb System — Defect 오브 시스템.
디컴파일 MegaCrit.Sts2.Core.Models.OrbModel + Models.Orbs.* 이식.

5종 오브 (디컴파일 수치):
  Lightning: 패시브 3딜(무작위 적, 턴 종료) / 이보크 8딜
  Frost:     패시브 2블록(턴 종료)          / 이보크 5블록
  Dark:      패시브마다 이보크값 +6 누적     / 이보크 시 최저 HP 적 타격
  Plasma:    패시브 에너지 +1(턴 시작)      / 이보크 +2  (Focus 미적용)
  Glass:     전체 적 4딜, 트리거마다 -1     / 이보크 = 패시브 ×2 (전체)
"""
from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from sts2_sim.entities.creature import Creature


class STS2Orb:
    """오브 베이스 클래스 (OrbModel 대응)."""
    orb_id: str = "unknown_orb"
    name: str = "Unknown Orb"
    # 패시브 트리거 시점: "turn_end" (BeforeTurnEndOrbTrigger) / "turn_start" (AfterTurnStartOrbTrigger)
    passive_timing: str = "turn_end"
    # Focus(집중) 적용 여부 — Plasma는 미적용 (디컴파일 확인)
    affected_by_focus: bool = True

    base_passive: int = 0
    base_evoke: int = 0

    def __init__(self):
        self.owner = None  # Player-like (gain_block/gain_energy/get_power_amount)

    def _focus(self) -> int:
        if not self.affected_by_focus or self.owner is None:
            return 0
        getter = getattr(self.owner, "get_power_amount", None)
        return getter("focus") if getter else 0

    @property
    def passive_val(self) -> int:
        """패시브 값 (Focus 반영)."""
        return max(0, self.base_passive + self._focus())

    @property
    def evoke_val(self) -> int:
        """이보크 값 (Focus 반영)."""
        return max(0, self.base_evoke + self._focus())

    def passive(self, combat) -> None:
        """패시브 발동 (서브클래스 구현)."""
        pass

    def evoke(self, combat) -> None:
        """이보크 발동 (서브클래스 구현)."""
        pass

    def __repr__(self) -> str:
        return self.name


class LightningOrb(STS2Orb):
    """번개 — 무작위 적 공격."""
    orb_id = "lightning"
    name = "Lightning"
    base_passive = 3
    base_evoke = 8

    def _hit_random(self, combat, amount: int) -> None:
        enemies = [e for e in combat.alive_enemies if not e.is_dead]
        if not enemies:
            return
        target = combat.rng.choice(enemies)
        target.take_damage(amount, source=self.owner)

    def passive(self, combat) -> None:
        self._hit_random(combat, self.passive_val)

    def evoke(self, combat) -> None:
        self._hit_random(combat, self.evoke_val)


class FrostOrb(STS2Orb):
    """서리 — 블록 획득."""
    orb_id = "frost"
    name = "Frost"
    base_passive = 2
    base_evoke = 5

    def passive(self, combat) -> None:
        if self.owner:
            self.owner.gain_block(self.passive_val)

    def evoke(self, combat) -> None:
        if self.owner:
            self.owner.gain_block(self.evoke_val)


class DarkOrb(STS2Orb):
    """어둠 — 이보크값 누적, 최저 HP 적 타격."""
    orb_id = "dark"
    name = "Dark"
    base_passive = 6
    base_evoke = 6  # 초기 이보크값 (누적 시작점)

    def __init__(self):
        super().__init__()
        self._accumulated_evoke = self.base_evoke

    @property
    def evoke_val(self) -> int:
        """누적된 이보크값 (Focus는 패시브 증가분에만 반영됨)."""
        return self._accumulated_evoke

    def passive(self, combat) -> None:
        self._accumulated_evoke += self.passive_val

    def evoke(self, combat) -> None:
        enemies = [e for e in combat.alive_enemies if not e.is_dead]
        if not enemies:
            return
        weakest = min(enemies, key=lambda e: e.current_hp)
        weakest.take_damage(self._accumulated_evoke, source=self.owner)


class PlasmaOrb(STS2Orb):
    """플라즈마 — 에너지 획득 (턴 시작, Focus 미적용)."""
    orb_id = "plasma"
    name = "Plasma"
    passive_timing = "turn_start"
    affected_by_focus = False
    base_passive = 1
    base_evoke = 2

    def passive(self, combat) -> None:
        if self.owner:
            self.owner.gain_energy(self.passive_val)

    def evoke(self, combat) -> None:
        if self.owner:
            self.owner.gain_energy(self.evoke_val)


class GlassOrb(STS2Orb):
    """유리 (STS2 신규) — 전체 적 타격, 트리거마다 감쇠."""
    orb_id = "glass"
    name = "Glass"
    base_passive = 4

    def __init__(self):
        super().__init__()
        self._current_passive = self.base_passive

    @property
    def passive_val(self) -> int:
        return max(0, self._current_passive + self._focus())

    @property
    def evoke_val(self) -> int:
        return self.passive_val * 2

    def passive(self, combat) -> None:
        amount = self.passive_val
        if amount <= 0:
            return
        self._current_passive = max(0, self._current_passive - 1)
        for enemy in [e for e in combat.alive_enemies if not e.is_dead]:
            enemy.take_damage(amount, source=self.owner)

    def evoke(self, combat) -> None:
        amount = self.evoke_val
        if amount <= 0:
            return
        for enemy in [e for e in combat.alive_enemies if not e.is_dead]:
            enemy.take_damage(amount, source=self.owner)


class OrbQueue:
    """오브 슬롯 큐. 채널 시 슬롯이 가득 차면 선두 오브를 자동 이보크."""

    def __init__(self, slot_count: int = 3):
        self.slot_count = slot_count
        self.orbs: List[STS2Orb] = []

    def channel(self, orb: STS2Orb, owner, combat) -> None:
        """오브 채널. 슬롯 초과 시 선두 오브 이보크 후 제거."""
        orb.owner = owner
        if len(self.orbs) >= self.slot_count:
            self.evoke_next(combat)
        self.orbs.append(orb)

    def evoke_next(self, combat, dequeue: bool = True) -> Optional[STS2Orb]:
        """선두 오브 이보크. dequeue=False면 큐에 유지 (Dualcast용)."""
        if not self.orbs:
            return None
        front = self.orbs[0]
        front.evoke(combat)
        if dequeue:
            self.orbs.pop(0)
        return front

    def gain_slots(self, count: int) -> None:
        self.slot_count += count

    def trigger_turn_end(self, combat) -> None:
        """턴 종료 패시브 (Lightning/Frost/Dark/Glass)."""
        for orb in list(self.orbs):
            if orb.passive_timing == "turn_end":
                orb.passive(combat)

    def trigger_turn_start(self, combat) -> None:
        """턴 시작 패시브 (Plasma)."""
        for orb in list(self.orbs):
            if orb.passive_timing == "turn_start":
                orb.passive(combat)

    def __len__(self) -> int:
        return len(self.orbs)

    def __repr__(self) -> str:
        slots = ", ".join(o.name for o in self.orbs)
        return f"OrbQueue[{slots}] ({len(self.orbs)}/{self.slot_count})"


ORB_REGISTRY = {
    "lightning": LightningOrb,
    "frost": FrostOrb,
    "dark": DarkOrb,
    "plasma": PlasmaOrb,
    "glass": GlassOrb,
}


def create_orb(orb_id: str) -> Optional[STS2Orb]:
    """오브 생성."""
    orb_class = ORB_REGISTRY.get(orb_id)
    return orb_class() if orb_class else None
