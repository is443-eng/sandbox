import os
import math
import csv
import argparse
from datetime import datetime, timedelta, timezone

import numpy as np
import requests
from dotenv import load_dotenv
from sgp4.api import Satrec

from tle_history import append_tle_to_history

# -----------------------------
# Time + coordinate math
# -----------------------------

def julian_date(dt_utc: datetime) -> float:
    """Julian Date for a timezone-aware UTC datetime."""
    year = dt_utc.year
    month = dt_utc.month
    day = dt_utc.day
    hour = dt_utc.hour
    minute = dt_utc.minute
    second = dt_utc.second + dt_utc.microsecond / 1e6

    if month <= 2:
        year -= 1
        month += 12

    A = year // 100
    B = 2 - A + (A // 4)

    jd_day = int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + B - 1524.5
    jd_frac = (hour + minute / 60.0 + second / 3600.0) / 24.0
    return jd_day + jd_frac

def gmst_radians(dt_utc: datetime) -> float:
    """Greenwich Mean Sidereal Time (approx) in radians."""
    jd = julian_date(dt_utc)
    T = (jd - 2451545.0) / 36525.0
    gmst_deg = (
        280.46061837
        + 360.98564736629 * (jd - 2451545.0)
        + 0.000387933 * T * T
        - (T * T * T) / 38710000.0
    )
    gmst_deg = gmst_deg % 360.0
    return math.radians(gmst_deg)

def eci_to_ecef(r_eci_km: np.ndarray, dt_utc: datetime) -> np.ndarray:
    """Rotate ECI (TEME-ish) to ECEF using GMST (approx)."""
    theta = gmst_radians(dt_utc)
    c = math.cos(theta)
    s = math.sin(theta)
    R = np.array([
        [ c,  s, 0.0],
        [-s,  c, 0.0],
        [0.0, 0.0, 1.0],
    ])
    return R @ r_eci_km

def ecef_to_geodetic_wgs84(r_ecef_km: np.ndarray):
    """Convert ECEF (km) to geodetic lat/lon/alt (deg, deg, km) on WGS84."""
    a = 6378.137  # km
    f = 1 / 298.257223563
    e2 = f * (2 - f)

    x, y, z = r_ecef_km
    lon = math.atan2(y, x)

    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - e2))
    for _ in range(6):
        sin_lat = math.sin(lat)
        N = a / math.sqrt(1 - e2 * sin_lat * sin_lat)
        alt = p / math.cos(lat) - N
        lat = math.atan2(z, p * (1 - e2 * (N / (N + alt))))

    sin_lat = math.sin(lat)
    N = a / math.sqrt(1 - e2 * sin_lat * sin_lat)
    alt = p / math.cos(lat) - N

    lat_deg = math.degrees(lat)
    lon_deg = (math.degrees(lon) + 540) % 360 - 180  # [-180, 180]
    return lat_deg, lon_deg, alt

# -----------------------------
# Circular stats for longitude
# -----------------------------

def circular_mean_deg(angles_deg: np.ndarray) -> float:
    """Mean angle in degrees for circular data."""
    ang = np.deg2rad(angles_deg)
    s = np.mean(np.sin(ang))
    c = np.mean(np.cos(ang))
    mu = math.atan2(s, c)
    mu_deg = (math.degrees(mu) + 540) % 360 - 180
    return mu_deg

def circular_std_deg(angles_deg: np.ndarray) -> float:
    """Circular standard deviation in degrees (wrap-safe)."""
    ang = np.deg2rad(angles_deg)
    s = np.mean(np.sin(ang))
    c = np.mean(np.cos(ang))
    R = math.hypot(s, c)
    R = min(max(R, 1e-12), 1.0)  # clamp
    std_rad = math.sqrt(-2.0 * math.log(R))
    return math.degrees(std_rad)

def circular_span_deg(angles_deg: np.ndarray) -> float:
    """
    Approx span around circular mean: compute deviations from mean on [-180,180]
    and take max-min.
    """
    mu = circular_mean_deg(angles_deg)
    # wrapped difference
    d = (angles_deg - mu + 540) % 360 - 180
    return float(d.max() - d.min())

# -----------------------------
# N2YO TLE fetch
# -----------------------------

def fetch_tle(norad_id: int, api_key: str):
    # N2YO format as discussed: /tle/{id}&apiKey=...
    url = f"https://api.n2yo.com/rest/v1/satellite/tle/{norad_id}&apiKey={api_key}"
    resp = requests.get(url, timeout=30)
    return resp.status_code, resp.json()

# -----------------------------
# Main
# -----------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fetch Arcturus TLE from N2YO, propagate 24h, output lat/lon/alt + ECEF XYZ and stationkeeping metrics."
    )
    parser.add_argument("--hours", type=float, default=24.0, help="Duration forward from start time (UTC). Default 24.")
    parser.add_argument("--step", type=int, default=60, help="Step size in seconds. Default 60.")
    parser.add_argument("--out", type=str, default="arcturus_24h_track.csv", help="Output CSV filename.")
    parser.add_argument("--no-history", action="store_true", help="Do not append TLE to history file.")
    parser.add_argument("--record-only", action="store_true", help="Only fetch TLE and append to history; no propagation.")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("N2YO_API_KEY")
    if not api_key:
        raise RuntimeError("N2YO_API_KEY not found in environment (.env)")

    norad_id = 56371  # Astranis Arcturus

    status, data = fetch_tle(norad_id, api_key)
    print("TLE fetch status code:", status)
    if status != 200:
        print("Response JSON:", data)
        raise SystemExit("TLE request failed; check API key and endpoint.")

    satname = data.get("info", {}).get("satname", "UNKNOWN")
    tle_raw = data.get("tle", "")

    if "\r\n" in tle_raw:
        line1, line2 = tle_raw.split("\r\n", 1)
    elif "\n" in tle_raw:
        line1, line2 = tle_raw.split("\n", 1)
    else:
        raise RuntimeError("Unexpected TLE format in response (missing line break).")

    print("satname:", satname)
    print("satid:", norad_id)

    if not args.no_history:
        try:
            hist_path = append_tle_to_history(norad_id, line1, line2, fetched_at=datetime.now(timezone.utc))
            print("TLE appended to", hist_path)
        except Exception as e:
            print("Warning: could not append TLE to history:", e)

    if args.record_only:
        print("Record-only: TLE recorded. Exiting.")
        return

    sat = Satrec.twoline2rv(line1.strip(), line2.strip())

    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=args.hours)

    rows = []
    lats = []
    lons = []
    alts = []

    t = start
    while t <= end:
        jd = julian_date(t)
        fr = 0.0
        e, r_eci, _v_eci = sat.sgp4(jd, fr)
        if e != 0:
            # Skip epochs with SGP4 error codes
            t += timedelta(seconds=args.step)
            continue

        r_eci = np.array(r_eci, dtype=float)  # km
        r_ecef = eci_to_ecef(r_eci, t)
        lat, lon, alt_km = ecef_to_geodetic_wgs84(r_ecef)

        rows.append({
            "timestamp_utc": t.isoformat(),
            "lat_deg": float(lat),
            "lon_deg": float(lon),
            "alt_km": float(alt_km),
            "x_ecef_km": float(r_ecef[0]),
            "y_ecef_km": float(r_ecef[1]),
            "z_ecef_km": float(r_ecef[2]),
        })

        lats.append(lat)
        lons.append(lon)
        alts.append(alt_km)

        t += timedelta(seconds=args.step)

    if not rows:
        raise SystemExit("No propagated points produced (unexpected).")

    # Write CSV
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["timestamp_utc", "lat_deg", "lon_deg", "alt_km", "x_ecef_km", "y_ecef_km", "z_ecef_km"]
        )
        w.writeheader()
        w.writerows(rows)

    lats = np.array(lats, dtype=float)
    lons = np.array(lons, dtype=float)
    alts = np.array(alts, dtype=float)

    # Stationkeeping-ish summaries over this 24h prediction window
    mean_lon = circular_mean_deg(lons)
    lon_std = circular_std_deg(lons)
    lon_span = circular_span_deg(lons)
    max_abs_lat = float(np.max(np.abs(lats)))

    alt_mean = float(np.mean(alts))
    alt_std = float(np.std(alts))

    print(f"\nWrote {len(rows)} points to {args.out}")
    print("\n24h summary (from propagated positions):")
    print(f"  mean_lon_deg:     {mean_lon:.6f}")
    print(f"  lon_std_deg:      {lon_std:.6f}   (circular std dev)")
    print(f"  lon_span_deg:     {lon_span:.6f}  (max-min around mean, wrap-safe)")
    print(f"  max_abs_lat_deg:  {max_abs_lat:.6f}")
    print(f"  alt_mean_km:      {alt_mean:.3f}")
    print(f"  alt_std_km:       {alt_std:.3f}")

    print("\nPreview (first 3 rows):")
    for r in rows[:3]:
        print(r)

if __name__ == "__main__":
    main()
