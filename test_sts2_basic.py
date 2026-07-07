#!/usr/bin/env python3
"""
STS2 기본 구조 테스트.
"""
import asyncio
from sts2_sim.entities.sts2_monster import (
    BigDummy, SingleAttackMoveMonster, MultiAttackMoveMonster,
    TwigSlimeS, Stabbot, AxeRubyRaider,
    Intent, IntentType
)


def test_big_dummy():
    """BigDummy 테스트."""
    dummy = BigDummy()
    assert dummy.title == "Big Dummy"
    assert dummy.max_initial_hp == 9999
    assert dummy.min_initial_hp == 9999
    print(f"✅ BigDummy: {dummy}")


def test_single_attack():
    """SingleAttackMoveMonster 테스트."""
    monster = SingleAttackMoveMonster()
    assert monster.title == "Single Attack Monster"
    assert monster.max_initial_hp == 999
    assert monster.min_initial_hp == 999

    monster.setup_for_combat(None)
    assert monster.current_hp == 999

    intent = monster.get_current_intent()
    assert intent.intent_type == IntentType.ATTACK
    assert intent.damage == 1
    print(f"✅ SingleAttackMoveMonster: {monster}")
    print(f"   Intent: {intent.intent_type.name}, Damage: {intent.damage}")


def test_multi_attack():
    """MultiAttackMoveMonster 테스트."""
    monster = MultiAttackMoveMonster()
    assert monster.title == "Multi Attack Monster"
    assert monster.max_initial_hp == 999

    monster.setup_for_combat(None)

    intent = monster.get_current_intent()
    assert intent.intent_type == IntentType.ATTACK
    assert intent.damage == 2
    assert intent.times == 3
    print(f"✅ MultiAttackMoveMonster: {monster}")
    print(f"   Intent: {intent.intent_type.name}, Damage: {intent.damage}, Times: {intent.times}")


async def test_damage():
    """데미지 처리 테스트."""
    monster = SingleAttackMoveMonster()
    monster.setup_for_combat(None)

    # 데미지 처리
    result = monster.take_damage(100)
    assert result["hp_lost"] == 100
    assert monster.current_hp == 899
    print(f"✅ Damage: took 100, remaining HP: {monster.current_hp}")

    # 블록 처리
    monster.gain_block(50)
    result = monster.take_damage(100)
    assert result["hp_lost"] == 50  # 50은 블록, 50은 HP 손실
    assert monster.current_hp == 849
    print(f"✅ Block: had 50 block, took 100 damage, remaining HP: {monster.current_hp}")


def test_sts2_monsters():
    """실제 STS2 몬스터들 테스트."""
    print("\n📍 STS2 실제 몬스터들:\n")

    # TwigSlimeS
    twig = TwigSlimeS()
    twig.setup_for_combat(None)
    assert twig.max_initial_hp == 11
    intent = twig.get_current_intent()
    assert intent.damage == 4
    print(f"✅ TwigSlimeS: HP {twig.current_hp}, Intent: {intent.intent_type.name}, Damage: {intent.damage}")

    # Stabbot
    stabbot = Stabbot()
    stabbot.setup_for_combat(None)
    assert stabbot.max_initial_hp == 23
    intent = stabbot.get_current_intent()
    assert intent.intent_type == IntentType.ATTACK_DEBUFF
    assert intent.damage == 11
    print(f"✅ Stabbot: HP {stabbot.current_hp}, Intent: {intent.intent_type.name}, Damage: {intent.damage}")

    # AxeRubyRaider - 상태 전환 테스트
    axe = AxeRubyRaider()
    axe.setup_for_combat(None)
    assert axe.max_initial_hp == 22
    intent = axe.get_current_intent()
    assert intent.intent_type == IntentType.ATTACK_DEFEND
    assert intent.damage == 5
    print(f"✅ AxeRubyRaider: HP {axe.current_hp}, Intent: {intent.intent_type.name}, Damage: {intent.damage}")

    # 상태 전환 확인
    move_name_1 = axe._move_state_machine.get_current_move_name()
    assert move_name_1 == "SWING_1"
    axe._move_state_machine.advance_state()
    move_name_2 = axe._move_state_machine.get_current_move_name()
    assert move_name_2 == "SWING_2"
    intent_2 = axe.get_current_intent()
    assert intent_2.intent_type == IntentType.ATTACK_DEFEND
    print(f"   State transition: {move_name_1} → {move_name_2}")

    axe._move_state_machine.advance_state()
    move_name_3 = axe._move_state_machine.get_current_move_name()
    assert move_name_3 == "BIG_SWING"
    intent_3 = axe.get_current_intent()
    assert intent_3.intent_type == IntentType.ATTACK
    assert intent_3.damage == 12
    print(f"   State transition: {move_name_2} → {move_name_3} (Damage: {intent_3.damage})")


def main():
    """메인."""
    print("🧪 STS2 기본 구조 테스트\n")

    test_big_dummy()
    test_single_attack()
    test_multi_attack()

    asyncio.run(test_damage())

    test_sts2_monsters()

    print("\n✅ 모든 테스트 통과!")


if __name__ == "__main__":
    main()
