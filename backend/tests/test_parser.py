import io

import pytest
from docx import Document
from pypdf import PdfWriter

from app.resume.parser import parse_resume


def _docx_bytes(text: str) -> bytes:
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _empty_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_parse_docx_extracts_text():
    data = _docx_bytes("Python backend engineer with Postgres")
    assert "Python backend engineer" in parse_resume("resume.docx", data)


def test_unsupported_extension_raises():
    with pytest.raises(ValueError):
        parse_resume("resume.txt", b"hello")


def test_empty_pdf_returns_empty_string_no_crash():
    assert parse_resume("resume.pdf", _empty_pdf_bytes()) == ""


def test_malformed_pdf_raises_value_error():
    # A file named .pdf but holding garbage must surface as a domain ValueError,
    # not leak pypdf's PdfStreamError (which the API layer wouldn't translate).
    with pytest.raises(ValueError):
        parse_resume("resume.pdf", b"this is not a pdf at all")


def test_malformed_docx_raises_value_error():
    # Likewise a fake .docx must not leak zipfile.BadZipFile.
    with pytest.raises(ValueError):
        parse_resume("resume.docx", b"this is not a docx at all")
