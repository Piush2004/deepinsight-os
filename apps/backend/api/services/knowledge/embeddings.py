import hashlib
import logging
import math
from typing import List

from api.core.interfaces.embedding_provider import EmbeddingProvider

logger = logging.getLogger(__name__)

# For a production BGE-M3 provider, you would typically use FlagEmbedding or sentence-transformers.
# In a real deployed environment, the model weights would be loaded once during app startup or as a microservice.

BGE_M3_DIMENSION = 1024


class BGEEmbeddingProvider(EmbeddingProvider):
    """
    Concrete implementation of EmbeddingProvider using BAAI/bge-m3.
    """
    def __init__(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer('BAAI/bge-m3')
        except ImportError:
            self.model = None
            # Fallback or error handling for environments where the model isn't downloaded

    def embed_text(self, text: str) -> List[float]:
        if not self.model:
            raise RuntimeError("SentenceTransformer is not installed or model failed to load.")
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not self.model:
            raise RuntimeError("SentenceTransformer is not installed or model failed to load.")
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()


class LocalHashingEmbeddingProvider(EmbeddingProvider):
    """
    Zero-dependency, fully local embedding provider using feature hashing over character
    n-grams, projected onto BGE_M3_DIMENSION and L2-normalized so it is drop-in compatible
    with the pgvector column and cosine-distance queries used elsewhere.

    This is a real (if lower-quality than a trained model) embedding technique - not a
    mock. It exists so retrieval works end-to-end on any machine with no GPU, no model
    download, and no paid API, per the project's free/local-first, model-agnostic rule.
    Swap in BGEEmbeddingProvider (or any other EmbeddingProvider) wherever better
    semantic quality is needed - both implement the exact same interface.
    """

    def __init__(self, dimension: int = BGE_M3_DIMENSION, ngram_size: int = 3):
        self.dimension = dimension
        self.ngram_size = ngram_size

    def _ngrams(self, text: str) -> List[str]:
        normalized = text.lower()
        if len(normalized) < self.ngram_size:
            return [normalized] if normalized else []
        return [normalized[i:i + self.ngram_size] for i in range(len(normalized) - self.ngram_size + 1)]

    def embed_text(self, text: str) -> List[float]:
        vector = [0.0] * self.dimension
        for gram in self._ngrams(text):
            digest = hashlib.sha256(gram.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            return vector
        return [v / norm for v in vector]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


def get_embedding_provider() -> EmbeddingProvider:
    """Prefers the real BGE-M3 model; falls back to the local hashing provider (with a
    loud warning) if sentence-transformers/the model weights aren't available, so
    ingestion and retrieval degrade gracefully instead of hard-failing."""
    try:
        provider = BGEEmbeddingProvider()
        if provider.model is not None:
            return provider
        logger.warning(
            "sentence-transformers/BGE-M3 unavailable - falling back to "
            "LocalHashingEmbeddingProvider. Retrieval will work but with lower semantic "
            "quality. Install sentence-transformers and the BAAI/bge-m3 weights for "
            "production-quality embeddings."
        )
    except Exception:
        logger.warning("BGEEmbeddingProvider failed to initialize - falling back to LocalHashingEmbeddingProvider.", exc_info=True)
    return LocalHashingEmbeddingProvider()
