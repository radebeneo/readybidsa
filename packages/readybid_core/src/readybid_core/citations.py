"""Citation validation.

Page numbers and document identity always come from application metadata (the source
segment), never from the model. A model citation is only a segment id plus a quote, and it
is accepted only when:

1. the segment belongs to the analysis being run (same document, same organisation),
2. the segment was extracted from the analysed document version (same sha256), and
3. the quote appears in the segment text after controlled whitespace normalisation
   (runs of whitespace collapse to one space). There is no fuzzy matching.
"""

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

_WHITESPACE = re.compile(r"\s+")

MIN_QUOTE_CHARS = 8
MAX_QUOTE_CHARS = 1000

RejectionReason = Literal[
    "unknown_segment",
    "wrong_document_version",
    "quote_too_short",
    "quote_too_long",
    "quote_not_found",
]


def normalise_whitespace(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def quote_hash(quote: str) -> str:
    return hashlib.sha256(quote.encode()).hexdigest()


@dataclass(frozen=True)
class SegmentRef:
    """The parts of a source segment needed to validate and display a citation."""

    id: str
    document_id: str
    document_sha256: str
    page_number: int
    text: str
    status: str = "ok"


@dataclass(frozen=True)
class ValidatedCitation:
    segment_id: str
    document_id: str
    page_number: int  # from segment metadata
    quote: str  # whitespace-normalised, exactly as found in the segment
    quote_sha256: str


@dataclass(frozen=True)
class RejectedCitation:
    segment_id: str
    quote: str
    reason: RejectionReason


class CitationValidator:
    """Validates model citations against the segments of one analysed document version."""

    def __init__(
        self, *, document_id: str, document_sha256: str, segments: Iterable[SegmentRef]
    ) -> None:
        self.document_id = document_id
        self.document_sha256 = document_sha256
        self._segments = {segment.id: segment for segment in segments}
        self._normalised: dict[str, str] = {}

    def _segment_text(self, segment: SegmentRef) -> str:
        cached = self._normalised.get(segment.id)
        if cached is None:
            cached = normalise_whitespace(segment.text)
            self._normalised[segment.id] = cached
        return cached

    def validate(self, segment_id: str, quote: str) -> ValidatedCitation | RejectedCitation:
        segment = self._segments.get(segment_id)
        if segment is None:
            return RejectedCitation(segment_id, quote, "unknown_segment")
        if (
            segment.document_id != self.document_id
            or segment.document_sha256 != self.document_sha256
        ):
            return RejectedCitation(segment_id, quote, "wrong_document_version")

        normalised_quote = normalise_whitespace(quote)
        if len(normalised_quote) < MIN_QUOTE_CHARS:
            return RejectedCitation(segment_id, quote, "quote_too_short")
        if len(normalised_quote) > MAX_QUOTE_CHARS:
            return RejectedCitation(segment_id, quote, "quote_too_long")
        if normalised_quote not in self._segment_text(segment):
            return RejectedCitation(segment_id, quote, "quote_not_found")

        return ValidatedCitation(
            segment_id=segment.id,
            document_id=segment.document_id,
            page_number=segment.page_number,
            quote=normalised_quote,
            quote_sha256=quote_hash(normalised_quote),
        )
