from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol


class EmbeddingService(Protocol):
    def embed_text(self, text: str) -> list[float]: ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbeddingService:
    """Deterministic embedding stub for tests and local ingestion flows."""

    def __init__(self, dimensions: int = 12) -> None:
        self.dimensions = dimensions

    def embed_text(self, text: str) -> list[float]:
        values = [0.0] * self.dimensions
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        if not tokens:
            return values
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = digest[0] % self.dimensions
            sign = 1.0 if digest[1] % 2 == 0 else -1.0
            values[index] += sign * (1.0 + (digest[2] / 255.0))
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [round(value / norm, 6) for value in values]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(value * value for value in left)) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right)) or 1.0
    return max(0.0, min(1.0, (numerator / (left_norm * right_norm) + 1.0) / 2.0))
