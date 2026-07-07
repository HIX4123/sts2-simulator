# STS2 시뮬레이터 — Phase 1 구현 완료 보고서

## 📋 개요
STS2(Slay the Spire 2) 헤드리스 Python 시뮬레이터의 **Phase 1** 구현 완료.
디컬파일된 `sts2.dll` 데이터를 기반으로 STS2 스타일의 게임 엔진 구축.

## ✅ Phase 1 완성 항목

### 1. 몬스터 시스템 (`sts2_sim/entities/sts2_monster.py`)
- **MonsterModel** 베이스 클래스 (STS2 아키텍처 준수)
- **MonsterMoveStateMachine** — 상태 머신 기반 행동 시스템
  - 단순 반복 행동 (e.g., TwigSlimeS)
  - 복잡한 상태 전환 (e.g., AxeRubyRaider: SWING_1 → SWING_2 → BIG_SWING)
  - Intent 시스템 (UI 표시 정보)

#### 구현된 몬스터 (11개)
| 몬스터 | HP | 특징 |
|--------|-----|------|
| BigDummy | 9999 | 테스트용 더미 |
| SingleAttackMoveMonster | 999 | 단순 공격 |
| MultiAttackMoveMonster | 999 | 다중 공격 |
| TwigSlimeS | 11 | 단순 택클 |
| Stabbot | 23 | 공격 + 디버프 |
| AxeRubyRaider | 22 | 상태 전환 (SWING1→SWING2→BIGSWING) |
| Parafright | 21 | 공격 |
| EyeWithTeeth | 6 | 소형 적 |
| BattleFriendV1 | 75 | 지원/공격 반복 |
| BattleFriendV2 | 150 | 강화된 지원/공격 |
| Zapbot | 30 | 전기 공격 |
| Guardbot | 40 | 공격/방어 반복 |

### 2. 파워 시스템 (`sts2_sim/models/sts2_power.py`)
- **STS2Power** 베이스 클래스
- 파워 팩토리 패턴 (동적 생성)
- 데미지/블록 수정 체계

#### 구현된 파워 (14개)
| 파워 | 타입 | 효과 |
|------|------|------|
| Strength | 버프 | 공격 데미지 +amount |
| Dexterity | 버프 | 블록 +amount |
| Vulnerable | 디버프 | 받는 데미지 ×1.5 (지속) |
| Weak | 디버프 | 주는 데미지 ×0.75 (지속) |
| Frail | 디버프 | 받는 블록 ×0.75 (지속) |
| Burning | 디버프 | 턴 종료 시 HP -amount |
| Poison | 디버프 | 턴 종료 시 HP -amount (amount 감소) |
| Thorns | 버프 | 피격 시 반격 |
| Ritual | 버프 | 턴 시작 시 Strength +amount 부여 |
| Metallicize | 버프 | 턴 종료 시 블록 +amount 획득 |
| HexPower | 디버프 | 플레이어 카드 Ethereal 부여 (Phase 3) |
| TangledPower | 디버프 | 공격 카드 플레이 차단 (Phase 3) |
| ShackledPower | 디버프 | 모든 카드 플레이 차단 (Phase 3) |
| CurlUpPower | 버프 | 첫 피격 시 블록 획득 후 제거 (Phase 3) |

### 3. 카드 시스템 (`sts2_sim/models/sts2_card.py`)
- **STS2Card** 베이스 클래스
- CardType, Rarity 열거형
- 카드 팩토리 패턴

#### 구현된 카드 (10개)
| 카드 | 타입 | 비용 | 효과 |
|------|------|------|------|
| Strike | 공격 | 1 | 데미지 5(업그레이드: 6) |
| Defend | 스킬 | 1 | 블록 7(업그레이드: 8) |
| Bash | 공격 | 2 | 데미지 8(업그레이드: 10) + Vulnerable |
| Cleave | 공격 | 1 | 모든 적에게 데미지 14(업그레이드: 16) |
| HeavyBlade | 공격 | 3 | 데미지 29(업그레이드: 32) |
| Pummel | 공격 | 1 | 데미지 3×4(업그레이드: 4×4) |
| Shiv | 공격 | 0 | 데미지 4(업그레이드: 5), 소모 |
| QuickSlash | 공격 | 1 | 데미지 12(업그레이드: 16) |
| Acrobatics | 스킬 | 1 | 블록 7(업그레이드: 8) + 드로우 |
| Deflect | 스킬 | 1 | 블록 3(업그레이드: 4) |

## 🏗️ 아키텍처 설계

### 몬스터 상태 머신 패턴
```
MonsterMoveStateMachine
├─ states: List[MoveState]
│  ├─ name: 행동 이름
│  ├─ execute: Callable (비동기)
│  ├─ intent: Intent (UI 정보)
│  └─ follow_up_state: 다음 상태
└─ current_state

매 턴:
  1. get_current_intent() → UI 표시
  2. execute_move(targets) → 비동기 실행
  3. advance_state() → 다음 상태로
```

### 파워 효과 체계
```
데미지 계산:
  base_damage
  → Strength 적용 (공격자)
  → Weak 적용 (공격자, ×0.75)
  → Vulnerable 적용 (피격자, ×1.5)
  → 최종 데미지

블록 계산:
  base_block
  → Dexterity 적용
  → Frail 적용 (×0.75)
  → 최종 블록
```

## 🧪 테스트 커버리지
- ✅ 기본 몬스터 테스트 (11개)
- ✅ 파워 수정 로직 (14개 파워)
- ✅ 카드 사용 (10개 카드)
- ✅ 몬스터 상태 전환 (AxeRubyRaider)
- ✅ 통합 테스트 (몬스터 + 파워 + 카드)

모든 테스트 통과 ✅

## 📊 현황 요약

| 항목 | 개수 | 상태 |
|------|------|------|
| 몬스터 | 11 | ✅ 완성 |
| 파워 | 14 | ✅ 완성 |
| 카드 | 10 | ✅ 완성 |
| 렐릭 | 0 | ⏸️ Phase 2 |
| 캐릭터 | 0 | ⏸️ Phase 2 |

## 🚀 다음 단계 (Phase 2+)
- **Phase 2**: 렐릭 시스템, 더 많은 몬스터, 캐릭터 시스템
- **Phase 3**: Defect (Orb 시스템), Watcher (Stance 시스템)
- **Phase 4**: 맵 생성, 이벤트, 런 루프 통합
- **Phase 5**: AI 정책, MCTS, 통계 분석

## 🔧 파일 구조
```
sts2_sim/
├─ entities/
│  └─ sts2_monster.py       (몬스터 11개)
├─ models/
│  ├─ sts2_power.py         (파워 14개)
│  └─ sts2_card.py          (카드 10개)
└─ test_sts2_*.py           (통합 테스트)
```

## 📝 명령어

### 테스트 실행
```bash
python3 test_sts2_basic.py        # 기본 몬스터 테스트
python3 test_sts2_integration.py  # 통합 테스트 (몬스터 + 파워 + 카드)
```

### 디컬파일 데이터 분석
```bash
python3 bulk_extract_monsters.py  # 몬스터 메타데이터 추출
python3 extract_sts2_data.py      # 전체 데이터 추출
```

---
**작성 일시**: 2026-07-07  
**상태**: Phase 1 완료 ✅  
**다음 리뷰**: Phase 2 계획 수립 시
