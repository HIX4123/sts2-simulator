# STS2 시뮬레이터 — 구현 현황

`sts2.dll` 디컴파일 데이터 기반 헤드리스 Slay the Spire 2 시뮬레이터.
모든 수치는 `decompiled/MegaCrit.Sts2.Core.*`에서 추출한 실제값 (Ascension 미적용 기본값).

## 📊 규모 요약

| 시스템 | 개수 | 비고 |
|--------|------|------|
| 몬스터 | 34종 | 상태 머신 AI, 실제 HP/데미지 |
| 인카운터 | 12종 | 실제 구성 로직 (부분 구성 3종은 주석 표기) |
| 캐릭터 | 5종 | Ironclad / Silent / Defect / Necrobinder / Regent |
| 카드 | 500종 | **Ironclad 85 + Silent 86 + Defect 86 + Necrobinder 82 + Regent 82 + Colorless 65종 완전 이식** + 스타터/상태이상/토큰 (STS2 전체 593종 중) |
| 파워 | 161종 | 비용 수정/자동 플레이/소모·버리기/생성·이보크 훅 배선 완료 |
| 렐릭 | 22종 | 스타터 5종은 실제 동작 |
| 오브 | 5종 | Lightning/Frost/Dark/Plasma/Glass + OrbQueue (슬롯 상한 10/EvokeLast/수동 패시브) |
| 테스트 | 13개 스위트 | 전부 통과, 시드 재현성 보장 |

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

## 👹 몬스터 34종

**기본 (sts2_monster.py):** BigDummy, SingleAttack/MultiAttackMoveMonster(테스트),
TwigSlimeS/M, Stabbot, Zapbot, Guardbot, AxeRubyRaider, FlailKnight, DampCultist,
Chomper, FatGremlin, Parafright, EyeWithTeeth, BattleFriendV1/V2

**Phase 6a (monsters_extra.py):** LeafSlimeS/M, CalcifiedCultist, SpectralKnight,
MagiKnight, Assassin/Brute/Tracker/CrossbowRubyRaider, SewerClam, SnappingJaxfruit,
SneakyGremlin, Noisebot, LivingShield, Mawler, GlobeHead, VineShambler

특수 메카닉: RandomBranchState(가중치/CannotRepeat/UseOnlyOnce), 조건 분기(LivingShield),
도주(FatGremlin/SneakyGremlin 대기→행동), 상태이상 삽입(Dazed/Slimed), Ritual 램핑,
Artifact 디버프 무효, Plating 감쇠 블록, Tangled 공격 봉쇄.

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
  - **Strength/Weak/Vulnerable IsPoweredAttack() 게이트**: 원본은 셋 다
    `props.IsPoweredAttack()`(Move && !Unpowered) 게이트가 있어 Unpowered
    반사·자해 피해(Thorns/FlameBarrier/Outbreak/Burn/NecroMastery/
    SleightOfFlesh 등)에는 적용되지 않지만, 현재 구현은 무조건 적용됨.
    Phase 6i에서 발견 — 다음 작업 단위로 예정(ROADMAP.md 참조)
- **오탐 판정 1건:** JackOfAllTrades가 MultiplayerOnly 카드 12종을 생성 후보에서
  제외하지 않는 것은 이 프로젝트가 `CardMultiplayerConstraint` 개념 자체를
  구현하지 않기로 한 전역 결정(Phase 6f부터 문서화)의 직접적 귀결 — 별도 버그
  아님

## 🔧 Phase 6i — 엔진 아키텍처 확장

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

## 🔬 생성 방법론 (Phase 6a)

몬스터 17종은 멀티에이전트 파이프라인으로 이식:
1. **이식 에이전트** — 디컴파일 .cs와 기존 패턴을 읽고 Python 클래스 생성
2. **검증 에이전트** — 원본과 수치/상태그래프 적대 대조 (LeafSlimeS 시드 재현성 버그,
   SpectralKnight CanRepeatXTimes 전개 오류를 잡아 수정)
3. **수동 대조** — 세션 한도로 미검증된 13종을 원본 소스와 직접 대조 (전부 일치 확인)

## 🚀 다음 단계

ROADMAP.md의 Phase 6g+ 참조 — Strength/Weak/Vulnerable IsPoweredAttack() 게이트
(Phase 6i 중 발견, stats 회귀 가능성 있어 별도 검증 필요), 몬스터 잔여 ~87종,
렐릭/포션 풀, 미이식 파워(Galvanic/Rampart/Dampen/HighVoltage), Ascension,
실제 맵 그래프.
