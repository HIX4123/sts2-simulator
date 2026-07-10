# STS2 시뮬레이터 — 구현 현황

`sts2.dll` 디컴파일 데이터 기반 헤드리스 Slay the Spire 2 시뮬레이터.
모든 수치는 `decompiled/MegaCrit.Sts2.Core.*`에서 추출한 실제값 (Ascension 미적용 기본값).

## 📊 규모 요약

| 시스템 | 개수 | 비고 |
|--------|------|------|
| 몬스터 | 34종 | 상태 머신 AI, 실제 HP/데미지 |
| 인카운터 | 12종 | 실제 구성 로직 (부분 구성 3종은 주석 표기) |
| 캐릭터 | 5종 | Ironclad / Silent / Defect / Necrobinder / Regent |
| 카드 | 16종 | 스타터 전량 + 상태이상 (STS2 전체 593종) |
| 파워 | 18종 | Plating/Artifact/Tangled 등 전투 배선 완료 |
| 렐릭 | 22종 | 스타터 5종은 실제 동작 |
| 오브 | 5종 | Lightning/Frost/Dark/Plasma/Glass + OrbQueue |
| 테스트 | 7개 스위트 | 전부 통과, 시드 재현성 보장 |

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
│  ├─ sts2_power.py      # 파워 18종
│  ├─ sts2_card.py       # 카드 16종
│  ├─ sts2_relic.py      # 렐릭 22종
│  └─ sts2_orb.py        # 오브 5종 + OrbQueue
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

런 완주(7층, 엘리트 피날레)는 현 카드 풀 16종으로는 실제 3기사 엘리트를 넘기 어려움 —
카드 풀 확대(Phase 6b)가 승률의 병목.

## 🔬 생성 방법론 (Phase 6a)

몬스터 17종은 멀티에이전트 파이프라인으로 이식:
1. **이식 에이전트** — 디컴파일 .cs와 기존 패턴을 읽고 Python 클래스 생성
2. **검증 에이전트** — 원본과 수치/상태그래프 적대 대조 (LeafSlimeS 시드 재현성 버그,
   SpectralKnight CanRepeatXTimes 전개 오류를 잡아 수정)
3. **수동 대조** — 세션 한도로 미검증된 13종을 원본 소스와 직접 대조 (전부 일치 확인)

## 🚀 다음 단계

ROADMAP.md의 Phase 6b+ 참조 — 몬스터 잔여 ~87종, 카드 풀 확대(593종),
렐릭/포션 풀, 미이식 파워(Galvanic/Rampart/Dampen/HighVoltage), Ascension, 실제 맵 그래프.
