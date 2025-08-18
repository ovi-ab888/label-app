from io import BytesIO
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from engine import parser as data_parser
from engine import templater
from engine import barcode as bc
from engine import pdf as pdf_engine
from engine import utils

# -------------------------------------------------
# Paths & environment
# -------------------------------------------------
APP_ROOT = Path(__file__).parent
TEMPLATE_DIR = APP_ROOT / "templates"
SAMPLES_DIR = APP_ROOT / "samples"
CONFIG_DIR = APP_ROOT / "config"

# Cloud-safe outputs: use /tmp on cloud, repo ./outputs on local
RUNNING_IN_CLOUD = bool(
    os.environ.get("STREAMLIT_RUNTIME")
    or os.environ.get("STREAMLIT_SERVER")
    or os.environ.get("STREAMLIT_CLOUD")
    or os.environ.get("RENDER")
    or os.environ.get("GITHUB_ACTIONS")
)
OUTPUTS_DIR = (Path(tempfile.gettempdir()) / "label-app-outputs") if RUNNING_IN_CLOUD else (APP_ROOT / "outputs")


def ensure_dir(p: Path):
    """If a file exists at 'p', move aside; then make directory."""
    if p.exists():
        if p.is_file():
            try:
                backup = p.with_name(p.name + f".bak-{datetime.now().strftime('%Y%m%d%H%M%S')}")
                p.rename(backup)
            except Exception:
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
    p.mkdir(parents=True, exist_ok=True)


# Make sure output dirs exist without crashing when a file blocks the path
ensure_dir(OUTPUTS_DIR)
ensure_dir(OUTPUTS_DIR / "previews")
ensure_dir(OUTPUTS_DIR / "batches")

st.set_page_config(page_title="Label Generator", page_icon="🏷️", layout="wide")

# -------------------------------------------------
# Config
# -------------------------------------------------
def list_templates():
    if not TEMPLATE_DIR.exists():
        return []
    return sorted([p.name for p in TEMPLATE_DIR.glob("*.svg")])


def load_config():
    app_cfg = (CONFIG_DIR / "app.toml")
    try:
        import tomllib  # py3.11+
    except Exception:
        import tomli as tomllib  # py3.10 fallback
    cfg = {
        "page_size": "A4",
        "dpi": 96,
        "pdf_merge": False,
        "zip_chunk_size": 200,
    }
    if app_cfg.exists():
        with open(app_cfg, "rb") as f:
            cfg.update(tomllib.load(f))
    return cfg


CFG = load_config()

# -------------------------------------------------
# Sidebar — Template & Settings
# -------------------------------------------------
with st.sidebar:
    st.header("Templates")

    templates = list_templates()
    if not templates:
        st.warning("No SVG templates found in `templates/`. Add at least one.")
        st.stop()

    selected_tpl_name = st.selectbox("Choose a template", templates, index=0)
    selected_tpl_path = TEMPLATE_DIR / selected_tpl_name
    template_svg_text = selected_tpl_path.read_text(encoding="utf-8")
    st.caption(f"Loaded: `{selected_tpl_name}`")

    st.divider()
    st.header("Config")
    barcode_type = st.selectbox("Barcode type", ["EAN13", "Code128"], index=0)
    zip_chunk_size = st.number_input(
        "ZIP chunk size (rows per chunk)",
        min_value=50,
        max_value=2000,
        value=int(CFG.get("zip_chunk_size", 200)),
        step=50,
    )

# -------------------------------------------------
# Main — Data load
# -------------------------------------------------
st.title("🏷️ Label Generator (CSV → SVG → PDF)")

col_u, col_s = st.columns([2, 1])
with col_u:
    uploaded = st.file_uploader("Upload CSV", type=["csv"], accept_multiple_files=False)
with col_s:
    sample_btn = st.button("Use samples/Data.csv", use_container_width=True)

if uploaded:
    csv_bytes = uploaded.read()
    df, errors = data_parser.load_csv(io.BytesIO(csv_bytes))
elif sample_btn:
    sample_path = SAMPLES_DIR / "Data.csv"
    if not sample_path.exists():
        df, errors = data_parser.load_csv(BytesIO(csv_bytes))
        st.stop()
    df, errors = data_parser.load_csv(sample_path)
else:
    st.info("Upload a CSV file or click 'Use samples/Data.csv'.")
    st.stop()

if errors:
    with st.expander("CSV Warnings / Errors", expanded=True):
        for e in errors:
            st.warning(e)

st.subheader("Data Preview")
st.dataframe(df.head(20), use_container_width=True)

# -------------------------------------------------
# Placeholder mapping
# -------------------------------------------------
placeholders = templater.extract_placeholders(template_svg_text)
text_placeholders = [p for p in placeholders if p != "var_BarcodeImg"]

st.subheader("Field Mapping")

# Try to auto-map from config/mapping_presets.json
preset = {}
try:
    preset_path = CONFIG_DIR / "mapping_presets.json"
    if preset_path.exists():
        preset = json.loads(preset_path.read_text(encoding="utf-8")).get("default", {})
except Exception:
    preset = {}

if "mapping" not in st.session_state:
    st.session_state.mapping = {}

mapping_cols = {}
for pid in text_placeholders:
    # Heuristic default: remove 'var_' and case-insensitive match to columns
    default_guess = preset.get(pid)
    if not default_guess:
        guess = pid.replace("var_", "").strip().lower()
        for c in df.columns:
            if c.strip().lower() == guess:
                default_guess = c
                break
    mapping_cols[pid] = st.selectbox(
        f"{pid} ↔ CSV column",
        options=[""] + list(df.columns),
        index=(1 + list(df.columns).index(default_guess)) if default_guess in df.columns else 0,
        key=f"map_{pid}",
    )

# Barcode mapping (only if placeholder exists)
barcode_col = None
if "var_BarcodeImg" in placeholders:
    suggested = "Barcode" if "Barcode" in df.columns else ""
    barcode_col = st.selectbox(
        "var_BarcodeImg ↔ CSV column (barcode data)",
        options=[""] + list(df.columns),
        index=(1 + list(df.columns).index(suggested)) if suggested in df.columns else 0,
        key="map_barcode",
    )

# -------------------------------------------------
# Row selection & Preview
# -------------------------------------------------
st.subheader("Preview")
row_idx = st.number_input("Row index (0-based)", min_value=0, max_value=max(len(df) - 1, 0), value=0)

col_p1, col_p2 = st.columns([1, 1])
with col_p1:
    if st.button("Generate Preview PDF", type="primary", use_container_width=True):
        row = df.iloc[int(row_idx)].to_dict()
        # Build value map for text placeholders
        value_map = {}
        for pid, colname in mapping_cols.items():
            if colname:
                raw = row.get(colname, "")
                value_map[pid] = utils.to_str(raw)
        # Barcode image (optional)
        barcode_data_uri = None
        if barcode_col and barcode_col in df.columns and pd.notna(row.get(barcode_col, None)):
            bdata = str(row.get(barcode_col))
            try:
                png_bytes = bc.generate_barcode_png(bdata, kind=barcode_type)
                barcode_data_uri = utils.png_bytes_to_data_uri(png_bytes)
            except Exception as e:
                st.error(f"Barcode generation failed: {e}")
        # Fill SVG
        filled_svg = templater.fill_svg(template_svg_text, value_map, barcode_data_uri)
        # Convert to PDF
        pdf_bytes = pdf_engine.svg_to_pdf(filled_svg, dpi=int(CFG.get("dpi", 96)))
        fname = utils.safe_filename(f"preview_{row_idx}_{row.get('PRODUCT_NAME', 'label')}.pdf")
        st.download_button(
            "Download preview PDF",
            data=pdf_bytes,
            file_name=fname,
            mime="application/pdf",
            use_container_width=True,
        )
        st.session_state["_last_preview_pdf"] = pdf_bytes

with col_p2:
    if st.session_state.get("_last_preview_pdf"):
        st.caption("Last preview generated. Re-run to refresh.")

# -------------------------------------------------
# Batch generation
# -------------------------------------------------
st.subheader("Batch Generation")

def build_value_map_for_row(row_dict):
    vm = {}
    for pid, colname in mapping_cols.items():
        if colname:
            vm[pid] = utils.to_str(row_dict.get(colname, ""))
    return vm

if st.button("Generate ALL (ZIP)", use_container_width=True):
    if not any(mapping_cols.values()):
        st.error("Please map at least one placeholder to a CSV column.")
        st.stop()

    progress = st.progress(0, text="Preparing...")
    total = len(df)

    def each_pdf():
        for i, (idx, row) in enumerate(df.iterrows(), start=1):
            row_dict = row.to_dict()

            # barcode (optional)
            barcode_uri = None
            if barcode_col and pd.notna(row_dict.get(barcode_col, None)):
                try:
                    png = bc.generate_barcode_png(str(row_dict.get(barcode_col)), kind=barcode_type)
                    barcode_uri = utils.png_bytes_to_data_uri(png)
                except Exception:
                    barcode_uri = None  # row will still be generated without barcode image

            # value map + svg → pdf
            vm = build_value_map_for_row(row_dict)
            svg_txt = templater.fill_svg(template_svg_text, vm, barcode_uri)
            pdf_bytes = pdf_engine.svg_to_pdf(svg_txt, dpi=int(CFG.get("dpi", 96)))

            # filename
            base = row_dict.get("PRODUCT_NAME") or row_dict.get("STYLE") or row_dict.get("BATCH") or f"row{idx}"
            progress.progress(min(i / max(total, 1), 1.0), text=f"Generated {i}/{total}")

            yield utils.safe_filename(f"{base}_{idx}.pdf"), pdf_bytes

    zip_bytes = pdf_engine.zip_pdfs(each_pdf())
    st.download_button(
        "Download ALL as ZIP",
        data=zip_bytes,
        file_name="labels_batch.zip",
        mime="application/zip",
        use_container_width=True,
    )
