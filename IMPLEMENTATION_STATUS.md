# STS2 시뮬레이터 — 구현 현황

`sts2.dll` 디컴파일 데이터 기반 헤드리스 Slay the Spire 2 시뮬레이터.
모든 수치는 `decompiled/MegaCrit.Sts2.Core.*`에서 추출한 실제값 (Ascension 미적용 기본값).

## 📊 규모 요약

| 시스템 | 개수 | 비고 |
|--------|------|------|
| 몬스터 | 89종 | 상태 머신 AI, 실제 HP/데미지 (보스 SoulFysh/LagavulinMatriarch/WaterfallGiant/Vantom 포함) |
| 인카운터 | 68종 | 실제 구성 로직 (미이식/자체 구성 4종은 주석 표기) |
| 캐릭터 | 5종 | Ironclad / Silent / Defect / Necrobinder / Regent |
| 카드 | 503종 | **Ironclad 85 + Silent 86 + Defect 86 + Necrobinder 82 + Regent 82 + Colorless 65종 완전 이식** + 스타터/상태이상(Infection/Toxic/Beckon 포함)/토큰 (STS2 전체 593종 중) |
| 파워 | 180종 | 비용 수정/자동 플레이/소모·버리기/생성·이보크 훅 배선 완료 |
| 렐릭 | 22종 | 스타터 5종은 실제 동작 |
| 오브 | 5종 | Lightning/Frost/Dark/Plasma/Glass + OrbQueue (슬롯 상한 10/EvokeLast/수동 패시브) |
| 테스트 | 27개 스위트 | 전부 통과, 시드 재현성 보장 |

## 🏗️ 구조

```
sts2_sim/
├─ entities/
│  ├─ creature.py        # 공유 데미지 파이프라인 (파워 수정, 블록, 피격 트리거)
│  ├─ player.py          # 전투 플레이어 (에너지/Stars/Osty/오브/렐릭/덱)
│  ├─ sts2_character.py  # 캐릭터 정의 (실제 시작 덱/렐릭/HP)
│  ├─ sts2_monster.py    # MonsterModel + 상태 머신 + 기본 17종
│  └─ monsters_extra.py  # Phase 6a 추가 17종
├─ models/
│  ├─ sts2_power.py      # 파워 120종
│  ├─ sts2_card.py       # 카드 베이스 + 스타터 16종 + 상태이상 5종
│  ├─ sts2_relic.py      # 렐릭 22종
│  └─ sts2_orb.py        # 오브 5종 + OrbQueue (상한 10/EvokeLast/이보크 훅)
├─ cards/
│  ├─ ironclad.py        # Phase 6b: Ironclad 풀 82종 (C19/U35/R25/Ancient2/Token1)
│  ├─ silent.py          # Phase 6c: Silent 풀 80종 (C19/U34/R25/Ancient2)
│  ├─ defect.py          # Phase 6d: Defect 풀 83종 (C20/U35/R25/Ancient2/Token1)
│  ├─ necrobinder.py     # Phase 6e: Necrobinder 풀 84종 (C20/U35/R25/Ancient2/Token2)
│  ├─ regent.py          # Phase 6f: Regent 풀 87종 (C20/U35/R25/Ancient2/Token5)
│  └─ colorless.py       # Phase 6g: Colorless 풀 65종 (U40/R25, Common 없음)
└─ core/
   ├─ combat.py          # 턴 루프 + SimplePolicy
   ├─ policy.py          # GreedyPolicy (인텐트 인지)
   ├─ encounters.py      # 인카운터 팩토리 + 난이도 풀
   ├─ run.py             # 런 루프 (보상/휴식/덱 성장)
   └─ stats.py           # 통계 러너 CLI
```

## 🎮 캐릭터 (디컴파일 Models.Characters 그대로)

| 캐릭터 | HP | 시작 덱 | 스타터 렐릭 | 고유 메카닉 |
|--------|----|---------|------------|------------|
| Ironclad | 80 | Strike×5, Defend×4, Bash | Burning Blood | — |
| Silent | 70 | Strike×5, Defend×5, Neutralize, Survivor (12장) | Ring of the Snake | — |
| Defect | 75 | Strike×4, Defend×4, Zap, Dualcast | Cracked Core | 오브 슬롯 3 |
| Necrobinder | 66 | Strike×4, Defend×4, Bodyguard, Unleash | Bound Phylactery | Osty 소환수 |
| Regent | 75 | Strike×4, Defend×4, FallingStar, Venerate | Divine Right | Stars 자원 |

※ Watcher는 STS2에 존재하지 않음 (디컴파일로 확인).

## 👹 몬스터 89종

**기본 (sts2_monster.py):** BigDummy, SingleAttack/MultiAttackMoveMonster(테스트),
TwigSlimeS/M, Stabbot, Zapbot, Guardbot, AxeRubyRaider, FlailKnight, DampCultist,
Chomper, FatGremlin, Parafright, EyeWithTeeth, BattleFriendV1/V2

**Phase 6a (monsters_extra.py):** LeafSlimeS/M, CalcifiedCultist, SpectralKnight,
MagiKnight, Assassin/Brute/Tracker/CrossbowRubyRaider, SewerClam, SnappingJaxfruit,
SneakyGremlin, Noisebot, LivingShield, Mawler, GlobeHead, VineShambler

**Phase 6j 배치1 (monsters_batch7a/7b/7c.py):**
FuzzyWurmCrawler, Nibbit, Seapunk, TurretOperator, PunchConstruct (7a) ·
DevotedSculptor, KinPriest, Toadpole, SludgeSpinner, HauntedShip (7b) ·
Wriggler, Myte, FrogKnight (7c)

**Phase 6k 배치8 (monsters_batch8.py):** MysteriousKnight, Flyconid,
ShrinkerBeetle, LouseProgenitor, SpinyToad, Byrdonis, FossilStalker,
SoulFysh(Act1 보스)

**Phase 6l 배치9 (monsters_batch9.py, Act1 완결):** CorpseSlug,
SkulkingColony(엘리트), TerrorEel(엘리트), PhantasmalGardener(엘리트),
LagavulinMatriarch(보스)

**Phase 6m 배치10 (monsters_batch10.py):** WaterfallGiant(보스 — 첫 사망을
가로채 누적 Steam만큼 폭발한 뒤 최종 사망하는 2단계 lifecycle)

**Phase 6n 배치11 (monsters_batch11.py):** SlimedBerserker,
SlitheringStrangler, Exoskeleton, HunterKiller, MechaKnight(엘리트),
BygoneEffigy(엘리트), Inklet, ScrollOfBiting, Vantom(보스 — Doom 즉사 면역)

**Phase 6o~6q 배치12 (monsters_batch12.py, 전투 중 소환 계열):**
PhrogParasite(엘리트 — 사망 시 Wriggler 4마리), TwoTailedRat(슬롯 기반
동족 소환), GremlinMerc(골드 절취 + 사망 시 동료 2종 소환)

**Phase 6r 배치13 (monsters_batch13.py):** CubexConstruct(개전 블록13 +
Artifact1, 무브마다 힘 누적), SoulNexus(엘리트, 3분기 CannotRepeat)

**Phase 6s 배치14 (monsters_batch14.py):** Fogmog(IllusionPower — 피해를
받으면 스택 1 소모하며 무효화), TheObscura

**Phase 6t 배치15 (monsters_batch15.py):** ToughEgg(개전 HP 14~18 +
HatchPower2, 첫 턴 HATCH_MOVE로 Minion 외 모든 파워 제거 + HP 19~22 재설정 →
NIBBLE 4딜 무한 반복), Ovicopter(LAY_EGGS로 빈 알 슬롯을 **뒤에서부터** 최대
3칸 ToughEgg+Minion 소환 → SMASH16 → TENDERIZER 7딜+취약2 → SUMMON_BRANCH
{살아있는 적 ≤3 ? LAY_EGGS : NUTRITIONAL_PASTE 힘+3 → SMASH})

**Phase 6u 배치16 (monsters_batch16.py):** Tunneler(HP 87, BITE 13 → BURROW
BurrowedPower+블록 32 → BELOW 23 반복; 블록 전소진 시 on_block_broken → stun
DIZZY 1턴 → BITE 재개), SlumberingBeetle(HP 86, 개전 Plating 15 + Slumber 3;
SNORE 반복 → Slumber 0이 되면 기상: 턴 종료 경로는 즉시 WakeUpMove 실행 후
Plating 상실, 피해 경로는 Stun(WakeUpMove, ROLL_OUT_MOVE) 삽입으로 다음 턴에
기상하며 Plating은 기상 턴 전까지 유지 → ROLL_OUT 16딜+힘+2 누적), OwlMagistrate(HP
231, 4무브 순환: SCRUTINY 16 → PECK_ASSAULT 4×6 → JUDICIAL_FLIGHT SoarPower →
VERDICT 33딜+취약 4, Soar 제거)

**`S1.M3.B17` (legacy Phase 6v, monsters_batch17.py):** Entomancer(엘리트, HP 145, 개전
PersonalHivePower1; **시작 무브는 BEES** 3딜×7 → SPEAR 18 → PHEROMONE_SPIT
{벌집 <3 ? 벌집+1&힘+1 : 힘+2} 순환), KinFollower(HP 58~59, 개전 Minion1,
QUICK_SLASH 5 → BOOMERANG 2×2 → POWER_DANCE 힘+2 순환; starts_with_dance면
POWER_DANCE부터 시작해 두 마리의 무브가 어긋난다), TorchHeadAmalgam(HP 199,
개전 Minion1, TACKLE 18 ×2는 개전 1회뿐 → BEAM 8×3 → 약태클 14 ×2 → BEAM
3턴 무한 루프)

**`S1.M3.B18` (monsters_batch18.py):** BowlbugEgg(HP 21~22, 7딜+블록7 반복),
BowlbugNectar(HP 35~38, 3딜 → 힘+15 → 공격 반복), BowlbugRock(HP 45~48,
개전 Imbalanced1, 15딜이 완전 블록되면 off-balance → DIZZY), BowlbugSilk
(HP 40~43, 약화1로 시작해 4딜×2와 교대). `bowlbugs_weak`/`bowlbugs_normal`
추가, `slumbering_beetle_normal`을 Rock+Silk+SlumberingBeetle 원본 구성으로 복원.

특수 메카닉: RandomBranchState(가중치/CannotRepeat/UseOnlyOnce/**cooldown**·
**max_repeats** — Phase 6k에서 엔진 확장, 아래 참고), 조건 분기(LivingShield,
FrogKnight HP 절반), ConditionalBranchState(슬롯·상태 조건 순차 평가 —
PhantasmalGardener/Exoskeleton), 도주(FatGremlin/SneakyGremlin 대기→행동),
상태이상 삽입(Dazed/Slimed/Infection/Toxic/Beckon/Wound, **손패 직접 삽입**
— MechaKnight 화상, 상한 초과분은 원본대로 버림 더미로), Ritual 램핑(첫 틱 스킵 포함, Phase 6j에서 타이밍
버그 수정), Artifact 디버프 무효, Plating 감쇠 블록(개전 즉시 지급 — Phase 6l),
Tangled 공격 봉쇄, 슬롯 의존 초기 행동(Nibbit/Toadpole/Myte/Wriggler/
PunchConstruct/PhantasmalGardener/Exoskeleton), 다단히트 파워 소급반영
방지(SuckPower.flush_landed_attacks — Phase 6k), 몬스터 자기부여 파워의
적턴종료 감쇠(Intangible — Phase 6k), 사망 인터셉트·부활(SteamEruption —
Phase 6m), 피해 상한 Cap 단계(Intangible/HardToKill), HP 손실 상한
(HardenedShell/Slippery), 최대 HP 감소(PaperCuts — Phase 6n),
피해 무효 스택(IllusionPower — Phase 6s), 역순 빈 슬롯 소환
(CombatState.last_free_slot — 원본 LastOrDefault 대응, Phase 6t), **블록 유지
파워(BurrowedPower: ShouldClearBlock=false로 턴 시작 블록 초기화 방지 + on_block_broken
후킹으로 전소진 시 stun, 제거 시 잔여 블록 0) + 기상 경로 이중화(SlumberPower: 피해
기상=Stun으로 다음 턴 행동, 턴 종료 기상=즉시 WakeUpMove; Plating은 기상 시점까지
유지, Phase 6u)**, **피격 반응 훅 AfterDamageReceived(Creature.on_damage_received —
원본에 UnblockedDamage 게이트가 없어 블록에 전부 막힌 피해에도 발동하고 대상이
그 피해로 죽은 경우에만 건너뛴다; PersonalHivePower가 파워드 피격마다 뽑을 더미
무작위 위치에 Dazed를 amount장 삽입, Phase 6v)**, **공격자 결과 훅
on_damage_given(`fully_blocked`는 실제 블록 흡수량 기준이라 Buffer의 HP 손실 0과
구분; ImbalancedPower가 완전 블록 시 일반 몬스터는 다음 턴 기절, BowlbugRock은
DIZZY로 전환) + 무브 callback 중 강제 상태 전환 보존(S1.M3.B18)**.

## 📈 실측 통계 (그리디 정책, 신선한 덱 20시드)

| 인카운터 | 승률 | 티어 |
|----------|------|------|
| slimes_weak, bots_normal, gremlins_weak | 20/20 | EASY |
| raiders/vine_shambler/sewer_clam/jaxfruit/cultists/mawler | 20/20 | MEDIUM |
| chompers_normal | 1/20 | HARD |
| globe_head_normal (HP 148) | 0/20 | HARD |
| knights_elite (3기사, 총 HP 276) | 0/20 | ELITE |

**Phase 6b 이후 런 통계 (그리디, 50시드):** 완주 0% — 평균 도달 층 5.6/7,
사망의 77%가 최종 엘리트(3기사, 총 HP 276). 실험상 **전 카드 업그레이드 튜닝 덱은 7/20 승리**
→ 병목은 카드 풀이 아니라 업그레이드 기회(휴식 2회)와 렐릭/포션 부재.
실제 맵 그래프·렐릭 풀 이식(Phase 6d+)에서 재측정 예정.
**Phase 6c Silent 런 통계 (그리디, 30시드):** 완주 0% — 평균 도달 층 4.8/7 (HP 70으로
Ironclad 5.6보다 낮음), 사망의 57%가 동일한 최종 엘리트 → 병목 동일.
**Phase 6d Defect 런 통계 (그리디, 30시드):** 완주 0% — 평균 도달 층 5.5/7,
사망의 80%가 동일한 최종 엘리트(사망 층 분포 {F3:3, F4:3, F6:24}) → 병목 동일.
그리디 정책이 오브 셋업 가치를 저평가하는 한계 포함 (채널 카드 estimate 미반영).
**Phase 6e Necrobinder 런 통계 (그리디, 30시드):** 완주 0% — 평균 도달 층 6.0/7
(HP 66 시작), 평균 골드 158.7 → 최종 엘리트 병목 동일. 그리디가 Osty 셋업·Doom
누적의 지연 가치를 저평가하는 한계 포함 (즉발 딜/블록만 estimate 반영).
**Phase 6f Regent 런 통계 (그리디, 30시드):** 완주 0% — 평균 도달 층 5.6/7
(HP 75 시작), 평균 골드 155.3 → 최종 엘리트 병목 동일. 그리디가 Stars 축적/Forge
누적의 지연 가치를 저평가하는 한계 포함 (즉발 딜/블록만 estimate 반영, 별 자원
소모 스킬은 즉시 가치가 낮아 후순위로 밀림).

## 🃏 Ironclad 카드 풀 (Phase 6b)

디컴파일 `IroncladCardPool` 90종 중 싱글플레이 85종 전량 이식
(멀티 전용 Blaze/DemonicShield/Midnight/Outrage/Tank 제외).

- **전투 엔진 확장:** X코스트(Whirlwind/Cascade), 자동 플레이(Havoc/Cascade/Stampede/
  Hellraiser/HowlFromBeyond), 비용 수정 파이프라인(FreeAttack/Corruption/Stomp 동적 비용),
  카드 소모 훅(DrumOfBattle), 선천성(Innate), 파워 카드 소멸, OneTwoPunch 2회 발동
- **신규 파워 26종:** DemonForm, FeelNoPain, DarkEmbrace, Rage, FlameBarrier, Juggernaut,
  Rupture, Barricade, NoDraw, TempStrength, Aggression, Colossus, CrimsonMantle, Cruelty,
  Hellraiser, Inferno, Juggling, NoEnergyGain, OneTwoPunch, Pyre, Stampede, Unmovable,
  Vicious, FreeAttack, Corruption, Vigor
- **정합성 수정:** 취약/약화 재적용 시 지속시간 스택 + amount-duration 동기화,
  FlameBarrier를 적 턴 이후 제거(반격 가능), 파워 카드가 버림 더미로 순환하던 문제 제거
- **보상 구조:** 희귀도 가중(C60/U37/R3) 3장 제시 → 가치 휴리스틱 선택 (원본 대응)
- **단순화 표기:** 카드 선택 UI가 필요한 효과(Armaments/Brand/Headbutt/TrueGrit+ 등)는
  무작위 선택으로 대체하고 소스에 `[선택→무작위]` 주석

## 🗡️ Silent 카드 풀 (Phase 6c)

디컴파일 `SilentCardPool` 91종 중 싱글플레이 86종 전량 이식
(멀티 전용 BladeSymphony/Concoct/Fade/Flanking/Sneaky 제외).

- **전투 엔진 확장:** **Sly** 키워드(효과로 버려질 때 무료 자동 플레이 — 턴 종료 버리기는
  미발동, 원본 CardCmd.Discard 대응), **Retain** 키워드(턴 종료 유지), 중앙 버리기 경로
  `discard_card`(MementoMori 카운터/버리기 훅), Shiv 생성 파이프라인
  `create_shivs`(손패 10장 제한, Accuracy 가산/PhantomBlades 첫타 보너스+Retain/
  FanOfKnives 전체 공격화/Inky 인챈트), 드로우 수정 파이프라인(ToolsOfTheTrade/Predator),
  조건부 플레이 훅(GrandFinale), 대상 지정 스킬(needs_target), Burst 스킬 2회 발동,
  FreeSkill 비용 파이프라인(Pounce), Strangle 카드 플레이 트리거
- **신규 파워 26종:** Accelerant, Accuracy, Afterimage, TempDexterity, Blur, Burst,
  CorrosiveWave, Envenom, FanOfKnives, InfiniteBlades, MasterPlanner, Nightmare,
  NoxiousFumes, Outbreak, PhantomBlades, SerpentForm, DoubleDamage, ShadowStep,
  Shadowmeld, Speedster, Strangle, TheHunt, ToolsOfTheTrade, Tracking, WellLaidPlans,
  WraithForm + Intangible/BlockNextTurn/DrawCardsNextTurn/FreeSkill
- **Poison 재작업:** 원본 TriggerCount 로직 — 상대의 Accelerant만큼 추가 발동
- **TheHunt:** 처치 시 combat.extra_card_rewards → 런 루프가 추가 보상 지급
- **전투 한정 키워드 변형 원복:** MasterPlanner Sly/PhantomBlades Retain은 전투 종료 시
  마스터 덱에서 초기화
- **단순화 표기:** 카드 선택 UI 효과(DaggerThrow/Prepared/HandTrick/Nightmare/
  WellLaidPlans/ToolsOfTheTrade)는 무작위 선택 `[선택→무작위]`

## 🔌 Defect 카드 풀 (Phase 6d)

디컴파일 `DefectCardPool` 91종 중 싱글플레이 86종 전량 이식
(멀티 전용 EnergySurge/Hibernate/Ignition/ImitationLearning/OneForAll 제외).
+ Fuel 토큰(Compact 변환물) + Wound/Burn/Void 상태이상 3종.

- **오브 엔진 확장:** OrbQueue 슬롯 상한 10 + `RemoveSlots`(뒤에서부터 오브째 제거,
  원본 OrbCmd 대응 — BulkUp), **EvokeLast**(가장 최근 오브 발동 — ConsumingShadow),
  수동 패시브 발동(대상 지정 — TeslaCoil/Darkness/Loop), 이보크 훅
  `after_orb_evoked`(Thunder), 라이트닝 채널 카운터(Voltaic), TempFocus 합산
  (`_focus()` = focus + temp_focus), 채널 시 슬롯 0·기본 슬롯 0이면 자동 1슬롯 추가/
  Defect는 미추가·가득 차면 선두 이보크(원본 Channel 규칙)
- **신규 파워 22종:** TempFocus, BiasedCognition, Buffer, EnergyNextTurn, Coolant,
  ConsumingShadow, CreativeAI, EchoForm, Feral, Hailstorm, Iteration, LightningRod,
  Loop, MachineLearning, SignalBoost, Smokestack, Spinner, Storm, Subroutine, Thunder,
  TrashToTreasure, FreePower (총 95종)
- **전투 엔진 확장:** **EchoForm/SignalBoost**(턴 첫 N장/다음 파워 2회 발동 —
  플레이 시작 시점 스냅샷으로 자기 자신 미중복), **Feral**(0코스트 공격을 손패로 복귀,
  턴당 상한), FreePower 비용 파이프라인, 전투 한정 비용 변형
  (SetThisCombat/AddThisCombat/SetUntilPlayed — MomentumStrike/Modded/
  AdaptiveStrike/RocketPunch), 카드 생성 훅 `generate_card`(Smokestack/
  TrashToTreasure/RocketPunch — **몬스터 삽입 경로는 미발동**),
  AfterEnergyReset 훅(LightningRod/Spinner/EnergyNextTurn),
  Burn 턴 종료 자해(2)/Void 드로우 시 에너지 -1, HP 손실 수정 파이프라인(Buffer)
- **오브 이보크 정합성:** MultiCast/Quadcast는 선두 오브를 X·4회 발동하되
  마지막에만 dequeue, Shatter는 각 오브를 2회(비제거→제거) 발동
  (전부 원본 `OrbCmd.EvokeNext(dequeue)` 타이밍 그대로)
- **덱 레벨 영구 상태:** Claw 전투 한정 전체 스케일링(`reset_combat_state`),
  GeneticAlgorithm 덱 레벨 영구 블록 성장(런 전체 유지)
- **단순화 표기:** 카드 선택 UI 효과(Hologram/Scavenge)는 무작위 선택 `[선택→무작위]`

## 💀 Necrobinder 카드 풀 (Phase 6e)

디컴파일 `NecrobinderCardPool` 91종 중 싱글플레이 82종 전량 이식
(멀티 전용 Cacophony/GlimpseBeyond/LegionOfBone/Soulbound/Underworld 제외;
스타터 Strike/Defend/Bodyguard/Unleash 기존 구현) + Soul/SweepingGaze 토큰.

- **Osty 소환수 엔진:** DieForYou(살아있는 Osty가 플레이어 겨냥 **파워드 공격**을
  대신 받음 — `Creature.take_damage` 리다이렉트), Summon(생존 시 최대HP+n/사망 시
  부활/부재 시 생성), Osty 공격 카드(CardTag.OstyAttack — Osty가 딜러, 부재 시 무효):
  Poke/Snap/Flatten/Fetch/RightHandHand/Rattle/SicEm/BoneShards/HighFive/Squeeze/
  Protector + 스타터 Unleash. **Calcify**는 Osty 파워드 공격에 +피해(`_deal_attack`),
  **NecroMastery**는 Osty HP 손실을 모든 적에게 관통 반사(`Osty.lose_hp`/`kill`)
- **Doom 엔진:** 적 턴 종료 시 HP ≤ Doom이면 즉사(DoomKill, `_trigger_doom`),
  EndOfDays 즉시 처치, **ReaperForm**(플레이어/Osty가 준 피해=Doom), BlightStrike
  (입힌 피해=Doom), Countdown/Neurosurge 매턴 자동 Doom, NoEscape 누진, Deathbringer/
  Scourge/NegativePulse 직접 부여, **Shroud**(Doom 부여 시 블록)/**DeathsDoor**
  (Doom 부여 턴 3배 블록)/**SleightOfFlesh**(디버프 부여 시 피해) — `apply_power` 훅
- **Ethereal 시너지 엔진:** `ethereal_played_this_combat` 집계 →
  **BansheesCry**(코스트 -2/Ethereal), **PullFromBelow**(타격 수), **SpiritOfAsh**
  (플레이 시 블록), **Pagestorm**(Ethereal 드로우 시 추가 드로우), **Veilpiercer**
  (Ethereal 0코스트), **CallOfTheVoid**(매턴 무작위 카드 Ethereal 부여)
- **신규 파워 25종:** Calcify, CallOfTheVoid, Countdown, DanseMacabre, BorrowedTime,
  Demesne, DevourLife, EnfeeblingTouch, Friendship, Hang, Haunt, Lethality,
  NecroMastery, Neurosurge, Oblivion, Pagestorm, ReaperForm, SentryMode, SicEm,
  SleightOfFlesh, Shroud, SpiritOfAsh, Veilpiercer, SummonNextTurn, Debilitate,
  ForbiddenGrimoire, Doom (총 120종)
- **전투 엔진 확장:** 사망 집계 `deaths_this_combat`(**Melancholy** 코스트 감소),
  카드 플레이 브로드캐스트(**RightHandHand** 버림 더미 회수), **Lethality** 첫 공격
  ×(1+amount/100), **Transfigure** Replay(`_extra_plays`), **Debilitate** 취약
  1.5→2.0/약화 0.75→0.5, `doom_applied_this_turn`, Osty 공격 카운터(**Rattle**/**Flatten**),
  `cards_drawn_this_turn`(**DeathMarch**)
- **Soul 토큰 파이프라인:** 뽑을 더미 무작위 위치/버림/손패 생성(GraveWarden/Reave/
  Severance/CaptureSpirit/Dirge/Seance 변형), **DevourLife**/**Haunt**(Soul 플레이 시 트리거)
- **단순화 표기:** 카드 선택 UI(Snap/SculptingStrike/Dredge/Cleanse 등)는 `[선택→무작위]`,
  ForbiddenGrimoire 전투 종료 보상·Eternal 키워드는 미모델링(마커)
- **적대 검증(8에이전트 배치 대조, 82카드+25파워):** 발견·수정 5건 —
  Oblivion 자기 트리거 Doom 초과, SicEm 자기 공격 소환 오발동(공격→파워 순서 반전),
  PullFromBelow 잘못된 Ethereal화·자기 히트 집계, Eidolon 오소모(원본 비-Exhaust),
  Severance 세 번째 Soul 손실 → 전부 원본 대조 후 수정 + 회귀 테스트 추가

## ⭐ Regent 카드 풀 (Phase 6f)

디컴파일 `RegentCardPool` 90종 중 싱글플레이 82종 전량 이식
(멀티 전용 Constellation/HammerTime/Largesse/Plot 제외;
스타터 Strike/Defend/FallingStar/Venerate 기존 구현) +
SovereignBlade/MinionStrike/MinionDiveBomb/MinionSacrifice/Debris 토큰.

- **Stars 자원 엔진:** 전투/턴 간 지속(플러시 없음), DivineRight(전투 시작 +3),
  별 X코스트(**Stardust** — 전량 소비 후 `star_x_value`), 카드 비용 파워 수정 훅
  `get_card_star_cost`(**VoidForm**)
- **Forge/SovereignBlade 엔진:** `_forge(n)` — 미소모 SovereignBlade가 없으면
  손패에 생성(`combat.generate_card` 경유, 훅 정상 발동), 소모 더미 포함 전체
  블레이드 데미지 +n 누적. **SovereignBlade**(2코스트/업글 1, Retain, 토큰,
  10+Forge 데미지): **Parry**(파워 수치만큼 블록), **SeekingEdge**(전체 공격화),
  **Conqueror**(대상 피해 2배 — `_playing_sovereign_blade` 플래그로 판정),
  **SwordSage**(Replay +n, 신규 생성 블레이드에도 소급 적용)
- **신규 파워 23종:** StarNextTurn, GenesisP, ParryP, SeekingEdgeP, BlackHoleP,
  ChildOfTheStarsP, ConquerorP, MonarchsGazeP, MonologueP, PaleBlueDotP, OrbitP,
  ReflectP, RetainHandP, ForegoneConclusionP, SpectrumShiftP, TyrannyP,
  SealedThroneP, ArsenalP, PillarOfCreationP, RoyaltiesP, SwordSageP, VoidFormP,
  FurnaceP
- **전투 엔진 확장:** `stars_gained_this_turn`(**Radiate**)/`cards_generated_this_combat`
  (**Supermassive**)/`last_star_paid`(**BlackHole**) 카운터, `_hits_taken_this_turn`
  (대상별, **BeatIntoShape**), `end_turn_requested`(**VoidForm** 플레이 시 즉시 턴종료),
  자동 선/후플레이 훅 `on_pre_play_phase`(**Bombardment** 소모 더미 자동 재생)/
  `on_post_play_phase`(**IAmInvincible** 뽑을 더미 맨 위 자동 재생),
  `_settle_card`의 `settle_to`(**ParticleWall** 손패/**ShiningStrike** 뽑을 더미 맨 위),
  `Creature.compute_modified_block`(파워 수정만 계산, 실제 블록 미변경 —
  **Glitterstream** 이월 블록 사전 계산용)
- **Monologue:** 카드 플레이마다 힘 누적(자기 플레이 1회 미발동), 턴 종료 시
  부여한 힘 전부 회수, 재플레이 시 기존 인스턴스에 병합(강도 합산 + 병합 순간
  1회 발동)
- **단순화 표기:** 카드 선택 UI(Begone/Charge/Guards/CosmicIndifference/Glimmer/
  PhotonCut/ForegoneConclusion/DecisionsDecisions/Tyranny)는 무작위 선택
  `[선택→무작위]` (단, Charge는 서로 다른 카드 2장을 보장하도록 비복원 추출).
  Quasar/BundleOfJoy/ManifestAuthority(생성)/SpectrumShift(파워)/HeirloomHammer(복제)의
  Colorless 카드 풀 참조는 Phase 6g에서 `sts2_sim.cards.colorless`로 배선 완료
  (아래 Colorless 섹션 참조)
- **적대 검증(8배치 대조, 87카드):** 발견·수정 5건 — Charge 무작위 선택 시
  동일 카드 중복 선택(서로 다른 2장 보장으로 수정), Glitterstream 이월 블록이
  시전 시점 블록 수정자(Frail 등) 미반영, DecisionsDecisions 자동 재생 루프가
  소모형 스킬에서 조기 중단, **Plating 파워가 피격 기반으로 잘못 감소**(원본은
  소유자 턴 시작마다 감소, 피해와 무관 — Ironclad **StoneArmor**/몬스터
  **SewerClam**도 함께 수정), Guards 제자리 카드 치환이 카드 생성 훅
  (Arsenal/PillarOfCreation/Supermassive) 미발동, MakeItSo 손패 복귀가 손패
  가득 참 상태에서 뽑을더미 카드를 리다이렉트하지 않음 → 전부 원본 대조 후
  수정 + 회귀 테스트 추가. 부수적으로 `Creature.compute_attack_damage`/
  `take_damage`/`gain_block`의 파워 순회 중 자기 제거(**Vigor**)로 인한
  `RuntimeError`도 함께 발견·수정(방어적 `list()` 순회)

## 🎨 Colorless 카드 풀 (Phase 6g)

디컴파일 `ColorlessCardPool` 65종 전량 이식 (Common 등급 없음 — Uncommon 40 /
Rare 25, 원본부터 그러함) + 신규 파워 16종.

- **신규 파워 16종:** AutomationP, BeaconOfHopeP, CalamityP, EntropyP, FastenP,
  KnockdownP, MayhemP, NoBlockP, NostalgiaP, PanacheP, PrepTimeP, RollingBoulderP,
  StratagemP, TagTeamP, TheBombP, TheGambitP
- **"소유 캐릭터 카드풀" 참조 카드** (Calamity/Discovery/Entropy/Jackpot/
  JackOfAllTrades/Splash): `player.character.name` → 캐릭터별 `*_POOL_BY_RARITY`로
  해석하는 헬퍼(`_character_pool_ids`/`_character_attack_ids`/
  `_character_zero_cost_ids`/`_other_character_attack_ids`) 신설. Regent의
  Quasar/BundleOfJoy/ManifestAuthority/SpectrumShift/HeirloomHammer도 여기 배선
- **멀티플레이 전용 카드 12종**(BeaconOfHope/BelieveInYou/Coordinate/GangUp/
  HuddleUp/Intercept/Knockdown/Lift/Mimic/Rally/TagTeam/TheBall)은 원본 목록에
  그대로 포함하되 "다른 플레이어/팀원" 대상 효과만 싱글플레이에 맞게 단순화
  (대상=자기 자신, 또는 발동 조건상 자기 외 대상이 없어 항상 무발동)
- **전투 엔진 확장:** `cards_played_this_combat`(GoldAxe), `_reshuffle`
  (Stratagem — 셔플 후 `after_shuffle` 파워 훅 발동), `auto_play_from_draw_pile`
  (Mayhem), `on_before_hand_draw` 카드 훅(Bolas/ThrummingHatchet 부메랑),
  `on_pre_play_phase` 파워 훅(Mayhem), `settle_to == "draw_random"`(TheBall),
  `_settle_override`/`modify_settle_pile` 파워 훅(Nostalgia — 소모 대신 뽑을 더미
  맨 위로)
- **적대 검증(8배치 대조, 65카드+16파워+엔진 확장분):** 확정 8건 수정 —
  - DarkShackles가 부여하는 TempStrength(음수)가 정적 `is_debuff=False`로
    선언되어 있어 Artifact가 무효화하지 못함 → `is_debuff`를 `amount < 0` 기준
    동적 property로 변경(원본 `TemporaryStrengthPower.Type`이 `IsPositive`에
    따라 Buff/Debuff가 갈리는 것과 대응). Coordinate(양수 적용)는 그대로 Buff 유지
  - Discovery/Calamity/Entropy/Splash가 참조하는 캐릭터 카드풀 헬퍼가 원본
    `CardFactory.FilterForCombat`의 `CanBeGeneratedInCombat` 체크를 하지 않아
    Feed/NotYet/TheHunt/Royalties/Nightmare/Transfigure(캐릭터 풀)와
    HandOfGreed/HiddenGem(Colorless 자체 풀)까지 생성 후보에 포함될 수 있었음
    → `_NOT_GENERATABLE_IN_COMBAT` 제외 목록 신설, 캐릭터 풀 헬퍼 전체 및
    Quasar/BundleOfJoy/SpectrumShift/JackOfAllTrades가 쓰는
    `_COLORLESS_GENERATABLE_IDS`에도 동일 적용
  - HiddenGem 폴백(타입 필터 결과가 비었을 때) 후보 선정에서 "재생 미보유"
    조건이 타입 필터와 함께 사라져 이미 Replay가 걸린 카드에 다시 적용될 수
    있었음 → 재생 미보유 필터와 타입 필터를 2단계로 분리해 폴백에서도 재생
    미보유 조건 유지
  - Entropy가 변환 대상 카드의 강화 상태를 대체 카드에 강제로 이전(원본
    Transform 파이프라인은 업그레이드 상태를 전혀 전달하지 않음) → 제거
  - 전부 원본 대조 후 수정 및 회귀 테스트 추가 (`test_sts2_phase6g.py`)
- **기지 차이로 문서화(수정 보류, ROADMAP.md Phase 6g+ 참조):**
  - **Entropy 대체 카드 풀**: 원본은 변환 대상 "카드 자신이 속한 풀"(Colorless
    카드라면 ColorlessCardPool)에서 대체 카드를 뽑지만, 카드별 소속 풀 조회
    인프라가 없어 항상 "소유 캐릭터 풀"에서 뽑음 — 손패에 소유 캐릭터 외
    카드(Colorless 등)가 섞였을 때만 관측 가능한 차이
- **오탐 판정 1건:** JackOfAllTrades가 MultiplayerOnly 카드 12종을 생성 후보에서
  제외하지 않는 것은 이 프로젝트가 `CardMultiplayerConstraint` 개념 자체를
  구현하지 않기로 한 전역 결정(Phase 6f부터 문서화)의 직접적 귀결 — 별도 버그
  아님

## ✅ Phase 6i — 엔진 아키텍처 확장

Phase 6g 검증에서 발견된 3개 기지 차이를 해소하는 후속 Phase. 5개 캐릭터 전투
엔진 전반에 영향을 주는 변경이라 별도로 분리해 진행:

- **카드 출처(card_source) 블록 파이프라인**: `gain_block`/`compute_modified_block`에
  `card_sourced` 인자 추가(`combat._card_effect_active`로 판정) →
  `NoBlockP.modify_block_card_sourced`가 원본처럼 카드 유래 블록만 차단
- **파워드/언파워드 피해 구분**: `take_damage`에 `powered` 인자 + `on_take_damage_powered`
  훅 추가(기존 `on_take_damage`는 폴백 유지) → `TheGambitP`가 원본 `IsPoweredAttack()`
  게이트를 따라 Unpowered 반사·자해 피해로는 발동하지 않도록 수정. 9개 호출부에
  `powered=False` 배선(Thorns/FlameBarrier/Juggernaut/Inferno/SerpentForm/Speedster/
  Hailstorm/Smokestack/Thunder/Outbreak/Burn)
- **`PowerInstanceType.Instanced` 다중 인스턴스**: `Creature._powers`의 단일 객체
  구조는 유지한 채 TheBomb/RollingBoulder/Automation/Panache 4종에 `self._instances`
  리스트 + `apply()` 오버라이드 패턴 적용 — 재적용 시 병합 대신 독립 인스턴스 추가
- **적대적 검증 재시도에서 추가로 확인된 3건**(1차 시도는 세션 한도로 5/7 에이전트
  실패, 재시도로 전부 성공):
  - `Dexterity`/`Frail`/`TempDexterity`가 원본 `IsPoweredCardOrMonsterMoveBlock()`
    게이트 없이 Plating/FrostOrb/Afterimage/Rage/FeelNoPain/CurlUp 등 Unpowered
    반응형 블록에도 적용되던 것을 `modify_block_powered` 훅으로 수정
    (`on_block_gained`/Juggernaut는 원본처럼 powered 무관 항상 발동 유지)
  - `Unmovable`(자체 문서화된 기지 차이, 원본 `IsCardOrMonsterMove()` 게이트)도
    동일 메커니즘으로 수정
  - `SleightOfFlesh` 반사 피해가 `take_damage()`를 우회(`lose_hp` 직접 호출)해
    블록을 무시하던 것을 수정(원본은 `Unpowered`만 설정, `Unblockable` 아님)
- 회귀 테스트 8종(`test_sts2_phase6g.py`), 13스위트 + 5캐릭터 20시드 stats 전부
  Phase 6h 기준과 완전 동일 (그리디 정책이 해당 엣지 케이스에 도달하지 않음 —
  스택 조합이 실제 플레이에서 드묾)
- **후속: Vulnerable/Colossus/Cruelty/Conqueror `IsPoweredAttack()` 게이트**
  (위 검증 완료 후 같은 회차에 마저 구현, 별도 적대적 검증 1건 추가 실행):
  - `Vulnerable`/`Colossus`/`ConquerorP`의 `modify_incoming`에 `powered` 게이트
    추가 — Unpowered 반사·자해 피해(Thorns/FlameBarrier/Outbreak/Burn/
    NecroMastery/SleightOfFlesh 등)에는 배율 미적용
  - **Strength/Weak(가해 측)는 수정 불필요로 확인 종결**: `compute_attack_damage`
    호출부를 전수 조사한 결과 카드 공격/몬스터 자체 공격만 그 경로를 타고,
    Unpowered 반사 피해는 전부 `take_damage`를 직접 호출해 그 파이프라인을
    우회하므로 애초에 영향이 없음이 확인됨 (앞서 "stats 회귀 가능성" 예측은
    실측 결과 틀림 — 실제로는 20/100시드 모두 완전 동일)
  - **적대적 검증에서 발견한 추가 버그**: `take_damage`의 Cruelty 취약 배율
    증폭이 incoming 수정 루프 종료 후 `pre_incoming`(원본값) 기준으로 별도
    가산되어, 같은 피격에 Intangible의 피해 상한(1로 고정)이 걸려 있어도
    이를 우회하는 문제. 원본 `Hook.ModifyDamageInternal`
    (`decompiled/MegaCrit.Sts2.Core.Hooks/Hook.cs`)이 Additive→Multiplicative→
    Cap 3단계를 엄격히 분리하고 Cap을 항상 최종 적용함을 확인 → Cruelty/
    Debilitate 증폭을 `Vulnerable.modify_incoming` 자체의 배율 계산에 원본과
    동일한 순서(base→Cruelty→Debilitate)로 접어넣고, `Creature.take_damage`의
    incoming 파이프라인을 Multiplicative 패스(`modify_incoming`)와 Cap 패스
    (`modify_damage_cap`, `Intangible`가 구현)로 분리 — 파워 적용 순서(딕셔너리
    삽입 순서)와 무관하게 정확한 결과가 나오도록 구조 수정
  - 회귀 테스트 4종 추가, 13스위트 + 5캐릭터 stats 재확인(20/100시드) — 전부
    기존 수치와 완전 동일

## ✅ Phase 6j — 몬스터 확대 2차 · 배치1

몬스터 잔여 ~87종 이식의 첫 배치(13종). 3개 서브배치(7a/7b/7c)로 나눠
멀티에이전트 파이프라인(이식→검증)으로 진행, 완료 후 나도 직접 디컴파일
원본과 전수 대조.

- **7a** (`monsters_batch7a.py`): FuzzyWurmCrawler, Nibbit, Seapunk,
  TurretOperator, PunchConstruct — 적대적 검증 0건
- **7b** (`monsters_batch7b.py`): DevotedSculptor, KinPriest, Toadpole,
  SludgeSpinner, HauntedShip — 적대적 검증에서 `Ritual` 파워 버그 1건 발견
  (아래 참조)
- **7c** (`monsters_batch7c.py`): Wriggler, Myte, FrogKnight — 헬퍼
  `_FrogKnightHalfHealthBranch`(HP 절반 이하 조건 분기 `RandomBranchState`)
  포함, 적대적 검증 0건
- **신규 상태이상 카드 2종**(`sts2_card.py`): `Infection`(비용0/사용불가,
  손패 보유 중 턴 종료마다 자해 3), `Toxic`(비용1/소모, 사용 시 자해 5)
- **`encounters.py`**: 신규 13개 인카운터 배선(원본 `GenerateMonsters()`
  구성 그대로). `Wriggler`/`KinPriest`는 미이식 소환/보스 의존성
  (PhrogParasite/TheKinBoss)으로 단독 인카운터 없이 보류. 난이도 풀 편입은
  실측 승률 테스트 이후로 의도적 보류(Phase 6a 선례 — ROADMAP.md 참조)
- **버그 수정: `Ritual` 첫 틱 스킵 누락** — 원본 `RitualPower.cs`의
  `WasJustAppliedByEnemy` 플래그(`AfterApplied`가 세우고 `AfterSideTurnEnd`가
  소비 후 스킵)를 직접 대조해 확인. 기존 `_PowerCardTrigger`의 `_skip_next`
  플래그 패턴을 재사용해 `Ritual.apply()`/`on_turn_start()`에 적용 —
  부여된 다음 턴은 힘이 발동하지 않고 그 다음 턴부터 발동하도록 수정.
  `DevotedSculptor`(+9)/`DampCultist`(+5)/`CalcifiedCultist`(+2) 3종에 영향,
  해당 전투 수치가 미세하게(스킵된 한 틱만큼) 변경됨을 `git stash` 전/후
  비교로 확인(다른 Phase와 달리 이번은 의도적 수치 변경)
- 회귀 테스트: 신규 `test_sts2_phase6j.py`(14개) + 기존
  `test_sts2_phase2.py`/`test_sts2_phase4.py`의 Ritual 타이밍 테스트 재작성
  — 14스위트 전체 통과
- **최종 적대적 재검증**(Ritual 수정 엣지 케이스 전담 + encounters.py 배선
  충실도): Ritual 관련 잠재 이슈 3건(재적용/스택 시 스킵 재무장 누락,
  owner.IsEnemy 게이트 부재, on_turn_start vs AfterSideTurnEnd 타이밍
  일반화 우려) 제기 → 전부 "포션 시스템 미이식 + 현재 3개 사용처 모두
  fresh 적용만 발생"으로 실측 도달 불가능함이 확인되어 기각(확정 버그
  0건). encounters.py는 이슈 제기 자체 없음

## ✅ Phase 6k — 몬스터 확대 2차 · 배치8

몬스터 잔여 ~74종의 두 번째 배치(8종, Act1 보스 SoulFysh 포함). 신규 파워 3종
(ShrinkPower/TerritorialPower/SuckPower) + 상태이상 카드 1종(Beckon) 동반.

- **`monsters_batch8.py`**: MysteriousKnight(FlailKnight 상속, 신규 파워
  불필요), Flyconid(취약/허약/공격 3분기, 신규 파워 불필요), ShrinkerBeetle
  (신규 `ShrinkPower`), LouseProgenitor(기존 `CurlUpPower` 재사용 — Phase 6k
  이전에 다른 목적으로 미리 이식돼 있었으나 어떤 몬스터에도 연결 안 된
  상태였음), SpinyToad(가시 토글, 신규 파워 불필요), Byrdonis(엘리트, 신규
  `TerritorialPower`), FossilStalker(신규 `SuckPower`), SoulFysh(Act1 보스,
  신규 상태이상 카드 `Beckon`)
- **`jaxfruit_normal` 원본 구성 복원**: Flyconid 미이식 시절 SnappingJaxfruit
  ×2로 대체해뒀던 것을 원본 구성(`SnappingJaxfruit`+`Flyconid`)으로 교체
- **`encounters.py`**: 신규 8개 인카운터 배선(원본 `GenerateMonsters()`
  구성 그대로 — Weak/Normal/Elite/Boss RoomType은 전투 시뮬레이터가 다루지
  않는 메타 정보라 미모델링, 원본에서도 RoomType/IsWeak은 전투 판정 코드와
  무관함을 확인)

### 적대적 검증 — 확정 버그 10건 (Phase 6j 이후 가장 많은 발견 건수)

Phase 6j와 동일하게 review→verify 워크플로우로 8개 항목(몬스터 7종+파워
조합/보스/인카운터)을 적대 검증했다. 세션 한도로 verify 단계 일부가
실패해("no verdict") 자동 기각 처리된 항목들은 전부 내가 직접 원본
`decompiled/`와 재대조해 별도로 판정했다. 그 결과 확정된 버그는 다음 9건:

1. **Flyconid RAND/INITIAL 분기 가중치 오독** — 원본 `RandomBranchState.cs`를
   직접 읽고 확인: `AddBranch(state, int, MoveRepeatType)` 3-인자 호출의
   두 번째 int 인자는 오버로드 결정 규칙상(C#은 리터럴 0만 enum 암묵 변환
   허용) weight가 아니라 **cooldown**에 바인딩되고, weight는 해당 오버로드
   내부에서 하드코딩된 1f다. 즉 VULNERABLE_SPORES_MOVE/FRAIL_SPORES_MOVE/
   SMASH_MOVE 세 분기의 실제 base weight는 3:2:1이 아니라 균등 1:1:1이며,
   대신 VULNERABLE_SPORES_MOVE는 최근 3무브, FRAIL_SPORES_MOVE는 최근
   2무브 이력에 자신이 없어야 선택 가능한 cooldown 게이트가 걸린다.
   `RandomBranchState`/`MonsterMoveStateMachine`(`sts2_monster.py`)에
   `cooldown`/이력(`history`) 추적을 새로 추가해 재현, 전멸 시(세 분기 모두
   배제) 첫 등록 분기로 폴백하는 원본 동작도 함께 반영
2. **FossilStalker RAND 분기 동일 오독** — 위 발견 직후 같은 파일을 재확인해
   직접 찾음(적대적 검증이 아니라 사후 자체 재검토로 발견). 2-인자
   `AddBranch(state, int)`의 int는 weight가 아니라 **maxRepeats**
   (`MoveRepeatType.CanRepeatXTimes`)로 바인딩됨 — 세 분기 균등 1:1:1이되
   동일 분기 2연속까지 허용, 3연속은 금지. `add_branch`에 `max_repeats`
   파라미터 추가로 재현
3. **SoulFysh 자기부여 Intangible 영구 누적** — 엔진 버그. `combat.py`가
   `on_enemy_turn_end`를 `notify_player_powers`로 플레이어 파워에만
   통지해, 몬스터가 스스로에게 건 파워(Intangible 등)는 절대 감소하지
   않았다. SoulFysh의 FADE_MOVE(5턴 순환마다 1회)가 반복될 때마다
   Intangible이 2→4→6...으로 누적되어 약 4번째 자기 턴 이후 사실상
   무적이 되고 보스전이 불가능해짐(재현: GreedyPolicy로 실행 시 플레이어가
   7턴째 사망). `combat.py`의 몬스터 턴 루프 끝에 `alive_enemies`에도
   동일 통지를 추가해 수정
4. **FossilStalker Suck 파워 조기 반영** — `LASH_MOVE`(2연타) 안에서 첫
   히트로 얻은 힘이 즉시 두 번째 히트 데미지 계산에 반영되어 총딜 9(원본은
   6)가 나오는 버그. 원본 `AttackCommand.Execute()`는 다단히트를 전부
   처리한 뒤 `AfterAttack`을 1회만 호출하므로 힘 부여는 해당 무브의 모든
   히트가 끝난 뒤에만 일어난다 — `SuckPower`에 `on_landed_attack`(카운트만)
   /`flush_landed_attacks`(무브 종료 시 일괄 적용) 분리, `MonsterModel.
   take_turn`이 무브 실행 직후 flush를 통지하도록 엔진 확장
5. **LouseProgenitor 블록 획득 powered 플래그 반전** — `CURL_AND_GROW_MOVE`의
   블록 14는 원본이 `ValueProp.Move`(파워드)인데 포트는 `powered=False`로
   구현해 Frail 배율 우회(코드베이스 전체에서 유일한 사례) — `powered=True`
   (기본값)로 수정
6. **Thorns/FlameBarrier/CurlUpPower의 IsPoweredAttack 게이트 누락** —
   SpinyToad 가시 토글 검증 중 발견. 원본은 셋 다 `IsPoweredAttack()`이
   아니면(오브/파워 반응형 Unpowered 피해) 반격/블록 획득을 하지 않는데,
   포트는 `on_take_damage`(게이트 없음)로 구현되어 있었음 — 이미 존재하던
   `on_take_damage_powered(attacker, hp_lost, powered)` 훅으로 교체해 세
   파워 모두 게이트 추가 (SpinyToad 고유 결함이 아니라 반격형 파워 공통
   이식 누락)
7. **SoulFysh Beckon 뽑을더미 삽입이 "무작위"가 아니라 "다음 드로우 확정"**
   — `add_status_to_player_draw`가 `draw_pile.append`를 썼는데, 이 엔진의
   `draw_cards`/`auto_play_from_draw_pile`은 전부 `draw_pile.pop()`(같은
   쪽 끝)으로 뽑으므로 append는 사실 "다음 드로우 확정"(엔진 자체가
   `_settle_card`에서 이 연산을 `draw_top`이라 명명)이지 무작위 위치가
   아니었다. 원본 `CardPilePosition.Random`에 맞춰 `combat.py`에
   `draw_random`(무작위 인덱스 `insert`, 기존 TheBall 카드의 방식과 동일
   패턴) 모드를 추가하고 `add_status_to_draw`가 이를 쓰도록 수정
8. **Beckon의 Unblockable 자해가 Intangible Cap 우회** — `lose_hp` 직접
   호출은 블록 우회(Unblockable)는 맞게 구현했지만 `take_damage`의 Cap
   단계(Intangible의 무조건 1 제한)를 완전히 건너뛰어, 플레이어가
   Intangible을 보유한 채 Beckon 자해를 맞아도 6 피해가 그대로 들어갔다 —
   `Creature.take_damage`에 `unblockable` 인자를 추가해(블록만 우회, Cap은
   유지) `Beckon.on_turn_end_in_hand`가 이를 쓰도록 수정
9. **(부수 발견, 관련 파워 3종에 걸친 시스템적 이슈) outgoing 데미지
   파이프라인 Additive/Multiplicative 미분리** — 원본 `Hook.
   ModifyDamageInternal`(디컴파일 `Hook.cs`)은 Additive(Strength/Vigor/
   TempStrength) 단계를 전부 적용한 뒤 Multiplicative(Weak/Shrink/
   DoubleDamage) 단계를 적용하는 두 단계로 엄격히 분리한다. 포트의
   `compute_attack_damage`는 파워 딕셔너리 삽입 순서대로 한 루프에서
   섞어 처리해, Shrink를 먼저 걸고 나중에 힘을 얻는 통상 순서와 그
   반대 순서의 최종 데미지가 달라지는 문제가 있었다(이미 있던 Weak도
   동일하게 노출되던 이슈, ShrinkPower 검증 중 발견) — `compute_attack_
   damage`를 `damage_stage`(additive/multiplicative) 기준 2단계로 분리해
   `Creature.take_damage`의 기존 Multiplicative→Cap 분리 패턴과 대칭을
   맞춤
10. **(advisor 리뷰 지적으로 발견, 선행 버그) FlailKnight/TwigSlimeM 분기
    가중치 오독** — 1·2번과 동일한 `AddBranch` 오버로드 오독 패턴이 Phase 6a
    때 이식된 `FlailKnight`(`FLAIL_MOVE`/`RAM_MOVE` 가중치 각 2로 오독)와
    `TwigSlimeM`(`POKEY_POUNCE_MOVE` 가중치 2로 오독)에도 있었음을 사후
    검토(체크리스트: "같은 실수를 다른 곳에서도 하지 않았는지 감사하라")로
    발견. `add_branch(...weight=[2-9])` 전수 grep 후 각 원본 `.cs`와
    재대조해 확정 — 두 몬스터 모두 실제로는 균등 분기(1:1:1 / 1:1) +
    `CanRepeatXTimes(2)`다. `MysteriousKnight`가 `FlailKnight`의 무브그래프를
    그대로 상속하므로 Phase 6k 표면에도 걸쳐 있던 버그. 수정 후
    EASY/MEDIUM/HARD/ELITE_POOL 전체(5캐릭터×40~60시드)에서 승률/평균턴
    변화 없음을 실측 확인(구조적으로 올바른 수정이되 현재 시뮬레이터의
    관측 가능한 밸런스에는 영향 없음)

기각된 항목(현재 코드베이스에서 도달 불가능하거나 연출 전용으로 확인):
인카운터 8종 배선 전수 대조 0건, jaxfruit_normal 배치 확인 0건,
MysteriousKnight의 super()/decimal 변환 관련 4건(전부 죽은 코드 경로),
ShrinkPower의 applier 사망 시 제거(단독 인카운터라 관측 불가), Byrdonis의
applier 인자 누락(무해), FossilStalker의 펫 제외/그룹핑 로직(펫 시스템
자체가 없어 무해), SoulFysh의 targets 순회 생략/GAZE_MOVE Intent 표시
누락/Vulnerable applier 누락(전부 단일플레이어 엔진에서 무관측), LouseProgenitor
의 Curled 플래그 미이식(연출 전용, 재확인 완료).

- 회귀 테스트: 신규 `test_sts2_phase6k.py`(21개) — 위 10건 버그 전부 재발
  방지 테스트 포함(Flyconid 균등가중치+쿨다운+폴백, FossilStalker 3연속
  금지, LouseProgenitor Frail-블록, SoulFysh Intangible 감쇠, Beckon+
  Intangible Cap, Thorns Unpowered 무반격, FlailKnight/TwigSlimeM 가중치
  감사 등), 15스위트 전체 통과

## ✅ Phase 6l — 몬스터 확대 2차 · Act1 완결

Act1(Underdocks) 미이식분 5종 + 신규 파워 5종. 엘리트 3종과 Act1 보스
LagavulinMatriarch 포함.

- **`monsters_batch9.py`**: CorpseSlug(신규 `RavenousPower`), SkulkingColony
  (엘리트, 신규 `HardenedShellPower`), TerrorEel(엘리트, 신규 `ShriekPower`),
  PhantasmalGardener(엘리트, 슬롯별 시작 무브), LagavulinMatriarch(보스,
  신규 `AsleepPower`/`SkittishPower`)
- **엔진 확장**: `ConditionalBranchState`(조건 순차 평가 분기 — 가중치/RNG
  없이 등록 순서대로 첫 True 분기 선택), `force_current_state`(HP·피격
  반응형 강제 전환), `MonsterModel.stun`(1턴 무행동 후 지정 무브 복귀),
  `Creature.slot_name`, `on_any_death` 전역 브로드캐스트
- **Plating 개전 즉시 블록 버그 수정**: 원본 `BeforeSideTurnStart(round1)`이
  라운드 1 플레이어 턴 시작 "전"에 블록을 지급 — 개전 Plating 보유 몬스터가
  플레이어의 첫 공격을 그냥 맞던 문제

## ✅ Phase 6m — Waterfall Giant 보스

사망 인터셉트/부활 구조가 필요해 6l에서 분리한 보스 1종.

- **`monsters_batch10.py`**: WaterfallGiant(HP 240) — 고정 6무브 순환,
  PRESSURE_GUN이 발동마다 20→25→30 성장, 모든 무브가 Steam 누적
- **`SteamEruptionPower`**: 소유자의 첫 사망을 가로채 HP를 복구하고
  ABOUT_TO_BLOW로 강제 전환 → 다음 턴 누적 Steam만큼 폭발 후 최종 사망.
  `persists_after_owner_death`로 사망 시 파워 일괄 제거에서 제외
- **`should_disappear_from_doom`**: Steam 보유 중 Doom 즉사 무효화

## ✅ Phase 6n — 몬스터 확대 2차 · 배치11

몬스터 9종 + 신규 파워 6종 + 인카운터 11종 (`MONSTER_REGISTRY` 70종).

- **`monsters_batch11.py`**: SlimedBerserker(신규 파워 불필요),
  SlitheringStrangler(`ConstrictPower`), Exoskeleton(`HardToKillPower`,
  슬롯별 시작 무브), HunterKiller(`TenderPower`), MechaKnight(엘리트,
  개전 Artifact 3 + 화상 4장을 **손패**로), BygoneEffigy(엘리트, `SlowPower`),
  Inklet(`SlipperyPower`), ScrollOfBiting(`PaperCutsPower`),
  Vantom(보스, HP 173 + 개전 `SlipperyPower` 8 + `ShouldDisappearFromDoom=false`)
- **신규 파워 6종**: Constrict / HardToKill / Tender / Slow / Slippery / PaperCuts
  (전부 Phase 6k 정찰에서 "미이식 파워"로 식별됐던 항목)

### 엔진 확장 3건 + 버그 수정 3건

1. **`Creature.lose_max_hp` 신설** — 원본 `CreatureCmd.LoseMaxHp`는 새 최대
   HP가 현재 HP보다 낮으면 그 초과분을 `Unblockable|Unpowered` **피해로**
   처리한 뒤 최대 HP를 `max(1, ...)`로 설정한다. 현재 HP를 직접 클램프하면
   `hp_lost_this_turn`/`times_hp_lost` 집계와 `on_hp_lost` 훅이 누락되고,
   최대 HP 전량 손실 시 원본은 사망하는데 이쪽은 HP 1로 생존하는 차이가 생김
2. **`on_landed_attack` 훅에 피격 대상 전달** — 원본 `AfterDamageGiven`이
   target을 받으므로 PaperCuts의 "플레이어를 맞혔을 때만" 조건 구현에 필요.
   호출부(`MonsterModel.attack`)와 기존 유일 소비자 `SuckPower`를 동반 수정
3. **`CombatState.notify_card_played` 신설** — 원본 `AfterCardPlayed`는 파워
   소유자의 편과 무관하게 전투 내 모든 파워에 통지된다. 기존
   `notify_player_powers`만으로는 몬스터가 스스로에게 건 `SlowPower`
   (BygoneEffigy)가 플레이어의 카드 플레이를 영원히 세지 못함 — Phase 6k에서
   같은 계열로 발견된 `on_enemy_turn_end` 누락 버그와 동일 패턴
4. **`resolve_initial` 분기 체인 미해석 버그** — 초기 상태 분기가 다시 분기를
   가리키는 경우(Exoskeleton INIT_MOVE의 fourth 슬롯 → RAND) 한 단계만 풀려
   브랜치 노드가 현재 상태로 남고 `execute_move`에서 터졌다. `advance_state`가
   이미 쓰던 while 루프 방식으로 통일해 수정
5. **손패 상한 초과 생성 카드 소실 버그** — `generate_card(to="hand")`가 손패
   10장일 때 카드를 어느 파일에도 넣지 않고 그대로 버렸다. 원본
   `CardPileCmd.Add`는 `isFullHandAdd`이면 대상 파일을 버림 더미로 바꾼다
   (CardPileCmd.cs:469-473). MechaKnight FLAMETHROWER(화상 4장)에서 실제로
   발현 — 개별 호출자가 아니라 공유 경로인 `generate_card`에서 고쳐
   기존 손패 삽입 호출자(`monsters_batch7c.py`)도 함께 교정했다.
   이 항목은 리뷰가 "원본을 읽지 않고 쓴 주석"을 지적한 데서 출발했다 —
   주석의 주장 자체는 맞았지만 검증 과정에서 이식 불일치가 드러난 사례
6. **`test_sts2_phase6.py` Plating 기대값 갱신** — Phase 6l의 개전 즉시 지급
   변경(정당한 동작 수정)을 낡은 6a 테스트가 따라가지 못해 실패하던 상태.
   실제 코드가 원본과 일치함을 확인하고 테스트 쪽을 현행 사양으로 갱신

### 이식 시 확인한 원본 세부 (오독하기 쉬운 지점)

- **`AddBranch` 오버로드**(Phase 6k와 동일 함정): HunterKiller RAND의 `2`와
  ScrollOfBiting rand의 `2`는 weight가 아니라 **maxRepeats**. 두 몬스터 모두
  분기 base weight는 균등 1:1
- **ExoskeletonsWeak는 슬롯이 3개**("first"/"second"/"third")뿐이라 fourth
  슬롯의 RAND 시작 개체가 나오지 않는다
- **ScrollsOfBitingNormal의 4번째 개체**는 `StarterMoveIdx = 2` **고정**이며
  앞 3마리처럼 `(num+i)%3` 회전이 아니다
- **SlitheringStranglerNormal의 소형 슬라임 2마리**는 각각 독립 추첨이라
  같은 종이 두 번 나올 수 있다(기존 `slimes_weak`의 셔플 방식과 다름)
- **MechaKnight 화상은 `PileType.Hand`** — 버림 더미가 아니라 손패로 직접 삽입
- **Inklet의 `INIT_RAND`**는 생성만 되고 상태 목록·초기 상태 어디에도 쓰이지
  않는 사문화 코드라 이식하지 않음. **BygoneEffigy의 `SLEEP_MOVE_2`**는 어떤
  무브도 진입하지 않지만 상태 목록에는 있어 원본 구성 그대로 보존

## ✅ Phase 6o~6q — 전투 중 소환 계열

Phase 6l 헤더부터 세 번 미뤄온 "전투 도중 몬스터 추가" 구조를 열고, 그에
막혀 있던 몬스터 3종을 이식했다.

### 엔진 (6o)

- **`CombatState.add_monster(monster, slot_name)`** — 원본 `CreatureCmd.Add`.
  전투 rng를 물려주고 `setup_for_combat`으로 초기화. `_combat_over` 플래그로
  종료 후 소환을 차단한다 (원본 `IsLiveCombat` 가드)
- **`_combat_is_won`에 `ShouldStopCombatFromEnding` 대응** — 해당 파워가
  남아 있으면 적이 전멸해 보여도 승리로 치지 않는다
- **`reap_deaths` 순회 안전성** — 사망 훅이 소환하면 `self.monsters`가 순회
  중 변경돼 터졌다. 스냅샷 순회로 수정

### 엔진 (6p)

- **인카운터 슬롯 목록 + `next_free_slot`** — 원본 `EncounterModel.Slots` /
  `GetNextSlot`. 생존한 적이 차지하지 않은 첫 칸을 반환하므로, 죽은 몬스터의
  슬롯은 다시 채워질 수 있다 (TwoTailedRat이 실제로 그렇게 동작한다)
- **`RandomBranchState` 확장 2건**:
  * `weight`에 callable 허용 — 원본 `Func<float>` 가중치 오버로드. 가중치가
    0이면 후보에서 제외되는 것까지 원본과 동일
  * `use_only_once` — `MoveRepeatType.UseOnlyOnce`

### 콘텐츠

- **PhrogParasite(엘리트, 6o)**: INFECT(감염 3장) ↔ LASH(4딜×4). 개전
  `InfestedPower(4)` — 사망 시 Wriggler 4마리가 wriggler1~4 슬롯에 스턴
  상태로 소환된다 (홀수 슬롯 NASTY_BITE / 짝수 WRIGGLE)
- **TwoTailedRat(6p)**: CanSummon 4조건 전부 이식 — 2턴 지연(무브 수행마다
  감소), 전투 3회 상한(같은 편이 카운터 공유), 빈 슬롯 존재, 동료의 중복
  소환 예약 방지. 소환 가능해지면 분기 가중치가 공격 1/12 · 소환 0.75로 바뀐다
- **GremlinMerc(6q)**: 무브마다 골드 20 절취(보유량 상한), 사망 시
  SneakyGremlin·FatGremlin 소환 + 훔친 골드를 FatGremlin에게 이관.
  잡으면 환수, 도주하면 손실 — 원본 `CalculateGoldProportion`의 핵심 결과와 동일

### 원본 소환 파워의 공통 이식 판단

원본 `InfestedPower`/`SurprisePower`는 `ShouldStopCombatFromEnding()=true`를
유지한 채 파워를 제거하지 않는다. 원본은 사망 훅이 비동기라 소환이 끝날
때까지 승리 판정을 미루는 용도지만, 이 엔진은 사망 훅이 동기라 소환이 이미
끝난 상태다 — 그대로 두면 승리가 영구히 차단되므로 **소환 직후 파워가
스스로를 제거**하도록 했다. 관측 가능한 결과(소환 전 승리 오판 방지)는 동일하다.

## 🔬 생성 방법론 (Phase 6a/6j/6k)

몬스터는 멀티에이전트 파이프라인으로 이식:
1. **이식 에이전트** — 디컴파일 .cs와 기존 패턴을 읽고 Python 클래스 생성
2. **검증 에이전트** — 원본과 수치/상태그래프 적대 대조 (Phase 6a: LeafSlimeS
   시드 재현성 버그, SpectralKnight CanRepeatXTimes 전개 오류 / Phase 6j:
   Ritual 첫 틱 스킵 누락 / Phase 6k: 위 9건, 특히 `RandomBranchState`의
   `AddBranch` 오버로드 오독이 서로 다른 두 몬스터(Flyconid/FossilStalker)
   에서 각기 다른 형태로 재발한 것이 인상적 — C# 오버로드 결정 규칙을
   추론이 아니라 실제 원본 클래스 정의를 직접 읽어 확정해야 함을 재확인)
3. **수동 대조** — 세션 한도로 미검증된 항목("no verdict") 또는 전체를
   원본 소스와 직접 재대조 (Phase 6j는 13종 전부 재대조, 3건의 자체 테스트
   저작 버그도 근본 원인 분석으로 수정 / Phase 6k는 세션 한도로 verify
   단계 절반 가량이 실패했으나 자동 기각으로 넘기지 않고 review 단계의
   원본 findings를 전부 다시 읽어 하나씩 재검증 — 그 결과 confirmed 5건
   외에 추가로 4건을 더 확정했다)

## 🚀 다음 단계

ROADMAP.md의 **`S1.M3.B19 — 후속 구현 배치 19`** 참조 — 몬스터
잔여 16종. ROADMAP에 몬스터별 필요 파워 표(디컴파일 스캔 결과)를 실어
두었으니 재조사 없이 그대로 쓸 것.
그 밖에 렐릭 297종 풀, 포션 64종, 이벤트 59종, 실제 맵 그래프, Ascension.

**원본 대비 이식률** (디컴파일 `Models.*`의 `: XxxModel` 파생 클래스 기준):
전투 코어(카드·파워·몬스터·인카운터·오브) **845/1051 ≈ 80%**,
런 콘텐츠(렐릭·포션·이벤트) **22/420 ≈ 5%**. 클래스 수로 드러나지 않는
공백으로 `core/run.py`의 축소된 런 루프(고정 층 시퀀스, 맵 그래프·상점·
이벤트 방 없음)가 있다.
