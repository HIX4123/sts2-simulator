"""
STS2 몬스터 배치 10 (Phase 6m) — Waterfall Giant 보스.
모든 수치는 Ascension 미적용 기본값이다.
"""
from __future__ import annotations
from typing import List

from sts2_sim.entities.creature import Creature
from sts2_sim.entities.sts2_monster import (
    Intent, IntentType, MonsterModel, MonsterMoveStateMachine, MoveState,
    MONSTER_REGISTRY,
)


class WaterfallGiant(MonsterModel):
    """워터폴 자이언트 — 첫 사망 뒤 축적한 Steam만큼 폭발하고 최종 사망한다."""
    monster_id = "waterfall_giant"
    title = "Waterfall Giant"

    def __init__(self):
        super().__init__()
        self._current_pressure_gun_damage = self.base_pressure_gun_damage
        self._steam_eruption_damage = 0
        self._about_to_blow_state: MoveState
        self._explode_state: MoveState
        self._pressure_gun_state: MoveState

    @property
    def min_initial_hp(self) -> int:
        return 240

    @property
    def max_initial_hp(self) -> int:
        return 240

    @property
    def siphon_heal(self) -> int:
        return 10

    @property
    def pressurize_amount(self) -> int:
        return 15

    @property
    def stomp_damage(self) -> int:
        return 15

    @property
    def ram_damage(self) -> int:
        return 10

    @property
    def pressure_up_damage(self) -> int:
        return 13

    @property
    def base_pressure_gun_damage(self) -> int:
        return 20

    @property
    def pressure_gun_increase(self) -> int:
        return 5

    @property
    def should_disappear_from_doom(self) -> bool:
        return not self.has_power("steam_eruption")

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        self._current_pressure_gun_damage = self.base_pressure_gun_damage
        self._steam_eruption_damage = 0

        pressurize = MoveState("PRESSURIZE_MOVE", self._pressurize_move,
                              Intent(IntentType.BUFF))
        stomp = MoveState("STOMP_MOVE", self._stomp_move,
                          Intent(IntentType.ATTACK_DEBUFF, damage=self.stomp_damage))
        ram = MoveState("RAM_MOVE", self._ram_move,
                        Intent(IntentType.ATTACK_BUFF, damage=self.ram_damage))
        siphon = MoveState("SIPHON_MOVE", self._siphon_move,
                           Intent(IntentType.BUFF))
        self._pressure_gun_state = MoveState(
            "PRESSURE_GUN_MOVE", self._pressure_gun_move,
            Intent(IntentType.ATTACK_BUFF, damage=self._current_pressure_gun_damage),
        )
        pressure_up = MoveState(
            "PRESSURE_UP_MOVE", self._pressure_up_move,
            Intent(IntentType.ATTACK_BUFF, damage=self.pressure_up_damage),
        )
        self._about_to_blow_state = MoveState(
            "ABOUT_TO_BLOW_MOVE", self._about_to_blow_move,
            Intent(IntentType.STUN),
        )
        self._explode_state = MoveState(
            "EXPLODE_MOVE", self._explode_move,
            Intent(IntentType.ATTACK),
        )

        pressurize.follow_up_state = stomp
        stomp.follow_up_state = ram
        ram.follow_up_state = siphon
        siphon.follow_up_state = self._pressure_gun_state
        self._pressure_gun_state.follow_up_state = pressure_up
        pressure_up.follow_up_state = stomp
        self._about_to_blow_state.follow_up_state = self._explode_state
        self._explode_state.follow_up_state = self._explode_state
        return MonsterMoveStateMachine([
            pressurize, stomp, ram, siphon, self._pressure_gun_state,
            pressure_up, self._about_to_blow_state, self._explode_state,
        ], pressurize)

    def trigger_about_to_blow_state(self) -> None:
        self._max_hp = 999_999_999
        self._current_hp = 999_999_999
        self._move_state_machine.force_current_state(self._about_to_blow_state)

    def _add_steam(self, amount: int = 3) -> None:
        from sts2_sim.models.sts2_power import SteamEruptionPower
        self.apply_power(SteamEruptionPower(amount))

    def _pressurize_move(self, targets: List[Creature]) -> None:
        self._add_steam(self.pressurize_amount)

    def _stomp_move(self, targets: List[Creature]) -> None:
        from sts2_sim.models.sts2_power import Weak
        for target in targets:
            self.attack(target, self.stomp_damage)
            target.apply_power(Weak(1))
        self._add_steam()

    def _ram_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.ram_damage)
        self._add_steam()

    def _siphon_move(self, targets: List[Creature]) -> None:
        self.heal(self.siphon_heal)
        self._add_steam()

    def _pressure_gun_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self._current_pressure_gun_damage)
        self._current_pressure_gun_damage += self.pressure_gun_increase
        self._pressure_gun_state.intent.damage = self._current_pressure_gun_damage
        self._add_steam()

    def _pressure_up_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self.pressure_up_damage)
        self._add_steam()

    def _about_to_blow_move(self, targets: List[Creature]) -> None:
        self._steam_eruption_damage = self.get_power_amount("steam_eruption")
        self.remove_power("steam_eruption")
        self._explode_state.intent.damage = self._steam_eruption_damage

    def _explode_move(self, targets: List[Creature]) -> None:
        for target in targets:
            self.attack(target, self._steam_eruption_damage)
        self._current_hp = 0


MONSTER_REGISTRY["waterfall_giant"] = WaterfallGiant
