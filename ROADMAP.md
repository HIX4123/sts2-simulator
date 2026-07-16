# STS2 Simulator Roadmap

Slay the Spire 2 헤드리스 Python 시뮬레이터.
**`sts2.dll` 디컴파일 코드(`decompiled/MegaCrit.Sts2.Core.*`)를 유일한 근거 자료로 삼아** 실제 STS2 게임 데이터를 이식한다.
(이전의 STS1 기반 추정 구현은 전부 제거됨.)

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

## 📋 Phase 6g+ — 남은 확대 (계획)

- [ ] Colorless 카드 풀 (`Models.CardPools.ColorlessCardPool`) — Regent 5개 카드/파워가
  참조하는 미이식 생성 로직(Quasar/BundleOfJoy/ManifestAuthority/SpectrumShift/
  HeirloomHammer) 포함
- [ ] 몬스터 잔여 ~87종 (보스/다체 연동 포함: Aeonglass, Fabricator 소환 등)
- [ ] 렐릭 풀 (`Models.RelicPools`), 포션 (`Models.PotionPools`)
- [ ] 미이식 파워: GalvanicPower, RampartPower, DampenPower, HighVoltagePower 등
- [ ] Ascension 수치 분기 (`AscensionHelper` — 현재 기본값만)
- [ ] 실제 맵 그래프 (현재 고정 층 시퀀스) — 업그레이드/보상 기회 확대로 엘리트 승률 개선
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
```

**통계 실행:**
```bash
python3 -m sts2_sim.core.stats ironclad 50 --policy greedy
```

**디컴파일 재생성 (참고):**
```bash
dotnet tool install -g ilspycmd
~/.dotnet/tools/ilspycmd sts2.dll -p -o decompiled/
```
