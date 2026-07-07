"""
ActMap - 3-Act 맵 구조.
Act 1: 17층 (층 1~16 + 보스)
Act 2: 17층 (층 18~33 + 보스)
Act 3: 17층 (층 35~50 + 보스)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List
from sts2_sim.rng.seeded_rng import SeededRng


class RoomType(Enum):
    MONSTER = auto()
    ELITE = auto()
    REST = auto()
    SHOP = auto()
    TREASURE = auto()
    EVENT = auto()
    BOSS = auto()


@dataclass
class MapNode:
    floor: int
    col: int
    room_type: RoomType
    act: int
    edges: List["MapNode"] = field(default_factory=list)

    def __repr__(self):
        return f"Node({self.floor},{self.room_type.name[:3]})"


# 각 Act의 층별 룸 타입 분포 (단순화: 선형)
ACT_FLOOR_PLANS = {
    1: [  # 17 floors
        RoomType.MONSTER, RoomType.MONSTER, RoomType.MONSTER, RoomType.MONSTER,
        RoomType.TREASURE,
        RoomType.EVENT, RoomType.MONSTER, RoomType.MONSTER,
        RoomType.REST,
        RoomType.ELITE, RoomType.EVENT, RoomType.MONSTER,
        RoomType.ELITE,
        RoomType.REST,
        RoomType.SHOP, RoomType.MONSTER,
        RoomType.BOSS,
    ],
    2: [  # 17 floors
        RoomType.MONSTER, RoomType.MONSTER, RoomType.MONSTER,
        RoomType.TREASURE,
        RoomType.EVENT, RoomType.ELITE, RoomType.MONSTER,
        RoomType.REST,
        RoomType.MONSTER, RoomType.ELITE, RoomType.EVENT,
        RoomType.SHOP,
        RoomType.MONSTER, RoomType.ELITE,
        RoomType.REST,
        RoomType.MONSTER,
        RoomType.BOSS,
    ],
    3: [  # 17 floors
        RoomType.MONSTER, RoomType.MONSTER, RoomType.ELITE,
        RoomType.TREASURE,
        RoomType.EVENT, RoomType.MONSTER, RoomType.ELITE,
        RoomType.REST,
        RoomType.MONSTER, RoomType.ELITE, RoomType.MONSTER,
        RoomType.SHOP,
        RoomType.ELITE, RoomType.MONSTER,
        RoomType.REST,
        RoomType.MONSTER,
        RoomType.BOSS,
    ],
}


class ActMap:
    def __init__(self, rng: SeededRng, num_acts: int = 3):
        self.rng = rng
        self.num_acts = num_acts
        self.nodes: list[MapNode] = []
        self._generate()

    def _generate(self):
        floor = 1
        for act in range(1, self.num_acts + 1):
            plan = ACT_FLOOR_PLANS[act]
            for room_type in plan:
                node = MapNode(floor=floor, col=0, room_type=room_type, act=act)
                self.nodes.append(node)
                floor += 1

    def get_path(self) -> list[MapNode]:
        return self.nodes

    def summary(self, act: int = None) -> str:
        nodes = [n for n in self.nodes if act is None or n.act == act]
        return " → ".join(n.room_type.name[:3] for n in nodes)
