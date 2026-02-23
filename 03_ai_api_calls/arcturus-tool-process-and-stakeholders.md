# Arcturus tracking app — process diagram and stakeholder mapping

Homework tool: **Arcturus orbit viewer** (Streamlit app in `02_productivity/shiny_app`). It runs the tracker script `01_query_api/04_arcturus_track_ecef_metrics.py` and visualizes the satellite ground track on two PyDeck maps.

---

## Process diagram (inputs → steps → outputs)

```mermaid
flowchart TB
    subgraph inputs["Inputs"]
        direction LR
        I1[Propagation window<br/>hours, step]
        I2[N2YO_API_KEY in .env]
        I3[Tracker script<br/>04_arcturus_track_ecef_metrics.py]
    end

    S1[Run tracker subprocess]
    S2[Load CSV to DataFrame]
    S3[Compute metrics]
    S4[Build path and scatter layers]
    S5[Render PyDeck maps]

    subgraph outputs["Outputs"]
        direction TB
        O1[Metrics row]
        O2[Global view map]
        O3[Track shape map]
        O4[Track table and propagation log]
        O1 --- O2
        O3 --- O4
    end

    I1 --> S1
    I2 --> S1
    I3 --> S1
    S1 --> S2 --> S3 --> S4 --> S5
    S5 --> O1
    S5 --> O2
    S5 --> O3
    S5 --> O4
```

---

## Stakeholder needs → system goals

| Stakeholder need | System goal |
|------------------|-------------|
| See where Arcturus is (and will be) over a time window | Run SGP4 propagation from live TLE and show the ground track on a map. |
| Compare global orbit vs detailed path shape | Provide two views: a global map and a zoom-to-fit track-shape map. |
| Adjust how far ahead and how fine the prediction is | Expose propagation window (hours) and time step (seconds) in the UI. |
| Get quick orbit stats without reading raw CSV | Compute and display metrics (point count, mean lon/lat, altitude mean/std). |
| Debug when propagation or API fails | Run tracker in subprocess and surface stdout/stderr in an expandable log. |
| Use one place for run and visualize (no CLI only) | Integrate tracker script as a subprocess so "Run propagation" runs and displays in the same app. |
