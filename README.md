# STS2 Simulator

Slay the Spire 2 헤드리스 Python 시뮬레이터

`sts2.dll` (Godot + .NET/C# 빌드) 분석을 바탕으로 구현한 게임 엔진입니다.

## 구현 내용

- **전투 엔진**: SeededRng(Java Random 호환 48-bit LCG), HookBus(Before/After 훅 97개), CombatManager(yield 기반)
- **캐릭터**: Ironclad, Silent
- **카드**: Ironclad 50+장, Silent 20+장
- **몬스터**: Act 1~3 (Jawworm, SlimeBoss, GremlinNob, TheChamp, DonuDeca 등)
- **유물**: BurningBlood 포함 17종
- **파워**: Strength, Dexterity, Vulnerable, Weak, Frail, Poison 등
- **맵**: 3-Act × 17층 구조, 전투/이벤트/상점/휴식/보물/보스 룸
- **이벤트**: 10종 (big_fish, shining_light, the_cleric 등)
- **풀 런**: 3-Act 연속 플레이스루 지원

## 실행

```bash
cd sts2_sim
python -m pytest test_full_run.py -v
```

## 프로젝트 구조

```
sts2_sim/
├── cards/          # 캐릭터별 카드 구현
├── core/           # 전투 엔진, 런 루프
├── entities/       # Player, Monster
├── hooks/          # HookBus
├── map/            # ActMap, 이벤트, 상점
├── models/         # 카드/파워 모델
├── relics/         # 유물
└── rng/            # SeededRng
```
