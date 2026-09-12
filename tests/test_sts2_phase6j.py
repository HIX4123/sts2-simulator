#!/usr/bin/env python3
"""
STS2 Phase 6j 통합 테스트.
몬스터 배치 7a/7b/7c 13종 (FuzzyWurmCrawler/Nibbit/Seapunk/TurretOperator/
PunchConstruct/DevotedSculptor/KinPriest/Toadpole/SludgeSpinner/HauntedShip/
Wriggler/Myte/FrogKnight) + Infection/Toxic 상태이상 카드 + Ritual 파워
첫 틱 스킵 버그 수정(적대적 검증에서 발견: DevotedSculptor/DampCultist/
CalcifiedCultist가 원본보다 1턴 빠르게 힘을 얻던 문제).
"""
import sts2_sim  # noqa: F401 — CARD_REGISTRY 등록
from sts2_sim.core.combat import CombatState
from sts2_sim.core.encounters import ENCOUNTERS, make_encounter
from sts2_sim.core.policy import GreedyPolicy
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import create_monster, MONSTER_REGISTRY, IntentType
from sts2_sim.entities.monsters_batch7a import (
    FuzzyWurmCrawler, Nibbit, Seapunk, TurretOperator, PunchConstruct,
)
from sts2_sim.entities.monsters_batch7b import (
    DevotedSculptor, KinPriest, Toadpole, SludgeSpinner, HauntedShip,
)
from sts2_sim.entities.monsters_batch7c import Wriggler, Myte, FrogKnight
from sts2_sim.models.sts2_card import create_card
from sts2_sim.models.sts2_power import Ritual


def make_combat(character_id="ironclad", monster_ids=("big_dummy",), seed=42):
    player = Player(create_character(character_id))
    monsters = [create_monster(mid) for mid in monster_ids]
    combat = CombatState(player, monsters, seed=seed)
    combat.start()
    player.energy = player.max_energy
    return combat, player, monsters


def test_registry_and_encounters():
    """13종 전부 MONSTER_REGISTRY에 등록, 12종은 ENCOUNTERS에도 등록됨
    (Wriggler는 PhrogParasite 소환 전용, KinPriest는 TheKinBoss 전용이라
    독립 인카운터 없음 — 둘 다 미이식 의존 관계라 보류)."""
    for mid in ("fuzzy_wurm_crawler", "nibbit", "seapunk", "turret_operator",
                "punch_construct", "devoted_sculptor", "kin_priest", "toadpole",
                "sludge_spinner", "haunted_ship", "wriggler", "myte", "frog_knight"):
        assert mid in MONSTER_REGISTRY, f"미등록: {mid}"
    for eid in ("fuzzy_wurm_crawler_weak", "nibbits_weak", "nibbits_normal",
                "seapunk_weak", "seapunk_normal", "turret_operator_weak",
                "punch_construct_normal", "devoted_sculptor_weak", "toadpoles_weak",
                "sludge_spinner_weak", "haunted_ship_normal", "mytes_normal",
                "frog_knight_normal"):
        assert eid in ENCOUNTERS, f"미등록 인카운터: {eid}"
    print(f"✅ 몬스터 13종 + 인카운터 13종 등록 확인")


def test_hp_ranges():
    """Ascension 미적용 기본 HP (디컴파일 원본과 대조 완료)."""
    checks = [
        (FuzzyWurmCrawler(), 55, 57),
        (Nibbit(), 42, 46),
        (Seapunk(), 44, 46),
        (TurretOperator(), 41, 41),
        (PunchConstruct(), 55, 55),
        (DevotedSculptor(), 162, 162),
        (KinPriest(), 190, 190),
        (Toadpole(), 21, 25),
        (SludgeSpinner(), 37, 39),
        (HauntedShip(), 63, 63),
        (Wriggler(), 17, 21),
        (Myte(), 61, 67),
        (FrogKnight(), 191, 191),
    ]
    for monster, min_hp, max_hp in checks:
        assert monster.min_initial_hp == min_hp, f"{monster.title} min_hp {monster.min_initial_hp} != {min_hp}"
        assert monster.max_initial_hp == max_hp, f"{monster.title} max_hp {monster.max_initial_hp} != {max_hp}"
    print(f"✅ 13종 HP 범위 디컴파일 원본과 일치")


def test_fuzzy_wurm_crawler_cycle():
    """FuzzyWurmCrawler: FIRST_ACID_GOOP → INHALE → ACID_GOOP → FIRST_ACID_GOOP 순환."""
    m = FuzzyWurmCrawler()
    m.setup_for_combat(None)
    names = []
    for _ in range(4):
        names.append(m._move_state_machine.current_state.name)
        m._move_state_machine.advance_state()
    assert names == ["FIRST_ACID_GOOP", "INHALE", "ACID_GOOP", "FIRST_ACID_GOOP"]
    print(f"✅ FuzzyWurmCrawler: {' → '.join(names)}")


def test_nibbit_slot_branch():
    """Nibbit: is_alone→BUTT / is_front→SLICE / 그 외→HISS 로 시작."""
    def initial_state(**kwargs):
        m = Nibbit(**kwargs)
        m.setup_for_combat(None)
        return m._move_state_machine.current_state.name

    assert initial_state(is_alone=True) == "BUTT_MOVE"
    assert initial_state(is_front=True) == "SLICE_MOVE"
    assert initial_state() == "HISS_MOVE"
    print(f"✅ Nibbit: is_alone/is_front/기본 슬롯 분기 정확")


def test_punch_construct_artifact_and_flags():
    """PunchConstruct: 개전 Artifact 1, starts_with_fast_punch 플래그로 초기 상태 변경."""
    m = PunchConstruct()
    m.setup_for_combat(None)
    assert m.get_power_amount("artifact") == 1
    assert m._move_state_machine.current_state.name == "READY_MOVE"

    m2 = PunchConstruct(starts_with_fast_punch=True)
    m2.setup_for_combat(None)
    assert m2._move_state_machine.current_state.name == "FAST_PUNCH_MOVE"
    print(f"✅ PunchConstruct: 개전 Artifact 1, starts_with_fast_punch 분기")


def test_toadpole_thorns_cycle():
    """Toadpole: WHIRL → SPIKEN(가시+2) → SPIKE_SPIT(가시-2 소모 후 3딜×3) → WHIRL."""
    m = Toadpole()
    m.setup_for_combat(None)
    assert m._move_state_machine.current_state.name == "WHIRL_MOVE"
    m.take_turn([])  # WHIRL
    m.take_turn([])  # SPIKEN
    assert m.get_power_amount("thorns") == 2
    m.take_turn([])  # SPIKE_SPIT — 가시 -2 소모
    assert m.get_power_amount("thorns") == 0
    print(f"✅ Toadpole: SPIKEN(+2가시) → SPIKE_SPIT(가시 소모 0으로 복귀)")


def test_sludge_spinner_cannot_repeat():
    """SludgeSpinner: RandomBranchState 3분기 모두 CannotRepeat (직전과 같은 분기 재선택 불가)."""
    m = SludgeSpinner()
    m.setup_for_combat(None, rng=__import__("random").Random(7))
    names = [m._move_state_machine.current_state.name]
    for _ in range(30):
        m.take_turn([])
        names.append(m._move_state_machine.current_state.name)
    branch_moves = [n for n in names if n in ("OIL_SPRAY_MOVE", "SLAM_MOVE", "RAGE_MOVE")]
    for a, b in zip(branch_moves, branch_moves[1:]):
        assert a != b, f"동일 분기 연속 발생: {a} → {b}"
    print(f"✅ SludgeSpinner: 30턴 무반복 분기 확인")


def test_haunted_ship_dazed_insertion():
    """HauntedShip: 개전 HAUNT_MOVE(약화3 + Dazed 5장 버림더미)."""
    combat, player, monsters = make_combat(monster_ids=("haunted_ship",))
    ship = monsters[0]
    assert ship._move_state_machine.current_state.name == "HAUNT_MOVE"
    ship.take_turn([player])
    dazed = [c for c in combat.discard_pile if c.card_id == "dazed"]
    assert len(dazed) == 5, f"Dazed 삽입 실패: {len(dazed)}"
    assert player.get_power_amount("weak") == 3
    print(f"✅ HauntedShip: HAUNT_MOVE → Dazed 5장 + 약화 3")


def test_wriggler_infection_and_stun():
    """Wriggler: WRIGGLE_MOVE → Infection 1장 버림더미 + 힘+2. start_stunned=True면 SPAWNED_MOVE부터."""
    combat, player, monsters = make_combat(monster_ids=("wriggler",))
    w = monsters[0]
    assert w._move_state_machine.current_state.name == "NASTY_BITE_MOVE"
    w.take_turn([player])  # BITE
    w.take_turn([player])  # WRIGGLE
    infection = [c for c in combat.discard_pile if c.card_id == "infection"]
    assert len(infection) == 1
    assert w.get_power_amount("strength") == 2

    stunned = Wriggler(start_stunned=True)
    stunned.setup_for_combat(None)
    assert stunned._move_state_machine.current_state.name == "SPAWNED_MOVE"
    assert stunned.get_current_intent().intent_type == IntentType.STUN
    print(f"✅ Wriggler: WRIGGLE_MOVE Infection 삽입 + 힘+2, StartStunned 분기")


def test_myte_toxic_and_slot_branch():
    """Myte: TOXIC_MOVE → 손패에 Toxic 2장. is_second=True면 SUCK_MOVE부터 시작."""
    combat, player, monsters = make_combat(monster_ids=("myte",))
    myte = monsters[0]
    assert myte._move_state_machine.current_state.name == "TOXIC_MOVE"
    myte.take_turn([player])
    toxic_in_hand = [c for c in combat.hand if c.card_id == "toxic"]
    assert len(toxic_in_hand) == 2, f"Toxic 삽입 실패: {len(toxic_in_hand)}"

    second = Myte(is_second=True)
    second.setup_for_combat(None)
    assert second._move_state_machine.current_state.name == "SUCK_MOVE"
    print(f"✅ Myte: TOXIC_MOVE 손패 삽입 2장, is_second 분기")


def test_frog_knight_half_health_branch_and_plating():
    """FrogKnight: 개전 Plating 15, HP < 절반이면 1회만 BEETLE_CHARGE(35딜) 후 TONGUE_LASH 복귀."""
    combat, player, monsters = make_combat(monster_ids=("frog_knight",))
    knight = monsters[0]
    assert knight.get_power_amount("plating") == 15
    assert knight._move_state_machine.current_state.name == "TONGUE_LASH"

    # HP를 절반 밑으로 강제로 낮춰 HALF_HEALTH 분기 확인
    knight._current_hp = knight.max_hp // 2 - 1
    knight.take_turn([player])   # TONGUE_LASH
    knight.take_turn([player])   # STRIKE_DOWN_EVIL
    knight.take_turn([player])   # FOR_THE_QUEEN — 자신 힘 +5
    assert knight.get_power_amount("strength") == 5
    hp0 = player.current_hp
    knight.take_turn([player])   # HALF_HEALTH 분기 평가 → BEETLE_CHARGE(35+힘5=40)
    assert knight.has_beetle_charged
    assert hp0 - player.current_hp == 40, f"BeetleCharge 데미지 불일치: {hp0 - player.current_hp}"

    # 한 번 돌진한 뒤로는 HP가 낮아도 TONGUE_LASH로 복귀 (HasBeetleCharged 우선)
    assert knight._move_state_machine.current_state.name == "TONGUE_LASH"
    print(f"✅ FrogKnight: 개전 Plating 15, HALF_HEALTH 1회 한정 BeetleCharge(35딜)")


def test_infection_and_toxic_cards():
    """Infection(사용불가, Unpowered 3자해), Toxic(1코스트 소모, Unpowered 5자해)."""
    infection = create_card("infection")
    assert infection is not None and not infection.playable and infection.cost == 0
    toxic = create_card("toxic")
    assert toxic is not None and toxic.exhausts and toxic.cost == 1
    print(f"✅ Infection/Toxic 카드 속성 확인 (사용불가/소모)")


def test_ritual_skips_first_tick():
    """Ritual 파워: 적용된 바로 그 턴은 발동하지 않고 다음 턴 시작부터 힘 부여
    (적대적 검증에서 발견된 버그 — 원본 RitualPower.WasJustAppliedByEnemy 대응)."""
    m = DevotedSculptor()
    m.setup_for_combat(None)
    ritual = Ritual(9)
    ritual.apply(m, m)
    assert m.get_power_amount("strength") == 0
    m._powers["ritual"].on_turn_start()  # 부여 다음 턴 — 스킵
    assert m.get_power_amount("strength") == 0
    m._powers["ritual"].on_turn_start()  # 그 다음 턴 — 발동
    assert m.get_power_amount("strength") == 9
    print(f"✅ Ritual: 첫 틱 스킵 후 다음 턴부터 힘 +9")


def test_full_combats_batch7_smoke():
    """13개 신규 인카운터 전부 여러 시드에 걸쳐 크래시 없이 완주."""
    encounter_ids = [
        "fuzzy_wurm_crawler_weak", "nibbits_weak", "nibbits_normal",
        "seapunk_weak", "seapunk_normal", "turret_operator_weak",
        "punch_construct_normal", "devoted_sculptor_weak", "toadpoles_weak",
        "sludge_spinner_weak", "haunted_ship_normal", "mytes_normal",
        "frog_knight_normal",
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
    print(f"✅ 5캐릭터 × 13인카운터 × 3시드 그리디 다턴 전투 크래시 없음")


def main():
    print("🧪 STS2 Phase 6j 통합 테스트\n")
    test_registry_and_encounters()
    test_hp_ranges()
    test_fuzzy_wurm_crawler_cycle()
    test_nibbit_slot_branch()
    test_punch_construct_artifact_and_flags()
    test_toadpole_thorns_cycle()
    test_sludge_spinner_cannot_repeat()
    test_haunted_ship_dazed_insertion()
    test_wriggler_infection_and_stun()
    test_myte_toxic_and_slot_branch()
    test_frog_knight_half_health_branch_and_plating()
    test_infection_and_toxic_cards()
    test_ritual_skips_first_tick()
    test_full_combats_batch7_smoke()

    print("\n" + "=" * 60)
    print("✅ Phase 6j 전체 테스트 통과!")
    print("=" * 60)
    print("\n📊 Phase 6j 구현 현황:")
    print("  ✅ 몬스터 배치 7a/7b/7c 13종 (FuzzyWurmCrawler/Nibbit/Seapunk/")
    print("     TurretOperator/PunchConstruct/DevotedSculptor/KinPriest/Toadpole/")
    print("     SludgeSpinner/HauntedShip/Wriggler/Myte/FrogKnight)")
    print("  ✅ 상태이상 카드 2종 추가 (Infection/Toxic)")
    print("  ✅ Ritual 파워 첫 틱 스킵 버그 수정 (적대적 검증에서 발견)")
    print("  ✅ 신규 인카운터 13종 등록 (MONSTER_REGISTRY 47종)")


if __name__ == "__main__":
    main()
