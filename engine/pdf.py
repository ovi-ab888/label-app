from __future__ import annotations
from typing import Iterable, Tuple
from io import BytesIO
import zipfile

def svg_to_pdf(svg_text: str, dpi: int = 96) -> bytes:
    """
    Try CairoSVG first (best quality). If unavailable on the platform,
    fall back to svglib+reportlab (pure-Python).
    """
    # 1) Try CairoSVG
    try:
        import cairosvg
        return cairosvg.svg2pdf(bytestring=svg_text.encode("utf-8"), dpi=dpi)
    except Exception:
        pass

    # 2) Fallback: svglib + reportlab
    from svglib.svglib import svg2rlg
    from reportlab.pdfgen import canvas
    from reportlab.graphics import renderPDF

    drawing = svg2rlg(BytesIO(svg_text.encode("utf-8")))
    buf = BytesIO()
    # Use SVG intrinsic size
    width = getattr(drawing, "width", 595)
    height = getattr(drawing, "height", 842)

    c = canvas.Canvas(buf, pagesize=(width, height))
    renderPDF.draw(drawing, c, 0, 0)
    c.showPage()
    c.save()
    return buf.getvalue()

def zip_pdfs(items: Iterable[Tuple[str, bytes]]) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in items:
            zf.writestr(name, data)
    return buf.getvalue()
