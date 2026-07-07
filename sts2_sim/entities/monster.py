"""
Monster 엔티티 + 전체 Act 1~3 구체 몬스터.
sts2.dll MegaCrit.Sts2.Core.Entities.Monsters 대응.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from sts2_sim.core.combat_state import CombatState


class IntentType(Enum):
    ATTACK = auto()
    ATTACK_BUFF = auto()
    ATTACK_DEBUFF = auto()
    BUFF = auto()
    DEBUFF = auto()
    DEFEND = auto()
    DEFEND_BUFF = auto()
    DEFEND_DEBUFF = auto()
    SLEEP = auto()
    STUN = auto()
    UNKNOWN = auto()


@dataclass
class Intent:
    intent_type: IntentType
    damage: int = 0
    times: int = 1


@dataclass
class Move:
    move_id: str
    weight: int = 1
    max_consecutive: int = 999


class Monster:
    def __init__(self, name: str, max_hp: int):
        self.name = name
        self._max_hp = max_hp
        self._current_hp = max_hp
        self._block = 0
        self._powers: dict = {}
        self._move_history: list[str] = []
        self._current_move: Optional[str] = None
        self.combat_state: Optional["CombatState"] = None
        self.monster_id: str = "unknown"

    @property
    def current_hp(self) -> int: return self._current_hp
    @property
    def max_hp(self) -> int: return self._max_hp
    @property
    def block(self) -> int: return self._block
    @property
    def is_dead(self) -> bool: return self._current_hp <= 0
    @property
    def hp_percent(self) -> float:
        return self._current_hp / self._max_hp if self._max_hp > 0 else 0.0

    def get_moves(self) -> list[Move]: return []

    def _get_intent_for_move(self, move_id: str) -> Intent:
        return Intent(IntentType.UNKNOWN)

    def roll_move(self, rng) -> str:
        moves = self.get_moves()
        if not moves:
            return "idle"
        weights = []
        for m in moves:
            consecutive = sum(1 for h in reversed(self._move_history)
                              if h == m.move_id)
            if consecutive >= m.max_consecutive:
                weights.append(0)
            else:
                weights.append(m.weight)
        total = sum(weights)
        if total == 0:
            weights = [m.weight for m in moves]
            total = sum(weights)
        r = rng.next_int(total)
        acc = 0
        for i, w in enumerate(weights):
            acc += w
            if r < acc:
                return moves[i].move_id
        return moves[-1].move_id

    def get_intent(self) -> Intent:
        if self._current_move:
            return self._get_intent_for_move(self._current_move)
        return Intent(IntentType.UNKNOWN)

    def setup_for_combat(self, state: "CombatState"):
        if state.combat_rng:
            self._current_move = self.roll_move(state.combat_rng)

    def take_turn(self, state: "CombatState"):
        if self._current_move:
            self.perform_move(state, self._current_move)
        self._move_history.append(self._current_move or "idle")
        if len(self._move_history) > 5:
            self._move_history.pop(0)

    def perform_move(self, state: "CombatState", move_id: str):
        pass

    def prepare_for_next_turn(self):
        self._block = 0
        if self.combat_state:
            self._current_move = self.roll_move(self.combat_state.combat_rng)
        # tick powers
        for p in list(self._powers.values()):
            if hasattr(p, 'tick_duration'):
                p.tick_duration()

    def gain_block(self, amount: int):
        self._block += max(0, amount)

    def apply_power(self, power, amount: int, applier=None):
        pid = power.power_id
        if pid in self._powers:
            self._powers[pid].apply(self, applier, amount)
        else:
            power.owner = self
            power.applier = applier
            power._amount = 0
            power.apply(self, applier, amount)
            self._powers[pid] = power
            if self.combat_state:
                self.combat_state.bus.register(power, priority=1)

    def has_power(self, power_id: str) -> bool:
        return power_id in self._powers and self._powers[power_id].amount > 0

    def get_power_amount(self, power_id: str) -> int:
        p = self._powers.get(power_id)
        return p.amount if p else 0

    def remove_power(self, power_id: str):
        p = self._powers.pop(power_id, None)
        if p and self.combat_state:
            self.combat_state.bus.unregister(p)

    def lose_hp(self, amount: int) -> int:
        actual = min(amount, self._current_hp)
        self._current_hp -= actual
        return actual

    def take_damage(self, amount: int, source=None):
        @dataclass
        class DmgResult:
            hp_lost: int = 0
            killed: bool = False
        if amount <= 0:
            return DmgResult()
        # block
        block_absorbed = min(self._block, amount)
        self._block -= block_absorbed
        hp_dmg = amount - block_absorbed
        hp_lost = self.lose_hp(hp_dmg)
        return DmgResult(hp_lost=hp_lost, killed=self.is_dead)

    def deal_damage(self, state: "CombatState", base_damage: int, times: int = 1):
        str_amt = self.get_power_amount("strength")
        for _ in range(times):
            dmg = max(0, base_damage + str_amt)
            if state.bus:
                ctx = {"amount": dmg, "source": self,
                       "target": state.player.creature}
                ctx = state.bus.fire("AfterModifyingDamageAmount", **ctx)
                dmg = max(0, int(ctx["amount"]))
            # Vulnerable on player
            if state.player.creature.has_power("vulnerable"):
                dmg = int(dmg * 1.5)
            state.player.creature.take_damage(dmg, source=self)

    def heal(self, amount: int):
        self._current_hp = min(self._current_hp + amount, self._max_hp)

    def __repr__(self):
        return f"{self.name}({self._current_hp}/{self._max_hp})"


# ══════════════════════════════════════════
# ACT 1 몬스터
# ══════════════════════════════════════════

class Jawworm(Monster):
    monster_id = "jawworm"
    def __init__(self, hp=None):
        super().__init__("Jaw Worm", hp or 32)
    def get_moves(self):
        return [Move("chomp",3,1), Move("thrash",5), Move("bellow",2,1)]
    def _get_intent_for_move(self, mid):
        if mid=="chomp": return Intent(IntentType.ATTACK, 11)
        if mid=="thrash": return Intent(IntentType.ATTACK_BUFF, 7)
        return Intent(IntentType.BUFF)
    def perform_move(self, state, mid):
        from sts2_sim.models.power_model import Strength
        if mid=="chomp": self.deal_damage(state, 11)
        elif mid=="thrash": self.deal_damage(state, 7); self.gain_block(5)
        elif mid=="bellow": self.apply_power(Strength(), 3, self); self.gain_block(6)


class RedLouse(Monster):
    monster_id = "red_louse"
    def __init__(self, hp=None):
        super().__init__("Red Louse", hp or 11)
        self._bite_dmg = 6
    def get_moves(self):
        return [Move("bite",2), Move("grow",1,1)]
    def _get_intent_for_move(self, mid):
        if mid=="bite": return Intent(IntentType.ATTACK, self._bite_dmg)
        return Intent(IntentType.BUFF)
    def perform_move(self, state, mid):
        from sts2_sim.models.power_model import Strength
        if mid=="bite": self.deal_damage(state, self._bite_dmg)
        elif mid=="grow": self.apply_power(Strength(), 3, self)


class GreenLouse(Monster):
    monster_id = "green_louse"
    def __init__(self, hp=None):
        super().__init__("Green Louse", hp or 11)
    def get_moves(self):
        return [Move("bite",2), Move("spit_web",1,1)]
    def _get_intent_for_move(self, mid):
        if mid=="bite": return Intent(IntentType.ATTACK, 6)
        return Intent(IntentType.DEBUFF)
    def perform_move(self, state, mid):
        from sts2_sim.models.power_model import Weak
        if mid=="bite": self.deal_damage(state, 6)
        elif mid=="spit_web":
            state.player.creature.apply_power(Weak(), 2, self)


class AcidSlimeSmall(Monster):
    monster_id = "acid_slime_s"
    def __init__(self, hp=None):
        super().__init__("Acid Slime (S)", hp or 8)
    def get_moves(self):
        return [Move("tackle",6), Move("lick",4)]
    def _get_intent_for_move(self, mid):
        if mid=="tackle": return Intent(IntentType.ATTACK, 3)
        return Intent(IntentType.DEBUFF)
    def perform_move(self, state, mid):
        from sts2_sim.models.power_model import Weak
        if mid=="tackle": self.deal_damage(state, 3)
        elif mid=="lick":
            state.player.creature.apply_power(Weak(), 1, self)


class AcidSlimeMedium(Monster):
    monster_id = "acid_slime_m"
    def __init__(self, hp=None):
        super().__init__("Acid Slime (M)", hp or 28)
    def get_moves(self):
        return [Move("corrosive_spit",2), Move("tackle",3), Move("lick",2)]
    def _get_intent_for_move(self, mid):
        if mid=="corrosive_spit": return Intent(IntentType.ATTACK_DEBUFF, 7)
        if mid=="tackle": return Intent(IntentType.ATTACK, 10)
        return Intent(IntentType.DEBUFF)
    def perform_move(self, state, mid):
        from sts2_sim.models.power_model import Weak
        from sts2_sim.cards.ironclad.common import Slimed
        if mid=="corrosive_spit":
            self.deal_damage(state, 7)
            state.discard_pile.append(Slimed())
        elif mid=="tackle": self.deal_damage(state, 10)
        elif mid=="lick":
            state.player.creature.apply_power(Weak(), 1, self)


class SpikeSlimeSmall(Monster):
    monster_id = "spike_slime_s"
    def __init__(self, hp=None):
        super().__init__("Spike Slime (S)", hp or 10)
    def get_moves(self):
        return [Move("flame_tackle",6), Move("lick",4)]
    def _get_intent_for_move(self, mid):
        if mid=="flame_tackle": return Intent(IntentType.ATTACK_DEBUFF, 5)
        return Intent(IntentType.DEBUFF)
    def perform_move(self, state, mid):
        from sts2_sim.models.power_model import Frail
        from sts2_sim.cards.ironclad.common import Slimed
        if mid=="flame_tackle":
            self.deal_damage(state, 5)
            state.discard_pile.append(Slimed())
        elif mid=="lick":
            state.player.creature.apply_power(Frail(), 1, self)


class SpikeSlimeMedium(Monster):
    monster_id = "spike_slime_m"
    def __init__(self, hp=None):
        super().__init__("Spike Slime (M)", hp or 28)
    def get_moves(self):
        return [Move("flame_tackle",3), Move("lick",2)]
    def _get_intent_for_move(self, mid):
        if mid=="flame_tackle": return Intent(IntentType.ATTACK_DEBUFF, 8)
        return Intent(IntentType.DEBUFF)
    def perform_move(self, state, mid):
        from sts2_sim.models.power_model import Frail
        from sts2_sim.cards.ironclad.common import Slimed
        if mid=="flame_tackle":
            self.deal_damage(state, 8)
            state.discard_pile.append(Slimed())
        elif mid=="lick":
            state.player.creature.apply_power(Frail(), 1, self)


class Cultist(Monster):
    monster_id = "cultist"
    def __init__(self, hp=None):
        super().__init__("Cultist", hp or 48)
        self._first_turn = True
    def get_moves(self):
        return [Move("incantation",1,1), Move("dark_strike",1)]
    def setup_for_combat(self, state):
        self._current_move = "incantation"
        self._first_turn = True
    def _get_intent_for_move(self, mid):
        if mid=="incantation": return Intent(IntentType.BUFF)
        return Intent(IntentType.ATTACK, 6)
    def perform_move(self, state, mid):
        from sts2_sim.models.power_model import Ritual
        if mid=="incantation":
            self.apply_power(Ritual(), 3, self)
            self._first_turn = False
        elif mid=="dark_strike": self.deal_damage(state, 6)
    def prepare_for_next_turn(self):
        self._block = 0
        if self._first_turn:
            self._current_move = "incantation"
        else:
            self._current_move = "dark_strike"
        for p in list(self._powers.values()):
            if hasattr(p, 'tick_duration'): p.tick_duration()


class FungiBeast(Monster):
    monster_id = "fungi_beast"
    def __init__(self, hp=None):
        super().__init__("Fungi Beast", hp or 22)
    def get_moves(self):
        return [Move("bite",3), Move("grow",1,1)]
    def _get_intent_for_move(self, mid):
        if mid=="bite": return Intent(IntentType.ATTACK, 6)
        return Intent(IntentType.BUFF)
    def perform_move(self, state, mid):
        from sts2_sim.models.power_model import Strength
        if mid=="bite": self.deal_damage(state, 6)
        elif mid=="grow": self.apply_power(Strength(), 5, self)


class SlimeBoss(Monster):
    """Act 1 보스."""
    monster_id = "slime_boss"
    def __init__(self):
        super().__init__("Slime Boss", 90)
        self._phase = 1
        self._split_done = False
    def get_moves(self):
        return [Move("goop_spray",1), Move("preparing",1,1), Move("slam",2)]
    def setup_for_combat(self, state):
        self._current_move = "goop_spray"
        self._phase = 1
        self._split_done = False
    def _get_intent_for_move(self, mid):
        if mid=="goop_spray": return Intent(IntentType.DEBUFF)
        if mid=="preparing": return Intent(IntentType.BUFF)
        return Intent(IntentType.ATTACK, 35)
    def perform_move(self, state, mid):
        from sts2_sim.models.power_model import Frail
        from sts2_sim.cards.ironclad.common import Slimed
        if mid=="goop_spray":
            for _ in range(3):
                state.discard_pile.append(Slimed())
        elif mid=="preparing":
            pass  # next turn slams
        elif mid=="slam":
            self.deal_damage(state, 22)
    def prepare_for_next_turn(self):
        self._block = 0
        # Phase 2: if HP < 50%
        if self.hp_percent < 0.5 and not self._split_done:
            self._split_done = True
            self._phase = 2
        # Rotate: goop → preparing → slam → goop ...
        cycle = ["goop_spray", "preparing", "slam"]
        cur_idx = cycle.index(self._current_move) if self._current_move in cycle else 0
        self._current_move = cycle[(cur_idx + 1) % len(cycle)]
        for p in list(self._powers.values()):
            if hasattr(p, 'tick_duration'): p.tick_duration()


# ══════════════════════════════════════════
# ACT 2 몬스터
# ══════════════════════════════════════════

class GremlinNob(Monster):
    """Act 2 엘리트 - 스킬 카드에 분노."""
    monster_id = "gremlin_nob"
    def __init__(self):
        super().__init__("Gremlin Nob", 42)
    def get_moves(self):
        return [Move("bellow",1,1), Move("skull_bash",2), Move("rush",3)]
    def setup_for_combat(self, state):
        self._current_move = "bellow"
    def _get_intent_for_move(self, mid):
        if mid=="bellow": return Intent(IntentType.BUFF)
        if mid=="skull_bash": return Intent(IntentType.ATTACK_DEBUFF, 6)
        return Intent(IntentType.ATTACK, 14)
    def perform_move(self, state, mid):
        from sts2_sim.models.power_model import Vulnerable
        if mid=="bellow":
            from sts2_sim.models.power_model import Strength
            self.apply_power(Strength(), 3, self)
        elif mid=="skull_bash":
            self.deal_damage(state, 6)
            state.player.creature.apply_power(Vulnerable(), 2, self)
        elif mid=="rush": self.deal_damage(state, 14)
    def prepare_for_next_turn(self):
        self._block = 0
        if self._current_move == "bellow":
            self._current_move = "skull_bash"
        elif self._current_move == "skull_bash":
            self._current_move = "rush"
        else:
            import random
            self._current_move = random.choice(["skull_bash", "rush"])
        for p in list(self._powers.values()):
            if hasattr(p, 'tick_duration'): p.tick_duration()


class Centurion(Monster):
    monster_id = "centurion"
    def __init__(self):
        super().__init__("Centurion", 30)
    def get_moves(self):
        return [Move("slash",3), Move("fury",2), Move("defend",2)]
    def _get_intent_for_move(self, mid):
        if mid=="slash": return Intent(IntentType.ATTACK, 12)
        if mid=="fury": return Intent(IntentType.ATTACK, 6, 3)
        return Intent(IntentType.DEFEND)
    def perform_move(self, state, mid):
        if mid=="slash": self.deal_damage(state, 12)
        elif mid=="fury":
            for _ in range(3): self.deal_damage(state, 6)
        elif mid=="defend": self.gain_block(15)


class Chosen(Monster):
    monster_id = "chosen"
    def __init__(self):
        super().__init__("Chosen", 28)
    def get_moves(self):
        return [Move("poke",3), Move("zap",2,1), Move("debilitate",2)]
    def _get_intent_for_move(self, mid):
        if mid=="poke": return Intent(IntentType.ATTACK, 5, 2)
        if mid=="zap": return Intent(IntentType.ATTACK_DEBUFF, 18)
        return Intent(IntentType.DEBUFF)
    def perform_move(self, state, mid):
        from sts2_sim.models.power_model import Vulnerable, Weak
        if mid=="poke":
            for _ in range(2): self.deal_damage(state, 5)
        elif mid=="zap":
            self.deal_damage(state, 18)
            state.player.creature.apply_power(Vulnerable(), 2, self)
        elif mid=="debilitate":
            state.player.creature.apply_power(Weak(), 2, self)
            state.player.creature.apply_power(Vulnerable(), 2, self)


class BookOfStabbing(Monster):
    monster_id = "book_of_stabbing"
    def __init__(self):
        super().__init__("Book of Stabbing", 35)
        self._stab_count = 1
    def get_moves(self):
        return [Move("multi_stab",3), Move("single_stab",2)]
    def _get_intent_for_move(self, mid):
        if mid=="multi_stab": return Intent(IntentType.ATTACK, 6, self._stab_count)
        return Intent(IntentType.ATTACK, 21)
    def perform_move(self, state, mid):
        if mid=="multi_stab":
            for _ in range(self._stab_count): self.deal_damage(state, 6)
            self._stab_count = min(self._stab_count + 1, 5)
        elif mid=="single_stab": self.deal_damage(state, 21)


# Act 2 보스
class TheChamp(Monster):
    monster_id = "the_champ"
    def __init__(self):
        super().__init__("The Champ", 70)
        self._phase = 1
    def get_moves(self):
        return [Move("face_slap",2), Move("taunt",1,1), Move("heavy_slash",2), Move("execute",1)]
    def setup_for_combat(self, state):
        self._current_move = "taunt"
    def _get_intent_for_move(self, mid):
        if mid=="face_slap": return Intent(IntentType.ATTACK_DEBUFF, 12)
        if mid=="taunt": return Intent(IntentType.DEBUFF)
        if mid=="heavy_slash": return Intent(IntentType.ATTACK, 16)
        return Intent(IntentType.ATTACK, 28)
    def perform_move(self, state, mid):
        from sts2_sim.models.power_model import Weak, Vulnerable, Frail
        if mid=="face_slap":
            self.deal_damage(state, 12)
            state.player.creature.apply_power(Weak(), 2, self)
            state.player.creature.apply_power(Frail(), 2, self)
        elif mid=="taunt":
            state.player.creature.apply_power(Vulnerable(), 2, self)
        elif mid=="heavy_slash": self.deal_damage(state, 16)
        elif mid=="execute": self.deal_damage(state, 28)
    def prepare_for_next_turn(self):
        self._block = 0
        if self.combat_state:
            self._current_move = self.roll_move(self.combat_state.combat_rng)
        for p in list(self._powers.values()):
            if hasattr(p, 'tick_duration'): p.tick_duration()


# ══════════════════════════════════════════
# ACT 3 몬스터
# ══════════════════════════════════════════

class Nemesis(Monster):
    monster_id = "nemesis"
    def __init__(self):
        super().__init__("Nemesis", 55)
    def get_moves(self):
        return [Move("scythe",2), Move("debuff",2,1), Move("intangible",1,1)]
    def _get_intent_for_move(self, mid):
        if mid=="scythe": return Intent(IntentType.ATTACK, 13, 3)
        if mid=="debuff": return Intent(IntentType.DEBUFF)
        return Intent(IntentType.BUFF)
    def perform_move(self, state, mid):
        from sts2_sim.models.power_model import Burning
        if mid=="scythe":
            for _ in range(3): self.deal_damage(state, 13)
        elif mid=="debuff":
            state.player.creature.apply_power(Burning(), 3, self)
        elif mid=="intangible":
            self.gain_block(20)


class GiantHead(Monster):
    monster_id = "giant_head"
    def __init__(self):
        super().__init__("Giant Head", 70)
        self._count = 0
    def get_moves(self):
        return [Move("count",3), Move("glare",1,1), Move("it_is_time",1)]
    def setup_for_combat(self, state):
        self._current_move = "count"
        self._count = 0
    def _get_intent_for_move(self, mid):
        if mid=="count": return Intent(IntentType.BUFF)
        if mid=="glare": return Intent(IntentType.DEBUFF)
        return Intent(IntentType.ATTACK, 35 + self._count * 10)
    def perform_move(self, state, mid):
        from sts2_sim.models.power_model import Weak
        if mid=="count":
            self._count += 1
        elif mid=="glare":
            state.player.creature.apply_power(Weak(), 1, self)
        elif mid=="it_is_time":
            dmg = 35 + self._count * 10
            self.deal_damage(state, dmg)


# Act 3 보스
class DonuDeca(Monster):
    """Act 3 보스: 듀얼 오브."""
    monster_id = "donu_deca"
    def __init__(self):
        super().__init__("Donu & Deca", 80)
    def get_moves(self):
        return [Move("circle_of_power",1,1), Move("beam",2), Move("giant_laser",1)]
    def setup_for_combat(self, state):
        self._current_move = "circle_of_power"
    def _get_intent_for_move(self, mid):
        if mid=="circle_of_power": return Intent(IntentType.BUFF)
        if mid=="beam": return Intent(IntentType.ATTACK, 10, 2)
        return Intent(IntentType.ATTACK, 50)
    def perform_move(self, state, mid):
        from sts2_sim.models.power_model import Strength
        if mid=="circle_of_power":
            self.apply_power(Strength(), 3, self)
            self.gain_block(25)
        elif mid=="beam":
            for _ in range(2): self.deal_damage(state, 10)
        elif mid=="giant_laser":
            self.deal_damage(state, 50)
    def prepare_for_next_turn(self):
        self._block = 0
        cycle = ["circle_of_power", "beam", "beam", "giant_laser"]
        cur = self._current_move
        try:
            idx = cycle.index(cur)
            self._current_move = cycle[(idx + 1) % len(cycle)]
        except ValueError:
            self._current_move = "beam"
        for p in list(self._powers.values()):
            if hasattr(p, 'tick_duration'): p.tick_duration()
