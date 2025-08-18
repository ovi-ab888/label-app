from __future__ import annotations
from typing import Iterable, Tuple, List
from io import BytesIO
import zipfile

# ----- CairoSVG path (আগের মতো) -----
def svg_to_pdf(svg_text: str, dpi: int = 96) -> bytes:
    try:
        import cairosvg
        return cairosvg.svg2pdf(bytestring=svg_text.encode("utf-8"), dpi=dpi)
    except Exception:
        # fallback: svglib+reportlab single page (একটা পেজে একটাই SVG হলে)
        from svglib.svglib import svg2rlg
        from reportlab.pdfgen import canvas
        drawing = svg2rlg(BytesIO(svg_text.encode("utf-8")))
        buf = BytesIO()
        w, h = getattr(drawing, "width", 595), getattr(drawing, "height", 842)
        c = canvas.Canvas(buf, pagesize=(w, h))
        from reportlab.graphics import renderPDF
        renderPDF.draw(drawing, c, 0, 0)
        c.showPage(); c.save()
        return buf.getvalue()

def zip_pdfs(items: Iterable[Tuple[str, bytes]]) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in items:
            zf.writestr(name, data)
    return buf.getvalue()

# ----- NEW: সব SVG এক পেজে গ্রিড করে বসানো -----
def svgs_grid_to_pdf(
    svg_texts: List[str],
    page_size: str = "A4",
    cols: int = 6,
    margin_mm: float = 10.0,
    gutter_mm: float = 6.0,
) -> bytes:
    """সব SVG এক পেজে N-up গ্রিডে বসিয়ে PDF বানায় (ভেক্টর কোয়ালিটি বজায় থাকে)।"""
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

    # প্রতি সেলের টার্গেট সাইজ
    cell_w = (page_w - 2 * margin - (cols - 1) * gutter) / cols
    cell_h = (page_h - 2 * margin - (rows - 1) * gutter) / rows

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))

    # টপ-লেফট থেকে বাম→ডানে, ওপর→নিচে
    for idx, svg in enumerate(svg_texts):
        r = idx // cols  # row
        q = idx % cols   # col

        # সেলের origin (bottom-left)
        x0 = margin + q * (cell_w + gutter)
        # reportlab-এর origin নিচে, তাই y উল্টো করে নিই
        y0 = page_h - margin - (r + 1) * cell_h - r * gutter + (cell_h - cell_h)

        # SVG→drawing
        drawing = svg2rlg(BytesIO(svg.encode("utf-8")))
        dw, dh = max(1.0, getattr(drawing, "width", cell_w)), max(1.0, getattr(drawing, "height", cell_h))

        # scale to fit cell
        scale = min(cell_w / dw, cell_h / dh)
        draw_w, draw_h = dw * scale, dh * scale

        # সেলের ভিতরে সেন্টার করে বসাই
        offset_x = x0 + (cell_w - draw_w) / 2.0
        # reportlab-এ (0,0) bottom-left, তাই y-ও bottom থেকে
        offset_y = page_h - (margin + (r + 1) * cell_h + r * gutter) + (cell_h - draw_h) / 2.0

        # রেন্ডার
        renderPDF.draw(drawing, c, offset_x, offset_y, showBoundary=False, scale=scale)

    c.showPage()
    c.save()
    return buf.getvalue()
