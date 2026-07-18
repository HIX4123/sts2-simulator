"""
STS2 추가 몬스터 — 디컴파일 Models.Monsters.* 이식 (Phase 6h / Batch 7b, 5종).
DevotedSculptor, KinPriest, Toadpole, SludgeSpinner, HauntedShip.
모든 수치는 Ascension 미적용 기본값 (AscensionHelper.GetValueIfAscension(..., tough, normal)의
normal/마지막 인자를 사용).
"""
from __future__ import annotations
from typing import List

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    MonsterModel, MonsterMoveStateMachine, MoveState, RandomBranchState,
    Intent, IntentType, MONSTER_REGISTRY,
)


class DevotedSculptor(MonsterModel):
    """헌신적인 조각가 — HP 162.
    FORBIDDEN_INCANTATION_MOVE(의식+9, 자신) 1회 → SAVAGE_MOVE(12딜) 반복."""
    monster_id = "devoted_sculptor"
    title = "Devoted Sculptor"

    @property
    def min_initial_hp(self) -> int:
        return 162

    @property
    def savage_damage(self) -> int:
        return 12

    @property
    def ritual_gain(self) -> int:
        return 9

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        incant = MoveState("FORBIDDEN_INCANTATION_MOVE", self._forbidden_incantation_move,
                           Intent(IntentType.BUFF))
        savage = MoveState("SAVAGE_MOVE", self._savage_move,
                           Intent(IntentType.ATTACK, damage=self.savage_damage))
        incant.follow_up_state = savage
        savage.follow_up_state = savage
        return MonsterMoveStateMachine([incant, savage], incant)

    def _forbidden_incantation_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Ritual
        self.apply_power(Ritual(self.ritual_gain))

    def _savage_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.savage_damage)


class KinPriest(MonsterModel):
    """킨 사제 — HP 190.
    ORB_OF_FRAILTY_MOVE(8딜+허약1) → ORB_OF_WEAKNESS_MOVE(8딜+약화1) →
    BEAM_MOVE(3딜×3) → RITUAL_MOVE(힘+2, 자신) 순환.

    원본 AfterDeath는 함께 등장하는 KinFollower 몬스터가 전멸했을 때 음악
    파라미터/대사만 트리거하는 연출 훅으로, 이 프로젝트에는 KinFollower가
    이식되어 있지 않고 전투 수치에도 영향이 없어 이식하지 않는다."""
    monster_id = "kin_priest"
    title = "Kin Priest"

    @property
    def min_initial_hp(self) -> int:
        return 190

    @property
    def orb_of_frailty_damage(self) -> int:
        return 8

    @property
    def orb_of_weakness_damage(self) -> int:
        return 8

    @property
    def beam_damage(self) -> int:
        return 3

    @property
    def ritual_strength(self) -> int:
        return 2

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        frailty = MoveState("ORB_OF_FRAILTY_MOVE", self._orb_of_frailty_move,
                            Intent(IntentType.ATTACK_DEBUFF, damage=self.orb_of_frailty_damage))
        weakness = MoveState("ORB_OF_WEAKNESS_MOVE", self._orb_of_weakness_move,
                             Intent(IntentType.ATTACK_DEBUFF, damage=self.orb_of_weakness_damage))
        beam = MoveState("BEAM_MOVE", self._beam_move,
                         Intent(IntentType.ATTACK, damage=self.beam_damage, times=3))
        ritual = MoveState("RITUAL_MOVE", self._ritual_move, Intent(IntentType.BUFF))
        frailty.follow_up_state = weakness
        weakness.follow_up_state = beam
        beam.follow_up_state = ritual
        ritual.follow_up_state = frailty
        return MonsterMoveStateMachine([frailty, weakness, beam, ritual], frailty)

    def _orb_of_frailty_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Frail
        for target in targets:
            self.attack(target, self.orb_of_frailty_damage)
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Frail(1))

    def _orb_of_weakness_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Weak
        for target in targets:
            self.attack(target, self.orb_of_weakness_damage)
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Weak(1))

    def _beam_move(self, targets: List[Creature]) -> None:
        for _ in range(3):
            for target in targets:
                self.attack(target, self.beam_damage)

    def _ritual_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(self.ritual_strength))


class Toadpole(MonsterModel):
    """두꺼비 올챙이 — HP 21~25.
    ConditionalBranchState("INIT_MOVE")로 슬롯 위치(IsFront)에 따라 초기 행동이
    갈리는 패턴 (Chomper의 scream_first와 동일하게 생성자 파라미터로 인코딩).
    WHIRL_MOVE(7딜) → SPIKEN_MOVE(자신 가시+2) → SPIKE_SPIT_MOVE(자신 가시-2 소모
    후 3딜×3) → WHIRL_MOVE 순환. is_front=True면 SPIKEN_MOVE부터 시작."""
    monster_id = "toadpole"
    title = "Toadpole"

    def __init__(self, is_front: bool = False):
        super().__init__()
        self.is_front = is_front

    @property
    def min_initial_hp(self) -> int:
        return 21

    @property
    def max_initial_hp(self) -> int:
        return 25

    @property
    def spike_spit_damage(self) -> int:
        return 3

    @property
    def whirl_damage(self) -> int:
        return 7

    @property
    def spiken_amount(self) -> int:
        return 2

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        spike_spit = MoveState("SPIKE_SPIT_MOVE", self._spike_spit_move,
                               Intent(IntentType.ATTACK, damage=self.spike_spit_damage, times=3))
        whirl = MoveState("WHIRL_MOVE", self._whirl_move,
                          Intent(IntentType.ATTACK, damage=self.whirl_damage))
        spiken = MoveState("SPIKEN_MOVE", self._spiken_move, Intent(IntentType.BUFF))
        whirl.follow_up_state = spiken
        spiken.follow_up_state = spike_spit
        spike_spit.follow_up_state = whirl
        initial = spiken if self.is_front else whirl
        return MonsterMoveStateMachine([spike_spit, whirl, spiken], initial)

    def _spike_spit_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Thorns
        # 원본: SpikeSpit 직전 자신의 ThornsPower를 -SpikenAmount만큼 소모
        # (SPIKEN_MOVE에서 얻은 임시 가시를 되돌림).
        self.apply_power(Thorns(-self.spiken_amount))
        for _ in range(3):
            for target in targets:
                self.attack(target, self.spike_spit_damage)

    def _whirl_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.whirl_damage)

    def _spiken_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Thorns
        self.apply_power(Thorns(self.spiken_amount))


class SludgeSpinner(MonsterModel):
    """슬러지 스피너 — HP 37~39.
    개전 OIL_SPRAY_MOVE(8딜+약화1) 고정 시작 이후, OIL_SPRAY_MOVE / SLAM_MOVE(11딜) /
    RAGE_MOVE(6딜+힘+3, 자신) 3분기 (모두 CannotRepeat — 직전 행동과 같으면 재선택 불가)."""
    monster_id = "sludge_spinner"
    title = "Sludge Spinner"

    @property
    def min_initial_hp(self) -> int:
        return 37

    @property
    def max_initial_hp(self) -> int:
        return 39

    @property
    def oil_spray_damage(self) -> int:
        return 8

    @property
    def slam_damage(self) -> int:
        return 11

    @property
    def rage_damage(self) -> int:
        return 6

    @property
    def rage_strength(self) -> int:
        return 3

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        oil_spray = MoveState("OIL_SPRAY_MOVE", self._oil_spray_move,
                              Intent(IntentType.ATTACK_DEBUFF, damage=self.oil_spray_damage))
        slam = MoveState("SLAM_MOVE", self._slam_move,
                         Intent(IntentType.ATTACK, damage=self.slam_damage))
        rage = MoveState("RAGE_MOVE", self._rage_move,
                         Intent(IntentType.ATTACK_BUFF, damage=self.rage_damage))
        branch = RandomBranchState("RAND")
        branch.add_branch(oil_spray, weight=1, cannot_repeat=True)
        branch.add_branch(slam, weight=1, cannot_repeat=True)
        branch.add_branch(rage, weight=1, cannot_repeat=True)
        oil_spray.follow_up_state = branch
        slam.follow_up_state = branch
        rage.follow_up_state = branch
        return MonsterMoveStateMachine([oil_spray, slam, rage, branch], oil_spray)

    def _oil_spray_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Weak
        for target in targets:
            self.attack(target, self.oil_spray_damage)
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Weak(1))

    def _slam_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.slam_damage)

    def _rage_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        for target in targets:
            self.attack(target, self.rage_damage)
        self.apply_power(Strength(self.rage_strength))


class HauntedShip(MonsterModel):
    """유령선 — HP 63.
    개전 HAUNT_MOVE(약화3 + Dazed 5장 버림더미 삽입) 1회 →
    SWIPE_MOVE(13딜) ↔ STOMP_MOVE(4딜×3) 교대 순환."""
    monster_id = "haunted_ship"
    title = "Haunted Ship"

    @property
    def min_initial_hp(self) -> int:
        return 63

    @property
    def swipe_damage(self) -> int:
        return 13

    @property
    def stomp_damage(self) -> int:
        return 4

    @property
    def haunt_dazed(self) -> int:
        return 5

    @property
    def haunt_weak(self) -> int:
        return 3

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        swipe = MoveState("SWIPE_MOVE", self._swipe_move,
                          Intent(IntentType.ATTACK, damage=self.swipe_damage))
        stomp = MoveState("STOMP_MOVE", self._stomp_move,
                          Intent(IntentType.ATTACK, damage=self.stomp_damage, times=3))
        haunt = MoveState("HAUNT_MOVE", self._haunt_move, Intent(IntentType.STATUS))
        swipe.follow_up_state = stomp
        stomp.follow_up_state = swipe
        haunt.follow_up_state = swipe
        return MonsterMoveStateMachine([swipe, stomp, haunt], haunt)

    def _swipe_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.swipe_damage)

    def _stomp_move(self, targets: List[Creature]) -> None:
        for _ in range(3):
            for target in targets:
                self.attack(target, self.stomp_damage)

    def _haunt_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Weak
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Weak(self.haunt_weak))
        self.add_status_to_player_discard("dazed", self.haunt_dazed)


BATCH7B_MONSTERS = {
    "devoted_sculptor": DevotedSculptor,
    "kin_priest": KinPriest,
    "toadpole": Toadpole,
    "sludge_spinner": SludgeSpinner,
    "haunted_ship": HauntedShip,
}

MONSTER_REGISTRY.update(BATCH7B_MONSTERS)
