from typing import BinaryIO, Dict, Any
from api.core.interfaces.document_loader import DocumentLoader

class TextLoader(DocumentLoader):
    def load(self, file: BinaryIO, **kwargs: Any) -> Dict[str, Any]:
        content = file.read().decode('utf-8')
        return {
            "text": content,
            "metadata": {"type": "text/plain"}
        }

class MarkdownLoader(DocumentLoader):
    def load(self, file: BinaryIO, **kwargs: Any) -> Dict[str, Any]:
        content = file.read().decode('utf-8')
        return {
            "text": content,
            "metadata": {"type": "text/markdown"}
        }

class PDFLoader(DocumentLoader):
    def load(self, file: BinaryIO, **kwargs: Any) -> Dict[str, Any]:
        try:
            import pypdf
        except ImportError:
            raise RuntimeError("pypdf is required to read PDFs.")
            
        pdf_reader = pypdf.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
            
        return {
            "text": text,
            "metadata": {
                "type": "application/pdf",
                "pages": len(pdf_reader.pages)
            }
        }


LOADERS_BY_MIME_TYPE = {
    "text/plain": TextLoader,
    "text/markdown": MarkdownLoader,
    "application/pdf": PDFLoader,
}


def get_loader_for_mime_type(mime_type: str) -> DocumentLoader:
    loader_cls = LOADERS_BY_MIME_TYPE.get(mime_type)
    if not loader_cls:
        raise ValueError(f"No loader available for mime type '{mime_type}'.")
    return loader_cls()
