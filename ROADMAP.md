# STS2 Simulator Roadmap

Slay the Spire 2 헤드리스 Python 시뮬레이터의 구현 현황 및 향후 계획.  
`sts2.dll` (`MegaCrit.Sts2.Core`) 네임스페이스 구조를 기준으로 대응 구현.

---

## ✅ Phase 1 — 전투 코어 (완료)

### 엔진
- [x] `HookBus` — 이벤트 훅 버스 (BeforeCardPlayed, AfterDamageReceived 등)
- [x] `CombatState` — 전투 상태 (hand/draw/discard/exhaust 파일, 에너지, 라운드)
- [x] `CombatManager` — 전투 루프 제너레이터 (`yield` 기반, 외부 정책 주입)
- [x] `Creature` — 공통 생명체 (HP, 블록, 파워 적용/제거, `take_damage` 파이프라인)
- [x] `Player` — 플레이어 (에너지, 덱, 드로우 파일 생성, 렐릭 등록)
- [x] `Monster` — 몬스터 기반 클래스 (인텐트, 이동 AI, `take_turn`)
- [x] `SeededRng` — 시드 기반 RNG (`fork` 지원)

### 카드 시스템
- [x] `CardModel` — 카드 기반 클래스 (비용, 타입, 희귀도, 업그레이드, 소모)
- [x] `PileType` — hand / draw / discard / exhaust
- [x] `apply_play_card` / `apply_end_turn` 헬퍼

### 파워 시스템 (`models/power_model.py`)
- [x] Strength, Dexterity, Vulnerable, Weak, Frail
- [x] Ritual, Metallicize, Thorns, NoDraw, Poison
- [x] Rage, DemonForm, Barricade, Corruption, Juggernaut, LimitBreak
- [x] ToolsOfTheTrade

---

## ✅ Phase 2 — 콘텐츠 1회차 (완료)

### Ironclad 카드
- [x] Basic: Strike, Defend, Bash
- [x] Common: Cleave, Clothesline, Headbutt, HeavyBlade, IronWave, PerfectedStrike, ShrugItOff, ThunderClap, TrueGrit, TwinStrike, WildStrike
- [x] Uncommon: Bloodletting, BurningPact, Carnage, Combust, DarkEmbrace, Disarm, Dropkick, DualWield, Entrench, Evolve, FeelNoPain, FlameBarrier, GhostlyArmor, Hemokinesis, Infernal Blade, Inflame, Intimidate, Metallicize, PowerThrough, Pummel, Rage, Rampage, RecklessCharge, Rupture, SearingBlow, SecondWind, SeeingRed, Sentinel, SeverSoul, Shockwave, SpotWeakness, Uppercut, Whirlwind
- [x] Rare: Bludgeon, Brutality, CorruptionCard, DemonFormCard, Exhume, Feed, FiendFire, Immolate, Impervious, Juggernaut, LimitBreakCard, Offering, Reaper

### Silent 카드
- [x] Basic: Strike, Defend, Survivor, Acrobatics, Shiv, Neutralize
- [x] Common: Bane, BladeDance, CloakAndDagger, DaggerSpray, DaggerThrow, Deflect, DodgeAndRoll, FlyingKnee, Outmaneuver, PiercingWail, PoisonedStab, Prepared, QuickSlash, Slice, SneakyStrike, SuckerPunch, AllOutAttack, Acupuncture
- [x] Uncommon: Backstab, CalculatedGamble, Caltrops, Catalyst, Choke, Concentrate, CripplingCloud, DeadlyPoison, Distraction, EndlessAgony, EscapePlan, Expertise, Footwork, InfiniteBlades, NoxiousFumes, RiddleWithHoles, Setup, Terror, ToolsOfTheTrade, Unload, WellLaidPlans
- [x] Rare: Adrenaline, Alchemize, BulletTime, CorpseExplosion, DieDieDie, Doppelganger, Envenom, GlassKnife, GrandFinale, Malaise, Nightmare, PhantasmalKiller, StormOfSteel, WraithForm

### 몬스터 (Act 1~3)
- [x] Act 1: Jawworm, RedLouse, GreenLouse, AcidSlimeSmall/Medium, SpikeSlimeSmall/Medium, Cultist, FungiBeast
- [x] Act 1 Elite/Boss: GremlinNob, SlimeBoss
- [x] Act 2: Centurion, Chosen, BookOfStabbing
- [x] Act 2 Boss: TheChamp
- [x] Act 3: Nemesis, GiantHead
- [x] Act 3 Boss: DonuDeca

### 맵 & 런 시스템
- [x] `ActMap` — 3-Act 맵 생성 (MONSTER/ELITE/BOSS/REST/TREASURE/SHOP/EVENT)
- [x] `run_full_playthrough` — 전체 런 루프
- [x] `RunConfig` — 시드, 액트 수, 상세 출력, `skip_card_prob`
- [x] 전투 보상 (골드, 카드)
- [x] 휴식 (30% HP 회복), 보물
- [x] 이벤트 룸 (기본 구현)

### 렐릭
- [x] Ironclad 스타터: BurningBlood
- [x] Silent 스타터: RingOfSnake
- [x] 기타 Ironclad 렐릭: AkabekosMemory, OddlySmoothStone 등

---

## 🔄 Phase 3 — 정확도 개선 (진행 중)

### 밸런스 수정
- [ ] **Act 2 몬스터 수치 교정** — `sts2.dll` 디컴파일로 실제 HP/데미지 값 추출
  - Centurion: 현재 추정치 → 실제값 검증 필요
  - Chosen: Hex(덱에 Dazed 추가) 미구현
  - BookOfStabbing: 다중 히트 AI 검증 필요
- [ ] **덱 관리 AI 개선** — `skip_card_prob` 기반 스킵 로직 고도화
  - 현재: 랜덤 스킵 → 목표: 덱 크기·시너지 기반 지능형 스킵
- [ ] Act 3 몬스터 추가 (Reptomancer, Awakened One 등)

### 미구현 메카닉
- [ ] **Hex 파워** (Chosen) — 카드 플레이마다 덱에 Dazed 추가
- [ ] **Shackled** — 이번 턴 카드 플레이 불가
- [ ] **Entangle** — 공격 카드 플레이 불가
- [ ] **CurlUp** (Louse) — 첫 공격 받을 때 블록 획득
- [ ] **모드 — 소환** (DonuDeca, 복수 몬스터 동기화 AI)
- [ ] **보스 특수 행동** — TheChamp 페이즈 전환

---

## 📋 Phase 4 — 확장 (계획)

### 추가 캐릭터
- [ ] **Defect** 카드 세트 (Orb 시스템 포함)
- [ ] **Watcher** 카드 세트 (Stance 시스템)
- [ ] **Necrobinder** (STS2 신규 캐릭터)
- [ ] **Regent** (STS2 신규 캐릭터)

### 공용 렐릭
- [ ] Common 렐릭 20종 (Akabeko, Anchor, BagOfMarbles 등)
- [ ] Uncommon 렐릭 20종
- [ ] Rare 렐릭 15종
- [ ] Boss 렐릭 (act 전환 보상)
- [ ] Shop 렐릭

### 이벤트 시스템
- [ ] Act별 이벤트 풀 완성 (현재 기본 구현만)
- [ ] Dead Adventurer, Big Fish, Falling 등 주요 이벤트

### AI & 분석
- [ ] **그리디 정책 개선** — 현재 단순 최대 데미지 우선 → 상황 인식 AI
- [ ] **몬테카를로 트리 탐색 (MCTS)** 정책 실험
- [ ] **덱 시뮬레이션 통계** — 씨드별 승률, 평균 클리어 층, HP 추이 분석
- [ ] **카드 픽 최적화** — 특정 덱 컨셉 기반 카드 선택 전략 탐색

### 인프라
- [ ] `pytest` 테스트 커버리지 80% 이상
- [ ] GitHub Actions CI (push 시 자동 테스트)
- [ ] 성능 벤치마크 (1000 런 / 초 목표)

---

## 🛠 개발 환경

```
Python 3.11+  |  외부 의존성 없음 (표준 라이브러리만 사용)
```

**로컬 실행:**
```bash
python3 -m sts2_sim.test_full_run
python3 -m pytest sts2_sim/
```

**참조 파일 (Codespace):**
```bash
# sts2.dll / sts2.xml — _data 브랜치에서 받기
git fetch origin _data && git checkout origin/_data -- sts2.dll sts2.xml
dotnet tool install -g ilspycmd
~/.dotnet/tools/ilspycmd sts2.dll -p -o decompiled/
```
