import pytest

from app.memory.embedding import DeterministicEmbeddingFallback


def test_deterministic_embedding_fallback_rejects_strict_mode() -> None:
    with pytest.raises(RuntimeError):
        DeterministicEmbeddingFallback().embed_strict("memory")
