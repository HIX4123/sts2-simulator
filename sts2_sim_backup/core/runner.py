"""
RunRunner — 3-Act 풀 런 루프.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Callable

from sts2_sim.rng.seeded_rng import SeededRng
from sts2_sim.map.act_map import ActMap, RoomType, MapNode
from sts2_sim.map.room_encounters import make_encounter
from sts2_sim.map.events import resolve_event, EVENT_POOL_BY_ACT
from sts2_sim.map.shop import run_shop
from sts2_sim.core.combat_state import CombatState
from sts2_sim.core.combat_manager import CombatManager, apply_play_card
from sts2_sim.entities.player import Player
from sts2_sim.hooks.hook_bus import HookBus


@dataclass
class RunConfig:
    seed: int = 42
    num_acts: int = 3
    verbose: bool = False


@dataclass
class FloorResult:
    floor: int
    act: int
    room_type: RoomType
    combat_won: Optional[bool] = None
    hp_after: int = 0
    gold_after: int = 0
    notes: str = ""


@dataclass
class RunResult:
    character: str
    seed: int
    won: bool
    floors_cleared: int
    final_hp: int
    final_gold: int
    floor_log: list[FloorResult] = field(default_factory=list)
    cause_of_death: str = ""


# ─────────────────────────────────────────
# 카드 플레이 정책
# ─────────────────────────────────────────

def _card_score(card, state) -> float:
    from sts2_sim.models.card_model import CardType
    ct = getattr(card, 'card_type', None)
    cost = max(1, card.energy_cost) if card.energy_cost > 0 else 1
    hp_pct = state.player.current_hp / max(1, state.player.max_hp)

    if card.energy_cost == 0:
        return 100.0
    if ct == CardType.POWER:
        return 7.0 / cost
    if ct == CardType.ATTACK:
        return (10.0 if hp_pct >= 0.4 else 4.0) / cost
    if ct == CardType.SKILL:
        card_id = getattr(card, 'card_id', '')
        is_block = any(k in card_id for k in ('defend','shrug','iron_wave','deflect'))
        if is_block:
            return (12.0 if hp_pct < 0.5 else 6.0) / cost
        return 5.0 / cost
    return 1.0 / cost


def greedy_policy(state: CombatState):
    played = True
    while played:
        played = False
        playable = [c for c in state.hand if c.can_play(state)]
        if not playable:
            break
        playable.sort(key=lambda c: _card_score(c, state), reverse=True)
        card = playable[0]
        target = state.get_random_enemy()
        if apply_play_card(state, card, target):
            played = True
        if state.is_over:
            break


# ─────────────────────────────────────────
# 보상 처리
# ─────────────────────────────────────────

def _combat_reward(player, room_type, act, rng, fr, verbose):
    gold_table = {
        (1, RoomType.MONSTER): (10, 20),
        (1, RoomType.ELITE):   (25, 40),
        (1, RoomType.BOSS):    (80, 100),
        (2, RoomType.MONSTER): (18, 28),
        (2, RoomType.ELITE):   (35, 55),
        (2, RoomType.BOSS):    (95, 115),
        (3, RoomType.MONSTER): (25, 35),
        (3, RoomType.ELITE):   (40, 60),
        (3, RoomType.BOSS):    (100, 130),
    }
    lo, hi = gold_table.get((act, room_type), (10, 20))
    gold = rng.next_int(hi - lo) + lo
    player.gain_gold(gold)
    fr.gold_after = player.gold

    # 카드 보상
    _add_reward_card(player, room_type, act, rng, fr, verbose)
    if verbose:
        print(f"       보상: 골드 +{gold}, 카드 '{fr.notes}'")


def _add_reward_card(player, room_type, act, rng, fr, verbose):
    from sts2_sim.cards.ironclad.basic import Strike, Defend, Bash
    from sts2_sim.cards.ironclad.uncommon import Inflame, Uppercut, Disarm, Whirlwind
    from sts2_sim.cards.ironclad.rare import Reaper, DemonFormCard, Bludgeon, FiendFire
    from sts2_sim.cards.silent.basic import (
        DeadlyPoison, PoisonedStab, Catalyst, Adrenaline,
        Acrobatics, QuickSlash, CloakAndDagger
    )
    is_silent = player.name == "Silent"

    if room_type == RoomType.BOSS:
        if is_silent:
            pool = [Adrenaline, Catalyst, CorpseExplosionWrapper]
        else:
            pool = [DemonFormCard, Reaper, Bludgeon, FiendFire]
    elif room_type == RoomType.ELITE:
        if is_silent:
            pool = [Catalyst, CloakAndDagger, PoisonedStab]
        else:
            pool = [Inflame, Uppercut, Whirlwind]
    else:
        if is_silent:
            pool = [DeadlyPoison, PoisonedStab, Acrobatics, QuickSlash]
        else:
            pool = [Inflame, Disarm, Bash, Uppercut]

    chosen_cls = rng.choice(pool)
    card = chosen_cls()
    player.add_card_to_deck(card)
    fr.notes = card.name


def CorpseExplosionWrapper():
    from sts2_sim.cards.silent.basic import CorpseExplosion
    return CorpseExplosion()


# ─────────────────────────────────────────
# 메인 런 루프
# ─────────────────────────────────────────

def run_full_playthrough(
    player: Player,
    config: RunConfig,
    policy: Callable = None,
) -> RunResult:
    if policy is None:
        policy = greedy_policy

    rng = SeededRng(config.seed)
    map_rng = rng.fork(0)
    encounter_rng = rng.fork(1)
    reward_rng = rng.fork(2)
    event_rng = rng.fork(3)
    shop_rng = rng.fork(4)

    act_map = ActMap(map_rng, num_acts=config.num_acts)
    path = act_map.get_path()

    if config.verbose:
        print(f"=== {player.name} 런 (시드 {config.seed}) ===")
        for act in range(1, config.num_acts + 1):
            print(f"Act {act}: {act_map.summary(act)}")
        print()

    floor_log: list[FloorResult] = []
    manager = CombatManager()

    for node in path:
        floor, room_type, act = node.floor, node.room_type, node.act
        fr = FloorResult(floor=floor, act=act, room_type=room_type, hp_after=player.current_hp)

        if config.verbose:
            print(f"[Act{act} 층{floor:2d}] {room_type.name:10s} HP {player.current_hp}/{player.max_hp} | 골드 {player.gold}")

        # ── 전투 룸 ──
        if room_type in (RoomType.MONSTER, RoomType.ELITE, RoomType.BOSS):
            enemies = make_encounter(room_type, act, encounter_rng.fork(floor * 100))
            if not enemies:
                floor_log.append(fr)
                continue

            bus = HookBus()
            state = CombatState(player=player, enemies=enemies,
                                combat_rng=encounter_rng.fork(floor * 100 + 1))
            player.creature.combat_state = state
            for e in enemies: e.combat_state = state

            gen = manager.run_combat(state)
            try:
                while True:
                    cs = next(gen)
                    policy(cs)
            except StopIteration as ex:
                combat_result = ex.value

            fr.combat_won = combat_result.won
            fr.hp_after = player.current_hp

            if config.verbose:
                status = "승리" if combat_result.won else "패배"
                print(f"         → {status} ({combat_result.turns}턴, HP {player.current_hp}/{player.max_hp})")

            if not combat_result.won:
                fr.notes = "패배"
                floor_log.append(fr)
                return RunResult(
                    character=player.name,
                    seed=config.seed,
                    won=False,
                    floors_cleared=floor - 1,
                    final_hp=0,
                    final_gold=player.gold,
                    floor_log=floor_log,
                    cause_of_death=f"Act{act} {floor}층 {room_type.name} 패배",
                )

            _combat_reward(player, room_type, act, reward_rng.fork(floor), fr, config.verbose)

            if room_type == RoomType.BOSS:
                floor_log.append(fr)
                if act == config.num_acts:
                    if config.verbose:
                        print(f"\n=== 최종 보스 처치! 런 승리 ===")
                        print(f"최종 HP: {player.current_hp}/{player.max_hp} | 골드: {player.gold}")
                    return RunResult(
                        character=player.name,
                        seed=config.seed,
                        won=True,
                        floors_cleared=floor,
                        final_hp=player.current_hp,
                        final_gold=player.gold,
                        floor_log=floor_log,
                    )
                else:
                    # Act 전환: 최대 HP +15, 완전 회복
                    player.creature._max_hp += 15
                    player.creature._current_hp = player.creature._max_hp
                    if config.verbose:
                        print(f"  Act {act} 보스 처치 → Act {act+1}로 진행 (최대HP +15, 완전 회복)")

        # ── 휴식 ──
        elif room_type == RoomType.REST:
            heal = max(1, int(player.creature.max_hp * 0.30))
            player.creature.heal(heal)
            fr.notes = f"HP +{heal} 회복"
            fr.hp_after = player.current_hp
            if config.verbose:
                print(f"         → 휴식: HP +{heal} → {player.current_hp}/{player.max_hp}")

        # ── 보물 ──
        elif room_type == RoomType.TREASURE:
            gold = reward_rng.fork(floor).next_int(20) + 20
            player.gain_gold(gold)
            fr.notes = f"골드 +{gold}"
            fr.gold_after = player.gold
            fr.hp_after = player.current_hp
            if config.verbose:
                print(f"         → 보물: 골드 +{gold}")

        # ── 이벤트 ──
        elif room_type == RoomType.EVENT:
            ev_pool = EVENT_POOL_BY_ACT.get(act, list(EVENT_POOL_BY_ACT[1]))
            ev_id = event_rng.fork(floor).choice(ev_pool)
            ev_result = resolve_event(ev_id, player, event_rng.fork(floor * 10))
            fr.notes = ev_result.description
            fr.hp_after = player.current_hp
            fr.gold_after = player.gold
            if config.verbose:
                print(f"         → 이벤트: {ev_result.description}")

        # ── 상점 ──
        elif room_type == RoomType.SHOP:
            shop_result = run_shop(player, shop_rng.fork(floor), verbose=config.verbose)
            fr.notes = f"구매: {shop_result['bought']}"
            fr.hp_after = player.current_hp
            fr.gold_after = player.gold

        floor_log.append(fr)

    # 모든 층 클리어 (보스 미포함)
    return RunResult(
        character=player.name,
        seed=config.seed,
        won=False,
        floors_cleared=len(path),
        final_hp=player.current_hp,
        final_gold=player.gold,
        floor_log=floor_log,
        cause_of_death="맵 종료",
    )
