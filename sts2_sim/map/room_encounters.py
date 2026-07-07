"""
룸 인카운터 팩토리 (3-Act 풀).
"""
from __future__ import annotations
from sts2_sim.map.act_map import RoomType
from sts2_sim.rng.seeded_rng import SeededRng


def make_encounter(room_type: RoomType, act: int, rng: SeededRng):
    from sts2_sim.entities.monster import (
        Jawworm, RedLouse, GreenLouse, AcidSlimeSmall, AcidSlimeMedium,
        SpikeSlimeSmall, SpikeSlimeMedium, Cultist, FungiBeast,
        SlimeBoss, GremlinNob, Centurion, Chosen, BookOfStabbing,
        TheChamp, Nemesis, GiantHead, DonuDeca,
    )

    # ── ACT 1 ──
    if act == 1:
        if room_type == RoomType.MONSTER:
            pool = [
                lambda: [Jawworm()],
                lambda: [RedLouse(), RedLouse()],
                lambda: [GreenLouse(), GreenLouse()],
                lambda: [AcidSlimeSmall(), SpikeSlimeSmall()],
                lambda: [Cultist()],
                lambda: [FungiBeast(), FungiBeast()],
                lambda: [AcidSlimeMedium()],
                lambda: [SpikeSlimeMedium()],
            ]
        elif room_type == RoomType.ELITE:
            pool = [
                lambda: [make_elite_jawworm()],
                lambda: [GremlinNob()],
            ]
        elif room_type == RoomType.BOSS:
            return [SlimeBoss()]
        else:
            return []

    # ── ACT 2 ──
    elif act == 2:
        if room_type == RoomType.MONSTER:
            pool = [
                lambda: [Centurion()],
                lambda: [Chosen()],
                lambda: [BookOfStabbing()],
                lambda: [Centurion(), GreenLouse()],
                lambda: [Chosen(), Chosen()],
            ]
        elif room_type == RoomType.ELITE:
            pool = [
                lambda: [GremlinNob()],
                lambda: [BookOfStabbing()],
            ]
        elif room_type == RoomType.BOSS:
            return [TheChamp()]
        else:
            return []

    # ── ACT 3 ──
    else:
        if room_type == RoomType.MONSTER:
            pool = [
                lambda: [Nemesis()],
                lambda: [GiantHead()],
                lambda: [Chosen(), Chosen()],
                lambda: [Centurion(), Centurion()],
            ]
        elif room_type == RoomType.ELITE:
            pool = [
                lambda: [Nemesis()],
                lambda: [GiantHead()],
            ]
        elif room_type == RoomType.BOSS:
            return [DonuDeca()]
        else:
            return []

    chosen = rng.choice(pool)
    return chosen()


def make_elite_jawworm():
    from sts2_sim.entities.monster import Jawworm
    e = Jawworm(hp=50)
    e.name = "Elite Jaw Worm"
    return e
