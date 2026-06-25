# src/rag/embedder.py
"""
Embeddings via Gemini Embedding 2 (gemini-embedding-2) @ 1536 dims.
The dimension MUST equal db_models.EMBED_DIM (the pgvector column size).

Set GEMINI_API_KEY in .env. For offline testing pass mock=True (deterministic
pseudo-vectors) so the pipeline can be verified without network/quota.
"""
import os, hashlib
from typing import Literal

try:
    from src.utils.db_models import EMBED_DIM
except Exception:
    EMBED_DIM = 1536

MODEL = "gemini-embedding-2"


class Embedder:
    def __init__(self, mock: bool = False, model: str = MODEL, dim: int = EMBED_DIM):
        self.mock, self.model, self.dim = mock, model, dim
        self._client = None
        if not mock:
            from google import genai
            self._client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def _mock_vec(self, text: str):
        # deterministic unit-ish vector from text hash (testing only)
        import struct
        seed = hashlib.sha256(text.encode()).digest()
        vals, i = [], 0
        while len(vals) < self.dim:
            b = hashlib.sha256(seed + str(i).encode()).digest()
            for j in range(0, len(b), 4):
                if len(vals) >= self.dim:
                    break
                vals.append((struct.unpack("I", b[j:j+4])[0] / 2**32) - 0.5)
            i += 1
        n = sum(v*v for v in vals) ** 0.5 or 1.0
        return [v / n for v in vals]

    def embed(self, text: str, task: Literal["retrieval_document", "retrieval_query"] = "retrieval_document"):
        if self.mock:
            return self._mock_vec(text)
        from google.genai import types
        resp = self._client.models.embed_content(
            model=self.model,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=self.dim,
                task_type="RETRIEVAL_DOCUMENT" if task == "retrieval_document" else "RETRIEVAL_QUERY",
            ),
        )
        return list(resp.embeddings[0].values)