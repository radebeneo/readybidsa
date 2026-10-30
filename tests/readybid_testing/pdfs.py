"""Synthetic PDFs generated in memory for tests (no binary fixtures committed)."""

from collections.abc import Sequence
from io import BytesIO


class ImageOnlyPage:
    """Marker for a page that draws an image and has no text layer, like a scanned page."""


IMAGE_ONLY = ImageOnlyPage()
PageSpec = str | None | ImageOnlyPage

# A 1x1 grey image XObject.
_IMAGE_OBJECT = (
    b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceGray "
    b"/BitsPerComponent 8 /Length 1 >>\nstream\n\x80\nendstream"
)


def build_pdf(pages: Sequence[PageSpec]) -> bytes:
    """Build a minimal PDF in memory.

    Each entry is the text of one page, None for a page with no content, or IMAGE_ONLY for
    a page that only shows an image. Text must not contain parentheses or backslashes.
    """
    count = len(pages)
    # Objects: 1 catalog, 2 page tree, 3 font, 4 image, then (page, contents) pairs from 5.
    kids = " ".join(f"{5 + 2 * i} 0 R" for i in range(count))
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {count} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        _IMAGE_OBJECT,
    ]
    for i, spec in enumerate(pages):
        if isinstance(spec, ImageOnlyPage):
            stream = b"q 400 0 0 500 100 150 cm /Im1 Do Q"
            resources = "<< /XObject << /Im1 4 0 R >> >>"
        else:
            stream = f"BT /F1 12 Tf 72 720 Td ({spec}) Tj ET".encode() if spec else b""
            resources = "<< /Font << /F1 3 0 R >> >>"
        objects.append(
            (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources {resources} /Contents {6 + 2 * i} 0 R >>"
            ).encode()
        )
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    ).encode()
    return bytes(out)


def build_encrypted_pdf() -> bytes:
    """A password-protected copy of a one-page synthetic PDF."""
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter(clone_from=PdfReader(BytesIO(build_pdf(["dev-fixture encrypted page"]))))
    writer.encrypt(user_password="dev-fixture", algorithm="AES-128")
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def build_malformed_pdf() -> bytes:
    """Starts like a PDF but the body is cut off and unusable."""
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R"
