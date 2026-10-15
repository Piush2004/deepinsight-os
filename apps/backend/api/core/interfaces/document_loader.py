from abc import ABC, abstractmethod
from typing import BinaryIO, Dict, Any

class DocumentLoader(ABC):
    """Abstract interface for extracting raw text from various file formats"""
    
    @abstractmethod
    def load(self, file: BinaryIO, **kwargs: Any) -> Dict[str, Any]:
        """
        Parse binary file and return a dict containing:
        - 'text': Extracted raw string
        - 'metadata': Any format-specific metadata (e.g. pages, headers)
        """
        pass
