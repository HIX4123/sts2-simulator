# STS2 시뮬레이터 — 구현 현황

`sts2.dll` 디컴파일 데이터 기반 헤드리스 Slay the Spire 2 시뮬레이터.
모든 수치는 `decompiled/MegaCrit.Sts2.Core.*`에서 추출한 실제값 (Ascension 미적용 기본값).

## 📊 규모 요약

| 시스템 | 개수 | 비고 |
|--------|------|------|
| 몬스터 | 34종 | 상태 머신 AI, 실제 HP/데미지 |
| 인카운터 | 12종 | 실제 구성 로직 (부분 구성 3종은 주석 표기) |
| 캐릭터 | 5종 | Ironclad / Silent / Defect / Necrobinder / Regent |
| 카드 | 264종 | **Ironclad 85 + Silent 86 + Defect 86종 완전 이식** + 스타터/상태이상/토큰 (STS2 전체 593종) |
| 파워 | 95종 | 카드 파워 74종 포함 — 비용 수정/자동 플레이/소모·버리기/생성·이보크 훅 배선 완료 |
| 렐릭 | 22종 | 스타터 5종은 실제 동작 |
| 오브 | 5종 | Lightning/Frost/Dark/Plasma/Glass + OrbQueue (슬롯 상한 10/EvokeLast/수동 패시브) |
| 테스트 | 10개 스위트 | 전부 통과, 시드 재현성 보장 |

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
│  ├─ sts2_power.py      # 파워 95종
│  ├─ sts2_card.py       # 카드 베이스 + 스타터 16종 + 상태이상 5종
│  ├─ sts2_relic.py      # 렐릭 22종
│  └─ sts2_orb.py        # 오브 5종 + OrbQueue (상한 10/EvokeLast/이보크 훅)
├─ cards/
│  ├─ ironclad.py        # Phase 6b: Ironclad 풀 82종 (C19/U35/R25/Ancient2/Token1)
│  ├─ silent.py          # Phase 6c: Silent 풀 80종 (C19/U34/R25/Ancient2)
│  └─ defect.py          # Phase 6d: Defect 풀 83종 (C20/U35/R25/Ancient2/Token1)
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

## 🔬 생성 방법론 (Phase 6a)

몬스터 17종은 멀티에이전트 파이프라인으로 이식:
1. **이식 에이전트** — 디컴파일 .cs와 기존 패턴을 읽고 Python 클래스 생성
2. **검증 에이전트** — 원본과 수치/상태그래프 적대 대조 (LeafSlimeS 시드 재현성 버그,
   SpectralKnight CanRepeatXTimes 전개 오류를 잡아 수정)
3. **수동 대조** — 세션 한도로 미검증된 13종을 원본 소스와 직접 대조 (전부 일치 확인)

## 🚀 다음 단계

ROADMAP.md의 Phase 6e+ 참조 — 나머지 캐릭터 카드 풀(Necrobinder/Regent/Colorless),
몬스터 잔여 ~87종, 렐릭/포션 풀, 미이식 파워(Galvanic/Rampart/Dampen/HighVoltage),
Ascension, 실제 맵 그래프.
