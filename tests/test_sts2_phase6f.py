#!/usr/bin/env python3
"""
STS2 Phase 6f 통합 테스트.
Regent 카드 풀 82종 (디컴파일 RegentCardPool 90종 - 멀티플레이 전용 4종
[Constellation/HammerTime/Largesse/Plot] - 스타터 4종[Strike/Defend/FallingStar/Venerate])
+ SovereignBlade/MinionStrike/MinionDiveBomb/MinionSacrifice/Debris 토큰
+ 신규 파워 23종 (Stars/Forge/SovereignBlade 시너지, BlackHole, Monologue,
VoidForm, MonarchsGaze 등).
"""
import sts2_sim  # noqa: F401 — CARD_REGISTRY 등록
from sts2_sim.core.combat import CombatState
from sts2_sim.core.policy import GreedyPolicy
from sts2_sim.core.run import RunState
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import create_monster
from sts2_sim.models.sts2_card import CARD_REGISTRY, CardType, Rarity, create_card
from sts2_sim.cards.regent import (
    REGENT_POOL_BY_RARITY, SovereignBlade, _all_pile_cards, _forge,
)


def make_combat(monster_ids=("big_dummy",), seed=42):
    player = Player(create_character("regent"))
    monsters = [create_monster(mid) for mid in monster_ids]
    combat = CombatState(player, monsters, seed=seed)
    combat.start()  # DivineRight — 별 3 획득
    player.energy = player.max_energy
    return combat, player, monsters


def play(combat, card_id, target=None, upgraded=False, energy=6):
    """카드를 손패에 넣고 플레이 (기본 에너지 6 리필)."""
    card = create_card(card_id)
    assert card is not None, f"미등록 카드: {card_id}"
    if upgraded:
        card.upgrade()
    combat.hand.append(card)
    if energy is not None:
        combat.player.energy = energy
    ok = combat.play_card(card, target)
    assert ok, f"{card_id} 플레이 실패 (에너지 {combat.player.energy}, 별 {combat.player.stars})"
    return card


def _enemy(combat):
    return combat.alive_enemies[0]


# ══════════════════════════════════════════

def test_pool_registration():
    print("=== 카드 풀 등록 ===\n")
    common = REGENT_POOL_BY_RARITY[Rarity.COMMON]
    uncommon = REGENT_POOL_BY_RARITY[Rarity.UNCOMMON]
    rare = REGENT_POOL_BY_RARITY[Rarity.RARE]
    assert len(common) == 20, len(common)
    assert len(uncommon) == 35, len(uncommon)
    assert len(rare) == 25, len(rare)
    for cid in ("sovereign_blade", "minion_strike", "minion_dive_bomb",
                "minion_sacrifice", "debris", "meteor_shower", "the_sealed_throne"):
        assert cid in CARD_REGISTRY, cid
    # 멀티플레이 전용 4종 미등록
    for cid in ("constellation", "hammer_time", "largesse", "plot"):
        assert cid not in CARD_REGISTRY, f"멀티 전용 등록됨: {cid}"
    # Ancient는 보상 풀 제외
    assert "meteor_shower" not in (common + uncommon + rare)
    assert "the_sealed_throne" not in (common + uncommon + rare)
    print(f"✅ 보상 풀 80종 (C{len(common)}/U{len(uncommon)}/R{len(rare)})"
          f" + Ancient 2 + 토큰 5 등록, 멀티 4종 제외")


def test_stars_resource_and_divine_right():
    print("\n=== Stars 자원 & DivineRight ===\n")
    combat, player, _ = make_combat()
    assert player.stars == 3, player.stars  # DivineRight 전투 시작 +3
    play(combat, "gather_light")  # 8블록 + 별 1
    assert player.stars == 4, player.stars
    play(combat, "cloak_of_stars")  # 0코스트/별 1 소모
    assert player.stars == 3, player.stars
    print("✅ DivineRight +3 / 별 획득·소모 정상")


def test_forge_creates_and_stacks():
    print("\n=== Forge: 생성/누적/소모 더미 강화 ===\n")
    combat, player, _ = make_combat()
    assert not any(isinstance(c, SovereignBlade) for c in _all_pile_cards(combat))
    _forge(player, combat, 5)
    blades = [c for c in combat.hand if isinstance(c, SovereignBlade)]
    assert len(blades) == 1, len(blades)
    blade = blades[0]
    assert blade._forged_damage == 5, blade._forged_damage
    _forge(player, combat, 3)  # 소모되지 않은 블레이드 존재 → 생성 없이 누적
    assert blade._forged_damage == 8, blade._forged_damage
    combat.hand.remove(blade)
    combat.exhaust_pile.append(blade)  # 소모된 것으로 시뮬레이션
    _forge(player, combat, 2)  # 소모 더미만 존재 → 새로 생성 + 소모 더미 것도 강화
    assert blade._forged_damage == 10, blade._forged_damage
    new_blades = [c for c in combat.hand if isinstance(c, SovereignBlade)]
    assert len(new_blades) == 1 and new_blades[0]._forged_damage == 2, new_blades
    print("✅ Forge: 신규 생성 / 누적 / 소모 더미 블레이드도 강화")


def test_sovereign_blade_damage_and_parry():
    print("\n=== SovereignBlade 데미지/업그레이드/Parry ===\n")
    combat, player, _ = make_combat()
    blade = create_card("sovereign_blade")
    assert blade.cost == 2 and blade.retains is True
    blade.upgrade()
    assert blade.cost == 1
    combat.hand.append(blade)
    combat.player.energy = 6
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    combat.play_card(blade, enemy)
    assert h0 - enemy.current_hp == 10, h0 - enemy.current_hp
    assert blade in combat.discard_pile  # Retain은 턴종료 유지일 뿐, 플레이 후엔 버림더미로

    combat2, player2, _ = make_combat()
    play(combat2, "parry")  # ParryP 10
    blade2 = create_card("sovereign_blade")
    combat2.hand.append(blade2)
    combat2.player.energy = 6
    enemy2 = _enemy(combat2)
    b0 = player2.block
    combat2.play_card(blade2, enemy2)
    assert player2.block - b0 == 10, player2.block - b0
    print("✅ SovereignBlade 10딜(+Forge) / 업글 코스트1 / Parry 10블록")


def test_sovereign_blade_seeking_edge_and_conqueror():
    print("\n=== SeekingEdge(전체화)/Conqueror(2배) ===\n")
    combat, player, _ = make_combat(("big_dummy", "big_dummy"))
    play(combat, "seeking_edge")  # SeekingEdgeP + Forge 7 → 블레이드 생성(fd=7)
    e0, e1 = combat.alive_enemies
    h0, h1 = e0.current_hp, e1.current_hp
    blade = [c for c in combat.hand if isinstance(c, SovereignBlade)][0]
    combat.player.energy = 6
    combat.play_card(blade, e0)
    assert h0 - e0.current_hp == 17 and h1 - e1.current_hp == 17, \
        (h0 - e0.current_hp, h1 - e1.current_hp)

    combat2, player2, _ = make_combat()
    enemy = _enemy(combat2)
    play(combat2, "conqueror", target=enemy)  # Forge 3(fd=3) + Conqueror 1
    assert enemy.get_power_amount("conqueror") == 1
    blade2 = [c for c in combat2.hand if isinstance(c, SovereignBlade)][0]
    combat2.player.energy = 6
    h0 = enemy.current_hp
    combat2.play_card(blade2, enemy)
    assert h0 - enemy.current_hp == (10 + 3) * 2, h0 - enemy.current_hp
    cp = enemy._powers["conqueror"]
    cp.on_turn_end()
    assert enemy.get_power_amount("conqueror") == 0 and "conqueror" not in enemy._powers
    print("✅ SeekingEdge 전체 공격 / Conqueror 2배 + 적 턴종료 감소")


def test_sword_sage_replay():
    print("\n=== SwordSage: SovereignBlade Replay ===\n")
    combat, player, _ = make_combat()
    play(combat, "sword_sage")  # SwordSageP(1) — 기존 블레이드 없음
    _forge(player, combat, 0)  # 생성만 (신규 블레이드 → SwordSageP.on_card_generated 적용)
    blade = [c for c in combat.hand if isinstance(c, SovereignBlade)][0]
    assert blade._extra_plays == 1, blade._extra_plays
    combat.player.energy = 6
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    combat.play_card(blade, enemy)
    assert h0 - enemy.current_hp == 20, h0 - enemy.current_hp  # 10딜 × 2회(Replay)
    print("✅ SwordSage: 신규 생성 블레이드에도 Replay 적용 → 2회 발동")


def test_star_next_turn_genesis_sealed_throne():
    print("\n=== StarNextTurn/Genesis/SealedThrone ===\n")
    combat, player, _ = make_combat()
    s0 = player.stars
    play(combat, "hidden_cache")  # 별 1 + 다음 턴 별 3
    assert player.stars == s0 + 1, player.stars
    assert player._powers["star_next_turn"].amount == 3
    combat.notify_player_powers("after_energy_reset")  # 다음 턴 에너지 리셋 시뮬레이션
    assert player.stars == s0 + 1 + 3, player.stars
    assert "star_next_turn" not in player._powers

    combat2, player2, _ = make_combat()
    play(combat2, "genesis")  # 매 턴 별 +2
    s1 = player2.stars
    combat2.notify_player_powers("after_energy_reset")
    assert player2.stars == s1 + 2, player2.stars
    assert "genesis" in player2._powers  # 지속
    combat2.notify_player_powers("after_energy_reset")
    assert player2.stars == s1 + 4, player2.stars

    combat3, player3, _ = make_combat()
    enemy = _enemy(combat3)
    play(combat3, "the_sealed_throne")  # 코스트1/별3 — 자기 자신은 미발동
    assert player3.stars == 0, player3.stars
    play(combat3, "strike", target=enemy)  # 이후 카드 → 별 +1
    assert player3.stars == 1, player3.stars
    print("✅ StarNextTurn(1회+제거) / Genesis(지속) / SealedThrone(자기미발동)")


def test_black_hole():
    print("\n=== BlackHole: 별 소모/획득 시 전체 피해 ===\n")
    combat, player, _ = make_combat()
    play(combat, "black_hole")  # BlackHoleP 3
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    play(combat, "cloak_of_stars")  # 별 1 소모 → 블랙홀 발동
    assert h0 - enemy.current_hp == 3, h0 - enemy.current_hp
    h1 = enemy.current_hp
    play(combat, "hidden_cache")  # 별 획득 → 블랙홀 발동
    assert h1 - enemy.current_hp == 3, h1 - enemy.current_hp
    print("✅ BlackHole: 별 소모/획득 각각 전체 3 피해")


def test_child_of_the_stars():
    print("\n=== ChildOfTheStars: 별 소모마다 블록 ===\n")
    combat, player, _ = make_combat()
    play(combat, "child_of_the_stars")  # amount=2
    b0 = player.block
    play(combat, "cloak_of_stars")  # 별 1 소모 → 블록 +2(선행) + 카드 자체 7블록
    assert player.block - b0 == 9, player.block - b0
    print("✅ ChildOfTheStars: 별 1 소모 → 사전 블록 +2 (+카드 자체 7블록)")


def test_radiate_and_lunar_blast():
    print("\n=== Radiate(별획득 수)/LunarBlast(스킬 수) ===\n")
    combat, player, _ = make_combat()
    combat.stars_gained_this_turn = 0  # DivineRight 집계분 리셋
    play(combat, "hidden_cache")  # 별 획득 1 → stars_gained_this_turn=1
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    play(combat, "radiate")
    assert h0 - enemy.current_hp == 3, h0 - enemy.current_hp

    combat2, player2, _ = make_combat()
    combat2.skills_played_this_turn = 3
    enemy2 = _enemy(combat2)
    h1 = enemy2.current_hp
    play(combat2, "lunar_blast", target=enemy2)
    assert h1 - enemy2.current_hp == 12, h1 - enemy2.current_hp
    print("✅ Radiate 3×1=3 / LunarBlast 4×3=12")


def test_crescent_spear_count():
    print("\n=== CrescentSpear: 별 카드 수 집계(+자신) ===\n")
    combat, player, _ = make_combat()
    combat.draw_pile = [create_card("cloak_of_stars"), create_card("cloak_of_stars")]
    combat.discard_pile = []
    combat.exhaust_pile = []
    combat.hand = []
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    play(combat, "crescent_spear", target=enemy)  # 8 + 2×(2+1)=14
    assert h0 - enemy.current_hp == 14, h0 - enemy.current_hp
    print("✅ CrescentSpear: 별카드 2장(+자신 1) → 8+2×3=14")


def test_beat_into_shape_forge():
    print("\n=== BeatIntoShape: 대상 피격 수 기반 Forge ===\n")
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    play(combat, "beat_into_shape", target=enemy)  # 5딜, 이전 히트 0회 → Forge 5
    blade = [c for c in _all_pile_cards(combat) if isinstance(c, SovereignBlade)][0]
    assert blade._forged_damage == 5, blade._forged_damage
    play(combat, "beat_into_shape", target=enemy)  # 이전 히트 1회 → Forge 5+5×1=10
    assert blade._forged_damage == 15, blade._forged_damage
    print("✅ BeatIntoShape: 1회차 Forge5 / 2회차(이전 1히트) Forge+10=15")


def test_supermassive_scaling():
    print("\n=== Supermassive: 생성 카드 수 스케일 ===\n")
    combat, player, _ = make_combat()
    combat.generate_card("debris", count=2, to="discard")
    assert combat.cards_generated_this_combat == 2
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    play(combat, "supermassive", target=enemy)  # 5+3×2=11
    assert h0 - enemy.current_hp == 11, h0 - enemy.current_hp
    print("✅ Supermassive: 생성 2장 → 5+3×2=11")


def test_stardust_x_cost():
    print("\n=== Stardust: 별 X코스트 전량 소비 ===\n")
    combat, player, _ = make_combat()
    player.stars = 4
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    play(combat, "stardust", target=enemy)
    assert player.stars == 0, player.stars
    assert h0 - enemy.current_hp == 20, h0 - enemy.current_hp  # 5×4
    print("✅ Stardust: 별 4개 전량 소비 → 5×4=20딜")


def test_heavenly_drill_threshold():
    print("\n=== HeavenlyDrill: X<4 vs X>=4(더블) ===\n")
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    play(combat, "heavenly_drill", target=enemy, energy=3)
    assert h0 - enemy.current_hp == 24, h0 - enemy.current_hp  # 8×3

    combat2, player2, _ = make_combat()
    enemy2 = _enemy(combat2)
    h1 = enemy2.current_hp
    play(combat2, "heavenly_drill", target=enemy2, energy=4)
    assert h1 - enemy2.current_hp == 64, h1 - enemy2.current_hp  # 8×(4×2)
    print("✅ HeavenlyDrill: X=3→24딜 / X=4(더블)→64딜")


def test_kingly_kick_and_punch_on_drawn():
    print("\n=== KinglyKick/KinglyPunch: 드로우 시 강화 ===\n")
    combat, player, _ = make_combat()
    kick = create_card("kingly_kick")
    assert kick._cost_add_this_combat == 0
    kick.on_drawn(combat)
    assert kick._cost_add_this_combat == -1
    assert combat.get_card_cost(kick) == 3, combat.get_card_cost(kick)  # 4-1

    punch = create_card("kingly_punch")
    punch.on_drawn(combat)
    punch.on_drawn(combat)
    assert punch._bonus_damage == 8, punch._bonus_damage
    combat.hand.append(punch)
    combat.player.energy = 6
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    combat.play_card(punch, enemy)
    assert h0 - enemy.current_hp == 16, h0 - enemy.current_hp  # 8+8
    print("✅ KinglyKick 드로우당 코스트-1 / KinglyPunch 드로우당 데미지+4")


def test_make_it_so_return():
    print("\n=== MakeItSo: 스킬 3장마다 손패 복귀 ===\n")
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    mis = play(combat, "make_it_so", target=enemy)  # 6딜, 소모X → 버림더미로
    assert mis in combat.discard_pile
    play(combat, "hidden_cache")
    play(combat, "hidden_cache")
    assert mis in combat.discard_pile, "2장째에 조기 복귀"
    play(combat, "hidden_cache")  # 3번째 스킬 → 복귀
    assert mis in combat.hand, "3장째에 복귀 실패"
    assert mis not in combat.discard_pile
    print("✅ MakeItSo: 스킬 3장 플레이마다 손패 복귀")


def test_make_it_so_full_hand_redirect():
    print("\n=== MakeItSo: 손패 가득 참 → 뽑을더미에서 버림더미로 리다이렉트 ===\n")
    combat, player, _ = make_combat()
    mis = create_card("make_it_so")
    combat.draw_pile.append(mis)  # 뽑을더미에 위치(복귀 시도 대상)
    combat.hand = [create_card("strike") for _ in range(10)]  # 손패 가득
    for _ in range(3):
        play(combat, "hidden_cache")  # 손패에 추가 → 즉시 소모(버림)되어 다시 10장
    assert mis not in combat.draw_pile, "뽑을더미에 그대로 남음(리다이렉트 실패)"
    assert mis in combat.discard_pile, "가득 찬 손패 시 버림더미 리다이렉트 실패"
    assert len(combat.hand) == 10  # 필러 그대로, mis는 손패에 들어가지 않음
    print("✅ MakeItSo: 손패 가득 참 → 뽑을더미에서 버림더미로 리다이렉트")


def test_settle_to_particle_wall_and_shining_strike():
    print("\n=== settle_to: ParticleWall(손패)/ShiningStrike(뽑을더미 맨 위) ===\n")
    combat, player, _ = make_combat()
    pw = play(combat, "particle_wall")  # 별2/9블록, 손패로 귀환
    assert pw in combat.hand and pw not in combat.discard_pile

    combat2, player2, _ = make_combat()
    enemy = _enemy(combat2)
    ss = play(combat2, "shining_strike", target=enemy)  # 8딜+별2, 뽑을더미 맨 위
    assert combat2.draw_pile and combat2.draw_pile[-1] is ss
    print("✅ ParticleWall→손패 / ShiningStrike→뽑을더미 맨 위")


def test_glitterstream_frail_interaction():
    print("\n=== Glitterstream: 이월 블록도 시전 시점 블록 수정자 반영(Frail) ===\n")
    from sts2_sim.models.sts2_power import Frail
    combat, player, _ = make_combat()
    player.apply_power(Frail(2))  # 블록 0.75배
    play(combat, "glitterstream")  # 이월 5 → Frail 반영 시 int(5*0.75)=3
    power = player._powers["block_next_turn"]
    assert power.amount == 3, power.amount
    print("✅ Glitterstream: Frail 보유 시 이월 블록도 0.75배로 미리 반영 (5→3)")


def test_bombardment_pre_play():
    print("\n=== Bombardment: 소모 더미 자동 선플레이 ===\n")
    combat, player, _ = make_combat()
    card = create_card("bombardment")
    combat.exhaust_pile.append(card)
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    card.on_pre_play_phase(combat)
    assert h0 - enemy.current_hp == 18, h0 - enemy.current_hp
    assert card in combat.exhaust_pile  # 다시 소모 더미로
    print("✅ Bombardment: 소모 더미에서 자동 플레이 후 재소모")


def test_i_am_invincible_post_play():
    print("\n=== IAmInvincible: 뽑을더미 맨 위면 자동 후플레이 ===\n")
    combat, player, _ = make_combat()
    card = create_card("i_am_invincible")
    combat.draw_pile.append(card)  # 맨 위(리스트 끝)
    b0 = player.block
    card.on_post_play_phase(combat)
    assert player.block - b0 == 10, player.block - b0
    assert card not in combat.draw_pile
    assert card in combat.discard_pile
    print("✅ IAmInvincible: 뽑을더미 맨 위 → 자동 플레이 후 버림더미")


def test_void_form():
    print("\n=== VoidForm: 매 턴 첫 2장 무료 + 즉시 턴종료 ===\n")
    combat, player, _ = make_combat()
    play(combat, "void_form")  # 코스트3
    power = player._powers["void_form"]
    assert power.amount == 2
    # 이번 턴 할인 차단 (use()가 큰 값으로 설정 + on_card_played가 +1)
    assert power._plays_this_turn >= 999999999, power._plays_this_turn
    assert power._active(combat) is False
    assert combat.end_turn_requested is True

    power.on_turn_start()  # 다음 턴 시작 시뮬레이션
    assert power._plays_this_turn == 0
    c1 = create_card("strike")
    c2 = create_card("defend")
    c3 = create_card("defend")
    assert combat.get_card_cost(c1) == 0
    combat.hand.append(c1)
    combat.player.energy = 6
    combat.play_card(c1, _enemy(combat))
    assert power._plays_this_turn == 1
    assert combat.get_card_cost(c2) == 0
    combat.hand.append(c2)
    combat.play_card(c2, None)
    assert power._plays_this_turn == 2
    assert combat.get_card_cost(c3) == c3.cost  # 3번째부터 정상 비용
    print("✅ VoidForm: 첫 2장 무료(다음 턴부터) / 플레이 시 즉시 턴종료 요청")


def test_tyranny_draw_and_exhaust():
    print("\n=== Tyranny: 드로우+1 & 턴 시작 손패 소모 ===\n")
    combat, player, _ = make_combat()
    play(combat, "tyranny")  # TyrannyP(1)
    power = player._powers["tyranny"]
    assert power.modify_hand_draw(5) == 6
    combat.draw_pile = [create_card("strike") for _ in range(10)]
    combat.hand = []
    n0 = len(combat.exhaust_pile)
    combat.draw_cards(6)
    combat.notify_player_powers("after_hand_draw", combat)
    assert len(combat.hand) == 5, len(combat.hand)  # 6장 드로우 - 1장 소모
    assert len(combat.exhaust_pile) == n0 + 1
    print("✅ Tyranny: 드로우 6 - 소모 1 = 손패 5")


def test_monologue():
    print("\n=== Monologue: 카드마다 힘 누적, 자기 미발동, 턴종료 회수 ===\n")
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    play(combat, "monologue")  # 자기 자신은 미발동
    assert player.get_power_amount("strength") == 0
    play(combat, "strike", target=enemy)
    assert player.get_power_amount("strength") == 1
    play(combat, "strike", target=enemy)
    assert player.get_power_amount("strength") == 2
    player._powers["monologue"].on_turn_end()
    assert player.get_power_amount("strength") == 0
    assert "monologue" not in player._powers
    print("✅ Monologue: 카드마다 힘+1(자기 제외), 턴종료 시 전량 회수")


def test_monarchs_gaze():
    print("\n=== MonarchsGaze: 파워드 공격 명중마다 임시 힘 감소 ===\n")
    combat, player, _ = make_combat()
    play(combat, "monarchs_gaze")  # MonarchsGazeP(1)
    enemy = _enemy(combat)
    play(combat, "strike", target=enemy)
    assert enemy.get_power_amount("temp_strength") == -1, enemy.get_power_amount("temp_strength")
    play(combat, "strike", target=enemy)
    assert enemy.get_power_amount("temp_strength") == -2, enemy.get_power_amount("temp_strength")
    print("✅ MonarchsGaze: 파워드 공격 명중마다 임시 힘 -1씩 누적")


def test_crush_under_and_dying_star_temp_strength():
    print("\n=== CrushUnder/DyingStar: 전체 피해 + 임시 힘 감소 ===\n")
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    play(combat, "crush_under")  # 전체 7딜 + 임시 힘 -1
    assert h0 - enemy.current_hp == 7, h0 - enemy.current_hp
    assert enemy.get_power_amount("temp_strength") == -1

    combat2, player2, _ = make_combat()
    enemy2 = _enemy(combat2)
    ds = create_card("dying_star")
    assert ds.is_ethereal is True
    combat2.hand.append(ds)
    combat2.player.energy = 6
    h1 = enemy2.current_hp
    combat2.play_card(ds, enemy2)
    assert h1 - enemy2.current_hp == 9, h1 - enemy2.current_hp
    assert enemy2.get_power_amount("temp_strength") == -9
    print("✅ CrushUnder 7딜/힘-1 / DyingStar(Ethereal) 9딜/힘-9")


def test_reflect():
    print("\n=== Reflect: 막은 피해 반사 ===\n")
    combat, player, _ = make_combat()
    play(combat, "reflect")  # 별3/15블록 + ReflectP 1
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    player.take_damage(10, source=enemy)
    assert player.block == 5, player.block  # 15 - 10
    assert h0 - enemy.current_hp == 10, h0 - enemy.current_hp  # 막은 10 반사
    reflect_p = player._powers["reflect"]
    reflect_p.on_turn_start()
    assert "reflect" not in player._powers
    print("✅ Reflect: 막은 10 반사 / 내 턴 시작마다 1 감소(0에서 제거)")


def test_knockout_blow_stars_on_kill():
    print("\n=== KnockoutBlow: 처치 시 별 획득 ===\n")
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    enemy._current_hp = 5
    s0 = player.stars
    play(combat, "knockout_blow", target=enemy)
    assert enemy.is_dead
    assert player.stars == s0 + 5, player.stars
    print("✅ KnockoutBlow: 처치 시 별 +5")


def test_royalties_gold():
    print("\n=== Royalties: 전투 승리 시 골드 ===\n")
    combat, player, _ = make_combat()
    play(combat, "royalties")  # RoyaltiesP 30
    g0 = player.character.gold
    combat.notify_player_powers("on_combat_end", True)
    assert player.character.gold == g0 + 30, player.character.gold
    print("✅ Royalties: 승리 시 골드 +30")


def test_foregone_conclusion():
    print("\n=== ForegoneConclusion: 다음 턴 드로우 전 사전 확보 ===\n")
    combat, player, _ = make_combat()
    play(combat, "foregone_conclusion")  # amount=2
    combat.draw_pile = [create_card("strike") for _ in range(5)]
    combat.hand = []
    combat.notify_player_powers("before_hand_draw", combat)
    assert len(combat.hand) == 2, len(combat.hand)
    assert len(combat.draw_pile) == 3, len(combat.draw_pile)
    assert "foregone_conclusion" not in player._powers
    print("✅ ForegoneConclusion: 드로우 전 2장 사전 확보 후 파워 제거")


def test_convergence_retain_hand():
    print("\n=== Convergence: 손패 유지(Ethereal 예외) ===\n")
    combat, player, _ = make_combat()
    play(combat, "convergence")  # RetainHandP(1) + EnergyNextTurn + StarNextTurn
    assert player._powers["retain_hand"].amount == 1
    normal = create_card("strike")
    ethereal = create_card("strike")
    ethereal.is_ethereal = True
    combat.hand = [normal, ethereal]
    combat._discard_hand()
    assert combat.hand == [normal], combat.hand
    assert ethereal in combat.exhaust_pile
    assert "retain_hand" not in player._powers
    print("✅ Convergence: 일반 카드 유지 / Ethereal은 그대로 소모")


def test_transform_cards():
    print("\n=== Begone/Charge/Guards: 카드 변환 ===\n")
    combat, player, _ = make_combat()
    combat.hand = [create_card("strike"), create_card("strike")]
    play(combat, "begone")
    assert len(combat.hand) == 2
    assert sum(1 for c in combat.hand if c.card_id == "minion_strike") == 1

    combat2, player2, _ = make_combat()
    combat2.draw_pile = [create_card("strike") for _ in range(5)]
    play(combat2, "charge")
    assert sum(1 for c in combat2.draw_pile if c.card_id == "minion_dive_bomb") == 2
    assert len(combat2.draw_pile) == 5

    combat3, player3, _ = make_combat()
    combat3.hand = [create_card("strike"), create_card("strike"), create_card("strike")]
    play(combat3, "guards")
    assert len(combat3.hand) == 3
    assert all(c.card_id == "minion_sacrifice" for c in combat3.hand)
    print("✅ Begone(1장)/Charge(2장)/Guards(전체) → 토큰 변환")


def test_guards_generation_hooks():
    print("\n=== Guards: 제자리 변환도 카드 생성 훅 발동 ===\n")
    combat, player, _ = make_combat()
    play(combat, "arsenal")           # ArsenalP 1
    play(combat, "pillar_of_creation")  # PillarOfCreationP 3
    combat.hand = [create_card("strike"), create_card("strike"), create_card("strike")]
    s0 = player.get_power_amount("strength")
    b0 = player.block
    g0 = combat.cards_generated_this_combat
    play(combat, "guards")
    assert player.get_power_amount("strength") == s0 + 3, player.get_power_amount("strength")
    assert player.block == b0 + 9, player.block  # 3장 × Pillar 3
    assert combat.cards_generated_this_combat == g0 + 3, combat.cards_generated_this_combat
    print("✅ Guards: 손패 3장 변환 → Arsenal 힘+3 / Pillar 블록+9 / 생성 카운터+3")


def test_putback_cards():
    print("\n=== CosmicIndifference/Glimmer/PhotonCut: 되돌리기 ===\n")
    combat, player, _ = make_combat()
    combat.discard_pile = [create_card("strike")]
    ci = play(combat, "cosmic_indifference")
    # 버림더미의 strike는 뽑을더미 맨 위로 이동, cosmic_indifference 자신은 플레이 후 버림더미로
    assert combat.discard_pile == [ci], combat.discard_pile
    assert combat.draw_pile and combat.draw_pile[-1].card_id == "strike"

    combat2, player2, _ = make_combat()
    combat2.draw_pile = [create_card("strike") for _ in range(5)]
    combat2.hand = []
    play(combat2, "glimmer")
    assert len(combat2.hand) == 2, len(combat2.hand)  # 3장 드로우 - 1장 되돌림

    combat3, player3, _ = make_combat()
    combat3.draw_pile = [create_card("strike") for _ in range(5)]
    combat3.hand = []
    enemy = _enemy(combat3)
    play(combat3, "photon_cut", target=enemy)
    assert len(combat3.hand) == 0, len(combat3.hand)  # 1장 드로우 - 1장 되돌림
    print("✅ CosmicIndifference/Glimmer/PhotonCut: 카드 되돌리기 정상")


def test_decisions_decisions():
    print("\n=== DecisionsDecisions: 손패 스킬 3회 자동 플레이 ===\n")
    combat, player, _ = make_combat()
    player.stars = 10
    combat.draw_pile = [create_card("know_thy_place") for _ in range(5)]
    combat.hand = []
    enemy = _enemy(combat)
    dd = play(combat, "decisions_decisions")  # 별6, 드로우3 + 무작위 스킬 3회 자동플레이
    # 소모형 스킬(KnowThyPlace)도 원본처럼 소모 더미에서 강제로 3회 재생된다
    assert enemy.get_power_amount("weak") == 3, enemy.get_power_amount("weak")
    assert enemy.get_power_amount("vulnerable") == 3, enemy.get_power_amount("vulnerable")
    # 3회 재생 후 최종적으로 소모 더미에: 자동플레이된 know_thy_place 1장(누적 소모X,
    # 재사용됨) + decisions_decisions 자신 소모 = 2장
    assert set(c.card_id for c in combat.exhaust_pile) == {"know_thy_place", "decisions_decisions"}
    assert len(combat.exhaust_pile) == 2, len(combat.exhaust_pile)
    assert sum(1 for c in combat.hand if c.card_id == "know_thy_place") == 2
    print("✅ DecisionsDecisions: 무작위 스킬 자동 플레이 후 소모 시 중단")


def test_crash_landing_and_generation_hooks():
    print("\n=== CrashLanding + Arsenal/PillarOfCreation 생성 훅 ===\n")
    combat, player, _ = make_combat()
    play(combat, "arsenal")   # ArsenalP 1
    play(combat, "pillar_of_creation")  # PillarOfCreationP 3
    combat.hand = []
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    b0 = player.block
    s0 = player.get_power_amount("strength")
    play(combat, "crash_landing", target=enemy)  # 전체 21딜 + 손패 가득 찰 때까지 Debris
    assert h0 - enemy.current_hp == 21, h0 - enemy.current_hp
    assert len(combat.hand) == 10, len(combat.hand)
    assert player.get_power_amount("strength") == s0 + 10, player.get_power_amount("strength")
    assert player.block == b0 + 30, player.block
    print("✅ CrashLanding: Debris 10장 생성 → Arsenal 힘+10 / Pillar 블록+30")


def test_pale_blue_dot():
    print("\n=== PaleBlueDot: 턴 5장 플레이 시 다음 턴 드로우 ===\n")
    combat, player, _ = make_combat()
    play(combat, "pale_blue_dot")  # amount=1 (플레이 자체가 1번째)
    for _ in range(3):
        play(combat, "strike", target=_enemy(combat))
    assert player.get_power_amount("draw_next_turn") == 0
    play(combat, "strike", target=_enemy(combat))  # 5번째 플레이
    assert player.get_power_amount("draw_next_turn") == 1
    print("✅ PaleBlueDot: 5장째 플레이에서 다음 턴 드로우 +1 발동")


def test_orbit_energy_accumulation():
    print("\n=== Orbit: 에너지 4 누적마다 +1 ===\n")
    combat, player, _ = make_combat()
    play(combat, "orbit")  # OrbitP amount=1
    power = player._powers["orbit"]
    for _ in range(4):
        play(combat, "strike", target=_enemy(combat))  # 코스트 1씩 4회
    assert power._energy_spent == 4, power._energy_spent
    assert power._trigger_count == 1, power._trigger_count
    print("✅ Orbit: 에너지 4 누적 소모 → 트리거 1회")


def test_full_combats_all_cards():
    print("\n=== 전 카드 전투 스모크 (그리디) ===\n")
    pool = (REGENT_POOL_BY_RARITY[Rarity.COMMON]
            + REGENT_POOL_BY_RARITY[Rarity.UNCOMMON]
            + REGENT_POOL_BY_RARITY[Rarity.RARE]
            + ["meteor_shower", "the_sealed_throne",
               "sovereign_blade", "minion_strike", "minion_dive_bomb",
               "minion_sacrifice", "debris"])
    fails = []
    for cid in pool:
        try:
            player = Player(create_character("regent"))
            monsters = [create_monster("big_dummy")]
            combat = CombatState(player, monsters, seed=7)
            combat.start()
            card = create_card(cid)
            combat.player.energy = 6
            combat.player.stars = 20
            combat.hand.append(card)
            tgt = combat.alive_enemies[0] if combat.alive_enemies else None
            combat.play_card(card, tgt)
        except Exception as e:  # noqa: BLE001
            fails.append((cid, repr(e)))
    assert not fails, f"플레이 크래시: {fails[:5]}"
    print(f"✅ 전 카드 {len(pool)}종 개별 플레이 크래시 없음")


def test_greedy_run():
    print("\n=== Regent 그리디 런 (재현성) ===\n")
    r1 = RunState("regent", seed=123).play(policy=GreedyPolicy())
    r2 = RunState("regent", seed=123).play(policy=GreedyPolicy())
    assert r1.floors_cleared == r2.floors_cleared, "재현성 실패"
    assert r1.final_hp == r2.final_hp
    print(f"✅ 시드 123 재현: {r1.floors_cleared}/{r1.total_floors}층, HP {r1.final_hp}")


def main():
    test_pool_registration()
    test_stars_resource_and_divine_right()
    test_forge_creates_and_stacks()
    test_sovereign_blade_damage_and_parry()
    test_sovereign_blade_seeking_edge_and_conqueror()
    test_sword_sage_replay()
    test_star_next_turn_genesis_sealed_throne()
    test_black_hole()
    test_child_of_the_stars()
    test_radiate_and_lunar_blast()
    test_crescent_spear_count()
    test_beat_into_shape_forge()
    test_supermassive_scaling()
    test_stardust_x_cost()
    test_heavenly_drill_threshold()
    test_kingly_kick_and_punch_on_drawn()
    test_make_it_so_return()
    test_make_it_so_full_hand_redirect()
    test_settle_to_particle_wall_and_shining_strike()
    test_glitterstream_frail_interaction()
    test_bombardment_pre_play()
    test_i_am_invincible_post_play()
    test_void_form()
    test_tyranny_draw_and_exhaust()
    test_monologue()
    test_monarchs_gaze()
    test_crush_under_and_dying_star_temp_strength()
    test_reflect()
    test_knockout_blow_stars_on_kill()
    test_royalties_gold()
    test_foregone_conclusion()
    test_convergence_retain_hand()
    test_transform_cards()
    test_guards_generation_hooks()
    test_putback_cards()
    test_decisions_decisions()
    test_crash_landing_and_generation_hooks()
    test_pale_blue_dot()
    test_orbit_energy_accumulation()
    test_full_combats_all_cards()
    test_greedy_run()
    print("\n🎉 Phase 6f 전체 테스트 통과!")


if __name__ == "__main__":
    main()
