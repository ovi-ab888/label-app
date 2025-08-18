from __future__ import annotations
from io import BytesIO
from typing import Literal
from PIL import Image  # noqa: F401
import barcode
from barcode.writer import ImageWriter

BarType = Literal["EAN13", "Code128"]

def _as_png_bytes(bc_obj, writer_opts=None) -> bytes:
    buf = BytesIO()
    (writer_opts or {}).setdefault("write_text", False)
    bc_obj.write(buf, options=writer_opts or {})
    return buf.getvalue()

def generate_barcode_png(data: str, kind: BarType = "EAN13") -> bytes:
    data = (data or "").strip()
    if not data: raise ValueError("Empty barcode data")
    writer_opts = {"write_text": False, "quiet_zone": 1.0, "module_height": 15.0}
    if kind.upper() == "EAN13":
        digits = ''.join(ch for ch in data if ch.isdigit())
        if len(digits) not in (12, 13): raise ValueError("EAN-13 requires 12 or 13 digits")
        if len(digits) == 13: digits = digits[:12]
        return _as_png_bytes(barcode.get("ean13", digits, writer=ImageWriter()), writer_opts)
    if kind.upper() == "CODE128":
        return _as_png_bytes(barcode.get("code128", data, writer=ImageWriter()), writer_opts)
    raise ValueError(f"Unsupported barcode kind: {kind}")

