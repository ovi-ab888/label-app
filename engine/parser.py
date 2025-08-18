from __future__ import annotations
from io import BytesIO, StringIO
from typing import List, Tuple, Union, IO
import pandas as pd

REQUIRED_SUGGESTED = ["PRODUCT_NAME", "COLOUR", "STYLE", "BATCH", "Barcode"]

def load_csv(src: Union[str, BytesIO, StringIO, IO[str]]) -> Tuple[pd.DataFrame, List[str]]:
    df = pd.read_csv(src)
    errors: List[str] = []
    drop_cols = [c for c in df.columns if str(c).startswith("Unnamed:")]
    if drop_cols:
        df = df.drop(columns=drop_cols)
        errors.append(f"Dropped columns: {', '.join(drop_cols)}")
    df.columns = [str(c).strip() for c in df.columns]
    if df.empty:
        errors.append("CSV is empty.")
    missing = [c for c in REQUIRED_SUGGESTED if c not in df.columns]
    if missing:
        errors.append(f"Suggested columns missing: {', '.join(missing)} (you can still map manually)")
    return df, errors
