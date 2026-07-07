#!/usr/bin/env python3
"""
STS2 몬스터 메타데이터 대량 추출 (Python 코드 생성용).
디컬파일 코드 읽고 Python 클래스 스텁 생성.
"""
import re
from pathlib import Path

MONSTERS_DIR = Path("/workspaces/sts2-simulator/decompiled/MegaCrit.Sts2.Core.Models.Monsters")

def extract_monster_hp(content: str) -> tuple[int, int]:
    """MinInitialHp, MaxInitialHp 추출."""
    min_hp = 0
    max_hp = 0

    # MinInitialHp 추출
    min_match = re.search(r'MinInitialHp\s*=>\s*(\d+)', content)
    if min_match:
        min_hp = int(min_match.group(1))

    # MaxInitialHp 추출 (없으면 MinInitialHp와 같음)
    max_match = re.search(r'MaxInitialHp\s*=>\s*(\d+)', content)
    if max_match:
        max_hp = int(max_match.group(1))
    elif min_hp > 0:
        max_hp = min_hp

    return min_hp, max_hp


def extract_monster_class_name(content: str) -> str:
    """클래스명 추출."""
    match = re.search(r'public sealed class (\w+)', content)
    return match.group(1) if match else "Unknown"


def generate_monster_class(class_name: str, min_hp: int, max_hp: int) -> str:
    """Python 몬스터 클래스 코드 생성."""
    if min_hp == 0:
        min_hp = 10
        max_hp = 10

    snake_name = re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower()
    human_name = re.sub(r'([A-Z])', r' \1', class_name).strip()

    code = f'''
class {class_name}(MonsterModel):
    """{human_name}."""
    monster_id = "{snake_name}"
    title = "{human_name}"

    @property
    def min_initial_hp(self) -> int:
        return {min_hp}

    @property
    def max_initial_hp(self) -> int:
        return {max_hp}

    def generate_move_state_machine(self) -> MonsterMoveStateMachine:
        # TODO: 구체적인 행동 정의
        idle_state = MoveState("IDLE", self._idle_move, Intent(IntentType.HIDDEN))
        idle_state.follow_up_state = idle_state
        return MonsterMoveStateMachine([idle_state], idle_state)

    async def _idle_move(self, targets: List[Creature]) -> None:
        """기본 행동 (구현 필요)."""
        pass
'''
    return code


def main():
    """메인."""
    monsters_data = []

    for cs_file in sorted(MONSTERS_DIR.glob("*.cs")):
        try:
            content = cs_file.read_text(encoding='utf-8')
            class_name = extract_monster_class_name(content)
            min_hp, max_hp = extract_monster_hp(content)

            if min_hp > 0 and class_name != "Unknown":
                monsters_data.append((class_name, min_hp, max_hp))
        except Exception as e:
            pass

    # 상위 20개만 추출 (간단한 몬스터부터)
    monsters_data = sorted(monsters_data, key=lambda x: x[1])[:20]

    print(f"# 추출된 몬스터 {len(monsters_data)}개:\n")
    for class_name, min_hp, max_hp in monsters_data:
        print(f"# {class_name}: HP {min_hp}~{max_hp}")

    print("\n\n# 생성된 Python 코드:\n")
    for class_name, min_hp, max_hp in monsters_data:
        code = generate_monster_class(class_name, min_hp, max_hp)
        print(code)

    return monsters_data


if __name__ == "__main__":
    main()
