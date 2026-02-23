import os
import requests
from dotenv import load_dotenv

load_dotenv()
N2YO_API_KEY = os.getenv("N2YO_API_KEY")
if not N2YO_API_KEY:
    raise RuntimeError("N2YO_API_KEY not found in environment (.env)")

NORAD_ID = 56371  # ARCTURUS (Astranis)

# N2YO docs: Request /tle/{id} and append &apiKey=...  (example: .../tle/25544&apiKey=...)  :contentReference[oaicite:2]{index=2}
url = f"https://api.n2yo.com/rest/v1/satellite/tle/{NORAD_ID}&apiKey={N2YO_API_KEY}"

resp = requests.get(url, timeout=30)

print("Status code:", resp.status_code)
data = resp.json()

# Print the minimum you need to start tracking:
# - satellite name/id
# - the TLE string (split into two lines)
print("satname:", data.get("info", {}).get("satname"))
print("satid:", data.get("info", {}).get("satid"))

tle = data.get("tle", "")
print("\nTLE (raw):")
print(tle)

if "\r\n" in tle:
    line1, line2 = tle.split("\r\n", 1)
    print("\nTLE (two lines):")
    print(line1)
    print(line2)
