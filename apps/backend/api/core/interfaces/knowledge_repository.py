from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from api.models.knowledge import Document, DocumentVersion

class KnowledgeRepository(ABC):
    """Abstract interface for interacting with knowledge domain models."""
    
    @abstractmethod
    def get_document(self, document_id: UUID, client_id: UUID) -> Optional[Document]:
        pass
        
    @abstractmethod
    def list_documents(self, client_id: UUID, skip: int = 0, limit: int = 100) -> List[Document]:
        pass
        
    @abstractmethod
    def delete_document(self, document_id: UUID, client_id: UUID) -> bool:
        pass
        
    @abstractmethod
    def create_new_version(self, document_id: UUID, client_id: UUID) -> DocumentVersion:
        """Create a new version for an existing document."""
        pass
