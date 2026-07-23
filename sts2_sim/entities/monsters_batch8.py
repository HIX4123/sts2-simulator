"""
STS2 몬스터 배치 8 (Phase 6k) — 디컴파일 Models.Monsters.* 이식 (8종).
MysteriousKnight / Flyconid / ShrinkerBeetle / LouseProgenitor / SpinyToad /
Byrdonis / FossilStalker / SoulFysh(Act1 보스).
모든 수치는 Ascension 미적용 기본값 (AscensionHelper.GetValueIfAscension(..., tough, normal)의
normal/마지막 인자를 사용).
"""
from __future__ import annotations
from typing import List

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    MonsterModel, MonsterMoveStateMachine, MoveState, RandomBranchState,
    Intent, IntentType, FlailKnight, MONSTER_REGISTRY,
)


class MysteriousKnight(FlailKnight):
    """신비한 기사 (이벤트 단일 몬스터) — FlailKnight 상속, HP/무브그래프 동일.
    개전 시 힘+6/도금+6 추가 부여 (원본 MysteriousKnight.cs: FlailKnight 서브클래스,
    AfterAddedToRoom만 오버라이드하여 base 호출 후 버프 추가)."""
    monster_id = "mysterious_knight"
    title = "Mysterious Knight"

    def after_added_to_room(self) -> None:
        super().after_added_to_room()
        from sts2_sim.models.sts2_power import Strength, Plating
        self.apply_power(Strength(6))
        self.apply_power(Plating(6))


class Flyconid(MonsterModel):
    """플라이코니드 — HP 47~49.

    원본(Flyconid.cs) 그래프: VULNERABLE_SPORES_MOVE(취약+2, 무공격) /
    FRAIL_SPORES_MOVE(8딜 + 허약+2) / SMASH_MOVE(11딜) 세 상태가 모두 "RAND"
    분기로 되돌아간다. 원본 AddBranch(state, int, MoveRepeatType) 3-인자 호출의
    "3"/"2"는 weight가 아니라 cooldown 파라미터로 바인딩되므로(디컴파일
    RandomBranchState.cs의 오버로드 결정 — weight는 이 오버로드에서 하드코딩된
    1f) 세 분기(VULNERABLE_SPORES/FRAIL_SPORES/SMASH) 모두 base weight는 동일하게
    1이며, VULNERABLE_SPORES는 최근 3회, FRAIL_SPORES는 최근 2회 무브 이력에
    자신이 없어야 선택 가능(cooldown 게이트) + 전부 CannotRepeat(직전 1회 반복
    금지)이 추가로 걸린다. 최초 행동만 별도의 "INITIAL" 분기(FRAIL_SPORES/SMASH
    동률 1:1, VULNERABLE_SPORES 제외)를 거친다 — RandomBranchState 자체가 초기
    상태이므로 이식 그대로 표현 가능. (적대적 검증에서 3:2:1/2:1 가중치로 오독한
    버그를 발견해 수정)"""
    monster_id = "flyconid"
    title = "Flyconid"

    @property
    def min_initial_hp(self) -> int:
        return 47

    @property
    def max_initial_hp(self) -> int:
        return 49

    @property
    def smash_damage(self) -> int:
        return 11

    @property
    def spore_damage(self) -> int:
        return 8

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        vuln = MoveState("VULNERABLE_SPORES_MOVE", self._vulnerable_spores_move,
                         Intent(IntentType.DEBUFF))
        frail = MoveState("FRAIL_SPORES_MOVE", self._frail_spores_move,
                          Intent(IntentType.ATTACK_DEBUFF, damage=self.spore_damage))
        smash = MoveState("SMASH_MOVE", self._smash_move,
                          Intent(IntentType.ATTACK, damage=self.smash_damage))
        rand = RandomBranchState("RAND")
        initial = RandomBranchState("INITIAL")
        vuln.follow_up_state = rand
        frail.follow_up_state = rand
        smash.follow_up_state = rand
        rand.add_branch(vuln, weight=1, cannot_repeat=True, cooldown=3)
        rand.add_branch(frail, weight=1, cannot_repeat=True, cooldown=2)
        rand.add_branch(smash, weight=1, cannot_repeat=True)
        initial.add_branch(frail, weight=1, cannot_repeat=True, cooldown=2)
        initial.add_branch(smash, weight=1, cannot_repeat=True)
        return MonsterMoveStateMachine([vuln, frail, smash, rand, initial], initial)

    def _vulnerable_spores_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Vulnerable
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Vulnerable(2))

    def _frail_spores_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Frail
        for target in targets:
            self.attack(target, self.spore_damage)
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Frail(2))

    def _smash_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.smash_damage)


class ShrinkerBeetle(MonsterModel):
    """슈링커 비틀 — HP 38~40.

    원본(ShrinkerBeetle.cs) 그래프: SHRINKER_MOVE(개전 1회 한정, 무한 지속 Shrink
    부여) → CHOMP_MOVE ↔ STOMP_MOVE 영구 교대 (Shrink는 딱 한 번만 발동되고
    이후로는 절대 재방문하지 않는다 — moveState.FollowUp만 CHOMP, 나머지 둘은
    서로만 순환)."""
    monster_id = "shrinker_beetle"
    title = "Shrinker Beetle"

    @property
    def min_initial_hp(self) -> int:
        return 38

    @property
    def max_initial_hp(self) -> int:
        return 40

    @property
    def chomp_damage(self) -> int:
        return 7

    @property
    def stomp_damage(self) -> int:
        return 13

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        shrink = MoveState("SHRINKER_MOVE", self._shrink_move, Intent(IntentType.DEBUFF))
        chomp = MoveState("CHOMP_MOVE", self._chomp_move,
                          Intent(IntentType.ATTACK, damage=self.chomp_damage))
        stomp = MoveState("STOMP_MOVE", self._stomp_move,
                          Intent(IntentType.ATTACK, damage=self.stomp_damage))
        shrink.follow_up_state = chomp
        chomp.follow_up_state = stomp
        stomp.follow_up_state = chomp
        return MonsterMoveStateMachine([shrink, chomp, stomp], shrink)

    def _shrink_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import ShrinkPower
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(ShrinkPower(-1))

    def _chomp_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.chomp_damage)

    def _stomp_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.stomp_damage)


class LouseProgenitor(MonsterModel):
    """루스 프로제니터 — HP 134~136, 개전 CurlUpPower(14) 부여.

    원본(LouseProgenitor.cs) 그래프: WEB_CANNON_MOVE(초기, 9딜+대상 허약+2) →
    CURL_AND_GROW_MOVE(블록14+힘+5) → POUNCE_MOVE(14딜) → WEB_CANNON_MOVE → ...
    (고정 3순환). Curled 플래그는 연출(우그림/펴짐 애니메이션) 전용이며 전투
    수치에 영향이 없어 미이식."""
    monster_id = "louse_progenitor"
    title = "Louse Progenitor"

    @property
    def min_initial_hp(self) -> int:
        return 134

    @property
    def max_initial_hp(self) -> int:
        return 136

    @property
    def web_damage(self) -> int:
        return 9

    @property
    def pounce_damage(self) -> int:
        return 14

    @property
    def curl_block(self) -> int:
        return 14

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import CurlUpPower
        self.apply_power(CurlUpPower(self.curl_block))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        web = MoveState("WEB_CANNON_MOVE", self._web_move,
                        Intent(IntentType.ATTACK_DEBUFF, damage=self.web_damage))
        curl = MoveState("CURL_AND_GROW_MOVE", self._curl_and_grow_move,
                         Intent(IntentType.DEFEND_BUFF))
        pounce = MoveState("POUNCE_MOVE", self._pounce_move,
                           Intent(IntentType.ATTACK, damage=self.pounce_damage))
        web.follow_up_state = curl
        curl.follow_up_state = pounce
        pounce.follow_up_state = web
        return MonsterMoveStateMachine([web, curl, pounce], web)

    def _web_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Frail
        for target in targets:
            self.attack(target, self.web_damage)
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Frail(2))

    def _curl_and_grow_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        # 원본 CreatureCmd.GainBlock(..., ValueProp.Move, null) — Unpowered 플래그
        # 없음: 파워드 무브 블록이라 Frail/Dexterity 배율 대상 (powered=True, 기본값).
        self.gain_block(self.curl_block)
        self.apply_power(Strength(5))

    def _pounce_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.pounce_damage)


class SpinyToad(MonsterModel):
    """스파이니 토드 — HP 116~119.

    원본(SpinyToad.cs) 그래프: PROTRUDING_SPIKES_MOVE(초기, 자신 가시+5) →
    SPIKE_EXPLOSION_MOVE(23딜 + 자신 가시-5, 순증감 0으로 상쇄) →
    TONGUE_LASH_MOVE(17딜) → PROTRUDING_SPIKES_MOVE → ... (고정 3순환).
    IsSpiny 플래그는 연출(가시 돋음/사라짐) 전용이라 미이식."""
    monster_id = "spiny_toad"
    title = "Spiny Toad"

    @property
    def min_initial_hp(self) -> int:
        return 116

    @property
    def max_initial_hp(self) -> int:
        return 119

    @property
    def lash_damage(self) -> int:
        return 17

    @property
    def explosion_damage(self) -> int:
        return 23

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        spikes = MoveState("PROTRUDING_SPIKES_MOVE", self._spikes_move, Intent(IntentType.BUFF))
        explosion = MoveState("SPIKE_EXPLOSION_MOVE", self._explosion_move,
                              Intent(IntentType.ATTACK, damage=self.explosion_damage))
        lash = MoveState("TONGUE_LASH_MOVE", self._lash_move,
                         Intent(IntentType.ATTACK, damage=self.lash_damage))
        spikes.follow_up_state = explosion
        explosion.follow_up_state = lash
        lash.follow_up_state = spikes
        return MonsterMoveStateMachine([spikes, explosion, lash], spikes)

    def _spikes_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Thorns
        self.apply_power(Thorns(5))

    def _explosion_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Thorns
        for target in targets:
            self.attack(target, self.explosion_damage)
        self.apply_power(Thorns(-5))

    def _lash_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.lash_damage)


class Byrdonis(MonsterModel):
    """버르도니스 (엘리트) — HP 81~84, 개전 TerritorialPower(1) 부여 (자기 턴마다 힘+1).

    원본(Byrdonis.cs) 그래프: SWOOP_MOVE(초기, 17딜) ↔ PECK_MOVE(3딜×3) 영구 교대."""
    monster_id = "byrdonis"
    title = "Byrdonis"

    @property
    def min_initial_hp(self) -> int:
        return 81

    @property
    def max_initial_hp(self) -> int:
        return 84

    @property
    def peck_damage(self) -> int:
        return 3

    @property
    def peck_repeat(self) -> int:
        return 3

    @property
    def swoop_damage(self) -> int:
        return 17

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import TerritorialPower
        self.apply_power(TerritorialPower(1))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        peck = MoveState("PECK_MOVE", self._peck_move,
                         Intent(IntentType.ATTACK, damage=self.peck_damage, times=self.peck_repeat))
        swoop = MoveState("SWOOP_MOVE", self._swoop_move,
                          Intent(IntentType.ATTACK, damage=self.swoop_damage))
        peck.follow_up_state = swoop
        swoop.follow_up_state = peck
        return MonsterMoveStateMachine([peck, swoop], swoop)

    def _peck_move(self, targets: List[Creature]) -> None:
        for _ in range(self.peck_repeat):
            for target in targets:
                self.attack(target, self.peck_damage)

    def _swoop_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.swoop_damage)


class FossilStalker(MonsterModel):
    """포실 스토커 — HP 51~53, 개전 SuckPower(3) 부여 (자신의 파워드 공격이
    적중할 때마다 힘+3).

    원본(FossilStalker.cs) 그래프: LATCH_MOVE(초기, 12딜) → RAND{TACKLE_MOVE(9딜+
    대상 허약+1)/LATCH_MOVE/LASH_MOVE(3딜×2)} 균등(1:1:1) 분기, RAND는 매 행동 후
    재진입. 원본 AddBranch(state, int) 2-인자 호출의 "2"는 weight가 아니라
    maxRepeats로 바인딩되므로(디컴파일 RandomBranchState.cs 오버로드 결정) 세 분기
    모두 base weight는 1이며, 대신 MoveRepeatType.CanRepeatXTimes(2) 규칙 —
    동일 분기가 직전 2회 연속 나왔으면 그 다음엔 제외(3연속 금지, 2연속까지는 허용)
    — 이 걸린다 (적대적 검증 이후 직접 원본 재대조로 발견해 수정: 최초엔 이를
    'CannotRepeat 없음'으로 오독했었다)."""
    monster_id = "fossil_stalker"
    title = "Fossil Stalker"

    @property
    def min_initial_hp(self) -> int:
        return 51

    @property
    def max_initial_hp(self) -> int:
        return 53

    @property
    def tackle_damage(self) -> int:
        return 9

    @property
    def latch_damage(self) -> int:
        return 12

    @property
    def lash_damage(self) -> int:
        return 3

    @property
    def lash_repeat(self) -> int:
        return 2

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import SuckPower
        self.apply_power(SuckPower(3))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        tackle = MoveState("TACKLE_MOVE", self._tackle_move,
                           Intent(IntentType.ATTACK_DEBUFF, damage=self.tackle_damage))
        latch = MoveState("LATCH_MOVE", self._latch_move,
                          Intent(IntentType.ATTACK, damage=self.latch_damage))
        lash = MoveState("LASH_MOVE", self._lash_move,
                         Intent(IntentType.ATTACK, damage=self.lash_damage, times=self.lash_repeat))
        rand = RandomBranchState("RAND")
        tackle.follow_up_state = rand
        latch.follow_up_state = rand
        lash.follow_up_state = rand
        rand.add_branch(latch, weight=1, max_repeats=2)
        rand.add_branch(tackle, weight=1, max_repeats=2)
        rand.add_branch(lash, weight=1, max_repeats=2)
        return MonsterMoveStateMachine([tackle, latch, lash, rand], latch)

    def _tackle_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Frail
        for target in targets:
            self.attack(target, self.tackle_damage)
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Frail(1))

    def _latch_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.latch_damage)

    def _lash_move(self, targets: List[Creature]) -> None:
        for _ in range(self.lash_repeat):
            for target in targets:
                self.attack(target, self.lash_damage)


class SoulFysh(MonsterModel):
    """소울 피시 (Act1 보스) — HP 211 고정.

    원본(SoulFysh.cs) 그래프: BECKON_MOVE(초기, 대상마다 Beckon 카드 뽑을더미
    1장+버림더미 1장 삽입) → DE_GAS_MOVE(16딜) → GAZE_MOVE(7딜 + 대상 버림더미에
    Beckon 1장) → FADE_MOVE(자신 Intangible+2) → SCREAM_MOVE(13딜 + 대상 취약+3)
    → BECKON_MOVE → ... (고정 5순환). IsInvisible 플래그는 연출 전용이라 미이식."""
    monster_id = "soul_fysh"
    title = "Soul Fysh"

    @property
    def min_initial_hp(self) -> int:
        return 211

    @property
    def max_initial_hp(self) -> int:
        return 211

    @property
    def de_gas_damage(self) -> int:
        return 16

    @property
    def scream_damage(self) -> int:
        return 13

    @property
    def gaze_damage(self) -> int:
        return 7

    @property
    def scream_vulnerable(self) -> int:
        return 3

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        beckon = MoveState("BECKON_MOVE", self._beckon_move, Intent(IntentType.STATUS))
        de_gas = MoveState("DE_GAS_MOVE", self._de_gas_move,
                           Intent(IntentType.ATTACK, damage=self.de_gas_damage))
        gaze = MoveState("GAZE_MOVE", self._gaze_move,
                        Intent(IntentType.ATTACK, damage=self.gaze_damage))
        fade = MoveState("FADE_MOVE", self._fade_move, Intent(IntentType.BUFF))
        scream = MoveState("SCREAM_MOVE", self._scream_move,
                           Intent(IntentType.ATTACK_DEBUFF, damage=self.scream_damage))
        beckon.follow_up_state = de_gas
        de_gas.follow_up_state = gaze
        gaze.follow_up_state = fade
        fade.follow_up_state = scream
        scream.follow_up_state = beckon
        return MonsterMoveStateMachine([beckon, de_gas, gaze, fade, scream], beckon)

    def _beckon_move(self, targets: List[Creature]) -> None:
        self.add_status_to_player_draw("beckon", 1)
        self.add_status_to_player_discard("beckon", 1)

    def _de_gas_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.de_gas_damage)

    def _gaze_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.gaze_damage)
        self.add_status_to_player_discard("beckon", 1)

    def _fade_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Intangible
        self.apply_power(Intangible(2))

    def _scream_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Vulnerable
        for target in targets:
            self.attack(target, self.scream_damage)
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Vulnerable(self.scream_vulnerable))


BATCH8_MONSTERS = {
    "mysterious_knight": MysteriousKnight,
    "flyconid": Flyconid,
    "shrinker_beetle": ShrinkerBeetle,
    "louse_progenitor": LouseProgenitor,
    "spiny_toad": SpinyToad,
    "byrdonis": Byrdonis,
    "fossil_stalker": FossilStalker,
    "soul_fysh": SoulFysh,
}

MONSTER_REGISTRY.update(BATCH8_MONSTERS)
