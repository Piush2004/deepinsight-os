from abc import ABC, abstractmethod
from typing import List, Any

class ChunkingStrategy(ABC):
    """Abstract interface for all document chunking strategies"""
    
    @abstractmethod
    def chunk(self, text: str, **kwargs: Any) -> List[str]:
        """Split a raw text string into manageable chunks."""
        pass
