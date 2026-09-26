from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PdfParseResult:
    text: str
    pages: list[str] = field(default_factory=list)
    needs_manual_review: bool = False
    parse_error: str | None = None


def parse_pdf_bytes(data: bytes) -> PdfParseResult:
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover
        return PdfParseResult(text="", needs_manual_review=True, parse_error=f"missing_dependency:{exc.name}")

    try:
        doc = fitz.open(stream=data, filetype="pdf")
        pages = [page.get_text("text").strip() for page in doc]
    except Exception as exc:  # pragma: no cover
        return PdfParseResult(text="", needs_manual_review=True, parse_error=f"pdf_parse_error:{type(exc).__name__}")

    text = "\n\n".join(page for page in pages if page)
    if len(text.strip()) < 30:
        return PdfParseResult(text=text, pages=pages, needs_manual_review=True, parse_error="scanned_or_unreadable_pdf")
    return PdfParseResult(text=text, pages=pages)


def parse_pdf_file(path: Path) -> PdfParseResult:
    return parse_pdf_bytes(path.read_bytes())
