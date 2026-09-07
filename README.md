# STS2 Simulator

Slay the Spire 2 헤드리스 Python 시뮬레이터.

`sts2.dll`(Godot + .NET/C# 빌드)을 디컴파일한 `decompiled/MegaCrit.Sts2.Core.*`를
기준으로 이식했습니다. 모든 수치는 원본 실제값(Ascension 미적용 기본값)이며,
런타임 코드는 **표준 라이브러리만** 사용합니다 (Python 3.11+).

## 구현 규모

| 시스템 | 개수 | 비고 |
|--------|------|------|
| 카드 | 503종 | Ironclad 85 / Silent 86 / Defect 86 / Necrobinder 82 / Regent 82 / Colorless 65 완전 이식 + 스타터·상태이상·토큰 |
| 파워 | 184종 | 데미지·블록·비용 수정, 카드 플레이/소모/생성 훅 배선 |
| 몬스터 | 91종 | 상태 머신 AI. 보스 SoulFysh / LagavulinMatriarch / WaterfallGiant / Vantom / KaiserCrab 포함 |
| 인카운터 | 69종 | 원본 `GenerateMonsters()` 구성 로직 재현 (미이식/자체 구성 4종은 코드 주석 표기) |
| 캐릭터 | 5종 | Ironclad / Silent / Defect / Necrobinder / Regent |
| 렐릭 | 22종 | 스타터 5종은 실제 동작 |
| 오브 | 5종 | Lightning / Frost / Dark / Plasma / Glass + OrbQueue |
| 테스트 | 28개 스위트 | 전부 통과, 시드 재현성 보장 |

원본(디컴파일) 대비 이식률은 전투 코어(카드·파워·몬스터·인카운터·오브)
약 **81%**, 런 콘텐츠(렐릭·포션·이벤트) 약 **5%**입니다. 현재 작업 위치는
**`S1.M3.B19 — 몬스터·인카운터 배치 19` 완료**이며, Stage·Milestone·Batch
ID 규약과 다음 작업은 [ROADMAP.md](ROADMAP.md), 세부 구현 현황은
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)를 참고하세요.

## 실행

테스트 스크립트는 이모지를 출력하므로 Windows에서는 UTF-8을 강제해야
`cp949` 인코딩 오류를 피할 수 있습니다.

```powershell
$env:PYTHONIOENCODING = "utf-8"
```

회귀 스위트 1개 실행:

```bash
python test_sts2_phase6n.py
```

루트 회귀 스위트 전체 실행 (첫 실패에서 중단):

```powershell
Get-ChildItem test_sts2_*.py | ForEach-Object {
    python $_.FullName
    if ($LASTEXITCODE -ne 0) { throw "Failed: $($_.Name)" }
}
```

시드 기반 다회 시뮬레이션:

```bash
python -m sts2_sim.core.stats ironclad 50 --policy greedy
python -m sts2_sim.core.stats ironclad 5 --policy greedy --verbose
```

`--verbose`는 앞 5회 런에 대해서만 턴/카드 단위 상세 로그를 남깁니다.

> 각 스위트는 `main()`으로 직접 실행되며 pytest로도 수집됩니다. 다만
> `pyproject.toml`의 `testpaths`가 `sts2_sim`을 가리키고 있어 인자 없는
> `pytest`로는 루트 스위트가 실행되지 않습니다 — 파일을 직접 지정하세요.

## 프로젝트 구조

```
sts2_sim/
├── cards/          # 캐릭터별 카드 (import 시 CARD_REGISTRY 등록)
│   ├── ironclad.py  silent.py  defect.py
│   └── necrobinder.py  regent.py  colorless.py
├── core/
│   ├── combat.py     # CombatState — 단일 전투 턴 루프의 오케스트레이션 경계
│   ├── encounters.py # 인카운터 ID → 시드 기반 몬스터 팩토리
│   ├── run.py        # RunState — 고정 층 시퀀스 런 루프
│   ├── policy.py     # GreedyPolicy (인텐트 인지 휴리스틱)
│   └── stats.py      # 다회 시드 집계
├── entities/
│   ├── creature.py       # HP/블록/파워/데미지 파이프라인 공유 베이스
│   ├── player.py  sts2_character.py
│   ├── sts2_monster.py   # MonsterModel + 무브 상태 머신
│   └── monsters_*.py     # 이식 배치별 몬스터
└── models/         # 카드/파워/렐릭/오브 모델 + 레지스트리
```

`import sts2_sim`이 카드 모듈을 전부 임포트하며, 각 모듈이 임포트 시점에
레지스트리를 채웁니다. 레지스트리 조회가 실패하면 해당 모듈이 임포트됐는지
먼저 확인하세요.

### 아키텍처 메모

- **파워 훅은 덕 타이핑**입니다. 전투/카드/몬스터 경로가 `on_turn_start`,
  `on_take_damage_powered`, `modify_hp_lost`, `on_any_death` 같은 선택적
  메서드를 `getattr`로 호출합니다. `hooks/hook_bus.py`는 레거시이며 살아있는
  동작은 이 경로를 타지 않습니다.
- **데미지 파이프라인 단계 순서**(Additive → Multiplicative → Cap → 블록 →
  HP 손실 수정)는 원본 `Hook.ModifyDamageInternal`을 따릅니다. 단계를 옮기면
  다단히트/피격 반응 동작이 달라집니다.
- **런 루프는 의도적으로 축소판**입니다. 고정 층 시퀀스를 쓰며 실제 맵 그래프,
  이벤트, 상점은 아직 구현하지 않았습니다.

## 관련 문서

- [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) — 시스템별 구현 현황과 검증 기록
- [ROADMAP.md](ROADMAP.md) — 단계별 진행 이력과 남은 계획
