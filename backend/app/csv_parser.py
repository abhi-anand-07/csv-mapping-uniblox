import io
import pandas as pd
from typing import List, Dict, Any
from app.models import IngestionResult


def detect_type(series: pd.Series) -> str:
    """Heuristic to detect the semantic type of a pandas Series."""
    if series.empty:
        return "empty"

    non_null = series.dropna()
    if non_null.empty:
        return "empty"

    sample = non_null.head(20)
    unique_count = non_null.nunique()
    total_count = len(non_null)

    # Boolean checks
    bool_like = {"yes", "no", "true", "false", "1", "0", "y", "n", "t", "f"}
    lower_vals = set(str(v).strip().lower() for v in sample if pd.notna(v))
    if lower_vals.issubset(bool_like) and len(lower_vals) <= 4:
        return "boolean"

    # Numeric checks (before date to avoid epoch false positives like 0, 1, 2)
    try:
        cleaned = non_null.astype(str).str.replace(r"[$,]", "", regex=True)
        parsed = pd.to_numeric(cleaned, errors="coerce")
        if parsed.notna().sum() / total_count > 0.8:
            # If all values are small integers, they might be dates (epoch) or actual integers
            # Heuristic: if values look like years (1900-2100) or have separators, check date
            vals = parsed.dropna()
            if (vals % 1 == 0).all():
                # Could be integer or epoch seconds
                # If all values are between 1900 and 2100, treat as integer (likely count or year)
                if vals.between(0, 2100).all() and not vals.between(30000, 50000).any():
                    # But check if they look like dates with dashes/slashes in original strings
                    date_like = sum(1 for v in non_null if '/' in str(v) or '-' in str(v))
                    if date_like / total_count < 0.5:
                        return "integer"
                return "integer"
            return "numeric"
    except Exception:
        pass

    # Date checks
    try:
        parsed = pd.to_datetime(non_null, errors="coerce", infer_datetime_format=True)
        if parsed.notna().sum() / total_count > 0.8:
            return "date"
    except Exception:
        pass

    # State check (2-letter codes)
    states = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        "DC", "PR"
    }
    upper_vals = set(str(v).strip().upper() for v in sample if pd.notna(v))
    if upper_vals.issubset(states) and len(upper_vals) <= 10:
        return "state"

    # ZIP check
    zip_vals = [str(v).strip() for v in sample if pd.notna(v)]
    if all(v.isdigit() and len(v) == 5 for v in zip_vals[:10]):
        return "zip"

    return "string"


def parse_csv(file_bytes: bytes) -> IngestionResult:
    """
    Step 1 of the agent pipeline: Ingest and understand the CSV.
    Handles encoding issues, extracts metadata, sample rows, and column statistics.
    """
    warnings: List[str] = []

    # Try common encodings
    df: pd.DataFrame
    for encoding in ["utf-8", "latin1", "cp1252"]:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            warnings.append(f"Failed with {encoding}: {str(e)}")
            continue
    else:
        raise ValueError("Could not decode CSV file with any common encoding")

    if df.empty:
        raise ValueError("CSV file is empty or has no rows")

    headers = list(df.columns)

    # Handle unnamed columns
    unnamed_count = 0
    new_headers = []
    for h in headers:
        if str(h).startswith("Unnamed:"):
            unnamed_count += 1
            new_headers.append(f"unnamed_col_{unnamed_count}")
        else:
            new_headers.append(str(h).strip())
    df.columns = new_headers
    headers = new_headers

    if unnamed_count > 0:
        warnings.append(f"Detected {unnamed_count} unnamed column(s)")

    # Deduplicate headers
    seen = set()
    deduped = []
    counts = {}
    for h in headers:
        if h in seen:
            counts[h] = counts.get(h, 1) + 1
            deduped.append(f"{h}_dup{counts[h]}")
        else:
            seen.add(h)
            deduped.append(h)
    df.columns = deduped
    headers = deduped

    row_count = len(df)
    sample_rows = df.head(5).fillna("").to_dict(orient="records")

    column_stats = {}
    for col in headers:
        series = df[col]
        null_count = series.isna().sum() + (series.astype(str).str.strip() == "").sum()
        null_pct = round(null_count / row_count * 100, 1)
        detected_type = detect_type(series)
        unique_vals = series.dropna().astype(str).unique()[:5].tolist()

        column_stats[col] = {
            "null_count": int(null_count),
            "null_percentage": null_pct,
            "detected_type": detected_type,
            "unique_values": unique_vals,
            "sample_values": series.dropna().head(3).astype(str).tolist(),
        }

    return IngestionResult(
        headers=headers,
        sample_rows=sample_rows,
        row_count=row_count,
        column_stats=column_stats,
        parsing_warnings=warnings,
    )
