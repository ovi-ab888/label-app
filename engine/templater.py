from __future__ import annotations
from typing import Dict, List, Optional
from lxml import etree
import re

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
NSMAP = {None: SVG_NS, "xlink": XLINK_NS}

def _decode_ai_id(s: str) -> str:
    return re.sub(r"_x([0-9A-Fa-f]{4})_", lambda m: chr(int(m.group(1), 16)), s)

def _first(node, xp):
    found = node.xpath(xp, namespaces={'svg': SVG_NS, 'xlink': XLINK_NS})
    return found[0] if found else None

def _ensure_text(node):
    if node.tag.endswith('text'): return node
    return _first(node, ".//svg:text")

def _ensure_image(node):
    if node.tag.endswith('image'): return node
    return _first(node, ".//svg:image")

def extract_placeholders(svg_text: str) -> List[str]:
    root = etree.fromstring(svg_text.encode("utf-8"))
    seen, out = set(), []
    for el in root.iter():
        _id = el.get("id")
        if not _id: continue
        nid = _decode_ai_id(_id)
        if nid.startswith("var_") and nid not in seen:
            out.append(nid); seen.add(nid)
    return out

def _set_text(el: etree._Element, value: str):
    maxlen = el.get("data-maxlen")
    if maxlen:
        try:
            n = int(maxlen)
            if len(value) > n: value = value[:max(0, n-1)] + "…"
        except Exception: pass
    for child in list(el): el.remove(child)
    el.text = value

def _token_fill(svg_text: str, values: Dict[str, str]) -> str:
    s = svg_text
    pairs = list(values.items()) + [(k.replace("var_",""), v) for k, v in values.items()]
    for k, v in pairs: s = s.replace(f"[[{k}]]", str(v))
    return s

def fill_svg(svg_text: str, values: Dict[str, str], barcode_data_uri: Optional[str] = None) -> str:
    pre = _token_fill(svg_text, values)
    root = etree.fromstring(pre.encode("utf-8"), etree.XMLParser(remove_blank_text=False))

    idx = {}
    for el in root.iter():
        _id = el.get("id")
        if _id: idx[_decode_ai_id(_id)] = el

    for pid, val in values.items():
        node = idx.get(pid)
        if node is not None:
            tgt = _ensure_text(node)
            if tgt is not None: _set_text(tgt, str(val))

    if barcode_data_uri:
        node = (idx.get("var_BarcodeImg") or idx.get("var_Barcode")
                or idx.get("_Image_var_Barcode") or idx.get("var_x5F_BarcodeImg"))
        if node is not None:
            img = _ensure_image(node)
            if img is not None:
                img.set("href", barcode_data_uri)
                img.set(f"{{{XLINK_NS}}}href", barcode_data_uri)

    return etree.tostring(root, encoding="utf-8").decode("utf-8")

