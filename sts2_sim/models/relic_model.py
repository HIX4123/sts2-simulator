"""
RelicModel — 렐릭 기반 클래스.
sts2.dll MegaCrit.Sts2.Core.Models.RelicModel 대응.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from sts2_sim.models.abstract_model import AbstractModel

if TYPE_CHECKING:
    from sts2_sim.entities.player import Player
    from sts2_sim.core.combat_state import CombatState


class RelicModel(AbstractModel):
    relic_id: str = "unknown_relic"
    name: str = "Unknown Relic"

    def __init__(self):
        super().__init__()
        self.owner: Optional["Player"] = None
        self._stack_count: int = 0

    def subscribed_hooks(self) -> list[str]:
        from sts2_sim.hooks.hook_bus import ALL_HOOKS
        hooks = []
        for hook in ALL_HOOKS:
            for cls in type(self).__mro__[:-1]:
                if cls is RelicModel or cls is AbstractModel:
                    break
                if hook in cls.__dict__:
                    hooks.append(hook)
                    break
        return hooks

    def __repr__(self):
        return f"{self.name}"
