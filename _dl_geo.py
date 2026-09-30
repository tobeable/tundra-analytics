import urllib.request, json, os

url = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"
out = r"c:\Users\A1C21E9\.snowflake\cortex\playground\workspace\src\assets\countries.geojson"

urllib.request.urlretrieve(url, out)
with open(out, encoding="utf-8") as f:
    data = json.load(f)
n = len(data["features"])
codes = [feat["properties"].get("ADM0_A3", "?") for feat in data["features"]]
size_kb = os.path.getsize(out) / 1024
print(f"Features: {n}")
print(f"Sample ADM0_A3: {codes[:10]}")
print(f"Size: {size_kb:.0f} KB")
