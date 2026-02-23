# Context for Arcturus Streamlit App

Use this document (and the files/links below) when building the Streamlit app that plots the **Arcturus** satellite track using `04_arcturus_track_ecef_metrics.py`.

---

## 1. Local files to reference

| File | Purpose |
|------|---------|
| `01_query_api/04_arcturus_track_ecef_metrics.py` | **Core program.** Fetches TLE from N2YO, propagates orbit with SGP4, outputs CSV with `timestamp_utc`, `lat_deg`, `lon_deg`, `alt_km`, `x_ecef_km`, `y_ecef_km`, `z_ecef_km`. CLI: `--hours`, `--step`, `--out`. Requires `N2YO_API_KEY` in `.env`. |
| `01_query_api/README.md` | **Docs.** Overview, API endpoint, CSV column definitions, usage, and example output. |
| `.env` (project root) | **Secrets.** Must contain `N2YO_API_KEY` for N2YO; script and app will need access. |

### Script behavior (summary)

- **Inputs:** `--hours` (float, default 24), `--step` (int, seconds, default 60), `--out` (CSV path).
- **Output:** CSV with columns above; one row per timestep. Use `lat_deg` and `lon_deg` for mapping.
- **Options for the app:** (A) Run the script as a subprocess (e.g. with temp CSV), then read CSV and plot; or (B) Refactor script to expose a function that returns the track data (no CSV) and call it from Streamlit.

---

## 2. Internet resources

### Streamlit – maps and charts

- **st.map** – Simple map with scatter points (lat/lon). Auto-centers and zooms.  
  https://docs.streamlit.io/develop/api-reference/charts/st.map  
  - Use a DataFrame with columns for latitude and longitude (e.g. `lat_deg`, `lon_deg`). Streamlit often auto-detects `lat`/`lon`; if your columns are `lat_deg`/`lon_deg`, pass them explicitly: `st.map(df, latitude="lat_deg", longitude="lon_deg")`.

- **st.pydeck_chart** – PyDeck-based maps (e.g. paths/lines, 3D). Good for orbit tracks.  
  https://docs.streamlit.io/develop/api-reference/charts/st.pydeck_chart  
  - PyDeck docs: https://deckgl.readthedocs.io/

### Streamlit – running the script / subprocess

- **Running a Python script from Streamlit:** Use `sys.executable` so the subprocess uses the same environment:  
  `subprocess.run([sys.executable, "path/to/04_arcturus_track_ecef_metrics.py", "--hours", "24", "--out", "out.csv"])`  
  - Knowledge base: https://docs.streamlit.io/knowledge-base/deploy/invoking-python-subprocess-deployed-streamlit-app  
- **Live output in the UI:** Use asyncio + `st.empty()` / `st.code()` to stream stdout/stderr:  
  https://techoverflow.net/2024/11/29/streamlit-complete-subprocess-run-live-update-solution-with-success-display/

### Streamlit – general

- **Get started:** https://docs.streamlit.io/get-started  
- **API reference (charts):** https://docs.streamlit.io/develop/api-reference/charts  
- **Configuration (e.g. .streamlit/config.toml):** https://docs.streamlit.io/develop/concepts/configuration

### Data format for plotting

- CSV from the script has: `timestamp_utc`, `lat_deg`, `lon_deg`, `alt_km`, `x_ecef_km`, `y_ecef_km`, `z_ecef_km`.
- For **st.map**: use `lat_deg` and `lon_deg` (WGS84).
- For **pydeck path/line**: use the same columns; order by `timestamp_utc` for a time-ordered track.

---

## 3. Suggested app flow

1. **Sidebar or form:** Hours, step (optional), “Run propagation” button.
2. **On “Run”:** Call the script (subprocess or refactored function) and get a CSV (or DataFrame).
3. **Load CSV** into a DataFrame (e.g. `pd.read_csv`).
4. **Plot:** Use `st.map(df, latitude="lat_deg", longitude="lon_deg")` for a simple map, or `st.pydeck_chart` with a PyDeck path layer for a connected orbit track.
5. **Optional:** Show metrics (mean lon, lon std, alt mean, etc.) from the script output or recompute from the DataFrame; display in `st.metric` or `st.json`.

---

## 4. Quick reference – CSV columns

| Column         | Use in app        |
|----------------|-------------------|
| `timestamp_utc`| Sort order, labels |
| `lat_deg`      | Map latitude      |
| `lon_deg`      | Map longitude     |
| `alt_km`       | Altitude display  |
| `x_ecef_km`, etc. | Optional 3D/ECEF |

Save this file and reference it (e.g. `@CONTEXT.md`) when asking the AI to generate or modify the Streamlit app.
