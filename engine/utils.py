from __future__ import annotations
import base64, re

def to_str(x) -> str:
    return "" if x is None else str(x)

def safe_filename(name: str) -> str:
    name = name or "file"
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9._-]", "", name)
    return name if name.lower().endswith(".pdf") else (name + ".pdf")

def png_bytes_to_data_uri(png_bytes: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")

