from __future__ import annotations
from typing import Iterable, Tuple, List
from io import BytesIO
import zipfile


def svg_to_pdf(svg_text: str, dpi: int = 96) -> bytes:
    """
    Convert a single SVG string to PDF bytes.
    Tries CairoSVG first (best quality). Falls back to svglib+reportlab if Cairo isn't available.
    """
    # 1) Try CairoSVG
    try:
        import cairosvg  # type: ignore
        return cairosvg.svg2pdf(bytestring=svg_text.encode("utf-8"), dpi=dpi)
    except Exception:
        pass

    # 2) Fallback: svglib + reportlab
    from svglib.svglib import svg2rlg
    from reportlab.pdfgen import canvas
    from reportlab.graphics import renderPDF

    drawing = svg2rlg(BytesIO(svg_text.encode("utf-8")))
    buf = BytesIO()
    width = float(getattr(drawing, "width", 595.0))   # ~A4 width (points)
    height = float(getattr(drawing, "height", 842.0)) # ~A4 height (points)

    c = canvas.Canvas(buf, pagesize=(width, height))
    renderPDF.draw(drawing, c, 0, 0)
    c.showPage()
    c.save()
    return buf.getvalue()


def zip_pdfs(items: Iterable[Tuple[str, bytes]]) -> bytes:
    """
    Build a ZIP from an iterable of (filename, pdf_bytes).
    """
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in items:
            zf.writestr(name, data)
    return buf.getvalue()


def svgs_grid_to_pdf(
    svg_texts: List[str],
    page_size: str = "A4",
    cols: int = 6,
    margin_mm: float = 10.0,
    gutter_mm: float = 6.0,
) -> bytes:
    """
    Compose many SVGs into a single one-page PDF in an N-up grid (vector-safe).
    - page_size: "A4", "LETTER", or "A3"
    - cols: number of columns
    - margin_mm/gutter_mm: outer margin and gap between cells (in millimetres)
    """
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPDF
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, LETTER, A3
    from reportlab.lib.units import mm

    PAGES = {"A4": A4, "LETTER": LETTER, "A3": A3}
    page_w, page_h = PAGES.get(page_size.upper(), A4)

    margin = margin_mm * mm
    gutter = gutter_mm * mm
    cols = max(1, int(cols))
    n = len(svg_texts)
    rows = max(1, (n + cols - 1) // cols)

    # Cell size
    cell_w = (page_w - 2 * margin - (cols - 1) * gutter) / cols
    cell_h = (page_h - 2 * margin - (rows - 1) * gutter) / rows

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))

    for idx, svg in enumerate(svg_texts):
        r = idx // cols          # row index
        q = idx % cols           # col index

        # SVG -> drawing
        drawing = svg2rlg(BytesIO(svg.encode("utf-8")))
        dw = float(getattr(drawing, "width", cell_w) or 1.0)
        dh = float(getattr(drawing, "height", cell_h) or 1.0)

        # Scale to fit the cell, preserve aspect
        scale = min(cell_w / dw, cell_h / dh)
        draw_w, draw_h = dw * scale, dh * scale

        # Cell top-left (ReportLab origin is bottom-left, beware Y math)
        x_cell_left = margin + q * (cell_w + gutter)
        y_cell_top = page_h - margin - r * (cell_h + gutter)

        # Center inside the cell
        offset_x = x_cell_left + (cell_w - draw_w) / 2.0
        offset_y = y_cell_top - draw_h - (cell_h - draw_h) / 2.0

        # Apply transform on the canvas (no 'scale' kw in renderPDF.draw)
        c.saveState()
        c.translate(offset_x, offset_y)
        c.scale(scale, scale)
        renderPDF.draw(drawing, c, 0, 0, showBoundary=False)
        c.restoreState()

    c.showPage()
    c.save()
    return buf.getvalue()
