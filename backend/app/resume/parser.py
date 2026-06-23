import io

from docx import Document
from pypdf import PdfReader


def _parse_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    parts = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(parts)


def _parse_docx(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)


def parse_resume(filename: str, data: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        text = _parse_pdf(data)
    elif lower.endswith(".docx"):
        text = _parse_docx(data)
    else:
        raise ValueError(f"Unsupported resume format: {filename}")
    return " ".join(text.split())
