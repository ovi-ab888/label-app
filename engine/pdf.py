from __future__ import annotations
from typing import Iterable, Tuple
from io import BytesIO
import zipfile
import cairosvg

def svg_to_pdf(svg_text: str, dpi: int = 96) -> bytes:
    return cairosvg.svg2pdf(bytestring=svg_text.encode("utf-8"), dpi=dpi)

def zip_pdfs(items: Iterable[Tuple[str, bytes]]) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in items: zf.writestr(name, data)
    return buf.getvalue()

