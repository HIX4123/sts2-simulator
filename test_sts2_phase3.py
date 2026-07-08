#!/usr/bin/env python3
"""
STS2 Phase 3 통합 테스트.
Orb 시스템 (5종) + 실제 캐릭터 로스터 + 스타터 카드/렐릭 + Osty/Stars 메카닉.
모든 기대값은 디컴파일 sts2.dll 데이터 기준.
"""
import random

from sts2_sim.entities.creature import Creature, Osty
from sts2_sim.models.sts2_orb import (
    LightningOrb, FrostOrb, DarkOrb, PlasmaOrb, GlassOrb,
    OrbQueue, create_orb,
)
from sts2_sim.models.sts2_power import Focus, Strength, Weak, create_power
from sts2_sim.models.sts2_card import (
    Strike, Defend, Bash, Neutralize, Survivor,
    Zap, Dualcast, Bodyguard, Unleash, FallingStar, Venerate,
    create_card,
)
from sts2_sim.models.sts2_relic import (
    CrackedCore, BoundPhylactery, DivineRight, RingOfTheSnake, create_relic,
)


class FakePlayer(Creature):
    """전투 중 플레이어 상태 (Phase 4의 Player 프로토콜 축소판)."""

    def __init__(self, name="Player", max_hp=75, orb_slots=3):
        super().__init__(name, max_hp)
        self.orb_queue = OrbQueue(orb_slots)
        self.energy = 3
        self.stars = 0
        self.osty = None

    def gain_energy(self, amount: int) -> None:
        self.energy += amount

    def gain_stars(self, amount: int) -> None:
        self.stars += amount

    def summon_osty(self, amount: int) -> None:
        if self.osty is None or self.osty.is_dead:
            self.osty = Osty(amount)
        else:
            self.osty.gain_summon_hp(amount)


class FakeCombat:
    """오브/카드가 사용하는 전투 컨텍스트 축소판."""

    def __init__(self, enemies, seed=42):
        self.alive_enemies = enemies
        self.rng = random.Random(seed)


def test_orbs():
    print("=== Orb 시스템 (디컴파일 수치) ===\n")

    # Lightning: 패시브 3딜 / 이보크 8딜
    player = FakePlayer()
    enemy = Creature("Enemy", 50)
    combat = FakeCombat([enemy])
    orb = LightningOrb()
    orb.owner = player
    orb.passive(combat)
    assert enemy.current_hp == 47, f"Lightning 패시브 실패: {enemy.current_hp}"
    orb.evoke(combat)
    assert enemy.current_hp == 39, f"Lightning 이보크 실패: {enemy.current_hp}"
    print(f"✅ Lightning: 패시브 3딜 → 이보크 8딜 (적 HP 50→{enemy.current_hp})")

    # Frost: 패시브 2블록 / 이보크 5블록
    player = FakePlayer()
    orb = FrostOrb()
    orb.owner = player
    orb.passive(None)
    assert player.block == 2
    orb.evoke(None)
    assert player.block == 7
    print(f"✅ Frost: 패시브 2블록 → 이보크 5블록 (블록 {player.block})")

    # Dark: 패시브마다 이보크값 +6, 최저 HP 적 타격
    player = FakePlayer()
    weak_enemy = Creature("Weak", 10)
    strong_enemy = Creature("Strong", 100)
    combat = FakeCombat([strong_enemy, weak_enemy])
    orb = DarkOrb()
    orb.owner = player
    assert orb.evoke_val == 6
    orb.passive(combat)
    orb.passive(combat)
    assert orb.evoke_val == 18, f"Dark 누적 실패: {orb.evoke_val}"
    orb.evoke(combat)
    assert weak_enemy.is_dead and strong_enemy.current_hp == 100, "Dark는 최저 HP 적을 쳐야 함"
    print(f"✅ Dark: 6 → 패시브×2 → 18딜, 최저 HP 적 처치")

    # Plasma: 턴 시작 에너지 +1 / 이보크 +2 (Focus 미적용)
    player = FakePlayer()
    orb = PlasmaOrb()
    orb.owner = player
    assert orb.passive_timing == "turn_start"
    player.apply_power(Focus(3))
    assert orb.passive_val == 1, "Plasma는 Focus 미적용이어야 함"
    orb.passive(None)
    orb.evoke(None)
    assert player.energy == 3 + 1 + 2
    print(f"✅ Plasma: 턴 시작 +1, 이보크 +2, Focus 미적용 (에너지 {player.energy})")

    # Glass: 전체 4딜, 트리거마다 -1, 이보크 = 패시브×2
    player = FakePlayer()
    e1, e2 = Creature("E1", 30), Creature("E2", 30)
    combat = FakeCombat([e1, e2])
    orb = GlassOrb()
    orb.owner = player
    orb.passive(combat)  # 4딜 전체
    assert e1.current_hp == 26 and e2.current_hp == 26
    orb.passive(combat)  # 3딜 전체
    assert e1.current_hp == 23 and e2.current_hp == 23
    assert orb.evoke_val == 4, f"Glass 이보크값: {orb.evoke_val} (2×2)"
    orb.evoke(combat)
    assert e1.current_hp == 19 and e2.current_hp == 19
    print(f"✅ Glass: 4→3딜 감쇠, 이보크 {orb.evoke_val}딜 전체")

    # Focus 적용 (Lightning)
    player = FakePlayer()
    player.apply_power(Focus(2))
    enemy = Creature("Enemy", 50)
    combat = FakeCombat([enemy])
    orb = LightningOrb()
    orb.owner = player
    assert orb.passive_val == 5, f"Focus 적용 실패: {orb.passive_val}"
    print(f"✅ Focus(2): Lightning 패시브 3→5")


def test_orb_queue():
    print("\n=== OrbQueue (채널/이보크/슬롯) ===\n")

    player = FakePlayer(orb_slots=3)
    enemy = Creature("Enemy", 100)
    combat = FakeCombat([enemy])

    # 채널 3개 (슬롯 꽉 참)
    for _ in range(3):
        player.orb_queue.channel(FrostOrb(), player, combat)
    assert len(player.orb_queue) == 3

    # 4번째 채널 → 선두 Frost 자동 이보크 (5블록)
    player.orb_queue.channel(LightningOrb(), player, combat)
    assert len(player.orb_queue) == 3
    assert player.block == 5, f"자동 이보크 실패: 블록 {player.block}"
    print(f"✅ 슬롯 초과 채널 → 선두 오브 자동 이보크 (블록 {player.block})")

    # 턴 종료 패시브: Frost 2개(2+2블록) + Lightning(3딜)
    player.orb_queue.trigger_turn_end(combat)
    assert player.block == 9, f"턴 종료 패시브 실패: 블록 {player.block}"
    assert enemy.current_hp == 97
    print(f"✅ 턴 종료 패시브: Frost×2 + Lightning (블록 {player.block}, 적 HP {enemy.current_hp})")


def test_starter_cards():
    print("\n=== 스타터 카드 (디컴파일 수치) ===\n")

    # Zap: 라이트닝 채널, 업글 시 0코스트
    player = FakePlayer()
    combat = FakeCombat([Creature("E", 50)])
    zap = Zap()
    assert zap.cost == 1
    zap.use(player, [], combat)
    assert len(player.orb_queue) == 1 and player.orb_queue.orbs[0].orb_id == "lightning"
    zap.upgrade()
    assert zap.cost == 0
    print(f"✅ Zap: 라이트닝 채널, 업글 후 0코스트")

    # Dualcast: 선두 오브 2회 이보크
    player = FakePlayer()
    enemy = Creature("E", 50)
    combat = FakeCombat([enemy])
    player.orb_queue.channel(LightningOrb(), player, combat)
    Dualcast().use(player, [], combat)
    assert enemy.current_hp == 50 - 16, f"Dualcast 실패: {enemy.current_hp} (8×2 기대)"
    assert len(player.orb_queue) == 0
    print(f"✅ Dualcast: 8딜 이보크 ×2 = 16딜, 오브 소진")

    # Neutralize: 3딜 + 약화 1
    player = FakePlayer()
    enemy = Creature("E", 50)
    Neutralize().use(player, [enemy])
    assert enemy.current_hp == 47
    assert enemy.get_power_amount("weak") == 1
    print(f"✅ Neutralize: 3딜 + 약화 1")

    # Survivor: 8블록
    player = FakePlayer()
    Survivor().use(player, [])
    assert player.block == 8
    print(f"✅ Survivor: 8블록")

    # Bash: 8딜 + 취약 2 → 취약 상태에서 Strike 6×1.5=9딜
    player = FakePlayer()
    enemy = Creature("E", 50)
    Bash().use(player, [enemy])
    assert enemy.current_hp == 42
    assert enemy.get_power_amount("vulnerable") == 2
    Strike().use(player, [enemy])
    assert enemy.current_hp == 42 - 9, f"취약 Strike 실패: {enemy.current_hp}"
    print(f"✅ Bash: 8딜+취약2, 이후 Strike 9딜 (6×1.5)")

    # Bodyguard: Osty 5 소환 / Unleash: (6+OstyHP)딜
    player = FakePlayer()
    enemy = Creature("E", 50)
    Bodyguard().use(player, [])
    assert player.osty is not None and player.osty.current_hp == 5
    Unleash().use(player, [enemy])
    assert enemy.current_hp == 50 - 11, f"Unleash 실패: {enemy.current_hp} (6+5 기대)"
    print(f"✅ Bodyguard: Osty 5 소환 → Unleash: 11딜 (6+5)")

    # FallingStar: 8딜 + 약화1 + 취약1, 별 2 소모 명시
    player = FakePlayer()
    enemy = Creature("E", 50)
    fs = FallingStar()
    assert fs.star_cost == 2 and fs.cost == 0
    fs.use(player, [enemy])
    assert enemy.current_hp == 42
    assert enemy.get_power_amount("weak") == 1 and enemy.get_power_amount("vulnerable") == 1
    print(f"✅ FallingStar: 8딜+약화1+취약1 (별 {fs.star_cost} 소모)")

    # Venerate: 별 2 획득
    player = FakePlayer()
    Venerate().use(player, [])
    assert player.stars == 2
    print(f"✅ Venerate: 별 2 획득")

    # 팩토리에 신규 카드 전부 등록 확인
    for cid in ["zap", "dualcast", "neutralize", "survivor", "bodyguard", "unleash", "falling_star", "venerate"]:
        assert create_card(cid) is not None, f"팩토리 누락: {cid}"
    print(f"✅ 카드 팩토리: 신규 8종 전부 등록")


def test_starter_relics():
    print("\n=== 스타터 렐릭 (디컴파일 동작) ===\n")

    # CrackedCore: 전투 시작 시 라이트닝 채널
    player = FakePlayer()
    combat = FakeCombat([Creature("E", 50)])
    core = CrackedCore()
    core.on_equip(player)
    core.on_combat_start(combat)
    assert len(player.orb_queue) == 1 and player.orb_queue.orbs[0].orb_id == "lightning"
    print(f"✅ CrackedCore: 전투 시작 시 라이트닝 채널")

    # BoundPhylactery: 전투 시작 + 2턴째부터 매 턴 Osty 1
    player = FakePlayer()
    phylactery = BoundPhylactery()
    phylactery.on_equip(player)
    phylactery.on_combat_start()
    assert player.osty is not None and player.osty.current_hp == 1
    phylactery.on_turn_start(turn=1)  # 1턴은 미발동
    assert player.osty.current_hp == 1
    phylactery.on_turn_start(turn=2)  # 2턴부터 +1
    assert player.osty.current_hp == 2
    print(f"✅ BoundPhylactery: 시작 1 + 2턴째 +1 (Osty HP {player.osty.current_hp})")

    # DivineRight: 전투 입장 시 별 3
    player = FakePlayer()
    dr = DivineRight()
    dr.on_equip(player)
    dr.on_combat_start()
    assert player.stars == 3
    print(f"✅ DivineRight: 별 3 획득")

    # 렐릭 팩토리
    for rid in ["cracked_core", "bound_phylactery", "divine_right", "ring_of_the_snake"]:
        assert create_relic(rid) is not None, f"팩토리 누락: {rid}"
    print(f"✅ 렐릭 팩토리: 스타터 4종 전부 등록")


def test_creature_pipeline():
    print("\n=== Creature 데미지 파이프라인 ===\n")

    attacker = Creature("Attacker", 50)
    target = Creature("Target", 50)

    # Strength(3) + Weak: (10+3)×0.75 = 9
    attacker.apply_power(Strength(3))
    attacker.apply_power(Weak(2))
    dmg = attacker.compute_attack_damage(10)
    assert dmg == 9, f"파이프라인 실패: {dmg} (13×0.75=9 기대)"
    print(f"✅ 공격측: (10+힘3)×약화0.75 = {dmg}")

    # 블록 관통
    target.gain_block(5)
    result = target.take_damage(dmg, source=attacker)
    assert result["hp_lost"] == 4 and target.current_hp == 46
    print(f"✅ 피격측: 블록 5 흡수 후 HP 4 손실")


def main():
    print("🧪 STS2 Phase 3 통합 테스트\n")
    test_orbs()
    test_orb_queue()
    test_starter_cards()
    test_starter_relics()
    test_creature_pipeline()

    print("\n" + "=" * 60)
    print("✅ Phase 3 모든 테스트 통과!")
    print("=" * 60)
    print("\n📊 Phase 3 구현 현황:")
    print("  ✅ Orb 시스템: 5종 (Lightning/Frost/Dark/Plasma/Glass) + OrbQueue")
    print("  ✅ 실제 STS2 로스터: Ironclad/Silent/Defect/Necrobinder/Regent")
    print("  ✅ 스타터 카드 14종 (실제 수치), 스타터 렐릭 5종")
    print("  ✅ Osty 소환수 / Stars 자원 / Focus 파워")


if __name__ == "__main__":
    main()
