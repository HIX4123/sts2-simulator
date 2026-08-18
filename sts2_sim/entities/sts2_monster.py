"""
STS2 MonsterModel — 디컴파일 MegaCrit.Sts2.Core.Models.Monsters.* 이식.

- MonsterModel은 Creature를 상속 (HP/블록/파워/데미지 파이프라인 공유)
- MonsterMoveStateMachine: MoveState(고정 전환) + RandomBranchState(가중치 분기)
- 모든 수치는 디컴파일 기준값 (Ascension 미적용 기본값)
"""
from __future__ import annotations
import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable, List, Optional

from sts2_sim.entities.creature import Creature

if TYPE_CHECKING:
    from sts2_sim.core.combat import CombatState


class IntentType(Enum):
    """STS2 Intent 타입."""
    ATTACK = auto()
    ATTACK_BUFF = auto()
    ATTACK_DEBUFF = auto()
    ATTACK_DEFEND = auto()
    BUFF = auto()
    DEBUFF = auto()
    DEFEND = auto()
    DEFEND_BUFF = auto()
    DEFEND_DEBUFF = auto()
    STATUS = auto()
    SLEEP = auto()
    STUN = auto()
    ESCAPE = auto()
    HIDDEN = auto()
    UNKNOWN = auto()


@dataclass
class Intent:
    """인텐트 정보."""
    intent_type: IntentType
    damage: int = 0
    times: int = 1


class MonsterState:
    """상태 머신 노드 베이스."""
    def __init__(self, name: str):
        self.name = name


class MoveState(MonsterState):
    """몬스터의 한 행동 상태."""
    def __init__(self, name: str, execute: Callable, intent: Intent):
        super().__init__(name)
        self.execute = execute
        self.intent = intent
        self.follow_up_state: Optional[MonsterState] = None


class RandomBranchState(MonsterState):
    """가중치 기반 무작위 분기 (디컴파일 RandomBranchState 대응).

    cannot_repeat=True인 분기는 직전 행동과 같으면 선택되지 않는다
    (디컴파일 MoveRepeatType.CannotRepeat — AddBranch(state, MoveRepeatType) 계열).
    cooldown>0이면 최근 cooldown회의 무브 이력 안에 자신이 있으면 제외된다
    (디컴파일 StateWeight.cooldown — AddBranch(state, int cooldown, MoveRepeatType)
    3-인자 오버로드가 실제로 바인딩되는 대상. 예: Flyconid RAND의 "3"/"2"는
    weight가 아니라 cooldown이며 세 분기 모두 base weight는 1로 동일하다).
    max_repeats가 설정되면 최근 max_repeats회 연속 동일 분기가 나왔을 때만 제외된다
    (디컴파일 MoveRepeatType.CanRepeatXTimes — AddBranch(state, int maxRepeats) 2-인자
    오버로드가 실제로 바인딩되는 대상. 예: FossilStalker RAND의 "2"는 weight가 아니라
    maxRepeats이며 세 분기 모두 base weight는 1로 동일하다).
    모든 분기가 제외되면(쿨다운/반복제한 전부 소진) 원본과 동일하게 첫 번째로
    등록된 분기로 폴백한다 (원본 GetNextState — 전체 weight합이 0이면 rng 결과와
    무관하게 리스트의 첫 항목이 선택됨)."""
    def __init__(self, name: str):
        super().__init__(name)
        # (state, weight, cannot_repeat, cooldown, max_repeats, use_only_once)
        self.branches: List[tuple] = []

    def add_branch(self, state: MoveState, weight=1, cannot_repeat: bool = False,
                   cooldown: int = 0, max_repeats: Optional[int] = None,
                   use_only_once: bool = False):
        """weight는 상수 또는 무인자 callable — 원본의 `Func<float>` 가중치
        오버로드(TwoTailedRat의 CanSummon 기반 확률 전환) 대응. 가중치가 0이면
        후보에서 제외된다.
        use_only_once — 원본 MoveRepeatType.UseOnlyOnce: 전투 중 한 번만 선택 가능."""
        self.branches.append((state, weight, cannot_repeat, cooldown, max_repeats, use_only_once))

    def resolve(self, rng: random.Random, last_move_name: Optional[str],
                history: Optional[List[str]] = None) -> MoveState:
        history = history or []
        candidates = []
        for s, w, cr, cd, mr, once in self.branches:
            if cr and s.name == last_move_name:
                continue
            if once and s.name in history:
                continue
            if mr is not None and len(history) >= mr and all(h == s.name for h in history[-mr:]):
                continue
            if cd > 0 and s.name in history[-cd:]:
                continue
            weight = w() if callable(w) else w
            if weight <= 0:  # 원본: 가중치 0인 분기는 뽑히지 않는다
                continue
            candidates.append((s, weight))
        if not candidates:
            return self.branches[0][0]
        states = [s for s, _ in candidates]
        weights = [w for _, w in candidates]
        return rng.choices(states, weights=weights, k=1)[0]


class ConditionalBranchState(MonsterState):
    """조건 기반 분기 (디컴파일 ConditionalBranchState 대응).

    RandomBranchState와 달리 가중치/RNG가 없다 — 등록 순서대로 조건 함수를
    평가해 처음 True를 반환하는 분기로 즉시 전환한다 (원본 GetNextState:
    foreach 순회 중 Evaluate() > 0인 첫 항목). 조건이 None이면 무조건 True로
    취급 (원본 ConditionalBranch.Evaluate — 람다 없으면 1 반환)."""
    def __init__(self, name: str):
        super().__init__(name)
        self.branches: List[tuple] = []  # (state, condition)

    def add_state(self, state: MonsterState, condition: Optional[Callable[[], bool]] = None) -> None:
        self.branches.append((state, condition))

    def resolve(self, rng: Optional[random.Random] = None, last_move_name: Optional[str] = None,
                history: Optional[List[str]] = None) -> MonsterState:
        for state, cond in self.branches:
            if cond is None or cond():
                return state
        raise ValueError(f"ConditionalBranchState {self.name}: 유효한 다음 상태를 찾지 못함")


class MonsterMoveStateMachine:
    """상태 머신: 몬스터의 행동 순서를 관리.

    initial_state로 RandomBranchState/ConditionalBranchState도 허용 —
    setup_for_combat에서 rng 주입 후 resolve_initial()이 시드 rng로 첫
    행동을 결정한다 (재현성 보장).
    """

    def __init__(self, states: List[MonsterState], initial_state: MonsterState):
        self.states = states
        self.states_by_name = {s.name: s for s in states}
        self.current_state: MonsterState = initial_state
        self.rng: random.Random = random.Random()
        self._last_move_name: Optional[str] = None
        self.history: List[str] = []  # 실행된 MoveState 이름 이력 (cooldown/max_repeats용)

    def resolve_initial(self) -> None:
        """초기 상태가 branch 노드면 현재 rng로 해석.
        분기가 다시 분기를 가리킬 수 있으므로(Exoskeleton INIT_MOVE의 fourth
        슬롯 → RAND) advance_state와 동일하게 MoveState에 도달할 때까지
        반복 해석한다 — 한 번만 풀면 브랜치 노드가 현재 상태로 남아
        execute_move에서 터진다."""
        while isinstance(self.current_state, (RandomBranchState, ConditionalBranchState)):
            self.current_state = self.current_state.resolve(self.rng, None, self.history)

    def get_current_intent(self) -> Intent:
        return self.current_state.intent

    def get_current_move_name(self) -> str:
        return self.current_state.name

    def execute_move(self, targets: List[Creature]) -> None:
        if self.current_state.execute:
            self.current_state.execute(targets)
        self._last_move_name = self.current_state.name
        self.history.append(self.current_state.name)

    def advance_state(self) -> None:
        nxt = self.current_state.follow_up_state
        while isinstance(nxt, (RandomBranchState, ConditionalBranchState)):
            nxt = nxt.resolve(self.rng, self._last_move_name, self.history)
        if nxt is not None:
            self.current_state = nxt

    def force_current_state(self, state: MonsterState) -> None:
        """디컴파일 ForceCurrentState/SetMoveImmediate 대응 — 정상 전환 절차를
        건너뛰고 즉시 현재 상태를 지정 상태로 덮어쓴다 (Shriek/Asleep 등의
        HP·피격 반응형 강제 전환용)."""
        self.current_state = state


class MonsterModel(Creature):
    """STS2 몬스터 베이스 (MonsterModel 대응). Creature 상속으로 파워/블록 공유."""

    monster_id: str = "unknown_monster"
    title: str = "Unknown Monster"

    def __init__(self):
        super().__init__(self.title, 1)
        self._move_state_machine: Optional[MonsterMoveStateMachine] = None
        self.combat_state: Optional["CombatState"] = None
        self.escaped = False
        # 원본 Creature.SlotName — 인카운터가 배치 위치(first/second/...)를 부여.
        # PhantasmalGardener처럼 시작 무브를 슬롯으로 결정하는 몬스터용.
        self.slot_name: Optional[str] = None
        # 소속 인카운터 ID — 전투 중 소환이 빈 슬롯을 찾을 때만 참조
        # (원본 CombatState.Encounter.GetNextSlot 대응, make_encounter가 새긴다).
        self.encounter_id: Optional[str] = None

    @property
    def min_initial_hp(self) -> int:
        return 0

    @property
    def max_initial_hp(self) -> int:
        return self.min_initial_hp

    @property
    def is_gone(self) -> bool:
        """전투에서 제거됨 (사망 또는 도주)."""
        return self.is_dead or self.escaped

    @property
    def should_disappear_from_doom(self) -> bool:
        """Doom 조건을 만족했을 때 전투에서 제거되는지 여부."""
        return True

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        nothing = MoveState("NOTHING", self._nothing_move, Intent(IntentType.HIDDEN))
        nothing.follow_up_state = nothing
        return MonsterMoveStateMachine([nothing], nothing)

    def _nothing_move(self, targets: List[Creature]) -> None:
        pass

    def setup_for_combat(self, state: Optional["CombatState"], rng: Optional[random.Random] = None) -> None:
        """전투 시작 시 초기화. 이후 after_added_to_room() 트리거."""
        self.combat_state = state
        self._max_hp = self.max_initial_hp
        self._current_hp = self.max_initial_hp
        self._block = 0
        self.escaped = False
        self._move_state_machine = self.generate_move_state_machine()
        if rng is not None:
            self._move_state_machine.rng = rng
        self._move_state_machine.resolve_initial()
        self.after_added_to_room()

    def after_added_to_room(self) -> None:
        """전투 투입 직후 (개전 버프 등, 서브클래스 오버라이드)."""
        pass

    def get_current_intent(self) -> Intent:
        if self._move_state_machine:
            return self._move_state_machine.get_current_intent()
        return Intent(IntentType.UNKNOWN)

    def stun(self, callback: Optional[Callable[[List[Creature]], None]] = None,
             next_move_name: Optional[str] = None) -> None:
        """디컴파일 CreatureCmd.Stun 대응 — 정상 무브 그래프를 건너뛰고 (다음)
        1턴은 callback(없으면 무행동)만 수행한 뒤, 그 다음부터 next_move_name
        (미지정 시 직전 위치 — StunInternal의 nextMoveId ?? StateLog.Last())으로
        재개한다. 이미 사망한 몬스터는 원본 StunInternal의 `!IsDead` 가드와
        동일하게 무시한다."""
        sm = self._move_state_machine
        if sm is None or self.is_dead:
            return
        if next_move_name is None:
            next_move_name = sm.history[-1] if sm.history else sm.current_state.name
        target = sm.states_by_name.get(next_move_name)
        stunned = MoveState("STUNNED", callback or (lambda targets: None), Intent(IntentType.STUN))
        stunned.follow_up_state = target
        sm.force_current_state(stunned)

    def take_turn(self, targets: List[Creature]) -> None:
        """현재 행동 실행 후 다음 상태로 전환.
        무브 실행 직후 flush_landed_attacks를 통지해(SuckPower 등) 같은 다단히트
        무브 안에서 앞선 히트로 얻은 파워가 뒤 히트에 소급 반영되지 않게 한다
        (원본 AfterAttack이 공격 커맨드 전체 종료 후 1회만 발동하는 것과 대응)."""
        if self._move_state_machine:
            self._move_state_machine.execute_move(targets)
            for p in list(self._powers.values()):
                flush = getattr(p, "flush_landed_attacks", None)
                if flush:
                    flush()
            self._move_state_machine.advance_state()

    def attack(self, target: Creature, base_damage: int) -> None:
        """공격 파이프라인 (자신의 Strength/Weak 반영).
        피해가 블록을 관통하면(hp_lost>0) 자신의 파워에 on_landed_attack 통지
        (원본 AfterAttack/AfterDamageGiven — FossilStalker SuckPower의 자기 파워드
        공격 적중 트리거, ScrollOfBiting PaperCutsPower의 대상 한정 최대 HP 감소).
        원본 AfterDamageGiven이 target을 넘겨받으므로 훅에도 피격 대상을 전달한다."""
        result = target.take_damage(self.compute_attack_damage(base_damage), source=self)
        if result.get("hp_lost", 0) > 0:
            for p in list(self._powers.values()):
                hook = getattr(p, "on_landed_attack", None)
                if hook:
                    hook(target)

    def add_status_to_player_discard(self, card_id: str, count: int) -> None:
        """플레이어 버림 더미에 상태이상 카드 삽입 (Dazed/Slimed)."""
        if self.combat_state and hasattr(self.combat_state, "add_status_to_discard"):
            self.combat_state.add_status_to_discard(card_id, count)

    def add_status_to_player_draw(self, card_id: str, count: int) -> None:
        """플레이어 뽑을 더미의 무작위 위치에 상태이상 카드 삽입 (SoulFysh BECKON_MOVE —
        원본 CardPilePosition.Random 대응)."""
        if self.combat_state and hasattr(self.combat_state, "add_status_to_draw"):
            self.combat_state.add_status_to_draw(card_id, count)

    def escape(self) -> None:
        """전투에서 도주 (FatGremlin 등)."""
        self.escaped = True

    def __repr__(self) -> str:
        return f"{self.title}({self._current_hp}/{self._max_hp})"


# ══════════════════════════════════════════
# 테스트 지원 몬스터 (디컴파일에도 존재)
# ══════════════════════════════════════════

class BigDummy(MonsterModel):
    """테스트용 더미 (HP 9999)."""
    monster_id = "big_dummy"
    title = "Big Dummy"

    @property
    def min_initial_hp(self) -> int:
        return 9999


class SingleAttackMoveMonster(MonsterModel):
    """단일 공격 테스트 몬스터 (POKE 1딜)."""
    monster_id = "single_attack"
    title = "Single Attack Monster"

    @property
    def min_initial_hp(self) -> int:
        return 999

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        poke = MoveState("POKE", self._poke_move, Intent(IntentType.ATTACK, damage=1))
        poke.follow_up_state = poke
        return MonsterMoveStateMachine([poke], poke)

    def _poke_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, 1)


class MultiAttackMoveMonster(MonsterModel):
    """다중 공격 테스트 몬스터 (2딜×3)."""
    monster_id = "multi_attack"
    title = "Multi Attack Monster"

    @property
    def min_initial_hp(self) -> int:
        return 999

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        atk = MoveState("ATTACK", self._attack_move, Intent(IntentType.ATTACK, damage=2, times=3))
        atk.follow_up_state = atk
        return MonsterMoveStateMachine([atk], atk)

    def _attack_move(self, targets: List[Creature]) -> None:
        for _ in range(3):
            for target in targets:
                self.attack(target, 2)


# ══════════════════════════════════════════
# 실전 몬스터 (디컴파일 수치)
# ══════════════════════════════════════════

class TwigSlimeS(MonsterModel):
    """나뭇가지 슬라임 (소) — HP 7~11, TACKLE 4딜."""
    monster_id = "twig_slime_s"
    title = "Twig Slime (S)"

    @property
    def min_initial_hp(self) -> int:
        return 7

    @property
    def max_initial_hp(self) -> int:
        return 11

    @property
    def tackle_damage(self) -> int:
        return 4

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        tackle = MoveState("TACKLE_MOVE", self._tackle_move,
                           Intent(IntentType.ATTACK, damage=self.tackle_damage))
        tackle.follow_up_state = tackle
        return MonsterMoveStateMachine([tackle], tackle)

    def _tackle_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.tackle_damage)


class TwigSlimeM(MonsterModel):
    """나뭇가지 슬라임 (중) — HP 26~28. POKEY_POUNCE 11딜 / STICKY_SHOT Slimed 1장 —
    두 분기 균등(1:1), POKEY_POUNCE는 2연속까지 허용 후 3연속 금지
    (MoveRepeatType.CanRepeatXTimes(2)). 원본 TwigSlimeM.cs의 AddBranch(state, 2)
    2-인자 호출은 weight가 아니라 maxRepeats로 바인딩됨 — Phase 6k 사후 감사로
    발견해 수정 (RandomBranchState.AddBranch 오버로드 오독)."""
    monster_id = "twig_slime_m"
    title = "Twig Slime (M)"

    @property
    def min_initial_hp(self) -> int:
        return 26

    @property
    def max_initial_hp(self) -> int:
        return 28

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        pounce = MoveState("POKEY_POUNCE_MOVE", self._pounce_move,
                           Intent(IntentType.ATTACK, damage=11))
        sticky = MoveState("STICKY_SHOT_MOVE", self._sticky_move,
                           Intent(IntentType.STATUS))
        branch = RandomBranchState("RAND")
        branch.add_branch(pounce, weight=1, max_repeats=2)
        branch.add_branch(sticky, weight=1, cannot_repeat=True)
        pounce.follow_up_state = branch
        sticky.follow_up_state = branch
        return MonsterMoveStateMachine([pounce, sticky, branch], sticky)

    def _pounce_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, 11)

    def _sticky_move(self, targets: List[Creature]) -> None:
        self.add_status_to_player_discard("slimed", 1)


class Stabbot(MonsterModel):
    """스탭봇 — HP 18~23, STAB 11딜 + 허약 1."""
    monster_id = "stabbot"
    title = "Stabbot"

    @property
    def min_initial_hp(self) -> int:
        return 18

    @property
    def max_initial_hp(self) -> int:
        return 23

    @property
    def stab_damage(self) -> int:
        return 11

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        stab = MoveState("STAB_MOVE", self._stab_move,
                         Intent(IntentType.ATTACK_DEBUFF, damage=self.stab_damage))
        stab.follow_up_state = stab
        return MonsterMoveStateMachine([stab], stab)

    def _stab_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Frail
        for target in targets:
            self.attack(target, self.stab_damage)
            if hasattr(target, "apply_power"):
                target.apply_power(Frail(1))


class Zapbot(MonsterModel):
    """잽봇 — HP 18~23, ZAP 14딜. (개전 시 HighVoltage 2 — 파워 미이식)."""
    monster_id = "zapbot"
    title = "Zapbot"

    @property
    def min_initial_hp(self) -> int:
        return 18

    @property
    def max_initial_hp(self) -> int:
        return 23

    @property
    def zap_damage(self) -> int:
        return 14

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        zap = MoveState("ZAP", self._zap_move,
                        Intent(IntentType.ATTACK, damage=self.zap_damage))
        zap.follow_up_state = zap
        return MonsterMoveStateMachine([zap], zap)

    def _zap_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.zap_damage)


class Guardbot(MonsterModel):
    """가드봇 — HP 16~20. GUARD: Fabricator 아군에 15블록 (Fabricator 미이식 시 무동작)."""
    monster_id = "guardbot"
    title = "Guardbot"

    @property
    def min_initial_hp(self) -> int:
        return 16

    @property
    def max_initial_hp(self) -> int:
        return 20

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        guard = MoveState("GUARD_MOVE", self._guard_move, Intent(IntentType.DEFEND))
        guard.follow_up_state = guard
        return MonsterMoveStateMachine([guard], guard)

    def _guard_move(self, targets: List[Creature]) -> None:
        if self.combat_state is None:
            return
        for ally in getattr(self.combat_state, "monsters", []):
            if getattr(ally, "monster_id", "") == "fabricator" and not ally.is_gone:
                ally.gain_block(15)


class AxeRubyRaider(MonsterModel):
    """도끼 루비 약탈자 — HP 20~22. SWING 5딜+5블록 ×2 → BIG_SWING 12딜 순환."""
    monster_id = "axe_ruby_raider"
    title = "Axe Ruby Raider"

    @property
    def min_initial_hp(self) -> int:
        return 20

    @property
    def max_initial_hp(self) -> int:
        return 22

    @property
    def swing_damage(self) -> int:
        return 5

    @property
    def swing_block(self) -> int:
        return 5

    @property
    def big_swing_damage(self) -> int:
        return 12

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        swing1 = MoveState("SWING_1", self._swing_move,
                           Intent(IntentType.ATTACK_DEFEND, damage=self.swing_damage))
        swing2 = MoveState("SWING_2", self._swing_move,
                           Intent(IntentType.ATTACK_DEFEND, damage=self.swing_damage))
        big = MoveState("BIG_SWING", self._big_swing_move,
                        Intent(IntentType.ATTACK, damage=self.big_swing_damage))
        swing1.follow_up_state = swing2
        swing2.follow_up_state = big
        big.follow_up_state = swing1
        return MonsterMoveStateMachine([swing1, swing2, big], swing1)

    def _swing_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.swing_damage)
        self.gain_block(self.swing_block)

    def _big_swing_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.big_swing_damage)


class FlailKnight(MonsterModel):
    """도리깨 기사 (엘리트) — HP 101.
    WAR_CHANT 힘+3(연속 불가) / FLAIL 9딜×2 / RAM 15딜 — 세 분기 균등(1:1:1),
    FLAIL/RAM은 동일 분기 2연속까지 허용 후 3연속 금지(MoveRepeatType.
    CanRepeatXTimes(2)). 초기 RAM.
    (원본 FlailKnight.cs의 AddBranch(state, 2) 2-인자 호출은 weight가 아니라
    maxRepeats로 바인딩됨 — Phase 6k에서 Flyconid/FossilStalker 검증 중 발견한
    RandomBranchState.AddBranch 오버로드 오독 패턴이 이 몬스터에도 있었음을
    사후 감사로 발견해 수정. MysteriousKnight가 이 무브그래프를 그대로
    상속하므로 영향받음.)"""
    monster_id = "flail_knight"
    title = "Flail Knight"

    @property
    def min_initial_hp(self) -> int:
        return 101

    @property
    def flail_damage(self) -> int:
        return 9

    @property
    def ram_damage(self) -> int:
        return 15

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        chant = MoveState("WAR_CHANT", self._war_chant_move, Intent(IntentType.BUFF))
        flail = MoveState("FLAIL_MOVE", self._flail_move,
                          Intent(IntentType.ATTACK, damage=self.flail_damage, times=2))
        ram = MoveState("RAM_MOVE", self._ram_move,
                        Intent(IntentType.ATTACK, damage=self.ram_damage))
        branch = RandomBranchState("RAND")
        branch.add_branch(chant, weight=1, cannot_repeat=True)
        branch.add_branch(flail, weight=1, max_repeats=2)
        branch.add_branch(ram, weight=1, max_repeats=2)
        chant.follow_up_state = branch
        flail.follow_up_state = branch
        ram.follow_up_state = branch
        return MonsterMoveStateMachine([chant, flail, ram, branch], ram)

    def _war_chant_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(3))

    def _flail_move(self, targets: List[Creature]) -> None:
        for _ in range(2):
            for target in targets:
                self.attack(target, self.flail_damage)

    def _ram_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.ram_damage)


class DampCultist(MonsterModel):
    """축축한 광신도 — HP 51~53. INCANTATION 의식+5 → DARK_STRIKE 1딜 반복."""
    monster_id = "damp_cultist"
    title = "Damp Cultist"

    @property
    def min_initial_hp(self) -> int:
        return 51

    @property
    def max_initial_hp(self) -> int:
        return 53

    @property
    def dark_strike_damage(self) -> int:
        return 1

    @property
    def incantation_amount(self) -> int:
        return 5

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        incant = MoveState("INCANTATION_MOVE", self._incantation_move, Intent(IntentType.BUFF))
        strike = MoveState("DARK_STRIKE_MOVE", self._dark_strike_move,
                           Intent(IntentType.ATTACK, damage=self.dark_strike_damage))
        incant.follow_up_state = strike
        strike.follow_up_state = strike
        return MonsterMoveStateMachine([incant, strike], incant)

    def _incantation_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Ritual
        self.apply_power(Ritual(self.incantation_amount))

    def _dark_strike_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.dark_strike_damage)


class Chomper(MonsterModel):
    """쵸퍼 — HP 60~64, 개전 시 Artifact 2.
    CLAMP 8딜×2 ↔ SCREECH Dazed 3장 삽입."""
    monster_id = "chomper"
    title = "Chomper"

    def __init__(self, scream_first: bool = False):
        super().__init__()
        self.scream_first = scream_first

    @property
    def min_initial_hp(self) -> int:
        return 60

    @property
    def max_initial_hp(self) -> int:
        return 64

    @property
    def clamp_damage(self) -> int:
        return 8

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import Artifact
        self.apply_power(Artifact(2))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        clamp = MoveState("CLAMP_MOVE", self._clamp_move,
                          Intent(IntentType.ATTACK, damage=self.clamp_damage, times=2))
        screech = MoveState("SCREECH_MOVE", self._screech_move, Intent(IntentType.STATUS))
        clamp.follow_up_state = screech
        screech.follow_up_state = clamp
        initial = screech if self.scream_first else clamp
        return MonsterMoveStateMachine([clamp, screech], initial)

    def _clamp_move(self, targets: List[Creature]) -> None:
        for _ in range(2):
            for target in targets:
                self.attack(target, self.clamp_damage)

    def _screech_move(self, targets: List[Creature]) -> None:
        self.add_status_to_player_discard("dazed", 3)


class FatGremlin(MonsterModel):
    """뚱보 그렘린 — HP 13~17. 소환 첫 턴 대기 후 도주."""
    monster_id = "fat_gremlin"
    title = "Fat Gremlin"

    @property
    def min_initial_hp(self) -> int:
        return 13

    @property
    def max_initial_hp(self) -> int:
        return 17

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        spawned = MoveState("SPAWNED_MOVE", self._spawned_move, Intent(IntentType.STUN))
        flee = MoveState("FLEE_MOVE", self._flee_move, Intent(IntentType.ESCAPE))
        spawned.follow_up_state = flee
        flee.follow_up_state = flee
        return MonsterMoveStateMachine([spawned, flee], spawned)

    def _spawned_move(self, targets: List[Creature]) -> None:
        pass

    def _flee_move(self, targets: List[Creature]) -> None:
        self.escape()


# ── HP만 확정, 행동은 단순화된 몬스터 (TODO: 디컴파일 행동 이식) ──

class Parafright(MonsterModel):
    """파라프라이트 — HP 21 (행동 단순화)."""
    monster_id = "parafright"
    title = "Parafright"

    @property
    def min_initial_hp(self) -> int:
        return 21

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        atk = MoveState("ATTACK", self._attack_move, Intent(IntentType.ATTACK, damage=3))
        atk.follow_up_state = atk
        return MonsterMoveStateMachine([atk], atk)

    def _attack_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, 3)


class EyeWithTeeth(MonsterModel):
    """이빨 달린 눈 — HP 6 (행동 단순화)."""
    monster_id = "eye_with_teeth"
    title = "Eye With Teeth"

    @property
    def min_initial_hp(self) -> int:
        return 6

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        bite = MoveState("BITE", self._bite_move, Intent(IntentType.ATTACK, damage=2))
        bite.follow_up_state = bite
        return MonsterMoveStateMachine([bite], bite)

    def _bite_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, 2)


class BattleFriendV1(MonsterModel):
    """전투 친구 V1 — HP 75 (테스트 지원, 행동 단순화)."""
    monster_id = "battle_friend_v1"
    title = "Battle Friend V1"

    @property
    def min_initial_hp(self) -> int:
        return 75

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        support = MoveState("SUPPORT", self._support_move, Intent(IntentType.BUFF))
        atk = MoveState("ATTACK", self._attack_move, Intent(IntentType.ATTACK, damage=8))
        support.follow_up_state = atk
        atk.follow_up_state = support
        return MonsterMoveStateMachine([support, atk], support)

    def _support_move(self, targets: List[Creature]) -> None:
        self.gain_block(10)

    def _attack_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, 8)


class BattleFriendV2(MonsterModel):
    """전투 친구 V2 — HP 150 (테스트 지원, 행동 단순화)."""
    monster_id = "battle_friend_v2"
    title = "Battle Friend V2"

    @property
    def min_initial_hp(self) -> int:
        return 150

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        support = MoveState("SUPPORT", self._support_move, Intent(IntentType.BUFF))
        atk = MoveState("ATTACK", self._attack_move, Intent(IntentType.ATTACK, damage=16))
        support.follow_up_state = atk
        atk.follow_up_state = support
        return MonsterMoveStateMachine([support, atk], support)

    def _support_move(self, targets: List[Creature]) -> None:
        self.gain_block(20)

    def _attack_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, 16)


MONSTER_REGISTRY = {
    "big_dummy": BigDummy,
    "single_attack": SingleAttackMoveMonster,
    "multi_attack": MultiAttackMoveMonster,
    "twig_slime_s": TwigSlimeS,
    "twig_slime_m": TwigSlimeM,
    "stabbot": Stabbot,
    "zapbot": Zapbot,
    "guardbot": Guardbot,
    "axe_ruby_raider": AxeRubyRaider,
    "flail_knight": FlailKnight,
    "damp_cultist": DampCultist,
    "chomper": Chomper,
    "fat_gremlin": FatGremlin,
    "parafright": Parafright,
    "eye_with_teeth": EyeWithTeeth,
    "battle_friend_v1": BattleFriendV1,
    "battle_friend_v2": BattleFriendV2,
}


def create_monster(monster_id: str) -> Optional[MonsterModel]:
    """몬스터 생성."""
    cls = MONSTER_REGISTRY.get(monster_id)
    return cls() if cls else None
