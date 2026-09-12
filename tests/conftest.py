"""pytest가 tests/에서 수집할 때 저장소 패키지를 import할 수 있게 한다."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
