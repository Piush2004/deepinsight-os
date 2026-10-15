from abc import ABC, abstractmethod
from typing import List

class EmbeddingProvider(ABC):
    """Abstract interface for all embedding models (e.g. BGE, OpenAI, Cohere)"""
    
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Embed a single string."""
        pass
        
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of strings."""
        pass
