from typing import List, Any
from api.core.interfaces.chunking_strategy import ChunkingStrategy

class RecursiveChunkingStrategy(ChunkingStrategy):
    """
    Splits text recursively based on a list of separators.
    Defaults to LangChain-style recursive character splitting.
    """
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", " ", ""]

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        final_chunks = []
        separator = separators[-1]
        
        for s in separators:
            if s == "":
                separator = s
                break
            if s in text:
                separator = s
                break
                
        splits = text.split(separator) if separator != "" else list(text)
        
        current_chunk_text = ""
        
        for split in splits:
            # If a single split is larger than chunk_size, we need to split it further with the next separator
            if len(split) > self.chunk_size and len(separators) > 1:
                if current_chunk_text:
                    final_chunks.append(current_chunk_text.strip())
                    current_chunk_text = ""
                sub_chunks = self._split_text(split, separators[1:])
                final_chunks.extend(sub_chunks)
                continue
                
            if len(current_chunk_text) + len(separator) + len(split) > self.chunk_size:
                if current_chunk_text:
                    final_chunks.append(current_chunk_text.strip())
                current_chunk_text = split
            else:
                if current_chunk_text:
                    current_chunk_text += separator + split
                else:
                    current_chunk_text = split
                    
        if current_chunk_text:
            final_chunks.append(current_chunk_text.strip())
            
        return final_chunks

    def chunk(self, text: str, **kwargs: Any) -> List[str]:
        # Simple recursive implementation (without overlap logic for brevity in scaffolding, 
        # but overlap can be implemented by holding back the last tokens).
        chunks = self._split_text(text, self.separators)
        return [c for c in chunks if c]
