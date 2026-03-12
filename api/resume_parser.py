"""Extract text from resume PDF or DOCX using free open-source libraries."""
import io
from pathlib import Path

import pdfplumber
from docx import Document


def extract_text_from_pdf(content: bytes) -> str:
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        parts = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
        return "\n\n".join(parts) if parts else ""


def extract_text_from_docx(content: bytes) -> str:
    doc = Document(io.BytesIO(content))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_resume_text(content: bytes, filename: str) -> str:
    suf = Path(filename).suffix.lower()
    if suf == ".pdf":
        return extract_text_from_pdf(content)
    if suf in (".docx", ".doc"):
        return extract_text_from_docx(content)
    raise ValueError(f"Unsupported file type: {suf}. Use PDF or DOCX.")
