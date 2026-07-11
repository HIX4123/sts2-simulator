#!/usr/bin/env python3
"""
STS2 Phase 6c 통합 테스트.
Silent 카드 풀 86종 (디컴파일 SilentCardPool 91종 - 멀티플레이 전용 5종)
+ 신규 파워 26종 + 전투 배선 (Sly/Retain/버리기 훅/Intangible/드로우 수정).
"""
import sts2_sim  # noqa: F401 — CARD_REGISTRY 등록
from sts2_sim.core.combat import CombatState
from sts2_sim.core.policy import GreedyPolicy
from sts2_sim.core.run import RunState
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import create_monster
from sts2_sim.models.sts2_card import CARD_REGISTRY, CardType, Rarity, create_card
from sts2_sim.models.sts2_power import Poison, Weak
from sts2_sim.cards.silent import SILENT_POOL_BY_RARITY


def make_combat(monster_ids=("big_dummy",), seed=42):
    player = Player(create_character("silent"))
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
    common = SILENT_POOL_BY_RARITY[Rarity.COMMON]
    uncommon = SILENT_POOL_BY_RARITY[Rarity.UNCOMMON]
    rare = SILENT_POOL_BY_RARITY[Rarity.RARE]
    total = len(common) + len(uncommon) + len(rare)
    # 86종 = 91 - 멀티5 : 보상 풀 80 + Basic 4 + Ancient 2 (+Shiv 토큰)
    assert total == 80, f"보상 풀 {total} != 80"
    assert len(common) == 20 and len(uncommon) == 35 and len(rare) == 25
    for cid in common + uncommon + rare + ["suppress", "wraith_form"]:
        assert cid in CARD_REGISTRY, f"레지스트리 누락: {cid}"
    assert create_card("suppress").rarity == Rarity.ANCIENT
    assert create_card("wraith_form").rarity == Rarity.ANCIENT
    print(f"✅ 보상 풀 80종 (C{len(common)}/U{len(uncommon)}/R{len(rare)})"
          f" + Ancient 2 등록")

    spots = {  # card_id: (cost, exhausts)
        "backstab": (0, True), "assassinate": (0, True), "adrenaline": (0, True),
        "grand_finale": (0, False), "bullet_time": (3, False),
        "snakebite": (2, False), "haze": (3, False), "pinpoint": (3, False),
    }
    for cid, (cost, exhausts) in spots.items():
        card = create_card(cid)
        assert card.cost == cost and card.exhausts == exhausts, cid
    assert create_card("skewer").x_cost and create_card("malaise").x_cost
    assert create_card("backstab").is_innate and create_card("suppress").is_innate
    assert create_card("snakebite").retains
    assert create_card("flick_flack").is_sly and create_card("tactician").is_sly
    print("✅ 비용/소모/X코스트/선천성/Sly/Retain 스팟 체크 통과")


def test_poison_pipeline():
    print("\n=== 중독 파이프라인 ===\n")
    combat, player, (dummy,) = make_combat()
    play(combat, "deadly_poison", dummy, energy=3)
    assert dummy.get_power_amount("poison") == 5, "DeadlyPoison 5"
    hp0 = dummy.current_hp
    dummy.tick_powers()  # 5 피해, 스택 4
    assert hp0 - dummy.current_hp == 5 and dummy.get_power_amount("poison") == 4
    print("✅ DeadlyPoison 5 → 틱 5딜, 스택 4")

    # BubbleBubble — 중독 상태에서만
    play(combat, "bubble_bubble", dummy, energy=3)
    assert dummy.get_power_amount("poison") == 13, "BubbleBubble +9"
    # Accelerant — 중독 2회 발동
    play(combat, "accelerant", energy=3)
    hp1 = dummy.current_hp
    dummy.tick_powers()
    assert hp1 - dummy.current_hp == 13 + 12, "Accelerant 2회 발동 (13+12)"
    assert dummy.get_power_amount("poison") == 11
    print("✅ BubbleBubble 조건부 +9, Accelerant 이중 틱")

    # Outbreak — 중독 부여 시 전체 피해
    play(combat, "outbreak", energy=3)
    hp2 = dummy.current_hp
    play(combat, "haze", energy=3)  # 중독 4 + Outbreak 3딜
    assert hp2 - dummy.current_hp == 3, "Outbreak 3딜"
    print("✅ Outbreak — 중독 부여 시 3딜")

    # Mirage — 중독 합만큼 블록
    psn = dummy.get_power_amount("poison")
    play(combat, "mirage", energy=3)
    assert player.block >= psn, f"Mirage 블록 {player.block} >= 중독 {psn}"
    print("✅ Mirage — 중독 합 블록")


def test_envenom_and_noxious():
    print("\n=== Envenom / NoxiousFumes / CorrosiveWave ===\n")
    combat, player, (dummy,) = make_combat()
    play(combat, "envenom", energy=3)
    play(combat, "slice", dummy, energy=3)
    assert dummy.get_power_amount("poison") == 1, "Envenom 중독 1"
    print("✅ Envenom — 비차단 피해 시 중독")

    play(combat, "noxious_fumes", energy=3)
    combat.notify_player_powers("on_turn_start")
    assert dummy.get_power_amount("poison") == 3, "NoxiousFumes +2"
    print("✅ NoxiousFumes — 턴 시작 중독 2")

    play(combat, "corrosive_wave", energy=3)
    combat.draw_pile.append(create_card("slice"))
    combat.draw_cards(1)
    assert dummy.get_power_amount("poison") == 5, "CorrosiveWave 드로우 시 +2"
    print("✅ CorrosiveWave — 드로우마다 중독 2")


def test_shiv_engine():
    print("\n=== Shiv 엔진 (Accuracy/PhantomBlades/FanOfKnives/Inky) ===\n")
    combat, player, monsters = make_combat(("big_dummy", "big_dummy"))
    d1, d2 = monsters
    play(combat, "blade_dance", energy=3)
    shivs = [c for c in combat.hand if c.card_id == "shiv"]
    assert len(shivs) == 3, "BladeDance Shiv 3장"
    play(combat, "accuracy", energy=3)
    hp0 = d1.current_hp
    combat.play_card(shivs[0], d1)
    assert hp0 - d1.current_hp == 4 + 4, "Shiv 4 + Accuracy 4"
    assert combat.exhaust_pile[-1].card_id == "shiv", "Shiv 소모"
    print("✅ BladeDance 3장, Accuracy +4, Shiv 소모")

    # PhantomBlades — 첫 Shiv +9, Retain 부여
    play(combat, "phantom_blades", energy=3)
    assert all(s.retains for s in combat.hand if s.card_id == "shiv")
    combat.shivs_played_this_turn = 0
    hp1 = d1.current_hp
    combat.play_card(shivs[1], d1)
    assert hp1 - d1.current_hp == 4 + 4 + 9, "첫 Shiv +9"
    hp2 = d1.current_hp
    combat.play_card(shivs[2], d1)
    assert hp2 - d1.current_hp == 4 + 4, "두 번째 Shiv는 보너스 없음"
    print("✅ PhantomBlades — Retain + 턴 첫 Shiv +9")

    # FanOfKnives — 전체 공격화
    play(combat, "fan_of_knives", energy=3)
    new_shivs = [c for c in combat.hand if c.card_id == "shiv"]
    assert len(new_shivs) == 4, "FanOfKnives Shiv 4장"
    h1, h2 = d1.current_hp, d2.current_hp
    combat.play_card(new_shivs[0], d1)
    assert d1.current_hp < h1 and d2.current_hp < h2, "Shiv 전체 공격"
    print("✅ FanOfKnives — Shiv 전체 공격화")

    # BladeOfInk — Inky Shiv: +1딜, 약화 1
    combat2, player2, (dummy,) = make_combat()
    play(combat2, "blade_of_ink", energy=3)
    inky = [c for c in combat2.hand if c.card_id == "shiv"]
    assert len(inky) == 2 and all(s.inky for s in inky)
    hp = dummy.current_hp
    combat2.play_card(inky[0], dummy)
    assert hp - dummy.current_hp == 5 and dummy.get_power_amount("weak") == 1
    print("✅ BladeOfInk — Inky Shiv 5딜 + 약화 1")


def test_sly_and_retain():
    print("\n=== Sly / Retain / WellLaidPlans ===\n")
    combat, player, (dummy,) = make_combat()
    # Sly — 버려질 때 자동 플레이
    sly = create_card("flick_flack")
    combat.hand.append(sly)
    hp0 = dummy.current_hp
    combat.discard_card(sly)
    assert hp0 - dummy.current_hp == 7, "Sly FlickFlack 자동 발동 7딜"
    print("✅ Sly — 버리기 시 자동 플레이")

    # 턴 종료 버리기는 Sly 발동 안 함 + Retain 유지
    keep = create_card("snakebite")
    other = create_card("slice")
    sly2 = create_card("untouchable")
    combat.hand.extend([keep, other, sly2])
    hp1 = dummy.current_hp
    block0 = player.block
    combat._discard_hand()
    assert keep in combat.hand, "Retain 카드 유지"
    assert other not in combat.hand and sly2 not in combat.hand
    assert dummy.current_hp == hp1 and player.block == block0, \
        "턴 종료 버리기는 Sly 미발동"
    print("✅ Retain 유지 / 턴 종료 Sly 미발동")

    # WellLaidPlans — 1장 유지
    play(combat, "well_laid_plans", energy=3)
    a, b = create_card("slice"), create_card("slice")
    combat.hand.extend([a, b])
    combat._discard_hand()
    kept = [c for c in combat.hand if c.card_id == "slice"]
    assert len(kept) == 1, "WellLaidPlans 1장 유지"
    print("✅ WellLaidPlans — 무작위 1장 유지")

    # HandTrick — 스킬에 이번 턴 Sly
    combat.hand.clear()
    skill = create_card("deflect")
    combat.hand.append(skill)
    play(combat, "hand_trick", energy=3)
    assert skill._sly_this_turn, "HandTrick Sly 부여"
    block1 = player.block
    combat.discard_card(skill)
    assert player.block > block1, "Sly Deflect 자동 발동"
    print("✅ HandTrick — 단일 턴 Sly")

    # MasterPlanner — 플레이한 스킬 영구 Sly
    play(combat, "master_planner", energy=3)
    s2 = play(combat, "deflect", energy=3)
    assert s2.is_sly, "MasterPlanner 스킬 Sly 부여"
    print("✅ MasterPlanner — 스킬 영구 Sly")


def test_discard_synergy():
    print("\n=== 버리기 시너지 (MementoMori/CalculatedGamble/StormOfSteel) ===\n")
    combat, player, (dummy,) = make_combat()
    combat.hand.extend([create_card("slice"), create_card("slice")])
    combat.discard_from_hand(2)
    assert combat.cards_discarded_this_turn == 2
    hp0 = dummy.current_hp
    play(combat, "memento_mori", dummy, energy=3)
    assert hp0 - dummy.current_hp == 9 + 4 * 2, "MementoMori 9+4×2"
    print("✅ MementoMori — 17딜 (버리기 2)")

    combat.hand.clear()
    combat.draw_pile.extend([create_card("slice")] * 3)
    combat.hand.extend([create_card("deflect")] * 3)
    play(combat, "calculated_gamble", energy=3)
    assert len(combat.hand) == 3, "CalculatedGamble 3버리기 3드로우"
    assert combat.exhaust_pile[-1].card_id == "calculated_gamble"
    print("✅ CalculatedGamble — 전부 버리고 같은 수 드로우, 소모")

    combat.hand.clear()
    combat.hand.extend([create_card("deflect")] * 4)
    play(combat, "storm_of_steel", upgraded=True, energy=3)
    shivs = [c for c in combat.hand if c.card_id == "shiv"]
    assert len(shivs) == 4 and all(s.upgraded for s in shivs), \
        "StormOfSteel+ 업그레이드 Shiv 4장"
    print("✅ StormOfSteel+ — 손패 수만큼 업그레이드 Shiv")


def test_calculated_damage():
    print("\n=== 계산형 데미지 (Finisher/Flechettes/PreciseCut/Murder/Skewer) ===\n")
    combat, player, (dummy,) = make_combat()
    play(combat, "slice", dummy, energy=3)
    play(combat, "slice", dummy, energy=3)
    hp0 = dummy.current_hp
    play(combat, "finisher", dummy, energy=3)
    assert hp0 - dummy.current_hp == 6 * 2, "Finisher 6×2 (선행 공격 2)"
    print("✅ Finisher — 공격 수 비례")

    combat.hand.extend([create_card("deflect"), create_card("deflect")])
    hp1 = dummy.current_hp
    play(combat, "flechettes", dummy, energy=3)
    assert hp1 - dummy.current_hp == 5 * 2, "Flechettes 5×스킬 2"
    print("✅ Flechettes — 손패 스킬 수 비례")

    combat.hand.clear()
    combat.hand.append(create_card("deflect"))
    hp2 = dummy.current_hp
    play(combat, "precise_cut", dummy, energy=3)
    assert hp2 - dummy.current_hp == 13 - 2, "PreciseCut 13-2×1"
    print("✅ PreciseCut — 손패 수 반비례")

    combat.cards_drawn_this_combat = 10
    hp3 = dummy.current_hp
    play(combat, "murder", dummy, energy=3)
    assert hp3 - dummy.current_hp == 1 + 10, "Murder 1+드로우 10"
    print("✅ Murder — 전투 드로우 수 비례")

    hp4 = dummy.current_hp
    play(combat, "skewer", dummy, energy=3)
    assert hp4 - dummy.current_hp == 8 * 3, "Skewer 8×3 (X=3)"
    assert player.energy == 0
    print("✅ Skewer — X코스트 8×X")


def test_defensive_powers():
    print("\n=== 방어 파워 (Blur/DodgeAndRoll/Shadowmeld/Intangible/WraithForm) ===\n")
    combat, player, (dummy,) = make_combat()
    play(combat, "blur", energy=3)
    assert player.block == 5 and player.has_power("blur")
    player.start_of_turn()
    assert player.block == 5, "Blur 블록 유지"
    combat.notify_player_powers("on_turn_start")
    player.start_of_turn()
    assert player.block == 0, "Blur 소진 후 초기화"
    print("✅ Blur — 1턴 블록 유지")

    play(combat, "dodge_and_roll", energy=3)
    assert player.get_power_amount("block_next_turn") == 4
    player.start_of_turn()
    combat.notify_player_powers("on_turn_start")
    assert player.block == 4, "DodgeAndRoll 다음 턴 4블록"
    print("✅ DodgeAndRoll — 다음 턴 블록")

    play(combat, "shadowmeld", energy=3)
    b0 = player.block
    play(combat, "deflect", energy=3)
    assert player.block - b0 == 8, "Shadowmeld 4×2"
    print("✅ Shadowmeld — 블록 2배")

    play(combat, "wraith_form", energy=3)
    assert player.get_power_amount("intangible") == 2
    hp0 = player.current_hp
    player.take_damage(30, source=dummy)
    assert hp0 - player.current_hp <= 1, "Intangible 피해 1 제한"
    combat.notify_player_powers("on_enemy_turn_end")
    assert player.get_power_amount("intangible") == 1
    combat.notify_player_powers("on_turn_start")
    assert player.get_power_amount("dexterity") == -1, "WraithForm 민첩 -1"
    print("✅ WraithForm — Intangible 2 + 민첩 감소")


def test_burst_and_free_skill():
    print("\n=== Burst / Pounce / BulletTime / Adrenaline / Tactician ===\n")
    combat, player, (dummy,) = make_combat()
    play(combat, "burst", energy=3)
    play(combat, "deflect", energy=3)
    assert player.block == 8, "Burst — Deflect 2회 발동 (4×2)"
    assert not player.has_power("burst")
    print("✅ Burst — 스킬 2회 발동")

    play(combat, "pounce", dummy, energy=3)
    assert player.get_power_amount("free_skill") == 1
    card = create_card("snakebite")  # 2코스트
    combat.hand.append(card)
    assert combat.get_card_cost(card) == 0, "FreeSkill 비용 0"
    player.energy = 0
    assert combat.play_card(card, dummy), "0에너지로 플레이"
    print("✅ Pounce — 다음 스킬 무료")

    combat.hand.extend([create_card("haze"), create_card("predator")])
    play(combat, "bullet_time", energy=3)
    assert all(combat.get_card_cost(c) == 0 for c in combat.hand)
    assert player.has_power("no_draw")
    print("✅ BulletTime — 손패 비용 0 + 드로우 불가")

    player.energy = 0
    play(combat, "adrenaline", energy=0)
    assert player.energy == 1, "Adrenaline 에너지 +1"
    play(combat, "tactician", energy=3)
    assert player.energy == 3 - 3 + 1, "Tactician 에너지 +1"
    print("✅ Adrenaline/Tactician — 에너지 획득")


def test_misc_attacks():
    print("\n=== EchoingSlash / GrandFinale / Expose / Strangle / Malaise ===\n")
    combat, player, monsters = make_combat(("big_dummy", "big_dummy"))
    weak_one, big = monsters
    weak_one._current_hp = 5
    hp_big = big.current_hp
    play(combat, "echoing_slash", energy=3)
    # 약한 적 처치 → 반복 → big은 10×2
    assert weak_one.is_dead and hp_big - big.current_hp == 20, "EchoingSlash 반복"
    print("✅ EchoingSlash — 처치 시 반복")

    gf = create_card("grand_finale")
    combat.hand.append(gf)
    assert not combat.is_card_playable(gf), "드로우 더미 있으면 불가"
    combat.draw_pile.clear()
    assert combat.is_card_playable(gf), "드로우 더미 비면 가능"
    hp0 = big.current_hp
    combat.play_card(gf, big)
    assert hp0 - big.current_hp == 60
    print("✅ GrandFinale — 조건부 60딜")

    big.gain_block(10)
    play(combat, "expose", big, energy=3)
    assert big.block == 0 and big.get_power_amount("vulnerable") == 2
    print("✅ Expose — 블록 제거 + 취약 2")

    play(combat, "strangle", big, energy=3)
    assert big.get_power_amount("strangle") == 2
    hp1 = big.current_hp
    play(combat, "slice", big, energy=3)
    # 취약(Expose) 상태라 Slice 6×1.5=9, + Strangle 2
    assert hp1 - big.current_hp == 9 + 2, "Strangle 카드 플레이 시 +2"
    print("✅ Strangle — 카드 플레이마다 비차단 피해")

    play(combat, "malaise", big, energy=2)
    assert big.get_power_amount("strength") == -2
    assert big.get_power_amount("weak") == 2
    print("✅ Malaise — X코스트 힘 감소 + 약화")


def test_turn_loop_powers():
    print("\n=== 턴 루프 파워 (InfiniteBlades/ToolsOfTheTrade/Predator/Nightmare/ShadowStep) ===\n")
    combat, player, (dummy,) = make_combat()
    play(combat, "infinite_blades", energy=3)
    combat.notify_player_powers("on_turn_start")
    assert any(c.card_id == "shiv" for c in combat.hand), "InfiniteBlades Shiv"
    print("✅ InfiniteBlades — 턴 시작 Shiv")

    combat, player, (dummy,) = make_combat()  # 격리 (InfiniteBlades 간섭 방지)
    combat.hand.append(create_card("slice"))
    play(combat, "nightmare", energy=3)  # 손패 무작위 카드 3장 복제 예약
    assert player.has_power("nightmare")
    combat.notify_player_powers("on_turn_start")
    assert sum(1 for c in combat.hand if c.card_id == "slice") == 4, \
        "Nightmare 3장 복제"
    print("✅ Nightmare — 다음 턴 3장 복제")

    play(combat, "shadow_step", energy=3)
    assert not combat.hand, "ShadowStep 손패 버리기"
    combat.notify_player_powers("on_turn_start")
    hp0 = dummy.current_hp
    play(combat, "slice", dummy, energy=3)
    assert hp0 - dummy.current_hp == 12, "DoubleDamage 6×2"
    print("✅ ShadowStep — 다음 턴 더블 데미지")

    # ToolsOfTheTrade — 드로우 +1 후 1버리기 (전투 루프 통합 확인용 수동 트리거)
    play(combat, "tools_of_the_trade", energy=3)
    draw = 5
    for power in player._powers.values():
        modify = getattr(power, "modify_hand_draw", None)
        if modify:
            draw = modify(draw)
    assert draw == 6, "ToolsOfTheTrade 드로우 +1"
    print("✅ ToolsOfTheTrade — 드로우 수정 파이프라인")


def test_tracking_and_speedster():
    print("\n=== Tracking / Speedster / SerpentForm / Afterimage ===\n")
    combat, player, (dummy,) = make_combat()
    play(combat, "tracking", energy=3)
    dummy.apply_power(Weak(2))
    hp0 = dummy.current_hp
    play(combat, "slice", dummy, energy=3)
    assert hp0 - dummy.current_hp == 9, "Tracking 6×1.5"
    print("✅ Tracking — 약화 대상 +50%")

    play(combat, "speedster", energy=3)
    combat.draw_pile.append(create_card("slice"))
    hp1 = dummy.current_hp
    combat.draw_cards(1)  # in_hand_draw=False → 트리거
    assert hp1 - dummy.current_hp == 2, "Speedster 추가 드로우 2딜"
    print("✅ Speedster — 추가 드로우 시 전체 피해")

    play(combat, "serpent_form", energy=3)
    hp2 = dummy.current_hp
    play(combat, "deflect", energy=3)
    assert hp2 - dummy.current_hp == 4, "SerpentForm 카드마다 4딜"
    print("✅ SerpentForm — 카드 플레이마다 피해")

    play(combat, "afterimage", energy=3)
    b0 = player.block
    play(combat, "slice", dummy, energy=3)
    assert player.block == b0 + 1, "Afterimage 카드마다 1블록"
    print("✅ Afterimage — 카드 플레이마다 블록")


def test_knife_trap_and_up_my_sleeve():
    print("\n=== KnifeTrap / UpMySleeve / PiercingWail ===\n")
    combat, player, (dummy,) = make_combat()
    for _ in range(3):
        combat.exhaust_pile.append(create_card("shiv"))
    hp0 = dummy.current_hp
    play(combat, "knife_trap", dummy, energy=3)
    assert hp0 - dummy.current_hp == 4 * 3, "KnifeTrap — 소모 Shiv 3장 발사"
    print("✅ KnifeTrap — 소모 더미 Shiv 재발사")

    ums = play(combat, "up_my_sleeve", energy=3)
    assert ums.cost == 1, "UpMySleeve 비용 -1"
    print("✅ UpMySleeve — 플레이마다 비용 감소")

    play(combat, "piercing_wail", energy=3)
    assert dummy.compute_attack_damage(10) == 4, "PiercingWail 적 공격 -6"
    dummy.tick_powers()
    assert dummy.get_power_amount("temp_strength") == 0, "임시 힘 원복"
    assert dummy.compute_attack_damage(10) == 10, "원복 후 정상"
    print("✅ PiercingWail — 임시 힘 -6")


def test_full_combat_and_runs():
    print("\n=== 시드 전투 + 10시드 런 ===\n")
    from sts2_sim.core.encounters import EASY_POOL, random_encounter_from
    import random
    player = Player(create_character("silent"))
    rng = random.Random(7)
    monsters = random_encounter_from(rng, EASY_POOL)
    combat = CombatState(player, monsters, seed=7)
    result = combat.run(GreedyPolicy())
    print(f"전투: {'승리' if result.victory else '패배'} {result.turns}턴, "
          f"HP {result.player_hp}")

    wins = floors = 0
    for seed in range(10):
        run = RunState("silent", seed=seed)
        res = run.play(GreedyPolicy())
        wins += res.victory
        floors += res.floors_cleared
    print(f"✅ 10시드 런: {wins}승, 평균 {floors / 10:.1f}층 도달")


if __name__ == "__main__":
    test_pool_registration()
    test_poison_pipeline()
    test_envenom_and_noxious()
    test_shiv_engine()
    test_sly_and_retain()
    test_discard_synergy()
    test_calculated_damage()
    test_defensive_powers()
    test_burst_and_free_skill()
    test_misc_attacks()
    test_turn_loop_powers()
    test_tracking_and_speedster()
    test_knife_trap_and_up_my_sleeve()
    test_full_combat_and_runs()
    print("\n🎉 Phase 6c 전체 테스트 통과!")
