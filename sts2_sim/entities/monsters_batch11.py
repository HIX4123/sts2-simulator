"""
STS2 몬스터 배치 11 (Phase 6n) — 디컴파일 Models.Monsters.* 이식 (9종).
SlimedBerserker / SlitheringStrangler / Exoskeleton / HunterKiller /
MechaKnight(엘리트) / BygoneEffigy(엘리트) / Inklet / ScrollOfBiting /
Vantom(보스).
모든 수치는 Ascension 미적용 기본값 (AscensionHelper.GetValueIfAscension(..., tough,
normal)의 normal/마지막 인자를 사용).

C# AddBranch 오버로드 주의 (CLAUDE.md 참조): 정수 인자는 weight가 아니다.
- AddBranch(state, MoveRepeatType.CannotRepeat) → cannot_repeat
- AddBranch(state, MoveRepeatType.CannotRepeat, 1f) → cannot_repeat + weight 1.0
- AddBranch(state, MoveRepeatType.CanRepeatForever) → 제한 없음
- AddBranch(state, int) 2-인자 → maxRepeats (base weight는 1 유지)
여기서는 HunterKiller RAND의 "2"와 ScrollOfBiting rand의 "2"가 전부
maxRepeats이며, 두 분기 모두 base weight는 1로 동일하다.

"""
from __future__ import annotations
from typing import List

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    MonsterModel, MonsterMoveStateMachine, MoveState, RandomBranchState,
    ConditionalBranchState, Intent, IntentType, MONSTER_REGISTRY,
)


class SlimedBerserker(MonsterModel):
    """슬라임드 버서커 — HP 261, 개전 파워 없음.

    원본(SlimedBerserker.cs) 그래프: VOMIT_ICHOR_MOVE(Slimed 10장을 버림 더미로) →
    FURIOUS_PUMMELING_MOVE(4딜×4회) → LEECHING_HUG_MOVE(대상 약화 3 + 자신 힘 +3) →
    SMOTHER_MOVE(30딜) → VOMIT_ICHOR_MOVE → ... (고정 4순환, RNG 분기 없음)."""
    monster_id = "slimed_berserker"
    title = "Slimed Berserker"

    @property
    def min_initial_hp(self) -> int:
        return 261

    @property
    def max_initial_hp(self) -> int:
        return 261

    @property
    def vomit_slimed_count(self) -> int:
        return 10

    @property
    def pummeling_damage(self) -> int:
        return 4

    @property
    def pummeling_repeat(self) -> int:
        return 4

    @property
    def leeching_weak(self) -> int:
        return 3

    @property
    def leeching_strength_gain(self) -> int:
        return 3

    @property
    def smother_damage(self) -> int:
        return 30

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        vomit = MoveState("VOMIT_ICHOR_MOVE", self._vomit_ichor_move,
                          Intent(IntentType.STATUS))
        pummeling = MoveState(
            "FURIOUS_PUMMELING_MOVE", self._furious_pummeling_move,
            Intent(IntentType.ATTACK, damage=self.pummeling_damage,
                   times=self.pummeling_repeat),
        )
        hug = MoveState("LEECHING_HUG_MOVE", self._leeching_hug_move,
                        Intent(IntentType.DEBUFF))
        smother = MoveState("SMOTHER_MOVE", self._smother_move,
                            Intent(IntentType.ATTACK, damage=self.smother_damage))
        vomit.follow_up_state = pummeling
        pummeling.follow_up_state = hug
        hug.follow_up_state = smother
        smother.follow_up_state = vomit
        return MonsterMoveStateMachine([vomit, smother, hug, pummeling], vomit)

    def _vomit_ichor_move(self, targets: List[Creature]) -> None:
        self.add_status_to_player_discard("slimed", self.vomit_slimed_count)

    def _furious_pummeling_move(self, targets: List[Creature]) -> None:
        for _ in range(self.pummeling_repeat):
            for target in targets:
                self.attack(target, self.pummeling_damage)

    def _leeching_hug_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength, Weak
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Weak(self.leeching_weak))
        self.apply_power(Strength(self.leeching_strength_gain))

    def _smother_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.smother_damage)


class SlitheringStrangler(MonsterModel):
    """슬리더링 스트랭글러 — HP 53~55, 개전 파워 없음.

    원본(SlitheringStrangler.cs) 그래프: CONSTRICT(대상에 속박 3) → rand →
    {THWACK(7딜 + 자신 블록 5), LASH(12딜)} → 다시 CONSTRICT → ... .
    두 분기 모두 CanRepeatForever(반복 제한 없음), 가중치 동일."""
    monster_id = "slithering_strangler"
    title = "Slithering Strangler"

    @property
    def min_initial_hp(self) -> int:
        return 53

    @property
    def max_initial_hp(self) -> int:
        return 55

    @property
    def constrict_amount(self) -> int:
        return 3

    @property
    def thwack_damage(self) -> int:
        return 7

    @property
    def thwack_block(self) -> int:
        return 5

    @property
    def lash_damage(self) -> int:
        return 12

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        constrict = MoveState("CONSTRICT", self._constrict_move, Intent(IntentType.DEBUFF))
        thwack = MoveState("THWACK", self._thwack_move,
                           Intent(IntentType.ATTACK_DEFEND, damage=self.thwack_damage))
        lash = MoveState("LASH", self._lash_move,
                         Intent(IntentType.ATTACK, damage=self.lash_damage))
        rand = RandomBranchState("rand")
        rand.add_branch(thwack)  # MoveRepeatType.CanRepeatForever — 제한 없음
        rand.add_branch(lash)
        constrict.follow_up_state = rand
        thwack.follow_up_state = constrict
        lash.follow_up_state = constrict
        return MonsterMoveStateMachine([rand, thwack, constrict, lash], constrict)

    def _constrict_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import ConstrictPower
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(ConstrictPower(self.constrict_amount), applier=self)

    def _thwack_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.thwack_damage)
        self.gain_block(self.thwack_block)  # 원본 ValueProp.Move

    def _lash_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.lash_damage)


class Exoskeleton(MonsterModel):
    """엑소스켈레톤 — HP 24~28, 개전 시 HardToKillPower(9)
    (한 번에 받는 피해가 9로 제한된다).

    원본(Exoskeleton.cs) 그래프: INIT_MOVE(슬롯별 시작 위치 결정) —
    first→SKITTER, second→MANDIBLES, third→ENRAGE, fourth→RAND.
    이후 SKITTER→RAND, MANDIBLES→ENRAGE, ENRAGE→RAND.
    RAND는 {SKITTER, MANDIBLES} 각 CannotRepeat + 가중치 1.

    PhantasmalGardener와 동일하게 슬롯이 배정되지 않으면(slot_name=None)
    INIT_MOVE가 해석되지 않으므로 반드시 인카운터 팩토리로 생성한다."""
    monster_id = "exoskeleton"
    title = "Exoskeleton"

    @property
    def min_initial_hp(self) -> int:
        return 24

    @property
    def max_initial_hp(self) -> int:
        return 28

    @property
    def skitter_damage(self) -> int:
        return 1

    @property
    def skitter_repeats(self) -> int:
        return 3

    @property
    def mandibles_damage(self) -> int:
        return 8

    @property
    def enrage_strength_gain(self) -> int:
        return 2

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import HardToKillPower
        self.apply_power(HardToKillPower(9))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        skitter = MoveState(
            "SKITTER_MOVE", self._skitter_move,
            Intent(IntentType.ATTACK, damage=self.skitter_damage,
                   times=self.skitter_repeats),
        )
        mandibles = MoveState("MANDIBLES_MOVE", self._mandibles_move,
                              Intent(IntentType.ATTACK, damage=self.mandibles_damage))
        enrage = MoveState("ENRAGE_MOVE", self._enrage_move, Intent(IntentType.BUFF))
        rand = RandomBranchState("RAND")
        rand.add_branch(skitter, cannot_repeat=True)
        rand.add_branch(mandibles, cannot_repeat=True)
        init = ConditionalBranchState("INIT_MOVE")
        init.add_state(skitter, lambda: self.slot_name == "first")
        init.add_state(mandibles, lambda: self.slot_name == "second")
        init.add_state(enrage, lambda: self.slot_name == "third")
        init.add_state(rand, lambda: self.slot_name == "fourth")
        skitter.follow_up_state = rand
        mandibles.follow_up_state = enrage
        enrage.follow_up_state = rand
        return MonsterMoveStateMachine([init, rand, skitter, mandibles, enrage], init)

    def _skitter_move(self, targets: List[Creature]) -> None:
        for _ in range(self.skitter_repeats):
            for target in targets:
                self.attack(target, self.skitter_damage)

    def _mandibles_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.mandibles_damage)

    def _enrage_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(self.enrage_strength_gain))


class HunterKiller(MonsterModel):
    """헌터 킬러 — HP 121, 개전 파워 없음.

    원본(HunterKiller.cs) 그래프: TENDERIZING_GOOP_MOVE(대상에 Tender 1) → RAND,
    이후 모든 무브가 RAND로 복귀. RAND = {BITE(17딜, CannotRepeat),
    PUNCTURE(7딜×3, maxRepeats 2)} — "2"는 weight가 아니라 최대 연속 반복 횟수."""
    monster_id = "hunter_killer"
    title = "Hunter Killer"

    @property
    def min_initial_hp(self) -> int:
        return 121

    @property
    def max_initial_hp(self) -> int:
        return 121

    @property
    def goop_tender(self) -> int:
        return 1

    @property
    def bite_damage(self) -> int:
        return 17

    @property
    def puncture_damage(self) -> int:
        return 7

    @property
    def puncture_repeat(self) -> int:
        return 3

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        goop = MoveState("TENDERIZING_GOOP_MOVE", self._goop_move, Intent(IntentType.DEBUFF))
        bite = MoveState("BITE_MOVE", self._bite_move,
                         Intent(IntentType.ATTACK, damage=self.bite_damage))
        puncture = MoveState(
            "PUNCTURE_MOVE", self._puncture_move,
            Intent(IntentType.ATTACK, damage=self.puncture_damage,
                   times=self.puncture_repeat),
        )
        rand = RandomBranchState("RAND")
        rand.add_branch(bite, cannot_repeat=True)
        rand.add_branch(puncture, max_repeats=2)  # AddBranch(state, 2) = maxRepeats
        goop.follow_up_state = rand
        bite.follow_up_state = rand
        puncture.follow_up_state = rand
        return MonsterMoveStateMachine([goop, bite, puncture, rand], goop)

    def _goop_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import TenderPower
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(TenderPower(self.goop_tender), applier=self)

    def _bite_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.bite_damage)

    def _puncture_move(self, targets: List[Creature]) -> None:
        for _ in range(self.puncture_repeat):
            for target in targets:
                self.attack(target, self.puncture_damage)


class MechaKnight(MonsterModel):
    """메카 나이트 (엘리트) — HP 300, 개전 시 ArtifactPower(3)
    (디버프 3회 무효화).

    원본(MechaKnight.cs) 그래프: CHARGE_MOVE(25딜) → FLAMETHROWER_MOVE(화상 4장을
    손패로) → WINDUP_MOVE(블록 15 + 자신 힘 +5) → HEAVY_CLEAVE_MOVE(35딜) →
    FLAMETHROWER_MOVE → ... (첫 CHARGE 이후 4순환이 아니라 3순환 반복).
    화상은 버림 더미가 아니라 손패(PileType.Hand)로 들어간다."""
    monster_id = "mecha_knight"
    title = "Mecha Knight"

    @property
    def min_initial_hp(self) -> int:
        return 300

    @property
    def max_initial_hp(self) -> int:
        return 300

    @property
    def charge_damage(self) -> int:
        return 25

    @property
    def heavy_cleave_damage(self) -> int:
        return 35

    @property
    def windup_block(self) -> int:
        return 15

    @property
    def windup_strength_gain(self) -> int:
        return 5

    @property
    def flamethrower_burn_count(self) -> int:
        return 4

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import Artifact
        self.apply_power(Artifact(3))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        charge = MoveState("CHARGE_MOVE", self._charge_move,
                           Intent(IntentType.ATTACK, damage=self.charge_damage))
        flamethrower = MoveState("FLAMETHROWER_MOVE", self._flamethrower_move,
                                 Intent(IntentType.STATUS))
        windup = MoveState("WINDUP_MOVE", self._windup_move, Intent(IntentType.DEFEND_BUFF))
        heavy_cleave = MoveState(
            "HEAVY_CLEAVE_MOVE", self._heavy_cleave_move,
            Intent(IntentType.ATTACK, damage=self.heavy_cleave_damage),
        )
        charge.follow_up_state = flamethrower
        flamethrower.follow_up_state = windup
        windup.follow_up_state = heavy_cleave
        heavy_cleave.follow_up_state = flamethrower
        return MonsterMoveStateMachine([charge, heavy_cleave, windup, flamethrower], charge)

    def _charge_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.charge_damage)

    def _flamethrower_move(self, targets: List[Creature]) -> None:
        # 원본 CardPileCmd.AddToCombatAndPreview<Burn>(targets, PileType.Hand, 4)
        # ponytail: generate_card(to="hand")는 손패 10장 상한을 넘는 분은 조용히
        # 버린다 (원본은 넘친 카드를 버림 더미로 보낸다). 이 프로젝트의 단일
        # 손패-삽입 경로가 공유하는 기존 동작이라 여기서만 우회하지 않는다 —
        # 상한 초과가 실제로 문제되면 combat.generate_card에 오버플로 처리를
        # 한 번 추가해 모든 호출자가 같이 고쳐지게 할 것.
        if self.combat_state is not None:
            self.combat_state.generate_card(
                "burn", count=self.flamethrower_burn_count,
                to="hand", creator_is_player=False)

    def _windup_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.gain_block(self.windup_block)  # 원본 ValueProp.Move
        self.apply_power(Strength(self.windup_strength_gain))

    def _heavy_cleave_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.heavy_cleave_damage)


class BygoneEffigy(MonsterModel):
    """바이곤 이피지 (엘리트) — HP 127, 개전 시 스스로에게 SlowPower(1)
    (플레이어가 이번 턴 낸 카드 1장당 받는 파워드 공격 피해 +10%).

    원본(BygoneEffigy.cs) 그래프: SLEEP_MOVE(무행동) → WAKE_MOVE(자신 힘 +10) →
    SLASHES_MOVE(13딜) → SLASHES_MOVE → ... (이후 계속 SLASHES).
    SLEEP_MOVE_2는 상태 목록에는 있으나 어떤 무브도 진입하지 않는 사문화 상태 —
    원본 리스트 구성을 그대로 보존한다."""
    monster_id = "bygone_effigy"
    title = "Bygone Effigy"

    @property
    def min_initial_hp(self) -> int:
        return 127

    @property
    def max_initial_hp(self) -> int:
        return 127

    @property
    def slash_damage(self) -> int:
        return 13

    @property
    def wake_strength_gain(self) -> int:
        return 10

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import SlowPower
        self.apply_power(SlowPower(1))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        sleep = MoveState("SLEEP_MOVE", self._sleep_move, Intent(IntentType.SLEEP))
        wake = MoveState("WAKE_MOVE", self._wake_move, Intent(IntentType.BUFF))
        sleep2 = MoveState("SLEEP_MOVE_2", self._sleep_move, Intent(IntentType.SLEEP))
        slashes = MoveState("SLASHES_MOVE", self._slash_move,
                            Intent(IntentType.ATTACK, damage=self.slash_damage))
        sleep.follow_up_state = wake
        wake.follow_up_state = slashes
        sleep2.follow_up_state = slashes
        slashes.follow_up_state = slashes
        return MonsterMoveStateMachine([sleep, wake, sleep2, slashes], sleep)

    def _sleep_move(self, targets: List[Creature]) -> None:
        pass

    def _wake_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(self.wake_strength_gain))

    def _slash_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.slash_damage)


class Inklet(MonsterModel):
    """잉클렛 — HP 11~17, 개전 시 SlipperyPower(1)
    (한 번에 잃는 HP가 1로 제한되고, 관통 피해를 받을 때마다 1 감소).

    원본(Inklet.cs) 그래프: JAB(3딜) → RAND, RAND = {PIERCING_GAZE(10딜),
    WHIRLWIND(2딜×3)} 각 CannotRepeat + 가중치 1. WHIRLWIND/PIERCING_GAZE는
    모두 JAB으로 복귀한다 (원본에서 moveState.FollowUpState가 RAND로 두 번
    대입되지만 마지막 대입이 유효 — JAB만 RAND로 간다).
    시작 무브는 가운데 잉클렛이면 WHIRLWIND, 아니면 JAB.
    INIT_RAND는 생성만 되고 상태 목록/초기 상태 어디에도 쓰이지 않는 사문화
    코드라 이식하지 않는다."""
    monster_id = "inklet"
    title = "Inklet"

    def __init__(self, middle_inklet: bool = False):
        super().__init__()
        self.middle_inklet = middle_inklet

    @property
    def min_initial_hp(self) -> int:
        return 11

    @property
    def max_initial_hp(self) -> int:
        return 17

    @property
    def jab_damage(self) -> int:
        return 3

    @property
    def whirlwind_damage(self) -> int:
        return 2

    @property
    def whirlwind_repeat(self) -> int:
        return 3

    @property
    def piercing_gaze_damage(self) -> int:
        return 10

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import SlipperyPower
        self.apply_power(SlipperyPower(1))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        jab = MoveState("JAB_MOVE", self._jab_move,
                        Intent(IntentType.ATTACK, damage=self.jab_damage))
        whirlwind = MoveState(
            "WHIRLWIND_MOVE", self._whirlwind_move,
            Intent(IntentType.ATTACK, damage=self.whirlwind_damage,
                   times=self.whirlwind_repeat),
        )
        piercing = MoveState("PIERCING_GAZE_MOVE", self._piercing_gaze_move,
                             Intent(IntentType.ATTACK, damage=self.piercing_gaze_damage))
        rand = RandomBranchState("RAND")
        rand.add_branch(piercing, cannot_repeat=True)
        rand.add_branch(whirlwind, cannot_repeat=True)
        jab.follow_up_state = rand
        whirlwind.follow_up_state = jab
        piercing.follow_up_state = jab
        initial = whirlwind if self.middle_inklet else jab
        return MonsterMoveStateMachine([jab, piercing, whirlwind, rand], initial)

    def _jab_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.jab_damage)

    def _whirlwind_move(self, targets: List[Creature]) -> None:
        for _ in range(self.whirlwind_repeat):
            for target in targets:
                self.attack(target, self.whirlwind_damage)

    def _piercing_gaze_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.piercing_gaze_damage)


class ScrollOfBiting(MonsterModel):
    """스크롤 오브 바이팅 — HP 30~37, 개전 시 PaperCutsPower(2)
    (공격이 플레이어의 블록을 뚫을 때마다 플레이어 최대 HP -2).

    원본(ScrollOfBiting.cs) 그래프: CHOMP(14딜) → MORE_TEETH(자신 힘 +2) →
    CHEW(5딜×2) → rand → {CHOMP(CannotRepeat), CHEW(maxRepeats 2)} — "2"는
    weight가 아니라 최대 연속 반복 횟수. 시작 무브는 StarterMoveIdx % 3으로
    0→CHOMP, 1→CHEW, 2→MORE_TEETH."""
    monster_id = "scroll_of_biting"
    title = "Scroll of Biting"

    def __init__(self, starter_move_idx: int = 0):
        super().__init__()
        self.starter_move_idx = starter_move_idx

    @property
    def min_initial_hp(self) -> int:
        return 30

    @property
    def max_initial_hp(self) -> int:
        return 37

    @property
    def chomp_damage(self) -> int:
        return 14

    @property
    def chew_damage(self) -> int:
        return 5

    @property
    def chew_repeat(self) -> int:
        return 2

    @property
    def more_teeth_strength_gain(self) -> int:
        return 2

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import PaperCutsPower
        self.apply_power(PaperCutsPower(2))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        chomp = MoveState("CHOMP", self._chomp_move,
                          Intent(IntentType.ATTACK, damage=self.chomp_damage))
        chew = MoveState("CHEW", self._chew_move,
                         Intent(IntentType.ATTACK, damage=self.chew_damage,
                                times=self.chew_repeat))
        more_teeth = MoveState("MORE_TEETH", self._more_teeth_move, Intent(IntentType.BUFF))
        rand = RandomBranchState("rand")
        rand.add_branch(chomp, cannot_repeat=True)
        rand.add_branch(chew, max_repeats=2)  # AddBranch(state, 2) = maxRepeats
        chomp.follow_up_state = more_teeth
        chew.follow_up_state = rand
        more_teeth.follow_up_state = chew
        initial = {0: chomp, 1: chew}.get(self.starter_move_idx % 3, more_teeth)
        return MonsterMoveStateMachine([chomp, chew, more_teeth, rand], initial)

    def _chomp_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.chomp_damage)

    def _chew_move(self, targets: List[Creature]) -> None:
        for _ in range(self.chew_repeat):
            for target in targets:
                self.attack(target, self.chew_damage)

    def _more_teeth_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(self.more_teeth_strength_gain))


class Vantom(MonsterModel):
    """반톰 (보스) — HP 173, 개전 시 SlipperyPower(8)
    (한 번에 잃는 HP가 1로 제한되고, 관통 피해를 받을 때마다 1 감소 —
    실질적으로 초반 8히트를 1피해로 흘린다).
    ShouldDisappearFromDoom=false — Doom 즉사로 제거되지 않는다.

    원본(Vantom.cs) 그래프: INK_BLOT_MOVE(7딜) → INKY_LANCE_MOVE(6딜×2) →
    DISMEMBER_MOVE(26딜 + 상처 3장을 버림 더미로) → PREPARE_MOVE(자신 힘 +2) →
    INK_BLOT_MOVE → ... (고정 4순환, RNG 분기 없음)."""
    monster_id = "vantom"
    title = "Vantom"

    @property
    def min_initial_hp(self) -> int:
        return 173

    @property
    def max_initial_hp(self) -> int:
        return 173

    @property
    def slippery_amount(self) -> int:
        return 8

    @property
    def ink_blot_damage(self) -> int:
        return 7

    @property
    def inky_lance_damage(self) -> int:
        return 6

    @property
    def inky_lance_repeat(self) -> int:
        return 2

    @property
    def dismember_damage(self) -> int:
        return 26

    @property
    def dismember_wounds(self) -> int:
        return 3

    @property
    def prepare_strength_gain(self) -> int:
        return 2

    @property
    def should_disappear_from_doom(self) -> bool:
        return False

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import SlipperyPower
        self.apply_power(SlipperyPower(self.slippery_amount))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        ink_blot = MoveState("INK_BLOT_MOVE", self._ink_blot_move,
                             Intent(IntentType.ATTACK, damage=self.ink_blot_damage))
        inky_lance = MoveState(
            "INKY_LANCE_MOVE", self._inky_lance_move,
            Intent(IntentType.ATTACK, damage=self.inky_lance_damage,
                   times=self.inky_lance_repeat),
        )
        dismember = MoveState("DISMEMBER_MOVE", self._dismember_move,
                              Intent(IntentType.ATTACK, damage=self.dismember_damage))
        prepare = MoveState("PREPARE_MOVE", self._prepare_move, Intent(IntentType.BUFF))
        ink_blot.follow_up_state = inky_lance
        inky_lance.follow_up_state = dismember
        dismember.follow_up_state = prepare
        prepare.follow_up_state = ink_blot
        return MonsterMoveStateMachine([ink_blot, inky_lance, dismember, prepare], ink_blot)

    def _ink_blot_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.ink_blot_damage)

    def _inky_lance_move(self, targets: List[Creature]) -> None:
        for _ in range(self.inky_lance_repeat):
            for target in targets:
                self.attack(target, self.inky_lance_damage)

    def _dismember_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.dismember_damage)
        self.add_status_to_player_discard("wound", self.dismember_wounds)

    def _prepare_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(self.prepare_strength_gain))


BATCH11_MONSTERS = {
    "slimed_berserker": SlimedBerserker,
    "slithering_strangler": SlitheringStrangler,
    "exoskeleton": Exoskeleton,
    "hunter_killer": HunterKiller,
    "mecha_knight": MechaKnight,
    "bygone_effigy": BygoneEffigy,
    "inklet": Inklet,
    "scroll_of_biting": ScrollOfBiting,
    "vantom": Vantom,
}

MONSTER_REGISTRY.update(BATCH11_MONSTERS)
