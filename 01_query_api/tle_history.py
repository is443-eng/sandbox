"""
TLE history storage and station-keeping burn detection.
Parse TLE orbital elements, append to a CSV history, and flag maneuvers from
consecutive TLE deltas (inclination, RAAN, eccentricity, mean motion).
"""

import csv
import math
from datetime import datetime, timezone
from pathlib import Path

# TLE format (1-based columns per CelesTrak): Line1 epoch 19-20 year, 21-32 day; Line2 incl 9-16, raan 18-25, ecc 27-33, argp 35-42, M 44-51, mm 53-63
# Python 0-based: line1[18:20], line1[20:32]; line2[8:16], [17:25], [26:33], [34:42], [43:51], [52:63]


def parse_tle_epoch(line1: str) -> datetime:
    """Parse epoch from TLE line 1 (UTC)."""
    yy = int(line1[18:20].strip())
    day_frac = float(line1[20:32].strip())
    year = 2000 + yy if yy < 57 else 1900 + yy
    # Day of year 1 = Jan 1 00:00; day_frac is fractional day
    base = datetime(year, 1, 1, tzinfo=timezone.utc)
    from datetime import timedelta
    epoch = base + timedelta(days=day_frac - 1.0)
    return epoch


def parse_tle_elements(line2: str) -> dict:
    """Parse orbital elements from TLE line 2. Angles in degrees, mean motion in rev/day."""
    incl = float(line2[8:16].strip())
    raan = float(line2[17:25].strip())
    ecc_str = line2[26:33].strip()
    ecc = float("0." + ecc_str) if ecc_str else 0.0
    argp = float(line2[34:42].strip())
    ma = float(line2[43:51].strip())
    mm = float(line2[52:63].strip())  # rev/day
    return {"incl_deg": incl, "raan_deg": raan, "ecc": ecc, "argp_deg": argp, "ma_deg": ma, "mean_motion_rev_per_day": mm}


def parse_tle(line1: str, line2: str) -> dict:
    """Return dict with epoch_utc (ISO), incl_deg, raan_deg, ecc, argp_deg, ma_deg, mean_motion_rev_per_day."""
    line1 = line1.strip()
    line2 = line2.strip()
    epoch = parse_tle_epoch(line1)
    el = parse_tle_elements(line2)
    el["epoch_utc"] = epoch.isoformat()
    el["epoch"] = epoch
    return el


HISTORY_COLUMNS = [
    "fetched_at_utc", "epoch_utc", "line1", "line2",
    "incl_deg", "raan_deg", "ecc", "argp_deg", "ma_deg", "mean_motion_rev_per_day",
]


def get_history_path(norad_id: int, data_dir: Path | None = None) -> Path:
    """Path to TLE history CSV for this NORAD ID."""
    if data_dir is None:
        data_dir = Path(__file__).resolve().parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / f"tle_history_{norad_id}.csv"


def append_tle_to_history(
    norad_id: int,
    line1: str,
    line2: str,
    fetched_at: datetime | None = None,
    data_dir: Path | None = None,
) -> Path:
    """Append one TLE record to history CSV. Returns path to file."""
    path = get_history_path(norad_id, data_dir)
    fetched_at = fetched_at or datetime.now(timezone.utc)
    try:
        parsed = parse_tle(line1.strip(), line2.strip())
    except (ValueError, IndexError) as e:
        raise ValueError(f"TLE parse error: {e}") from e
    row = {
        "fetched_at_utc": fetched_at.isoformat(),
        "epoch_utc": parsed["epoch_utc"],
        "line1": line1.strip(),
        "line2": line2.strip(),
        "incl_deg": parsed["incl_deg"],
        "raan_deg": parsed["raan_deg"],
        "ecc": parsed["ecc"],
        "argp_deg": parsed["argp_deg"],
        "ma_deg": parsed["ma_deg"],
        "mean_motion_rev_per_day": parsed["mean_motion_rev_per_day"],
    }
    file_exists = path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HISTORY_COLUMNS)
        if not file_exists:
            w.writeheader()
        w.writerow(row)
    return path


def load_tle_history(norad_id: int, data_dir: Path | None = None):
    """Load TLE history as a list of dicts, sorted by epoch_utc. Returns [] if file missing."""
    import pandas as pd
    path = get_history_path(norad_id, data_dir)
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if df.empty:
        return df
    df["epoch_dt"] = pd.to_datetime(df["epoch_utc"], utc=True)
    df = df.sort_values("epoch_dt").reset_index(drop=True)
    return df


def _delta_deg(a1: float, a2: float) -> float:
    """Signed difference a2 - a1 in [-180, 180] for angles."""
    d = (a2 - a1 + 540.0) % 360.0 - 180.0
    return d


def detect_burns(
    df,
    thresh_incl_deg: float = 0.008,
    thresh_raan_deg: float = 0.03,
    thresh_ecc: float = 0.00008,
    thresh_mean_motion: float = 0.002,
) -> "pd.DataFrame":
    """
    Compare consecutive TLEs and flag rows where a significant change indicates a burn.
    Returns DataFrame with columns: epoch_utc, epoch_dt, burn_type, d_incl, d_raan, d_ecc, d_mean_motion, index.
    """
    import pandas as pd
    if df is None or not isinstance(df, pd.DataFrame) or len(df) < 2:
        return pd.DataFrame()
    df = df.sort_values("epoch_dt").reset_index(drop=True)
    burns = []
    for i in range(1, len(df)):
        r0 = df.iloc[i - 1]
        r1 = df.iloc[i]
        d_incl = float(r1["incl_deg"] - r0["incl_deg"])
        d_raan = _delta_deg(float(r0["raan_deg"]), float(r1["raan_deg"]))
        d_ecc = float(r1["ecc"] - r0["ecc"])
        d_mm = float(r1["mean_motion_rev_per_day"] - r0["mean_motion_rev_per_day"])
        types = []
        if abs(d_incl) >= thresh_incl_deg:
            types.append("incl")
        if abs(d_raan) >= thresh_raan_deg:
            types.append("raan")
        if abs(d_ecc) >= thresh_ecc:
            types.append("ecc")
        if abs(d_mm) >= thresh_mean_motion:
            types.append("mm")
        if types:
            burns.append({
                "epoch_utc": r1["epoch_utc"],
                "epoch_dt": r1["epoch_dt"],
                "burn_type": "+".join(types),
                "d_incl_deg": d_incl,
                "d_raan_deg": d_raan,
                "d_ecc": d_ecc,
                "d_mean_motion": d_mm,
                "index": i,
            })
    return pd.DataFrame(burns)


def burns_per_week_series(burns_df, weeks: int = 12):
    """
    Given a burns DataFrame with epoch_dt, return a Series of burn counts per week (last `weeks` weeks).
    Index = week start (Sunday) UTC, value = count. Only weeks that have at least one burn are included
    unless we reindex; here we return counts for weeks that appear in the data.
    """
    import pandas as pd
    if burns_df is None or burns_df.empty:
        return pd.Series(dtype=int)
    df = burns_df.copy()
    df["epoch_dt"] = pd.to_datetime(df["epoch_dt"], utc=True)
    df = df[df["epoch_dt"] >= (df["epoch_dt"].max() - pd.Timedelta(weeks=weeks))]
    df["week"] = df["epoch_dt"].dt.to_period("W").dt.start_time
    counts = df.groupby("week").size()
    return counts.astype(int)
