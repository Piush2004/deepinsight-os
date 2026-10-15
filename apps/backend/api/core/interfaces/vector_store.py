from abc import ABC, abstractmethod
from typing import List, Any, Dict, Optional

class VectorStore(ABC):
    """Abstract interface for all vector databases (e.g. PgVector, Pinecone, Milvus)"""
    
    @abstractmethod
    def add_documents(self, documents: List[Dict[str, Any]], client_id: str) -> None:
        """Store documents with their embeddings. Must enforce client_id separation."""
        pass
        
    @abstractmethod
    def similarity_search(
        self, 
        query_embedding: List[float], 
        client_id: str, 
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve most similar documents for a specific client."""
        pass
        
    @abstractmethod
    def delete_by_document_id(self, document_id: str, client_id: str) -> None:
        """Delete all vector chunks associated with a specific document ID."""
        pass
