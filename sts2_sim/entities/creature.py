"""
STS2 Creature — 플레이어/소환수(Osty)가 공유하는 생명체 베이스.
HP, 블록, 파워 컨테이너 및 데미지 파이프라인 제공.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from sts2_sim.models.sts2_power import STS2Power


class Creature:
    """HP/블록/파워를 가진 생명체."""

    def __init__(self, name: str, max_hp: int):
        self.name = name
        self._max_hp = max_hp
        self._current_hp = max_hp
        self._block = 0
        self._powers: Dict[str, Any] = {}
        self.hp_lost_this_turn = 0   # Spite 등 "이번 턴 HP 손실" 조건용
        self.times_hp_lost = 0       # TearAsunder — 전투 중 HP 손실 횟수

    @property
    def current_hp(self) -> int:
        return self._current_hp

    @property
    def max_hp(self) -> int:
        return self._max_hp

    @property
    def block(self) -> int:
        return self._block

    @property
    def is_dead(self) -> bool:
        return self._current_hp <= 0

    @property
    def is_alive(self) -> bool:
        return not self.is_dead

    # ──────────────────────────────────────────
    # 파워
    # ──────────────────────────────────────────

    def apply_power(self, power: "STS2Power", applier: Optional["Creature"] = None) -> bool:
        """파워 적용 (동일 ID면 스택). 디버프는 Artifact가 1회 무효화."""
        if power.is_debuff and self.get_power_amount("artifact") > 0:
            artifact = self._powers["artifact"]
            artifact.amount -= 1
            if artifact.amount <= 0:
                artifact.remove()
            return False
        power.apply(self, applier)
        # Vicious — 시전자가 적에게 취약을 걸 때마다 드로우
        if (applier is not None and applier is not self
                and power.power_id == "vulnerable"):
            vicious = applier.get_power_amount("vicious")
            combat = getattr(applier, "combat", None)
            if vicious > 0 and combat is not None:
                combat.draw_cards(vicious)
        # Outbreak — 시전자가 적에게 중독을 걸 때마다 모든 적에게 피해
        if (applier is not None and applier is not self
                and power.power_id == "poison"):
            outbreak = applier.get_power_amount("outbreak")
            combat = getattr(applier, "combat", None)
            if outbreak > 0 and combat is not None:
                for enemy in list(combat.alive_enemies):
                    enemy.take_damage(outbreak, source=applier)
        # Shroud — 시전자가 Doom을 부여할 때마다 블록 획득 (원본 ShroudPower)
        if (applier is not None and applier is not self
                and power.power_id == "doom"):
            combat = getattr(applier, "combat", None)
            if combat is not None:
                combat.doom_applied_this_turn = True  # DeathsDoor
            shroud = applier.get_power_amount("shroud")
            if shroud > 0:
                applier._block += shroud  # 원본 Unpowered — 민첩 미적용
        # SleightOfFlesh — 시전자가 적에게 디버프를 부여할 때마다 그 적에게 피해
        if (applier is not None and applier is not self and power.is_debuff):
            sof = applier.get_power_amount("sleight_of_flesh")
            if sof > 0 and not self.is_dead:
                self.lose_hp(sof)  # 원본 Unpowered — 무보정 피해
        return True

    def has_power(self, power_id: str) -> bool:
        return power_id in self._powers and self._powers[power_id].amount != 0

    def get_power_amount(self, power_id: str) -> int:
        p = self._powers.get(power_id)
        return p.amount if p else 0

    def remove_power(self, power_id: str) -> None:
        self._powers.pop(power_id, None)

    def tick_powers(self) -> None:
        """턴 종료 시 파워 지속시간/도트 처리."""
        for p in list(self._powers.values()):
            p.tick_duration()

    # ──────────────────────────────────────────
    # 데미지 파이프라인
    # ──────────────────────────────────────────

    def compute_attack_damage(self, base: int) -> int:
        """공격자 측 데미지 수정 (Strength → Weak 순)."""
        amount = base
        for p in list(self._powers.values()):
            if getattr(p, "damage_side", None) == "outgoing":
                amount = p.modify_damage(amount, is_attack=True)
        return max(0, amount)

    def take_damage(self, amount: int, source: Optional[object] = None) -> Dict[str, Any]:
        """피격 처리: 수신 측 수정(Vulnerable/Colossus/Cruelty) → 블록 → HP → 피격 트리거."""
        # Osty DieForYou — 살아있는 Osty가 플레이어를 겨냥한 공격을 대신 받는다
        # (원본 DieForYouPower.ModifyUnblockedDamageTarget — 파워드 공격 한정).
        osty = getattr(self, "osty", None)
        if (osty is not None and osty is not self and osty.is_alive
                and source is not None and source is not self):
            return osty.take_damage(amount, source)
        pre_incoming = amount
        for p in list(self._powers.values()):
            if getattr(p, "damage_side", None) == "incoming":
                modify_src = getattr(p, "modify_incoming", None)
                if modify_src:
                    amount = modify_src(amount, source)
                else:
                    amount = p.modify_damage(amount, is_attack=True)

        # Cruelty — 공격자의 Cruelty가 취약 배율을 amount/100만큼 증폭 (1.5x → 1.75x 등)
        if (source is not None and hasattr(source, "get_power_amount")
                and self.get_power_amount("vulnerable") > 0):
            cruelty = source.get_power_amount("cruelty")
            if cruelty > 0:
                amount += int(pre_incoming * cruelty / 100)

        if amount <= 0:
            return {"hp_lost": 0, "damage": 0, "killed": False}

        block_absorbed = min(self._block, amount)
        self._block -= block_absorbed
        hp_lost = self.lose_hp(amount - block_absorbed, from_damage=True)

        # Reflect — 블록으로 막은 파워드 공격 피해를 공격자에게 반사
        if block_absorbed > 0 and source is not None:
            for p in list(self._powers.values()):
                on_blocked = getattr(p, "on_damage_blocked", None)
                if on_blocked:
                    on_blocked(source, block_absorbed)

        if hp_lost > 0:
            for p in list(self._powers.values()):
                on_hit = getattr(p, "on_take_damage", None)
                if on_hit:
                    on_hit(source, hp_lost)

        # damage = 파워 수정 후 총 피해량(블록 흡수 포함) — BlightStrike/ReaperForm 등이 참조
        return {"hp_lost": hp_lost, "damage": amount, "killed": self.is_dead}

    def compute_modified_block(self, amount: int) -> int:
        """파워(Dexterity/Frail 등)의 modify_block만 적용한 값 반환 (실제 블록은 미변경).
        Glitterstream처럼 시전 시점에 수정된 값을 나중에 지급해야 하는 카드용."""
        for p in list(self._powers.values()):
            amount = p.modify_block(amount)
        return max(0, amount)

    def gain_block(self, amount: int) -> None:
        """블록 획득 (Dexterity/Frail 수정 적용, on_block_gained 트리거)."""
        gained = self.compute_modified_block(amount)
        self._block += gained
        if gained > 0:
            for p in list(self._powers.values()):
                hook = getattr(p, "on_block_gained", None)
                if hook:
                    hook(gained)

    def lose_hp(self, amount: int, from_damage: bool = False) -> int:
        """HP 감소. from_damage=False(카드/자해)일 때만 on_hp_lost 트리거 (Rupture)."""
        # Buffer 등 HP 손실 수정 파이프라인 (원본 ModifyHpLostAfterOstyLate)
        for p in list(self._powers.values()):
            modify = getattr(p, "modify_hp_lost", None)
            if modify:
                amount = modify(amount)
        actual = min(max(0, amount), self._current_hp)
        self._current_hp -= actual
        if actual > 0:
            self.hp_lost_this_turn += actual
            self.times_hp_lost += 1
        if actual > 0 and not from_damage:
            for p in list(self._powers.values()):
                hook = getattr(p, "on_hp_lost", None)
                if hook:
                    hook(actual)
        return actual

    def heal(self, amount: int) -> None:
        self._current_hp = min(self._current_hp + amount, self._max_hp)

    def gain_max_hp(self, amount: int) -> None:
        self._max_hp += amount
        self._current_hp = min(self._current_hp + max(0, amount), self._max_hp)

    def start_of_turn(self) -> None:
        """턴 시작: 블록 초기화 (Barricade/Blur 보유 시 유지), 턴별 카운터 리셋."""
        if not self.has_power("barricade") and not self.has_power("blur"):
            self._block = 0
        self.hp_lost_this_turn = 0

    def __repr__(self) -> str:
        return f"{self.name}(HP:{self._current_hp}/{self._max_hp}, Block:{self._block})"


class Osty(Creature):
    """Necrobinder의 소환수 Osty."""

    def __init__(self, hp: int, owner: Optional["Creature"] = None):
        super().__init__("Osty", hp)
        self.owner = owner  # 소환한 플레이어 (NecroMastery 반사용)

    def gain_summon_hp(self, amount: int) -> None:
        """소환 스택: 살아있으면 최대/현재 HP 증가."""
        self._max_hp += amount
        self._current_hp += amount

    def _reflect_necro_mastery(self, hp_lost: int) -> None:
        """NecroMastery — Osty가 HP를 잃으면 (잃은 HP × amount)를 모든 적에게 관통 피해."""
        if self.owner is None or hp_lost <= 0:
            return
        nm = self.owner.get_power_amount("necro_mastery")
        if nm <= 0:
            return
        combat = getattr(self.owner, "combat", None)
        if combat is None:
            return
        for enemy in list(combat.alive_enemies):
            enemy.lose_hp(hp_lost * nm)  # 원본 Unblockable|Unpowered

    def lose_hp(self, amount: int, from_damage: bool = False) -> int:
        actual = super().lose_hp(amount, from_damage)
        self._reflect_necro_mastery(actual)
        return actual

    def kill(self) -> None:
        """즉시 처치 (BoneShards/Sacrifice). HP 감소분만큼 NecroMastery 반사."""
        lost = self._current_hp
        self._current_hp = 0
        self._reflect_necro_mastery(lost)
