"""Embedding provider abstraction with OpenAI-compatible, DashScope, and Ark paths."""

import hashlib
from urllib.parse import urlparse
from typing import Any
from abc import ABC, abstractmethod

from app.core.config import settings
from app.services.runtime_configuration_service import effective_embedding_configuration


class EmbeddingProvider(ABC):
    """Abstract embedding provider."""

    @abstractmethod
    def embed(self, text: str | list[str]) -> list[list[float]]:
        """Generate embeddings. Returns one vector per input text."""
        ...

    @abstractmethod
    def embed_strict(self, text: str | list[str]) -> list[list[float]]:
        """Generate embeddings without deterministic fallback."""
        ...

    @property
    @abstractmethod
    def is_fallback(self) -> bool:
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...


def _target_embedding_dimensions() -> int:
    configured = effective_embedding_configuration()["dimensions"]
    return configured if configured > 0 else 768


def _normalize_vector(vector: list[float]) -> list[float]:
    """Pad or truncate provider output to the configured embedding dimension."""
    dim = _target_embedding_dimensions()
    return vector[:dim] if len(vector) >= dim else vector + [0.0] * (dim - len(vector))


class DeterministicEmbeddingFallback(EmbeddingProvider):
    """Deterministic deterministic fallback embedding using SHA256 hash.

    Not cryptographically meaningful but produces stable, repeatable
    vectors for the same input text. Clearly marked as a local fallback.
    """

    @property
    def is_fallback(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "deterministic_fallback"

    def embed(self, text: str | list[str]) -> list[list[float]]:
        texts = [text] if isinstance(text, str) else text
        results = []
        for t in texts:
            vec = self._hash_to_vector(t)
            results.append(vec)
        return results

    def embed_strict(self, text: str | list[str]) -> list[list[float]]:
        raise RuntimeError("deterministic embedding fallback cannot be used in strict mode")

    def _hash_to_vector(self, text: str) -> list[float]:
        vec = []
        for i in range(_target_embedding_dimensions()):
            seed = text + str(i)
            h = hashlib.sha256(seed.encode()).digest()
            val = sum(h) / (256 * len(h))
            vec.append(val)
        # Normalize to unit length
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """Real embedding via OpenAI-compatible API.

    Falls back to deterministic local vectors if not configured.
    """

    def __init__(self):
        configuration = effective_embedding_configuration()
        self._base_url = str(configuration["base_url"]).rstrip("/")
        self._model = configuration["model"] or "text-embedding-3-small"
        self._api_key = configuration["api_key"]
        self._configured = bool(self._api_key and self._base_url)
        self._fallback = DeterministicEmbeddingFallback()

    @property
    def is_fallback(self) -> bool:
        return not self._configured

    @property
    def provider_name(self) -> str:
        return "openai_compatible" if self._configured else "deterministic_fallback"

    def embed(self, text: str | list[str]) -> list[list[float]]:
        try:
            return self.embed_strict(text)
        except Exception:
            return self._fallback.embed(text)

    def embed_strict(self, text: str | list[str]) -> list[list[float]]:
        if not self._configured:
            raise RuntimeError("OpenAI-compatible embedding provider is not configured")

        import httpx

        texts = [text] if isinstance(text, str) else text
        resp = httpx.post(
            f"{self._base_url}/embeddings",
            json={
                "model": self._model,
                "input": texts,
            },
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=settings.EMBEDDING_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        vectors = [d["embedding"] for d in data["data"]]
        return [_normalize_vector(v) for v in vectors]


def _derive_dashscope_api_base(embedding_base_url: str) -> str:
    """Map compatible-mode URL to DashScope native API host."""
    base = (embedding_base_url or settings.DASHSCOPE_EMBEDDING_BASE_URL or "").strip().rstrip("/")
    if not base:
        return ""
    if "/compatible-mode/v1" in base:
        return base.replace("/compatible-mode/v1", "")
    parsed = urlparse(base)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return base


class DashScopeMultimodalEmbeddingProvider(EmbeddingProvider):
    """DashScope native multimodal embedding provider.

    Supports text-only input for memory retrieval and can be extended to
    image/video payloads later.
    """

    def __init__(self):
        configuration = effective_embedding_configuration()
        self._base_url = _derive_dashscope_api_base(configuration["base_url"])
        self._api_key = configuration["api_key"]
        self._model = configuration["model"]
        self._configured = bool(self._api_key and self._base_url and self._model)
        self._fallback = DeterministicEmbeddingFallback()

    @property
    def is_fallback(self) -> bool:
        return not self._configured

    @property
    def provider_name(self) -> str:
        return "dashscope_multimodal" if self._configured else "deterministic_fallback"

    def embed(self, text: str | list[str]) -> list[list[float]]:
        try:
            return self.embed_strict(text)
        except Exception:
            return self._fallback.embed(text)

    def embed_strict(self, text: str | list[str]) -> list[list[float]]:
        if not self._configured:
            raise RuntimeError("DashScope multimodal embedding provider is not configured")

        import httpx

        texts = [text] if isinstance(text, str) else text
        return [self._embed_one_text(httpx, t) for t in texts]

    def _embed_one_text(self, httpx_module: Any, text: str) -> list[float]:
        url = (
            f"{self._base_url}"
            "/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding"
        )
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "input": {"contents": [{"text": text}]},
            "parameters": {"dimension": _target_embedding_dimensions()},
        }

        try:
            resp = httpx_module.post(
                url,
                json=payload,
                headers=headers,
                timeout=settings.EMBEDDING_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
        except Exception:
            # Some models or regions do not accept dimension override.
            payload.pop("parameters", None)
            resp = httpx_module.post(
                url,
                json=payload,
                headers=headers,
                timeout=settings.EMBEDDING_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()

        data = resp.json()
        raw = (
            data.get("output", {})
            .get("embeddings", [{}])[0]
            .get("embedding")
        )
        if not isinstance(raw, list):
            raise ValueError("DashScope embedding response missing output.embeddings[0].embedding")

        return _normalize_vector(raw)


class VolcengineArkEmbeddingProvider(EmbeddingProvider):
    """Volcengine Ark SDK multimodal embedding provider.

    Doubao vision embedding models must use Ark's native multimodal embedding
    route instead of the OpenAI-compatible embeddings adapter.
    """

    DEFAULT_MODEL = "doubao-embedding-vision-251215"

    def __init__(self):
        configuration = effective_embedding_configuration()
        self._api_key = configuration["api_key"]
        self._base_url = str(configuration["base_url"] or "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
        self._model = configuration["model"] or self.DEFAULT_MODEL
        self._configured = bool(self._api_key and self._model)
        self._fallback = DeterministicEmbeddingFallback()
        self._client: Any | None = None

    @property
    def is_fallback(self) -> bool:
        return not self._configured

    @property
    def provider_name(self) -> str:
        return "volcengine_ark" if self._configured else "deterministic_fallback"

    def embed(self, text: str | list[str]) -> list[list[float]]:
        try:
            return self.embed_strict(text)
        except Exception:
            return self._fallback.embed(text)

    def embed_strict(self, text: str | list[str]) -> list[list[float]]:
        if not self._configured:
            raise RuntimeError("Volcengine Ark embedding provider is not configured")

        texts = [text] if isinstance(text, str) else text
        return [self._embed_one_text(t) for t in texts]

    def _get_client(self) -> Any:
        if self._client is None:
            from volcenginesdkarkruntime import Ark

            self._client = Ark(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=settings.EMBEDDING_TIMEOUT_SECONDS,
                max_retries=settings.EMBEDDING_MAX_RETRIES,
            )
        return self._client

    def _embed_one_text(self, text: str) -> list[float]:
        resp = self._get_client().multimodal_embeddings.create(
            model=self._model,
            input=[{"type": "text", "text": text}],
            dimensions=_target_embedding_dimensions(),
        )
        raw = self._extract_embedding(resp)
        return _normalize_vector(raw)

    @staticmethod
    def _extract_embedding(resp: Any) -> list[float]:
        data = resp.get("data") if isinstance(resp, dict) else getattr(resp, "data", None)
        embedding = None
        if isinstance(data, dict):
            embedding = data.get("embedding")
        elif data is not None:
            embedding = getattr(data, "embedding", None)

        if embedding is None and isinstance(resp, dict):
            embedding = resp.get("embedding")
        elif embedding is None:
            embedding = getattr(resp, "embedding", None)

        if not isinstance(embedding, list):
            raise ValueError("Ark embedding response missing data.embedding")

        return [float(value) for value in embedding]


def _select_embedding_provider_name() -> str:
    configuration = effective_embedding_configuration()
    configured = str(configuration["provider"] or "auto").strip().lower()
    if configured in ("openai_compatible", "dashscope_multimodal", "volcengine_ark"):
        return configured

    model = str(configuration["model"] or "").strip().lower()
    if model.startswith("doubao-embedding-vision"):
        return "volcengine_ark"
    if (
        model.startswith("tongyi-embedding-vision")
        or model.startswith("qwen3-vl-embedding")
        or model.startswith("qwen2.5-vl-embedding")
    ):
        return "dashscope_multimodal"
    return "openai_compatible"


# Singleton
_provider: EmbeddingProvider | None = None
_provider_revision: int | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _provider, _provider_revision
    configuration = effective_embedding_configuration()
    revision = int(configuration["revision"])
    if _provider is None or _provider_revision != revision:
        provider_name = _select_embedding_provider_name()
        if provider_name == "volcengine_ark":
            _provider = VolcengineArkEmbeddingProvider()
        elif provider_name == "dashscope_multimodal":
            _provider = DashScopeMultimodalEmbeddingProvider()
        else:
            _provider = OpenAICompatibleEmbeddingProvider()
        _provider_revision = revision
    return _provider


def embed_text(text: str) -> list[float]:
    """Convenience: embed a single text, return one vector."""
    return get_embedding_provider().embed(text)[0]
