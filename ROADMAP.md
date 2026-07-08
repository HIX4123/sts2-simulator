# STS2 Simulator Roadmap

Slay the Spire 2 헤드리스 Python 시뮬레이터.
**`sts2.dll` 디컴파일 코드(`decompiled/MegaCrit.Sts2.Core.*`)를 유일한 근거 자료로 삼아** 실제 STS2 게임 데이터를 이식한다.
(이전의 STS1 기반 추정 구현은 전부 제거됨.)

---

## ✅ Phase 1 — 코어 시스템 (완료)

- [x] `MonsterModel` — 상태 머신 기반 몬스터 (디컴파일 `MonsterMoveStateMachine` 구조 이식)
- [x] `MoveState` / `Intent` — 행동 상태 및 인텐트
- [x] `STS2Power` — 파워 베이스 + 데미지/블록 수정 체계
- [x] `STS2Card` — 카드 베이스 (타입/희귀도/업그레이드)
- [x] 몬스터 11종 (TwigSlimeS, Stabbot, AxeRubyRaider, Zapbot, Guardbot 등)

## ✅ Phase 2 — 렐릭 & 캐릭터 (완료)

- [x] `STS2Relic` — 렐릭 베이스 + 팩토리
- [x] 렐릭 19종 (스타터/Common/Uncommon/Rare/Boss)
- [x] 캐릭터 시스템 + 몬스터 5종 추가 (총 16종)

## 🔄 Phase 3 — 실제 STS2 캐릭터 로스터 & Orb 시스템 (진행 중)

디컴파일 `Models.Characters`/`Models.Orbs` 기준:

- [ ] 캐릭터 로스터 교정 — 실제 STS2는 **Ironclad, Silent, Defect, Necrobinder, Regent** (Watcher 없음)
  - Ironclad: HP 80, Strike×5/Defend×4/Bash, BurningBlood ✅
  - Silent: HP 70, **12장 덱** (Strike×5/Defend×5/Neutralize/Survivor), RingOfTheSnake(첫 턴 +2 드로우)
  - Defect: HP 75, Strike×4/Defend×4/Zap/Dualcast, CrackedCore, 오브 슬롯 3
  - Necrobinder(신규): HP 66, Bodyguard/Unleash, BoundPhylactery — **Osty 소환수** 메카닉
  - Regent(신규): HP 75, FallingStar/Venerate, DivineRight — **Stars 자원** 메카닉
- [ ] Orb 시스템 (`OrbModel` + 5종: Lightning/Frost/Dark/Plasma/**Glass**)
  - Lightning: 패시브 3딜(무작위 적) / 이보크 8딜
  - Frost: 패시브 2블록 / 이보크 5블록
  - Dark: 패시브마다 이보크값 +6 / 이보크 시 최저 HP 적
  - Plasma: 턴 시작 에너지 +1 / 이보크 +2 (Focus 미적용)
  - Glass(STS2 신규): 전체 4딜, 트리거마다 -1 / 이보크 = 패시브×2
- [ ] Focus 파워, 스타터 카드 8종 (Zap, Dualcast, Neutralize, Survivor, Bodyguard, Unleash, FallingStar, Venerate)
- [ ] 스타터 렐릭 교정 (CrackedCore, BoundPhylactery, DivineRight, RingOfTheSnake)

## 📋 Phase 4 — 전투 루프 & 런 시스템 (계획)

- [ ] `CombatState` — 턴 루프 (에너지/드로우/카드 플레이/오브 트리거/몬스터 턴)
- [ ] 덱 관리 (draw/discard/exhaust, 시드 셔플)
- [ ] 인카운터 풀 (디컴파일 `Models.Encounters` 기준: AxebotsNormal, BowlbugsWeak 등)
- [ ] 런 루프 (방 진행, 보상, 휴식)

## 📋 Phase 5 — AI & 분석 (계획)

- [ ] 그리디 카드 플레이 정책
- [ ] 시드별 통계 러너 (승률, 평균 턴 수, HP 추이)
- [ ] MCTS 정책 실험

## 📋 Phase 6 — 콘텐츠 확대 (계획)

- [ ] 몬스터 121종 전체 이식 (현재 16종)
- [ ] 캐릭터별 카드 풀 (`Models.CardPools` 기준)
- [ ] 렐릭 풀 (`Models.RelicPools`), 포션 (`Models.PotionPools`)
- [ ] Ascension 수치 분기 (`AscensionHelper.GetValueIfAscension`)

---

## 🛠 개발 환경

```
Python 3.11+  |  외부 의존성 없음 (표준 라이브러리만 사용)
```

**테스트 실행:**
```bash
python3 test_sts2_basic.py        # Phase 1 몬스터
python3 test_sts2_integration.py  # Phase 1 통합
python3 test_sts2_phase2.py       # Phase 2 렐릭/캐릭터
```

**디컴파일 재생성 (참고):**
```bash
dotnet tool install -g ilspycmd
~/.dotnet/tools/ilspycmd sts2.dll -p -o decompiled/
```
