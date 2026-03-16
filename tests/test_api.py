from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_api_modules_importable():
    from backend.api import jobs, ingestion, feedback  # noqa: F401
