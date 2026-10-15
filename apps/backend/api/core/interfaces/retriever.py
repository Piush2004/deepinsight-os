from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from uuid import UUID

class Retriever(ABC):
    """Abstract interface for retrieving documents from the vector store."""
    
    @abstractmethod
    def retrieve(self, query: str, client_id: UUID, top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Retrieve relevant document chunks based on a query."""
        pass
