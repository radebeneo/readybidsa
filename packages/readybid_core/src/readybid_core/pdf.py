"""PDF validation and per-page text extraction with explicit coverage flags.

ReadyBid supports text-readable English PDFs only (no OCR). Every physical page becomes
exactly one source segment, including pages without extractable text. Those pages are
kept and flagged, never dropped.

Extraction signals are deliberately conservative: some text on a page does not prove the
whole page was extracted (a scanned page may carry a short text header), so pages with
images and little text are marked "suspicious" rather than "ok".
"""

import hashlib
import logging
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from pypdf import PdfReader
from pypdf.errors import PdfReadError, PyPdfError
from pypdf.generic import DictionaryObject

logger = logging.getLogger(__name__)

# Pages with fewer extracted characters than this are treated as unreadable
# (typically scanned or image-only pages).
MIN_READABLE_CHARS = 20
# A page that contains images and fewer characters than this may be partly scanned.
SUSPICIOUS_WITH_IMAGES_CHARS = 400
# Share of letters/digits below which extracted text is likely garbage (broken font maps).
MIN_ALNUM_RATIO = 0.4
# The PDF header must appear near the start of the file (the spec allows leading junk;
# readers accept it within the first 1024 bytes).
HEADER_SEARCH_BYTES = 1024

ExtractionStatus = Literal["ok", "suspicious", "empty", "error"]


class PdfValidationError(ValueError):
    """Raised when an upload is not an acceptable PDF. `code` is safe to show to users."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ValidatedPdf:
    sha256: str
    size_bytes: int
    page_count: int


@dataclass(frozen=True)
class PageText:
    page_number: int  # 1-based, matches what users see in a PDF viewer
    text: str
    readable: bool


@dataclass(frozen=True)
class Segment:
    id: str
    page_number: int  # 1-based physical page
    text: str
    char_count: int
    status: ExtractionStatus
    note: str | None

    @property
    def readable(self) -> bool:
        return self.status == "ok"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def segment_id(document_id: str, document_sha256: str, page_number: int) -> str:
    """Deterministic segment id, so re-running extraction is idempotent."""
    digest = hashlib.sha256(f"{document_id}:{document_sha256}:{page_number}".encode()).hexdigest()
    return "seg_" + digest[:32]


def _open_reader(data: bytes) -> PdfReader:
    try:
        return PdfReader(BytesIO(data), strict=False)
    except (PyPdfError, ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        # Do not echo parser internals to the user; log them for debugging.
        logger.info("PDF could not be parsed: %s: %s", type(error).__name__, error)
        raise PdfValidationError("malformed_pdf", "The file could not be read as a PDF.") from None
    except RecursionError:
        raise PdfValidationError("malformed_pdf", "The file could not be read as a PDF.") from None


def validate_pdf(data: bytes, *, max_bytes: int, max_pages: int) -> ValidatedPdf:
    """Validate an upload by its content, not its filename or declared MIME type."""
    size = len(data)
    if size == 0:
        raise PdfValidationError("empty_file", "The file is empty.")
    if size > max_bytes:
        limit_mb = max_bytes / (1024 * 1024)
        raise PdfValidationError("too_large", f"The file is larger than {limit_mb:g} MB.")
    if b"%PDF-" not in data[:HEADER_SEARCH_BYTES]:
        raise PdfValidationError("not_pdf", "The file is not a PDF.")

    reader = _open_reader(data)
    try:
        encrypted = reader.is_encrypted
    except (PyPdfError, ValueError, KeyError, TypeError):
        raise PdfValidationError("malformed_pdf", "The file could not be read as a PDF.") from None
    if encrypted:
        raise PdfValidationError(
            "encrypted_pdf", "The PDF is encrypted or password-protected. Upload an unlocked copy."
        )

    try:
        page_count = len(reader.pages)
    except (PyPdfError, ValueError, KeyError, TypeError, IndexError, RecursionError):
        raise PdfValidationError("malformed_pdf", "The file could not be read as a PDF.") from None
    if page_count < 1:
        raise PdfValidationError("no_pages", "The PDF has no pages.")
    if page_count > max_pages:
        raise PdfValidationError(
            "too_many_pages", f"The PDF has {page_count} pages. The limit is {max_pages}."
        )

    return ValidatedPdf(sha256=sha256_hex(data), size_bytes=size, page_count=page_count)


def _page_has_images(page: DictionaryObject) -> bool:
    """Check the page's XObjects for images without decoding them."""
    try:
        resources = page.get("/Resources")
        resources = resources.get_object() if resources is not None else None
        if not isinstance(resources, DictionaryObject):
            return False
        xobjects = resources.get("/XObject")
        xobjects = xobjects.get_object() if xobjects is not None else None
        if not isinstance(xobjects, DictionaryObject):
            return False
        for ref in xobjects.values():
            obj = ref.get_object()
            if isinstance(obj, DictionaryObject) and obj.get("/Subtype") in ("/Image", "/Form"):
                return True
    except (PyPdfError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        # Unknown structure: treat as "may contain images" so the page is not marked ok blindly.
        return True
    return False


def _classify(text: str, has_images: bool) -> tuple[ExtractionStatus, str | None]:
    char_count = len(text)
    if char_count == 0:
        return "empty", "No extractable text. The page may be scanned or image-only."
    if char_count < MIN_READABLE_CHARS:
        return "suspicious", "Very little extractable text. The page may be scanned."
    alnum = sum(1 for ch in text if ch.isalnum())
    if alnum / char_count < MIN_ALNUM_RATIO:
        return "suspicious", "Extracted text looks garbled. Check the page in the PDF."
    if has_images and char_count < SUSPICIOUS_WITH_IMAGES_CHARS:
        return "suspicious", "The page contains images and little text. Part of it may be scanned."
    return "ok", None


def extract_segments(data: bytes, *, document_id: str, document_sha256: str) -> list[Segment]:
    """Extract one segment per physical page. Pages that fail are kept with status "error"."""
    reader = _open_reader(data)
    if reader.is_encrypted:
        raise PdfValidationError("encrypted_pdf", "The PDF is encrypted or password-protected.")

    segments: list[Segment] = []
    for page_number, page in enumerate(reader.pages, start=1):
        seg_id = segment_id(document_id, document_sha256, page_number)
        try:
            text = (page.extract_text() or "").strip()
        except Exception as error:  # noqa: BLE001 - pypdf can raise many types on bad pages
            logger.info("Text extraction failed on page %d: %s", page_number, type(error).__name__)
            segments.append(
                Segment(
                    id=seg_id,
                    page_number=page_number,
                    text="",
                    char_count=0,
                    status="error",
                    note="Text could not be extracted from this page.",
                )
            )
            continue
        # Postgres text columns cannot store NUL bytes.
        text = text.replace("\x00", "")
        status, note = _classify(text, _page_has_images(page))
        segments.append(
            Segment(
                id=seg_id,
                page_number=page_number,
                text=text,
                char_count=len(text),
                status=status,
                note=note,
            )
        )
    return segments


def flagged_pages(segments: list[Segment]) -> list[int]:
    """Pages whose text may be missing or incomplete. Coverage is incomplete if any exist."""
    return [segment.page_number for segment in segments if segment.status != "ok"]


def extract_pages(data: bytes) -> list[PageText]:
    """Simple per-page extraction kept for callers that do not need segment metadata."""
    reader = PdfReader(BytesIO(data))
    pages: list[PageText] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        pages.append(
            PageText(page_number=page_number, text=text, readable=len(text) >= MIN_READABLE_CHARS)
        )
    return pages


def unreadable_pages(pages: list[PageText]) -> list[int]:
    return [page.page_number for page in pages if not page.readable]


__all__ = [
    "MIN_READABLE_CHARS",
    "PageText",
    "PdfReadError",
    "PdfValidationError",
    "Segment",
    "ValidatedPdf",
    "extract_pages",
    "extract_segments",
    "flagged_pages",
    "segment_id",
    "sha256_hex",
    "unreadable_pages",
    "validate_pdf",
]
