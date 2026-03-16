from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_retrieval_services_importable():
    from backend.services.retrieval_service import RetrievalService  # noqa: F401
    from backend.services.hybrid_retriever import HybridRetriever  # noqa: F401
