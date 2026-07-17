#!/usr/bin/env python3
"""
STS2 Phase 6g 통합 테스트.
Colorless 카드 풀 65종 (디컴파일 ColorlessCardPool 전량, Common 등급 없음
— Uncommon 40 / Rare 25) + 신규 파워 16종 (Automation/BeaconOfHope/Calamity/
Entropy/Fasten/Knockdown/Mayhem/NoBlock/Nostalgia/Panache/PrepTime/
RollingBoulder/Stratagem/TagTeam/TheBomb/TheGambit).
DarkShackles/Coordinate는 기존 TempStrength(Regent Phase 6f) 재사용.
"""
import sts2_sim  # noqa: F401 — CARD_REGISTRY 등록
from sts2_sim.core.combat import CombatState
from sts2_sim.core.policy import GreedyPolicy
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import create_monster
from sts2_sim.models.sts2_card import CARD_REGISTRY, CardType, Rarity, create_card
from sts2_sim.cards.colorless import _COLORLESS_CARDS, COLORLESS_POOL_BY_RARITY


def make_combat(character_id="ironclad", monster_ids=("big_dummy",), seed=42):
    player = Player(create_character(character_id))
    monsters = [create_monster(mid) for mid in monster_ids]
    combat = CombatState(player, monsters, seed=seed)
    combat.start()
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
    assert ok, f"{card_id} 플레이 실패 (에너지 {combat.player.energy})"
    return card


def _enemy(combat):
    return combat.alive_enemies[0]


# ══════════════════════════════════════════

def test_pool_registration():
    print("=== 카드 풀 등록 ===\n")
    uncommon = COLORLESS_POOL_BY_RARITY[Rarity.UNCOMMON]
    rare = COLORLESS_POOL_BY_RARITY[Rarity.RARE]
    assert len(uncommon) == 40, len(uncommon)
    assert len(rare) == 25, len(rare)
    assert Rarity.COMMON not in COLORLESS_POOL_BY_RARITY  # 원본부터 Common 없음
    assert len(_COLORLESS_CARDS) == 65, len(_COLORLESS_CARDS)
    for cls in _COLORLESS_CARDS:
        assert cls.card_id in CARD_REGISTRY, cls.card_id
    print(f"✅ Colorless 65종 등록 (U{len(uncommon)}/R{len(rare)}), Common 없음")


def test_gang_up_flat_damage():
    print("\n=== GangUp: 아군 없음 → 항상 기본 5딜 ===\n")
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    play(combat, "gang_up", target=enemy)
    assert h0 - enemy.current_hp == 5, h0 - enemy.current_hp
    print("✅ GangUp: 5딜 고정")


def test_gold_axe_scaling():
    print("\n=== GoldAxe: 완료된 카드 플레이 수만큼 딜 ===\n")
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    play(combat, "strike", target=enemy)
    play(combat, "strike", target=enemy)
    h0 = enemy.current_hp
    play(combat, "gold_axe", target=enemy)  # 앞선 2장 완료 → 2딜
    assert h0 - enemy.current_hp == 2, h0 - enemy.current_hp
    gold_axe = create_card("gold_axe")
    gold_axe.upgrade()
    assert gold_axe.retains is True
    print("✅ GoldAxe: 완료 플레이 수 스케일 + 업글 Retain")


def test_the_ball_escalation():
    print("\n=== TheBall: 플레이마다 영구 데미지 증가 + 뽑을더미 무작위 귀환 ===\n")
    combat, player, _ = make_combat()
    ball = create_card("the_ball")
    assert ball.settle_to == "draw_random"
    enemy = _enemy(combat)
    combat.hand.append(ball)
    combat.player.energy = 6
    h0 = enemy.current_hp
    combat.play_card(ball, enemy)
    assert h0 - enemy.current_hp == 10, h0 - enemy.current_hp
    assert ball._current_damage == 25, ball._current_damage  # 10+15
    assert ball not in combat.discard_pile
    assert ball in combat.draw_pile
    print("✅ TheBall: 10딜 → 다음 데미지 25로 누적, 버림 대신 뽑을더미로")


def test_rend_debuff_scaling():
    print("\n=== Rend: 대상의 지속 디버프 수만큼 추가 피해 ===\n")
    from sts2_sim.models.sts2_power import Frail, Weak
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    enemy.apply_power(Frail(2))
    enemy.apply_power(Weak(2))
    h0 = enemy.current_hp
    play(combat, "rend", target=enemy)  # 15 + 5×2 = 25
    assert h0 - enemy.current_hp == 25, h0 - enemy.current_hp
    print("✅ Rend: 디버프 2개 → 15+5×2=25딜")


def test_fisticuffs_block_from_damage():
    print("\n=== Fisticuffs: 준 피해만큼 블록 ===\n")
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    b0 = player.block
    play(combat, "fisticuffs", target=enemy)  # 7딜
    assert player.block - b0 == 7, player.block - b0
    print("✅ Fisticuffs: 7딜 → 블록 +7")


def test_omnislice_splash():
    print("\n=== Omnislice: 다른 모든 적에게 Unpowered 스플래시 ===\n")
    combat, player, _ = make_combat(monster_ids=("big_dummy", "big_dummy", "big_dummy"))
    e0, e1, e2 = combat.alive_enemies
    h1, h2 = e1.current_hp, e2.current_hp
    play(combat, "omnislice", target=e0)  # 8딜 대상 + 8 스플래시 나머지
    assert h1 - e1.current_hp == 8, h1 - e1.current_hp
    assert h2 - e2.current_hp == 8, h2 - e2.current_hp
    print("✅ Omnislice: 대상 외 모든 적에게 동일 피해 스플래시")


def test_hand_of_greed_gold_on_kill():
    print("\n=== HandOfGreed: 처치 시 골드 ===\n")
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    enemy._current_hp = 5
    g0 = player.character.gold
    play(combat, "hand_of_greed", target=enemy)
    assert enemy.is_dead
    assert player.character.gold == g0 + 20, player.character.gold
    print("✅ HandOfGreed: 처치 시 골드 +20")


def test_mind_blast_draw_pile_scaling():
    print("\n=== MindBlast: 뽑을 더미 장수만큼 딜 ===\n")
    combat, player, _ = make_combat()
    combat.draw_pile = [create_card("strike") for _ in range(6)]
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    play(combat, "mind_blast", target=enemy)
    assert h0 - enemy.current_hp == 6, h0 - enemy.current_hp
    mb = create_card("mind_blast")
    assert mb.is_innate is True
    print("✅ MindBlast: 뽑을더미 6장 → 6딜, 선천성")


def test_volley_x_cost_random_targets():
    print("\n=== Volley: X코스트 전량 소비, 무작위 적 히트 ===\n")
    combat, player, _ = make_combat(monster_ids=("big_dummy", "big_dummy"))
    hp_before = {id(m): m.current_hp for m in combat.alive_enemies}
    play(combat, "volley", energy=3)
    total_lost = sum(hp_before[id(m)] - m.current_hp for m in combat.alive_enemies)
    assert total_lost == 30, total_lost  # 10 × 3
    assert player.energy == 0
    print("✅ Volley: 에너지 3 전량 소비 → 총 30딜(무작위 분배)")


def test_bolas_and_thrumming_hatchet_boomerang():
    print("\n=== Bolas/ThrummingHatchet: 직전 턴 플레이 시 손패 복귀 ===\n")
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    bolas = play(combat, "bolas", target=enemy)
    assert bolas in combat.discard_pile
    for pile in (combat.discard_pile, combat.draw_pile):
        for card in list(pile):
            hook = getattr(card, "on_before_hand_draw", None)
            if hook:
                hook(combat)
    assert bolas in combat.hand, "Bolas가 다음 턴 드로우 전 손패로 복귀해야 함"
    assert bolas not in combat.discard_pile
    print("✅ Bolas: 직전 턴 플레이 → 다음 턴 드로우 전 손패 복귀")


def test_mayhem_auto_play_from_draw_pile():
    print("\n=== Mayhem: 매 선플레이 페이즈마다 뽑을더미 맨 위 자동 플레이 ===\n")
    combat, player, _ = make_combat()
    play(combat, "mayhem")  # MayhemP(1)
    combat.draw_pile = [create_card("strike")]
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    combat.notify_player_powers("on_pre_play_phase", combat)
    assert h0 - enemy.current_hp == 6, h0 - enemy.current_hp
    assert not combat.draw_pile
    print("✅ Mayhem: 뽑을더미 맨 위 카드 자동 플레이")


def test_nostalgia_settle_override():
    print("\n=== Nostalgia: 이번 턴 첫 카드는 버림 대신 뽑을더미 맨 위로 ===\n")
    combat, player, _ = make_combat()
    play(combat, "nostalgia")  # NostalgiaP(1)
    enemy = _enemy(combat)
    strike = play(combat, "strike", target=enemy)  # 이번 턴 1번째 공격/스킬 플레이
    assert strike in combat.draw_pile and strike not in combat.discard_pile
    strike2 = play(combat, "strike", target=enemy)  # 2번째 → 정상 버림
    assert strike2 in combat.discard_pile
    print("✅ Nostalgia: 첫 1장만 뽑을더미 맨 위, 이후는 정상 버림")


def test_stratagem_after_shuffle():
    print("\n=== Stratagem: 셔플 시 무작위 카드 손패로 ===\n")
    combat, player, _ = make_combat()
    play(combat, "stratagem")  # StratagemP(1)
    combat.draw_pile = []
    combat.discard_pile = [create_card("strike") for _ in range(5)]
    combat.hand = []
    combat._reshuffle()
    assert len(combat.hand) == 1, len(combat.hand)
    assert len(combat.draw_pile) == 4, len(combat.draw_pile)
    print("✅ Stratagem: 셔플 후 무작위 1장 손패로 이동")


def test_panache_aoe_every_fifth_play():
    print("\n=== Panache: 5장째 플레이마다 전체 피해 ===\n")
    combat, player, _ = make_combat()
    play(combat, "panache")  # PanacheP(10), 자기 자신이 1번째(already_applied만 세팅, 감소 없음)
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    for _ in range(4):
        play(combat, "strike", target=enemy)  # 2~5번째 플레이 → cards_left 5→1(4회 감소)
    assert enemy.current_hp == h0 - 4 * 6, "스트라이크 피해만 있어야 함"
    play(combat, "strike", target=enemy)  # 6번째 플레이(5회째 감소) → cards_left 0 → 발동
    lost = h0 - enemy.current_hp
    assert lost == 5 * 6 + 10, lost
    print("✅ Panache: 6번째(감소 5회째) 플레이에서 전체 10 피해 발동")


def test_rolling_boulder_escalation():
    print("\n=== RollingBoulder: 매 턴 시작 피해 + 누적 ===\n")
    combat, player, _ = make_combat()
    play(combat, "rolling_boulder")  # RollingBoulderP(5)
    power = player._powers["rolling_boulder"]
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    power.on_turn_start()
    assert h0 - enemy.current_hp == 5, h0 - enemy.current_hp
    assert power.amount == 10, power.amount
    h1 = enemy.current_hp
    power.on_turn_start()
    assert h1 - enemy.current_hp == 10, h1 - enemy.current_hp
    print("✅ RollingBoulder: 5딜 → 10 누적 → 10딜")


def test_the_bomb_explosion():
    print("\n=== TheBomb: N턴 후 폭발 ===\n")
    combat, player, _ = make_combat()
    play(combat, "the_bomb")  # TheBombP(3), damage=40
    power = player._powers["the_bomb"]
    enemy = _enemy(combat)
    power.on_turn_end()
    assert power.amount == 2
    power.on_turn_end()
    assert power.amount == 1
    h0 = enemy.current_hp
    power.on_turn_end()  # 폭발
    assert h0 - enemy.current_hp == 40, h0 - enemy.current_hp
    assert "the_bomb" not in player._powers
    print("✅ TheBomb: 3턴째에 40 피해 후 파워 제거")


def test_rolling_boulder_instanced_stacking():
    print("\n=== RollingBoulder: Instanced — 재적용 시 독립 인스턴스 추가 ===\n")
    combat, player, _ = make_combat()
    play(combat, "rolling_boulder")  # 1번째 인스턴스 (5)
    play(combat, "rolling_boulder")  # 2번째 인스턴스 (5) — 병합되지 않고 독립 추가
    power = player._powers["rolling_boulder"]
    assert power._instances == [5, 5], power._instances
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    power.on_turn_start()  # 5+5=10 피해, 이후 각각 10으로 성장
    assert h0 - enemy.current_hp == 10, h0 - enemy.current_hp
    assert power._instances == [10, 10], power._instances
    assert power.amount == 20, power.amount
    h1 = enemy.current_hp
    power.on_turn_start()  # 10+10=20 피해
    assert h1 - enemy.current_hp == 20, h1 - enemy.current_hp
    print("✅ RollingBoulder 2장: 병합 대신 독립 성장(5+5→10+10→20 피해)")


def test_the_bomb_instanced_stacking():
    print("\n=== TheBomb: Instanced — 재적용 시 독립 인스턴스 추가 ===\n")
    combat, player, _ = make_combat()
    play(combat, "the_bomb")  # 1번째 폭탄: 3턴, 40딜
    play(combat, "the_bomb", upgraded=True)  # 2번째 폭탄(독립): 3턴, 50딜
    power = player._powers["the_bomb"]
    assert power._instances == [[3, 40], [3, 50]], power._instances
    assert power.amount == 6, power.amount  # 두 인스턴스 턴수 합(get_power_amount 호환)
    enemy = _enemy(combat)
    power.on_turn_end()  # 둘 다 3→2
    power.on_turn_end()  # 둘 다 2→1
    h0 = enemy.current_hp
    power.on_turn_end()  # 둘 다 1→0 → 각자 개별 폭발
    assert h0 - enemy.current_hp == 90, h0 - enemy.current_hp  # 40+50, 소실 없음
    assert "the_bomb" not in player._powers
    print("✅ TheBomb 2장(비강화+강화): 3턴 후 각자 개별 폭발(40+50=90)")


def test_panic_button_no_block():
    print("\n=== PanicButton: 큰 블록 + 2턴간 블록 차단 ===\n")
    combat, player, _ = make_combat()
    play(combat, "panic_button")  # 30블록 + NoBlockP(2)
    assert player.block == 30, player.block
    b0 = player.block
    play(combat, "defend")  # 파워드 블록 → 차단
    assert player.block == b0, player.block
    power = player._powers["no_block"]
    power.on_enemy_turn_end()
    assert power.amount == 1
    power.on_enemy_turn_end()
    assert "no_block" not in player._powers
    b1 = player.block
    play(combat, "defend")
    assert player.block > b1, "차단 해제 후 정상 블록"
    print("✅ PanicButton: 블록 차단 2턴 후 해제")


def test_panic_button_exempts_power_sourced_block():
    print("\n=== PanicButton: 카드 유래 블록만 차단, 파워 유래 블록은 면제 ===\n")
    from sts2_sim.models.sts2_power import Metallicize
    combat, player, _ = make_combat()
    play(combat, "panic_button")  # NoBlockP(2)
    player.apply_power(Metallicize(5))
    b0 = player.block
    metallicize = player._powers["metallicize"]
    metallicize.on_turn_end()  # 파워 유래 블록 — cardSource == null → 면제
    assert player.block - b0 == 5, player.block - b0
    b1 = player.block
    play(combat, "defend")  # 카드 유래 블록 — 계속 차단
    assert player.block == b1, player.block
    print("✅ PanicButton 중 Metallicize(파워)는 블록 획득, Defend(카드)는 여전히 차단")


def test_the_gambit_instakill():
    print("\n=== TheGambit: 다음 파워드 피격 시 즉사 ===\n")
    combat, player, monsters = make_combat(monster_ids=("stabbot",))
    play(combat, "the_gambit")  # 50블록 + TheGambitP(1)
    assert player.block == 50, player.block
    enemy = monsters[0]
    player._block = 0  # 블록 없이 직격 시뮬레이션
    enemy.attack(player, 11)
    assert player.is_dead, "파워드 공격 비차단 피해 → 즉사해야 함"
    print("✅ TheGambit: 파워드 비차단 피해 → 즉시 사망")


def test_the_gambit_ignores_unpowered_reflect():
    print("\n=== TheGambit: Thorns/FlameBarrier Unpowered 반사 피해는 무시 ===\n")
    from sts2_sim.models.sts2_power import Thorns
    combat, player, monsters = make_combat(monster_ids=("stabbot",))
    play(combat, "the_gambit")  # 50블록 + TheGambitP(1)
    enemy = monsters[0]
    enemy.apply_power(Thorns(5))
    player._block = 0
    play(combat, "strike", target=enemy)  # 플레이어 공격 → 적 Thorns 반격(Unpowered)
    assert not player.is_dead, "Thorns Unpowered 반격은 TheGambit을 발동시키면 안 됨"
    assert "the_gambit" in player._powers, "TheGambitP는 소모되지 않고 유지되어야 함"
    print("✅ TheGambit: Thorns Unpowered 반사 피해로는 사망하지 않음(파워도 유지)")


def test_prep_time_vigor():
    print("\n=== PrepTime: 매 턴 시작 Vigor ===\n")
    combat, player, _ = make_combat()
    play(combat, "prep_time")  # PrepTimeP(4)
    power = player._powers["prep_time"]
    power.on_turn_start()
    assert player.get_power_amount("vigor") == 4, player.get_power_amount("vigor")
    print("✅ PrepTime: 턴 시작마다 Vigor +4")


def test_automation_energy_every_10_draws():
    print("\n=== Automation: 10장 뽑을 때마다 에너지 ===\n")
    combat, player, _ = make_combat()
    play(combat, "automation")  # AutomationP(1)
    combat.draw_pile = [create_card("strike") for _ in range(11)]
    combat.hand = []
    e0 = player.energy
    combat.draw_cards(9)
    assert player.energy == e0, "9장은 아직 발동 전"
    combat.draw_cards(1)  # 10번째
    assert player.energy == e0 + 1, player.energy
    print("✅ Automation: 10장째 드로우에서 에너지 +1")


def test_automation_instanced_stacking():
    print("\n=== Automation: Instanced — 오프셋 있는 두 카운터가 개별 발동 ===\n")
    combat, player, _ = make_combat()
    combat.draw_pile = [create_card("strike") for _ in range(30)]
    combat.hand = []
    play(combat, "automation")  # 1번째 카운터: 10에서 시작
    combat.draw_cards(4)        # 1번째 카운터 10→6 (아직 미발동)
    play(combat, "automation")  # 2번째 카운터(독립): 10에서 새로 시작 — 오프셋 발생
    e0 = player.energy
    combat.draw_cards(6)        # 1번째 6→0(발동,+1) / 2번째 10→4
    assert player.energy == e0 + 1, player.energy
    combat.draw_cards(4)        # 2번째 4→0(발동,+1)
    assert player.energy == e0 + 2, player.energy
    print("✅ Automation 2장(오프셋): 병합된 단일 카운터가 아니라 서로 다른 시점에 개별 발동")


def test_panache_instanced_stacking():
    print("\n=== Panache: Instanced — 오프셋 있는 두 카운터가 개별 발동 ===\n")
    from sts2_sim.models.sts2_power import PanacheP
    combat, player, _ = make_combat()
    player.apply_power(PanacheP(10))
    power = player._powers["panache"]
    power._instances[0]["applied"] = True
    power._instances[0]["left"] = 2  # 1번째: 2번만 더 감소하면 발동
    player.apply_power(PanacheP(14))  # 2번째 인스턴스(독립) 추가 — 병합되지 않음
    assert len(power._instances) == 2, power._instances
    power._instances[1]["applied"] = True
    power._instances[1]["left"] = 5  # 2번째: 아직 멀었음(오프셋)
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    strike = create_card("strike")
    power.on_card_played(strike, combat)  # 1번째 2→1, 2번째 5→4 (둘 다 미발동)
    assert enemy.current_hp == h0
    power.on_card_played(strike, combat)  # 1번째 1→0(발동,+10) / 2번째 4→3(대기)
    assert h0 - enemy.current_hp == 10, h0 - enemy.current_hp
    print("✅ Panache 2장(오프셋): 1번째 인스턴스만 먼저 발동, 2번째는 대기 중")


def test_calamity_generates_attack_cards():
    print("\n=== Calamity: 공격 카드 플레이마다 소유 캐릭터 풀 공격카드 생성 ===\n")
    combat, player, _ = make_combat(character_id="ironclad")
    play(combat, "calamity")  # CalamityP(1)
    enemy = _enemy(combat)
    g0 = combat.cards_generated_this_combat
    n0 = len(combat.hand)  # calamity 재생 직후(손패 미포함), strike는 아직 추가 전
    play(combat, "strike", target=enemy)
    assert combat.cards_generated_this_combat == g0 + 1, combat.cards_generated_this_combat
    assert len(combat.hand) == n0 + 1, len(combat.hand)  # strike 추가 후 제거(±0) + 생성(+1)
    print("✅ Calamity: 공격 카드 플레이 후 캐릭터풀 공격카드 1장 생성")


def test_entropy_transforms_hand_card():
    print("\n=== Entropy: 턴 시작 시 손패 카드 변환 ===\n")
    combat, player, _ = make_combat(character_id="ironclad")
    play(combat, "entropy")  # EntropyP(1)
    power = player._powers["entropy"]
    combat.hand = [create_card("strike")]
    power.on_turn_start()
    assert len(combat.hand) == 1
    assert combat.hand[0].card_id != "strike", combat.hand[0].card_id
    print(f"✅ Entropy: strike → {combat.hand[0].card_id}로 변환")


def test_discovery_jack_and_jackpot_generation():
    print("\n=== Discovery/JackOfAllTrades/Jackpot: 카드 생성 ===\n")
    combat, player, _ = make_combat(character_id="ironclad")
    combat.hand = []
    play(combat, "discovery")
    assert len(combat.hand) == 1, len(combat.hand)
    assert combat.hand[0]._free_this_turn is True

    combat2, player2, _ = make_combat(character_id="ironclad")
    combat2.hand = []
    play(combat2, "jack_of_all_trades", upgraded=True)
    assert len(combat2.hand) == 2, len(combat2.hand)
    assert len(set(c.card_id for c in combat2.hand)) == 2, "서로 다른 카드여야 함"

    combat3, player3, _ = make_combat(character_id="ironclad")
    enemy = _enemy(combat3)
    combat3.hand = []
    play(combat3, "jackpot", target=enemy)
    assert len(combat3.hand) == 3, len(combat3.hand)
    for c in combat3.hand:
        assert c.cost == 0 and not c.x_cost
    print("✅ Discovery(1장,무료)/JackOfAllTrades(서로 다른 2장)/Jackpot(0코스트 3장)")


def test_fasten_defend_bonus():
    print("\n=== Fasten: Defend 태그 카드 블록 가산 ===\n")
    combat, player, _ = make_combat()
    play(combat, "fasten")  # FastenP(4)
    b0 = player.block
    play(combat, "defend")  # 5 + 4
    assert player.block - b0 == 9, player.block - b0
    b1 = player.block
    play(combat, "ultimate_defend")  # 11 + 4
    assert player.block - b1 == 15, player.block - b1
    b2 = player.block
    play(combat, "strike", target=_enemy(combat))  # Strike는 Defend 태그 아님 → 가산 없음
    print("✅ Fasten: Defend 태그 카드에만 고정 블록 가산")


def test_dark_shackles_blocked_by_artifact():
    print("\n=== DarkShackles/Coordinate: TempStrength 부호별 Artifact 상호작용 ===\n")
    from sts2_sim.models.sts2_power import Artifact
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    enemy.apply_power(Artifact(1))
    play(combat, "dark_shackles", target=enemy)
    assert enemy.get_power_amount("temp_strength") == 0, "음수 TempStrength는 Debuff → Artifact가 무효화해야 함"
    assert enemy.get_power_amount("artifact") == 0, "무효화 시 Artifact 1스택 소모"

    player.apply_power(Artifact(1))
    play(combat, "coordinate")
    assert player.get_power_amount("temp_strength") == 5, player.get_power_amount("temp_strength")
    assert player.get_power_amount("artifact") == 1, "양수 TempStrength는 Buff → Artifact가 소모되면 안 됨"
    print("✅ DarkShackles(음수)는 Artifact에 막히고, Coordinate(양수)는 막히지 않음")


def test_character_pool_excludes_cannot_generate_in_combat():
    print("\n=== 캐릭터 카드풀 생성 헬퍼: CanBeGeneratedInCombat=false 카드 제외 ===\n")
    from sts2_sim.cards.colorless import _character_pool_ids, _COLORLESS_GENERATABLE_IDS
    _, player, _ = make_combat(character_id="ironclad")
    pool = _character_pool_ids(player)
    assert "feed" not in pool, "Feed는 CanBeGeneratedInCombat=false"
    assert "not_yet" not in pool, "NotYet은 CanBeGeneratedInCombat=false"
    assert "hand_of_greed" not in _COLORLESS_GENERATABLE_IDS
    assert "hidden_gem" not in _COLORLESS_GENERATABLE_IDS
    print("✅ Feed/NotYet/HandOfGreed/HiddenGem은 전투 중 카드 생성 후보에서 제외")


def test_hidden_gem_fallback_preserves_replay_filter():
    print("\n=== HiddenGem: 폴백 시에도 재생 미보유 조건 유지 ===\n")
    combat, player, _ = make_combat()
    replayed = create_card("strike")
    replayed._extra_plays = 1  # 이미 리플레이 보유 — 폴백에서도 후보 제외되어야 함
    combat.draw_pile = [replayed]
    play(combat, "hidden_gem")
    assert replayed._extra_plays == 1, replayed._extra_plays
    print("✅ HiddenGem: 이미 Replay가 걸린 카드는 폴백 후보에서도 제외됨")


def test_entropy_no_force_upgrade():
    print("\n=== Entropy: 원본 카드 강화 상태를 대체 카드에 강제 이전하지 않음 ===\n")
    combat, player, _ = make_combat(character_id="ironclad")
    play(combat, "entropy")  # EntropyP(1)
    power = player._powers["entropy"]
    upgraded_strike = create_card("strike")
    upgraded_strike.upgrade()
    combat.hand = [upgraded_strike]
    power.on_turn_start()
    assert len(combat.hand) == 1
    assert combat.hand[0].card_id != "strike", combat.hand[0].card_id
    assert not combat.hand[0].upgraded, "원본 Transform 파이프라인은 강화 상태를 전달하지 않음"
    print(f"✅ Entropy: 강화된 strike → 비강화 {combat.hand[0].card_id}로 변환")


def test_dexterity_ignores_unpowered_block():
    print("\n=== Dexterity: Unpowered 블록(파워 반응형)에는 적용 안 됨 ===\n")
    from sts2_sim.models.sts2_power import Dexterity, Metallicize
    combat, player, _ = make_combat()
    player.apply_power(Dexterity(3))
    player.apply_power(Metallicize(5))
    b0 = player.block
    player._powers["metallicize"].on_turn_end()  # Unpowered 블록 — Dexterity 미적용
    assert player.block - b0 == 5, player.block - b0
    b1 = player.block
    play(combat, "defend")  # 카드(Move) 블록 — Dexterity 적용
    gained = player.block - b1
    assert gained == 5 + 3, gained
    print("✅ Dexterity: Metallicize(Unpowered) 미적용, Defend(카드) +3 적용")


def test_frail_ignores_unpowered_block():
    print("\n=== Frail: Unpowered 블록(파워 반응형)에는 적용 안 됨 ===\n")
    from sts2_sim.models.sts2_power import Frail, Metallicize
    combat, player, _ = make_combat()
    player.apply_power(Frail(99))
    player.apply_power(Metallicize(8))
    b0 = player.block
    player._powers["metallicize"].on_turn_end()  # Unpowered 블록 — Frail 미적용
    assert player.block - b0 == 8, player.block - b0
    b1 = player.block
    play(combat, "defend")  # 카드(Move) 블록 — Frail 0.75배 적용
    gained = player.block - b1
    assert gained == int(5 * 0.75), gained
    print("✅ Frail: Metallicize(Unpowered) 미적용, Defend(카드) 0.75배 적용")


def test_unmovable_ignores_unpowered_block():
    print("\n=== Unmovable: Unpowered 블록은 집계·배율 모두 제외 ===\n")
    from sts2_sim.models.sts2_power import Unmovable
    combat, player, _ = make_combat()
    player.apply_power(Unmovable(1))
    b0 = player.block
    player.gain_block(4, powered=False)  # Unpowered — 배율 미적용, 카운터도 소모 안 됨
    assert player.block - b0 == 4, player.block - b0
    b1 = player.block
    play(combat, "defend")  # 첫 카드/무브 블록 — 2배
    gained = player.block - b1
    assert gained == 5 * 2, gained
    print("✅ Unmovable: Unpowered 블록 미집계, 첫 카드 블록 2배 정상 적용")


def test_sleight_of_flesh_reflect_respects_block():
    print("\n=== SleightOfFlesh: 반사 피해가 블록으로 막힘 (Unpowered이지 Unblockable 아님) ===\n")
    from sts2_sim.models.sts2_power import Frail
    combat, player, monsters = make_combat(character_id="necrobinder")
    play(combat, "sleight_of_flesh")  # SoFP(9)
    enemy = monsters[0]
    enemy._block = 5
    hp0 = enemy.current_hp
    enemy.apply_power(Frail(2), applier=player)  # 디버프 부여 → 반사 9피해, 5블록 흡수
    assert enemy.block == 0, enemy.block
    assert hp0 - enemy.current_hp == 4, hp0 - enemy.current_hp  # 9 - 5(block) = 4
    print("✅ SleightOfFlesh: 반사 피해 9가 블록 5에 흡수되어 HP 4만 손실")


def test_vulnerable_ignores_unpowered_damage():
    print("\n=== Vulnerable: Unpowered 피해(반사·자해)에는 배율 미적용 ===\n")
    from sts2_sim.models.sts2_power import Vulnerable
    combat, player, monsters = make_combat()  # big_dummy — HP 넉넉
    enemy = monsters[0]
    enemy.apply_power(Vulnerable(2))
    hp0 = enemy.current_hp
    enemy.take_damage(10, source=player, powered=False)  # Unpowered — 배율 미적용
    assert hp0 - enemy.current_hp == 10, hp0 - enemy.current_hp
    hp1 = enemy.current_hp
    enemy.take_damage(10, source=player, powered=True)  # Powered — 1.5배
    assert hp1 - enemy.current_hp == 15, hp1 - enemy.current_hp
    print("✅ Vulnerable: Unpowered 피해 10 그대로, Powered 피해 10×1.5=15")


def test_colossus_ignores_unpowered_damage():
    print("\n=== Colossus: 취약 공격자의 Unpowered 피해에는 절반 배율 미적용 ===\n")
    from sts2_sim.models.sts2_power import Colossus, Vulnerable
    combat, player, monsters = make_combat(monster_ids=("stabbot",))
    enemy = monsters[0]
    player.apply_power(Colossus(1))
    enemy.apply_power(Vulnerable(2))  # 공격자(enemy)가 취약 보유
    hp0 = player.current_hp
    player.take_damage(10, source=enemy, powered=False)  # Unpowered — Colossus 미적용
    assert hp0 - player.current_hp == 10, hp0 - player.current_hp
    hp1 = player.current_hp
    player.take_damage(10, source=enemy, powered=True)  # Powered — 절반
    assert hp1 - player.current_hp == 5, hp1 - player.current_hp
    print("✅ Colossus: Unpowered 피해 10 그대로, Powered 피해 10→5(절반)")


def test_cruelty_respects_powered_gate():
    print("\n=== Cruelty: Unpowered 피해에는 취약 배율 증폭도 미적용 ===\n")
    from sts2_sim.models.sts2_power import Vulnerable, Cruelty
    combat, player, monsters = make_combat()  # big_dummy — HP 넉넉
    enemy = monsters[0]
    enemy.apply_power(Vulnerable(2))
    player.apply_power(Cruelty(50))  # 취약 배율 +0.5 (Powered에만 증폭)
    hp0 = enemy.current_hp
    enemy.take_damage(10, source=player, powered=False)  # Unpowered — 둘 다 미적용
    assert hp0 - enemy.current_hp == 10, hp0 - enemy.current_hp
    hp1 = enemy.current_hp
    enemy.take_damage(10, source=player, powered=True)  # Powered — (1.5+0.5)=2.0배
    assert hp1 - enemy.current_hp == 20, hp1 - enemy.current_hp
    print("✅ Cruelty: Unpowered 미적용, Powered 취약 배율 1.5→2.0 확인")


def test_intangible_cap_applies_after_multiplicative():
    print("\n=== Intangible: Vulnerable/Cruelty 배율과 무관하게 항상 1로 고정 "
          "(파워 적용 순서 무관) ===\n")
    from sts2_sim.models.sts2_power import Intangible, Vulnerable, Cruelty
    combat, player, monsters = make_combat()  # big_dummy — HP 넉넉
    dealer = player
    dealer.apply_power(Cruelty(50))

    target_a = monsters[0]
    target_a.apply_power(Intangible(2))
    target_a.apply_power(Vulnerable(3))
    r_a = target_a.take_damage(20, source=dealer, powered=True)
    assert r_a["hp_lost"] == 1, r_a  # Cap이 Multiplicative(1.5+0.5=2.0배)보다 나중에 적용

    combat2, _, monsters2 = make_combat()
    target_b = monsters2[0]
    target_b.apply_power(Vulnerable(3))   # 순서를 바꿔도(Vulnerable 먼저) 결과는 동일
    target_b.apply_power(Intangible(2))
    r_b = target_b.take_damage(20, source=dealer, powered=True)
    assert r_b["hp_lost"] == 1, r_b
    print("✅ Intangible: 파워 적용 순서와 무관하게 Cap이 Multiplicative 이후 최종 적용 (1로 고정)")


def test_regent_colorless_integration():
    print("\n=== Regent × Colorless 통합 (Quasar/BundleOfJoy/ManifestAuthority/"
          "HeirloomHammer/SpectrumShift) ===\n")
    all_ids = set(COLORLESS_POOL_BY_RARITY[Rarity.UNCOMMON]) | set(COLORLESS_POOL_BY_RARITY[Rarity.RARE])
    combat, player, _ = make_combat(character_id="regent")
    player.stars = 20

    n0 = len(combat.hand)
    play(combat, "quasar")  # Colorless 3장 중 1장 선택→무작위
    assert len(combat.hand) == n0 + 1, len(combat.hand)
    assert combat.hand[-1].card_id in all_ids, combat.hand[-1].card_id

    n1 = len(combat.hand)
    play(combat, "bundle_of_joy")  # Colorless 서로 다른 3장 생성
    assert len(combat.hand) == n1 + 3, len(combat.hand)
    generated = [c.card_id for c in combat.hand[n1:]]
    assert len(set(generated)) == 3, generated  # 서로 다른 카드(distinct)
    assert all(cid in all_ids for cid in generated), generated

    b0 = player.block
    n2 = len(combat.hand)
    play(combat, "manifest_authority")  # 7블록 + Colorless 1장
    assert player.block - b0 == 7, player.block - b0
    assert len(combat.hand) == n2 + 1, len(combat.hand)

    n3 = len(combat.hand)
    play(combat, "heirloom_hammer", target=_enemy(combat))  # 손패의 Colorless 1장 복제
    assert len(combat.hand) == n3 + 1, len(combat.hand)  # 복제 대상 존재 → 손패 +1

    play(combat, "spectrum_shift")  # SpectrumShiftP(1) — before_hand_draw 훅
    power = player._powers["spectrum_shift"]
    n4 = len(combat.hand)
    power.before_hand_draw(combat)
    assert len(combat.hand) == n4 + 1, len(combat.hand)
    assert combat.hand[-1].card_id in all_ids, combat.hand[-1].card_id
    print("✅ Regent Colorless 참조 카드 5종(Quasar/BundleOfJoy/ManifestAuthority/"
          "HeirloomHammer/SpectrumShift) 실제 생성 동작 확인")


def test_full_combats_all_cards():
    print("\n=== 전 카드 전투 스모크 (개별 플레이, 업글 포함) ===\n")
    fails = []
    for cls in _COLORLESS_CARDS:
        for upgraded in (False, True):
            for char_id in ("ironclad",):
                try:
                    player = Player(create_character(char_id))
                    monsters = [create_monster("big_dummy"), create_monster("big_dummy")]
                    combat = CombatState(player, monsters, seed=7)
                    combat.start()
                    card = create_card(cls.card_id)
                    if upgraded:
                        card.upgrade()
                    combat.player.energy = 6
                    combat.player.stars = 20
                    combat.hand.append(card)
                    tgt = combat.alive_enemies[0] if combat.alive_enemies else None
                    combat.play_card(card, tgt)
                except Exception as e:  # noqa: BLE001
                    fails.append((cls.card_id, upgraded, repr(e)))
    assert not fails, f"플레이 크래시: {fails[:8]}"
    print(f"✅ 전 카드 {len(_COLORLESS_CARDS)}종 × 2(업글여부) 개별 플레이 크래시 없음")


def test_full_combats_all_characters_greedy():
    print("\n=== 5개 캐릭터 + 전체 Colorless 덱 그리디 다턴 스모크 ===\n")
    fails = []
    for char_id in ("ironclad", "silent", "defect", "necrobinder", "regent"):
        for seed in range(3):
            try:
                player = Player(create_character(char_id))
                for cls in _COLORLESS_CARDS:
                    player.master_deck.append(create_card(cls.card_id))
                monsters = [create_monster("stabbot"), create_monster("zapbot")]
                combat = CombatState(player, monsters, seed=seed)
                combat.run(GreedyPolicy(), max_turns=15)
            except Exception as e:  # noqa: BLE001
                fails.append((char_id, seed, repr(e)))
    assert not fails, f"다턴 크래시: {fails[:8]}"
    print("✅ 5개 캐릭터 × 3시드 그리디 다턴 전투 크래시 없음")


def main():
    test_pool_registration()
    test_gang_up_flat_damage()
    test_gold_axe_scaling()
    test_the_ball_escalation()
    test_rend_debuff_scaling()
    test_fisticuffs_block_from_damage()
    test_omnislice_splash()
    test_hand_of_greed_gold_on_kill()
    test_mind_blast_draw_pile_scaling()
    test_volley_x_cost_random_targets()
    test_bolas_and_thrumming_hatchet_boomerang()
    test_mayhem_auto_play_from_draw_pile()
    test_nostalgia_settle_override()
    test_stratagem_after_shuffle()
    test_panache_aoe_every_fifth_play()
    test_panache_instanced_stacking()
    test_rolling_boulder_escalation()
    test_rolling_boulder_instanced_stacking()
    test_the_bomb_explosion()
    test_the_bomb_instanced_stacking()
    test_panic_button_no_block()
    test_panic_button_exempts_power_sourced_block()
    test_the_gambit_instakill()
    test_the_gambit_ignores_unpowered_reflect()
    test_prep_time_vigor()
    test_automation_energy_every_10_draws()
    test_automation_instanced_stacking()
    test_calamity_generates_attack_cards()
    test_entropy_transforms_hand_card()
    test_discovery_jack_and_jackpot_generation()
    test_fasten_defend_bonus()
    test_dark_shackles_blocked_by_artifact()
    test_character_pool_excludes_cannot_generate_in_combat()
    test_hidden_gem_fallback_preserves_replay_filter()
    test_entropy_no_force_upgrade()
    test_dexterity_ignores_unpowered_block()
    test_frail_ignores_unpowered_block()
    test_unmovable_ignores_unpowered_block()
    test_sleight_of_flesh_reflect_respects_block()
    test_vulnerable_ignores_unpowered_damage()
    test_colossus_ignores_unpowered_damage()
    test_cruelty_respects_powered_gate()
    test_intangible_cap_applies_after_multiplicative()
    test_regent_colorless_integration()
    test_full_combats_all_cards()
    test_full_combats_all_characters_greedy()
    print("\n🎉 Phase 6g 전체 테스트 통과!")


if __name__ == "__main__":
    main()
