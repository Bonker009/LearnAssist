"""Generate the test-fixture PDF with no third-party dependencies.

Each page carries distinct, known text so parser tests can assert that a given
phrase resolves to a specific page number -- which is the whole point of the
citation feature.
"""
import pathlib
import zlib

PAGES = [
    ["Lecture 1: Photosynthesis", "",
     "Photosynthesis converts light energy into chemical energy.",
     "It occurs in the chloroplasts of plant cells."],
    ["The Light-Dependent Reactions", "",
     "Light-dependent reactions take place in the thylakoid membrane.",
     "They produce ATP and NADPH, and release oxygen as a by-product."],
    ["The Calvin Cycle", "",
     "The Calvin cycle occurs in the stroma and fixes carbon dioxide.",
     "RuBisCO is the enzyme that catalyses the first carbon fixation step."],
]


def escape(text):
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def content_stream(lines):
    out = ["BT", "/F1 14 Tf", "72 720 Td", "18 TL"]
    for line in lines:
        out.append(f"({escape(line)}) Tj")
        out.append("T*")
    out.append("ET")
    return "\n".join(out).encode("latin-1")


def build(path):
    objects = {}
    n_pages = len(PAGES)
    page_ids = [4 + 2 * i for i in range(n_pages)]

    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode()
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    for i, lines in enumerate(PAGES):
        pid = page_ids[i]
        cid = pid + 1
        objects[pid] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {cid} 0 R >>"
        ).encode()
        data = zlib.compress(content_stream(lines))
        objects[cid] = (
            f"<< /Length {len(data)} /Filter /FlateDecode >>\nstream\n".encode()
            + data + b"\nendstream"
        )

    buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for num in sorted(objects):
        offsets[num] = len(buf)
        buf += f"{num} 0 obj\n".encode() + objects[num] + b"\nendobj\n"

    xref_at = len(buf)
    count = max(objects) + 1
    buf += f"xref\n0 {count}\n".encode()
    buf += b"0000000000 65535 f \n"
    for num in range(1, count):
        buf += f"{offsets.get(num, 0):010d} 00000 n \n".encode()
    buf += (
        f"trailer\n<< /Size {count} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode()

    pathlib.Path(path).write_bytes(bytes(buf))
    return len(buf)


if __name__ == "__main__":
    target = pathlib.Path(__file__).parent / "lecture_sample.pdf"
    print(f"wrote {target} ({build(target)} bytes, {len(PAGES)} pages)")
