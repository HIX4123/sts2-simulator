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

## 📋 Phase 6g+ — 남은 확대 (계획)

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
python3 -m sts2_sim.core.stats ironclad 50 --policy greedy --verbose  # 턴/카드 단위 상세 로그
```

**디컴파일 재생성 (참고):**
```bash
dotnet tool install -g ilspycmd
~/.dotnet/tools/ilspycmd sts2.dll -p -o decompiled/
```
