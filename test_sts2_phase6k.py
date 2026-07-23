#!/usr/bin/env python3
"""
STS2 Phase 6k 통합 테스트.
몬스터 배치8 8종 (MysteriousKnight/Flyconid/ShrinkerBeetle/LouseProgenitor/
SpinyToad/Byrdonis/FossilStalker/SoulFysh) + 신규 파워 3종 (ShrinkPower/
TerritorialPower/SuckPower) + 상태이상 카드 Beckon + 엔진 확장(attack()의
on_landed_attack 훅, 뽑을 더미 상태이상 삽입 add_status_to_player_draw).
"""
import sts2_sim  # noqa: F401 — CARD_REGISTRY 등록
from sts2_sim.core.combat import CombatState
from sts2_sim.core.encounters import ENCOUNTERS, make_encounter
from sts2_sim.core.policy import GreedyPolicy
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import create_monster, MONSTER_REGISTRY, IntentType
from sts2_sim.entities.monsters_batch8 import (
    MysteriousKnight, Flyconid, ShrinkerBeetle, LouseProgenitor, SpinyToad,
    Byrdonis, FossilStalker, SoulFysh,
)
from sts2_sim.models.sts2_card import create_card


def make_combat(character_id="ironclad", monster_ids=("big_dummy",), seed=42):
    player = Player(create_character(character_id))
    monsters = [create_monster(mid) for mid in monster_ids]
    combat = CombatState(player, monsters, seed=seed)
    combat.start()
    player.energy = player.max_energy
    return combat, player, monsters


def test_registry_and_encounters():
    """8종 전부 MONSTER_REGISTRY + ENCOUNTERS 등록."""
    for mid in ("mysterious_knight", "flyconid", "shrinker_beetle", "louse_progenitor",
                "spiny_toad", "byrdonis", "fossil_stalker", "soul_fysh"):
        assert mid in MONSTER_REGISTRY, f"미등록: {mid}"
    for eid in ("mysterious_knight_event", "flyconid_normal", "shrinker_beetle_weak",
                "louse_progenitor_normal", "spiny_toad_normal", "byrdonis_elite",
                "fossil_stalker_normal", "soul_fysh_boss"):
        assert eid in ENCOUNTERS, f"미등록 인카운터: {eid}"
    print("✅ 몬스터 8종 + 인카운터 8종 등록 확인")


def test_hp_ranges():
    """Ascension 미적용 기본 HP (디컴파일 원본과 대조 완료)."""
    checks = [
        (MysteriousKnight(), 101, 101),
        (Flyconid(), 47, 49),
        (ShrinkerBeetle(), 38, 40),
        (LouseProgenitor(), 134, 136),
        (SpinyToad(), 116, 119),
        (Byrdonis(), 81, 84),
        (FossilStalker(), 51, 53),
        (SoulFysh(), 211, 211),
    ]
    for monster, min_hp, max_hp in checks:
        assert monster.min_initial_hp == min_hp, f"{monster.title} min_hp {monster.min_initial_hp} != {min_hp}"
        assert monster.max_initial_hp == max_hp, f"{monster.title} max_hp {monster.max_initial_hp} != {max_hp}"
    print("✅ 8종 HP 범위 디컴파일 원본과 일치")


def test_mysterious_knight_buffs():
    """MysteriousKnight: FlailKnight 상속 + 개전 힘+6/도금+6 추가."""
    m = MysteriousKnight()
    m.setup_for_combat(None)
    assert m.get_power_amount("strength") == 6
    assert m.get_power_amount("plating") == 6
    assert m._move_state_machine.current_state.name == "RAM_MOVE"
    print("✅ MysteriousKnight: 개전 힘+6/도금+6, FlailKnight 무브그래프(RAM_MOVE 시작)")


def test_flyconid_initial_branch_excludes_vulnerable():
    """Flyconid: INITIAL 분기는 FRAIL_SPORES/SMASH만 (VULNERABLE_SPORES 제외)."""
    import random
    seen = set()
    for seed in range(50):
        m = Flyconid()
        m.setup_for_combat(None, rng=random.Random(seed))
        seen.add(m._move_state_machine.current_state.name)
    assert seen <= {"FRAIL_SPORES_MOVE", "SMASH_MOVE"}, f"INITIAL 분기 오류: {seen}"
    assert "VULNERABLE_SPORES_MOVE" not in seen
    print(f"✅ Flyconid: INITIAL 분기 = {seen} (VULNERABLE_SPORES 제외 확인)")


def test_shrinker_beetle_shrink_once_then_cycle():
    """ShrinkerBeetle: SHRINKER_MOVE는 개전 1회만, 이후 CHOMP/STOMP 영구 교대."""
    combat, player, monsters = make_combat(monster_ids=("shrinker_beetle",))
    beetle = monsters[0]
    assert beetle._move_state_machine.current_state.name == "SHRINKER_MOVE"
    beetle.take_turn([player])  # SHRINKER_MOVE 실행 → CHOMP로 전환
    assert player.get_power_amount("shrink") < 0  # 무한 지속(음수)
    names = [beetle._move_state_machine.current_state.name]
    for _ in range(5):
        beetle.take_turn([player])
        names.append(beetle._move_state_machine.current_state.name)
    assert "SHRINKER_MOVE" not in names, "SHRINKER_MOVE가 재방문됨 (원본은 1회 한정)"
    assert names == ["CHOMP_MOVE", "STOMP_MOVE", "CHOMP_MOVE", "STOMP_MOVE", "CHOMP_MOVE", "STOMP_MOVE"]
    print(f"✅ ShrinkerBeetle: Shrink 1회 부여 후 CHOMP/STOMP 영구 교대 ({' → '.join(names)})")


def test_shrink_power_reduces_damage_and_is_infinite():
    """ShrinkPower(-1)은 아군의 공격 데미지 30% 감소, 자기 턴 종료에도 소멸 안 함."""
    from sts2_sim.models.sts2_power import ShrinkPower
    m = FossilStalker()
    m.setup_for_combat(None)
    m.apply_power(ShrinkPower(-1))
    assert m.compute_attack_damage(10) == int(10 * 0.7)
    m.tick_powers()  # 자기 턴 종료 시뮬레이션 — 무한이라 유지
    assert m.get_power_amount("shrink") < 0
    m.compute_attack_damage(10)
    print("✅ ShrinkPower: 공격 30% 감소 + 무한 지속(자기 턴 종료에도 소멸 안 함)")


def test_louse_progenitor_curl_up_and_cycle():
    """LouseProgenitor: 개전 CurlUpPower(14), WEB→CURL_AND_GROW→POUNCE→WEB 순환."""
    combat, player, monsters = make_combat(monster_ids=("louse_progenitor",))
    louse = monsters[0]
    assert louse.get_power_amount("curl_up") == 14
    assert louse._move_state_machine.current_state.name == "WEB_CANNON_MOVE"
    louse.take_turn([player])  # WEB_CANNON_MOVE
    assert player.get_power_amount("frail") == 2
    louse.take_turn([player])  # CURL_AND_GROW_MOVE
    assert louse.get_power_amount("strength") == 5
    assert louse.block == 14
    assert louse._move_state_machine.current_state.name == "POUNCE_MOVE"
    print("✅ LouseProgenitor: 개전 CurlUp(14), WEB(허약2)→CURL_AND_GROW(블록14+힘5)→POUNCE 순환")


def test_curl_up_power_blocks_first_hit_only():
    """CurlUpPower: 첫 피격에만 블록 획득 후 소멸."""
    from sts2_sim.models.sts2_power import CurlUpPower
    m = LouseProgenitor()
    m.setup_for_combat(None)
    m._powers.pop("curl_up", None)
    m.apply_power(CurlUpPower(14))
    m.take_damage(1, source=None)
    assert m.get_power_amount("curl_up") == 0  # 소멸
    assert m.block == 14
    print("✅ CurlUpPower: 첫 피격 시 블록14 획득 후 파워 소멸")


def test_spiny_toad_thorns_cycle_nets_to_zero():
    """SpinyToad: PROTRUDING_SPIKES(가시+5) → SPIKE_EXPLOSION(23딜+가시-5) → TONGUE_LASH(17딜) 순환."""
    combat, player, monsters = make_combat(monster_ids=("spiny_toad",))
    toad = monsters[0]
    assert toad._move_state_machine.current_state.name == "PROTRUDING_SPIKES_MOVE"
    toad.take_turn([player])  # 가시+5
    assert toad.get_power_amount("thorns") == 5
    hp0 = player.current_hp
    toad.take_turn([player])  # 23딜 + 가시-5
    assert hp0 - player.current_hp == 23
    assert toad.get_power_amount("thorns") == 0
    hp1 = player.current_hp
    toad.take_turn([player])  # 17딜
    assert hp1 - player.current_hp == 17
    assert toad._move_state_machine.current_state.name == "PROTRUDING_SPIKES_MOVE"
    print("✅ SpinyToad: 가시+5→폭발(23딜, 가시 상쇄)→혓바닥(17딜)→순환 복귀")


def test_thorns_does_not_retaliate_against_unpowered_damage():
    """Thorns(및 FlameBarrier/CurlUpPower)는 Unpowered 피해(오브/파워 반응형)에는
    반응하지 않아야 한다 (원본 ThornsPower.BeforeDamageReceived — IsPoweredAttack()
    게이트. SpinyToad의 가시 토글 메커니즘 검증 중 이 게이트 누락을 발견해 수정 —
    SpinyToad 자체의 결함이 아니라 반격형 파워 공통 이식 누락이었다)."""
    from sts2_sim.models.sts2_power import Thorns
    toad = SpinyToad()
    toad.setup_for_combat(None)
    toad.apply_power(Thorns(5))
    attacker = Player(create_character("ironclad"))
    hp0 = attacker.current_hp
    toad.take_damage(10, source=attacker, powered=False)  # Unpowered 피해 — 반격 없어야 함
    assert attacker.current_hp == hp0, f"Unpowered 피해에 반격 발생: {hp0 - attacker.current_hp}"
    toad.take_damage(10, source=attacker, powered=True)  # Powered 피해 — 반격 발생
    assert hp0 - attacker.current_hp == 5, f"Powered 피해에 반격 실패: {hp0 - attacker.current_hp}"
    print("✅ Thorns: Unpowered 피해엔 반격 없음, Powered 피해엔 정상 반격")


def test_byrdonis_territorial_grows_every_turn():
    """Byrdonis: 개전 Territorial(1) → 자기 턴 종료마다 힘+1 누적."""
    combat, player, monsters = make_combat(monster_ids=("byrdonis",))
    bird = monsters[0]
    assert bird.get_power_amount("territorial") == 1
    assert bird.get_power_amount("strength") == 0
    for expected in (1, 2, 3):
        bird.take_turn([player])
        for power in list(bird._powers.values()):
            hook = getattr(power, "on_turn_end", None)
            if hook:
                hook()
        assert bird.get_power_amount("strength") == expected, \
            f"{expected}턴째 힘 {bird.get_power_amount('strength')}"
    print("✅ Byrdonis: 개전 Territorial(1), 매 자기 턴 종료마다 힘 누적(+1,+2,+3)")


def test_fossil_stalker_suck_gains_strength_per_landed_hit():
    """FossilStalker: 개전 Suck(3) → 자신의 공격이 적중할 때마다 힘+3 (다단히트는 히트마다
    카운트되지만, 같은 무브 안에서는 소급 반영되지 않아 LASH_MOVE 2연타 총딜은
    6(3+3)이지 9(3+3+3)가 아니다 — 적대적 검증에서 발견된 힘 조기반영 버그 수정."""
    combat, player, monsters = make_combat(monster_ids=("fossil_stalker",))
    stalker = monsters[0]
    assert stalker.get_power_amount("suck") == 3
    assert stalker._move_state_machine.current_state.name == "LATCH_MOVE"
    stalker.take_turn([player])  # LATCH_MOVE — 단일 히트
    assert stalker.get_power_amount("strength") == 3

    stalker2 = FossilStalker()
    stalker2.setup_for_combat(None)
    lash = next(s for s in stalker2._move_state_machine.states if s.name == "LASH_MOVE")
    stalker2._move_state_machine.current_state = lash
    dummy = Player(create_character("ironclad"))
    hp0 = dummy.current_hp
    stalker2.take_turn([dummy])  # take_turn 경유 — flush_landed_attacks 타이밍까지 검증
    assert hp0 - dummy.current_hp == 6, \
        f"LASH_MOVE 총딜 불일치(힘 조기반영 버그 재발 의심): {hp0 - dummy.current_hp}"
    assert stalker2.get_power_amount("strength") == 6, \
        f"2연타 Suck 누적 실패: {stalker2.get_power_amount('strength')}"
    print("✅ FossilStalker: 개전 Suck(3), LASH_MOVE 2연타 총딜 6(소급반영 없음) 후 힘+6 일괄 반영")


def test_soul_fysh_beckon_insertion_and_fade():
    """SoulFysh: BECKON_MOVE(뽑을더미1+버림더미1) → DE_GAS → GAZE(버림더미1추가) → FADE(무형+2) → SCREAM(취약+3)."""
    combat, player, monsters = make_combat(monster_ids=("soul_fysh",))
    fysh = monsters[0]
    assert fysh._move_state_machine.current_state.name == "BECKON_MOVE"
    fysh.take_turn([player])  # BECKON_MOVE
    beckon_draw = [c for c in combat.draw_pile if c.card_id == "beckon"]
    beckon_discard = [c for c in combat.discard_pile if c.card_id == "beckon"]
    assert len(beckon_draw) == 1, f"뽑을더미 Beckon 삽입 실패: {len(beckon_draw)}"
    assert len(beckon_discard) == 1, f"버림더미 Beckon 삽입 실패: {len(beckon_discard)}"

    fysh.take_turn([player])  # DE_GAS_MOVE
    fysh.take_turn([player])  # GAZE_MOVE
    beckon_discard2 = [c for c in combat.discard_pile if c.card_id == "beckon"]
    assert len(beckon_discard2) == 2, f"GAZE_MOVE Beckon 추가 실패: {len(beckon_discard2)}"

    fysh.take_turn([player])  # FADE_MOVE
    assert fysh.get_power_amount("intangible") == 2

    fysh.take_turn([player])  # SCREAM_MOVE
    assert player.get_power_amount("vulnerable") > 0
    assert fysh._move_state_machine.current_state.name == "BECKON_MOVE"
    print("✅ SoulFysh: Beckon 삽입(뽑을더미+버림더미), 무형+2, 취약 부여, 5순환 복귀")


def test_beckon_card_unblockable_self_damage():
    """Beckon: 1코스트, 사용 가능(소모 아님), 턴 종료 시 손패에 있으면 블록 무시 6 피해."""
    beckon = create_card("beckon")
    assert beckon is not None and beckon.playable and not beckon.exhausts and beckon.cost == 1
    player = Player(create_character("ironclad"))
    player._block = 100
    hp0 = player.current_hp
    beckon.on_turn_end_in_hand(player, None)
    assert hp0 - player.current_hp == 6, f"Beckon 블록 무시 실패: {hp0 - player.current_hp}"
    assert player.block == 100  # 블록은 그대로 (Unblockable — 소모 안 됨)
    print("✅ Beckon: 1코스트 사용 가능, 턴 종료 시 블록 무시 6 자해")


def test_flyconid_cooldown_gating():
    """Flyconid RAND: 세 분기 모두 base weight는 균등(1:1:1)이다 (적대적 검증에서
    3:2:1로 오독했던 버그를 원본 RandomBranchState.cs 오버로드 재대조로 발견해
    수정 — AddBranch(state,int,MoveRepeatType)의 int는 weight가 아니라 cooldown).
    VULNERABLE_SPORES_MOVE는 최근 3무브, FRAIL_SPORES_MOVE는 최근 2무브 이력에
    자신이 있으면 제외되고, 세 분기가 전부 제외되면 원본과 동일하게 첫 번째로
    등록된 분기(VULNERABLE_SPORES_MOVE)로 폴백한다."""
    import random
    m = Flyconid()
    m.setup_for_combat(None)
    rand = next(s for s in m._move_state_machine.states if s.name == "RAND")

    rng = random.Random(0)
    counts = {"VULNERABLE_SPORES_MOVE": 0, "FRAIL_SPORES_MOVE": 0, "SMASH_MOVE": 0}
    for _ in range(6000):
        picked = rand.resolve(rng, None, [])  # 이력 없음 — 어떤 게이트도 걸리지 않음
        counts[picked.name] += 1
    for name, c in counts.items():
        ratio = c / 6000
        assert 0.28 < ratio < 0.38, f"{name} 비율 {ratio:.3f} — 균등(1/3≈0.333)에서 벗어남"

    # 최근 3무브 안에 VULNERABLE_SPORES_MOVE가 있으면 절대 재선택되지 않음
    history = ["FRAIL_SPORES_MOVE", "SMASH_MOVE", "VULNERABLE_SPORES_MOVE"]
    for _ in range(50):
        picked = rand.resolve(rng, "VULNERABLE_SPORES_MOVE", history)
        assert picked.name != "VULNERABLE_SPORES_MOVE"

    # 세 분기 모두 배제되면(직전=SMASH·최근 이력에 VULN/FRAIL 전부 포함) 첫 분기로 폴백
    exhausting = ["VULNERABLE_SPORES_MOVE", "FRAIL_SPORES_MOVE", "SMASH_MOVE"]
    picked = rand.resolve(rng, "SMASH_MOVE", exhausting)
    assert picked.name == "VULNERABLE_SPORES_MOVE", f"전멸 시 첫 분기 폴백 실패: {picked.name}"
    print("✅ Flyconid RAND: 균등 가중치(1:1:1) + 쿨다운 게이트 + 전멸 시 폴백 확인")


def test_fossil_stalker_no_three_in_a_row():
    """FossilStalker RAND: 세 분기 모두 base weight는 균등(1:1:1)하되, 동일 분기가
    연속 2회까지는 허용되지만 3회 연속은 금지된다 (원본 MoveRepeatType.CanRepeatXTimes(2)
    — 적대적 검증 이후 원본 RandomBranchState.cs 오버로드 재대조로 발견해 수정,
    최초엔 'CannotRepeat 없음 + 가중치 2:2:2'로 오독했었다)."""
    import random
    m = FossilStalker()
    m.setup_for_combat(None, rng=random.Random(11))
    names = [m._move_state_machine.current_state.name]
    for _ in range(300):
        m.take_turn([])
        names.append(m._move_state_machine.current_state.name)
    for i in range(2, len(names)):
        assert not (names[i] == names[i - 1] == names[i - 2]), \
            f"3연속 발생(원본은 최대 2연속 허용): idx={i}, {names[i-2:i+1]}"
    print("✅ FossilStalker: 300턴 시뮬레이션에서 동일 분기 3연속 발생 없음")


def test_louse_progenitor_curl_block_is_powered():
    """LouseProgenitor CURL_AND_GROW_MOVE의 블록 획득은 파워드 무브 블록이라 Frail이
    걸려 있으면 0.75배로 줄어야 한다 (적대적 검증에서 발견된 powered=False 오구현
    수정 — 원본 CreatureCmd.GainBlock(..., ValueProp.Move, null)에는 Unpowered
    플래그가 없다)."""
    from sts2_sim.models.sts2_power import Frail
    m = LouseProgenitor()
    m.setup_for_combat(None)
    m.apply_power(Frail(1))
    curl = next(s for s in m._move_state_machine.states if s.name == "CURL_AND_GROW_MOVE")
    m._move_state_machine.current_state = curl
    m.take_turn([])
    assert m.block == int(14 * 0.75), f"Frail이 블록에 반영되지 않음: {m.block}"
    print("✅ LouseProgenitor: Frail 보유 시 CURL_AND_GROW 블록 14→10 (파워드 블록 확인)")


def test_soul_fysh_self_intangible_decays_on_enemy_turn_end():
    """SoulFysh가 스스로에게 건 Intangible도 (플레이어 파워뿐 아니라) 몬스터 파워도
    on_enemy_turn_end 통지를 받아야 정상 감소한다 — 이전엔 combat.py가 플레이어
    파워에만 통지해 몬스터 자기부여 Intangible이 영원히 누적, 보스전이 사실상
    불가능해지는 버그가 있었다 (적대적 검증에서 발견)."""
    combat, player, monsters = make_combat(monster_ids=("soul_fysh",))
    fysh = monsters[0]
    fysh.take_turn([player])  # BECKON_MOVE
    fysh.take_turn([player])  # DE_GAS_MOVE
    fysh.take_turn([player])  # GAZE_MOVE
    fysh.take_turn([player])  # FADE_MOVE — Intangible(2) 자가부여
    assert fysh.get_power_amount("intangible") == 2
    # combat.py 몬스터 턴 루프가 매 라운드 끝에 실제로 호출하는 통지를 재현
    for _ in range(3):
        for power in list(fysh._powers.values()):
            hook = getattr(power, "on_enemy_turn_end", None)
            if hook:
                hook()
    assert fysh.get_power_amount("intangible") == 0, \
        f"Intangible이 감소하지 않음(영구 누적 버그 재발): {fysh.get_power_amount('intangible')}"
    print("✅ SoulFysh: 자가부여 Intangible이 on_enemy_turn_end 통지로 정상 감소(2→0)")


def test_beckon_respects_intangible_cap():
    """Beckon의 Unblockable 자해는 블록만 우회할 뿐, Intangible의 Cap 단계(무조건 1로
    제한)는 우회하지 않아야 한다 (적대적 검증에서 발견된 lose_hp 직접호출 버그 —
    take_damage(unblockable=True)로 수정해 Cap 파이프라인을 그대로 통과시킨다)."""
    from sts2_sim.models.sts2_power import Intangible
    player = Player(create_character("ironclad"))
    player.apply_power(Intangible(1))
    hp0 = player.current_hp
    beckon = create_card("beckon")
    beckon.on_turn_end_in_hand(player, None)
    assert hp0 - player.current_hp == 1, \
        f"Intangible을 무시하고 전체 피해가 들어감: {hp0 - player.current_hp}"
    print("✅ Beckon: Intangible 보유 시 6 피해가 1로 제한됨 (Unblockable이지만 Cap은 미우회)")


def test_jaxfruit_normal_now_includes_real_flyconid():
    """jaxfruit_normal: Flyconid 이식 완료로 원본 구성(Jaxfruit+Flyconid) 복원."""
    import random
    monsters = make_encounter("jaxfruit_normal", random.Random(0))
    titles = sorted(m.title for m in monsters)
    assert titles == ["Flyconid", "Snapping Jaxfruit"], titles
    print("✅ jaxfruit_normal: Jaxfruit×2 대체 → 원본 Jaxfruit+Flyconid 구성 복원")


def test_full_combats_batch8_smoke():
    """8개 신규 인카운터 전부 여러 시드에 걸쳐 크래시 없이 완주."""
    encounter_ids = [
        "mysterious_knight_event", "flyconid_normal", "shrinker_beetle_weak",
        "louse_progenitor_normal", "spiny_toad_normal", "byrdonis_elite",
        "fossil_stalker_normal", "soul_fysh_boss",
    ]
    import random
    for char_id in ("ironclad", "silent", "defect", "necrobinder", "regent"):
        for eid in encounter_ids:
            for seed in range(3):
                player = Player(create_character(char_id))
                monsters = make_encounter(eid, random.Random(seed))
                combat = CombatState(player, monsters, seed=seed)
                result = combat.run(GreedyPolicy(), max_turns=60)
                assert isinstance(result.victory, bool)
    print("✅ 5캐릭터 × 8인카운터 × 3시드 그리디 다턴 전투 크래시 없음")


def main():
    print("🧪 STS2 Phase 6k 통합 테스트\n")
    test_registry_and_encounters()
    test_hp_ranges()
    test_mysterious_knight_buffs()
    test_flyconid_initial_branch_excludes_vulnerable()
    test_shrinker_beetle_shrink_once_then_cycle()
    test_shrink_power_reduces_damage_and_is_infinite()
    test_louse_progenitor_curl_up_and_cycle()
    test_curl_up_power_blocks_first_hit_only()
    test_spiny_toad_thorns_cycle_nets_to_zero()
    test_thorns_does_not_retaliate_against_unpowered_damage()
    test_byrdonis_territorial_grows_every_turn()
    test_fossil_stalker_suck_gains_strength_per_landed_hit()
    test_soul_fysh_beckon_insertion_and_fade()
    test_beckon_card_unblockable_self_damage()
    test_flyconid_cooldown_gating()
    test_fossil_stalker_no_three_in_a_row()
    test_louse_progenitor_curl_block_is_powered()
    test_soul_fysh_self_intangible_decays_on_enemy_turn_end()
    test_beckon_respects_intangible_cap()
    test_jaxfruit_normal_now_includes_real_flyconid()
    test_full_combats_batch8_smoke()

    print("\n" + "=" * 60)
    print("✅ Phase 6k 전체 테스트 통과!")
    print("=" * 60)
    print("\n📊 Phase 6k 구현 현황:")
    print("  ✅ 몬스터 배치8 8종 (MysteriousKnight/Flyconid/ShrinkerBeetle/")
    print("     LouseProgenitor/SpinyToad/Byrdonis/FossilStalker/SoulFysh)")
    print("  ✅ 신규 파워 3종 (ShrinkPower/TerritorialPower/SuckPower)")
    print("  ✅ 상태이상 카드 Beckon 추가 (Unblockable 자해)")
    print("  ✅ 엔진 확장: attack() on_landed_attack 훅, 뽑을더미 상태이상 삽입")
    print("  ✅ jaxfruit_normal 원본 구성 복원 (Flyconid 이식 완료)")
    print("  ✅ 신규 인카운터 8종 등록 (MONSTER_REGISTRY 55종)")


if __name__ == "__main__":
    main()
