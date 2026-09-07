"""몬스터 배치 모듈 일괄 임포트 — MONSTER_REGISTRY 등록 지점.

`sts2_sim.cards`가 카드 풀을 CARD_REGISTRY에 등록하는 것과 같은 역할.
이 모듈을 거치지 않으면 배치 모듈이 로드되지 않아 `create_monster("exoskeleton")`
같은 조회가 조용히 None을 반환한다 (기본 몬스터 17종만 등록된 상태).
"""
from sts2_sim.entities import (  # noqa: F401
    monsters_batch7a,
    monsters_batch7b,
    monsters_batch7c,
    monsters_batch8,
    monsters_batch9,
    monsters_batch10,
    monsters_batch11,
    monsters_batch12,
    monsters_batch13,
    monsters_batch14,
    monsters_batch15,
    monsters_batch16,
    monsters_batch17,
    monsters_batch18,
    monsters_batch19,
    monsters_batch20,
    monsters_batch21,
    monsters_batch22,
    monsters_extra,
    sts2_monster,
)
