"""
STS2 추가 몬스터 — 디컴파일 Models.Monsters.* 이식 (Phase 6a, 17종).
멀티 에이전트 이식 + 수치 검증 파이프라인으로 생성 후 수동 대조.
모든 수치는 Ascension 미적용 기본값.
"""
from __future__ import annotations
import random
from typing import TYPE_CHECKING, List, Optional

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    MonsterModel, MonsterMoveStateMachine, MoveState, RandomBranchState,
    Intent, IntentType, MONSTER_REGISTRY,
)

if TYPE_CHECKING:
    from sts2_sim.core.combat import CombatState


class LeafSlimeS(MonsterModel):
    """잎사귀 슬라임 (소) — HP 11~15. TACKLE 3딜 / GOOP Slimed 1장 삽입 (둘 다 연속 불가).

    원본 초기 상태는 RandomBranchState("RAND") — 첫 행동은 전투 rng로
    가중치 분기(양쪽 weight 1, CannotRepeat)를 굴려 결정된다.
    """
    monster_id = "leaf_slime_s"
    title = "Leaf Slime (S)"

    @property
    def min_initial_hp(self) -> int:
        return 11

    @property
    def max_initial_hp(self) -> int:
        return 15

    @property
    def tackle_damage(self) -> int:
        return 3

    @property
    def goop_amount(self) -> int:
        return 1

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        tackle = MoveState("TACKLE_MOVE", self._tackle_move,
                           Intent(IntentType.ATTACK, damage=self.tackle_damage))
        goop = MoveState("GOOP_MOVE", self._goop_move, Intent(IntentType.STATUS))
        branch = RandomBranchState("RAND")
        branch.add_branch(tackle, weight=1, cannot_repeat=True)
        branch.add_branch(goop, weight=1, cannot_repeat=True)
        tackle.follow_up_state = branch
        goop.follow_up_state = branch
        # 원본은 RandomBranchState에서 시작 — 기계 자신의 rng로 분기를 해석해
        # 첫 행동을 결정 (전역 random 모듈 사용 금지)
        machine = MonsterMoveStateMachine([tackle, goop, branch], tackle)
        machine.current_state = branch.resolve(machine.rng, None)
        return machine

    def setup_for_combat(self, state: Optional["CombatState"], rng: Optional[random.Random] = None) -> None:
        # setup_for_combat은 상태 머신 생성 이후에 rng를 주입하므로,
        # 주입된 (시드 가능한) rng로 초기 분기를 재해석한다 —
        # 원본에서 초기 RandomBranchState가 첫 인텐트 롤 시 전투 Rng로 굴려지는 것에 대응.
        super().setup_for_combat(state, rng)
        machine = self._move_state_machine
        branch = next(s for s in machine.states if isinstance(s, RandomBranchState))
        machine.current_state = branch.resolve(machine.rng, None)

    def _tackle_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.tackle_damage)

    def _goop_move(self, targets: List[Creature]) -> None:
        self.add_status_to_player_discard("slimed", self.goop_amount)


class LeafSlimeM(MonsterModel):
    """잎사귀 슬라임 (중) — HP 32~35. CLUMP_SHOT 8딜 ↔ STICKY_SHOT Slimed 2장. 초기 STICKY_SHOT."""
    monster_id = "leaf_slime_m"
    title = "Leaf Slime (M)"

    @property
    def min_initial_hp(self) -> int:
        return 32

    @property
    def max_initial_hp(self) -> int:
        return 35

    @property
    def clump_damage(self) -> int:
        return 8

    @property
    def sticky_amount(self) -> int:
        return 2

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        clump = MoveState("CLUMP_SHOT", self._clump_shot_move,
                          Intent(IntentType.ATTACK, damage=self.clump_damage))
        sticky = MoveState("STICKY_SHOT", self._sticky_shot_move,
                           Intent(IntentType.STATUS))
        clump.follow_up_state = sticky
        sticky.follow_up_state = clump
        return MonsterMoveStateMachine([clump, sticky], sticky)

    def _clump_shot_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.clump_damage)

    def _sticky_shot_move(self, targets: List[Creature]) -> None:
        self.add_status_to_player_discard("slimed", self.sticky_amount)


class CalcifiedCultist(MonsterModel):
    """석회화된 광신도 — HP 38~41. INCANTATION 의식+2 → DARK_STRIKE 9딜 반복."""
    monster_id = "calcified_cultist"
    title = "Calcified Cultist"

    @property
    def min_initial_hp(self) -> int:
        return 38

    @property
    def max_initial_hp(self) -> int:
        return 41

    @property
    def dark_strike_damage(self) -> int:
        return 9

    @property
    def incantation_amount(self) -> int:
        return 2

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


class SpectralKnight(MonsterModel):
    """유령 기사 — HP 93 (승천 97).

    HEX 헥스 2 → SOUL_SLASH 15딜 → RAND 분기.
    원본 분기 (SpectralKnight.cs:52-53):
      AddBranch(slash, 2)            → 가중치 1, CanRepeatXTimes(연속 최대 2회)
      AddBranch(flame, CannotRepeat) → 가중치 1, 연속 불가
    ⇒ 슬래시 후 50/50, 슬래시 2연속이면 강제 SOUL_FLAME(3딜×3),
      SOUL_FLAME 후에는 강제 SOUL_SLASH.
    파이썬 인프라에 CanRepeatXTimes가 없어 동등한 결정적 그래프로 전개:
      slash1 → RAND(slash2 w1 / flame w1), slash2 → flame, flame → slash1.
    """
    monster_id = "spectral_knight"
    title = "Spectral Knight"

    @property
    def min_initial_hp(self) -> int:
        return 93

    @property
    def soul_slash_damage(self) -> int:
        return 15

    @property
    def soul_flame_damage(self) -> int:
        return 3

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        hex_state = MoveState("HEX", self._hex_move, Intent(IntentType.DEBUFF))
        # slash1: 비연속 첫 슬래시 (HEX 후속 및 FLAME 후 강제 슬래시)
        slash1 = MoveState("SOUL_SLASH", self._soul_slash_move,
                           Intent(IntentType.ATTACK, damage=self.soul_slash_damage))
        # slash2: 2연속째 슬래시 (원본 CanRepeatXTimes maxTimes=2의 전개)
        slash2 = MoveState("SOUL_SLASH", self._soul_slash_move,
                           Intent(IntentType.ATTACK, damage=self.soul_slash_damage))
        flame = MoveState("SOUL_FLAME", self._soul_flame_move,
                          Intent(IntentType.ATTACK, damage=self.soul_flame_damage, times=3))
        branch = RandomBranchState("RAND")
        hex_state.follow_up_state = slash1
        slash1.follow_up_state = branch
        # 원본: 슬래시 1회 시점에서 slash/flame 가중치 각 1 → 50/50
        branch.add_branch(slash2, weight=1)
        branch.add_branch(flame, weight=1)
        # 슬래시 2연속 후 slash 가중치 0 → 강제 FLAME (CanRepeatXTimes 2)
        slash2.follow_up_state = flame
        # FLAME 후 flame 가중치 0 → 강제 SLASH (CannotRepeat)
        flame.follow_up_state = slash1
        return MonsterMoveStateMachine([hex_state, slash1, slash2, flame, branch], hex_state)

    def _hex_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import HexPower
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(HexPower(2))

    def _soul_slash_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.soul_slash_damage)

    def _soul_flame_move(self, targets: List[Creature]) -> None:
        for _ in range(3):
            for target in targets:
                self.attack(target, self.soul_flame_damage)


class MagiKnight(MonsterModel):
    """마법 기사 — HP 82. POWER_SHIELD 6딜+5블록 → DAMPEN 디버프 → (RAM 10딜 → PREP 5블록 → BOMB 35딜) 순환."""
    monster_id = "magi_knight"
    title = "Magi Knight"

    @property
    def min_initial_hp(self) -> int:
        return 82

    @property
    def power_shield_damage(self) -> int:
        return 6

    @property
    def power_shield_block(self) -> int:
        return 5

    @property
    def spear_damage(self) -> int:
        return 10

    @property
    def bomb_damage(self) -> int:
        return 35

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        shield = MoveState("POWER_SHIELD_MOVE", self._power_shield_move,
                           Intent(IntentType.ATTACK_DEFEND, damage=self.power_shield_damage))
        dampen = MoveState("DAMPEN_MOVE", self._dampen_move, Intent(IntentType.DEBUFF))
        prep = MoveState("PREP_MOVE", self._prep_move, Intent(IntentType.DEFEND))
        bomb = MoveState("MAGIC_BOMB", self._magic_bomb_move,
                         Intent(IntentType.ATTACK, damage=self.bomb_damage))
        ram = MoveState("RAM_MOVE", self._spear_move,
                        Intent(IntentType.ATTACK, damage=self.spear_damage))
        shield.follow_up_state = dampen
        dampen.follow_up_state = ram
        ram.follow_up_state = prep
        prep.follow_up_state = bomb
        bomb.follow_up_state = ram
        return MonsterMoveStateMachine([shield, dampen, ram, prep, bomb], shield)

    def _power_shield_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.power_shield_damage)
        self.gain_block(self.power_shield_block)

    def _dampen_move(self, targets: List[Creature]) -> None:
        # TODO: DampenPower 미이식 — 플레이어의 강화된 카드를 전투 중 다운그레이드,
        # 시전자(MagiKnight)가 모두 죽으면 해제되어 원래 강화 수준 복구.
        pass

    def _prep_move(self, targets: List[Creature]) -> None:
        self.gain_block(self.power_shield_block)

    def _magic_bomb_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.bomb_damage)

    def _spear_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.spear_damage)


class AssassinRubyRaider(MonsterModel):
    """암살자 루비 약탈자 — HP 18~23, KILLSHOT 10딜 반복."""
    monster_id = "assassin_ruby_raider"
    title = "Assassin Ruby Raider"

    @property
    def min_initial_hp(self) -> int:
        return 18

    @property
    def max_initial_hp(self) -> int:
        return 23

    @property
    def killshot_damage(self) -> int:
        return 10

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        killshot = MoveState("KILLSHOT_MOVE", self._killshot_move,
                             Intent(IntentType.ATTACK, damage=self.killshot_damage))
        killshot.follow_up_state = killshot
        return MonsterMoveStateMachine([killshot], killshot)

    def _killshot_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.killshot_damage)


class BruteRubyRaider(MonsterModel):
    """야만 루비 약탈자 — HP 30~33. BEAT 7딜 ↔ ROAR 힘+3 교대 순환."""
    monster_id = "brute_ruby_raider"
    title = "Brute Ruby Raider"

    @property
    def min_initial_hp(self) -> int:
        return 30

    @property
    def max_initial_hp(self) -> int:
        return 33

    @property
    def beat_damage(self) -> int:
        return 7

    @property
    def roar_strength(self) -> int:
        return 3

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        beat = MoveState("BEAT_MOVE", self._beat_move,
                         Intent(IntentType.ATTACK, damage=self.beat_damage))
        roar = MoveState("ROAR_MOVE", self._roar_move, Intent(IntentType.BUFF))
        beat.follow_up_state = roar
        roar.follow_up_state = beat
        return MonsterMoveStateMachine([beat, roar], beat)

    def _beat_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.beat_damage)

    def _roar_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(self.roar_strength))


class TrackerRubyRaider(MonsterModel):
    """추적자 루비 약탈자 — HP 21~25. TRACK 허약 2 → HOUNDS 1딜×8 반복."""
    monster_id = "tracker_ruby_raider"
    title = "Tracker Ruby Raider"

    @property
    def min_initial_hp(self) -> int:
        return 21

    @property
    def max_initial_hp(self) -> int:
        return 25

    @property
    def hounds_damage(self) -> int:
        return 1

    @property
    def hounds_repeat(self) -> int:
        return 8

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        track = MoveState("TRACK_MOVE", self._track_move, Intent(IntentType.DEBUFF))
        hounds = MoveState("HOUNDS_MOVE", self._hounds_move,
                           Intent(IntentType.ATTACK, damage=self.hounds_damage,
                                  times=self.hounds_repeat))
        track.follow_up_state = hounds
        hounds.follow_up_state = hounds
        return MonsterMoveStateMachine([track, hounds], track)

    def _track_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Frail
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Frail(2))

    def _hounds_move(self, targets: List[Creature]) -> None:
        for _ in range(self.hounds_repeat):
            for target in targets:
                self.attack(target, self.hounds_damage)


class CrossbowRubyRaider(MonsterModel):
    """석궁 루비 약탈자 — HP 18~21. RELOAD 3블록 ↔ FIRE 14딜 순환 (RELOAD 시작)."""
    monster_id = "crossbow_ruby_raider"
    title = "Crossbow Ruby Raider"

    @property
    def min_initial_hp(self) -> int:
        return 18

    @property
    def max_initial_hp(self) -> int:
        return 21

    @property
    def fire_damage(self) -> int:
        return 14

    @property
    def reload_block(self) -> int:
        return 3

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        fire = MoveState("FIRE_MOVE", self._fire_move,
                         Intent(IntentType.ATTACK, damage=self.fire_damage))
        reload = MoveState("RELOAD_MOVE", self._reload_move, Intent(IntentType.DEFEND))
        fire.follow_up_state = reload
        reload.follow_up_state = fire
        return MonsterMoveStateMachine([reload, fire], reload)

    def _fire_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.fire_damage)

    def _reload_move(self, targets: List[Creature]) -> None:
        self.gain_block(self.reload_block)


class SewerClam(MonsterModel):
    """하수도 조개 — HP 56, 개전 시 Plating 8. JET 10딜 → PRESSURIZE 힘+4 순환."""
    monster_id = "sewer_clam"
    title = "Sewer Clam"

    @property
    def min_initial_hp(self) -> int:
        return 56

    @property
    def jet_damage(self) -> int:
        return 10

    @property
    def plating_amount(self) -> int:
        return 8

    def after_added_to_room(self) -> None:
        from sts2_sim.models.sts2_power import Plating
        self.apply_power(Plating(self.plating_amount))

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        pressurize = MoveState("PRESSURIZE_MOVE", self._pressurize_move, Intent(IntentType.BUFF))
        jet = MoveState("JET_MOVE", self._jet_move,
                        Intent(IntentType.ATTACK, damage=self.jet_damage))
        pressurize.follow_up_state = jet
        jet.follow_up_state = pressurize
        return MonsterMoveStateMachine([pressurize, jet], jet)

    def _pressurize_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        self.apply_power(Strength(4))

    def _jet_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.jet_damage)


class SnappingJaxfruit(MonsterModel):
    """스내핑 잭스프루트 — HP 31~33. ENERGY_ORB 3딜 + 자신 힘+2 반복."""
    monster_id = "snapping_jaxfruit"
    title = "Snapping Jaxfruit"

    @property
    def min_initial_hp(self) -> int:
        return 31

    @property
    def max_initial_hp(self) -> int:
        return 33

    @property
    def energy_damage(self) -> int:
        return 3

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        orb = MoveState("ENERGY_ORB_MOVE", self._energy_orb_move,
                        Intent(IntentType.ATTACK_BUFF, damage=self.energy_damage))
        orb.follow_up_state = orb
        return MonsterMoveStateMachine([orb], orb)

    def _energy_orb_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        for target in targets:
            self.attack(target, self.energy_damage)
        self.apply_power(Strength(2))


class SneakyGremlin(MonsterModel):
    """교활한 그렘린 — HP 10~14. 소환 첫 턴 대기(스턴) 후 TACKLE 9딜 반복."""
    monster_id = "sneaky_gremlin"
    title = "Sneaky Gremlin"

    @property
    def min_initial_hp(self) -> int:
        return 10

    @property
    def max_initial_hp(self) -> int:
        return 14

    @property
    def tackle_damage(self) -> int:
        return 9

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        spawned = MoveState("SPAWNED_MOVE", self._spawned_move, Intent(IntentType.STUN))
        tackle = MoveState("TACKLE_MOVE", self._tackle_move,
                           Intent(IntentType.ATTACK, damage=self.tackle_damage))
        spawned.follow_up_state = tackle
        tackle.follow_up_state = tackle
        return MonsterMoveStateMachine([spawned, tackle], spawned)

    def _spawned_move(self, targets: List[Creature]) -> None:
        pass

    def _tackle_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.tackle_damage)


class Noisebot(MonsterModel):
    """노이즈봇 — HP 18~23. NOISE 매 턴 Dazed 2장 삽입 (원본: 버림 1장 + 뽑을 더미 1장)."""
    monster_id = "noisebot"
    title = "Noisebot"

    @property
    def min_initial_hp(self) -> int:
        return 18

    @property
    def max_initial_hp(self) -> int:
        return 23

    @property
    def noise_status_count(self) -> int:
        return 2

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        noise = MoveState("NOISE_MOVE", self._noise_move, Intent(IntentType.STATUS))
        noise.follow_up_state = noise
        return MonsterMoveStateMachine([noise], noise)

    def _noise_move(self, targets: List[Creature]) -> None:
        # 원본: Dazed 1장 → 버림 더미, Dazed 1장 → 뽑을 더미 무작위 위치.
        # 시뮬레이터에는 버림 더미 삽입만 있어 2장 모두 버림 더미로 단순화.
        self.add_status_to_player_discard("dazed", self.noise_status_count)


class LivingShield(MonsterModel):
    """리빙 실드 — HP 55, 개전 시 Rampart 25 (미이식).
    아군 생존 시 SHIELD_SLAM 6딜 반복 / 아군 전멸 시 SMASH 16딜+힘3 반복."""
    monster_id = "living_shield"
    title = "Living Shield"

    @property
    def min_initial_hp(self) -> int:
        return 55

    @property
    def shield_slam_damage(self) -> int:
        return 6

    @property
    def smash_damage(self) -> int:
        return 16

    @property
    def enrage_str(self) -> int:
        return 3

    def after_added_to_room(self) -> None:
        # TODO: RampartPower(25) — 플레이어 턴 시작마다 TurretOperator 아군에게
        # 스택(25)만큼 블록 부여 (파워 미이식)
        pass

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        slam = MoveState("SHIELD_SLAM_MOVE", self._shield_slam_move,
                         Intent(IntentType.ATTACK, damage=self.shield_slam_damage))
        smash = MoveState("SMASH_MOVE", self._smash_move,
                          Intent(IntentType.ATTACK_BUFF, damage=self.smash_damage))

        # 디컴파일 ConditionalBranchState("SHIELD_SLAM_BRANCH") 대응:
        # 아군 생존 시 SHIELD_SLAM, 아군 전멸 시 SMASH (SMASH 이후엔 SMASH 고정 반복)
        monster = self

        class _ShieldSlamBranch(RandomBranchState):
            def resolve(self, rng, last_move_name, history=None):
                return slam if monster._get_ally_count() > 0 else smash

        branch = _ShieldSlamBranch("SHIELD_SLAM_BRANCH")
        branch.add_branch(slam)
        branch.add_branch(smash)
        slam.follow_up_state = branch
        smash.follow_up_state = smash
        return MonsterMoveStateMachine([slam, smash, branch], slam)

    def _shield_slam_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.shield_slam_damage)

    def _smash_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        for target in targets:
            self.attack(target, self.smash_damage)
        self.apply_power(Strength(self.enrage_str))

    def _get_ally_count(self) -> int:
        if self.combat_state is None:
            return 0
        return sum(
            1 for m in getattr(self.combat_state, "monsters", [])
            if m is not self and not m.is_gone
        )


class Mawler(MonsterModel):
    """몰러 — HP 72. 초기 CLAW 4딜×2, 이후 RIP_AND_TEAR 14딜 / ROAR 취약 3 (1회 한정) / CLAW 랜덤 분기."""
    monster_id = "mawler"
    title = "Mawler"

    def __init__(self):
        super().__init__()
        self._roar_branch: Optional[RandomBranchState] = None
        self._roar_state: Optional[MoveState] = None

    @property
    def min_initial_hp(self) -> int:
        return 72

    @property
    def rip_and_tear_damage(self) -> int:
        return 14

    @property
    def claw_damage(self) -> int:
        return 4

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        rip = MoveState("RIP_AND_TEAR_MOVE", self._rip_and_tear_move,
                        Intent(IntentType.ATTACK, damage=self.rip_and_tear_damage))
        roar = MoveState("ROAR_MOVE", self._roar_move, Intent(IntentType.DEBUFF))
        claw = MoveState("CLAW_MOVE", self._claw_move,
                         Intent(IntentType.ATTACK, damage=self.claw_damage, times=2))
        branch = RandomBranchState("RAND")
        branch.add_branch(rip, weight=1, cannot_repeat=True)
        branch.add_branch(roar, weight=1, cannot_repeat=True)  # 원본 UseOnlyOnce — 사용 후 분기에서 제거
        branch.add_branch(claw, weight=1, cannot_repeat=True)
        rip.follow_up_state = branch
        roar.follow_up_state = branch
        claw.follow_up_state = branch
        self._roar_branch = branch
        self._roar_state = roar
        return MonsterMoveStateMachine([rip, roar, claw, branch], claw)

    def _rip_and_tear_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.rip_and_tear_damage)

    def _roar_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Vulnerable
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(Vulnerable(3))
        # MoveRepeatType.UseOnlyOnce: 한 번 사용하면 분기 후보에서 제거
        if self._roar_branch is not None and self._roar_state is not None:
            self._roar_branch.branches = [
                b for b in self._roar_branch.branches if b[0] is not self._roar_state
            ]

    def _claw_move(self, targets: List[Creature]) -> None:
        for _ in range(2):
            for target in targets:
                self.attack(target, self.claw_damage)


class GlobeHead(MonsterModel):
    """글로브 헤드 — HP 148, 개전 시 Galvanic 6 (파워 미이식).
    SHOCKING_SLAP 13딜+허약 2 → THUNDER_STRIKE 6딜×3 → GALVANIC_BURST 16딜+힘+2 순환."""
    monster_id = "globe_head"
    title = "Globe Head"

    @property
    def min_initial_hp(self) -> int:
        return 148

    @property
    def thunder_strike_damage(self) -> int:
        return 6

    @property
    def shocking_slap_damage(self) -> int:
        return 13

    @property
    def galvanic_burst_damage(self) -> int:
        return 16

    def after_added_to_room(self) -> None:
        # TODO: GalvanicPower(6) — 플레이어의 파워 카드에 Galvanized 부여,
        # 해당 카드 사용 시 플레이어가 6 피해 (카드 상태이상 시스템 미이식)
        pass

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        strike = MoveState("THUNDER_STRIKE", self._thunder_strike_move,
                           Intent(IntentType.ATTACK, damage=self.thunder_strike_damage, times=3))
        slap = MoveState("SHOCKING_SLAP", self._shocking_slap_move,
                         Intent(IntentType.ATTACK_DEBUFF, damage=self.shocking_slap_damage))
        burst = MoveState("GALVANIC_BURST", self._galvanic_burst_move,
                          Intent(IntentType.ATTACK_BUFF, damage=self.galvanic_burst_damage))
        slap.follow_up_state = strike
        strike.follow_up_state = burst
        burst.follow_up_state = slap
        return MonsterMoveStateMachine([slap, strike, burst], slap)

    def _thunder_strike_move(self, targets: List[Creature]) -> None:
        for _ in range(3):
            for target in targets:
                self.attack(target, self.thunder_strike_damage)

    def _shocking_slap_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Frail
        for target in targets:
            self.attack(target, self.shocking_slap_damage)
            if hasattr(target, "apply_power"):
                target.apply_power(Frail(2))

    def _galvanic_burst_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Strength
        for target in targets:
            self.attack(target, self.galvanic_burst_damage)
        self.apply_power(Strength(2))


class VineShambler(MonsterModel):
    """덩굴 셈블러 — HP 61. SWIPE 6딜×2 → GRASPING_VINES 8딜+얽힘 1 → CHOMP 16딜 고정 순환."""
    monster_id = "vine_shambler"
    title = "Vine Shambler"

    @property
    def min_initial_hp(self) -> int:
        return 61

    @property
    def grasping_vines_damage(self) -> int:
        return 8

    @property
    def swipe_damage(self) -> int:
        return 6

    @property
    def chomp_damage(self) -> int:
        return 16

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        vines = MoveState("GRASPING_VINES_MOVE", self._grasping_vines_move,
                          Intent(IntentType.ATTACK_DEBUFF, damage=self.grasping_vines_damage))
        swipe = MoveState("SWIPE_MOVE", self._swipe_move,
                          Intent(IntentType.ATTACK, damage=self.swipe_damage, times=2))
        chomp = MoveState("CHOMP_MOVE", self._chomp_move,
                          Intent(IntentType.ATTACK, damage=self.chomp_damage))
        swipe.follow_up_state = vines
        vines.follow_up_state = chomp
        chomp.follow_up_state = swipe
        return MonsterMoveStateMachine([vines, swipe, chomp], swipe)

    def _grasping_vines_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import TangledPower
        for target in targets:
            self.attack(target, self.grasping_vines_damage)
        for target in targets:
            if hasattr(target, "apply_power"):
                target.apply_power(TangledPower(1))

    def _swipe_move(self, targets: List[Creature]) -> None:
        for _ in range(2):
            for target in targets:
                self.attack(target, self.swipe_damage)

    def _chomp_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.chomp_damage)


EXTRA_MONSTERS = {
    "leaf_slime_s": LeafSlimeS,
    "leaf_slime_m": LeafSlimeM,
    "calcified_cultist": CalcifiedCultist,
    "spectral_knight": SpectralKnight,
    "magi_knight": MagiKnight,
    "assassin_ruby_raider": AssassinRubyRaider,
    "brute_ruby_raider": BruteRubyRaider,
    "tracker_ruby_raider": TrackerRubyRaider,
    "crossbow_ruby_raider": CrossbowRubyRaider,
    "sewer_clam": SewerClam,
    "snapping_jaxfruit": SnappingJaxfruit,
    "sneaky_gremlin": SneakyGremlin,
    "noisebot": Noisebot,
    "living_shield": LivingShield,
    "mawler": Mawler,
    "globe_head": GlobeHead,
    "vine_shambler": VineShambler,
}

MONSTER_REGISTRY.update(EXTRA_MONSTERS)
