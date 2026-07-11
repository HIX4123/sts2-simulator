"""
STS2 카드 플레이 정책.

GreedyPolicy: 인텐트 인지 그리디 —
  1) 막타 가능한 공격 우선 (데미지 소스 제거)
  2) 예상 피해 > 현재 블록이면 방어 스킬
  3) 효율 최고 공격
  4) 남는 에너지로 유틸 스킬 (Zap/Venerate 등)
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Tuple

from sts2_sim.models.sts2_card import CardType
from sts2_sim.entities.sts2_monster import IntentType

if TYPE_CHECKING:
    from sts2_sim.core.combat import CombatState
    from sts2_sim.entities.sts2_monster import MonsterModel
    from sts2_sim.models.sts2_card import STS2Card


# 카드별 (기본값, 업그레이드값) 추정 테이블
_ATTACK_DAMAGE = {
    "strike": (6, 9), "bash": (8, 10), "neutralize": (3, 4),
    "shiv": (4, 6), "unleash": (6, 9), "falling_star": (8, 12),
}
_BLOCK_VALUE = {
    "defend": (5, 8), "deflect": (4, 7), "survivor": (8, 11),
}
# 취약 미적용 대상에 취약을 거는 카드의 셋업 가치 (이후 턴 1.5× 데미지 반영)
_VULN_SETUP_BONUS = {
    "bash": 6, "falling_star": 4,
}

_ATTACK_INTENTS = {
    IntentType.ATTACK, IntentType.ATTACK_BUFF,
    IntentType.ATTACK_DEBUFF, IntentType.ATTACK_DEFEND,
}


def _card_value(table: dict, card: "STS2Card") -> int:
    base, upgraded = table.get(card.card_id, (0, 0))
    return upgraded if card.upgraded else base


def estimate_attack_damage(card: "STS2Card", player, target: "MonsterModel",
                           combat: "CombatState" = None) -> int:
    """카드의 예상 공격 데미지 (힘/약화/취약 반영)."""
    base = _card_value(_ATTACK_DAMAGE, card)
    if base == 0:
        base = card.damage_estimate(player, combat, target)  # Phase 6b 카드 프로토콜
    if card.card_id == "unleash":
        osty = getattr(player, "osty", None)
        base += osty.current_hp if (osty and osty.is_alive) else 0
    dmg = player.compute_attack_damage(base)
    if target.get_power_amount("vulnerable") > 0:
        dmg = int(dmg * 1.5)
    return dmg


def estimate_block(card: "STS2Card", player, combat: "CombatState" = None) -> int:
    """카드의 예상 블록량."""
    value = _card_value(_BLOCK_VALUE, card)
    if value == 0:
        value = card.block_estimate(player, combat)
    return value


def estimate_incoming_damage(combat: "CombatState") -> int:
    """이번 몬스터 턴의 예상 총 피해."""
    total = 0
    for monster in combat.alive_enemies:
        intent = monster.get_current_intent()
        if intent.intent_type in _ATTACK_INTENTS:
            per_hit = intent.damage + monster.get_power_amount("strength")
            if monster.get_power_amount("weak") > 0:
                per_hit = int(per_hit * 0.75)
            total += max(0, per_hit) * intent.times
    if combat.player.get_power_amount("vulnerable") > 0:
        total = int(total * 1.5)
    return total


class GreedyPolicy:
    """인텐트 인지 그리디 정책."""

    def choose(self, combat: "CombatState") -> Optional[Tuple["STS2Card", Optional["MonsterModel"]]]:
        player = combat.player
        enemies = combat.alive_enemies
        if not enemies:
            return None

        playable = [c for c in combat.hand if combat.is_card_playable(c)]
        if not playable:
            return None

        attacks = [c for c in playable if c.card_type == CardType.ATTACK]
        skills = [c for c in playable if c.card_type == CardType.SKILL]
        powers = [c for c in playable if c.card_type == CardType.POWER]

        def cost_of(c) -> int:
            return player.energy if c.x_cost else combat.get_card_cost(c)

        # 1) 막타: 적 하나를 지금 제거할 수 있으면 최우선
        for target in sorted(enemies, key=lambda m: m.current_hp):
            effective_hp = target.current_hp + target.block
            killers = [c for c in attacks
                       if estimate_attack_damage(c, player, target, combat) >= effective_hp]
            if killers:
                # 최소 비용으로 처치
                best = min(killers, key=lambda c: (cost_of(c),
                                                   estimate_attack_damage(c, player, target, combat)))
                return (best, target)

        # 2) 파워 카드: 셋업은 이를수록 이득 — 남는 에너지가 충분하면 우선 설치
        if powers:
            cheapest = min(powers, key=cost_of)
            if cost_of(cheapest) <= player.energy:
                return (cheapest, None)

        # 3) 공격 vs 방어: 에너지당 가치 비교
        #    공격 가치 = 예상 데미지 / 비용, 방어 가치 = 실제로 막는 HP / 비용
        incoming = estimate_incoming_damage(combat)
        target = min(enemies, key=lambda m: m.current_hp + m.block)

        def attack_score(c) -> float:
            score = estimate_attack_damage(c, player, target, combat)
            if target.get_power_amount("vulnerable") == 0:
                score += _VULN_SETUP_BONUS.get(c.card_id, 0)
                score += getattr(c, "vuln_setup", 0)
            return score / max(1, cost_of(c))

        best_attack = None
        attack_value = -1.0
        if attacks:
            best_attack = max(attacks, key=attack_score)
            attack_value = attack_score(best_attack)

        best_blocker = None
        block_value = -1.0
        blockers = [c for c in skills if estimate_block(c, player, combat) > 0]
        if blockers:
            def hp_saved(c):
                return min(estimate_block(c, player, combat),
                           max(0, incoming - player.block))
            best_blocker = max(blockers, key=lambda c: hp_saved(c) / max(1, cost_of(c)))
            block_value = hp_saved(best_blocker) / max(1, cost_of(best_blocker))

        if best_blocker is not None and block_value > attack_value:
            return (best_blocker, None)
        if best_attack is not None and attack_value > 0:
            return (best_attack, target)
        if best_blocker is not None and block_value > 0:
            return (best_blocker, None)

        # 4) 유틸 스킬 (오브/스타/드로우 등)
        utility = [c for c in skills if estimate_block(c, player, combat) == 0]
        if utility:
            return (utility[0], None)
        if best_attack is not None:
            return (best_attack, target)
        # 남는 에너지에 블록 가치가 없으면 종료
        return None
