"""Generate the fixture PDFs used by tests/test_extract_pdf.py (stdlib only).

Regenerate with: cd api && uv run python tests/fixtures/make_fixtures.py
"""

from pathlib import Path

HERE = Path(__file__).parent

SENTENCES = [
    "Photosynthesis converts light energy into chemical energy stored in glucose molecules.",
    "Mitochondria produce most of the ATP that a eukaryotic cell uses to power its work.",
    "The Krebs cycle oxidizes acetyl-CoA to carbon dioxide while capturing high-energy electrons.",
]


def build_pdf(page_streams: list[bytes]) -> bytes:
    """Build a minimal valid PDF: one content stream per page, Helvetica as /F1."""
    n = len(page_streams)
    # Object ids: 1 catalog, 2 pages, 3 font, then (page, content) pairs.
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n))
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, stream in enumerate(page_streams):
        content_id = 5 + 2 * i
        objects.append(
            (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode()
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    return bytes(out)


def text_stream(sentence: str) -> bytes:
    return f"BT /F1 12 Tf 50 700 Td ({sentence}) Tj ET".encode()


def main() -> None:
    (HERE / "text.pdf").write_bytes(build_pdf([text_stream(s) for s in SENTENCES]))
    (HERE / "image_only.pdf").write_bytes(build_pdf([b"0.5 0.5 0.5 rg 100 100 300 300 re f"]))
    (HERE / "too_many_pages.pdf").write_bytes(build_pdf([b""] * 201))
    (HERE / "corrupt.pdf").write_bytes(b"%PDF-1.7\n" + bytes(range(256)) * 4)


if __name__ == "__main__":
    main()
