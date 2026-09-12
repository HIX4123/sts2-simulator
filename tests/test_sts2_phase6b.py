#!/usr/bin/env python3
"""
STS2 Phase 6b 통합 테스트.
Ironclad 카드 풀 85종 (디컴파일 IroncladCardPool 90종 - 멀티플레이 전용 5종)
+ 신규 파워 16종 + 전투 배선 (X코스트/자동 플레이/비용 수정/소모 훅).
"""
import sts2_sim  # noqa: F401 — CARD_REGISTRY 등록
from sts2_sim.core.combat import CombatState
from sts2_sim.core.policy import GreedyPolicy
from sts2_sim.core.run import RunState
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import create_monster
from sts2_sim.models.sts2_card import CARD_REGISTRY, CardType, Rarity, create_card
from sts2_sim.cards.ironclad import IRONCLAD_POOL_BY_RARITY


def make_combat(monster_ids=("big_dummy",), seed=42):
    player = Player(create_character("ironclad"))
    monsters = [create_monster(mid) for mid in monster_ids]
    combat = CombatState(player, monsters, seed=seed)
    combat.start()
    player.energy = player.max_energy
    return combat, player, monsters


def play(combat, card_id, target=None, upgraded=False, energy=None):
    """카드를 핸드에 넣고 플레이."""
    card = create_card(card_id)
    assert card is not None, f"미등록 카드: {card_id}"
    if upgraded:
        card.upgrade()
    combat.hand.append(card)
    if energy is not None:
        combat.player.energy = energy
    ok = combat.play_card(card, target)
    assert ok, f"{card_id} 플레이 실패"
    return card


def test_pool_registration():
    print("=== 카드 풀 등록 ===\n")
    common = IRONCLAD_POOL_BY_RARITY[Rarity.COMMON]
    uncommon = IRONCLAD_POOL_BY_RARITY[Rarity.UNCOMMON]
    rare = IRONCLAD_POOL_BY_RARITY[Rarity.RARE]
    total = len(common) + len(uncommon) + len(rare)
    # 85종 = 90 - 멀티5 : 보상 풀 79 + Basic 3(strike/defend/bash) + Ancient 2 + 별도 GiantRock
    assert total == 79, f"보상 풀 {total} != 79"
    for cid in common + uncommon + rare + ["break", "corruption", "giant_rock"]:
        assert cid in CARD_REGISTRY, f"레지스트리 누락: {cid}"
        card = create_card(cid)
        assert card.card_type in (CardType.ATTACK, CardType.SKILL, CardType.POWER)
    print(f"✅ 보상 풀 79종 (C{len(common)}/U{len(uncommon)}/R{len(rare)})"
          f" + Ancient 2 + Token 1 등록")

    # 디컴파일 수치 스팟 체크
    spots = {  # card_id: (cost, exhausts)
        "bludgeon": (3, False), "impervious": (2, True), "offering": (0, True),
        "whirlwind": (0, False), "feed": (1, True), "barricade": (3, False),
        "demon_form": (3, False), "anger": (0, False), "fiend_fire": (2, True),
    }
    for cid, (cost, exhausts) in spots.items():
        card = create_card(cid)
        assert card.cost == cost and card.exhausts == exhausts, cid
    assert create_card("whirlwind").x_cost and create_card("cascade").x_cost
    assert create_card("break").rarity == Rarity.ANCIENT
    print("✅ 비용/소모/X코스트/희귀도 스팟 체크 통과")


def test_simple_attacks_and_blocks():
    print("\n=== 단순 공격/블록 수치 ===\n")
    combat, player, (dummy,) = make_combat()
    hp0 = dummy.current_hp
    play(combat, "bludgeon", dummy, energy=3)
    assert hp0 - dummy.current_hp == 32, "Bludgeon 32딜"
    play(combat, "bludgeon", dummy, upgraded=True, energy=3)
    assert hp0 - dummy.current_hp == 32 + 42, "Bludgeon+ 42딜"
    play(combat, "twin_strike", dummy, energy=3)
    assert hp0 - dummy.current_hp == 74 + 10, "TwinStrike 5×2"
    print("✅ Bludgeon 32/42, TwinStrike 5×2")

    play(combat, "impervious", energy=3)
    assert player.block == 30, "Impervious 30블록"
    assert combat.exhaust_pile[-1].card_id == "impervious", "Impervious 소모"
    print("✅ Impervious 30블록 + 소모")


def test_anger_and_rampage():
    print("\n=== Anger 사본 / Rampage 누적 ===\n")
    combat, player, (dummy,) = make_combat()
    play(combat, "anger", dummy, energy=3)
    copies = [c for c in combat.discard_pile if c.card_id == "anger"]
    assert len(copies) == 2, "원본 + 사본"
    print("✅ Anger: 사본이 버림 더미에 추가")

    rampage = create_card("rampage")
    hp0 = dummy.current_hp
    combat.hand.append(rampage)
    combat.play_card(rampage, dummy)
    assert hp0 - dummy.current_hp == 9
    combat.discard_pile.remove(rampage)
    combat.hand.append(rampage)
    player.energy = 3
    combat.play_card(rampage, dummy)
    assert hp0 - dummy.current_hp == 9 + 14, "2회차 9+5=14딜"
    print("✅ Rampage: 플레이마다 +5 누적")


def test_computed_damage():
    print("\n=== 계산형 데미지 (BodySlam/PerfectedStrike/AshenStrike/Bully) ===\n")
    combat, player, (dummy,) = make_combat()
    player.gain_block(12)
    hp0 = dummy.current_hp
    play(combat, "body_slam", dummy, energy=3)
    assert hp0 - dummy.current_hp == 12, "BodySlam = 블록"
    print("✅ BodySlam: 현재 블록만큼 데미지")

    # 스타터 덱: Strike×5 → 6 + 2×(5+자신1) = 18
    hp0 = dummy.current_hp
    play(combat, "perfected_strike", dummy, energy=3)
    assert hp0 - dummy.current_hp == 18, f"PerfectedStrike 18딜"
    print("✅ PerfectedStrike: 6 + 2×Strike 수")

    combat.exhaust_pile.extend([create_card("dazed"), create_card("dazed")])
    hp0 = dummy.current_hp
    play(combat, "ashen_strike", dummy, energy=3)
    # 소모 더미: impervious 등 없음 — 이 전투에서 Dazed 2장만
    dealt = hp0 - dummy.current_hp
    assert dealt == 6 + 3 * 2, f"AshenStrike 12딜 != {dealt}"
    print("✅ AshenStrike: 6 + 3×소모 더미")

    from sts2_sim.models.sts2_power import Vulnerable
    dummy.apply_power(Vulnerable(3))
    hp0 = dummy.current_hp
    play(combat, "bully", dummy, energy=3)
    # 4 + 2×3 = 10, 취약 1.5× = 15
    assert hp0 - dummy.current_hp == 15, "Bully 10딜 ×1.5"
    print("✅ Bully: 4 + 2×취약 수치")


def test_whirlwind_x_cost():
    print("\n=== Whirlwind X코스트 ===\n")
    combat, player, monsters = make_combat(("big_dummy", "big_dummy"))
    hp0 = [m.current_hp for m in monsters]
    play(combat, "whirlwind", energy=3)
    assert player.energy == 0, "에너지 전부 소비"
    for before, m in zip(hp0, monsters):
        assert before - m.current_hp == 5 * 3, "5딜 ×3회 전체"
    print("✅ Whirlwind: 에너지 3 전부 소비, 모든 적에게 5×3")


def test_exhaust_synergy():
    print("\n=== 소모 시너지 (FiendFire + FeelNoPain + DarkEmbrace) ===\n")
    combat, player, (dummy,) = make_combat()
    play(combat, "feel_no_pain", energy=3)   # 소모마다 3블록
    play(combat, "dark_embrace", energy=3)   # 소모마다 1드로우
    combat.hand = [create_card("strike"), create_card("defend")]
    combat.draw_pile = [create_card("strike"), create_card("strike")]
    hp0 = dummy.current_hp
    ff = create_card("fiend_fire")
    combat.hand.append(ff)
    player.energy = 2
    combat.play_card(ff, dummy)
    # 핸드 2장 소모 → 7×2=14딜, FNP 3×2=6블록(+FF 자체 소모 3), DE 드로우 2(+1)
    assert hp0 - dummy.current_hp == 14, "FiendFire 7×2"
    assert player.block == 9, f"FeelNoPain 3×3 (핸드2+자체소모1) != {player.block}"
    assert len(combat.hand) == 2, "DarkEmbrace 드로우 (핸드소모2 → 드로우2, 자체소모 시 더미 소진)"
    print("✅ FiendFire 핸드 소모 → FeelNoPain 블록 + DarkEmbrace 드로우 연쇄")

    combat2, player2, (dummy2,) = make_combat()
    hp0 = dummy2.current_hp
    combat2.exhaust_pile = [create_card("dazed")] * 3
    play(combat2, "pacts_end", energy=3)
    assert hp0 - dummy2.current_hp == 17, "PactsEnd 조건 충족 시 17딜"
    print("✅ PactsEnd: 소모 더미 3장 이상 조건")


def test_power_cards():
    print("\n=== 파워 카드 배선 ===\n")
    combat, player, (dummy,) = make_combat()

    play(combat, "demon_form", energy=3)
    play(combat, "inflame", energy=3)
    assert player.get_power_amount("strength") == 2, "Inflame 힘 +2"
    for p in list(player._powers.values()):
        hook = getattr(p, "on_turn_start", None)
        if hook:
            hook()
    assert player.get_power_amount("strength") == 4, "DemonForm 턴 시작 +2"
    print("✅ DemonForm/Inflame")

    play(combat, "barricade", energy=3)
    player.gain_block(10)
    block_with_juggernaut = player.block
    player.start_of_turn()
    assert player.block == block_with_juggernaut, "Barricade 블록 유지"
    print("✅ Barricade: 턴 시작 블록 유지")

    hp0 = dummy.current_hp
    play(combat, "juggernaut", energy=3)
    player.gain_block(5)
    assert hp0 - dummy.current_hp == 6, "Juggernaut 6딜"
    print("✅ Juggernaut: 블록 획득 시 무작위 적 피해")

    play(combat, "rupture", energy=3)
    str0 = player.get_power_amount("strength")
    play(combat, "bloodletting", energy=3)
    assert player.get_power_amount("strength") == str0 + 1, "Rupture 힘 +1"
    assert player.energy == 3 + 2, "Bloodletting 에너지 +2 (0코스트)"
    print("✅ Rupture + Bloodletting")

    play(combat, "pyre", energy=3)
    assert player.max_energy == 4, "Pyre 최대 에너지 +1"
    print("✅ Pyre: 최대 에너지 +1")


def test_corruption():
    print("\n=== Corruption (Ancient) ===\n")
    combat, player, (dummy,) = make_combat()
    play(combat, "corruption", energy=3)
    defend = create_card("defend")
    combat.hand.append(defend)
    player.energy = 0
    assert combat.get_card_cost(defend) == 0, "스킬 비용 0"
    assert combat.play_card(defend), "0에너지로 스킬 플레이"
    assert defend in combat.exhaust_pile, "플레이한 스킬 소모"
    print("✅ Corruption: 스킬 0코스트 + 소모")


def test_one_two_punch_and_unrelenting():
    print("\n=== OneTwoPunch / Unrelenting ===\n")
    combat, player, (dummy,) = make_combat()
    play(combat, "one_two_punch", energy=3)
    hp0 = dummy.current_hp
    play(combat, "strike", dummy, energy=3)
    assert hp0 - dummy.current_hp == 12, "Strike 2회 발동"
    assert player.get_power_amount("one_two_punch") == 0, "1회 사용 후 제거"
    print("✅ OneTwoPunch: 공격 카드 2회 발동")

    combat2, player2, (dummy2,) = make_combat()
    play(combat2, "unrelenting", dummy2, energy=3)
    assert player2.energy == 1
    strike = create_card("strike")
    combat2.hand.append(strike)
    assert combat2.get_card_cost(strike) == 0, "다음 공격 무료"
    combat2.play_card(strike, dummy2)
    assert player2.energy == 1, "에너지 소비 없음"
    assert player2.get_power_amount("free_attack") == 0
    print("✅ Unrelenting: 다음 공격 카드 비용 0")


def test_stomp_dynamic_cost():
    print("\n=== Stomp 동적 비용 ===\n")
    combat, player, (dummy,) = make_combat()
    stomp = create_card("stomp")
    combat.hand.append(stomp)
    assert combat.get_card_cost(stomp) == 3
    play(combat, "strike", dummy, energy=5)
    play(combat, "strike", dummy)
    assert combat.get_card_cost(stomp) == 1, "공격 2회 후 비용 1"
    print("✅ Stomp: 이번 턴 공격 플레이당 비용 -1")


def test_second_wind_and_vicious():
    print("\n=== SecondWind / Vicious ===\n")
    combat, player, (dummy,) = make_combat()
    combat.hand = [create_card("defend"), create_card("defend"), create_card("strike")]
    sw = create_card("second_wind")
    combat.hand.append(sw)
    player.energy = 1
    combat.play_card(sw)
    assert player.block == 10, "비공격 2장 × 5블록"
    assert len([c for c in combat.hand if c.card_type != CardType.ATTACK]) == 0
    print("✅ SecondWind: 비공격 소모 + 장당 5블록")

    combat2, player2, (dummy2,) = make_combat()
    combat2.draw_pile = [create_card("strike"), create_card("strike")]
    play(combat2, "vicious", energy=3)
    hand0 = len(combat2.hand)
    play(combat2, "thunderclap", dummy2, energy=3)
    assert len(combat2.hand) == hand0 + 1, "취약 부여 → 1드로우"
    print("✅ Vicious: 취약 부여 시 드로우")


def test_temp_strength():
    print("\n=== 임시 힘 (SetupStrike/Mangle) ===\n")
    combat, player, (dummy,) = make_combat()
    hp0 = dummy.current_hp
    play(combat, "setup_strike", dummy, energy=3)
    assert hp0 - dummy.current_hp == 7
    hp0 = dummy.current_hp
    play(combat, "strike", dummy, energy=3)
    assert hp0 - dummy.current_hp == 9, "임시 힘 +3 반영"
    player.tick_powers()
    assert player.get_power_amount("temp_strength") == 0, "턴 종료 제거"
    print("✅ SetupStrike: 이번 턴 힘 +3, 턴 종료 소멸")

    combat2, player2, (dummy2,) = make_combat()
    from sts2_sim.models.sts2_power import Strength
    dummy2.apply_power(Strength(5))
    play(combat2, "mangle", dummy2, energy=3)
    assert dummy2.compute_attack_damage(10) == 10 + 5 - 10, "힘 -10 (임시)"
    dummy2.tick_powers()
    assert dummy2.compute_attack_damage(10) == 15, "몬스터 턴 후 복원"
    print("✅ Mangle: 대상 이번 턴 힘 -10 후 복원")


def test_auto_play():
    print("\n=== 자동 플레이 (Havoc/Cascade/HowlFromBeyond) ===\n")
    combat, player, (dummy,) = make_combat()
    combat.draw_pile = [create_card("strike")]
    hp0 = dummy.current_hp
    play(combat, "havoc", energy=3)
    assert hp0 - dummy.current_hp == 6, "맨 위 Strike 자동 플레이"
    assert combat.exhaust_pile[-1].card_id == "strike", "강제 소모"
    print("✅ Havoc: 드로우 더미 맨 위 자동 플레이 + 소모")

    combat2, player2, (dummy2,) = make_combat()
    combat2.draw_pile = [create_card("strike"), create_card("strike"),
                         create_card("defend")]
    hp0 = dummy2.current_hp
    play(combat2, "cascade", energy=2)
    # X=2: 위에서 defend, strike 순 플레이
    assert hp0 - dummy2.current_hp == 6 and player2.block == 5
    print("✅ Cascade: X장 자동 플레이")

    combat3, player3, (dummy3,) = make_combat()
    howl = create_card("howl_from_beyond")
    hp0 = dummy3.current_hp
    combat3._exhaust_card(howl)
    assert hp0 - dummy3.current_hp == 18, "소모 시 자동 재발동"
    print("✅ HowlFromBeyond: 소모되면 자동 발동")


def test_feed_and_self_damage():
    print("\n=== Feed / 자해 카드 ===\n")
    combat, player, (dummy,) = make_combat()
    dummy._current_hp = 5
    max0 = player.max_hp
    play(combat, "feed", dummy, energy=3)
    assert dummy.is_dead and player.max_hp == max0 + 3, "처치 시 최대 HP +3"
    assert player.character.max_hp == player.max_hp, "캐릭터 동기화"
    print("✅ Feed: 처치 시 최대 HP +3")

    combat2, player2, (dummy2,) = make_combat()
    hp0 = player2.current_hp
    hand0 = len(combat2.hand)
    play(combat2, "offering", energy=0)
    assert player2.current_hp == hp0 - 6 and player2.energy == 2
    assert len(combat2.hand) == hand0 + 3, "3드로우"
    print("✅ Offering: HP -6, 에너지 +2, 3드로우")


def test_reward_pool():
    print("\n=== 보상 풀 (희귀도 가중) ===\n")
    run = RunState("ironclad", seed=7)
    deck0 = len(run.deck)
    for _ in range(30):
        run._card_reward([])
    assert len(run.deck) == deck0 + 30
    new_ids = {c.card_id for c in run.deck[deck0:]}
    pool = set(sum(IRONCLAD_POOL_BY_RARITY.values(), []))
    assert new_ids <= pool, f"풀 밖 카드: {new_ids - pool}"
    assert len(new_ids) >= 10, "다양성"
    print(f"✅ 보상 30장 전부 Ironclad 풀 소속 ({len(new_ids)}종)")


def test_full_combat_with_new_cards():
    print("\n=== 신규 카드 덱 실전 전투 (그리디 정책) ===\n")
    deck_ids = ["strike", "strike", "bash", "defend", "defend",
                "pommel_strike", "thunderclap", "shrug", "iron_wave",
                "inflame", "demon_form", "impervious", "whirlwind",
                "battle_trance", "offering"]
    results = []
    for trial in range(2):
        deck = [create_card(cid) for cid in deck_ids]
        deck = [c for c in deck if c is not None]
        player = Player(create_character("ironclad"), deck=deck)
        monsters = [create_monster("twig_slime_m"), create_monster("twig_slime_s")]
        combat = CombatState(player, monsters, seed=123)
        result = combat.run(GreedyPolicy())
        results.append((result.victory, result.turns, result.player_hp))
    assert results[0] == results[1], "시드 재현성"
    assert results[0][0], "슬라임전 승리"
    print(f"✅ 신규 카드 포함 전투 승리 (턴 {results[0][1]}, HP {results[0][2]}), 시드 재현성 유지")


def test_full_run():
    print("\n=== 확장 풀 런 진행 ===\n")
    wins = 0
    for seed in range(10):
        run = RunState("ironclad", seed=seed)
        result = run.play(policy=GreedyPolicy())
        wins += 1 if result.victory else 0
    print(f"✅ 10시드 런 완료 (완주 {wins}/10) — 크래시 없음")


if __name__ == "__main__":
    test_pool_registration()
    test_simple_attacks_and_blocks()
    test_anger_and_rampage()
    test_computed_damage()
    test_whirlwind_x_cost()
    test_exhaust_synergy()
    test_power_cards()
    test_corruption()
    test_one_two_punch_and_unrelenting()
    test_stomp_dynamic_cost()
    test_second_wind_and_vicious()
    test_temp_strength()
    test_auto_play()
    test_feed_and_self_damage()
    test_reward_pool()
    test_full_combat_with_new_cards()
    test_full_run()
    print("\n" + "=" * 50)
    print("✅ Phase 6b 전체 테스트 통과!")
    print("  ✅ Ironclad 카드 풀 85종 (Common 19 / Uncommon 35 / Rare 25 / Ancient 2 / 기존 3)")
    print("  ✅ 신규 파워 16종 + X코스트/자동 플레이/비용 수정/소모 훅 배선")
    print("  ✅ 희귀도 가중 보상 풀, 그리디 정책 호환, 시드 재현성")
