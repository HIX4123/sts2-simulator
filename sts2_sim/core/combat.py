"""
STS2 CombatState — 헤드리스 전투 턴 루프.

턴 구조 (STS2 대응 단순화):
  플레이어 턴: 블록 초기화 → 에너지 리셋 → 렐릭/오브 턴 시작 훅
             → 드로우(기본 5, 렐릭 수정) → 정책이 카드 플레이 → 턴 종료
             (오브 턴 종료 패시브 → 파워 틱 → 핸드 버리기, 에테리얼은 소모)
  몬스터 턴: 블록 초기화 → 파워 턴 시작 훅(Ritual 등) → 행동 실행 → 파워 틱
"""
from __future__ import annotations
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Tuple

from sts2_sim.models.sts2_card import CardType, create_card

if TYPE_CHECKING:
    from sts2_sim.entities.player import Player
    from sts2_sim.entities.sts2_monster import MonsterModel
    from sts2_sim.models.sts2_card import STS2Card


@dataclass
class CombatResult:
    victory: bool
    turns: int
    player_hp: int


class CombatState:
    """단일 전투 상태 및 턴 루프."""

    BASE_DRAW = 5

    def __init__(self, player: "Player", monsters: List["MonsterModel"], seed: int = 0):
        self.player = player
        self.monsters = monsters
        self.rng = random.Random(seed)
        self.turn = 0
        # 파워(Juggernaut 등)가 전투 컨텍스트에 접근할 수 있도록 역참조
        self.player.combat = self

        self.draw_pile: List["STS2Card"] = list(player.master_deck)
        self.rng.shuffle(self.draw_pile)
        self.hand: List["STS2Card"] = []
        self.discard_pile: List["STS2Card"] = []
        self.exhaust_pile: List["STS2Card"] = []
        self.cards_exhausted_this_turn = 0  # EvilEye/ForgottenRitual 조건
        self.attacks_played_this_turn = 0   # Stomp 동적 비용
        self.skills_played_this_turn = 0    # Pinpoint 동적 비용
        self.cards_discarded_this_turn = 0  # MementoMori
        self.shivs_played_this_turn = 0     # PhantomBlades 첫 Shiv 보너스
        self.cards_drawn_this_combat = 0    # Murder
        self.extra_card_rewards = 0         # TheHunt — 런 루프가 소비
        self.in_hand_draw = False           # Speedster — 턴 시작 드로우 구분
        self.cards_played_this_turn = 0     # Ftl / EchoForm
        self.energy_spent_this_turn = 0     # HelixDrill
        self.zero_cost_attacks_this_turn = 0  # Feral AfterApplied 집계
        self.lightning_channeled_this_combat = 0  # Voltaic
        self.ethereal_played_this_combat = 0  # BansheesCry/PullFromBelow/Veilpiercer
        self.osty_attacks_this_turn = 0       # Rattle/Flatten (이번 턴 Osty 공격 수)
        self.cards_drawn_this_turn = 0        # DeathMarch (손패 드로우 제외)
        self.deaths_this_combat = 0           # Melancholy (전투 중 사망 수)
        self._dead_seen: set = set()          # 사망 집계 중복 방지
        self.doom_applied_this_turn = False   # DeathsDoor (이번 턴 Doom 부여 여부)
        self.stars_gained_this_turn = 0       # Radiate (이번 턴 별 획득 합계)
        self.cards_generated_this_combat = 0  # Supermassive (전투 중 생성 카드 수)
        self.last_star_paid = 0               # BlackHole (직전 플레이의 별 소모량)
        self.end_turn_requested = False       # VoidForm — 플레이 시 턴 강제 종료
        self._auto_playing = False            # VoidForm — 자동 플레이 제외 판정
        self.cards_played_this_combat = 0     # GoldAxe (Colorless) — 전투 전체 누적
        self.verbose = False                  # --verbose — 턴/카드/피격 단위 상세 로그
        self.log: List[str] = []              # verbose=True일 때만 누적
        self._card_effect_active = False      # NoBlockP — card.use() 실행 구간에서만 True
                                               # (원본 CreatureCmd.GainBlock의 cardSource 대응)

    # ──────────────────────────────────────────
    # 오브/카드가 참조하는 컨텍스트 프로토콜
    # ──────────────────────────────────────────

    @property
    def alive_enemies(self) -> List["MonsterModel"]:
        return [m for m in self.monsters if not m.is_gone]

    def _log(self, msg: str) -> None:
        """--verbose 전용 로그 누적 (verbose=False면 완전 무비용)."""
        if self.verbose:
            self.log.append(msg)

    def _reshuffle(self) -> None:
        """버림 더미를 뽑을 더미로 셔플 (원본 AfterShuffle 훅 통지 — Stratagem)."""
        self.draw_pile = self.discard_pile
        self.discard_pile = []
        self.rng.shuffle(self.draw_pile)
        self.notify_player_powers("after_shuffle", self)

    def draw_cards(self, count: int) -> None:
        if self.player.get_power_amount("no_draw") > 0:
            return
        for _ in range(count):
            if not self.draw_pile:
                if not self.discard_pile:
                    return
                self._reshuffle()
            card = self.draw_pile.pop()
            self.hand.append(card)
            self.cards_drawn_this_combat += 1
            if not self.in_hand_draw:
                self.cards_drawn_this_turn += 1  # DeathMarch — 손패 드로우 제외 집계
            # Hellraiser 자동 플레이 / CorrosiveWave 중독 / Speedster 피해 / Iteration
            self.notify_player_powers("on_card_drawn", card, self)
            on_drawn = getattr(card, "on_drawn", None)  # Void — 드로우 시 에너지 -1
            if on_drawn:
                on_drawn(self)

    def discard_card(self, card: "STS2Card") -> None:
        """카드 1장 버리기 (효과에 의한 버리기): Sly면 무료 자동 플레이."""
        if card in self.hand:
            self.hand.remove(card)
        sly = card.is_sly or card._sly_this_turn
        self.discard_pile.append(card)
        self.cards_discarded_this_turn += 1
        self.notify_player_powers("on_card_discarded", card, self)
        if sly and card.playable:
            self.discard_pile.remove(card)
            self.auto_play(card)

    def discard_from_hand(self, count: int) -> None:
        for _ in range(count):
            if not self.hand:
                return
            self.discard_card(self.rng.choice(self.hand))

    def discard_all_hand(self) -> int:
        """핸드 전체 버리기 (ShadowStep/StormOfSteel). 버린 수 반환."""
        cards = list(self.hand)
        for card in cards:
            self.discard_card(card)
        return len(cards)

    def create_shivs(self, count: int, upgraded: bool = False,
                     inky: bool = False) -> List["STS2Card"]:
        """Shiv를 손패에 생성 (최대 손패 10장, PhantomBlades Retain 부여)."""
        made = []
        for _ in range(count):
            if len(self.hand) >= 10:  # CardPile.MaxCardsInHand
                break
            shiv = create_card("shiv")
            if upgraded:
                shiv.upgrade()
            shiv.inky = inky
            if self.player.get_power_amount("phantom_blades") > 0:
                shiv.retains = True
            self.hand.append(shiv)
            made.append(shiv)
        return made

    def notify_player_powers(self, hook: str, *hook_args) -> None:
        """플레이어 파워에 카드 이벤트 통지 (on_card_played / on_card_exhausted 등)."""
        for power in list(self.player._powers.values()):
            fn = getattr(power, hook, None)
            if fn:
                fn(*hook_args)

    def notify_card_played(self, card: "STS2Card") -> None:
        """카드 플레이를 플레이어·몬스터 양측 파워에 통지.
        원본 AfterCardPlayed는 소유자 편과 무관하게 전투 내 모든 파워에 전달된다
        (BygoneEffigy의 SlowPower처럼 몬스터가 스스로에게 건 파워도 플레이어의
        카드 플레이를 세어야 함) — 플레이어 파워만 통지하면 그런 파워가 영원히
        누적되지 않는 버그가 생기므로 on_enemy_turn_end와 같은 방식으로 적 측에도
        별도 통지한다."""
        self.notify_player_powers("on_card_played", card, self)
        for enemy in list(self.alive_enemies):
            for power in list(enemy._powers.values()):
                hook = getattr(power, "on_card_played", None)
                if hook:
                    hook(card, self)

    def _exhaust_card(self, card: "STS2Card") -> None:
        """카드 소모 + 소모 이벤트 통지."""
        self.exhaust_pile.append(card)
        self.cards_exhausted_this_turn += 1
        self.notify_player_powers("on_card_exhausted", card, self)
        on_exhausted = getattr(card, "on_exhausted", None)  # DrumOfBattle/HowlFromBeyond
        if on_exhausted:
            on_exhausted(self)

    def exhaust_from_hand(self, count: int) -> int:
        """핸드에서 무작위 카드 소모. 실제 소모된 수 반환."""
        exhausted = 0
        for _ in range(count):
            if not self.hand:
                break
            card = self.rng.choice(self.hand)
            self.hand.remove(card)
            self._exhaust_card(card)
            exhausted += 1
        return exhausted

    def exhaust_all_hand(self) -> int:
        """핸드 전체 소모 (FiendFire류). 소모된 수 반환."""
        cards = list(self.hand)
        self.hand = []
        for card in cards:
            self._exhaust_card(card)
        return len(cards)

    def generate_card(self, card_id: str, count: int = 1, upgraded: bool = False,
                      to: str = "discard", creator_is_player: bool = True) -> List["STS2Card"]:
        """전투 중 카드 생성 (AddGeneratedCardToCombat 대응).
        플레이어가 생성했으면 파워 훅(Smokestack/TrashToTreasure)과
        카드 훅 on_card_generated_combat(RocketPunch)에 통지.
        to="hand"인데 손패가 상한(10)이면 원본 CardPileCmd.Add의
        isFullHandAdd 분기(targetPile = Discard)대로 버림 더미로 보낸다 —
        예전처럼 조용히 버리면 MechaKnight FLAMETHROWER(화상 4장)처럼
        한 번에 여러 장을 손패로 넣는 무브에서 카드가 사라진다."""
        made = []
        for _ in range(count):
            card = create_card(card_id)
            if card is None:
                continue
            if upgraded:
                card.upgrade()
            if to == "hand":
                if len(self.hand) < 10:
                    self.hand.append(card)
                else:
                    self.discard_pile.append(card)
            elif to == "draw":
                self.draw_pile.append(card)
            elif to == "draw_random":  # CardPilePosition.Random 대응 (SoulFysh Beckon 등)
                idx = self.rng.randrange(len(self.draw_pile) + 1)
                self.draw_pile.insert(idx, card)
            else:
                self.discard_pile.append(card)
            made.append(card)
            if creator_is_player:
                self.cards_generated_this_combat += 1  # Supermassive 집계
                self.notify_player_powers("on_card_generated", card, self)
                for pile in (self.hand, self.draw_pile, self.discard_pile):
                    for c in pile:
                        hook = getattr(c, "on_card_generated_combat", None)
                        if hook:
                            hook(card, self)
        return made

    def auto_play_from_draw_pile(self, count: int) -> None:
        """뽑을 더미 맨 위 count장 자동 플레이 (원본 CardPileCmd.AutoPlayFromDrawPile
        — Mayhem, Colorless Phase 6g)."""
        for _ in range(count):
            if self._combat_is_won():
                return
            if not self.draw_pile:
                if not self.discard_pile:
                    return
                self._reshuffle()
            card = self.draw_pile.pop()
            self.auto_play(card)

    def record_orb_channel(self, orb) -> None:
        """오브 채널 기록 (Voltaic — 이번 전투 라이트닝 채널 수)."""
        if orb.orb_id == "lightning":
            self.lightning_channeled_this_combat += 1

    def add_status_to_discard(self, card_id: str, count: int) -> None:
        """몬스터가 상태이상 카드를 버림 더미에 삽입 (Dazed/Slimed) — 생성 훅 미발동."""
        self.generate_card(card_id, count=count, creator_is_player=False)

    def add_status_to_draw(self, card_id: str, count: int) -> None:
        """몬스터가 상태이상 카드를 뽑을 더미의 무작위 위치에 삽입 (원본
        CardPilePosition.Random 대응 — SoulFysh BECKON_MOVE) — 생성 훅 미발동.
        draw_pile.append(맨 위/확정 다음 드로우)와 달리 매번 독립적으로 무작위
        위치에 끼워 넣어 다음 드로우에 무조건 뽑히지 않도록 한다."""
        self.generate_card(card_id, count=count, to="draw_random", creator_is_player=False)

    def get_card_cost(self, card: "STS2Card") -> int:
        """실효 비용: 파워(FreeAttack/Corruption)의 비용 수정 반영. X코스트는 0(최소)."""
        if card.x_cost:
            return 0
        if card._free_this_turn:  # BulletTime / WhiteNoise
            return 0
        if card._free_until_played:  # RocketPunch — 상태이상 생성 시 0
            return 0
        cost = card.cost
        if card._cost_this_combat is not None:  # SetThisCombat (MomentumStrike 등)
            cost = card._cost_this_combat
        cost += card._cost_add_this_combat       # AddThisCombat (Modded)
        dynamic = getattr(card, "dynamic_cost", None)  # Stomp — 상태 의존 비용
        if dynamic:
            cost = dynamic(self)
        for power in self.player._powers.values():
            modify = getattr(power, "modify_card_cost", None)
            if modify:
                cost = modify(card, cost)
        return max(0, cost)

    def get_card_star_cost(self, card: "STS2Card") -> int:
        """실효 별 비용: 파워(VoidForm)의 별 비용 수정 반영. 별 X코스트는 0(최소)."""
        if getattr(card, "star_x_cost", False):
            return 0
        cost = card.star_cost
        for power in self.player._powers.values():
            modify = getattr(power, "modify_card_star_cost", None)
            if modify:
                cost = modify(card, cost)
        return max(0, cost)

    def is_card_playable(self, card: "STS2Card") -> bool:
        """비용/자원 + Shackled(전체)/Tangled(공격) 차단 검사."""
        if not card.playable:
            return False
        dynamic = getattr(card, "dynamic_playable", None)  # GrandFinale
        if dynamic and not dynamic(self):
            return False
        if (self.get_card_cost(card) > self.player.energy
                or self.get_card_star_cost(card) > self.player.stars):
            return False
        if self.player.get_power_amount("shackled") > 0:
            return False
        if card.card_type == CardType.ATTACK and self.player.get_power_amount("tangled") > 0:
            return False
        return True

    # ──────────────────────────────────────────
    # 전투 루프
    # ──────────────────────────────────────────

    def start(self) -> None:
        """전투 개시: 몬스터 배치 → 렐릭 전투 시작 훅."""
        for i, monster in enumerate(self.monsters):
            monster.setup_for_combat(self, rng=random.Random(self.rng.random()))
        for relic in self.player.relics:
            relic.on_combat_start(self)

    def run(self, policy, max_turns: int = 100) -> CombatResult:
        """정책(policy.choose)이 카드를 고르는 전투 루프 실행."""
        self.start()

        while True:
            self.turn += 1
            if self.turn > max_turns:
                return self._finish(False)

            # ── 플레이어 턴 ──
            self.player.start_of_turn()
            self.cards_exhausted_this_turn = 0
            self.attacks_played_this_turn = 0
            self.skills_played_this_turn = 0
            self.cards_discarded_this_turn = 0
            self.shivs_played_this_turn = 0
            self.cards_played_this_turn = 0
            self.energy_spent_this_turn = 0
            self.zero_cost_attacks_this_turn = 0
            self.osty_attacks_this_turn = 0
            self.cards_drawn_this_turn = 0
            self.doom_applied_this_turn = False
            self.stars_gained_this_turn = 0
            self.end_turn_requested = False
            for monster in self.monsters:
                monster._hits_taken_this_turn = 0  # BeatIntoShape 턴 집계
            self.player.energy = self.player.max_energy
            self._log(f"--- Turn {self.turn} --- Player HP {self.player.current_hp}/"
                      f"{self.player.max_hp} Block {self.player.block} "
                      f"Energy {self.player.energy}")
            for enemy in self.alive_enemies:
                intent = enemy.get_current_intent()
                dmg = f" dmg={intent.damage}x{intent.times}" if intent.damage else ""
                self._log(f"  {enemy.title} HP {enemy.current_hp}/{enemy.max_hp} "
                          f"intent={intent.intent_type.name}{dmg}")
            # EnergyNextTurn/LightningRod/Spinner (원본 AfterEnergyReset)
            self.notify_player_powers("after_energy_reset")
            for relic in self.player.relics:
                relic.on_turn_start(self, self.turn)
            for power in list(self.player._powers.values()):
                on_start = getattr(power, "on_turn_start", None)
                if on_start:
                    on_start()
            self.player.orb_queue.trigger_turn_start(self)

            if self.turn == 1:
                # 선천성(Innate) 카드는 첫 손패에 우선 포함
                innate = [c for c in self.draw_pile if c.is_innate]
                for card in innate:
                    self.draw_pile.remove(card)
                    self.hand.append(card)

            draw_count = self.BASE_DRAW
            for relic in self.player.relics:
                draw_count = relic.modify_hand_draw(draw_count, self.turn)
            for power in list(self.player._powers.values()):
                modify = getattr(power, "modify_hand_draw", None)
                if modify:  # ToolsOfTheTrade / DrawCardsNextTurn
                    draw_count = modify(draw_count)
            # Bolas/ThrummingHatchet(Colorless) — 직전 턴에 플레이된 카드 손패 복귀
            for pile in (self.discard_pile, self.draw_pile):
                for card in list(pile):
                    hook = getattr(card, "on_before_hand_draw", None)
                    if hook and card in pile:
                        hook(self)
            self.notify_player_powers("before_hand_draw", self)  # CreativeAI 파워 카드 생성
            self.in_hand_draw = True
            self.draw_cards(draw_count)
            self.in_hand_draw = False
            self.notify_player_powers("after_hand_draw", self)  # ToolsOfTheTrade 버리기

            # 자동 선플레이 페이즈 (원본 AutoPrePlayPhase) — Bombardment 소모 더미 자동 플레이
            for card in list(self.exhaust_pile):
                hook = getattr(card, "on_pre_play_phase", None)
                if hook and card in self.exhaust_pile:
                    hook(self)
            self.notify_player_powers("on_pre_play_phase", self)  # Mayhem(Colorless)
            if self._combat_is_won():
                return self._finish(True)

            while True:
                choice = policy.choose(self)
                if choice is None:
                    break
                card, target = choice
                self.play_card(card, target)
                if self._combat_is_won() or self.end_turn_requested:
                    break

            if self._combat_is_won():
                return self._finish(True)

            # 자동 후플레이 페이즈 (원본 AutoPostPlayPhase) — IAmInvincible 자동 플레이
            if self.draw_pile:
                hook = getattr(self.draw_pile[-1], "on_post_play_phase", None)
                if hook:
                    hook(self)
            if self._combat_is_won():
                return self._finish(True)

            # 턴 종료
            self.player.orb_queue.trigger_turn_end(self)
            if self._combat_is_won():
                return self._finish(True)
            for power in list(self.player._powers.values()):
                on_end = getattr(power, "on_turn_end", None)
                if on_end:
                    on_end()
            self.player.tick_powers()
            self._discard_hand()
            if self.player.is_dead:  # Poison/Burning 자해
                return self._finish(False)

            # ── 몬스터 턴 ──
            for monster in list(self.alive_enemies):
                monster.start_of_turn()
                for power in list(monster._powers.values()):
                    on_start = getattr(power, "on_turn_start", None)
                    if on_start:
                        on_start()
                monster.take_turn([self.player])
                if self.verbose:
                    self._log(f"  {monster.title} acts -> Player HP "
                              f"{self.player.current_hp}/{self.player.max_hp} "
                              f"Block {self.player.block}")
                for power in list(monster._powers.values()):
                    on_end = getattr(power, "on_turn_end", None)
                    if on_end:
                        on_end()
                monster.tick_powers()
                if self.player.is_dead:
                    return self._finish(False)

            self._trigger_doom()  # 적 턴 종료 시 Doom 즉사 (원본 BeforeSideTurnEnd)
            self.reap_deaths()    # Doom 처치 포함 사망 집계
            self.notify_player_powers("on_enemy_turn_end")  # Colossus 감쇠
            # 원본 AfterSideTurnEnd(side==Enemy)는 소유자가 플레이어든 몬스터든
            # 무관하게 통지된다 (예: SoulFysh가 자기 자신에게 건 Intangible도
            # 적 턴 종료마다 감소해야 함) — 플레이어 파워 통지만으로는 몬스터가
            # 스스로에게 건 파워가 영원히 감소하지 않는 버그가 생기므로 별도 통지.
            for enemy in list(self.alive_enemies):
                for power in list(enemy._powers.values()):
                    hook = getattr(power, "on_enemy_turn_end", None)
                    if hook:
                        hook()

            if self._combat_is_won():
                return self._finish(True)

    def _trigger_doom(self) -> None:
        """Doom 보유 적: 턴 종료 시 HP가 Doom 수치 이하이면 즉사 (원본 DoomKill = 직접 처치)."""
        for enemy in list(self.alive_enemies):
            doom = enemy._powers.get("doom")
            if (doom is not None and doom.is_owner_doomed()
                    and enemy.should_disappear_from_doom):
                enemy._current_hp = 0

    def _combat_is_won(self) -> bool:
        """사망 훅의 동기 부활을 먼저 수습한 뒤 승리를 판정한다."""
        self.reap_deaths()
        return not self.alive_enemies

    def _resolve_targets(self, card: "STS2Card",
                         target: Optional["MonsterModel"]) -> List["MonsterModel"]:
        if card.card_type != CardType.ATTACK \
                and not getattr(card, "needs_target", False):
            return []
        if card.target_all:
            return list(self.alive_enemies)
        return [target] if target is not None else self.alive_enemies[:1]

    def play_card(self, card: "STS2Card", target: Optional["MonsterModel"] = None) -> bool:
        """카드 플레이: 비용 지불 → 효과 → 버림/소모 이동 → 렐릭 훅."""
        if card not in self.hand or not self.is_card_playable(card):
            return False

        if card.x_cost:
            paid = self.player.energy
            card.x_value = paid  # X = 남은 에너지 전부 소비
            self.player.energy = 0
        else:
            paid = self.get_card_cost(card)
            self.player.energy -= paid
        if getattr(card, "star_x_cost", False):
            star_paid = self.player.stars  # Stardust — 별 전부 소비
            card.star_x_value = star_paid
        else:
            star_paid = self.get_card_star_cost(card)
        self.player.stars -= star_paid
        self.last_star_paid = star_paid     # BlackHole — 플레이 종료 후 발동 판정
        if star_paid > 0:
            # ChildOfTheStars (원본 AfterStarsSpent — 효과 처리 전 지불 시점)
            self.notify_player_powers("after_stars_spent", star_paid)
        if paid > 0:
            self.notify_player_powers("after_energy_spent", card, paid)  # Orbit
        card._last_paid = paid              # Feral 판정
        card._free_until_played = False     # RocketPunch — 플레이로 소모
        self.energy_spent_this_turn += paid
        prior_plays = self.cards_played_this_turn  # EchoForm — 이번 턴 몇 번째 플레이인지
        self.cards_played_this_turn += 1
        self.cards_played_this_combat += 1
        if card.card_type == CardType.ATTACK and paid == 0:
            self.zero_cost_attacks_this_turn += 1  # 원본 CardPlayStartedEntry(EnergyValue==0, Attack)
        if card.is_ethereal:
            self.ethereal_played_this_combat += 1  # Necrobinder ethereal 시너지

        # 카드는 효과 처리 전에 핸드를 떠난다 (효과 중 핸드 버리기가 자신을 버리지 않도록)
        self.hand.remove(card)

        if card.card_type == CardType.ATTACK:
            self.attacks_played_this_turn += 1
            # FreeAttack(Unrelenting) — 효과 처리 전에 스택 차감 (원본 BeforeCardPlayed)
            if self.player.get_power_amount("free_attack") > 0:
                fa = self.player._powers["free_attack"]
                fa.amount -= 1
                if fa.amount <= 0:
                    fa.remove()
        elif card.card_type == CardType.SKILL:
            self.skills_played_this_turn += 1
            # FreeSkill(Pounce) — 효과 처리 전에 스택 차감
            if self.player.get_power_amount("free_skill") > 0:
                fs = self.player._powers["free_skill"]
                fs.amount -= 1
                if fs.amount <= 0:
                    fs.remove()
        elif card.card_type == CardType.POWER:
            # FreePower(Synthesis) — 효과 처리 전에 스택 차감
            if self.player.get_power_amount("free_power") > 0:
                fp = self.player._powers["free_power"]
                fp.amount -= 1
                if fp.amount <= 0:
                    fp.remove()

        # 원본 ModifyCardPlayCount는 플레이 시작 시점 기준 — 이 플레이로
        # 부여된 파워(EchoForm/SignalBoost 자신)는 이번 플레이에 미적용
        echo_before = self.player.get_power_amount("echo_form")
        signal_boost_before = self.player.get_power_amount("signal_boost")

        # Lethality — 이번 턴 첫 공격 카드 판정 (원본 첫 attack CardPlayStarted)
        self.player._first_attack_this_turn = (
            card.card_type == CardType.ATTACK and self.attacks_played_this_turn == 1)

        # SealedThrone — 효과 처리 전 발동 (원본 BeforeCardPlayed)
        self.notify_player_powers("before_card_played", card, self)

        targets = self._resolve_targets(card, target)
        if self.verbose:
            tgt = f" -> {targets[0].title}" if targets else ""
            self._log(f"  Play {card.name}{tgt} (cost {paid})")
        self._card_effect_active = True
        card.use(self.player, targets, self)

        # OneTwoPunch — 공격 카드 2회 발동
        if (card.card_type == CardType.ATTACK
                and self.player.get_power_amount("one_two_punch") > 0):
            otp = self.player._powers["one_two_punch"]
            otp.amount -= 1
            if otp.amount <= 0:
                otp.remove()
            retargets = [t for t in self._resolve_targets(card, target) if not t.is_gone]
            if retargets or card.card_type != CardType.ATTACK:
                card.use(self.player, retargets, self)

        # Burst — 스킬 카드 2회 발동
        if (card.card_type == CardType.SKILL
                and self.player.get_power_amount("burst") > 0):
            burst = self.player._powers["burst"]
            burst.amount -= 1
            if burst.amount <= 0:
                burst.remove()
            card.use(self.player, [], self)

        # SignalBoost — 파워 카드 2회 발동
        if card.card_type == CardType.POWER and signal_boost_before > 0:
            sb = self.player._powers.get("signal_boost")
            if sb is not None:
                sb.amount -= 1
                if sb.amount <= 0:
                    sb.remove()
            card.use(self.player, [], self)

        # EchoForm — 매 턴 처음 N장의 카드 2회 발동
        if prior_plays < echo_before:
            retargets = [t for t in self._resolve_targets(card, target) if not t.is_gone]
            if retargets or card.card_type != CardType.ATTACK:
                card.use(self.player, retargets, self)

        # Transfigure Replay — 카드에 부여된 추가 발동 횟수만큼 재발동
        for _ in range(getattr(card, "_extra_plays", 0)):
            retargets = [t for t in self._resolve_targets(card, target) if not t.is_gone]
            if retargets or card.card_type != CardType.ATTACK:
                card.use(self.player, retargets, self)

        self._card_effect_active = False
        self._settle_card(card)
        self.player._first_attack_this_turn = False

        for relic in self.player.relics:
            relic.on_card_played(card)
        self.notify_card_played(card)
        self._broadcast_card_played(card, paid)  # RightHandHand — 버림 더미 회수
        self._trigger_strangle()
        self.reap_deaths()  # Melancholy — 사망 집계
        if self.verbose:
            enemy_state = ", ".join(
                f"{m.title} {m.current_hp}/{m.max_hp}" for m in self.alive_enemies)
            self._log(f"    -> Player Block {self.player.block} | {enemy_state}")
        return True

    def _broadcast_card_played(self, card: "STS2Card", paid: int) -> None:
        """버림/드로우 더미의 카드에 플레이 이벤트 통지 (RightHandHand)."""
        for pile in (self.discard_pile, self.draw_pile):
            for c in list(pile):
                hook = getattr(c, "on_ally_card_played", None)
                if hook:
                    hook(card, paid, self)

    def reap_deaths(self) -> None:
        """새 사망 episode를 집계하고 사망 훅·owner 파워 정리를 수행한다.

        훅에서 동기적으로 부활한 몬스터는 latch를 해제하여 최종 재사망을 별도
        episode로 집계한다 (Waterfall Giant의 Steam Eruption)."""
        for monster in self.monsters:
            key = id(monster)
            if not monster.is_dead:
                self._dead_seen.discard(key)
                continue
            if key in self._dead_seen:
                continue

            self._dead_seen.add(key)
            self.deaths_this_combat += 1
            self._broadcast_death(monster)

            for power_id, power in list(monster._powers.items()):
                if not getattr(power, "persists_after_owner_death", False):
                    monster.remove_power(power_id)

            if not monster.is_dead:
                self._dead_seen.discard(key)

    def _broadcast_death(self, dead: "Creature") -> None:
        """원본 AfterDeath — 플레이어/몬스터 구분 없이 전투 내 모든 파워에 통지."""
        for creature in [self.player, *self.monsters]:
            for p in list(creature._powers.values()):
                hook = getattr(p, "on_any_death", None)
                if hook:
                    hook(dead)

    def _trigger_strangle(self) -> None:
        """Strangle — 플레이어 카드 플레이마다 교살당한 적이 비차단 피해."""
        for enemy in list(self.alive_enemies):
            amount = enemy.get_power_amount("strangle")
            if amount > 0:
                enemy.lose_hp(amount)

    def _settle_card(self, card: "STS2Card", force_exhaust: bool = False) -> None:
        """플레이 후 카드 이동: 파워는 전투에서 제거, 소모 or 버림 (Corruption 스킬은 소모)."""
        card._free_this_turn = False
        card._sly_this_turn = False
        if card.card_type == CardType.POWER:
            return  # 파워 카드는 플레이 시 전투에서 사라진다
        # Feral — 매 턴 처음 N장의 0코스트 공격은 손패로 (원본은 소모보다 우선)
        # 원본은 !card.IsDupe 조건도 있으나, dupe(복제) 생성원(Duplication Potion 등)은
        # 미구현이라 관측 불가 — AdaptiveStrike는 CreateClone(비-dupe)이라 복귀가 정상.
        if card.card_type == CardType.ATTACK and card._last_paid == 0:
            feral = self.player._powers.get("feral")
            if (feral is not None and feral.used_this_turn < feral.amount
                    and len(self.hand) < 10):
                feral.used_this_turn += 1
                self.hand.append(card)
                return
        if (force_exhaust or card.exhausts
                or (card.card_type == CardType.SKILL
                    and self.player.has_power("corruption"))):
            self._exhaust_card(card)
            return
        # Regent — 버림 대신 다른 위치로 이동하는 카드 (원본 GetResultPileTypeAndPosition)
        settle_to = getattr(card, "settle_to", None)
        if settle_to == "draw_top":       # ShiningStrike — 뽑을 더미 맨 위
            self.draw_pile.append(card)
        elif settle_to == "hand" and len(self.hand) < 10:  # ParticleWall — 손패로
            self.hand.append(card)
        elif settle_to == "draw_random":  # TheBall(Colorless) — 뽑을 더미 무작위 위치
            idx = self.rng.randrange(len(self.draw_pile) + 1)
            self.draw_pile.insert(idx, card)
        else:
            override = self._settle_override(card)
            if override == "draw_top":
                self.draw_pile.append(card)
            else:
                self.discard_pile.append(card)

    def _settle_override(self, card: "STS2Card") -> Optional[str]:
        """파워가 기본 버림 경로를 재정의 (Nostalgia — 이번 턴 첫 N장 공격/스킬을
        뽑을 더미 맨 위로 대신 이동)."""
        if card.card_type not in (CardType.ATTACK, CardType.SKILL):
            return None
        for power in self.player._powers.values():
            fn = getattr(power, "modify_settle_pile", None)
            if fn:
                result = fn(card, self)
                if result:
                    return result
        return None

    def auto_play(self, card: "STS2Card", force_exhaust: bool = False) -> None:
        """비용 없이 카드 자동 플레이 (Havoc/Cascade/Stampede/Hellraiser).
        card는 이미 어느 파일에서든 제거된 상태이거나 핸드에 있을 수 있다."""
        if card in self.hand:
            self.hand.remove(card)
        if not card.playable:
            self.discard_pile.append(card)
            return
        target = min(self.alive_enemies, key=lambda m: m.current_hp) \
            if self.alive_enemies else None
        if card.x_cost:
            card.x_value = 0  # X코스트 자동 플레이는 X=0 (원본 AutoPlay 동일)
        card._last_paid = 0  # 자동 플레이는 에너지 미지불 (Feral 판정 대상)
        self.cards_played_this_turn += 1
        self.cards_played_this_combat += 1
        if card.card_type == CardType.ATTACK:
            self.attacks_played_this_turn += 1
            self.zero_cost_attacks_this_turn += 1  # 원본 CardPlayStartedEntry(EnergyValue==0)
        elif card.card_type == CardType.SKILL:
            self.skills_played_this_turn += 1
        if card.is_ethereal:
            self.ethereal_played_this_combat += 1
        self.player._first_attack_this_turn = (
            card.card_type == CardType.ATTACK and self.attacks_played_this_turn == 1)
        self.last_star_paid = 0  # 자동 플레이는 별 미지불 (BlackHole 미발동)
        prev_auto = self._auto_playing
        self._auto_playing = True  # VoidForm — 자동 플레이는 무료 카드 수 미차감
        self.notify_player_powers("before_card_played", card, self)  # SealedThrone
        targets = self._resolve_targets(card, target)
        if self.verbose:
            tgt = f" -> {targets[0].title}" if targets else ""
            self._log(f"  [Auto] Play {card.name}{tgt}")
        self._card_effect_active = True
        card.use(self.player, targets, self)
        self._card_effect_active = False
        self._settle_card(card, force_exhaust=force_exhaust)
        self.player._first_attack_this_turn = False
        for relic in self.player.relics:
            relic.on_card_played(card)
        self.notify_card_played(card)
        self._auto_playing = prev_auto
        self._broadcast_card_played(card, 0)
        self._trigger_strangle()
        self.reap_deaths()

    def _discard_hand(self) -> None:
        """턴 종료 핸드 정리. 에테리얼은 소모, Retain 카드는 유지."""
        self.notify_player_powers("on_before_hand_discard", self)  # WellLaidPlans
        for card in list(self.hand):
            hook = getattr(card, "on_turn_end_in_hand", None)  # Burn 자해
            if hook:
                hook(self.player, self)
        cards = list(self.hand)
        self.hand = []
        # RetainHand (Convergence) — 손패 전체 유지. Ethereal 소모는 그대로
        # (원본 ShouldFlush=false — Ethereal 처리는 flush와 별개의 DoTurnEnd)
        retain_hand = self.player._powers.get("retain_hand")
        if retain_hand is not None:
            for card in cards:
                if card.is_ethereal:
                    self._exhaust_card(card)
                else:
                    card._retain_this_turn = False
                    card._free_this_turn = False
                    card._sly_this_turn = False
                    self.hand.append(card)
            retain_hand.amount -= 1
            if retain_hand.amount <= 0:
                retain_hand.remove()
            return
        for card in cards:
            if card.is_ethereal:
                self._exhaust_card(card)
            elif card.retains or card._retain_this_turn:
                card._retain_this_turn = False
                card._free_this_turn = False
                card._sly_this_turn = False
                self.hand.append(card)
            else:
                card._free_this_turn = False
                card._sly_this_turn = False
                self.discard_pile.append(card)

    def _finish(self, victory: bool) -> CombatResult:
        # 전투 한정 키워드 변형(MasterPlanner Sly/PhantomBlades Retain 등)을 원복
        for pile in (self.hand, self.draw_pile, self.discard_pile, self.exhaust_pile):
            for card in pile:
                card.is_sly = type(card).is_sly
                # 업그레이드로 부여된 Retain(Monologue/RoyalGamble)은 영구 유지
                card.retains = (type(card).retains
                                or getattr(card, "_retains_permanent", False))
                card._free_this_turn = card._sly_this_turn = False
                card._retain_this_turn = False
                card._free_until_played = False
                card._cost_this_combat = None
                card._cost_add_this_combat = 0
                card._extra_plays = 0
                reset = getattr(card, "reset_combat_state", None)  # Claw 누적 데미지
                if reset:
                    reset()
        self.notify_player_powers("on_combat_end", victory)  # Royalties 골드 보상
        for relic in self.player.relics:
            relic.on_combat_end(victory)
        self.player.sync_to_character()
        self._log(f"=== {'VICTORY' if victory else 'DEFEAT'} "
                  f"(turn {self.turn}, HP {self.player.current_hp}) ===")
        return CombatResult(victory=victory, turns=self.turn, player_hp=self.player.current_hp)


class SimplePolicy:
    """기본 그리디 정책: 공격 우선, 남는 에너지로 스킬. 최저 HP 적 우선 타격."""

    def choose(self, combat: CombatState) -> Optional[Tuple["STS2Card", Optional["MonsterModel"]]]:
        player = combat.player
        enemies = combat.alive_enemies
        if not enemies:
            return None

        playable = [c for c in combat.hand if combat.is_card_playable(c)]
        if not playable:
            return None

        target = min(enemies, key=lambda m: m.current_hp)

        attacks = [c for c in playable if c.card_type == CardType.ATTACK]
        if attacks:
            best = max(attacks, key=lambda c: c.cost)
            return (best, target)

        skills = [c for c in playable if c.card_type != CardType.ATTACK]
        if skills:
            return (skills[0], None)
        return None
