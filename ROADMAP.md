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

## 📋 Phase 6b+ — 남은 확대 (계획)

- [ ] 몬스터 잔여 ~87종 (보스/다체 연동 포함: Aeonglass, Fabricator 소환 등)
- [ ] 카드 풀 확대 (STS2 전체 593종 중 16종 이식됨) — `Models.CardPools` 기준 캐릭터별 풀
- [ ] 렐릭 풀 (`Models.RelicPools`), 포션 (`Models.PotionPools`)
- [ ] 미이식 파워: GalvanicPower, RampartPower, DampenPower, HighVoltagePower 등
- [ ] Ascension 수치 분기 (`AscensionHelper` — 현재 기본값만)
- [ ] 실제 맵 그래프 (현재 고정 층 시퀀스)
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
