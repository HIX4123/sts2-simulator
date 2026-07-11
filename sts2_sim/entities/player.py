"""
STS2 Player — 전투 중 플레이어 엔티티.
캐릭터(메타)로부터 생성되며 에너지/Stars/Osty/오브 큐/렐릭/덱을 관리한다.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional

from sts2_sim.entities.creature import Creature, Osty
from sts2_sim.models.sts2_orb import OrbQueue
from sts2_sim.models.sts2_card import create_card
from sts2_sim.models.sts2_relic import create_relic

if TYPE_CHECKING:
    from sts2_sim.entities.sts2_character import STS2Character
    from sts2_sim.models.sts2_card import STS2Card
    from sts2_sim.models.sts2_relic import STS2Relic


class Player(Creature):
    """전투 플레이어. 캐릭터의 현재 HP를 이어받는다.

    deck: 런 레벨 덱(카드 인스턴스 리스트). 지정하면 그대로 사용해
    카드 업그레이드 등이 런 전체에 유지된다. 미지정 시 시작 덱 생성.
    """

    def __init__(self, character: "STS2Character", deck: Optional[List["STS2Card"]] = None):
        super().__init__(character.name, character.max_hp)
        self._current_hp = character.current_hp
        self.character = character
        self.max_energy = character.max_energy
        self.energy = 0
        self.stars = 0
        self.osty: Optional[Osty] = None
        self.orb_queue = OrbQueue(character.base_orb_slot_count)

        self.relics: List["STS2Relic"] = []
        for relic_id in character.get_start_relics():
            relic = create_relic(relic_id)
            if relic:
                relic.on_equip(self)
                self.relics.append(relic)

        if deck is not None:
            self.master_deck: List["STS2Card"] = deck
        else:
            self.master_deck = []
            for card_id in character.get_start_deck():
                card = create_card(card_id)
                if card:
                    self.master_deck.append(card)

    def gain_energy(self, amount: int) -> None:
        if self.has_power("no_energy_gain"):  # ExpectAFight 이후 차단
            return
        self.energy += amount

    def gain_stars(self, amount: int) -> None:
        self.stars += amount

    def summon_osty(self, amount: int) -> None:
        """Osty 소환. 생존 중이면 HP 스택 (디컴파일 OstyCmd.Summon 대응)."""
        if self.osty is None or self.osty.is_dead:
            self.osty = Osty(amount)
        else:
            self.osty.gain_summon_hp(amount)

    def sync_to_character(self) -> None:
        """전투 결과 HP를 캐릭터(런 상태)에 반영."""
        self.character.current_hp = self._current_hp
