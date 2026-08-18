"""
STS2 몬스터 배치 9 (Phase 6l) — 디컴파일 Models.Monsters.* 이식 (5종).
Act1(Underdocks) 미이식분 완결: CorpseSlug / SkulkingColony(엘리트) /
TerrorEel(엘리트) / PhantasmalGardener(엘리트) / LagavulinMatriarch(보스).
모든 수치는 Ascension 미적용 기본값 (AscensionHelper.GetValueIfAscension(..., tough, normal)의
normal/마지막 인자를 사용).

GremlinMerc/LivingFog(+GasBomb)/TwoTailedRat(전투 중 소환·슬롯 소비 구조 필요)와
WaterfallGiant(SteamEruptionPower의 사망 인터셉트/부활 구조 필요)는 각각 별도
엔진 서브시스템이 필요해 Phase 6m/6n으로 분리한다.
"""
from __future__ import annotations
from typing import List

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    MonsterModel, MonsterMoveStateMachine, MoveState, ConditionalBranchState,
    Intent, IntentType, MONSTER_REGISTRY,
)


class CorpseSlug(MonsterModel):
    """콥스 슬러그 — HP 25~27. 개전 시 스스로에게 RavenousPower(4) 부여
    (같은 편 슬러그가 죽으면 1턴 스턴 후 힘+4).

    원본(CorpseSlug.cs) 그래프: WHIP_SLAP_MOVE(3딜×2회) → GLOMP_MOVE(8딜) →
    GOOP_MOVE(대상 허약+2, 무공격) → WHIP_SLAP_MOVE → ... (고정 3순환, RNG
    분기 없음). 인카운터의 EnsureCorpseSlugsStartWithDifferentMoves가
    같은 전투 내 슬러그마다 시작 위치(starter_move_idx)를 다르게 배정한다."""
    monster_id = "corpse_slug"
    title = "Corpse Slug"

    def __init__(self, starter_move_idx: int = 0):
        super().__init__()
        self.starter_move_idx = starter_move_idx

    @property
    def min_initial_hp(self) -> int:
        return 25

    @property
    def max_initial_hp(self) -> int:
        return 27

    @property
    def whip_slap_damage(self) -> int:
        return 3

    @property
    def glomp_damage(self) -> int:
        return 8

    @property
    def goop_frail(self) -> int:
        return 2

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import RavenousPower
        self.apply_power(RavenousPower(4))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        whip = MoveState("WHIP_SLAP_MOVE", self._whip_slap_move,
                         Intent(IntentType.ATTACK, damage=self.whip_slap_damage, times=2))
        glomp = MoveState("GLOMP_MOVE", self._glomp_move,
                          Intent(IntentType.ATTACK, damage=self.glomp_damage))
        goop = MoveState("GOOP_MOVE", self._goop_move, Intent(IntentType.DEBUFF))
        whip.follow_up_state = glomp
        glomp.follow_up_state = goop
        goop.follow_up_state = whip
        initial = {0: whip, 1: glomp, 2: goop}.get(self.starter_move_idx % 3, whip)
        return MonsterMoveStateMachine([whip, glomp, goop], initial)

    def _whip_slap_move(self, targets: List[Creature]) -> None:
        for _ in range(2):
            for target in targets:
                self.attack(target, self.whip_slap_damage)

    def _glomp_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.glomp_damage)

    def _goop_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Frail
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Frail(self.goop_frail))


class SkulkingColony(MonsterModel):
    """스컬킹 콜로니 (엘리트) — HP 75, 개전 HardenedShellPower(20) 부여
    (자신의 한 턴 동안 최대 20 HP 손실로 제한).

    원본(SkulkingColony.cs) 그래프: ZOOM_MOVE(14딜) → ZOOM_MOVE_2(14딜,
    ZOOM_MOVE와 동일 동작의 별개 상태) → INERTIA_MOVE(9딜+힘+2) →
    PIERCING_STABS_MOVE(7딜×2) → ZOOM_MOVE → ... (고정 4순환, RNG 분기 없음)."""
    monster_id = "skulking_colony"
    title = "Skulking Colony"

    @property
    def min_initial_hp(self) -> int:
        return 75

    @property
    def max_initial_hp(self) -> int:
        return 75

    @property
    def inertia_damage(self) -> int:
        return 9

    @property
    def zoom_damage(self) -> int:
        return 14

    @property
    def piercing_stabs_damage(self) -> int:
        return 7

    @property
    def inertia_strength_gain(self) -> int:
        return 2

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import HardenedShellPower
        self.apply_power(HardenedShellPower(20))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        zoom1 = MoveState("ZOOM_MOVE", self._zoom_move,
                          Intent(IntentType.ATTACK, damage=self.zoom_damage))
        zoom2 = MoveState("ZOOM_MOVE_2", self._zoom_move,
                          Intent(IntentType.ATTACK, damage=self.zoom_damage))
        inertia = MoveState("INERTIA_MOVE", self._inertia_move,
                           Intent(IntentType.ATTACK_BUFF, damage=self.inertia_damage))
        piercing = MoveState("PIERCING_STABS_MOVE", self._piercing_stabs_move,
                            Intent(IntentType.ATTACK, damage=self.piercing_stabs_damage, times=2))
        zoom1.follow_up_state = zoom2
        zoom2.follow_up_state = inertia
        inertia.follow_up_state = piercing
        piercing.follow_up_state = zoom1
        return MonsterMoveStateMachine([zoom1, zoom2, inertia, piercing], zoom1)

    def _zoom_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.zoom_damage)

    def _inertia_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        for target in targets:
            self.attack(target, self.inertia_damage)
        self.apply_power(Strength(self.inertia_strength_gain))

    def _piercing_stabs_move(self, targets: List[Creature]) -> None:
        for _ in range(2):
            for target in targets:
                self.attack(target, self.piercing_stabs_damage)


class TerrorEel(MonsterModel):
    """테러 일 (엘리트) — HP 140, 개전 ShriekPower(70) 부여 (HP가 70 이하로
    떨어지면 1턴 스턴 후 대상에게 영구 취약(99)을 건다).

    원본(TerrorEel.cs) 그래프: CRASH_MOVE(16딜) ↔ THRASH_MOVE(3딜×3+활력+6)
    영구 교대(고정 2순환). ShriekPower가 발동하면 CreatureCmd.Stun으로
    STUN_MOVE(무행동)를 1턴 삽입한 뒤 TERROR_MOVE(대상 취약+99, 사실상 영구)로
    강제 전환되고, 이후 CRASH_MOVE로 복귀해 원래 순환을 재개한다."""
    monster_id = "terror_eel"
    title = "Terror Eel"

    @property
    def min_initial_hp(self) -> int:
        return 140

    @property
    def max_initial_hp(self) -> int:
        return 140

    @property
    def shriek_amount(self) -> int:
        return 70

    @property
    def crash_damage(self) -> int:
        return 16

    @property
    def thrash_damage(self) -> int:
        return 3

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import ShriekPower
        self.apply_power(ShriekPower(self.shriek_amount))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        crash = MoveState("CRASH_MOVE", self._crash_move,
                          Intent(IntentType.ATTACK, damage=self.crash_damage))
        thrash = MoveState("THRASH_MOVE", self._thrash_move,
                           Intent(IntentType.ATTACK_BUFF, damage=self.thrash_damage, times=3))
        stun = MoveState("STUN_MOVE", self._stun_move, Intent(IntentType.STUN))
        terror = MoveState("TERROR_MOVE", self._terror_move, Intent(IntentType.DEBUFF))
        crash.follow_up_state = thrash
        thrash.follow_up_state = crash
        stun.follow_up_state = terror
        terror.follow_up_state = crash
        return MonsterMoveStateMachine([crash, thrash, stun, terror], crash)

    def _crash_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.crash_damage)

    def _thrash_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Vigor
        for _ in range(3):
            for target in targets:
                self.attack(target, self.thrash_damage)
        self.apply_power(Vigor(6))

    def _stun_move(self, targets: List[Creature]) -> None:
        pass

    def _terror_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Vulnerable
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Vulnerable(99))


class PhantasmalGardener(MonsterModel):
    """팬텀 가드너 (엘리트, 4마리 동시 등장) — HP 26~31, 개전 SkittishPower(6)
    부여 (플레이어 카드 공격에 턴당 1회 블록+6).

    원본(PhantasmalGardener.cs)은 배치 슬롯(first/second/third/fourth)에 따라
    시작 무브가 다르다 (ConditionalBranchState "INIT_MOVE") — first=FLAIL,
    second=BITE, third=LASH, fourth=ENLARGE. 이후 고정 순환:
    BITE_MOVE(5딜) → LASH_MOVE(7딜) → FLAIL_MOVE(1딜×3) → ENLARGE_MOVE(힘+2) →
    BITE_MOVE → ... (RNG 분기 없음, 슬롯은 시작 위치만 결정)."""
    monster_id = "phantasmal_gardener"
    title = "Phantasmal Gardener"

    @property
    def min_initial_hp(self) -> int:
        return 26

    @property
    def max_initial_hp(self) -> int:
        return 31

    @property
    def bite_damage(self) -> int:
        return 5

    @property
    def lash_damage(self) -> int:
        return 7

    @property
    def flail_damage(self) -> int:
        return 1

    @property
    def flail_repeat(self) -> int:
        return 3

    @property
    def enlarge_str(self) -> int:
        return 2

    @property
    def skittish_amount(self) -> int:
        return 6

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import SkittishPower
        self.apply_power(SkittishPower(self.skittish_amount))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        bite = MoveState("BITE_MOVE", self._bite_move,
                         Intent(IntentType.ATTACK, damage=self.bite_damage))
        lash = MoveState("LASH_MOVE", self._lash_move,
                         Intent(IntentType.ATTACK, damage=self.lash_damage))
        flail = MoveState("FLAIL_MOVE", self._flail_move,
                          Intent(IntentType.ATTACK, damage=self.flail_damage, times=self.flail_repeat))
        enlarge = MoveState("ENLARGE_MOVE", self._enlarge_move, Intent(IntentType.BUFF))
        bite.follow_up_state = lash
        lash.follow_up_state = flail
        flail.follow_up_state = enlarge
        enlarge.follow_up_state = bite
        init = ConditionalBranchState("INIT_MOVE")
        init.add_state(flail, lambda: self.slot_name == "first")
        init.add_state(bite, lambda: self.slot_name == "second")
        init.add_state(lash, lambda: self.slot_name == "third")
        init.add_state(enlarge, lambda: self.slot_name == "fourth")
        return MonsterMoveStateMachine([bite, lash, flail, enlarge, init], init)

    def _bite_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.bite_damage)

    def _lash_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.lash_damage)

    def _flail_move(self, targets: List[Creature]) -> None:
        for _ in range(self.flail_repeat):
            for target in targets:
                self.attack(target, self.flail_damage)

    def _enlarge_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(self.enlarge_str))


class LagavulinMatriarch(MonsterModel):
    """라가불린 마트리아크 (Act1 보스) — HP 222, 개전 Plating(12)+AsleepPower(3)
    부여 (잠든 상태 — 3턴 무공격, 피격 시 즉시 깨어남).

    원본(LagavulinMatriarch.cs): SLEEP_MOVE(무공격) → ConditionalBranchState
    "SLEEP_BRANCH"(Asleep 보유 시 SLEEP_MOVE 재방문, 아니면 SLASH_MOVE로 진입).
    깨어난 뒤 고정 순환: SLASH_MOVE(19딜) → DISEMBOWEL_MOVE(9딜×2) →
    SLASH2_MOVE(12딜+블록12) → SOUL_SIPHON_MOVE(대상 힘-2/민첩-2, 자신 힘+2) →
    SLASH_MOVE → ... (RNG 분기 없음)."""
    monster_id = "lagavulin_matriarch"
    title = "Lagavulin Matriarch"

    @property
    def min_initial_hp(self) -> int:
        return 222

    @property
    def max_initial_hp(self) -> int:
        return 222

    @property
    def slash_damage(self) -> int:
        return 19

    @property
    def slash2_damage(self) -> int:
        return 12

    @property
    def slash2_block(self) -> int:
        return 12

    @property
    def disembowel_damage(self) -> int:
        return 9

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import Plating, AsleepPower
        self.apply_power(Plating(12))
        self.apply_power(AsleepPower(3))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        sleep = MoveState("SLEEP_MOVE", self._sleep_move, Intent(IntentType.SLEEP))
        slash = MoveState("SLASH_MOVE", self._slash_move,
                          Intent(IntentType.ATTACK, damage=self.slash_damage))
        slash2 = MoveState("SLASH2_MOVE", self._slash2_move,
                           Intent(IntentType.ATTACK_DEFEND, damage=self.slash2_damage))
        disembowel = MoveState("DISEMBOWEL_MOVE", self._disembowel_move,
                               Intent(IntentType.ATTACK, damage=self.disembowel_damage, times=2))
        soul_siphon = MoveState("SOUL_SIPHON_MOVE", self._soul_siphon_move, Intent(IntentType.DEBUFF))
        branch = ConditionalBranchState("SLEEP_BRANCH")
        branch.add_state(sleep, lambda: self.has_power("asleep"))
        branch.add_state(slash, lambda: not self.has_power("asleep"))
        sleep.follow_up_state = branch
        slash.follow_up_state = disembowel
        disembowel.follow_up_state = slash2
        slash2.follow_up_state = soul_siphon
        soul_siphon.follow_up_state = slash
        return MonsterMoveStateMachine([sleep, slash, slash2, disembowel, soul_siphon, branch], sleep)

    def _sleep_move(self, targets: List[Creature]) -> None:
        pass

    def _slash_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.slash_damage)

    def _slash2_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.slash2_damage)
        self.gain_block(self.slash2_block)

    def _disembowel_move(self, targets: List[Creature]) -> None:
        for _ in range(2):
            for target in targets:
                self.attack(target, self.disembowel_damage)

    def _soul_siphon_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength, Dexterity
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Strength(-2))
                target.apply_power(Dexterity(-2))
        self.apply_power(Strength(2))


BATCH9_MONSTERS = {
    "corpse_slug": CorpseSlug,
    "skulking_colony": SkulkingColony,
    "terror_eel": TerrorEel,
    "phantasmal_gardener": PhantasmalGardener,
    "lagavulin_matriarch": LagavulinMatriarch,
}

MONSTER_REGISTRY.update(BATCH9_MONSTERS)
