"""
Arcturus orbit tracker — Streamlit app (03 version) WITH COVERAGE BEAM.
Archived copy: includes coverage beam circle + beam center offset (nadir/steered).
Uses 04_arcturus_track_ecef_metrics.py to propagate; shows global view + color-coded
analemma (figure-8) with time-of-day scale. Astranis-inspired theme.
"""

import math
import sys
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import pydeck as pdk

# -----------------------------------------------------------------------------
# Paths (app lives in 03_ai_api_calls; sandbox = parent)
# -----------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
TRACKER_SCRIPT = REPO_ROOT / "01_query_api" / "04_arcturus_track_ecef_metrics.py"

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


def coverage_beam_circle(lat_deg: float, lon_deg: float, half_angle_deg: float, n_pts: int = 64) -> list[list[float]]:
    """Return a closed ring of [lon, lat] points (in degrees) for a circular beam on the sphere.
    Center at (lat_deg, lon_deg); half_angle_deg = angular radius of the circle in degrees.
    """
    lat_rad = math.radians(lat_deg)
    lon_rad = math.radians(lon_deg)
    d_rad = math.radians(half_angle_deg)
    ring = []
    for i in range(n_pts):
        bearing = 2.0 * math.pi * i / n_pts
        # Destination point given start (lat_rad, lon_rad), bearing (rad from N), angular dist d_rad
        lat2 = math.asin(
            math.sin(lat_rad) * math.cos(d_rad)
            + math.cos(lat_rad) * math.sin(d_rad) * math.cos(bearing)
        )
        lon2 = lon_rad + math.atan2(
            math.sin(bearing) * math.sin(d_rad) * math.cos(lat_rad),
            math.cos(d_rad) - math.sin(lat_rad) * math.sin(lat2),
        )
        ring.append([math.degrees(lon2), math.degrees(lat2)])
    ring.append(ring[0])
    return ring


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
    st.divider()
    st.markdown("**Coverage beam**")
    beam_half_angle = st.slider(
        "Beam half-angle (°)",
        1.0, 20.0, 6.0, 0.5,
        help="Angular radius of coverage circle. ~1° ≈ 110 km; 6° ≈ 670 km.",
    )
    st.caption("Beam center offset (for steered beam):")
    beam_offset_lat = st.number_input("Lat offset (°)", -30.0, 30.0, 0.0, 0.5, help="Positive = north of sub-satellite point")
    beam_offset_lon = st.number_input("Lon offset (°)", -30.0, 30.0, 0.0, 0.5, help="Positive = east of sub-satellite point")
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
# Coverage beam: center = sub-satellite point + optional offset (for steered/off-nadir beam)
beam_center_lat = float(last["lat_deg"]) + beam_offset_lat
beam_center_lon = float(last["lon_deg"]) + beam_offset_lon
beam_ring = coverage_beam_circle(beam_center_lat, beam_center_lon, beam_half_angle)
beam_df = pd.DataFrame([{"polygon": [beam_ring]}])
beam_layer = pdk.Layer(
    "PolygonLayer",
    data=beam_df,
    get_polygon="polygon",
    get_fill_color=[0, 119, 182, 55],
    get_line_color=[0, 168, 232, 200],
    get_line_width=2,
    line_width_min_pixels=2,
    line_width_units="pixels",
    pickable=False,
)
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
    layers=[beam_layer, path_layer, scatter_layer],
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
    st.caption(
    "Orbit path (blue); dot = satellite. **N/S inclination** describes where the sub-satellite point moves (the figure-8), not antenna pointing. "
    "Coverage circle = estimated footprint: default center is **nadir** (straight below). Use **lat/lon offset** in sidebar for a steered beam (e.g. off the equator)."
)

with col_ana:
    st.subheader("Analemma (figure-8)")
    st.pydeck_chart(deck_ana, use_container_width=True, height=MAP_HEIGHT)
    st.markdown(scale_html, unsafe_allow_html=True)

# ---- Report ----
def build_report_md(
    mean_lon: float, mean_lat: float, n_pts: int, alt_mean: float, alt_std: float,
    drift_deg_per_day: float, ew_box_deg: float, ns_box_deg: float,
    inclination_proxy_deg: float, radial_km: float,
    slot_lon: float | None, delta_slot: float | None, hours: float, step: int,
) -> str:
    lines = [
        "# Arcturus orbit report",
        "", f"*Generated from propagation: {hours:.0f} h window, {step} s step*", "",
        "## Summary",
        f"- **Points:** {n_pts:,}", f"- **Mean longitude:** {mean_lon:.2f}°",
        f"- **Mean latitude:** {mean_lat:.2f}°", f"- **Altitude:** {alt_mean:.1f} ± {alt_std:.2f} km", "",
        "## Station-keeping (GEO compliance)",
        f"- **Longitude drift:** {drift_deg_per_day:.4f} °/day",
        f"- **E–W box width:** {ew_box_deg:.3f}°", f"- **N–S box height:** {ns_box_deg:.3f}°",
        f"- **Inclination proxy (N–S amplitude):** {inclination_proxy_deg:.3f}°",
        f"- **Radial variation:** {radial_km:.2f} km",
    ]
    if slot_lon is not None and delta_slot is not None:
        lines.append(f"- **Δ from assigned slot ({slot_lon:.1f}°):** {delta_slot:.3f}°")
    lines.extend(["", "---", "*Arcturus · NORAD 56371 · Astranis*"])
    return "\n".join(lines)

st.divider()
st.subheader("Report")
report_md = build_report_md(
    mean_lon=mean_lon, mean_lat=mean_lat, n_pts=n_pts, alt_mean=alt_mean, alt_std=alt_std,
    drift_deg_per_day=drift_deg_per_day, ew_box_deg=ew_box_deg, ns_box_deg=ns_box_deg,
    inclination_proxy_deg=inclination_proxy_deg, radial_km=radial_km,
    slot_lon=slot_lon,
    delta_slot=delta_from_slot_deg(mean_lon, slot_lon) if slot_lon is not None else None,
    hours=hours, step=step,
)
report_col1, _ = st.columns(2)
with report_col1:
    st.download_button(
        label="Download report (Markdown)",
        data=report_md,
        file_name="arcturus_report.md",
        mime="text/markdown",
        type="secondary",
    )
with st.expander("Preview report (Markdown)"):
    st.markdown(report_md)

with st.expander("Track data (first 10 rows)"):
    st.dataframe(df.head(10), use_container_width=True, hide_index=True)
if log_message:
    with st.expander("Propagation log"):
        st.code(log_message)
