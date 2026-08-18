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
                    enemy.take_damage(outbreak, source=applier, powered=False)
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
        # (원본 ValueProp.Unpowered — Unblockable은 아니므로 블록으로 막힘, take_damage 경유 필수)
        if (applier is not None and applier is not self and power.is_debuff):
            sof = applier.get_power_amount("sleight_of_flesh")
            if sof > 0 and not self.is_dead:
                self.take_damage(sof, source=applier, powered=False)
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
        """공격자 측 데미지 수정 — 원본 Hook.ModifyDamageInternal과 동일하게 Additive
        단계(Strength/Vigor/TempStrength)를 전부 적용한 뒤 Multiplicative 단계
        (Weak/Shrink/DoubleDamage)를 적용한다. 파워 딕셔너리 삽입 순서와 무관하게
        고정된 순서를 보장해야 하므로(Additive→Multiplicative가 뒤바뀌면 배율이
        힘 증가분에도 걸리거나 걸리지 않는 차이가 생김) 단일 루프로 섞어 처리하지
        않고 두 단계로 분리한다."""
        amount = base
        outgoing = [p for p in self._powers.values() if getattr(p, "damage_side", None) == "outgoing"]
        additive = [p for p in outgoing if getattr(p, "damage_stage", None) == "additive"]
        multiplicative = [p for p in outgoing if getattr(p, "damage_stage", None) != "additive"]
        for p in additive:
            amount = p.modify_damage(amount, is_attack=True)
        for p in multiplicative:
            amount = p.modify_damage(amount, is_attack=True)
        return max(0, amount)

    def take_damage(self, amount: int, source: Optional[object] = None,
                     powered: bool = True, unblockable: bool = False) -> Dict[str, Any]:
        """피격 처리: 수신 측 수정(Vulnerable/Colossus 등 배율 → Intangible 등 상한)
        → 블록 → HP → 피격 트리거.
        powered=False — 원본 ValueProp.Unpowered(오브/파워 반응형 피해 전부 해당,
        Thorns/FlameBarrier 반격 포함): TheGambitPower의 IsPoweredAttack() 트리거
        조건에서 제외된다. 실제 공격 카드(_deal_attack)/몬스터 공격은 기본값(True).
        unblockable=True — 원본 ValueProp.Unblockable(Beckon 등): Multiplicative/Cap
        단계는 powered 여부와 무관하게 그대로 적용되지만 블록 흡수만 건너뛴다."""
        # Osty DieForYou — 살아있는 Osty가 플레이어를 겨냥한 공격을 대신 받는다
        # (원본 DieForYouPower.ModifyUnblockedDamageTarget — 파워드 공격 한정).
        osty = getattr(self, "osty", None)
        if (osty is not None and osty is not self and osty.is_alive
                and source is not None and source is not self):
            return osty.take_damage(amount, source, powered)
        # 원본 Hook.ModifyDamageInternal은 Multiplicative(Vulnerable/Colossus 등,
        # 순서 무관 — 곱셈은 교환법칙 성립) → Cap(Intangible 등, 항상 최종 단계) 순서를
        # 엄격히 분리한다. 두 파워 종류를 한 루프에서 순서대로 섞어 처리하면 Intangible이
        # Vulnerable보다 먼저 적용(파워 딕셔너리 순서)됐을 때 상한이 배율보다 먼저
        # 걸려버리는 오류가 생기므로 Multiplicative 파워를 전부 적용한 뒤 Cap을 마지막에
        # 적용한다.
        cap: Optional[int] = None
        for p in list(self._powers.values()):
            if getattr(p, "damage_side", None) != "incoming":
                continue
            modify_cap = getattr(p, "modify_damage_cap", None)
            if modify_cap is not None:
                c = modify_cap(amount, source, powered)
                if c is not None and (cap is None or c < cap):
                    cap = c
                continue
            modify_src = getattr(p, "modify_incoming", None)
            if modify_src:
                amount = modify_src(amount, source, powered)
            else:
                amount = p.modify_damage(amount, is_attack=True)
        if cap is not None:
            amount = min(amount, cap)

        if amount <= 0:
            return {"hp_lost": 0, "damage": 0, "killed": False}

        if unblockable:
            block_absorbed = 0
        else:
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
                on_hit_powered = getattr(p, "on_take_damage_powered", None)
                if on_hit_powered is not None:
                    on_hit_powered(source, hp_lost, powered)
                else:
                    on_hit = getattr(p, "on_take_damage", None)
                    if on_hit:
                        on_hit(source, hp_lost)

        # damage = 파워 수정 후 총 피해량(블록 흡수 포함) — BlightStrike/ReaperForm 등이 참조
        return {"hp_lost": hp_lost, "damage": amount, "killed": self.is_dead}

    def compute_modified_block(self, amount: int, card_sourced: bool = False,
                                powered: bool = True) -> int:
        """파워(Dexterity/Frail 등)의 modify_block만 적용한 값 반환 (실제 블록은 미변경).
        Glitterstream처럼 시전 시점에 수정된 값을 나중에 지급해야 하는 카드용.
        card_sourced — 원본 cardSource != null 대응(NoBlockPower 전용).
        powered — 원본 IsPoweredCardOrMonsterMoveBlock()(Move && !Unpowered) 대응
        (DexterityPower/FrailPower 전용) — 카드 플레이/몬스터 무브의 블록만 True,
        파워·오브·렐릭이 직접 부여하는 반응형 블록은 False. 두 축은 서로 다른 파워가
        각자 필요한 훅(modify_block_card_sourced 또는 modify_block_powered)만
        선택적으로 구현하며, 둘 다 없으면 modify_block(amount)로 대체된다."""
        for p in list(self._powers.values()):
            modify_cs = getattr(p, "modify_block_card_sourced", None)
            modify_pw = getattr(p, "modify_block_powered", None)
            if modify_cs is not None:
                amount = modify_cs(amount, card_sourced)
            elif modify_pw is not None:
                amount = modify_pw(amount, powered)
            else:
                amount = p.modify_block(amount)
        return max(0, amount)

    def gain_block(self, amount: int, powered: bool = True) -> None:
        """블록 획득 (Dexterity/Frail 수정 적용, on_block_gained 트리거는 원본
        AfterBlockGained처럼 powered 여부와 무관하게 항상 발동 — Juggernaut 등).
        card_sourced 여부는 combat._card_effect_active(카드 자신의 use() 실행 구간에서만
        True)로 판정 — 카드가 직접 부여하는 블록과 파워/오브/렐릭/몬스터 자체 반응으로
        얻는 블록을 구분한다 (원본 CreatureCmd.GainBlock의 cardPlay 인자 대응).
        powered=False — 파워/오브/렐릭이 직접 부여하는 반응형 블록(Plating/FrostOrb/
        Afterimage/Rage/FeelNoPain/CurlUp 등, 원본 ValueProp.Unpowered)이 호출 시
        명시; 카드 플레이·몬스터 무브는 기본값(True)."""
        combat = getattr(self, "combat", None)
        card_sourced = bool(getattr(combat, "_card_effect_active", False))
        gained = self.compute_modified_block(amount, card_sourced=card_sourced, powered=powered)
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

    def lose_max_hp(self, amount: int) -> None:
        """최대 HP 감소 (원본 CreatureCmd.LoseMaxHp — PaperCutsPower 등).
        새 최대 HP가 현재 HP보다 낮으면 그 초과분을 먼저 Unblockable|Unpowered
        피해로 처리한다 — 현재 HP를 그냥 깎으면 hp_lost_this_turn/times_hp_lost
        집계와 on_hp_lost 트리거가 누락되고, 최대 HP 전량 손실 시 사망 대신
        1로 살아남는 차이가 생긴다.
        이어서 최대 HP를 최소 1로 낮추고 현재 HP를 그 이하로 클램프한다
        (원본 SetMaxHpInternal의 CurrentHp = Min(CurrentHp, MaxHp) — 위 피해가
        Intangible 등 Cap 파이프라인에 막혀 현재 HP가 새 최대치보다 높게 남는
        경우를 정리한다).
        원본의 isFromCard 인자는 피해 props에 Move를 더할 뿐이고 Unpowered가
        그대로 유지되어 IsPoweredAttack이 어느 쪽이든 false이므로 이식하지 않는다."""
        new_max_hp = self._max_hp - amount
        if new_max_hp < self._current_hp:
            self.take_damage(self._current_hp - new_max_hp, source=None,
                             powered=False, unblockable=True)
        self._max_hp = max(1, new_max_hp)
        self._current_hp = min(self._current_hp, self._max_hp)

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
