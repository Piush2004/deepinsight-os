from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_upload_document_requires_auth():
    # Should fail without token
    response = client.post("/api/v1/documents/upload", files={"file": ("test.txt", b"hello world", "text/plain")})
    assert response.status_code in [401, 403]

def test_get_documents_requires_auth():
    response = client.get("/api/v1/documents")
    assert response.status_code in [401, 403]

def test_knowledge_pipeline_interface_mocking():
    """
    This test verifies that the pipeline services can be instantiated with mocked interfaces.
    """
    from api.services.knowledge.pipeline import DocumentUploadService, ValidationService, MetadataService, ExtractionService, CleaningService, ChunkingService, EmbeddingService, StorageService, VerificationService
    from api.core.interfaces.chunking_strategy import ChunkingStrategy
    from api.core.interfaces.embedding_provider import EmbeddingProvider
    from api.core.interfaces.vector_store import VectorStore
    from api.core.interfaces.document_loader import DocumentLoader
    from typing import List, Dict, Any, BinaryIO
    
    class MockLoader(DocumentLoader):
        def load(self, file: BinaryIO, **kwargs: Any) -> Dict[str, Any]:
            return {"text": "mock text", "metadata": {}}
            
    class MockChunking(ChunkingStrategy):
        def chunk(self, text: str, **kwargs: Any) -> List[str]:
            return ["mock chunk"]
            
    class MockEmbedding(EmbeddingProvider):
        def embed_text(self, text: str) -> List[float]: return [0.1]
        def embed_batch(self, texts: List[str]) -> List[List[float]]: return [[0.1]]
        
    class MockVectorStore(VectorStore):
        def add_documents(self, documents: List[Dict[str, Any]], client_id: str) -> None: pass
        def similarity_search(self, q: List[float], cid: str, k: int=5, f: dict=None) -> List[Dict[str, Any]]: return []
        def delete_by_document_id(self, did: str, cid: str) -> None: pass
        
    # Instantiate Pipeline
    upload_service = DocumentUploadService(
        db=None,
        validation=ValidationService(),
        metadata=MetadataService(),
        extraction=ExtractionService(MockLoader()),
        cleaning=CleaningService(),
        chunking=ChunkingService(MockChunking()),
        embedding=EmbeddingService(MockEmbedding()),
        storage=StorageService(MockVectorStore(), db=None),
        verification=VerificationService(db=None)
    )
    
    assert upload_service is not None
