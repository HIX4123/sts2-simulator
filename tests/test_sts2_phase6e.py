#!/usr/bin/env python3
"""
STS2 Phase 6e 통합 테스트.
Necrobinder 카드 풀 82종 (디컴파일 NecrobinderCardPool 91종 - 멀티플레이 전용 5종
- 스타터 4종[Strike/Defend/Bodyguard/Unleash]) + Soul/SweepingGaze 토큰
+ 신규 파워 25종 (Doom/Calcify/ReaperForm/DieForYou/NecroMastery/Ethereal 시너지 등).
"""
import sts2_sim  # noqa: F401 — CARD_REGISTRY 등록
from sts2_sim.core.combat import CombatState
from sts2_sim.core.policy import GreedyPolicy
from sts2_sim.core.run import RunState
from sts2_sim.entities.player import Player
from sts2_sim.entities.creature import Osty
from sts2_sim.entities.sts2_character import create_character
from sts2_sim.entities.sts2_monster import create_monster
from sts2_sim.models.sts2_card import CARD_REGISTRY, CardType, Rarity, create_card
from sts2_sim.models.sts2_power import Doom, Strength, Vulnerable, Weak
from sts2_sim.cards.necrobinder import NECROBINDER_POOL_BY_RARITY


def make_combat(monster_ids=("big_dummy",), seed=42, no_osty=False):
    player = Player(create_character("necrobinder"))
    monsters = [create_monster(mid) for mid in monster_ids]
    combat = CombatState(player, monsters, seed=seed)
    combat.start()  # BoundPhylactery가 Osty 1 소환
    player.energy = player.max_energy
    if no_osty:
        player.osty = None
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
    common = NECROBINDER_POOL_BY_RARITY[Rarity.COMMON]
    uncommon = NECROBINDER_POOL_BY_RARITY[Rarity.UNCOMMON]
    rare = NECROBINDER_POOL_BY_RARITY[Rarity.RARE]
    assert len(common) == 20, len(common)
    assert len(uncommon) == 35, len(uncommon)
    assert len(rare) == 25, len(rare)
    # 토큰 + Ancient 등록 확인
    for cid in ("soul", "sweeping_gaze", "forbidden_grimoire", "protector"):
        assert cid in CARD_REGISTRY, cid
    # 멀티플레이 전용 5종은 미등록
    for cid in ("cacophony", "glimpse_beyond", "legion_of_bone",
                "soulbound", "underworld"):
        assert cid not in CARD_REGISTRY, f"멀티 전용 등록됨: {cid}"
    # Ancient는 보상 풀 제외
    assert "protector" not in (common + uncommon + rare)
    print(f"✅ 보상 풀 80종 (C{len(common)}/U{len(uncommon)}/R{len(rare)})"
          f" + Ancient 2 + 토큰 2 등록, 멀티 5종 제외")


def test_soul_token():
    print("\n=== Soul 토큰 ===\n")
    combat, player, _ = make_combat()
    combat.draw_pile = [create_card("strike") for _ in range(5)]
    n0 = len(combat.hand)
    play(combat, "soul")
    assert len(combat.hand) == n0 + 2, f"Soul 드로우 {len(combat.hand)-n0} != 2"
    soul = create_card("soul"); soul.upgrade()
    assert soul.exhausts and soul.cost == 0
    print("✅ Soul: 0코스트 2장 드로우(업글 3), 소모")


def test_osty_summon_stack_revive():
    print("\n=== Osty 소환/스택/부활 ===\n")
    combat, player, _ = make_combat(no_osty=True)
    play(combat, "afterlife", energy=3)   # Summon 6
    assert player.osty.max_hp == 6 and player.osty.current_hp == 6
    play(combat, "pull_aggro", energy=2)  # Summon 4 → 스택
    assert player.osty.max_hp == 10, player.osty.max_hp
    player.osty._current_hp = 0           # Osty 사망
    play(combat, "afterlife", energy=3)   # 부활 (새 Osty 6)
    assert player.osty.max_hp == 6 and player.osty.is_alive
    print("✅ Summon: 생존 시 최대HP 증가 / 사망 시 부활")


def test_osty_attack_and_missing():
    print("\n=== Osty 공격 & 부재 시 무효 ===\n")
    # Osty 존재 → Poke 6 피해
    combat, player, monsters = make_combat()
    player.summon_osty(20)  # 확실히 살아있게
    hp0 = _enemy(combat).current_hp
    play(combat, "poke", target=_enemy(combat))
    assert _enemy(combat).current_hp == hp0 - 6, hp0 - _enemy(combat).current_hp
    # Osty 부재 → 무효
    combat2, player2, _ = make_combat(no_osty=True)
    hp1 = _enemy(combat2).current_hp
    play(combat2, "poke", target=_enemy(combat2))
    assert _enemy(combat2).current_hp == hp1, "Osty 없이 데미지 발생"
    print("✅ Osty 공격은 Osty 존재 시에만 (Poke 6 / 부재 시 무효)")


def test_die_for_you_redirect():
    print("\n=== DieForYou 리다이렉트 ===\n")
    combat, player, monsters = make_combat()
    player.summon_osty(30)
    php0 = player.current_hp
    ohp0 = player.osty.current_hp
    player.take_damage(10, source=monsters[0])  # 파워드 공격 → Osty가 대신 받음
    assert player.current_hp == php0, "플레이어가 피해를 받음"
    assert player.osty.current_hp == ohp0 - 10, "Osty가 대신 받지 않음"
    print("✅ 살아있는 Osty가 플레이어 겨냥 공격을 대신 받음")


def test_doom_kill():
    print("\n=== Doom 즉사 ===\n")
    combat, player, monsters = make_combat()
    enemy = _enemy(combat)
    enemy._current_hp = 15
    enemy.apply_power(Doom(20), applier=player)   # HP 15 <= 20 → doomed
    assert not enemy.is_dead
    combat._trigger_doom()
    assert enemy.is_dead, "Doom 즉사 실패"
    print("✅ 적 턴 종료 시 HP <= Doom 수치면 즉사")


def test_blight_strike_doom():
    print("\n=== BlightStrike: Doom = 입힌 피해 ===\n")
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    play(combat, "blight_strike", target=enemy)
    assert enemy.get_power_amount("doom") == 8, enemy.get_power_amount("doom")
    print("✅ BlightStrike 8딜 → Doom 8 부여")


def test_calcify_boosts_osty():
    print("\n=== Calcify: Osty 공격 강화 ===\n")
    combat, player, _ = make_combat()
    player.summon_osty(20)
    play(combat, "calcify")               # Calcify 4
    enemy = _enemy(combat)
    hp0 = enemy.current_hp
    play(combat, "poke", target=enemy)    # Osty 6 + Calcify 4 = 10
    assert hp0 - enemy.current_hp == 10, hp0 - enemy.current_hp
    print("✅ Calcify 4 → Osty 공격 Poke 6+4=10")


def test_reaper_form_doom():
    print("\n=== ReaperForm: 피해만큼 Doom ===\n")
    combat, player, _ = make_combat()
    play(combat, "reaper_form", energy=3)   # ReaperForm 1
    enemy = _enemy(combat)
    play(combat, "strike", target=enemy)    # 6딜 → Doom 6
    assert enemy.get_power_amount("doom") == 6, enemy.get_power_amount("doom")
    print("✅ ReaperForm: Strike 6딜 → Doom 6")


def test_haunt_and_devour_on_soul():
    print("\n=== Haunt/DevourLife: Soul 플레이 트리거 ===\n")
    combat, player, _ = make_combat()
    combat.draw_pile = [create_card("defend") for _ in range(5)]
    play(combat, "haunt")                 # Haunt 7
    enemy = _enemy(combat)
    hp0 = enemy.current_hp
    play(combat, "soul")                  # Soul 플레이 → Haunt 7 관통
    assert enemy.current_hp == hp0 - 7, hp0 - enemy.current_hp
    # DevourLife: Soul 플레이 시 Osty 소환
    combat2, player2, _ = make_combat(no_osty=True)
    combat2.draw_pile = [create_card("defend") for _ in range(5)]
    play(combat2, "devour_life")          # DevourLife 1
    play(combat2, "soul")                 # Osty 1 소환
    assert player2.osty is not None and player2.osty.max_hp == 1
    print("✅ Haunt 7 관통 / DevourLife Osty 소환 (Soul 플레이 시)")


def test_ethereal_synergy():
    print("\n=== Ethereal 시너지 ===\n")
    # SpiritOfAsh: Ethereal 카드 낼 때마다 블록
    combat, player, _ = make_combat()
    play(combat, "spirit_of_ash")          # 4블록/이더리얼
    b0 = player.block
    play(combat, "parse", energy=3)        # Parse는 Ethereal → +4 블록
    assert player.block == b0 + 4, player.block - b0
    # BansheesCry 코스트 감소: 이번 전투 Ethereal 플레이 2장 → 9 - 4 = 5
    assert combat.ethereal_played_this_combat >= 1
    bc = create_card("banshees_cry")
    combat.ethereal_played_this_combat = 3
    assert bc.dynamic_cost(combat) == 3, bc.dynamic_cost(combat)  # 9 - 6
    # Veilpiercer: 다음 Ethereal 카드 0코스트
    combat3, player3, _ = make_combat()
    play(combat3, "veilpiercer", target=_enemy(combat3))  # Veilpiercer 1
    defile = create_card("defile")
    assert combat3.get_card_cost(defile) == 0, combat3.get_card_cost(defile)
    print("✅ SpiritOfAsh 블록 / BansheesCry 코스트감소 / Veilpiercer 0코스트")


def test_pull_from_below_hits():
    print("\n=== PullFromBelow: 앞선 Ethereal 플레이 수만큼 타격 ===\n")
    combat, player, _ = make_combat()
    # 원본: PullFromBelow 자신은 Ethereal 키워드가 아님 (자기 미집계)
    assert create_card("pull_from_below").is_ethereal is False
    combat.ethereal_played_this_combat = 2  # 앞서 플레이한 이더리얼 2장
    enemy = _enemy(combat)
    hp0 = enemy.current_hp
    # 자신은 Ethereal이 아니므로 카운터는 2로 유지 → 5×2=10
    play(combat, "pull_from_below", target=enemy)
    assert hp0 - enemy.current_hp == 10, hp0 - enemy.current_hp
    print("✅ PullFromBelow: 5딜 × (앞선 Ethereal 2장) = 10, 자신은 비-Ethereal")


def test_oblivion_no_self_trigger():
    print("\n=== Oblivion: 자기 플레이는 Doom 미부여, 이후 카드만 부여 ===\n")
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    play(combat, "oblivion", target=enemy)   # OblivionP 3 — 자기 자신은 Doom 0 (원본 미기록)
    assert enemy.get_power_amount("doom") == 0, enemy.get_power_amount("doom")
    play(combat, "poke", target=enemy)        # 이후 카드 1장 → Doom 3
    assert enemy.get_power_amount("doom") == 3, enemy.get_power_amount("doom")
    play(combat, "poke", target=enemy)        # 또 1장 → Doom 6
    assert enemy.get_power_amount("doom") == 6, enemy.get_power_amount("doom")
    print("✅ Oblivion 자기 미발동 → 이후 2장 = Doom 6")


def test_sic_em_attack_before_power():
    print("\n=== SicEm: 자기 공격은 소환 미발동, 이후 Osty 공격만 소환 ===\n")
    combat, player, _ = make_combat()
    player.summon_osty(20)                    # Osty max_hp 21
    enemy = _enemy(combat)
    mhp0 = player.osty.max_hp
    play(combat, "sic_em", target=enemy)      # Osty 공격(파워 부여 전 → 소환 미발동) → SicEm 3 부여
    assert enemy.get_power_amount("sic_em") == 3, enemy.get_power_amount("sic_em")
    assert player.osty.max_hp == mhp0, "SicEm 자기 공격이 소환을 발동시킴"
    play(combat, "poke", target=enemy)        # 이후 Osty 공격 → SicEm 소환 3
    assert player.osty.max_hp == mhp0 + 3, player.osty.max_hp
    print("✅ SicEm 자기 공격 미발동 → 이후 Osty 공격이 소환 3")


def test_necro_mastery_reflect():
    print("\n=== NecroMastery: Osty 피해 반사 ===\n")
    combat, player, monsters = make_combat(("big_dummy", "big_dummy"))
    play(combat, "necro_mastery", energy=2)   # Summon 5 + NecroMastery 1
    e0, e1 = combat.alive_enemies
    h0, h1 = e0.current_hp, e1.current_hp
    player.osty.take_damage(4, source=monsters[0])  # Osty 4 피해 → 모든 적 4 반사
    assert e0.current_hp == h0 - 4 and e1.current_hp == h1 - 4, "반사 실패"
    print("✅ NecroMastery: Osty 4 피해 → 모든 적 4 반사")


def test_debilitate_multiplier():
    print("\n=== Debilitate: 취약 배수 강화 ===\n")
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    enemy.apply_power(Vulnerable(3), applier=player)
    # 일반 취약: 10 × 1.5 = 15
    dmg_normal = enemy._powers["vulnerable"].modify_incoming(10, player)
    assert dmg_normal == 15, dmg_normal
    enemy.apply_power(__import__("sts2_sim.models.sts2_power", fromlist=["Debilitate"]).Debilitate(2), applier=player)
    # Debilitate: 10 × 2.0 = 20
    dmg_deb = enemy._powers["vulnerable"].modify_incoming(10, player)
    assert dmg_deb == 20, dmg_deb
    print("✅ Debilitate: 취약 배수 1.5 → 2.0 (10→15 vs 10→20)")


def test_hang_multiplier():
    print("\n=== Hang: 스택 배수 ===\n")
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    enemy._current_hp = 500
    h0 = enemy.current_hp
    play(combat, "hang", target=enemy)   # 10딜, Hang 2
    assert h0 - enemy.current_hp == 10, h0 - enemy.current_hp
    assert enemy.get_power_amount("hang") == 2
    h1 = enemy.current_hp
    play(combat, "hang", target=enemy)   # 10×2 = 20딜, Hang +2 → 4
    assert h1 - enemy.current_hp == 20, h1 - enemy.current_hp
    assert enemy.get_power_amount("hang") == 4
    print("✅ Hang: 1회 10딜 → 2회 20딜 (스택 배수)")


def test_lethality_first_attack():
    print("\n=== Lethality: 첫 공격 배수 ===\n")
    combat, player, _ = make_combat()
    play(combat, "lethality")            # +50% 첫 공격, Ethereal
    enemy = _enemy(combat)
    h0 = enemy.current_hp
    play(combat, "strike", target=enemy)   # 6 × 1.5 = 9 (첫 공격)
    assert h0 - enemy.current_hp == 9, h0 - enemy.current_hp
    h1 = enemy.current_hp
    play(combat, "strike", target=enemy)   # 6 (두번째 공격, 배수 없음)
    assert h1 - enemy.current_hp == 6, h1 - enemy.current_hp
    print("✅ Lethality: 첫 Strike 9 / 두번째 Strike 6")


def test_sacrifice_block():
    print("\n=== Sacrifice: Osty 최대HP×2 블록 ===\n")
    combat, player, _ = make_combat()
    player.summon_osty(12)   # maxHP 커지게 (기존 1 + 12 = 13)
    mhp = player.osty.max_hp
    play(combat, "sacrifice")
    assert player.osty.is_dead, "Osty 미사망"
    assert player.block == mhp * 2, f"{player.block} != {mhp*2}"
    print(f"✅ Sacrifice: Osty 죽이고 {mhp}×2={mhp*2} 블록")


def test_end_of_days_instant_kill():
    print("\n=== EndOfDays: 즉시 Doom 처치 ===\n")
    combat, player, monsters = make_combat(("big_dummy", "big_dummy"))
    for e in combat.alive_enemies:
        e._current_hp = 20   # <= 29
    play(combat, "end_of_days", energy=3)
    assert len(combat.alive_enemies) == 0, "즉시 처치 실패"
    print("✅ EndOfDays: Doom 29 부여 후 HP<=29 적 즉사")


def test_the_scythe_scaling():
    print("\n=== TheScythe: 영구 성장 ===\n")
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    enemy._current_hp = 500
    scythe = create_card("the_scythe")
    combat.hand.append(scythe)
    combat.player.energy = 2
    h0 = enemy.current_hp
    combat.play_card(scythe, enemy)      # 13딜, +4 → 17
    assert h0 - enemy.current_hp == 13
    assert scythe._current_damage == 17
    print("✅ TheScythe: 13딜 후 다음 17로 영구 성장")


def test_times_up_and_no_escape():
    print("\n=== TimesUp / NoEscape: Doom 연동 ===\n")
    combat, player, _ = make_combat()
    enemy = _enemy(combat)
    enemy._current_hp = 500
    enemy.apply_power(Doom(14), applier=player)
    h0 = enemy.current_hp
    play(combat, "times_up", target=enemy, energy=2)  # Doom 14 = 14딜
    assert h0 - enemy.current_hp == 14, h0 - enemy.current_hp
    # NoEscape: 기존 Doom 14 (1×10=+5) → base 10 + 5 = 15 추가
    d0 = enemy.get_power_amount("doom")
    play(combat, "no_escape", target=enemy)
    assert enemy.get_power_amount("doom") == d0 + 15, enemy.get_power_amount("doom") - d0
    print("✅ TimesUp: Doom 14 = 14딜 / NoEscape: Doom 스케일 +15")


def test_melancholy_cost_reduction():
    print("\n=== Melancholy: 사망 시 코스트 감소 ===\n")
    combat, player, monsters = make_combat(("big_dummy", "big_dummy"))
    mel = create_card("melancholy")
    assert mel.dynamic_cost(combat) == 3
    combat.alive_enemies[0]._current_hp = 0
    combat.reap_deaths()
    assert combat.deaths_this_combat == 1
    assert mel.dynamic_cost(combat) == 2, mel.dynamic_cost(combat)
    print("✅ Melancholy: 적 1 사망 → 코스트 3→2")


def test_summon_next_turn():
    print("\n=== Invoke: 다음 턴 소환/에너지 ===\n")
    combat, player, _ = make_combat(no_osty=True)
    play(combat, "invoke")   # SummonNextTurn 2 + EnergyNextTurn 2
    assert player.osty is None, "Invoke가 즉시 소환함"
    # 다음 턴 시작 시뮬레이션
    for p in list(player._powers.values()):
        if hasattr(p, "on_turn_start"):
            p.on_turn_start()
    assert player.osty is not None and player.osty.max_hp == 2
    print("✅ Invoke: 다음 턴 시작 시 Osty 2 소환")


def test_full_combats_all_cards():
    print("\n=== 전 카드 전투 스모크 (그리디) ===\n")
    pool = (NECROBINDER_POOL_BY_RARITY[Rarity.COMMON]
            + NECROBINDER_POOL_BY_RARITY[Rarity.UNCOMMON]
            + NECROBINDER_POOL_BY_RARITY[Rarity.RARE]
            + ["protector", "forbidden_grimoire"])
    policy = GreedyPolicy()
    fails = []
    for cid in pool:
        try:
            player = Player(create_character("necrobinder"))
            monsters = [create_monster("big_dummy")]
            combat = CombatState(player, monsters, seed=7)
            combat.start()
            # 카드 1장을 덱에 넣고 손패에서 강제로 플레이해 크래시 없나 확인
            card = create_card(cid)
            combat.player.energy = 6
            combat.hand.append(card)
            tgt = combat.alive_enemies[0] if combat.alive_enemies else None
            combat.play_card(card, tgt)
        except Exception as e:  # noqa: BLE001
            fails.append((cid, repr(e)))
    assert not fails, f"플레이 크래시: {fails[:5]}"
    print(f"✅ 전 카드 {len(pool)}종 개별 플레이 크래시 없음")


def test_greedy_run():
    print("\n=== Necrobinder 그리디 런 (재현성) ===\n")
    r1 = RunState("necrobinder", seed=123).play(policy=GreedyPolicy())
    r2 = RunState("necrobinder", seed=123).play(policy=GreedyPolicy())
    assert r1.floors_cleared == r2.floors_cleared, "재현성 실패"
    assert r1.final_hp == r2.final_hp
    print(f"✅ 시드 123 재현: {r1.floors_cleared}/{r1.total_floors}층, HP {r1.final_hp}")


def main():
    test_pool_registration()
    test_soul_token()
    test_osty_summon_stack_revive()
    test_osty_attack_and_missing()
    test_die_for_you_redirect()
    test_doom_kill()
    test_blight_strike_doom()
    test_calcify_boosts_osty()
    test_reaper_form_doom()
    test_haunt_and_devour_on_soul()
    test_ethereal_synergy()
    test_pull_from_below_hits()
    test_oblivion_no_self_trigger()
    test_sic_em_attack_before_power()
    test_necro_mastery_reflect()
    test_debilitate_multiplier()
    test_hang_multiplier()
    test_lethality_first_attack()
    test_sacrifice_block()
    test_end_of_days_instant_kill()
    test_the_scythe_scaling()
    test_times_up_and_no_escape()
    test_melancholy_cost_reduction()
    test_summon_next_turn()
    test_full_combats_all_cards()
    test_greedy_run()
    print("\n🎉 Phase 6e 전체 테스트 통과!")


if __name__ == "__main__":
    main()
