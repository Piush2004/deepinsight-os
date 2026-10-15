from abc import ABC, abstractmethod
from typing import Dict, Any
from uuid import UUID

class KnowledgeQueryService(ABC):
    """Abstract interface for high-level knowledge queries."""
    
    @abstractmethod
    def query(self, question: str, client_id: UUID, context_filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Perform a knowledge query (e.g. RAG retrieval)."""
        pass
