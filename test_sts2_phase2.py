#!/usr/bin/env python3
"""
STS2 Phase 2 통합 테스트.
렐릭 시스템 + 캐릭터 시스템 + 추가 몬스터.
"""
from sts2_sim.models.sts2_relic import (
    BurningBlood, RingOfTheSnake, Akabeko, Anchor, Cloak,
    create_relic
)
from sts2_sim.entities.sts2_character import (
    Ironclad, Silent, Defect, Necrobinder, Regent, create_character
)
from sts2_sim.entities.sts2_monster import (
    FlailKnight, Zapbot, Guardbot, DampCultist, Chomper, IntentType
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

    # Ring of the Snake — 첫 턴 드로우 +2 (디컴파일 실제 동작)
    rs = RingOfTheSnake()
    rs.on_equip(player)
    assert rs.modify_hand_draw(5, turn=1) == 7
    assert rs.modify_hand_draw(5, turn=2) == 5
    print(f"✅ Ring of the Snake 장착: 첫 턴 드로우 5→7")

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

    # Silent — STS2 실제 덱: 12장 (Strike×5, Defend×5, Neutralize, Survivor)
    silent = Silent()
    deck = silent.get_start_deck()
    relics = silent.get_start_relics()
    assert len(deck) == 12, f"Silent 덱 크기 실패: {len(deck)} != 12"
    assert "ring_of_the_snake" in relics
    assert "neutralize" in deck and "survivor" in deck
    print(f"✅ Silent: {silent}, 덱 크기: {len(deck)}, 렐릭: {relics}")

    # Defect — STS2 실제 덱: Zap/Dualcast, CrackedCore, 오브 슬롯 3
    defect = Defect()
    deck = defect.get_start_deck()
    assert "zap" in deck and "dualcast" in deck
    assert "cracked_core" in defect.get_start_relics()
    assert defect.base_orb_slot_count == 3
    print(f"✅ Defect: {defect}, 오브 슬롯: {defect.base_orb_slot_count}")

    # Necrobinder (STS2 신규) — HP 66, Osty 소환수
    necro = Necrobinder()
    assert necro.max_hp == 66
    assert "bodyguard" in necro.get_start_deck() and "unleash" in necro.get_start_deck()
    assert "bound_phylactery" in necro.get_start_relics()
    print(f"✅ Necrobinder: {necro}")

    # Regent (STS2 신규) — HP 75, Stars 자원
    regent = Regent()
    assert regent.max_hp == 75
    assert "falling_star" in regent.get_start_deck() and "venerate" in regent.get_start_deck()
    assert "divine_right" in regent.get_start_relics()
    print(f"✅ Regent: {regent}")

    # 캐릭터 팩토리
    char = create_character("ironclad")
    assert char is not None and char.name == "Ironclad"
    print(f"✅ 캐릭터 팩토리: ironclad → {char}")

    # 모든 캐릭터 (실제 STS2 로스터 — Watcher 없음)
    expected_deck_sizes = {"ironclad": 10, "silent": 12, "defect": 10, "necrobinder": 10, "regent": 10}
    for char_id, deck_size in expected_deck_sizes.items():
        char = create_character(char_id)
        assert char is not None
        assert len(char.get_start_deck()) == deck_size
    assert create_character("watcher") is None, "Watcher는 STS2에 없어야 함"
    print(f"✅ 실제 STS2 로스터 5개 캐릭터 생성 가능 (Watcher 없음 확인)")


def test_additional_monsters():
    """추가 몬스터 테스트."""
    print("\n=== 추가 몬스터 ===\n")

    # 디컴파일 실제 수치 (Ascension 미적용 기본값)
    monsters = [
        (FlailKnight(), "Flail Knight", 101, 101),
        (Zapbot(), "Zapbot", 18, 23),
        (Guardbot(), "Guardbot", 16, 20),
        (DampCultist(), "Damp Cultist", 51, 53),
        (Chomper(), "Chomper", 60, 64),
    ]

    for monster, name, min_hp, max_hp in monsters:
        monster.setup_for_combat(None)
        assert monster.title == name
        assert monster.min_initial_hp == min_hp
        assert monster.max_initial_hp == max_hp
        assert monster.current_hp == max_hp
        intent = monster.get_current_intent()
        print(f"✅ {name}: HP {monster.current_hp}, Intent: {intent.intent_type.name}")

    print(f"\n✅ 총 {len(monsters)}개 실전 몬스터 (실제 수치)")


def test_monster_combat():
    """몬스터 전투 시뮬레이션."""
    print("\n=== 몬스터 전투 시뮬레이션 ===\n")

    # DampCultist: INCANTATION(의식+5) → DARK_STRIKE(1딜) 반복
    cultist = DampCultist()
    cultist.setup_for_combat(None)

    intent_1 = cultist.get_current_intent()
    assert intent_1.intent_type == IntentType.BUFF
    print(f"Turn 1: DampCultist 인텐트: {intent_1.intent_type.name} (INCANTATION)")

    cultist._move_state_machine.advance_state()
    intent_2 = cultist.get_current_intent()
    assert intent_2.intent_type == IntentType.ATTACK and intent_2.damage == 1
    print(f"Turn 2: DampCultist 인텐트: {intent_2.intent_type.name}, 데미지: {intent_2.damage}")

    cultist._move_state_machine.advance_state()
    intent_3 = cultist.get_current_intent()
    assert intent_3.intent_type == IntentType.ATTACK
    print(f"Turn 3: DampCultist 인텐트: {intent_3.intent_type.name} (DARK_STRIKE 반복)")

    # Ritual 파워 동작: 턴 시작마다 힘 +5
    cultist2 = DampCultist()
    cultist2.setup_for_combat(None)
    cultist2.take_turn([])  # INCANTATION → Ritual(5)
    assert cultist2.get_power_amount("ritual") == 5
    ritual = cultist2._powers["ritual"]
    ritual.on_turn_start()
    assert cultist2.get_power_amount("strength") == 5
    print("✅ DampCultist: Ritual(5) → 턴 시작 힘 +5")

    # Chomper: 개전 시 Artifact 2
    chomper = Chomper()
    chomper.setup_for_combat(None)
    assert chomper.get_power_amount("artifact") == 2
    print("✅ Chomper: 개전 시 Artifact 2 (디버프 2회 무효)")


def main():
    """메인."""
    test_relics()
    test_characters()
    test_additional_monsters()
    test_monster_combat()

    print("\n" + "="*60)
    print("✅ Phase 2 모든 테스트 통과!")
    print("="*60)
    print("\n📊 구현 현황:")
    print("  ✅ 렐릭 시스템 (스타터/Common/Uncommon/Rare/Boss)")
    print("  ✅ 실제 STS2 캐릭터 5종 (Ironclad/Silent/Defect/Necrobinder/Regent)")
    print("  ✅ 실전 몬스터 (디컴파일 수치): FlailKnight/Zapbot/Guardbot/DampCultist/Chomper")
    print("  ✅ Ritual/Artifact 파워 동작 검증")


if __name__ == "__main__":
    main()
