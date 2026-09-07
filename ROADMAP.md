# STS2 Simulator Roadmap

Slay the Spire 2 헤드리스 Python 시뮬레이터.
**`sts2.dll` 디컴파일 코드(`decompiled/MegaCrit.Sts2.Core.*`)를 유일한 근거 자료로 삼아** 실제 STS2 게임 데이터를 이식한다.
(이전의 STS1 기반 추정 구현은 전부 제거됨.)

**현재 위치: `S1.M3.B22 — TheAdversary Mk1~Mk3` 완료** — 카드 507종 /
파워 188종 / 몬스터 94종 / 인카운터 70종 / 렐릭 22종 / 오브 5종,
루트 회귀 31스위트 전체 통과.

## 작업 단위와 ID 규약

새 작업은 **Stage → Milestone → Batch** 계층으로 관리한다.

| 단위 | ID | 정의 | 완료 조건 |
|---|---|---|---|
| Stage | `S<n>` | 제품 생애주기의 최상위 목표 | 소속 Milestone을 모두 닫고 제품 수준의 종료 조건을 충족 |
| Milestone | `S<n>.M<n>` | Stage 안의 검증 가능한 기능·커버리지 게이트 | 정해진 능력과 커버리지를 회귀 검증으로 입증 |
| Batch | `S<n>.M<n>.B<n>` | 한 번의 구현·리뷰·회귀 검증으로 닫는 전달 단위 | 원본 대조, 해당 최소 회귀, 루트 전체 회귀 통과 |

- ID에는 한국어 제목을 함께 쓴다(예: `S1.M3.B18 — 몬스터·인카운터 배치 18`).
- 번호는 각 상위 단위 안에서 단조 증가시키며 완료된 ID를 재사용하거나 재번호화하지 않는다.
- 새 회귀 파일은 점을 underscore로 바꾼 `test_sts2_s1_m3_b18.py` 형식을 쓴다.
  기존 `test_sts2_phase*.py`와 역사적 Phase 제목은 호환성과 이력 보존을 위해 바꾸지 않는다.
- 런타임 콘텐츠 모듈은 일정 ID와 분리해 기존 계보(`monsters_batch18.py`)를 잇는다.

### 제품 Stage와 현재 S1 Milestone

| ID | 이름 | 범위 및 종료 조건 |
|---|---|---|
| `S1` | 시뮬레이터 | 전체 런에 필요한 게임 시스템을 충실하고 시드 재현 가능하게 시뮬레이션 |
| `S1.M1` | 시뮬레이터 기반 | 전투 모델, 캐릭터, 카드·파워·오브의 기초 모델 완성 |
| `S1.M2` | 실행·평가 루프 | 전투·축소 런 루프와 재현 가능한 baseline 정책·통계 실행 완성 |
| `S1.M3` | 원본 충실도·콘텐츠 완성 | 원본 대조 기반 전투·런 시스템과 필수 콘텐츠를 전체 런 범위까지 확장 |
| `S2` | 클리어 AI | 완성된 시뮬레이터에서 클리어 정책을 구축하고 재현 가능한 평가로 입증 |
| `S3` | 라이브 모드 | 검증된 AI를 실제 게임에 통합하고 라이브 동작을 검증 |

### 기존 Phase 대응표

| 역사적 이름 | 새 체계 | 비고 |
|---|---|---|
| Phase 1~3 | `S1.M1 시뮬레이터 기반` | 코어 모델, 실제 캐릭터, Orb |
| Phase 4~5 | `S1.M2 실행·평가 루프` | Phase 5 정책은 S2 AI가 아닌 시뮬레이터 검증용 baseline |
| Phase 6a~6v | `S1.M3 원본 충실도·콘텐츠 완성` | 카드 풀, 엔진 훅, 몬스터·인카운터 확대 |

Phase 6의 몬스터 모듈 계보는 `6j=B07a~B07c`, `6k=B08`, `6l=B09`,
`6m=B10`, `6n=B11`, `6o~6q=B12` 기능·콘텐츠 조각, `6r~6v=B13~B17`이다.
이 계보를 이어 다음 작업부터 새 ID를 적용한다.

원본(디컴파일 `Models.*`의 `: XxxModel` 파생 클래스) 대비 이식률:

| 영역 | 이식 / 원본 | 비율 |
|---|---|---|
| 카드 | 503 / 593 | 85% |
| 파워 | 184 / 248 | 74% |
| 몬스터 | 91 / 117 | 78% |
| 인카운터 | 69 / 88 | 78% |
| 오브 | 5 / 5 | 100% |
| **전투 코어 소계** | **852 / 1051** | **81%** |
| 렐릭 | 22 / 297 | 7% |
| 포션 | 0 / 64 | 0% |
| 이벤트 | 0 / 59 | 0% |
| **런 콘텐츠 소계** | **22 / 420** | **5%** |

전투 자체는 약 81%까지 왔고 런 레벨 콘텐츠가 비어 있다. 클래스 수로는
드러나지 않는 구조적 공백이 하나 더 있다 — `core/run.py`가 실제 맵 그래프
없이 고정 층 시퀀스로 돌고 상점·이벤트 방이 없다.

다음은 [`S1.M3.B20 — 후속 구현 배치 20`](#-s1m3b20--후속-구현-배치-20-계획).

---

## ✅ Phase 1~2 — 코어 시스템 (완료)

- [x] `MonsterModel` — 상태 머신 기반 몬스터 (디컴파일 `MonsterMoveStateMachine` 이식)
- [x] `STS2Power` / `STS2Card` / `STS2Relic` 베이스 + 팩토리
- [x] `Creature` — 공유 데미지 파이프라인 (Strength→Weak→Vulnerable, 블록, 피격 트리거)

## ✅ Phase 3 — 실제 캐릭터 로스터 & Orb 시스템 (완료)

- [x] 실제 STS2 로스터: **Ironclad, Silent, Defect, Necrobinder, Regent** (Watcher 없음)
  - Silent 12장 덱 (Neutralize/Survivor), Defect Zap/Dualcast + CrackedCore + 오브 슬롯 3
  - Necrobinder: **Osty 소환수** / Regent: **Stars 자원**
- [x] Orb 5종 (Lightning/Frost/Dark/Plasma/**Glass**) + OrbQueue + Focus
- [x] 스타터 카드 14종 / 스타터 렐릭 5종 (디컴파일 수치 그대로)

## ✅ Phase 4 — 전투 루프 & 런 시스템 (완료)

- [x] `CombatState` 턴 루프 (에너지/드로우/카드/오브 트리거/파워 틱/에테리얼)
- [x] `Player` 전투 엔티티, 몬스터 = Creature 통합
- [x] `RandomBranchState` (가중치 분기 + CannotRepeat + UseOnlyOnce + 초기 분기 시드 해석)
- [x] 상태이상 삽입 (Dazed/Slimed), Artifact, 도주, Ritual 스케일링
- [x] 런 루프: 층 진행, 카드 보상, 휴식(회복/업그레이드), HP 이월

## ✅ Phase 5 — AI & 분석 (완료)

- [x] `GreedyPolicy` — 막타 → 공격/방어 에너지당 가치 비교 → 취약 셋업 보너스
- [x] 예상 피해 계산 (인텐트 + 힘/약화/취약)
- [x] 통계 러너: `python3 -m sts2_sim.core.stats <char> <n> [--policy greedy|simple]`
- [x] 시드 완전 재현성

## ✅ Phase 6a — 몬스터 확대 1차 (완료)

- [x] 신규 17종 이식 (총 **34종**) — 멀티에이전트 이식→적대검증 파이프라인 + 수동 대조
- [x] 실제 인카운터 구성 12종 (SlimesWeak 3마리 구성, KnightsElite 3기사, 레이더 3/5 등)
- [x] Plating 파워, Tangled/Shackled 카드 차단 배선

## ✅ Phase 6b — Ironclad 카드 풀 (완료)

- [x] **Ironclad 카드 풀 완전 이식**: `IroncladCardPool` 90종 중 싱글플레이 85종
  (멀티 전용 Blaze/DemonicShield/Midnight/Outrage/Tank 5종 제외) + GiantRock 토큰
- [x] 카드 파워 26종 신규 배선 (DemonForm/Juggernaut/Corruption/Hellraiser/Inferno 등, 총 43종)
- [x] 전투 엔진 확장: X코스트(Whirlwind/Cascade), 자동 플레이(Havoc/Stampede/Hellraiser),
  비용 수정 파이프라인(FreeAttack/Corruption/Stomp), 소모 훅(DrumOfBattle/HowlFromBeyond),
  선천성(Innate), 전체 공격, 파워 카드 소멸 처리
- [x] 취약/약화 지속시간-수치 동기화 + 재적용 스택 수정
- [x] 보상 시스템: 희귀도 가중(60/37/3) 3장 제시 → 휴리스틱 선택 (원본 보상 구조)
- [x] GreedyPolicy 확장: 카드 자체 추정치 프로토콜(damage/block_estimate), 파워 우선 설치

## ✅ Phase 6c — Silent 카드 풀 (완료)

- [x] **Silent 카드 풀 완전 이식**: `SilentCardPool` 91종 중 싱글플레이 86종
  (멀티 전용 BladeSymphony/Concoct/Fade/Flanking/Sneaky 5종 제외)
- [x] 카드 파워 26종 신규 배선 (Envenom/NoxiousFumes/Outbreak/Accelerant/
  PhantomBlades/Intangible/Burst/Nightmare 등, 총 73종)
- [x] 전투 엔진 확장: **Sly**(버리기 시 자동 플레이), **Retain**(턴 종료 유지),
  버리기 훅(`discard_card`/MementoMori 카운터), Shiv 생성 파이프라인
  (Accuracy/PhantomBlades/FanOfKnives/Inky 연동), 드로우 수정 파이프라인
  (ToolsOfTheTrade/Predator), 조건부 플레이(GrandFinale), 대상 지정 스킬
- [x] Poison 재작업: Accelerant 다중 발동 (원본 TriggerCount 로직)
- [x] TheHunt 처치 → 런 루프 추가 카드 보상 배선

## ✅ Phase 6d — Defect 카드 풀 (완료)

- [x] **Defect 카드 풀 완전 이식**: `DefectCardPool` 91종 중 싱글플레이 86종
  (멀티 전용 EnergySurge/Hibernate/Ignition/ImitationLearning/OneForAll 5종 제외)
  + Fuel 토큰(Compact 변환물) + Wound/Burn/Void 상태이상
- [x] 카드 파워 22종 신규 배선 (EchoForm/Feral/Buffer/Storm/Subroutine/
  Thunder/Loop/CreativeAI/TempFocus 등, 총 95종)
- [x] 오브 엔진 확장: 슬롯 상한 10 + RemoveSlots(뒤에서부터 오브째 제거,
  원본 OrbCmd), **EvokeLast**(ConsumingShadow), 수동 패시브 발동(대상 지정 —
  TeslaCoil/Darkness/Loop), 이보크 훅 `after_orb_evoked`(Thunder),
  채널 카운터(Voltaic), TempFocus 합산
- [x] 전투 엔진 확장: **EchoForm**(턴 첫 N장 2회 발동, 플레이 시작 시점 스냅샷),
  **SignalBoost**(파워 2회), **Feral**(0코스트 공격 손패 복귀), FreePower 비용
  파이프라인, 전투 한정 비용 변형(SetThisCombat/AddThisCombat/SetUntilPlayed —
  MomentumStrike/Modded/AdaptiveStrike/RocketPunch), 카드 생성 훅
  `generate_card`(Smokestack/TrashToTreasure/RocketPunch — 몬스터 삽입 미발동),
  AfterEnergyReset 훅(LightningRod/Spinner/EnergyNextTurn),
  Burn 턴 종료 자해 / Void 드로우 에너지 손실, HP 손실 수정 파이프라인(Buffer)
- [x] Claw 전투 한정 전체 스케일링 / GeneticAlgorithm 덱 레벨 영구 블록 성장
- [x] 멀티에이전트 적대 검증 (9에이전트로 82카드+22파워를 디컴파일 원본과 배치 대조):
  FeralPower 적용 시점 카운터 초기화 누락(원본 AfterApplied) 발견 → 수정,
  Feral IsDupe 예외는 dupe 생성원(Duplication Potion 등) 미구현이라 관측 불가로 기록.
  나머지 전 항목 일치. 오브 이보크 6종(MultiCast/Quadcast/Shatter/Voltaic/Barrage/Tempest)은 수동 재대조.

## ✅ Phase 6e — Necrobinder 카드 풀 (완료)

- [x] **Necrobinder 카드 풀 완전 이식**: `NecrobinderCardPool` 91종 중 싱글플레이 82종
  (멀티 전용 5종 제외: Cacophony/GlimpseBeyond/LegionOfBone/Soulbound/Underworld;
  스타터 4종 Strike/Defend/Bodyguard/Unleash는 기존 구현) + Soul/SweepingGaze 토큰
- [x] 카드 파워 25종 신규 배선 (Calcify/CallOfTheVoid/Countdown/DanseMacabre/
  BorrowedTime/Demesne/DevourLife/EnfeeblingTouch/Friendship/Hang/Haunt/Lethality/
  NecroMastery/Neurosurge/Oblivion/Pagestorm/ReaperForm/SentryMode/SicEm/
  SleightOfFlesh/Shroud/SpiritOfAsh/Veilpiercer/SummonNextTurn/Debilitate 등)
- [x] **Osty 소환수 엔진**: DieForYou(살아있는 Osty가 플레이어 겨냥 파워드 공격 대신 받음),
  Osty 공격 카드 12종(Poke/Snap/Flatten/Fetch/RightHandHand/Rattle/SicEm/BoneShards/
  HighFive/Squeeze/Protector + 스타터 Unleash — Osty가 딜러, Calcify 보너스),
  NecroMastery 반사(Osty HP 손실 → 모든 적 관통), Sacrifice/BoneShards Osty 제물
- [x] **Doom 엔진**: 적 턴 종료 시 HP ≤ Doom 즉사(DoomKill), EndOfDays 즉시 처치,
  ReaperForm(준 피해만큼 Doom), BlightStrike(입힌 피해=Doom), Countdown/Neurosurge
  매턴 자동 Doom, NoEscape 누진 Doom, Shroud(Doom 부여 시 블록)
- [x] **Ethereal 시너지 엔진**: 전투 내 Ethereal 플레이 집계(BansheesCry 코스트 감소/
  PullFromBelow 타격 수), SpiritOfAsh(블록)/Pagestorm(추가 드로우)/Veilpiercer(0코스트)
- [x] 전투 엔진 확장: 사망 집계(Melancholy 코스트 감소), 카드 플레이 브로드캐스트
  (RightHandHand 회수), Lethality 첫 공격 배수, Transfigure Replay(_extra_plays),
  Debilitate 취약/약화 배수 강화, Doom 부여 집계(DeathsDoor), Osty 공격 카운터(Rattle/Flatten)
- [x] Soul 토큰 생성 파이프라인(뽑을 더미 무작위/버림/손패), DevourLife/Haunt(Soul 플레이 트리거)
- [x] 멀티에이전트 적대 검증 (8에이전트로 82카드+25파워를 디컴파일 원본과 배치 대조).
  발견·수정: Oblivion 자기 트리거 Doom 초과 부여, SicEm 자기 공격 소환 오발동,
  PullFromBelow 잘못된 Ethereal화·자기 집계, Eidolon 오소모, Severance Soul 소실 —
  전부 원본 대조 후 수정 및 회귀 테스트 추가

## ✅ Phase 6f — Regent 카드 풀 (완료)

- [x] **Regent 카드 풀 완전 이식**: `RegentCardPool` 90종 중 싱글플레이 82종
  (멀티 전용 4종 제외: Constellation/HammerTime/Largesse/Plot;
  스타터 4종 Strike/Defend/FallingStar/Venerate는 기존 구현) +
  SovereignBlade/MinionStrike/MinionDiveBomb/MinionSacrifice/Debris 토큰
- [x] 카드 파워 23종 신규 배선 (StarNextTurn/GenesisP/ParryP/SeekingEdgeP/BlackHoleP/
  ChildOfTheStarsP/ConquerorP/MonarchsGazeP/MonologueP/PaleBlueDotP/OrbitP/ReflectP/
  RetainHandP/ForegoneConclusionP/SpectrumShiftP/TyrannyP/SealedThroneP/ArsenalP/
  PillarOfCreationP/RoyaltiesP/SwordSageP/VoidFormP/FurnaceP)
- [x] **Stars 자원 엔진**: 별 획득/소모(턴 간 지속, DivineRight 전투 시작 +3),
  별 X코스트(Stardust — 전량 소비), 카드 비용 파워 수정 훅(VoidForm)
- [x] **Forge/SovereignBlade 엔진**: Forge(n) — 미소모 블레이드 없으면 손패 생성,
  소모 더미 포함 전체 블레이드 데미지 누적; SovereignBlade(Parry 블록/SeekingEdge
  전체화/Conqueror 2배/SwordSage Replay 연동)
- [x] Replay 엔진 재사용(SwordSage — combat._extra_plays), 카드 생성 파이프라인 훅
  재사용(Arsenal/PillarOfCreation/Supermassive 카운터)
- [x] 자동 플레이 훅 확장: on_pre_play_phase(Bombardment 소모 더미 자동 선플레이),
  on_post_play_phase(IAmInvincible 뽑을 더미 맨 위 자동 후플레이)
- [x] 멀티에이전트 적대 검증 (8배치로 87카드를 디컴파일 원본과 대조).
  발견·수정: Charge 무작위 선택 시 동일 카드 중복 선택 가능(서로 다른 2장 보장으로 수정),
  Glitterstream 이월 블록이 시전 시점 블록 수정자(Frail 등) 미반영,
  DecisionsDecisions 자동 재생 루프가 소모형 스킬에서 조기 중단(3회 미만 재생),
  Plating 파워가 피격 기반으로 감소(원본은 소유자 턴 시작마다 감소, 피해와 무관 —
  Ironclad StoneArmor/몬스터 SewerClam도 함께 수정), Guards 제자리 카드 치환이
  카드 생성 훅(Arsenal/PillarOfCreation/Supermassive) 미발동, MakeItSo 손패 복귀가
  손패 가득 참 상태에서 뽑을더미 카드를 리다이렉트하지 않음 —
  전부 원본 대조 후 수정 및 회귀 테스트 추가. 부수적으로 `compute_attack_damage`/
  `take_damage`/`gain_block`의 파워 순회가 콜백 중 자기 제거(Vigor)로 인해
  `RuntimeError`를 일으키는 기존 버그도 함께 발견·수정(list() 방어 순회)

## ✅ Phase 6g — Colorless 카드 풀 (완료)

- [x] **Colorless 카드 풀 완전 이식**: `ColorlessCardPool` 65종 전량(Common 등급 없음
  — Uncommon 40 / Rare 25, 원본 그대로) + 신규 파워 16종(Automation/BeaconOfHope/
  Calamity/Entropy/Fasten/Knockdown/Mayhem/NoBlock/Nostalgia/Panache/PrepTime/
  RollingBoulder/Stratagem/TagTeam/TheBomb/TheGambit)
- [x] Regent 5개 카드/파워의 미이식 Colorless 생성 로직 배선 완료: Quasar(3장 중
  1장 무작위)/BundleOfJoy(서로 다른 3장)/ManifestAuthority(7블록+1장)/
  HeirloomHammer(손패 Colorless 카드 복제)/SpectrumShift(매 드로우 전 amount장 생성)
- [x] "소유 캐릭터 카드풀" 참조 카드(Calamity/Discovery/Entropy/Jackpot/
  JackOfAllTrades/Splash) — `player.character.name` → 캐릭터별 `*_POOL_BY_RARITY`
  해석 헬퍼(`_character_pool_ids` 등) 신설
- [x] 전투 엔진 확장: `_reshuffle`(Stratagem), `auto_play_from_draw_pile`(Mayhem),
  `on_before_hand_draw` 카드 훅(Bolas/ThrummingHatchet 부메랑), `on_pre_play_phase`
  파워 훅, `settle_to == "draw_random"`(TheBall), `_settle_override`/
  `modify_settle_pile`(Nostalgia), `cards_played_this_combat`(GoldAxe)
- [x] 멀티에이전트 적대 검증 (8배치로 65카드+16파워+전투엔진 확장분을 디컴파일 원본과 대조).
  확정 8건 수정: DarkShackles가 부여하는 TempStrength(음수)가 항상 `is_debuff=False`로
  취급되어 Artifact가 무효화하지 못함(→ `is_debuff`를 `amount<0` 동적 property로 변경,
  Coordinate의 양수 케이스는 그대로 Buff 유지), Discovery/Calamity/Entropy/Splash가
  참조하는 캐릭터 카드풀 헬퍼가 `CanBeGeneratedInCombat=false` 카드(Feed/NotYet/
  TheHunt/Royalties/Nightmare/Transfigure/HandOfGreed/HiddenGem)를 걸러내지 않음
  (→ `_NOT_GENERATABLE_IN_COMBAT` 제외 목록 신설, Quasar/BundleOfJoy/SpectrumShift/
  JackOfAllTrades의 Colorless 생성 경로에도 동일 적용), HiddenGem 폴백 후보 선정 시
  "재생 미보유" 조건이 타입 필터와 함께 사라져 이미 Replay가 걸린 카드에 중복 적용
  가능(→ 2단계 필터로 분리), Entropy가 변환 대상 카드의 강화 상태를 대체 카드에
  강제로 이전(원본 Transform 파이프라인은 업그레이드를 전달하지 않음 → 제거) —
  전부 원본 대조 후 수정 및 회귀 테스트 추가
- [x] **기지 차이로 문서화(수정 보류)**: NoBlockPower의 "카드 유래 블록만 차단"
  (`cardSource == null` 예외 — Metallicize/오브/렐릭성 블록은 면제)은 `gain_block`/
  `compute_modified_block` 파이프라인에 카드 출처 인자가 없어 미구현;
  TheGambitPower의 "파워드 공격만 즉사 트리거"(`IsPoweredAttack()` — Thorns/
  FlameBarrier 반사 피해는 Unpowered라 면제)는 `take_damage`에 파워드/언파워드
  구분 인자가 없어 미구현; `PowerInstanceType.Instanced`(TheBomb/RollingBoulder/
  Automation/Panache 등 — 재적용 시 병합이 아닌 독립 인스턴스 추가) 미구현
  (`Creature._powers`가 power_id당 단일 인스턴스만 보관하는 구조적 한계);
  Entropy의 대체 카드 풀이 "변환 대상 카드 자신의 소속 풀"이 아닌 "소유 캐릭터
  풀"이라 손패에 Colorless 카드가 섞였을 때만 다르게 동작(카드별 소속 풀 조회
  인프라 부재). 넷 다 5개 캐릭터 전투 엔진 전반에 걸친 아키텍처 변경이 필요해
  이번 포팅 범위에서는 보류 — `IMPLEMENTATION_STATUS.md` 참조
- [x] JackOfAllTrades가 MultiplayerOnly 카드 12종을 생성 후보에서 제외하지 않는
  것은 검증에서 오탐(기지 단순화)으로 판정: 이 프로젝트는 CardMultiplayerConstraint
  개념 자체를 구현하지 않기로 한 프로젝트 전역 결정(Phase 6f부터 문서화됨)의
  직접적 귀결이며 JackOfAllTrades만의 누락이 아님

## ✅ Phase 6h — `--verbose` 모드 (완료)

- [x] `CombatState.verbose`/`CombatState.log` — 턴 시작(플레이어 HP/블록/에너지 +
  적 인텐트), 카드 플레이(이름/대상/코스트 + 결과 HP/블록), 자동 플레이(Sly/
  Hellraiser/Mayhem 등), 몬스터 턴 행동 결과, 전투 종료(승패)를 로그로 남김.
  `verbose=False`(기본값)면 `_log()`가 즉시 반환해 완전 무비용
- [x] `RunState.play(..., verbose=False)` — 층별 요약 로그(기존 `combat_log`,
  Phase 4부터 존재)에 턴/카드 상세 로그를 끼워 넣음
- [x] `stats.run_stats(..., verbose=False)` / CLI `--verbose` 플래그 —
  `python3 -m sts2_sim.core.stats <char> <n> --policy greedy --verbose`.
  로그 폭주 방지를 위해 처음 `VERBOSE_RUN_CAP`(5)개 런만 전체 로그 출력,
  이후 런은 한 줄 요약(승패/층/HP/골드)만 출력
- [x] 회귀 테스트 추가(`test_sts2_phase5.py`): verbose on/off 시 결과(승패/층/HP)가
  동일함을 확인, verbose=False는 턴 단위 로그가 전혀 남지 않음을 확인

## ✅ Phase 6i — 엔진 아키텍처 확장 (완료)

Phase 6g 검증에서 발견된 3개 기지 차이(NoBlockPower/TheGambitPower/Instanced 파워)를
후속 Phase로 분리해 구현. 5개 캐릭터 전투 엔진 전반에 영향을 주는 변경이라 별도
아키텍처 확장으로 취급.

- [x] **카드 출처(card_source) 블록 파이프라인**: `Creature.gain_block`/
  `compute_modified_block`에 `card_sourced` 인자 추가 — `combat._card_effect_active`
  (카드 자신의 `use()` 실행 구간에서만 True)로 판정. `NoBlockP.modify_block_card_sourced`
  구현으로 카드 유래 블록만 차단(원본 `cardSource == null` 면제, Metallicize/Plating
  등 파워 유래 블록은 계속 통과)
- [x] **파워드/언파워드 피해 구분**: `Creature.take_damage`에 `powered` 인자 추가,
  `on_take_damage_powered(attacker, hp_lost, powered)` 훅(기존 `on_take_damage`는
  폴백으로 유지) — `TheGambitP`가 원본 `IsPoweredAttack()`(Move && !Unpowered)
  게이트를 따라 Thorns/FlameBarrier/Outbreak/Burn/오브 반응형 등 Unpowered 반사·자해
  피해로는 발동하지 않도록 수정. 9개 호출부에 `powered=False` 배선
- [x] **`PowerInstanceType.Instanced` 다중 인스턴스**: `Creature._powers`의
  power_id당 단일 객체 구조는 유지한 채, TheBomb/RollingBoulder/Automation/Panache
  4종 각각 `self._instances` 리스트 + `apply()` 오버라이드로 재적용 시 병합 대신
  독립 인스턴스를 추가하도록 구현(`self.amount`는 인스턴스 합으로 하위 호환 유지)
- [x] **적대적 검증 재시도(1차 세션 한도로 5/7 에이전트 실패 → 재시도 성공)**에서
  신규 확인 3건 추가 수정:
  - `Dexterity`/`Frail`/`TempDexterity`: 원본 `IsPoweredCardOrMonsterMoveBlock()`
    (Move && !Unpowered) 게이트 누락 — Plating/FrostOrb/Afterimage/Rage/FeelNoPain/
    CurlUp 등 Unpowered 반응형 블록에도 잘못 적용되던 것을 `modify_block_powered`
    훅으로 수정. `on_block_gained`(Juggernaut)는 원본처럼 powered 무관 항상 발동 유지
  - `Unmovable`(원본 `IsCardOrMonsterMove()` 게이트, 자체 문서화된 기지 차이)도
    동일 메커니즘으로 함께 수정
  - `SleightOfFlesh` 반사 피해가 `take_damage()`를 우회(`lose_hp` 직접 호출)해
    블록을 무시하고 잘못된 훅 경로를 타던 것을 수정(원본 `ValueProp.Unpowered`만
    설정, `Unblockable` 아님 — 블록으로 막혀야 함)
- [x] 회귀 테스트 8종 추가(`test_sts2_phase6g.py`), 13스위트 전체 + 5캐릭터
  20시드 stats 회귀 확인 — 모든 수치 Phase 6h 기준과 완전 동일(그리디 정책이
  해당 엣지 케이스 조합에 도달하지 않음)
- [x] **후속: Vulnerable/Colossus/Cruelty/Conqueror `IsPoweredAttack()` 게이트**
  (위 검증에서 발견, 같은 회차에 마저 구현):
  - `Vulnerable.modify_incoming`/`Colossus.modify_incoming`/`ConquerorP.modify_incoming`에
    `powered` 게이트 추가 — Unpowered 반사·자해 피해에는 적용 안 됨
  - **Strength/Weak(가해 측)는 수정 불필요로 확인 종결**: `compute_attack_damage`는
    카드 공격(`_deal_attack`)과 몬스터 자체 공격에서만 호출되고, Thorns/FlameBarrier
    등 Unpowered 반사 피해는 전부 그 파이프라인을 우회해 `take_damage`를 직접
    호출하므로 애초에 Strength/Weak가 적용될 경로가 없음 — 그대로 둠
  - **Cruelty 증폭 파이프라인 재구성**: `take_damage`의 Cruelty 증폭이 incoming
    루프 종료 후 `pre_incoming`(수정 전 원본값) 기준으로 별도 가산되어 Intangible의
    피해 상한(Cap)을 우회하는 버그를 발견·수정. 원본 `Hook.ModifyDamageInternal`이
    Additive→Multiplicative→Cap 3단계를 엄격히 분리하고(`decompiled/
    MegaCrit.Sts2.Core.Hooks/Hook.cs`) Cap은 항상 최종 단계에 적용됨을 확인 →
    Cruelty/Debilitate 증폭을 `Vulnerable.modify_incoming` 자체의 배율 계산에
    접어넣고(원본과 동일 순서: base→Cruelty→Debilitate), `Creature.take_damage`의
    incoming 파이프라인을 Multiplicative 패스(`modify_incoming`) → Cap 패스
    (`modify_damage_cap`, `Intangible`가 구현)로 분리 — 파워 적용 순서(딕셔너리
    삽입 순서)와 무관하게 항상 정확한 결과가 나오도록 구조 수정
  - 회귀 테스트 4종 추가, 13스위트 + 5캐릭터 stats 재확인 — 이번에도 완전 동일
    (Intangible+Vulnerable+Cruelty 동시 보유는 그리디 정책이 도달하지 않는 조합)

## ✅ Phase 6j — 몬스터 확대 2차 · 배치1 (완료)

몬스터 잔여 ~87종 이식의 첫 배치. 13종 + 관련 인카운터 13종 + 상태이상 카드 2종.

- [x] **7a**: FuzzyWurmCrawler, Nibbit, Seapunk, TurretOperator, PunchConstruct
- [x] **7b**: DevotedSculptor, KinPriest, Toadpole, SludgeSpinner, HauntedShip
- [x] **7c**: Wriggler, Myte, FrogKnight (+ 헬퍼 `_FrogKnightHalfHealthBranch`,
  HP 절반 이하 시점을 조건 분기하는 `RandomBranchState` 서브클래스)
- [x] **신규 상태이상 카드 2종** (`sts2_card.py`): `Infection`(비용0/사용불가,
  손패 보유 중 턴 종료마다 자해 3), `Toxic`(비용1/소모, 사용 시 자해 5) —
  원본 `Infection.cs`/`Toxic.cs` 그대로
- [x] **`encounters.py` 배선**: 13개 신규 `ENCOUNTERS` 항목 추가(원본
  `GenerateMonsters()` 구성 그대로). `Wriggler`/`KinPriest`는 각각 미이식
  소환/보스 의존성(PhrogParasite/TheKinBoss)이 있어 단독 인카운터 없이 보류.
  난이도 풀(EASY/MEDIUM/HARD/ELITE) 편입은 Phase 6a 방식대로 실측 승률
  테스트 이후로 의도적 보류 — 현재는 `make_encounter()`로만 접근 가능
- [x] **버그 발견 및 수정: `Ritual` 파워 첫 틱 스킵 누락** — 적대적 검증(7b
  리뷰)에서 발견 후 원본 `RitualPower.cs`의 `WasJustAppliedByEnemy` 플래그를
  직접 대조해 확인. 원본은 `AfterApplied`가 적을 표시하고 `AfterSideTurnEnd`가
  그 표시를 소비하며 스킵하므로, **부여된 바로 그 턴 다음 턴은 힘이 발동하지
  않고 그 다음 턴부터 발동**한다. 포팅본은 즉시 발동시키고 있었음 — 기존
  `_PowerCardTrigger`의 `_skip_next` 플래그 패턴을 재사용해 `Ritual.apply()`/
  `on_turn_start()`에 동일 메커니즘 적용. `DevotedSculptor`(+9)/`DampCultist`
  (+5)/`CalcifiedCultist`(+2) 3종 전부에 영향 — 해당 몬스터를 낀 전투는
  수치가 미세하게(스킵된 한 틱만큼) 약해짐. `git stash`로 격리한 전/후
  stats 비교로 차이가 작고 방향이 올바름을 확인(다른 모든 Phase와 달리
  이번은 의도적으로 수치가 바뀌는 버그 수정)
- [x] 회귀 테스트 신규 스위트(`test_sts2_phase6j.py`, 14개 테스트: 등록/
  인카운터/HP범위/상태머신 분기/상태이상 삽입/Ritual 스킵 등) + 기존
  `test_sts2_phase2.py`/`test_sts2_phase4.py`의 Ritual 관련 테스트를 새
  타이밍에 맞게 재작성 — 14스위트 전체 통과
- [x] **최종 적대적 재검증**(Ritual 수정 엣지 케이스 + encounters.py 배선
  충실도 전담): Ritual 관련 잠재 이슈 3건 제기 → 전부 검증 단계에서
  "현재 코드베이스에서 도달 불가능한 데드 코드 경로"로 반박·기각(포션
  시스템 미이식으로 플레이어측 Ritual 보유 경로 없음, 3개 사용처 전부
  fresh 적용만 발생해 재적용/스택 케이스 없음) — 확정 버그 0건.
  encounters.py 배선은 이슈 제기 자체 없음(0건)

## ✅ Phase 6k — 몬스터 확대 2차 · 배치8 (완료)

몬스터 잔여 ~74종의 두 번째 배치. 8종 + 관련 인카운터 8종 + 신규 파워 3종 +
상태이상 카드 1종. Act1 보스 SoulFysh 포함.

- [x] **배치8**: MysteriousKnight(FlailKnight 상속, 개전 힘+6/도금+6),
  Flyconid(취약/허약/공격 3분기, 신규 파워 불필요), ShrinkerBeetle(신규
  `ShrinkPower`), LouseProgenitor(기존 `CurlUpPower` 재사용), SpinyToad(가시
  토글, 신규 파워 불필요), Byrdonis(엘리트, 신규 `TerritorialPower` —
  자기 턴마다 힘 누적), FossilStalker(신규 `SuckPower` — 파워드 공격 적중
  시 힘 획득), SoulFysh(Act1 보스, 신규 상태이상 카드 `Beckon`)
- [x] **`jaxfruit_normal` 원본 구성 복원**: Flyconid 미이식 시절 SnappingJaxfruit
  ×2로 대체해뒀던 것을 원본(`SnappingJaxfruit`+`Flyconid`)으로 교체
- [x] **`encounters.py` 배선**: 8개 신규 `ENCOUNTERS` 항목(원본 `RoomType`별
  Weak/Normal/Elite/Boss 구성 그대로 — RoomType 자체는 전투 시뮬레이터
  범위 밖이라 미모델링)
- [x] **적대적 검증 + 사후 감사에서 발견한 버그 10건 확정 수정**:
  1. **Flyconid RAND/INITIAL 분기 가중치 오독** — 원본 `RandomBranchState.cs`의
     `AddBranch(state, int, MoveRepeatType)` 3-인자 오버로드는 int가 weight가
     아니라 **cooldown**으로 바인딩됨(오버로드 결정은 C# 인자 타입으로 확정적).
     세 분기 모두 실제 base weight는 균등 1:1:1이며, VULNERABLE_SPORES_MOVE는
     최근 3무브, FRAIL_SPORES_MOVE는 최근 2무브 이력에 자신이 없어야 선택
     가능(cooldown 게이트). 엔진에 `cooldown`/`max_repeats`/이력(history) 추적을
     새로 추가해 재현 (`RandomBranchState`/`MonsterMoveStateMachine`)
  2. **FossilStalker RAND 분기 동일 오독** — 2-인자 `AddBranch(state, int)`의
     int는 weight가 아니라 **maxRepeats**(`MoveRepeatType.CanRepeatXTimes`)로
     바인딩됨. 세 분기 균등 1:1:1이되 동일 분기 2연속까지는 허용, 3연속은
     금지 — 위 엔진 확장의 `max_repeats` 파라미터로 재현(적대적 검증
     이후 원본 재대조 중 직접 발견)
  3. **SoulFysh 자기부여 Intangible 영구 누적** — `combat.py`가 `on_enemy_turn_end`를
     플레이어 파워에만 통지해 몬스터가 스스로에게 건 파워는 절대 감소하지
     않던 엔진 버그. FADE_MOVE마다 Intangible이 계속 쌓여 보스전이 사실상
     불가능해짐 — 몬스터 파워에도 동일 통지를 추가해 수정
  4. **FossilStalker Suck 파워 조기 반영** — `LASH_MOVE`(2연타) 안에서 첫 히트로
     얻은 힘이 즉시 두 번째 히트 데미지에 반영되어 총딜 9(원본은 6). 원본은
     공격 커맨드 전체가 끝난 뒤 착지 횟수만큼 한 번에 힘을 부여 — 히트 시점엔
     카운트만 하고 무브 종료 시(`take_turn`) 일괄 적용하도록 `SuckPower`에
     `flush_landed_attacks` 추가
  5. **LouseProgenitor 블록 획득 powered 플래그 반전** — `CURL_AND_GROW_MOVE`의
     블록 14는 원본이 `ValueProp.Move`(파워드)인데 `powered=False`로 잘못
     구현되어 Frail 배율을 우회하고 있었음 — `powered=True`(기본값)로 수정
  6. **Thorns/FlameBarrier/CurlUpPower의 IsPoweredAttack 게이트 누락** —
     SpinyToad의 가시 토글 검증 중 발견. 세 반격형 파워 모두 Unpowered
     피해(오브/파워 반응형)에도 반격하던 것을 `on_take_damage_powered` 훅으로
     교체해 게이트 추가 (SpinyToad 고유 결함이 아니라 공통 이식 누락)
  7. **SoulFysh Beckon 뽑을더미 삽입이 "무작위 위치"가 아니라 "다음 드로우
     확정"이었던 문제** — `draw_pile.append`가 무작위 위치 삽입이 아니라
     사실상 맨 위(다음 드로우 확정)였음. 원본 `CardPilePosition.Random`에
     맞춰 `combat.py`에 `draw_random`(무작위 인덱스 삽입) 모드 추가
  8. **Beckon의 Unblockable 자해가 Intangible Cap을 우회** — `lose_hp` 직접
     호출이 블록뿐 아니라 Intangible의 무조건 1 제한(Cap 단계)까지 건너뛰고
     있었음 — `take_damage`에 `unblockable` 인자를 추가해 Cap 파이프라인은
     유지한 채 블록만 우회하도록 수정
  9. **(부수 발견) outgoing 데미지 파이프라인 Additive/Multiplicative 미분리** —
     Strength(Additive)와 Weak/Shrink/DoubleDamage(Multiplicative)가 파워
     딕셔너리 삽입 순서대로 한 루프에서 섞여 처리되어, Shrink를 먼저 걸고
     나중에 힘을 얻는 통상적인 순서와 그 반대 순서의 결과가 달라지던 버그
     (원본 `Hook.ModifyDamageInternal`은 Additive→Multiplicative 순서를 엄격히
     분리) — `compute_attack_damage`를 2단계로 분리해 순서 불변성 확보
  10. **(사후 감사로 발견, 선행 버그) FlailKnight/TwigSlimeM 분기 가중치
      오독** — 위 1·2번과 완전히 동일한 `AddBranch` 오버로드 오독 패턴이
      Phase 6a에서 이미 이식된 `FlailKnight`(`FLAIL_MOVE`/`RAM_MOVE`
      가중치 각 2로 오독, 실제론 균등 1:1:1 + `CanRepeatXTimes(2)`)와
      `TwigSlimeM`(`POKEY_POUNCE_MOVE` 가중치 2, 실제론 균등 1:1 +
      `CanRepeatXTimes(2)`)에도 있었음을 리뷰(advisor) 지적으로
      `add_branch(...weight=[2-9])` 전수 감사 후 발견해 수정.
      `MysteriousKnight`가 `FlailKnight`의 무브그래프를 그대로 상속하므로
      Phase 6k 표면에도 걸쳐 있던 버그. 수정 후 EASY/MEDIUM/HARD/ELITE_POOL
      전체(5캐릭터 × 40~60시드)에서 승률/평균턴 변화 없음을 실측 확인
- [x] 회귀 테스트 신규 스위트(`test_sts2_phase6k.py`, 21개 테스트) — 위 10건
  버그 전부 재발 방지 테스트 포함, 15스위트 전체 통과

## ✅ Phase 6l — 몬스터 확대 2차 · Act1 완결 (완료)

Act1(Underdocks) 미이식분 5종 + 신규 파워 5종 + 엔진 확장.

- [x] **배치9**: CorpseSlug(신규 `RavenousPower` — 동료 사망 시 스턴 후 힘 획득,
  인카운터가 개체별 시작 무브를 다르게 배정), SkulkingColony(엘리트, 신규
  `HardenedShellPower` — 자기 한 턴 HP 손실 총합 제한), TerrorEel(엘리트, 신규
  `ShriekPower` — HP 임계 도달 시 강제 무브 전환), PhantasmalGardener(엘리트,
  슬롯별 시작 무브 — 신규 `ConditionalBranchState`), LagavulinMatriarch(보스,
  신규 `AsleepPower`/`SkittishPower`)
- [x] **엔진 확장**: `ConditionalBranchState`(조건 순차 평가 분기),
  `force_current_state`(HP·피격 반응형 강제 전환), `MonsterModel.stun`,
  `Creature.slot_name`, `combat.reap_deaths`의 `on_any_death` 전역 브로드캐스트
- [x] **Plating 개전 즉시 블록 지급 버그 수정** — 원본 `BeforeSideTurnStart(round1)`이
  라운드 1 플레이어 턴 시작 "전"에 블록을 지급하므로, 개전 시 Plating을 받는
  몬스터는 플레이어의 첫 공격부터 블록으로 막아야 함
- [x] 회귀 테스트 신규 스위트(`test_sts2_phase6l.py`) + 인카운터 6종 등록

## ✅ Phase 6m — Waterfall Giant 보스 (완료)

사망 인터셉트/부활 구조가 필요해 6l에서 분리했던 보스 1종.

- [x] **배치10**: WaterfallGiant(HP 240) — 고정 6무브 순환, PRESSURE_GUN이
  발동마다 20→25→30으로 성장, 모든 무브가 Steam을 누적
- [x] **신규 `SteamEruptionPower`**: 소유자의 첫 사망을 가로채 최대/현재 HP를
  복구하고 ABOUT_TO_BLOW 상태로 강제 전환 → 다음 턴 누적 Steam만큼 폭발 후
  최종 사망. `persists_after_owner_death` 플래그로 사망 시 파워 일괄 제거에서 제외
- [x] **`should_disappear_from_doom` 게이트**: Steam 보유 중에는 Doom 즉사가
  이 보스를 제거하지 못함
- [x] 회귀 테스트 신규 스위트(`test_sts2_phase6m.py`) — 2단계 사망 lifecycle,
  플레이어 턴 종료 사망의 조기 승리 방지 포함

## ✅ Phase 6n — 몬스터 확대 2차 · 배치11 (완료)

몬스터 9종 + 신규 파워 6종 + 인카운터 11종 (`MONSTER_REGISTRY` 70종).

- [x] **배치11**: SlimedBerserker(고정 4순환, 신규 파워 불필요),
  SlitheringStrangler(신규 `ConstrictPower`), Exoskeleton(신규
  `HardToKillPower`, 슬롯별 시작 무브), HunterKiller(신규 `TenderPower`),
  MechaKnight(엘리트, 개전 Artifact 3 + 화상 4장을 **손패**로),
  BygoneEffigy(엘리트, 신규 `SlowPower`), Inklet(신규 `SlipperyPower`),
  ScrollOfBiting(신규 `PaperCutsPower`), Vantom(보스, HP 173 + 개전
  Slippery 8 + `ShouldDisappearFromDoom=false` — Doom 즉사 면역)
- [x] **신규 파워 6종**: Constrict(보유자 턴 종료마다 자해, 블록 적용,
  applier 사망 시 제거) / HardToKill(Cap 단계 피해 상한) / Tender(카드
  플레이마다 힘·민첩 -1, 자신 턴 종료 시 전량 복구) / Slow(이번 턴 카드
  1장당 받는 파워드 피해 +10%) / Slippery(HP 손실 1 제한 + 관통 시 스택 감소) /
  PaperCuts(관통 히트마다 플레이어 최대 HP 감소)
- [x] **엔진 확장 3건**:
  1. `Creature.lose_max_hp` — 원본 `CreatureCmd.LoseMaxHp`대로 현재 HP 초과분을
     `Unblockable|Unpowered` 피해로 처리(손실 집계/`on_hp_lost` 훅 보존)한 뒤
     최대 HP를 최소 1로 설정. 현재 HP를 직접 깎으면 최대 HP 전량 손실 시
     사망하지 않는 차이가 생김
  2. `on_landed_attack` 훅에 피격 대상 전달 — 원본 `AfterDamageGiven`이 target을
     받으므로 PaperCuts의 "플레이어를 맞혔을 때만" 조건에 필요 (`SuckPower` 동반 수정)
  3. `CombatState.notify_card_played` — 원본 `AfterCardPlayed`는 소유자 편과
     무관하게 통지되므로 몬스터 파워에도 전달. 없으면 BygoneEffigy의 SlowPower가
     영원히 누적되지 않음 (6k의 `on_enemy_turn_end` 누락과 동일 계열 버그)
- [x] **`resolve_initial` 버그 수정**: 초기 상태 분기가 다시 분기를 가리킬 때
  (Exoskeleton fourth 슬롯 → RAND) 한 단계만 해석돼 브랜치 노드가 현재 상태로
  남아 `execute_move`에서 터지던 문제 — `advance_state`와 동일한 반복 해석으로 수정
- [x] **손패 상한 초과 생성 카드 소실 버그 수정**: `generate_card(to="hand")`가
  손패 10장일 때 카드를 어느 파일에도 넣지 않고 버려, MechaKnight
  FLAMETHROWER(화상 4장)처럼 한 번에 여러 장을 손패로 넣는 무브에서 카드가
  사라졌다. 원본 `CardPileCmd.Add`의 `isFullHandAdd` 분기(targetPile = Discard)대로
  버림 더미로 돌리도록 공유 경로에서 수정 — 기존 손패 삽입 호출자도 함께 교정
- [x] **`test_sts2_phase6.py` Plating 기대값 갱신**: Phase 6l의 개전 즉시 지급
  변경을 낡은 6a 테스트가 따라가지 못해 실패하던 기존 이슈 해소
- [x] 회귀 테스트 신규 스위트(`test_sts2_phase6n.py`, 24개 테스트) — 루트 18스위트 전체 통과

## ✅ Phase 6o — 전투 중 소환 엔진 (완료)

Phase 6l부터 세 번 미뤄온 "전투 도중 몬스터 추가" 구조. 소환 대상 Wriggler가
이미 이식돼 있어 가장 단순한 소비자인 PhrogParasite로 검증했다.

- [x] **`CombatState.add_monster(monster, slot_name)`** — 원본 `CreatureCmd.Add`.
  전투 rng를 물려주고 `setup_for_combat`으로 HP/무브그래프/개전 파워 초기화.
  `_combat_over` 플래그로 종료 후 소환 차단 (원본 `IsLiveCombat` 가드)
- [x] **`ShouldStopCombatFromEnding` 대응** — 해당 파워가 남아 있으면 적이
  전멸해 보여도 승리로 치지 않는다
- [x] **`reap_deaths` 순회 안전성** — 사망 훅이 소환하면 `self.monsters`가
  순회 중 변경되어 터지던 문제를 스냅샷 순회로 수정
- [x] **InfestedPower + PhrogParasite(엘리트)** — 사망 시 Wriggler 4마리를
  wriggler1~4 슬롯에 스턴 상태로 소환 (홀수 NASTY_BITE / 짝수 WRIGGLE)

## ✅ Phase 6p — 슬롯 기반 소환 (완료)

- [x] **인카운터 슬롯 목록 + `next_free_slot`** — 원본 `EncounterModel.Slots`와
  `GetNextSlot`(생존 적이 차지하지 않은 첫 칸). `make_encounter`가 몬스터에
  `encounter_id`를 새겨 소환체가 같은 슬롯 풀을 공유한다
- [x] **`RandomBranchState` 확장**: weight에 callable 허용(원본 `Func<float>`
  가중치 오버로드, 0이면 후보 제외) + `use_only_once`(`MoveRepeatType.UseOnlyOnce`)
- [x] **TwoTailedRat** — CanSummon 4조건 전부 이식(2턴 지연, 전투 3회 상한을
  같은 편이 공유, 빈 슬롯 존재, 동료의 중복 소환 예약 방지). 소환 가능 시
  분기 가중치가 공격 1/12 · 소환 0.75로 전환된다

## ✅ Phase 6q — GremlinMerc (완료)

- [x] **ThieveryPower / SurprisePower / HeistPower** — 공격마다 골드 절취(보유량
  상한), 사망 시 SneakyGremlin·FatGremlin 소환 + 훔친 골드 이관, 이관받은
  그렘린을 잡으면 환수. FatGremlin은 다음 턴 도주하므로 놓치면 골드를 잃는다
- [x] **GremlinMerc(HP 47~49)** + `gremlin_merc_normal` 인카운터 —
  "미이식 몬스터 대체" 부분 구성이던 것을 원본 구성으로 복원

## ✅ Phase 6r — 배치13 (완료)

- [x] **CubexConstruct**(HP 65) — 개전 블록 13 + Artifact 1,
  CHARGE_UP → REPEATER_BLAST ×2 → EXPEL 순환하며 무브마다 힘 누적
- [x] **SoulNexus**(엘리트, HP 234) — SOUL_BURN/MAELSTROM/DRAIN_LIFE
  3분기, 전부 CannotRepeat
- [x] **MinionPower** — 하수인 표식. 소유자 사망 후에도 유지
  (`ShouldPowerBeRemovedAfterOwnerDeath=false`)

## ✅ Phase 6s — 배치14 (완료)

- [x] **IllusionPower** — 피해를 받으면 스택 1을 소모하며 그 피해를 무효화
- [x] **EyeWithTeeth / Parafright** 스텁 2종을 정식 이식으로 승격
- [x] **Fogmog**(HP 74) / **TheObscura**(HP 123) — 각각 EyeWithTeeth /
  Parafright 소환

## ✅ Phase 6t — 배치15 (완료)

- [x] **HatchPower** — 턴 종료마다 카운터 1 감소(표시용). 실제 부화는
  `HATCH_MOVE`가 수행
- [x] **ToughEgg**(HP 14~18) — 개전 `HatchPower(2)`, 첫 턴 부화로 Minion을
  제외한 모든 파워를 제거하고 HP를 19~22로 재설정 → `NIBBLE` 4딜 무한 반복
- [x] **Ovicopter**(HP 124~130) — `LAY_EGGS`(빈 알 슬롯을 **뒤에서부터**
  최대 3칸 ToughEgg + `MinionPower(1)`) → `SMASH` 16 → `TENDERIZER` 7딜 +
  취약 2 → `SUMMON_BRANCH`{살아있는 적 ≤3 ? `LAY_EGGS` :
  `NUTRITIONAL_PASTE` 힘 +3 → `SMASH`}
- [x] **`CombatState.last_free_slot`** — 원본 `LastOrDefault` 대응 역순 빈
  슬롯 탐색 (`encounters.get_last_free_slot`)
- [x] **`ovicopter_normal`** 인카운터 (슬롯 `egg1`~`egg5` + `ovicopter`)

## ✅ Phase 6u — 배치16 (완료)

- [x] **BurrowedPower** — 원본 `ShouldClearBlock`이 소유자 본인에게만 false를
  반환해 블록이 턴 시작에 초기화되지 않는다. `AfterBlockBroken`(블록이 있었고
  이 피해로 전부 소진된 순간 1회)에 `GetStunned` → `Stun(StillDizzyMove,
  "BITE_MOVE")` → 파워 제거 순으로 발동하고, `AfterRemoved`의
  `LoseBlock(999999999)`을 `remove()` 자체에 붙여 어떤 제거 경로로도 잔여
  블록을 들고 나오지 못하게 했다
- [x] **SlumberPower** — 두 감소 경로의 **결과가 다르다**는 점이 핵심:
  피해(`AfterDamageReceived`, `UnblockedDamage != 0`)로 0이 되면
  `Stun(WakeUpMove, "ROLL_OUT_MOVE")`이라 기상이 **다음 턴의 행동**이 되고,
  턴 종료(`AfterSideTurnEnd`)로 0이 되면 `WakeUpMove`를 그 자리에서 실행하고
  상태머신은 건드리지 않아 `SNORE`가 한 번 더 남는다
- [x] **SoarPower** — `ModifyDamageMultiplicative`로 소유자가 받는 **파워드**
  공격 피해 50% 감소 (`IsPoweredAttack` 게이트)
- [x] **Tunneler**(HP 87) — `BITE` 13 → `BURROW`(Burrowed + 블록 32) →
  `BELOW` 23 무한 반복. 블록을 전부 깨야만 굴에서 끌려나와 `DIZZY` 1턴 후
  `BITE`부터 재개
- [x] **SlumberingBeetle**(HP 86) — 개전 `Plating` 15 + `Slumber` 3 →
  `SNORE` ↔ `SNORE_NEXT`{Slumber 보유? `SNORE` : `ROLL_OUT`} →
  `ROLL_OUT` 16딜 + 자기 힘 +2 무한 반복. 기상 시 Plating 상실
- [x] **OwlMagistrate**(HP 231) — `MAGISTRATE_SCRUTINY` 16 → `PECK_ASSAULT`
  4딜 ×6 → `JUDICIAL_FLIGHT`(Soar) → `VERDICT` 33딜 + 취약 4 & Soar 제거 → 순환
- [x] **인카운터 4종** — `tunneler_normal`(원본 그대로 Chomper(ScreamFirst) +
  Tunneler), `tunneler_weak`, `slumbering_beetle_normal`(부분 구성 — 원본의
  BowlbugRock/BowlbugSilk 미이식), `owl_magistrate_normal`

## ✅ Phase 6v — 배치17 (완료)

- [x] **AfterDamageReceived 훅** — 양수 공격이 블록에 전부 막혀도 대상 파워에
  통지하되, 그 피해로 대상이 죽은 경우에는 건너뛰도록 원본 `CreatureCmd` 순서로
  `Creature.take_damage`에 배선
- [x] **PersonalHivePower** — Entomancer가 플레이어의 파워드 공격을 받을 때마다
  공격자의 뽑을 더미 무작위 위치에 `Dazed`를 amount장 생성. 완전 블록에도
  발동하고, 언파워드 피해와 치명타 사망에는 발동하지 않는다
- [x] **Entomancer**(HP 145) — 개전 PersonalHive 1, `BEES` 3×7 → `SPEAR` 18 →
  `PHEROMONE_SPIT`{벌집 <3 ? 벌집 +1 & 힘 +1 : 힘 +2} 순환
- [x] **KinFollower**(HP 58~59) — 개전 Minion 1, `QUICK_SLASH` 5 →
  `BOOMERANG` 2×2 → `POWER_DANCE` 힘 +2 순환. `starts_with_dance` 개체는
  Dance부터 시작
- [x] **TorchHeadAmalgam**(HP 199) — 개전 Minion 1, 강태클 18×2는 개전
  한 번뿐이고 이후 `BEAM` 8×3 → 약태클 14×2를 반복
- [x] **인카운터 3종** — `entomancer_elite`, `kin_followers_weak`(KinPriest
  미이식 부분 구성), `torch_head_amalgam_normal`(Queen 미이식 부분 구성)

## ✅ `S1.M3.B18 — 몬스터·인카운터 배치 18` (완료)

- [x] **완전 블록 결과 훅** — `Creature.take_damage()`가 블록 흡수량에 근거한
  `fully_blocked`를 반환하고, `MonsterModel.attack()`이 공격자 파워의
  `on_damage_given(target, result)`에 결과 전체를 통지. 실제 HP 손실 전용
  `on_landed_attack` 경계는 유지해 `Buffer`와 `SuckPower` 의미를 보존
- [x] **강제 상태 전환 보존** — 실행할 무브를 callback 전에 history에 기록하고,
  callback이 `stun()` 등으로 현재 상태를 바꾸면 같은 턴 자동 advance를 생략해
  다음 턴 `STUNNED` 상태가 사라지던 공용 상태 머신 버그 수정
- [x] **ImbalancedPower** — 보유자의 공격이 전부 막히면 일반 몬스터는 기절하고,
  BowlbugRock은 `is_off_balance`로 전환. Single 재적용은 중첩하지 않음
- [x] **Bowlbug 4종** — Egg(7딜+블록7 반복), Nectar(3딜→힘+15→공격 반복),
  Rock(15딜, 완전 블록 시 DIZZY), Silk(약화1 시작, 4×2와 교대)
- [x] **인카운터 2종** — `bowlbugs_weak`, `bowlbugs_normal`의 원본 슬롯과
  시드 기반 무작위 구성을 재현
- [x] **`slumbering_beetle_normal` 복원** — BowlbugRock + BowlbugSilk +
  SlumberingBeetle 원본 3체 구성으로 복원
- [x] `test_sts2_s1_m3_b18.py` 및 루트 회귀 27스위트 전체 통과

## ✅ `S1.M3.B19 — 몬스터·인카운터 배치 19` (완료)

- [x] **Kaiser Crab 보스 2종** — Crusher(HP 209, `THRASH` 12 →
  `ENLARGING_STRIKE` 4 → `BUG_STING` 6×2+약화2+허약2 → `ADAPT` 힘+2 →
  `GUARDED_STRIKE` 12+블록18)와 Rocket(HP 199, `TARGETING_RETICLE` 3 →
  `PRECISION_BEAM` 18 → `CHARGE_UP` 힘+2 → `LASER` 31 → `RECHARGE` 무행동)의
  고정 5무브 순환 이식. 두 팔 모두 Doom으로 사라지지 않음
- [x] **BackAttackLeftPower / BackAttackRightPower** — Crusher·Rocket의 좌우를
  표시하는 원본 마커 파워
- [x] **CrabRagePower** — 한 팔이 죽으면 남은 팔에 힘+6과 언파워드 블록99를
  지급하고 1회 발동 후 제거
- [x] **SurroundedPower** — 기본 `facing=right`에서 Crusher의 파워드 공격만
  1.5배. 한 팔 사망 후 남은 팔을 향하도록 원본 조건에 따라 방향 갱신
- [x] **인카운터 1종** — `kaiser_crab_boss`의 Crusher/Rocket 슬롯 구성 재현
- [x] `test_sts2_s1_m3_b19.py` 및 루트 회귀 28스위트 전체 통과
- [ ] 원본의 카드·포션 대상 선택 시 방향 전환은 현재 카드 대상 통지와 포션
  시스템이 없어 보류

## ✅ `S1.M3.B20 — CeremonialBeast / PlowPower / RingingPower` (완료)

- [x] **CeremonialBeast** (HP 252, 보스) — STAMP→PLow 순환, HP 150 이하 전이
  (힘 상실+기절), 이후 BEAST_CRY→STOMP→CRUSH 순환. RingingPower 부여
- [x] **PlowPower** — 매 턴 자동 PLow, 플레이어 HP가 임계치 이하면 힘 상실+기절
- [x] **RingingPower** — 카드 사용 시 반사 피해
- [x] **인카운터** — `ceremonial_beast_boss` 구성 추가
- [x] `test_sts2_s1_m3_b20.py` 및 전체 회귀 31스위트 통과

## ✅ `S1.M3.B21 — KnowledgeDemon / Curse 선택 4종 / 파워 4종` (완료)

- [x] **KnowledgeDemon** (HP 379, 보스) — Curse 선택 카드 메커니즘, 힘 스케일링
- [x] **Curse 선택 카드 4종** — MindRot/Sloth/WasteAway/Disintegration (상태이상)
- [x] **파워 4종** — MindRotPower/SlothPower/WasteAwayPower/DisintegrationPower
- [x] **인카운터** — `knowledge_demon_boss` 구성 추가
- [x] `test_sts2_s1_m3_b21.py` 및 전체 회귀 31스위트 통과

## ✅ `S1.M3.B22 — TheAdversary Mk1~Mk3 시험 몬스터` (완료)

- [x] **TheAdversary Mk1/Mk2/Mk3** — 개발용 테스트 몬스터 (스케일링 검증용)
- [x] `test_sts2_s1_m3_b22.py` 및 전체 회귀 31스위트 통과

## 📋 `S1.M3.B23 — 후속 구현 배치 23` (계획)

아래 잔여 대상 중 선행 의존성이 작은 묶음을 원본 대조 후 선정한다. Affliction,
Curse 선택, 다체 보스처럼 별도 엔진이 필요한 대상은 한 Batch에 억지로 섞지 않는다.

### 몬스터 잔여 14종 — 차단 요인별 분류

인카운터가 실제로 배치하는 대상 기준(개발용 클래스, 렐릭 전용 소환 펫
Byrdpip/PaelsLegion, 소환 전용 하위 엔티티 제외). **아래 "필요 파워"는
디컴파일 원본을 스캔해 뽑은 것이므로 재조사 없이 그대로 쓸 것.**

| 몬스터 | HP | 필요한 미이식 파워 | 비고 |
|---|---|---|---|
| InfestedPrism | 161 | `VitalSparkPower` | Affliction/Tainted 시스템 필요 |
| CeremonialBeast | 252 | `PlowPower`, `RingingPower` | Ringing 카드 Affliction 필요 |
| ThievingHopper | 79 | `EscapeArtistPower`, `FlutterPower`, `SwipePower` | 영구 덱 절취·사망 시 보상 반환 필요 |
| KnowledgeDemon | 379 | 없음 | Curse 선택 카드/즉시 선택 효과 필요 |
| LivingFog + GasBomb | 80 / 7 | `SmoggyPower` | **Affliction 시스템**(카드 단위 상태이상) 필요 |
| Fabricator + Axebot/Rocket | | | 무작위 봇 소환 |
| Decimillipede 세그먼트 | | | 체인 연동 구조 |
| TheAdversary Mk1-3, Queen, Aeonglass | | | 다체/보스 특수 구조 |
| TheLost / TheForgotten / TheInsatiable | | Possess 계열 | |

- [ ] `Architect`(HP 9999, 무행동)는 연출/개발용 더미라 이식 대상에서 제외
- [ ] 렐릭 풀 297종 (`Models.RelicPools`) — 현재 22종. 훅 표면은 이미 있어
  대부분 훅 하나짜리 얕은 작업, 20~30종씩 묶어 진행
- [ ] 포션 64종 (`Models.PotionPools`) — 포션 시스템 자체가 미구현
- [ ] 이벤트 59종 — 실제 맵 그래프와 함께 진행해야 의미가 있다
- [ ] 실제 맵 그래프 (현재 고정 층 시퀀스) — 상점/이벤트 방 포함
- [ ] Ascension 수치 분기 (`AscensionHelper` — 현재 기본값만)
- [ ] MCTS 정책 실험

---

## 🛠 개발 환경

```
Python 3.11+  |  외부 의존성 없음 (표준 라이브러리만 사용)
```

**테스트 실행:**
```bash
python3 test_sts2_basic.py        # 몬스터 기본
python3 test_sts2_integration.py  # 코어 통합
python3 test_sts2_phase2.py       # 렐릭/캐릭터
python3 test_sts2_phase3.py       # Orb/스타터 카드/렐릭
python3 test_sts2_phase4.py       # 전투/런 루프
python3 test_sts2_phase5.py       # 정책/통계
python3 test_sts2_phase6.py       # 신규 몬스터/인카운터
python3 test_sts2_phase6b.py      # Ironclad 카드 풀 85종
python3 test_sts2_phase6c.py      # Silent 카드 풀 86종
python3 test_sts2_phase6d.py      # Defect 카드 풀 86종 + 오브 엔진 확장
python3 test_sts2_phase6e.py      # Necrobinder 카드 풀 82종 + Osty/Doom/Ethereal 엔진
python3 test_sts2_phase6f.py      # Regent 카드 풀 + 별(star) 엔진
python3 test_sts2_phase6g.py      # Colorless 카드 풀
python3 test_sts2_phase6j.py      # 몬스터 배치1 13종
python3 test_sts2_phase6k.py      # 몬스터 배치8 8종 + 분기 오버로드 감사
python3 test_sts2_phase6l.py      # 몬스터 배치9 5종 (Act1 완결)
python3 test_sts2_phase6m.py      # WaterfallGiant 보스 (2단계 사망)
python3 test_sts2_phase6n.py      # 몬스터 배치11 9종 + 파워 6종
python3 test_sts2_phase6o.py      # 전투 중 소환 엔진 + PhrogParasite
python3 test_sts2_phase6p.py      # 슬롯 기반 소환 + TwoTailedRat
python3 test_sts2_phase6q.py      # GremlinMerc (골드 절취/동료 소환)
python3 test_sts2_phase6r.py      # 배치13 (CubexConstruct/SoulNexus)
python3 test_sts2_phase6s.py      # 배치14 (Fogmog/TheObscura)
python3 test_sts2_phase6t.py      # 배치15 (ToughEgg/Ovicopter)
python3 test_sts2_phase6u.py      # 배치16 (Tunneler/SlumberingBeetle/OwlMagistrate)
python3 test_sts2_phase6v.py      # 배치17 (Entomancer/KinFollower/TorchHeadAmalgam)
python3 test_sts2_s1_m3_b18.py    # 배치18 (Bowlbug 4종/Imbalanced/인카운터)
python3 test_sts2_s1_m3_b19.py    # 배치19 (Crusher/Rocket/Kaiser Crab 보스)
```

**통계 실행:**
```bash
python3 -m sts2_sim.core.stats ironclad 50 --policy greedy
python3 -m sts2_sim.core.stats ironclad 50 --policy greedy --verbose  # 턴/카드 단위 상세 로그
```

**디컴파일 재생성 (참고):**
```bash
dotnet tool install -g ilspycmd
~/.dotnet/tools/ilspycmd sts2.dll -p -o decompiled/
```
