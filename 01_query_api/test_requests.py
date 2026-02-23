import requests

url = "https://httpbin.org/post"
payload = {"name": "test"}

r = requests.post(url, json=payload)
r.raise_for_status()
print(r.json())