#!/usr/bin/env python3
"""
자동 파서: 디컬파일된 STS2 C# 코드에서 게임 데이터 추출
- 몬스터 (HP, 클래스명)
- 파워 (ID, 이름, 훅)
- 카드 (효과, 비용)
- 렐릭 (훅, 효과)
- 캐릭터 (시작 스텟, 덱)
"""
import os
import re
import json
from pathlib import Path
from typing import Dict, List, Any

DECOMPILED_ROOT = Path("/workspaces/sts2-simulator/decompiled")


def extract_monsters() -> Dict[str, Dict[str, Any]]:
    """몬스터 클래스 메타데이터 추출."""
    # 개별 몬스터는 Models.Monsters에 있고, 인카운터(몬스터 그룹)는 Models.Encounters에 있음
    monsters_files = []

    # 두 디렉토리 모두 검사
    for monsters_dir_name in ["MegaCrit.Sts2.Core.Models.Monsters", "MegaCrit.Sts2.Core.Models.Encounters"]:
        monsters_dir = DECOMPILED_ROOT / monsters_dir_name
        if monsters_dir.exists():
            monsters_files.extend(sorted(monsters_dir.glob("*.cs")))

    monsters = {}

    for cs_file in monsters_files:
        try:
            content = cs_file.read_text(encoding='utf-8')

            # 클래스명 추출
            class_match = re.search(r'public (?:partial )?class (\w+)', content)
            if not class_match:
                continue

            class_name = class_match.group(1)
            meta = {"file": cs_file.name, "class_name": class_name}

            # MaxHp/MaxHealth 추출
            hp_patterns = [
                r'this\.MaxHp\s*=\s*(\d+)',
                r'MaxHealth\s*=\s*(\d+)',
                r'MaxHp\s*=>\s*(\d+)',
                r'"MaxHp":\s*(\d+)',
                r'(?:public|private)\s+int\s+MaxHp\s*=>\s*(\d+)',
            ]
            for pattern in hp_patterns:
                hp_match = re.search(pattern, content)
                if hp_match:
                    meta["max_hp"] = int(hp_match.group(1))
                    break

            # 메서드명 추출 (GetMoves, TakeTurn 등)
            methods = re.findall(r'(?:public|private|protected|internal)\s+(?:override\s+)?(?:async\s+)?\w+\s+(\w+)\s*\(', content)
            meta["methods"] = list(set(methods))[:10]  # 중복 제거, 처음 10개

            # Intent 또는 Move 관련 문자열 찾기
            move_names = re.findall(r'"(\w+)".*?(?:Move|Intent|ActionNames)', content)
            if move_names:
                meta["move_hints"] = move_names[:5]

            monsters[class_name] = meta
        except Exception as e:
            print(f"⚠️  {cs_file.name} 파싱 실패: {e}")

    return monsters


def extract_powers() -> Dict[str, Dict[str, Any]]:
    """파워 클래스 메타데이터 추출."""
    powers_dir = DECOMPILED_ROOT / "MegaCrit.Sts2.Core.Models.Powers"
    powers = {}

    if not powers_dir.exists():
        print(f"⚠️  파워 디렉토리 없음: {powers_dir}")
        return powers

    for cs_file in sorted(powers_dir.glob("*.cs")):
        try:
            content = cs_file.read_text(encoding='utf-8')

            class_match = re.search(r'public (?:partial )?class (\w+)', content)
            if not class_match:
                continue

            class_name = class_match.group(1)
            meta = {"file": cs_file.name, "class_name": class_name}

            # ID/PowerId 추출
            id_patterns = [
                r'(?:public\s+)?(?:const\s+)?string\s+\w*[Ii]d\s*=\s*"(\w+)"',
                r'PowerId\s*=\s*"(\w+)"',
            ]
            for pattern in id_patterns:
                id_match = re.search(pattern, content)
                if id_match:
                    meta["power_id"] = id_match.group(1)
                    break

            # 훅 메서드명 추출 (On*, Before*, After* 등)
            hook_methods = re.findall(
                r'(?:public|private|protected)\s+(?:override\s+)?(?:async\s+)?(?:void|Task|Task<\w+>)\s+((?:On|Before|After)\w+)\s*\(',
                content
            )
            if hook_methods:
                meta["hooks"] = list(set(hook_methods))

            # 이름 필드 추출
            name_match = re.search(r'(?:public\s+)?(?:const\s+)?string\s+\w*[Nn]ame\s*=\s*"([^"]+)"', content)
            if name_match:
                meta["name"] = name_match.group(1)

            powers[class_name] = meta
        except Exception as e:
            print(f"⚠️  {cs_file.name} 파싱 실패: {e}")

    return powers


def extract_characters() -> Dict[str, Dict[str, Any]]:
    """캐릭터 클래스 메타데이터 추출."""
    chars_dir = DECOMPILED_ROOT / "MegaCrit.Sts2.Core.Entities.Characters"
    characters = {}

    if not chars_dir.exists():
        print(f"⚠️  캐릭터 디렉토리 없음: {chars_dir}")
        return characters

    for cs_file in sorted(chars_dir.glob("*.cs")):
        try:
            content = cs_file.read_text(encoding='utf-8')

            class_match = re.search(r'public (?:partial )?class (\w+)', content)
            if not class_match:
                continue

            class_name = class_match.group(1)
            meta = {"file": cs_file.name, "class_name": class_name}

            # HP 추출
            hp_patterns = [
                r'(?:MaxHp|MaxHealth)\s*=\s*(\d+)',
                r'HP\s*=\s*(\d+)',
            ]
            for pattern in hp_patterns:
                hp_match = re.search(pattern, content)
                if hp_match:
                    meta["max_hp"] = int(hp_match.group(1))
                    break

            # 에너지/턴 에너지
            energy_match = re.search(r'(?:Energy|TurnEnergy)\s*=\s*(\d+)', content)
            if energy_match:
                meta["energy"] = int(energy_match.group(1))

            # 카드 풀 관련 메서드 찾기
            methods = re.findall(r'(?:public|private|protected)\s+(?:override\s+)?(?:List|IEnumerable)<\w+>\s+(\w+)\s*\(', content)
            if methods:
                meta["card_methods"] = list(set(methods))

            characters[class_name] = meta
        except Exception as e:
            print(f"⚠️  {cs_file.name} 파싱 실패: {e}")

    return characters


def extract_relics() -> Dict[str, Dict[str, Any]]:
    """렐릭 클래스 메타데이터 추출."""
    relics_dir = DECOMPILED_ROOT / "MegaCrit.Sts2.Core.Models.Relics"
    relics = {}

    if not relics_dir.exists():
        print(f"⚠️  렐릭 디렉토리 없음: {relics_dir}")
        return relics

    for cs_file in sorted(relics_dir.glob("*.cs"))[:50]:  # 처음 50개만 (너무 많을 수 있음)
        try:
            content = cs_file.read_text(encoding='utf-8')

            class_match = re.search(r'public (?:partial )?class (\w+)', content)
            if not class_match:
                continue

            class_name = class_match.group(1)
            meta = {"file": cs_file.name, "class_name": class_name}

            # ID 추출
            id_match = re.search(r'(?:public\s+)?(?:const\s+)?string\s+\w*[Ii]d\s*=\s*"(\w+)"', content)
            if id_match:
                meta["relic_id"] = id_match.group(1)

            # 훅 메서드 추출
            hook_methods = re.findall(
                r'(?:public|private|protected)\s+(?:override\s+)?(?:async\s+)?(?:void|Task|Task<\w+>)\s+((?:On|Before|After)\w+)\s*\(',
                content
            )
            if hook_methods:
                meta["hooks"] = list(set(hook_methods))

            relics[class_name] = meta
        except Exception as e:
            print(f"⚠️  {cs_file.name} 파싱 실패: {e}")

    return relics


def extract_orbs() -> Dict[str, Dict[str, Any]]:
    """Orb 클래스 메타데이터 추출 (Defect용)."""
    orbs_dir = DECOMPILED_ROOT / "MegaCrit.Sts2.Core.Models.Orbs"
    orbs = {}

    if not orbs_dir.exists():
        print(f"⚠️  Orb 디렉토리 없음: {orbs_dir}")
        return orbs

    for cs_file in sorted(orbs_dir.glob("*.cs")):
        try:
            content = cs_file.read_text(encoding='utf-8')

            class_match = re.search(r'public (?:partial )?class (\w+)', content)
            if not class_match:
                continue

            class_name = class_match.group(1)
            meta = {"file": cs_file.name, "class_name": class_name}

            # 훅 메서드
            hook_methods = re.findall(
                r'(?:public|private|protected)\s+(?:override\s+)?(?:void|Task)\s+((?:On|Before|After)\w+)\s*\(',
                content
            )
            if hook_methods:
                meta["hooks"] = list(set(hook_methods))

            orbs[class_name] = meta
        except Exception as e:
            print(f"⚠️  {cs_file.name} 파싱 실패: {e}")

    return orbs


def main():
    """메인: 모든 데이터 추출 및 저장."""
    print("🔍 STS2 디컬파일 코드에서 데이터 추출 중...")

    data = {
        "monsters": extract_monsters(),
        "powers": extract_powers(),
        "characters": extract_characters(),
        "relics": extract_relics(),
        "orbs": extract_orbs(),
    }

    # 통계
    print("\n📊 추출 결과:")
    print(f"  몬스터: {len(data['monsters'])}")
    print(f"  파워: {len(data['powers'])}")
    print(f"  캐릭터: {len(data['characters'])}")
    print(f"  렐릭: {len(data['relics'])}")
    print(f"  Orb: {len(data['orbs'])}")

    # JSON 저장
    output_file = Path("/tmp/sts2_extracted_data.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n✅ 추출 완료: {output_file}")

    # 샘플 출력
    if data['monsters']:
        print("\n📋 몬스터 샘플 (처음 3개):")
        for name, meta in list(data['monsters'].items())[:3]:
            print(f"  {name}: HP={meta.get('max_hp', '?')}, methods={meta.get('methods', [])[:3]}")

    if data['powers']:
        print("\n⚡ 파워 샘플 (처음 3개):")
        for name, meta in list(data['powers'].items())[:3]:
            print(f"  {name}: ID={meta.get('power_id', '?')}, hooks={meta.get('hooks', [])[:2]}")

    if data['characters']:
        print("\n👤 캐릭터 샘플:")
        for name, meta in data['characters'].items():
            print(f"  {name}: HP={meta.get('max_hp', '?')}, Energy={meta.get('energy', '?')}")

    return data


if __name__ == "__main__":
    main()
