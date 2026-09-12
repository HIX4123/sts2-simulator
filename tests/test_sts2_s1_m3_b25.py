#!/usr/bin/env python3
"""S1.M3.B25 — 런 루프 인카운터 해금 + 렐릭 배치 25 회귀 테스트."""
from sts2_sim.core.combat import CombatState
from sts2_sim.core.encounters import (
    BOSS_POOL, ELITE_POOL, HARD_POOL, EASY_POOL, MEDIUM_POOL,
)
from sts2_sim.core.run import DEFAULT_FLOOR_PLAN, RunState
from sts2_sim.entities.creature import Creature
from sts2_sim.entities.player import Player
from sts2_sim.entities.sts2_character import Ironclad
from sts2_sim.entities.sts2_monster import BigDummy
from sts2_sim.models.sts2_card import CardType
from sts2_sim.models.sts2_relic import (
    RELIC_REGISTRY, RelicRarity,
    Sai, VeryHotCocoa, IronClub,
    MrStruggles, RoyalPoison, LostWisp,
    HappyFlower, Pendulum,
    HornCleat, Nunchaku, TuningFork, Kusarigama,
    CaptainsWheel, Pocketwatch, BlackBlood,
    create_relic,
)


class EndTurnPolicy:
    def choose(self, combat):
        return None


class DummyAttack:
    """테스트용 1코스트 공격 카드."""
    card_type = CardType.ATTACK
    card_id = "dummy_attack"
    name = "Dummy Attack"
    cost = 1
    upgraded = False
    exhausts = False
    innate = False
    retain = False
    damage = 6
    block = 0
    def use(self, player, target, combat):
        target.take_damage(6, source=player)
    def damage_estimate(self, player, target, combat):
        return 6.0
    def block_estimate(self, player, combat):
        return 0.0


class DummySkill:
    """테스트용 1코스트 스킬 카드."""
    card_type = CardType.SKILL
    card_id = "dummy_skill"
    name = "Dummy Skill"
    cost = 1
    upgraded = False
    exhausts = False
    innate = False
    retain = False
    damage = 0
    block = 5
    def use(self, player, target, combat):
        player.gain_block(5)
    def damage_estimate(self, player, target, combat):
        return 0.0
    def block_estimate(self, player, combat):
        return 5.0


class DummyPower:
    """테스트용 1코스트 파워 카드."""
    card_type = CardType.POWER
    card_id = "dummy_power"
    name = "Dummy Power"
    cost = 1
    upgraded = False
    exhausts = False
    innate = False
    retain = False
    damage = 0
    block = 0
    def use(self, player, target, combat):
        pass
    def damage_estimate(self, player, target, combat):
        return 0.0
    def block_estimate(self, player, combat):
        return 0.0


# ─── 렐릭 레어리티 테스트 ───

def test_ancient_and_event_rarity_exist():
    assert hasattr(RelicRarity, "ANCIENT")
    assert hasattr(RelicRarity, "EVENT")


def test_registry_has_at_least_46_relics():
    assert len(RELIC_REGISTRY) >= 46


def _make_combat(*relics, monster=None):
    """테스트용 전투 세팅 — Player에 렐릭 장착."""
    char = Ironclad()
    player = Player(char, deck=[])
    player.relics = []
    for relic in relics:
        relic.on_equip(player)
        player.relics.append(relic)
    combat = CombatState(player, [monster or BigDummy()], seed=42)
    return player, combat


# ─── Sai ───

def test_sai_block_every_turn():
    player, combat = _make_combat(Sai())
    combat.start()
    relic = player.relics[0]
    relic.on_turn_start(combat, turn=1)
    assert player.block >= 7
    relic.on_turn_start(combat, turn=2)
    assert player.block >= 14


# ─── VeryHotCocoa ───

def test_very_hot_cocoa_energy_turn1_only():
    player, combat = _make_combat(VeryHotCocoa())
    combat.start()
    relic = player.relics[0]
    e0 = player.energy
    relic.on_turn_start(combat, turn=1)
    assert player.energy == e0 + 4
    relic.on_turn_start(combat, turn=2)
    assert player.energy == e0 + 4  # no change on turn 2


# ─── HappyFlower ───

def test_happy_flower_every_3_turns():
    player, combat = _make_combat(HappyFlower())
    combat.start()
    relic = player.relics[0]
    relic.on_combat_start(combat)
    e0 = player.energy
    relic.on_turn_start(combat, turn=1)
    assert player.energy == e0
    relic.on_turn_start(combat, turn=2)
    assert player.energy == e0
    relic.on_turn_start(combat, turn=3)
    assert player.energy == e0 + 1


# ─── Pendulum ───

def test_pendulum_draw_every_3_turns():
    player, combat = _make_combat(Pendulum())
    combat.start()
    relic = player.relics[0]
    relic.on_combat_start(combat)
    relic.on_turn_start(combat, turn=1)
    assert relic.counter == 1
    relic.on_turn_start(combat, turn=2)
    assert relic.counter == 2
    relic.on_turn_start(combat, turn=3)
    assert relic.counter == 3


# ─── HornCleat ───

def test_horn_cleat_turn2_only():
    player, combat = _make_combat(HornCleat())
    combat.start()
    relic = player.relics[0]
    relic.on_turn_start(combat, turn=1)
    assert player.block == 0
    relic.on_turn_start(combat, turn=2)
    assert player.block == 14
    relic.on_turn_start(combat, turn=3)
    assert player.block == 14


# ─── CaptainsWheel ───

def test_captains_wheel_turn3_only():
    player, combat = _make_combat(CaptainsWheel())
    combat.start()
    relic = player.relics[0]
    relic.on_turn_start(combat, turn=1)
    assert player.block == 0
    relic.on_turn_start(combat, turn=2)
    assert player.block == 0
    relic.on_turn_start(combat, turn=3)
    assert player.block == 18


# ─── MrStruggles ───

def test_mr_struggles_damage_scales_with_turn():
    monster = BigDummy()
    player, combat = _make_combat(MrStruggles(), monster=monster)
    combat.start()
    relic = player.relics[0]
    hp_before = monster.current_hp
    relic.on_turn_start(combat, turn=1)
    assert monster.current_hp == hp_before - 1
    hp_before = monster.current_hp
    relic.on_turn_start(combat, turn=5)
    assert monster.current_hp == hp_before - 5


# ─── RoyalPoison ───

def test_royal_poison_self_damage_turn1_only():
    player, combat = _make_combat(RoyalPoison())
    combat.start()
    relic = player.relics[0]
    hp_before = player.current_hp
    relic.on_turn_start(combat, turn=1)
    assert player.current_hp == hp_before - 4
    hp_before = player.current_hp
    relic.on_turn_start(combat, turn=2)
    assert player.current_hp == hp_before


# ─── Nunchaku ───

def test_nunchaku_energy_every_10_attacks():
    player, combat = _make_combat(Nunchaku())
    combat.start()
    relic = player.relics[0]
    relic.on_combat_start(combat)
    atk = DummyAttack()
    e0 = player.energy
    for _ in range(9):
        relic.on_card_played(atk, combat)
    assert player.energy == e0
    relic.on_card_played(atk, combat)
    assert player.energy == e0 + 1


# ─── TuningFork ───

def test_tuning_fork_block_every_10_skills():
    player, combat = _make_combat(TuningFork())
    combat.start()
    relic = player.relics[0]
    relic.on_combat_start(combat)
    sk = DummySkill()
    b0 = player.block
    for _ in range(9):
        relic.on_card_played(sk, combat)
    assert player.block == b0
    relic.on_card_played(sk, combat)
    assert player.block == b0 + 7


# ─── IronClub ───

def test_iron_club_draw_every_4_cards():
    player, combat = _make_combat(IronClub())
    combat.start()
    relic = player.relics[0]
    relic.on_combat_start(combat)
    atk = DummyAttack()
    for _ in range(3):
        relic.on_card_played(atk, combat)
    assert relic.counter == 3
    relic.on_card_played(atk, combat)
    assert relic.counter == 4


# ─── Kusarigama ───

def test_kusarigama_damage_every_3_attacks_in_turn():
    monster = BigDummy()
    player, combat = _make_combat(Kusarigama(), monster=monster)
    combat.start()
    relic = player.relics[0]
    relic.on_turn_start(combat, turn=1)
    atk = DummyAttack()
    hp_before = monster.current_hp
    relic.on_card_played(atk, combat)
    relic.on_card_played(atk, combat)
    assert monster.current_hp == hp_before
    relic.on_card_played(atk, combat)
    assert monster.current_hp == hp_before - 6


# ─── LostWisp ───

def test_lost_wisp_power_card_triggers():
    monster = BigDummy()
    player, combat = _make_combat(LostWisp(), monster=monster)
    combat.start()
    relic = player.relics[0]
    hp_before = monster.current_hp
    relic.on_card_played(DummyPower(), combat)
    assert monster.current_hp == hp_before - 8
    hp_before = monster.current_hp
    relic.on_card_played(DummyAttack(), combat)
    assert monster.current_hp == hp_before


# ─── Pocketwatch ───

def test_pocketwatch_bonus_draw_after_low_turn():
    player, combat = _make_combat(Pocketwatch())
    combat.start()
    relic = player.relics[0]
    relic.on_combat_start(combat)
    assert relic.modify_hand_draw(5, turn=1) == 5  # turn 1 exempt
    relic.on_turn_start(combat, turn=2)
    relic._cards_last_turn = 2
    assert relic.modify_hand_draw(5, turn=2) == 8  # 5 + 3
    relic._cards_last_turn = 5
    assert relic.modify_hand_draw(5, turn=3) == 5  # no bonus


# ─── BlackBlood ───

def test_black_blood_heal_on_victory():
    player, combat = _make_combat(BlackBlood())
    relic = player.relics[0]
    player.heal(-(player.max_hp - 50))  # HP를 50으로 낮춤
    assert player.current_hp == 50
    relic.on_combat_end(victory=True)
    assert player.current_hp == 62
    relic.on_combat_end(victory=False)
    assert player.current_hp == 62  # no heal on defeat


# ─── 런 루프 인카운터 풀 ───

def test_boss_pool_has_7_encounters():
    assert len(BOSS_POOL) == 7
    for boss_id in BOSS_POOL:
        assert boss_id.endswith("_boss"), boss_id


def test_elite_pool_has_10_encounters():
    assert len(ELITE_POOL) == 10


def test_hard_pool_has_2_encounters():
    assert len(HARD_POOL) == 2


def test_floor_plan_includes_boss():
    assert "B" in DEFAULT_FLOOR_PLAN
    assert DEFAULT_FLOOR_PLAN[-1] == "B"


def test_run_reaches_boss_floor():
    """런이 보스 층(F8)까지 도달하는지 확인 (스모크 테스트)."""
    from sts2_sim.core.policy import GreedyPolicy
    runner = RunState("ironclad", seed=0)
    result = runner.play(GreedyPolicy())
    assert result.total_floors == 8
    # F7 엘리트를 통과해 보스 층(F8)에 도달해야 함
    assert result.floors_cleared >= 7


# ─── run_all ───

_TESTS = [
    test_ancient_and_event_rarity_exist,
    test_registry_has_at_least_46_relics,
    test_sai_block_every_turn,
    test_very_hot_cocoa_energy_turn1_only,
    test_happy_flower_every_3_turns,
    test_pendulum_draw_every_3_turns,
    test_horn_cleat_turn2_only,
    test_captains_wheel_turn3_only,
    test_mr_struggles_damage_scales_with_turn,
    test_royal_poison_self_damage_turn1_only,
    test_nunchaku_energy_every_10_attacks,
    test_tuning_fork_block_every_10_skills,
    test_iron_club_draw_every_4_cards,
    test_kusarigama_damage_every_3_attacks_in_turn,
    test_lost_wisp_power_card_triggers,
    test_pocketwatch_bonus_draw_after_low_turn,
    test_black_blood_heal_on_victory,
    test_boss_pool_has_7_encounters,
    test_elite_pool_has_10_encounters,
    test_hard_pool_has_2_encounters,
    test_floor_plan_includes_boss,
    test_run_reaches_boss_floor,
]


def main():
    for test in _TESTS:
        test()
        print(f"✅ {test.__name__}")
    print(f"\n✅ S1.M3.B25 전체 테스트 통과! ({len(_TESTS)}개)")


if __name__ == "__main__":
    main()
