#!/usr/bin/env python3
"""
STS2 Phase 6d 통합 테스트.
Defect 카드 풀 86종 (디컴파일 DefectCardPool 91종 - 멀티플레이 전용 5종)
+ 신규 파워 22종 + 오브 엔진 확장 (슬롯 상한 10/RemoveSlots/EvokeLast/
수동 패시브/이보크 훅) + 전투 배선 (EchoForm/Feral/상태이상 생성 훅/
전투 한정 비용 변형).
"""
import sts2_sim  # noqa: F401 — CARD_REGISTRY 등록
from sts2_sim.core.combat import CombatState
from sts2_sim.core.policy import GreedyPolicy
from sts2_sim.core.run import RunState
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import create_monster
from sts2_sim.models.sts2_card import CARD_REGISTRY, CardType, Rarity, create_card
from sts2_sim.models.sts2_orb import (
    LightningOrb, FrostOrb, DarkOrb, PlasmaOrb, GlassOrb, OrbQueue,
)
from sts2_sim.cards.defect import DEFECT_POOL_BY_RARITY, DEFECT_POWER_CARD_IDS


def make_combat(monster_ids=("big_dummy",), seed=42, clear_orbs=True):
    player = Player(create_character("defect"))
    monsters = [create_monster(mid) for mid in monster_ids]
    combat = CombatState(player, monsters, seed=seed)
    combat.start()
    player.energy = player.max_energy
    if clear_orbs:
        # Cracked Core(스타터 렐릭)가 전투 시작 시 채널한 라이트닝 제거 —
        # 오브 상태를 결정적으로 만들기 위함
        player.orb_queue.orbs.clear()
        combat.lightning_channeled_this_combat = 0
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
    common = DEFECT_POOL_BY_RARITY[Rarity.COMMON]
    uncommon = DEFECT_POOL_BY_RARITY[Rarity.UNCOMMON]
    rare = DEFECT_POOL_BY_RARITY[Rarity.RARE]
    total = len(common) + len(uncommon) + len(rare)
    # 86종 = 91 - 멀티5 : 보상 풀 80 + Basic 4(zap/dualcast/strike/defend)
    # + Ancient 2 (+Fuel 토큰)
    assert total == 80, f"보상 풀 {total} != 80"
    assert len(common) == 20 and len(uncommon) == 35 and len(rare) == 25
    for cid in common + uncommon + rare + ["biased_cognition", "quadcast", "fuel"]:
        assert cid in CARD_REGISTRY, f"레지스트리 누락: {cid}"
    assert create_card("biased_cognition").rarity == Rarity.ANCIENT
    assert create_card("quadcast").rarity == Rarity.ANCIENT
    # 멀티플레이 전용 5종 제외 확인
    for cid in ("energy_surge", "hibernate", "ignition",
                "imitation_learning", "one_for_all"):
        assert cid not in CARD_REGISTRY, f"멀티 전용 카드 등록됨: {cid}"
    print(f"✅ 보상 풀 80종 (C{len(common)}/U{len(uncommon)}/R{len(rare)})"
          f" + Ancient 2 + Fuel 등록")

    spots = {  # card_id: (cost, exhausts)
        "boot_sequence": (0, True), "reboot": (0, True), "shatter": (1, True),
        "supercritical": (0, True), "voltaic": (3, True), "rainbow": (2, True),
        "meteor_strike": (5, False), "hyperbeam": (2, False), "modded": (0, False),
        "helix_drill": (0, False), "beam_cell": (0, False),
    }
    for cid, (cost, exhausts) in spots.items():
        card = create_card(cid)
        assert card.cost == cost and card.exhausts == exhausts, cid
    assert create_card("tempest").x_cost and create_card("multi_cast").x_cost
    assert create_card("boot_sequence").is_innate
    ml = create_card("machine_learning")
    assert not ml.is_innate
    ml.upgrade()
    assert ml.is_innate, "MachineLearning 업글 → 선천성"
    assert len(DEFECT_POWER_CARD_IDS) == 20, "파워 카드 20종"
    print("✅ 비용/소모/X코스트/선천성 스팟 체크 통과")


def test_orb_queue_engine():
    print("\n=== 오브 큐 엔진 확장 ===\n")
    combat, player, (dummy,) = make_combat()
    queue = player.orb_queue

    # 슬롯 상한 10 (OrbCmd.AddSlots)
    queue.gain_slots(20)
    assert queue.slot_count == 10, "슬롯 상한 10"
    # RemoveSlots — 뒤에서부터 오브째 제거
    for orb_cls in (LightningOrb, FrostOrb, DarkOrb):
        queue.channel(orb_cls(), player, combat)
    queue.remove_slots(8)
    assert queue.slot_count == 2 and len(queue.orbs) == 2
    assert queue.orbs[-1].orb_id == "frost", "뒤(어둠)부터 제거"
    print("✅ 슬롯 상한 10 / RemoveSlots 뒤에서부터 오브째 제거")

    # EvokeLast (ConsumingShadow 용)
    hp0 = dummy.current_hp
    queue.channel(DarkOrb(), player, combat)  # [L, F, D] → 슬롯 2라 L 이보크
    assert len(queue.orbs) == 2 and queue.orbs[0].orb_id == "frost"
    assert hp0 - dummy.current_hp == 8, "가득 찬 채널 → 선두 라이트닝 이보크 8"
    queue.evoke_last(combat)  # Dark 이보크 (초기 누적 6)
    assert hp0 - dummy.current_hp == 8 + 6 and len(queue.orbs) == 1
    print("✅ 가득 찬 채널 → 선두 이보크 / EvokeLast")

    # Voltaic 카운터
    assert combat.lightning_channeled_this_combat == 1
    play(combat, "voltaic", energy=3)  # 1개 채널됨 → 라이트닝 1개 추가
    assert combat.lightning_channeled_this_combat == 2
    assert queue.orbs[-1].orb_id == "lightning"
    print("✅ Voltaic — 이번 전투 라이트닝 채널 수만큼 채널")


def test_focus_and_temp_focus():
    print("\n=== 집중 / 임시 집중 ===\n")
    combat, player, (dummy,) = make_combat()
    play(combat, "defragment", energy=3)
    orb = FrostOrb()
    orb.owner = player
    assert orb.passive_val == 3, "Defragment: 서리 패시브 2+1"
    play(combat, "focused_strike", dummy)  # 9딜 + 임시 집중 1
    assert orb.passive_val == 4, "TempFocus 가산"
    player.tick_powers()  # 턴 종료 — TempFocus 만료
    assert orb.passive_val == 3 and player.get_power_amount("focus") == 1
    print("✅ Focus 영구 / TempFocus 턴 한정")

    # Synchronize — 오브 종류 수 × 2
    queue = player.orb_queue
    queue.channel(LightningOrb(), player, combat)
    queue.channel(LightningOrb(), player, combat)
    queue.channel(FrostOrb(), player, combat)
    play(combat, "synchronize", energy=3)
    assert player.get_power_amount("temp_focus") == 4, "종류 2 × 2"
    # Hyperbeam — 집중 -3
    play(combat, "hyperbeam", dummy, energy=3)
    assert player.get_power_amount("focus") == 1 - 3
    print("✅ Synchronize 종류×2 / Hyperbeam 집중 -3")

    # BiasedCognition — 집중 +4, 턴 시작마다 -1
    play(combat, "biased_cognition", energy=3)
    assert player.get_power_amount("focus") == -2 + 4
    player._powers["biased_cognition"].on_turn_start()
    assert player.get_power_amount("focus") == 1
    print("✅ BiasedCognition +4 / 턴당 -1")


def test_claw_and_combat_cost_mutations():
    print("\n=== Claw 스케일링 / 전투 한정 비용 변형 ===\n")
    combat, player, (dummy,) = make_combat()
    claw2 = create_card("claw")
    combat.draw_pile.append(claw2)
    played = play(combat, "claw", dummy, energy=3)
    assert claw2._extra_this_combat == 2 and played._extra_this_combat == 2
    hp0 = dummy.current_hp
    combat.hand.append(claw2)
    combat.play_card(claw2, dummy)
    assert hp0 - dummy.current_hp == 5, "두 번째 Claw 3+2"
    # MomentumStrike — 플레이 후 이번 전투 비용 0
    ms = play(combat, "momentum_strike", dummy, energy=3)
    assert combat.get_card_cost(ms) == 0, "SetThisCombat(0)"
    # Modded — 플레이마다 비용 +1
    md = play(combat, "modded", energy=3)
    assert combat.get_card_cost(md) == 1, "AddThisCombat(+1)"
    # AdaptiveStrike — 비용 0 사본
    play(combat, "adaptive_strike", dummy, energy=3)
    clones = [c for c in combat.discard_pile if c.card_id == "adaptive_strike"]
    assert len(clones) == 2, "본체 + 사본"
    assert any(combat.get_card_cost(c) == 0 for c in clones), "사본 비용 0"
    # 전투 종료 시 원복
    combat._finish(True)
    assert ms._cost_this_combat is None and md._cost_add_this_combat == 0
    assert played._extra_this_combat == 0, "Claw 누적 리셋"
    print("✅ Claw 전체 버프(+2)/MomentumStrike 0/Modded 누진/"
          "AdaptiveStrike 사본 — 전투 종료 원복")


def test_calculated_attacks():
    print("\n=== 오브/에너지 계산 공격 ===\n")
    combat, player, (dummy,) = make_combat()
    queue = player.orb_queue
    queue.gain_slots(2)
    for orb_cls in (FrostOrb, FrostOrb, DarkOrb):
        queue.channel(orb_cls(), player, combat)
    # Barrage — 오브 수(3) × 5딜
    hp0 = dummy.current_hp
    play(combat, "barrage", dummy, energy=3)
    assert hp0 - dummy.current_hp == 15, f"Barrage 5×3 = {hp0 - dummy.current_hp}"
    # CompileDriver — 종류 수(2)만큼 드로우
    combat.draw_pile.extend(create_card("strike") for _ in range(4))
    hand0 = len(combat.hand)
    play(combat, "compile_driver", dummy, energy=3)
    assert len(combat.hand) == hand0 + 2, "종류 2 드로우"
    print("✅ Barrage(오브 수) / CompileDriver(종류 수)")

    # HelixDrill — 이번 턴 소비 에너지만큼 타격
    combat2, player2, (dummy2,) = make_combat()
    play(combat2, "leap", energy=3)          # 1 소비
    play(combat2, "cold_snap", dummy2)       # 1 소비
    hp0 = dummy2.current_hp
    play(combat2, "helix_drill", dummy2)     # 0코스트 — 3딜 × 2
    assert hp0 - dummy2.current_hp == 6, "HelixDrill 3×2"
    print("✅ HelixDrill — 소비 에너지 비례 (자기 비용 제외)")

    # Ftl — 이번 턴 3장 미만이면 드로우
    combat3, player3, (dummy3,) = make_combat()
    combat3.draw_pile.extend(create_card("strike") for _ in range(4))
    hand0 = len(combat3.hand)
    play(combat3, "ftl", dummy3, energy=3)   # 첫 플레이 → 드로우 1
    assert len(combat3.hand) == hand0 + 1
    play(combat3, "leap")
    play(combat3, "leap")
    hand0 = len(combat3.hand)
    play(combat3, "ftl", dummy3)             # 4번째 플레이 → 드로우 없음
    assert len(combat3.hand) == hand0
    print("✅ Ftl — 이번 턴 플레이 수 조건 드로우")


def test_echo_form_and_doublers():
    print("\n=== EchoForm / SignalBoost ===\n")
    combat, player, (dummy,) = make_combat()
    play(combat, "echo_form", energy=3)
    combat.cards_played_this_turn = 0  # 새 턴 흉내
    hp0 = dummy.current_hp
    play(combat, "cold_snap", dummy, energy=3)  # 첫 카드 → 2회 발동
    assert hp0 - dummy.current_hp == 12, "EchoForm 6×2"
    assert len(player.orb_queue) == 2, "채널도 2회"
    hp0 = dummy.current_hp
    play(combat, "ball_lightning", dummy)  # 두 번째 카드 → 1회
    assert hp0 - dummy.current_hp == 7
    print("✅ EchoForm — 매 턴 첫 카드만 2회")

    combat2, player2, (dummy2,) = make_combat()
    play(combat2, "signal_boost", energy=3)
    assert player2.get_power_amount("signal_boost") == 1
    play(combat2, "defragment")  # 파워 → 2회 발동
    assert player2.get_power_amount("focus") == 2, "SignalBoost 파워 2회"
    assert player2.get_power_amount("signal_boost") == 0
    print("✅ SignalBoost — 다음 파워 카드 2회")


def test_feral_returns_attacks():
    print("\n=== Feral ===\n")
    combat, player, (dummy,) = make_combat()
    play(combat, "feral", energy=3)
    beam = play(combat, "beam_cell", dummy)  # 0코스트 공격 → 손패 복귀
    assert beam in combat.hand and beam not in combat.discard_pile
    beam2 = play(combat, "go_for_the_eyes", dummy)  # 이번 턴 2번째 → 버림
    assert beam2 in combat.discard_pile
    player._powers["feral"].on_turn_start()  # 새 턴 → 카운터 리셋
    combat.hand.remove(beam)
    combat.hand.append(beam)
    combat.play_card(beam, dummy)
    assert beam in combat.hand, "새 턴 첫 0코스트 공격 복귀"
    cs = play(combat, "cold_snap", dummy, energy=3)  # 1코스트 → 대상 아님
    assert cs in combat.discard_pile

    # 원본 AfterApplied: Feral 적용 전 이미 플레이한 0코스트 공격은 예산을 차감한다
    combat2, player2, (dummy2,) = make_combat()
    pre = play(combat2, "beam_cell", dummy2)  # Feral 전 0코스트 공격 → 복귀 없음
    assert pre in combat2.discard_pile
    assert combat2.zero_cost_attacks_this_turn == 1
    play(combat2, "feral", energy=3)
    assert player2._powers["feral"].used_this_turn == 1, "적용 전 0코스트 공격만큼 예산 차감"
    after = play(combat2, "beam_cell", dummy2)  # 예산 소진 → 복귀 안 함
    assert after in combat2.discard_pile and after not in combat2.hand
    print("✅ Feral — 턴당 1장, 0코스트 공격만 복귀, 적용 전 플레이분 예산 차감")


def test_power_play_triggers():
    print("\n=== Storm / Subroutine / FreePower ===\n")
    combat, player, (dummy,) = make_combat()
    play(combat, "storm", energy=3)
    assert len(player.orb_queue) == 0, "Storm 자신에는 미발동"
    play(combat, "defragment", energy=3)
    assert len(player.orb_queue) == 1, "다음 파워 → 라이트닝 채널"
    assert player.orb_queue.orbs[0].orb_id == "lightning"
    play(combat, "subroutine", energy=3)
    assert len(player.orb_queue) == 2, "Subroutine도 파워 — Storm 발동"
    player.energy = 1
    play(combat, "loop")  # 파워: Subroutine 에너지 +1, Storm 채널
    assert player.energy == 0 + 1, "Subroutine 에너지 +1"
    print("✅ Storm/Subroutine — 자기 자신 미발동, 이후 파워마다 발동")

    # Synthesis → 다음 파워 비용 0
    combat2, player2, (dummy2,) = make_combat()
    play(combat2, "synthesis", dummy2, energy=3)
    assert player2.get_power_amount("free_power") == 1
    buffer_card = create_card("buffer")
    combat2.hand.append(buffer_card)
    assert combat2.get_card_cost(buffer_card) == 0
    player2.energy = 0
    assert combat2.play_card(buffer_card), "0비용으로 플레이"
    assert player2.get_power_amount("free_power") == 0
    assert player2.get_power_amount("buffer") == 1
    print("✅ Synthesis/FreePower — 다음 파워 무료")


def test_status_generation_hooks():
    print("\n=== 상태이상 생성 훅 (Smokestack/TrashToTreasure/RocketPunch) ===\n")
    combat, player, (dummy,) = make_combat()
    play(combat, "smokestack", energy=3)
    play(combat, "trash_to_treasure", energy=3)
    rocket = create_card("rocket_punch")
    combat.draw_pile.append(rocket)
    hp0 = dummy.current_hp
    play(combat, "turbo", energy=3)  # Void 생성 → 훅 3종 발동
    assert hp0 - dummy.current_hp == 5, "Smokestack 5딜"
    assert len(player.orb_queue) == 1, "TrashToTreasure 무작위 오브 1"
    assert combat.get_card_cost(rocket) == 0, "RocketPunch 플레이 전까지 0"
    assert any(c.card_id == "void" for c in combat.discard_pile)
    # 몬스터 삽입은 미발동
    hp1 = dummy.current_hp
    combat.add_status_to_discard("dazed", 1)
    assert dummy.current_hp == hp1, "몬스터 생성 상태이상은 훅 미발동"
    # RocketPunch 플레이하면 비용 소모
    combat.draw_pile.remove(rocket)
    combat.hand.append(rocket)
    player.energy = 0
    assert combat.play_card(rocket, dummy)
    assert combat.get_card_cost(rocket) == 2, "플레이 후 원래 비용"
    print("✅ Turbo Void 생성 → Smokestack/TrashToTreasure/RocketPunch, "
          "몬스터 삽입 미발동")


def test_status_cards_and_compact():
    print("\n=== 상태이상 카드 / Compact / FlakCannon ===\n")
    combat, player, (dummy,) = make_combat()
    # Burn — 턴 종료 시 손패에 있으면 2 피해
    combat.hand.append(create_card("burn"))
    hp0 = player.current_hp
    combat._discard_hand()
    assert hp0 - player.current_hp == 2, "Burn 자해 2"
    # Void — 드로우 시 에너지 -1
    combat.draw_pile.append(create_card("void"))
    player.energy = 3
    combat.draw_cards(1)
    assert player.energy == 2, "Void 드로우 → 에너지 -1"
    # Compact — 손패 상태이상 → Fuel
    combat.hand.append(create_card("wound"))
    play(combat, "compact", energy=3)
    fuels = [c for c in combat.hand if c.card_id == "fuel"]
    assert len(fuels) == 2, "Void+Wound → Fuel 2장"
    player.energy = 0
    assert combat.play_card(fuels[0])
    assert player.energy == 1 and fuels[0] in combat.exhaust_pile
    print("✅ Burn/Void/Wound + Compact 변환 + Fuel 에너지")

    # FlakCannon — 상태이상 전부 소모, 수만큼 타격
    combat2, player2, (dummy2,) = make_combat()
    combat2.hand.append(create_card("wound"))
    combat2.draw_pile.append(create_card("dazed"))
    combat2.discard_pile.append(create_card("slimed"))
    hp0 = dummy2.current_hp
    play(combat2, "flak_cannon", dummy2, energy=3)
    assert hp0 - dummy2.current_hp == 24, "FlakCannon 8×3"
    assert len(combat2.exhaust_pile) == 3
    print("✅ FlakCannon — 상태이상 3장 소모 → 8×3딜")


def test_evoke_cards():
    print("\n=== MultiCast / Quadcast / Shatter / Darkness / TeslaCoil ===\n")
    combat, player, (dummy,) = make_combat()
    queue = player.orb_queue
    queue.channel(DarkOrb(), player, combat)
    queue.channel(FrostOrb(), player, combat)
    # MultiCast X=2: 선두(Dark, 6) 2회 이보크 후 제거
    hp0 = dummy.current_hp
    play(combat, "multi_cast", energy=2)
    assert hp0 - dummy.current_hp == 12, "Dark 6 × 2회"
    assert len(queue) == 1 and queue.orbs[0].orb_id == "frost"
    print("✅ MultiCast — 선두 오브 X회 이보크(마지막에만 제거)")

    # Darkness — 채널 + 어둠 패시브 발동 (업글 2회)
    combat2, player2, (dummy2,) = make_combat()
    play(combat2, "darkness", upgraded=True, energy=3)
    dark = player2.orb_queue.orbs[0]
    assert dark._accumulated_evoke == 6 + 12, "업글 Darkness 패시브 2회 (+6×2)"
    print("✅ Darkness — 어둠 패시브 즉시 발동")

    # TeslaCoil — 라이트닝 패시브를 대상에게
    combat3, player3, (dummy3,) = make_combat()
    player3.orb_queue.channel(LightningOrb(), player3, combat3)
    hp0 = dummy3.current_hp
    play(combat3, "tesla_coil", dummy3, energy=3)
    assert hp0 - dummy3.current_hp == 3 + 3, "3딜 + 패시브 3 (대상 고정)"
    print("✅ TeslaCoil — 패시브 수동 발동 (대상 지정)")

    # Shatter — 전체 7딜 + 모든 오브 2회 이보크
    combat4, player4, (dummy4,) = make_combat()
    q4 = player4.orb_queue
    q4.channel(FrostOrb(), player4, combat4)
    q4.channel(FrostOrb(), player4, combat4)
    hp0 = dummy4.current_hp
    play(combat4, "shatter", dummy4, energy=3)
    assert hp0 - dummy4.current_hp == 7, "전체 7딜"
    assert player4.block == 5 * 4, "서리 2개 × 이보크 2회 = 블록 20"
    assert len(q4) == 0, "모든 오브 소진"
    print("✅ Shatter — 오브별 2회 이보크 후 전부 제거")


def test_turn_loop_powers():
    print("\n=== 턴 루프 파워 (Coolant/Hailstorm/Loop/ConsumingShadow/"
          "LightningRod/Spinner/Thunder) ===\n")
    combat, player, (dummy,) = make_combat()
    queue = player.orb_queue
    play(combat, "coolant", energy=3)
    queue.channel(FrostOrb(), player, combat)
    queue.channel(DarkOrb(), player, combat)
    player._powers["coolant"].on_turn_start()
    assert player.block == 4, "Coolant — 종류 2 × 2블록"
    play(combat, "hailstorm", energy=3)
    hp0 = dummy.current_hp
    player._powers["hailstorm"].on_turn_end()
    assert hp0 - dummy.current_hp == 6, "Hailstorm — 서리 보유 → 전체 6"
    play(combat, "loop", energy=3)
    blk0 = player.block
    player._powers["loop"].on_turn_start()
    assert player.block == blk0 + 2, "Loop — 선두 서리 패시브 +2블록"
    print("✅ Coolant/Hailstorm/Loop")

    # ConsumingShadow — 턴 종료 시 최신 오브 이보크
    # 채널 2개째에 슬롯(3) 초과 → 선두 서리 이보크, 큐 [D, D, D]
    play(combat, "consuming_shadow", energy=3)
    hp0 = dummy.current_hp
    player._powers["consuming_shadow"].on_turn_end()
    assert hp0 - dummy.current_hp == 6, "최신 어둠 오브 이보크 (6)"
    assert len(queue) == 2
    print("✅ ConsumingShadow — EvokeLast")

    # Thunder — 라이트닝 이보크마다 대상에 추가 피해
    combat2, player2, (dummy2,) = make_combat()
    play(combat2, "thunder", energy=3)
    player2.orb_queue.channel(LightningOrb(), player2, combat2)
    hp0 = dummy2.current_hp
    player2.orb_queue.evoke_next(combat2)
    assert hp0 - dummy2.current_hp == 8 + 6, "이보크 8 + Thunder 6"
    print("✅ Thunder — 이보크 훅")

    # LightningRod / Spinner / EnergyNextTurn — 에너지 리셋 훅
    combat3, player3, (dummy3,) = make_combat()
    play(combat3, "lightning_rod", energy=3)
    play(combat3, "spinner", energy=3)
    play(combat3, "charge_battery", energy=3)
    player3.energy = 3
    combat3.notify_player_powers("after_energy_reset")
    assert player3.energy == 4, "EnergyNextTurn +1"
    ids = [o.orb_id for o in player3.orb_queue.orbs]
    assert ids.count("lightning") == 1 and ids.count("glass") == 1
    assert player3.get_power_amount("lightning_rod") == 1, "스택 1 감소"
    assert player3.get_power_amount("energy_next_turn") == 0, "1회성 제거"
    print("✅ LightningRod/Spinner/ChargeBattery — AfterEnergyReset")


def test_defensive_and_energy():
    print("\n=== Buffer / DoubleEnergy / Sunder / Supercritical ===\n")
    combat, player, (dummy,) = make_combat()
    play(combat, "buffer", energy=3)
    hp0 = player.current_hp
    player.take_damage(15)
    assert player.current_hp == hp0, "Buffer — HP 손실 무효"
    assert player.get_power_amount("buffer") == 0
    player.take_damage(5)
    assert player.current_hp == hp0 - 5, "스택 소진 후 정상 피해"
    print("✅ Buffer")

    player.energy = 3
    play(combat, "double_energy")  # 1 지불 후 2 → 4
    assert player.energy == 4, f"DoubleEnergy 2→4 (실제 {player.energy})"
    play(combat, "supercritical")
    assert player.energy == 8, "Supercritical +4"
    print("✅ DoubleEnergy/Supercritical")

    # Sunder — 처치 시 에너지 +3
    combat2, player2, monsters2 = make_combat(("stabbot",))
    player2.energy = 3
    play(combat2, "sunder", monsters2[0])
    assert monsters2[0].is_dead and player2.energy == 0 + 3, "처치 → +3"
    print("✅ Sunder — 막타 에너지 환급")


def test_draw_and_generation():
    print("\n=== 드로우/생성 (Skim/Reboot/Scrape/AllForOne/Hologram/"
          "WhiteNoise/CreativeAI/Iteration/MachineLearning) ===\n")
    combat, player, (dummy,) = make_combat()
    combat.draw_pile.extend(create_card("strike") for _ in range(8))
    hand0 = len(combat.hand)
    play(combat, "skim", energy=3)
    assert len(combat.hand) == hand0 + 3
    # Reboot — 손패를 드로우 더미로 섞고 4장
    play(combat, "reboot")
    assert len(combat.hand) == 4, "Reboot 드로우 4"
    print("✅ Skim/Reboot")

    # Scrape — 드로우 후 비용≠0 버리기
    combat2, player2, (dummy2,) = make_combat()
    combat2.draw_pile = [create_card("strike"), create_card("beam_cell"),
                         create_card("leap"), create_card("hotfix")]
    play(combat2, "scrape", dummy2, energy=3)
    hand_ids = {c.card_id for c in combat2.hand}
    assert hand_ids == {"beam_cell", "hotfix"}, f"0코스트만 유지: {hand_ids}"
    assert {c.card_id for c in combat2.discard_pile} >= {"strike", "leap"}
    print("✅ Scrape — 비용 있는 드로우 버리기")

    # AllForOne — 버림 더미 0코스트 회수
    combat3, player3, (dummy3,) = make_combat()
    combat3.discard_pile = [create_card("beam_cell"), create_card("turbo"),
                            create_card("leap"), create_card("wound")]
    play(combat3, "all_for_one", dummy3, energy=3)
    hand_ids = [c.card_id for c in combat3.hand]
    assert "beam_cell" in hand_ids and "turbo" in hand_ids
    assert "leap" not in hand_ids and "wound" not in hand_ids, "상태이상 제외"
    print("✅ AllForOne — 0코스트 공격/스킬/파워만")

    # WhiteNoise — 무작위 파워 카드, 이번 턴 무료
    combat4, player4, (dummy4,) = make_combat()
    play(combat4, "white_noise", energy=3)
    powers = [c for c in combat4.hand if c.card_type == CardType.POWER]
    assert len(powers) == 1 and combat4.get_card_cost(powers[0]) == 0
    print("✅ WhiteNoise — 파워 생성 + 이번 턴 무료")

    # CreativeAI — 드로우 전 파워 카드 생성
    combat5, player5, (dummy5,) = make_combat()
    play(combat5, "creative_ai", energy=3)
    combat5.notify_player_powers("before_hand_draw", combat5)
    assert sum(1 for c in combat5.hand if c.card_type == CardType.POWER) == 1
    print("✅ CreativeAI")

    # Iteration — 첫 상태이상 드로우 → 추가 드로우
    combat6, player6, (dummy6,) = make_combat()
    play(combat6, "iteration", energy=3)
    combat6.draw_pile = [create_card("strike"), create_card("strike"),
                         create_card("wound")]
    combat6.draw_cards(1)  # wound → 2장 추가 드로우
    assert len(combat6.hand) == 3, "Iteration 상태이상 → +2 드로우"
    print("✅ Iteration")

    # MachineLearning — 드로우 수정
    combat7, player7, (dummy7,) = make_combat()
    play(combat7, "machine_learning", energy=3)
    ml = player7._powers["machine_learning"]
    assert ml.modify_hand_draw(5) == 6
    print("✅ MachineLearning +1 드로우")


def test_misc_cards():
    print("\n=== 기타 (GoForTheEyes/GeneticAlgorithm/BulkUp/Capacitor/"
          "Uproar/Chill/Chaos) ===\n")
    # GoForTheEyes — 공격 인텐트에만 약화
    combat, player, monsters = make_combat(("stabbot",), seed=3)
    play(combat, "go_for_the_eyes", monsters[0], energy=3)
    assert monsters[0].get_power_amount("weak") == 1, "공격 인텐트 → 약화"
    print("✅ GoForTheEyes — 인텐트 조건 약화")

    # GeneticAlgorithm — 영구 성장 (전투 넘어 유지)
    ga = create_card("genetic_algorithm")
    combat2, player2, (dummy2,) = make_combat()
    combat2.hand.append(ga)
    combat2.play_card(ga)
    assert player2.block == 1 and ga.increased_block == 3
    combat2._finish(True)
    assert ga.increased_block == 3, "전투 종료에도 유지 (덱 레벨)"
    combat3, player3, (dummy3,) = make_combat()
    combat3.hand.append(ga)
    combat3.play_card(ga)
    assert player3.block == 4, "1 + 누적 3"
    print("✅ GeneticAlgorithm — 런 영구 블록 성장")

    # BulkUp / Capacitor — 슬롯 증감
    combat4, player4, (dummy4,) = make_combat()
    play(combat4, "bulk_up", energy=3)
    assert player4.orb_queue.slot_count == 2
    assert player4.get_power_amount("strength") == 2
    assert player4.get_power_amount("dexterity") == 2
    play(combat4, "capacitor", energy=3)
    assert player4.orb_queue.slot_count == 4
    print("✅ BulkUp -1슬롯/+힘민첩, Capacitor +2슬롯")

    # Uproar — 드로우 더미 공격 자동 플레이
    combat5, player5, (dummy5,) = make_combat()
    combat5.draw_pile = [create_card("beam_cell")]
    hp0 = dummy5.current_hp
    play(combat5, "uproar", dummy5, energy=3)
    assert hp0 - dummy5.current_hp == 12 + 3, "6×2 + 자동 BeamCell 3"
    print("✅ Uproar — 자동 플레이")

    # Chill — 적 수만큼 서리
    combat6, player6, monsters6 = make_combat(("big_dummy", "big_dummy"))
    play(combat6, "chill", energy=3)
    assert len(player6.orb_queue) == 2, "적 2 → 서리 2"
    # Chaos — 무작위 채널
    play(combat6, "chaos", upgraded=True)
    assert len(player6.orb_queue) == 3, "슬롯 3 상한 (초과 채널은 이보크)"
    print("✅ Chill/Chaos")


def test_full_combat_and_runs():
    print("\n=== 통합: Defect 전투/런 ===\n")
    player = Player(create_character("defect"))
    monsters = [create_monster("twig_slime_s"), create_monster("twig_slime_s")]
    combat = CombatState(player, monsters, seed=7)
    result = combat.run(GreedyPolicy())
    print(f"전투: {'승리' if result.victory else '패배'} {result.turns}턴, "
          f"HP {result.player_hp}")

    wins = floors = 0
    for seed in range(10):
        run = RunState("defect", seed=seed)
        res = run.play(GreedyPolicy())
        wins += res.victory
        floors += res.floors_cleared
    print(f"✅ 10시드 런: {wins}승, 평균 {floors / 10:.1f}층 도달")


if __name__ == "__main__":
    test_pool_registration()
    test_orb_queue_engine()
    test_focus_and_temp_focus()
    test_claw_and_combat_cost_mutations()
    test_calculated_attacks()
    test_echo_form_and_doublers()
    test_feral_returns_attacks()
    test_power_play_triggers()
    test_status_generation_hooks()
    test_status_cards_and_compact()
    test_evoke_cards()
    test_turn_loop_powers()
    test_defensive_and_energy()
    test_draw_and_generation()
    test_misc_cards()
    test_full_combat_and_runs()
    print("\n🎉 Phase 6d 전체 테스트 통과!")
