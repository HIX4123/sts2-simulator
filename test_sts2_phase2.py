#!/usr/bin/env python3
"""
STS2 Phase 2 통합 테스트.
렐릭 시스템 + 캐릭터 시스템 + 추가 몬스터.
"""
from sts2_sim.models.sts2_relic import (
    BurningBlood, RingOfSnake, Akabeko, Anchor, Cloak,
    create_relic
)
from sts2_sim.entities.sts2_character import (
    Ironclad, Silent, Defect, Watcher, create_character
)
from sts2_sim.entities.sts2_monster import (
    FlailKnight, Looter, ShelledParasite, GremlinWizard, Cultist
)


class MockCreature:
    """테스트용 생물."""
    def __init__(self, name: str, max_hp: int = 100):
        self.name = name
        self._current_hp = max_hp
        self._max_hp = max_hp
        self._block = 0
        self._relics = {}

    @property
    def current_hp(self) -> int:
        return self._current_hp

    @property
    def max_hp(self) -> int:
        return self._max_hp

    def gain_max_hp(self, amount: int) -> None:
        """최대 HP 증가."""
        self._max_hp += amount

    def heal(self, amount: int) -> None:
        """HP 회복."""
        self._current_hp = min(self._current_hp + amount, self._max_hp)

    def gain_block(self, amount: int) -> None:
        """블록 획득."""
        self._block += max(0, amount)

    def gain_gold(self, amount: int) -> None:
        """골드 획득."""
        pass

    def __repr__(self) -> str:
        return f"{self.name}(HP:{self._current_hp}/{self._max_hp})"


def test_relics():
    """렐릭 시스템 테스트."""
    print("🧪 Phase 2 통합 테스트\n")
    print("=== 렐릭 시스템 ===\n")

    player = MockCreature("Player", max_hp=100)

    # Burning Blood — 전투 승리 시 6 HP 회복
    bb = BurningBlood()
    bb.on_equip(player)
    print(f"✅ BurningBlood 장착: {player}")

    player._current_hp = 50  # 피해 입은 상태
    bb.on_combat_end(victory=True)
    assert player.current_hp == 56, f"Burning Blood 회복 실패: {player.current_hp} != 56"
    print(f"   전투 승리 후 HP 회복: {player}")

    # Ring of Snake
    rs = RingOfSnake()
    rs.on_equip(player)
    print(f"✅ Ring of Snake 장착: {rs}")

    # Anchor — 최대 HP +10
    player2 = MockCreature("Player2", max_hp=100)
    anchor = Anchor()
    anchor.on_equip(player2)
    assert player2.max_hp == 110, f"Anchor HP 증가 실패: {player2.max_hp} != 110"
    print(f"✅ Anchor 장착: 최대 HP {player2.max_hp}")

    # Cloak — 스킬 카드 플레이 시 1 블록
    cloak = Cloak()
    cloak.on_equip(player)
    # 스킬 카드 플레이 시뮬레이션
    from sts2_sim.models.sts2_card import Deflect
    card = Deflect()
    player._block = 0
    cloak.on_card_played(card)
    assert player._block >= 1, f"Cloak 블록 증가 실패"
    print(f"✅ Cloak 장착: 스킬 카드 플레이 시 블록 +1")

    # 렐릭 팩토리
    relic = create_relic("akabeko")
    assert relic is not None and relic.name == "Akabeko"
    print(f"✅ 렐릭 팩토리: akabeko → {relic}")


def test_characters():
    """캐릭터 시스템 테스트."""
    print("\n=== 캐릭터 시스템 ===\n")

    # Ironclad
    ironclad = Ironclad()
    deck = ironclad.get_start_deck()
    relics = ironclad.get_start_relics()
    assert len(deck) == 10, f"Ironclad 덱 크기 실패: {len(deck)} != 10"
    assert "burning_blood" in relics
    print(f"✅ Ironclad: {ironclad}, 덱 크기: {len(deck)}, 렐릭: {relics}")

    # Silent
    silent = Silent()
    deck = silent.get_start_deck()
    relics = silent.get_start_relics()
    assert len(deck) == 10, f"Silent 덱 크기 실패"
    assert "ring_of_snake" in relics
    print(f"✅ Silent: {silent}, 덱 크기: {len(deck)}, 렐릭: {relics}")

    # Defect
    defect = Defect()
    print(f"✅ Defect: {defect}")

    # Watcher
    watcher = Watcher()
    print(f"✅ Watcher: {watcher}")

    # 캐릭터 팩토리
    char = create_character("ironclad")
    assert char is not None and char.name == "Ironclad"
    print(f"✅ 캐릭터 팩토리: ironclad → {char}")

    # 모든 캐릭터
    for char_id in ["ironclad", "silent", "defect", "watcher"]:
        char = create_character(char_id)
        assert char is not None
        assert len(char.get_start_deck()) == 10
    print(f"✅ 모든 캐릭터 생성 가능: 4개")


def test_additional_monsters():
    """추가 몬스터 테스트."""
    print("\n=== 추가 몬스터 ===\n")

    monsters = [
        (FlailKnight(), "Flail Knight", 45, 50),
        (Looter(), "Looter", 38, 42),
        (ShelledParasite(), "Shelled Parasite", 16, 20),
        (GremlinWizard(), "Gremlin Wizard", 28, 32),
        (Cultist(), "Cultist", 48, 55),
    ]

    for monster, name, min_hp, max_hp in monsters:
        monster.setup_for_combat(None)
        assert monster.title == name
        assert monster.min_initial_hp == min_hp
        assert monster.max_initial_hp == max_hp
        assert monster.current_hp == max_hp
        intent = monster.get_current_intent()
        print(f"✅ {name}: HP {monster.current_hp}, Intent: {intent.intent_type.name}")

    print(f"\n✅ 총 {len(monsters)}개 추가 몬스터")


def test_monster_combat():
    """몬스터 전투 시뮬레이션."""
    print("\n=== 몬스터 전투 시뮬레이션 ===\n")

    player = MockCreature("Player", max_hp=100)
    cultist = Cultist()
    cultist.setup_for_combat(None)

    # Cultist 첫 행동 (ritual)
    intent_1 = cultist.get_current_intent()
    print(f"Turn 1: Cultist 인텐트: {intent_1.intent_type.name}")

    # 상태 전환
    cultist._move_state_machine.advance_state()
    intent_2 = cultist.get_current_intent()
    print(f"Turn 2: Cultist 인텐트: {intent_2.intent_type.name}, 데미지: {intent_2.damage}")
    assert intent_2.intent_type.name == "ATTACK"

    cultist._move_state_machine.advance_state()
    intent_3 = cultist.get_current_intent()
    print(f"Turn 3: Cultist 인텐트: {intent_3.intent_type.name} (다시 반복)")

    print("✅ Cultist 상태 전환 정상 작동")


def main():
    """메인."""
    test_relics()
    test_characters()
    test_additional_monsters()
    test_monster_combat()

    print("\n" + "="*60)
    print("✅ Phase 2 모든 테스트 통과!")
    print("="*60)
    print("\n📊 Phase 2 구현 현황:")
    print("  ✅ 렐릭 시스템: 19개 렐릭")
    print("  ✅ 캐릭터 시스템: 4개 캐릭터 (Ironclad, Silent, Defect, Watcher)")
    print("  ✅ 추가 몬스터: 5개 (총 16개)")
    print("  ✅ 캐릭터별 스타트 덱/렐릭 정의")
    print("\n📈 누적 구현:")
    print("  - 몬스터: 16개")
    print("  - 파워: 14개")
    print("  - 카드: 10개")
    print("  - 렐릭: 19개")
    print("  - 캐릭터: 4개")


if __name__ == "__main__":
    main()
