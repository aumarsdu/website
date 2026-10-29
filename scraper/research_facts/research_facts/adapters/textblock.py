"""Text-block adapters for posters (OCR output) and handbooks (PDF text).

Both inputs are *already* text with geometry, so this adapter does not run OCR
or parse PDFs. The upstream jobs that produce those files are documented in
``README.md`` under "Real wiring". Keeping them outside this package means the
extraction rules are testable without a 4 GB model dependency, and an OCR engine
upgrade never changes field semantics.

Input contract, one JSON object per line in a ``.jsonl`` file::

    {
      "document_id": "poster-rs-2027-0142",     # required, unique in the run
      "provider": "demo-provider",              # required
      "external_id": "RS-2027-0142",            # optional but strongly preferred
      "title_hint": "遥感无人机",                 # optional
      "source_authority": "supplier_marketing", # optional
      "image": "posters/RS-2027-0142.jpg",      # poster flavour
      "pages": [{"page": 1, "blocks": [...]}],  # handbook flavour
      "blocks": [{"text": "...", "bbox": [x, y, w, h], "conf": 0.98}],
      "meta": {}
    }

``bbox`` is ``[x, y, width, height]`` in pixels. ``conf`` is the engine's own
box score and is used to cap extraction confidence; it is real measured data,
not an estimate produced here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable

from ..config import Settings
from ..errors import ParseError
from ..extract import claims_from_blocks, deliverable_shape_claim
from ..labels import (
    TextBlock,
    group_rows,
    row_detail,
    row_pointer,
    row_to_text,
    template_signature,
)
from ..schema import FieldClaim, RejectedCandidate
from ..storage import read_jsonl
from ..utils import clean_text, comparison_key
from .base import AdapterOutput, make_document


def _blocks_from_payload(payload: dict[str, Any], document_id: str) -> tuple[list[TextBlock], int]:
    """Flatten poster blocks or handbook pages into one reading-ordered list."""
    blocks: list[TextBlock] = []
    order = 0
    page_count = 0

    pages = payload.get("pages")
    if isinstance(pages, list):
        for page_index, page in enumerate(pages, start=1):
            if not isinstance(page, dict):
                raise ParseError(f"{document_id}: page {page_index} is not an object")
            page_number = page.get("page", page_index)
            page_count = max(page_count, int(page_number))
            for block_index, block in enumerate(page.get("blocks") or []):
                text = clean_text((block or {}).get("text", ""))
                if not text:
                    continue
                blocks.append(
                    TextBlock(
                        text=text,
                        pointer=f"p{int(page_number)}#b{block_index}",
                        detail=f"page={int(page_number)}",
                        order=order,
                        bbox=_bbox(block),
                        ocr_confidence=_conf(block),
                    )
                )
                order += 1

    flat = payload.get("blocks")
    if isinstance(flat, list):
        for block_index, block in enumerate(flat):
            text = clean_text((block or {}).get("text", ""))
            if not text:
                continue
            blocks.append(
                TextBlock(
                    text=text,
                    pointer=f"b{block_index}",
                    detail=f"image={payload.get('image', '')}".strip(),
                    order=order,
                    bbox=_bbox(block),
                    ocr_confidence=_conf(block),
                )
            )
            order += 1

    return blocks, page_count


def _bbox(block: dict[str, Any] | None) -> tuple[float, float, float, float] | None:
    raw = (block or {}).get("bbox")
    if isinstance(raw, (list, tuple)) and len(raw) == 4:
        try:
            return (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))
        except (TypeError, ValueError):
            return None
    return None


def _conf(block: dict[str, Any] | None) -> float | None:
    raw = (block or {}).get("conf")
    if isinstance(raw, (int, float)):
        return float(raw)
    return None


def _row_blocks(blocks: list[TextBlock], document_id: str) -> list[TextBlock]:
    """Turn geometric OCR boxes into readable rows (poster layout only)."""
    rows = group_rows(blocks)
    result: list[TextBlock] = []
    for index, row in enumerate(rows):
        texts = [block.text for block in row if block.text.strip()]
        if not texts:
            continue
        confidences = [block.ocr_confidence for block in row if block.ocr_confidence is not None]
        result.append(
            TextBlock(
                text=row_to_text(row),
                # A joined row must still name the exact boxes it came from.
                pointer=f"row{index}[{row_pointer(row)}]",
                detail=row_detail(row),
                order=index,
                bbox=None,
                ocr_confidence=min(confidences) if confidences else None,
            )
        )
    return result


def _pick_title_hint(payload: dict[str, Any], blocks: Iterable[TextBlock]) -> str | None:
    hint = clean_text(payload.get("title_hint", ""))
    if hint:
        return hint
    for block in blocks:
        text = block.text.strip()
        # A poster headline is the longest single line near the top.
        if len(text) >= 6:
            return text
    return None


class TextBlockAdapter:
    """Extract labeled facts from a text block file.

    ``source_kind`` selects the reading strategy: posters join columns into rows
    and match labels without a separator, handbooks keep one line per block and
    require an explicit ``label: value`` separator.
    """

    def __init__(self, name: str, source_kind: str, accepts: tuple[str, ...]) -> None:
        self.name = name
        self.source_kind = source_kind
        self.accepts = accepts
        # Set by the pipeline so one corrupt line does not lose the whole file.
        self.on_error: Callable[[int, Exception], None] | None = None

    def load(self, path: Path, settings: Settings) -> list[AdapterOutput]:
        is_poster = self.source_kind == "poster_ocr"
        outputs: list[AdapterOutput] = []
        for index, payload in enumerate(read_jsonl(Path(path), on_error=self.on_error)):
            document_id = clean_text(payload.get("document_id", "")) or f"{path.stem}-{index:04d}"
            provider = clean_text(payload.get("provider", "")) or "unknown"
            blocks, page_count = _blocks_from_payload(payload, document_id)
            reading_blocks = _row_blocks(blocks, document_id) if is_poster else blocks

            rejected: list[RejectedCandidate] = []
            claims: list[FieldClaim] = claims_from_blocks(
                reading_blocks,
                document_id=document_id,
                source_kind=self.source_kind,
                settings=settings,
                require_delimiter=not is_poster,
                locator_kind="text_row" if is_poster else "text_line",
                base_confidence="medium" if is_poster else "high",
                # Posters are the geometric case; a handbook line is not.
                label_must_lead_row=is_poster,
                rejected=rejected,
            )
            # The stat-tile template states deliverables without a label, so a
            # shape rule reads that one line. Posters only, one field only.
            if is_poster:
                for block in reading_blocks:
                    shape = deliverable_shape_claim(
                        block, document_id=document_id, locator_kind="text_row"
                    )
                    if shape is not None:
                        claims.append(shape)

            document = make_document(
                document_id=document_id,
                source_kind=self.source_kind,
                provider=provider,
                origin=str(Path(path)),
                external_id=clean_text(payload.get("external_id", "")) or None,
                title_hint=_pick_title_hint(payload, reading_blocks),
                source_authority=clean_text(payload.get("source_authority", "")) or "unknown",
                meta={
                    "block_count": len(blocks),
                    "page_count": page_count,
                    "image": payload.get("image"),
                    "template_signature": list(template_signature(reading_blocks)),
                    **{k: v for k, v in (payload.get("meta") or {}).items()},
                },
            )
            outputs.append(
                AdapterOutput(
                    document=document,
                    claims=claims,
                    rejected=rejected,
                    stats={
                        "blocks": len(blocks),
                        "reading_units": len(reading_blocks),
                        "pages": page_count,
                    },
                )
            )
        return outputs


poster_adapter = TextBlockAdapter(
    name="poster_ocr",
    source_kind="poster_ocr",
    accepts=("*.jsonl",),
)

handbook_adapter = TextBlockAdapter(
    name="handbook_pdf",
    source_kind="handbook_pdf",
    accepts=("*.jsonl",),
)


def title_similarity(left: str | None, right: str | None) -> float:
    """Character-bigram overlap, used only to propose an identity link."""
    if not left or not right:
        return 0.0
    from difflib import SequenceMatcher

    return round(SequenceMatcher(None, comparison_key(left), comparison_key(right)).ratio(), 4)
