"""
Arcturus orbit tracker — Streamlit app (03 version).
Uses 04_arcturus_track_ecef_metrics.py to propagate; shows global view + color-coded
analemma (figure-8) with time-of-day scale. No coverage beam (see arcturus_app_with_beam.py for that).
Astranis-inspired theme.
"""

import math
import sys
import subprocess
import tempfile
from pathlib import Path
import os
import textwrap
from io import BytesIO

import numpy as np
import pandas as pd
import streamlit as st
import pydeck as pdk
import requests
from dotenv import load_dotenv
try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
except ImportError:
    Image = ImageDraw = ImageFont = None

# TLE history and burn detection (script lives in 01_query_api)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "01_query_api"))
from tle_history import (
    load_tle_history,
    detect_burns,
    burns_per_week_series,
    get_history_path,
)

# -----------------------------------------------------------------------------
# Paths (app lives in 03_ai_api_calls; sandbox = parent)
# -----------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
TRACKER_SCRIPT = REPO_ROOT / "01_query_api" / "04_arcturus_track_ecef_metrics.py"
NORAD_ID = 56371
TLE_DATA_DIR = REPO_ROOT / "01_query_api" / "data"

# Load environment variables (including OPENAI_API_KEY) from project-root .env
load_dotenv(dotenv_path=REPO_ROOT / ".env")


# -----------------------------------------------------------------------------
# AI report generation prompt (locked content; do not edit)
# -----------------------------------------------------------------------------
AI_REPORT_PROMPT = """
# Executive Satellite Briefing Prompt — Editable Knobs Version

---

## KNOB GROUP A — Report Purpose & Audience

*(Safe to edit tone and wording only — does not affect calculations or visuals)*

**Goal**

* Generate a single-page executive satellite operations briefing

**Input**

* CSV of propagated sub-satellite geodetic positions

  * timestamp
  * latitude
  * longitude
  * optional altitude
* Typical duration: 24–72 hours

**Audience**

* Non-specialists (management / customers / partners)

**Communication Priority**

* Operational understanding
* Not academic orbital mechanics

---

## KNOB GROUP B — Visual Theme (Branding Layer)

*(Safe to change aesthetic style — layout and analytics unaffected)*

### Background Rules

* Entire canvas dark navy/black
* No white backgrounds anywhere
* Panels visually blend into background
* No visible plotting frames

### Color Palette (locked mapping)

| Element                   | Color     |
| ------------------------- | --------- |
| Primary orbit path        | `#7DF9FF` |
| Secondary gradient accent | `#4FD1C5` |
| Start marker              | `#00FFA3` |
| End marker                | `#FFD166` |
| Reference crosshair       | `#94A3B8` |
| Primary text              | `#E5E7EB` |
| Secondary text            | `#9CA3AF` |
| Maneuver detection        | `#FF4D6D` |

* Do not use plotting defaults
* Do not substitute colors

---

## KNOB GROUP C — Layout Engine

*(Changing this changes structure but not analysis)*

### Title

* Title should be at top with subtitle below.

### Grid

* Strict 2×2 equal-size panel grid
* Even spacing
* Perfect alignment
* all panels below title and subtitle, no overlap
* Panels must never intersect or share pixel space under any circumstance
* Renderer must automatically shrink panel content if needed to preserve separation

### Panel Map

| Position     | Panel     |
| ------------ | --------- |
| Top-Left     | Analemma  |
| Top-Right    | Metrics   |
| Bottom-Left  | Globe     |
| Bottom-Right | Narrative |

### Text Collision Handling

The renderer must:

* Measure bounding boxes
* Resize fonts dynamically
* Wrap text
* Reposition content

**Rule:** shrink text before allowing overlap

---

## KNOB GROUP D — File Interpretation Rules

*(Controls metadata extraction — safe to modify parsing policy)*

From filename:

* Extract 4–6 digit NORAD-style number
* Label: `NORAD ID (from filename)`

Selection logic:

* Choose most plausible candidate if multiple
* If none → `not provided`

---

## KNOB GROUP E — Data Detection Rules

*(Controls robustness to different CSV formats)*

Automatically detect columns:

* Timestamp
* Latitude
* Longitude
* Optional altitude

Automatically infer:

* Sampling cadence
* Total time span
* GEO-like behavior

---

## KNOB GROUP F — Orbital Analytics Engine

*(This section controls the math — changing values here changes conclusions)*

### Compute

* Mean longitude
* North-south span
* East-west span
* Drift rate (deg/day linear fit)
* Inclination estimate
* Altitude variation

### Maneuver Detection Logic

Detect via:

* Slope change
* Position jump
* Curvature break

Return exactly:

* Maneuver detected
* No maneuver detected
* Inconclusive

### Numeric Formatting Rule (Required)

All numeric outputs shown to the user must be rounded to reasonable precision:

* Longitudes and spans: 2 decimal places
* Drift rate: 3 decimal places (deg/day)
* Inclination estimate: 2 decimal places
* Altitude variation: 1 decimal place (if present)

If raw floating-point precision or excessive decimals are displayed → abort render and print:

`ERROR: numeric formatting invalid`

---

## KNOB GROUP G — Analemma Visualization

*(Pure visualization of computed orbit behavior)*

Title (locked):

* `Analemma`
* No subtitles allowed

Plot:

* Latitude vs longitude
* Centered on mean longitude

Include:

* Center crosshair
* Start marker
* End marker
* Smooth time gradient

  * Early `#4FD1C5`
  * Late `#7DF9FF`
* Bright green labels at exactly: 0hr, 6hr, 12hr, 18hr, 24hr

### Label Enforcement Rule (Required)

The renderer MUST compute the nearest data point to each target elapsed time and place a visible label for ALL five times:

* 0hr
* 6hr
* 12hr
* 18hr
* 24hr

If any label cannot be placed → abort render and print:

`ERROR: analemma time labels missing`

* No map background

Purpose:

* Motion direction visible without labels

---

## KNOB GROUP H — Globe Visualization (Hard-Data Version)

*(Geographic context layer — mandatory, never optional)*

### Purpose

The globe must provide real-world geographic context.
A blank sphere is considered a rendering failure.

If geographic coastlines cannot be rendered, the program must **stop and report an error instead of producing output**.

---

### Data Source Requirement (Mandatory)

The renderer MUST load a real Earth polygon dataset before plotting.

Acceptable sources (priority order):

1. Natural Earth (1:110m or 1:50m)
2. GSHHG coastline dataset
3. Built-in geopandas Natural Earth dataset

Unacceptable:

* Procedural continents
* Placeholder shapes
* Simplified circles
* Empty sphere fallback

If the dataset cannot be loaded → abort render and print:

`ERROR: geographic dataset unavailable — globe cannot be rendered`

---

### Projection Rules

Projection: orthographic

The globe must be centered on:

* latitude = final sub-satellite latitude
* longitude = final sub-satellite longitude

The sub-satellite point must always appear at the center of the visible hemisphere.

---

### Visual Elements

#### Sphere

* Dark sphere background
* No grid shading
* No texture maps

#### Reference Lines

* Equator line
* Prime meridian

#### Continents

* Real land polygons required
* Must match recognizable Earth geography

Appearance:

* Fill: very low contrast dark land
* Coastlines: slightly brighter than land
* Country borders: bright green (#00FFA3)

### Boundary Enforcement (Required)

Country borders MUST be visibly rendered in bright green and visually distinguishable from coastlines.

If borders are not present or not visually distinguishable → abort render and print:

`ERROR: country borders missing`

Failure to distinguish land vs ocean visually = render failure

---

### Visibility Rules

Polygons must be clipped to the visible hemisphere.

No wrap-around artifacts allowed:

* no lines across space
* no back-side continents
* no polygon spikes

---

### Sub-Satellite Marker

Plot at exact final timestamp location.

Marker:

* color: `#FFD166`
* must lie directly over the Earth surface

Label (locked):

* Display the timestamp corresponding to the final data point
* Do NOT display the phrase "Sub-satellite point"
* This label must be positioned outside the marker to avoid obscuring geography

---

### Globe Title Rule

* The globe panel must NOT display any title text

---

### Verification Step (Required)

After plotting, renderer must verify:

1. At least one land polygon was drawn
2. The sub-satellite point is inside the sphere boundary
3. The globe contains non-uniform pixel values (not blank)
4. Country border pixels exist

If any fail → abort output and print:

`ERROR: globe verification failed`

---

### Rendering Priority

The globe is considered a **primary analytic element**, not decoration.

If the globe fails, the slide must NOT be produced.

---

## KNOB GROUP I — Metrics Panel Content

*(Operational numbers only — wording safe to edit)*

Title (locked):

* `Operational metrics`

Show exactly these and no others:

* Mean longitude
* North-south span
* East-west span
* Drift rate
* Inclination estimate
* Altitude variation
* Maneuver status

### Metrics Enforcement Rule (Required)

The renderer must verify all seven metrics are displayed.

If any metric is missing → abort render and print:

`ERROR: metrics panel incomplete`

### Absolute Title Placement Rule (Required)

The title must be drawn using fixed panel coordinates:

* Title anchor position: `(x = 0.02, y = 0.96)` in panel axes coordinates
* Vertical alignment: top
* Metrics content region begins at `y = 0.86`
* Metrics must only be drawn inside `0.02 ≤ x ≤ 0.98` and `0.02 ≤ y ≤ 0.86`

Renderer must NOT compute placement relative to text bounding boxes.

**Verification:**

If any metric text has `y > 0.86` → abort render and print:

`ERROR: metrics title overlap`

**Rule:** Shrink metric font or wrap text — never move title or metrics above the boundary.

Exclude all other values.

---

## KNOB GROUP J — Narrative Generator

*(Editable explanation logic — safe for tone adjustments)*

Title (locked):

* `Operational Summary`

### Content Requirements (Mandatory)

The narrative must:

1. Reference the computed operational metrics numerically
2. Explain whether the satellite is holding its slot
3. Explain whether a maneuver occurred
4. Explain the physical meaning of the figure-8
5. Contain at least 4 complete sentences

If fewer than four sentences OR no numeric references → abort render and print:

`ERROR: narrative insufficient detail`

### Absolute Title Placement Rule (Required)

The title must be drawn using fixed panel coordinates:

* Title anchor position: `(x = 0.02, y = 0.96)` in panel axes coordinates
* Vertical alignment: top

The Narrative panel is divided into two hard regions:

**Title band (reserved):**
`0.90 ≤ y ≤ 1.00`

**Narrative text region (allowed area only):**
`0.02 ≤ y ≤ 0.80`

The renderer must place the paragraph starting at:

`y_start = 0.80`

and text must flow downward only.

The renderer must NEVER place any narrative text above `y = 0.80`.

---

### Hard Containment Verification (Required)

After rendering, the renderer must compute the bounding box of all narrative text.

If any pixel of the paragraph lies above `y = 0.80` → abort render and print:

`ERROR: narrative text entered title band`

---

### Layout Adjustment Rules (Required)

If the paragraph does not fit inside `0.02 ≤ y ≤ 0.80`, the renderer must apply in order:

1. Reduce body font size
2. Increase wrapping (shorter line width)
3. Reduce line spacing

The renderer must NEVER move the paragraph upward and must NEVER move the title.

Do NOT describe or explain the color gradient or color meaning of the analemma.

---

## KNOB GROUP K — Output Constraints

*(Hard constraints — changing breaks deliverable expectations)*

* Single cohesive slide
* Not a paper
* Not multi-page

### Slide Header Rules (locked)

* Title: `'NORAD ID extracted from file name' 24hr Report`
* Subtitle: must display the exact time interval covered by the dataset

---

## Why This Structure Helps

You can now safely edit:

| If you want to change… | Edit this knob |
| ---------------------- | -------------- |
| Wording                | A, I, J        |
| Brand look             | B              |
| Panel arrangement      | C              |
| Filename parsing       | D              |
| CSV robustness         | E              |
| Orbit math             | F              |
| Plot appearance        | G, H           |
| Output format          | K              |

---
"""


# -----------------------------------------------------------------------------
# Astranis-style CSS
# -----------------------------------------------------------------------------
ASTRA_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root {
  --astranis-blue: #0077B6;
  --astranis-blue-light: #00A8E8;
  --space-black: #0D1117;
  --space-gray: #161B22;
  --text-primary: #E6EDF3;
  --text-muted: #8B949E;
}
.stApp { background-color: var(--space-black); }
h1, h2, h3 { font-family: 'Inter', sans-serif !important; color: var(--text-primary) !important; }
h1 { font-weight: 700 !important; letter-spacing: -0.02em !important; border-bottom: 2px solid var(--astranis-blue); padding-bottom: 0.3em !important; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, var(--space-gray) 0%, var(--space-black) 100%) !important; }
[data-testid="stSidebar"] .stMarkdown { color: var(--text-primary) !important; }
[data-testid="metric-label"] { color: var(--text-muted) !important; }
[data-testid="stMetricValue"] { color: var(--astranis-blue-light) !important; }
div[data-testid="stExpander"] { background: var(--space-gray) !important; border-radius: 8px !important; }
.stButton > button {
  background: var(--astranis-blue) !important;
  color: white !important;
  font-weight: 600 !important;
  border-radius: 6px !important;
  border: none !important;
  padding: 0.5rem 1.25rem !important;
  transition: background 0.2s ease !important;
}
.stButton > button:hover {
  background: var(--astranis-blue-light) !important;
  box-shadow: 0 0 12px rgba(0, 168, 232, 0.4) !important;
}
</style>
"""

# -----------------------------------------------------------------------------
# Run tracker script
# -----------------------------------------------------------------------------
def run_tracker(hours: float, step: int, out_path: Path) -> tuple[bool, str]:
    """Run 04_arcturus_track_ecef_metrics.py; return (success, message)."""
    if not TRACKER_SCRIPT.exists():
        return False, f"Tracker script not found: {TRACKER_SCRIPT}"
    cmd = [
        sys.executable,
        str(TRACKER_SCRIPT),
        "--hours", str(hours),
        "--step", str(step),
        "--out", str(out_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        if result.returncode != 0:
            return False, err or out or f"Exit code {result.returncode}"
        return True, out
    except subprocess.TimeoutExpired:
        return False, "Propagation timed out (120s)."
    except Exception as e:
        return False, str(e)


def run_tracker_record_only() -> tuple[bool, str]:
    """Run tracker with --record-only to fetch and append current TLE to history."""
    if not TRACKER_SCRIPT.exists():
        return False, "Tracker script not found."
    cmd = [sys.executable, str(TRACKER_SCRIPT), "--record-only"]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        if result.returncode != 0:
            return False, err or out or f"Exit code {result.returncode}"
        return True, out
    except subprocess.TimeoutExpired:
        return False, "Request timed out."
    except Exception as e:
        return False, str(e)


def show_tle_section():
    """Render TLE history, record button, burn detection, and maneuver frequency chart."""
    st.divider()
    st.subheader("TLE history & station-keeping burns")
    st.caption("Successive TLEs are recorded when you run propagation or click **Record current TLE**. Burns are inferred from changes in inclination, RAAN, eccentricity, or mean motion between consecutive TLEs.")
    hist_path = get_history_path(NORAD_ID, TLE_DATA_DIR)
    if not hist_path.exists():
        st.info("No TLE history yet. Run **Run propagation** or click **Record current TLE** to build history.")
    if st.button("Record current TLE", type="secondary", help="Fetch latest TLE from N2YO and append to history (no propagation)."):
        ok, msg = run_tracker_record_only()
        if ok:
            st.success("TLE recorded.")
            st.rerun()
        else:
            st.error(msg)
    tle_df = load_tle_history(NORAD_ID, TLE_DATA_DIR)
    if tle_df.empty:
        return
    st.markdown(f"**TLE history** ({len(tle_df)} records)")
    with st.expander("View TLE history (epoch & elements)", expanded=False):
        display_cols = ["epoch_utc", "incl_deg", "raan_deg", "ecc", "mean_motion_rev_per_day"]
        st.dataframe(tle_df[display_cols].tail(50), use_container_width=True, hide_index=True)
    st.markdown("**Burn detection** (thresholds apply to consecutive TLE pairs)")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        thresh_incl = st.number_input("Δ incl (°)", 0.0, 0.5, 0.008, 0.001, key="th_incl")
    with c2:
        thresh_raan = st.number_input("Δ RAAN (°)", 0.0, 0.5, 0.03, 0.005, key="th_raan")
    with c3:
        thresh_ecc = st.number_input("Δ ecc", 0.0, 0.001, 0.00008, 0.00001, format="%.5f", key="th_ecc")
    with c4:
        thresh_mm = st.number_input("Δ mean motion", 0.0, 0.02, 0.002, 0.0005, key="th_mm")
    burns_df = detect_burns(tle_df, thresh_incl_deg=thresh_incl, thresh_raan_deg=thresh_raan, thresh_ecc=thresh_ecc, thresh_mean_motion=thresh_mm)
    if burns_df.empty:
        st.caption("No burns detected with current thresholds.")
    else:
        st.markdown(f"**Detected burns:** {len(burns_df)}")
        with st.expander("Burn table", expanded=True):
            st.dataframe(
                burns_df[["epoch_utc", "burn_type", "d_incl_deg", "d_raan_deg", "d_ecc", "d_mean_motion"]].rename(columns={"epoch_utc": "Epoch (UTC)", "burn_type": "Type", "d_incl_deg": "Δincl °", "d_raan_deg": "ΔRAAN °", "d_ecc": "Δecc", "d_mean_motion": "ΔMM"}),
                use_container_width=True,
                hide_index=True,
            )
        weeks = st.slider("Maneuver frequency window (weeks)", 4, 52, 12, key="burns_weeks")
        freq = burns_per_week_series(burns_df, weeks=weeks)
        if not freq.empty:
            st.markdown("**Maneuvers per week**")
            freq_df = freq.reset_index()
            freq_df.columns = ["week_start", "burns"]
            freq_df["week_start"] = freq_df["week_start"].dt.strftime("%Y-%m-%d")
            st.bar_chart(freq_df.set_index("week_start")["burns"], height=280)
        else:
            st.caption("No burn counts in the selected window.")


# -----------------------------------------------------------------------------
# Station-keeping metrics
# -----------------------------------------------------------------------------
def circular_lon_span_deg(lon_deg: np.ndarray) -> float:
    """Wrap-safe longitude span in degrees."""
    rad = np.deg2rad(np.asarray(lon_deg, dtype=float))
    return float(np.ptp(np.unwrap(rad)) * 180.0 / math.pi)


def longitude_drift_deg_per_day(lon_deg: np.ndarray, hours: float) -> float:
    """Estimate longitude drift (°/day) from first to last point."""
    if len(lon_deg) < 2 or hours <= 0:
        return 0.0
    diff = (float(lon_deg[-1]) - float(lon_deg[0]) + 180.0) % 360.0 - 180.0
    return diff / (hours / 24.0)


def delta_from_slot_deg(mean_lon: float, slot_lon: float) -> float:
    """Circular difference mean_lon − slot_lon in [-180, 180]."""
    return (mean_lon - slot_lon + 180.0) % 360.0 - 180.0


def hour_to_rgba(h: float) -> list[int]:
    """Map hour 0–24 to blue → cyan → yellow → blue (same as analemma)."""
    x = (h / 24.0) * 2.0 * math.pi
    r = int(127 + 128 * math.sin(x))
    g = int(127 + 128 * math.sin(x + 2.0 * math.pi / 3.0))
    b = int(127 + 128 * math.sin(x + 4.0 * math.pi / 3.0))
    return [max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)), 255]


def rgba_to_hex(r: int, g: int, b: int) -> str:
    """Convert 0–255 RGB to #RRGGBB."""
    return f"#{r:02x}{g:02x}{b:02x}"


# -----------------------------------------------------------------------------
# Page config and layout
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Arcturus Tracker | Astranis",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(ASTRA_CSS, unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### 🛰️ Arcturus Tracker")
    st.markdown("*NORAD 56371 · Astranis*")
    st.divider()
    hours = st.slider("Propagation window (hours)", 1.0, 72.0, 24.0, 1.0)
    step = st.selectbox("Time step (seconds)", [60, 120, 300], index=0)
    st.divider()
    st.markdown("**Station-keeping**")
    use_slot = st.checkbox("Compare to assigned slot", value=False, help="Show Δ from target longitude")
    slot_lon = st.number_input("Assigned slot longitude (°)", -180.0, 180.0, 0.0, 0.5, disabled=not use_slot) if use_slot else None
    run_clicked = st.button("Run propagation", type="primary", use_container_width=True)

st.title("Arcturus orbit track")
st.caption("Geodetic track from SGP4 propagation · WGS84")

# Run propagation and load data
csv_path = None
log_message = ""
if run_clicked:
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        csv_path = Path(f.name)
    success, log_message = run_tracker(hours, step, csv_path)
    if not success:
        st.error("Propagation failed")
        st.code(log_message)
        if csv_path and csv_path.exists():
            csv_path.unlink()
        st.stop()

if run_clicked and csv_path and csv_path.exists():
    try:
        df = pd.read_csv(csv_path)
        df = df.sort_values("timestamp_utc").reset_index(drop=True)
        st.session_state["track_df"] = df
        st.session_state["track_log"] = log_message
    except Exception as e:
        st.error(f"Could not load CSV: {e}")
        st.stop()
    finally:
        if csv_path.exists():
            csv_path.unlink()

if "track_df" not in st.session_state:
    st.info("Use the sidebar to set the propagation window and click **Run propagation** to compute the Arcturus track.")
    if log_message:
        with st.expander("Last run output"):
            st.code(log_message)
    show_tle_section()
    st.stop()

df = st.session_state["track_df"]
log_message = st.session_state.get("track_log", "")

# Metrics row
mean_lon = df["lon_deg"].mean()
mean_lat = df["lat_deg"].mean()
alt_mean = df["alt_km"].mean()
alt_std = df["alt_km"].std()
n_pts = len(df)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Points", f"{n_pts:,}")
m2.metric("Mean longitude (°)", f"{mean_lon:.2f}")
m3.metric("Mean latitude (°)", f"{mean_lat:.2f}")
m4.metric("Altitude mean (km)", f"{alt_mean:.1f}")
m5.metric("Altitude std (km)", f"{alt_std:.2f}")

# Station-keeping metrics
lat_min_deg = float(df["lat_deg"].min())
lat_max_deg = float(df["lat_deg"].max())
ns_box_deg = lat_max_deg - lat_min_deg
ew_box_deg = circular_lon_span_deg(df["lon_deg"].values)
ts_first = pd.to_datetime(df["timestamp_utc"].iloc[0])
ts_last = pd.to_datetime(df["timestamp_utc"].iloc[-1])
total_hours = (ts_last - ts_first).total_seconds() / 3600.0
drift_deg_per_day = longitude_drift_deg_per_day(df["lon_deg"].values, total_hours)
inclination_proxy_deg = ns_box_deg / 2.0
radial_km = float(df["alt_km"].max() - df["alt_km"].min())

st.subheader("Station-keeping (GEO compliance)")
sk1, sk2, sk3, sk4, sk5, sk6 = st.columns(6)
sk1.metric("Longitude drift", f"{drift_deg_per_day:.4f}", "°/day")
sk2.metric("E–W box width", f"{ew_box_deg:.3f}", "°")
sk3.metric("N–S box height", f"{ns_box_deg:.3f}", "°")
sk4.metric("Incl. proxy (N–S amp)", f"{inclination_proxy_deg:.3f}", "°")
sk5.metric("Radial variation", f"{radial_km:.2f}", "km")
if slot_lon is not None:
    delta_slot = delta_from_slot_deg(mean_lon, slot_lon)
    sk6.metric("Δ from assigned slot", f"{delta_slot:.3f}", "°")
else:
    sk6.metric("Δ from assigned slot", "—", "set in sidebar")

# ---- Global view: path, coverage beam, current position ----
path_data = df[["lon_deg", "lat_deg"]].values.tolist()
path_df = pd.DataFrame([{"path": path_data}])
path_layer = pdk.Layer(
    "PathLayer",
    data=path_df,
    get_path="path",
    get_color=[0, 119, 182, 200],
    get_width=2.5,
    width_min_pixels=2,
    cap_rounded=True,
    joint_rounded=True,
)
last = df.iloc[-1]
scatter_df = pd.DataFrame([{"lon": last["lon_deg"], "lat": last["lat_deg"], "alt_km": last["alt_km"]}])
scatter_layer = pdk.Layer(
    "ScatterplotLayer",
    data=scatter_df,
    get_position=["lon", "lat"],
    get_radius=25000,
    get_fill_color=[0, 168, 232, 255],
    get_line_color=[255, 255, 255, 255],
    get_line_width_min_pixels=1,
    radius_min_pixels=3,
    radius_max_pixels=6,
    pickable=True,
)
view_global = pdk.ViewState(
    latitude=float(mean_lat),
    longitude=float(mean_lon),
    zoom=1.5,
    pitch=0,
    bearing=0,
)
deck_global = pdk.Deck(
    layers=[path_layer, scatter_layer],
    initial_view_state=view_global,
    map_style="dark",
    tooltip={"text": "Arcturus · Alt: {alt_km} km"},
)

# Analemma view (zoom + center) and layer — build before same-row layout
lat_min, lat_max = float(df["lat_deg"].min()), float(df["lat_deg"].max())
lon_min, lon_max = float(df["lon_deg"].min()), float(df["lon_deg"].max())
lon_span = lon_max - lon_min
if lon_span <= 0:
    lon_span += 360.0
lat_span = max(lat_max - lat_min, 0.5)
lon_span = max(lon_span, 0.5)
padding = 1.15
zoom_lon = math.log2(360.0 / (lon_span * padding))
zoom_lat = math.log2(180.0 / (lat_span * padding))
zoom_fit = max(1.0, min(min(zoom_lon, zoom_lat), 15.0))
zoom_ana = min(15.0, zoom_fit + 1.0)
lat_center = (lat_min + lat_max) / 2
lon_center = (lon_min + lon_max) / 2

df_ana = df[["lon_deg", "lat_deg", "timestamp_utc"]].copy()
ts = pd.to_datetime(df_ana["timestamp_utc"])
df_ana["hour_utc"] = ts.dt.hour + ts.dt.minute / 60.0 + ts.dt.second / 3600.0
df_ana["color"] = df_ana["hour_utc"].apply(hour_to_rgba)

ana_layer = pdk.Layer(
    "ScatterplotLayer",
    data=df_ana,
    get_position=["lon_deg", "lat_deg"],
    get_fill_color="color",
    get_radius=4000,
    radius_min_pixels=2,
    radius_max_pixels=6,
    pickable=True,
)
view_ana = pdk.ViewState(
    latitude=lat_center,
    longitude=lon_center,
    zoom=zoom_ana,
    pitch=0,
    bearing=0,
)
deck_ana = pdk.Deck(
    layers=[ana_layer],
    initial_view_state=view_ana,
    map_style="dark",
    tooltip={"text": "Lon: {lon_deg:.2f}° · Lat: {lat_deg:.2f}° · Hour UTC: {hour_utc:.1f}"},
)

# Color scale for analemma (time of day UTC)
scale_hours = [0, 4, 8, 12, 16, 20, 24]
scale_html_parts = []
for h in scale_hours:
    r, g, b, _ = hour_to_rgba(h)
    hex_c = rgba_to_hex(r, g, b)
    label = "00:00" if h == 0 else "24:00" if h == 24 else f"{h:02d}:00"
    scale_html_parts.append(
        f'<span style="display:inline-block;width:1.8em;height:1em;background:{hex_c};'
        f'border:1px solid #444;border-radius:2px;vertical-align:middle;" title="{label} UTC"></span>'
        f'<span style="color:#8B949E;font-size:0.85em;margin-right:0.8em;">{label}</span>'
    )
scale_html = (
    '<div style="margin-bottom:0.5em;">'
    '<span style="color:#8B949E;font-size:0.9em;margin-right:0.5em;">Time of day (UTC):</span>'
    + "".join(scale_html_parts) +
    '</div>'
)

# ---- Same row: global view | analemma; tops aligned; scale below analemma ----
MAP_HEIGHT = 700
col_global, col_ana = st.columns([2, 1])

with col_global:
    st.subheader("Global view")
    st.pydeck_chart(deck_global, use_container_width=True, height=MAP_HEIGHT)
    st.caption("Orbit path (blue); dot = current satellite position. Analemma (right) shows N–S / E–W motion by time of day (UTC).")

with col_ana:
    st.subheader("Analemma (figure-8)")
    st.pydeck_chart(deck_ana, use_container_width=True, height=MAP_HEIGHT)
    st.markdown(scale_html, unsafe_allow_html=True)

# ---- Download propagation data (for AI report generation) ----
st.divider()
st.subheader("Download propagation data")
st.caption("Download the propagation as CSV to use as context in an AI prompt for report generation.")
propagation_csv = df.to_csv(index=False)
st.download_button(
    label="Download propagation (CSV)",
    data=propagation_csv,
    file_name=f"arcturus_propagation_{NORAD_ID}_{ts_first.strftime('%Y%m%d_%H%M')}.csv",
    mime="text/csv",
    type="secondary",
)

st.subheader("AI-generated executive briefing")
st.caption("Use your OpenAI API key (`OPENAI_API_KEY` in `.env`) to generate a one-page executive report from the current propagation.")
ai_col1, ai_col2 = st.columns([1, 2])
with ai_col1:
    generate_clicked = st.button("Generate AI report", type="primary")
with ai_col2:
    st.caption("The AI uses a fixed prompt (Knob Groups A–K) and the current propagation CSV.")

ai_report = None
if generate_clicked:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("`OPENAI_API_KEY` not found in environment (.env). Please add it and restart the app.")
    else:
        try:
            # Use a reasonably sized CSV string as context
            csv_text = df.to_csv(index=False)
            # Trim extremely large CSVs to avoid hitting token limits
            if len(csv_text) > 200_000:
                csv_text = csv_text[:200_000]
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert satellite operations analyst who produces concise executive briefings.",
                    },
                    {
                        "role": "user",
                        "content": AI_REPORT_PROMPT + "\n\n---\n\nCSV DATA:\n\n" + csv_text,
                    },
                ],
            }
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60,
            )
            if resp.status_code != 200:
                st.error(f"OpenAI API error ({resp.status_code}): {resp.text[:500]}")
            else:
                data = resp.json()
                try:
                    ai_report = data["choices"][0]["message"]["content"]
                except Exception:
                    st.error("Unexpected OpenAI response format.")
        except Exception as e:
            st.error(f"Error calling OpenAI API: {e}")

if ai_report:
    st.markdown("**AI Executive Briefing**")
    # Show as plain text in the app.
    st.text(ai_report)

    # Always offer Markdown download of the raw AI output.
    st.download_button(
        label="Download AI report (Markdown)",
        data=ai_report,
        file_name=f"arcturus_ai_report_{NORAD_ID}_{ts_first.strftime('%Y%m%d_%H%M')}.md",
        mime="text/markdown",
        type="secondary",
    )

    # Optional: render a simple PNG slide containing the AI text (requires Pillow).
    if Image is not None:
        try:
            img_width, img_height = 1600, 900
            background_color = (10, 15, 25)      # dark navy/black
            text_color = (229, 231, 235)         # primary text

            img = Image.new("RGB", (img_width, img_height), color=background_color)
            draw = ImageDraw.Draw(img)

            margin = 80
            max_chars_per_line = 90
            wrapped_text = textwrap.fill(ai_report, width=max_chars_per_line)

            try:
                font = ImageFont.truetype("DejaVuSans.ttf", 26)
            except Exception:
                font = ImageFont.load_default()

            draw.multiline_text(
                (margin, margin),
                wrapped_text,
                fill=text_color,
                font=font,
                spacing=6,
            )

            buf = BytesIO()
            img.save(buf, format="PNG")
            png_bytes = buf.getvalue()

            st.download_button(
                label="Download AI report (PNG)",
                data=png_bytes,
                file_name=f"arcturus_ai_report_{NORAD_ID}_{ts_first.strftime('%Y%m%d_%H%M')}.png",
                mime="image/png",
                type="secondary",
            )
        except Exception as e:
            st.caption(f"PNG export unavailable: {e}")

with st.expander("Track data (first 10 rows)"):
    st.dataframe(df.head(10), use_container_width=True, hide_index=True)
if log_message:
    with st.expander("Propagation log"):
        st.code(log_message)

show_tle_section()
