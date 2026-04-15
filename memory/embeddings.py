"""Local embedding backends for reliable offline memory indexing."""

from __future__ import annotations

import hashlib
import math
from typing import Iterable


class LocalHashEmbeddingFunction:
    """Deterministic, no-download embedding function for Chroma.

    This avoids first-run stalls caused by remote model downloads.
    """

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def name(self) -> str:
        return "local_hash"

    def default_space(self) -> str:
        return "cosine"

    def __call__(self, input: Iterable[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in input]

    def embed_documents(self, texts: list[str] | None = None, **kwargs) -> list[list[float]]:
        docs = texts if texts is not None else kwargs.get("input", [])
        return [self._embed_text(text) for text in docs]

    def embed_query(self, text: str | None = None, **kwargs) -> list[list[float]]:
        q = text if text is not None else kwargs.get("input", "")
        if isinstance(q, list):
            q = q[0] if q else ""
        return [self._embed_text(q)]

    def _embed_text(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        tokens = text.lower().split()

        if not tokens:
            return vec

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (digest[5] / 255.0)
            vec[idx] += sign * weight

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


def get_embedding_function(backend: str, model_name: str):
    """Return an embedding function compatible with Chroma."""
    if backend == "sentence_transformer":
        from chromadb.utils import embedding_functions

        return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)

    return LocalHashEmbeddingFunction()
