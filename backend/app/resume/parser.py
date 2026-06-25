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
        parser = _parse_pdf
    elif lower.endswith(".docx"):
        parser = _parse_docx
    else:
        raise ValueError(f"Unsupported resume format: {filename}")
    # Normalize library failures (pypdf.PdfStreamError, zipfile.BadZipFile, …) on
    # a corrupt/mismatched file into one domain ValueError, so the API layer's
    # single `except ValueError` translates BOTH "bad extension" and "bad bytes"
    # into a clean 400 instead of leaking a 500.
    try:
        text = parser(data)
    except Exception as exc:  # noqa: BLE001 - deliberate boundary normalization
        raise ValueError(f"Could not read resume file: {filename}") from exc
    return " ".join(text.split())
