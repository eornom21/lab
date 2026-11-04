#!/usr/bin/env python3
"""Fetch the 120th Congress district outlines (the lines in force for the Nov 3, 2026 election, Jan 1, 2026 vintage) from
the Census Bureau's TIGERweb service, simplified for a national map, into electionlab/geo/cd120.json.
Run by .github/workflows/fetch_cd.yml (the cloud workspace can't reach census.gov)."""
import json, urllib.request, urllib.parse, sys
BASE = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/0/query"
feats, off = [], 0
while True:
    q = {"where": "1=1", "outFields": "STATE,CD120,GEOID,BASENAME,INTPTLAT,INTPTLON,AREALAND", "f": "geojson", "outSR": "4326",
         "maxAllowableOffset": "0.012", "geometryPrecision": "3", "resultOffset": str(off), "resultRecordCount": "100", "orderByFields": "GEOID"}
    with urllib.request.urlopen(BASE + "?" + urllib.parse.urlencode(q), timeout=120) as r: j = json.load(r)
    fs = j.get("features") or []
    feats += fs; off += len(fs)
    print("got", len(fs), "total", len(feats), file=sys.stderr)
    if not fs or not (j.get("exceededTransferLimit") or (j.get("properties") or {}).get("exceededTransferLimit")) and len(fs) < 100: break
    if len(fs) < 100: break
out = []
for f in feats:
    p = f.get("properties") or {}
    cd = p.get("CD120")
    if cd in (None, "ZZ"): continue
    out.append({"type": "Feature", "properties": {"st": p.get("STATE"), "cd": cd, "geoid": p.get("GEOID"), "lat": float(p.get("INTPTLAT") or 0), "lon": float(p.get("INTPTLON") or 0), "area": p.get("AREALAND")}, "geometry": f.get("geometry")})
json.dump({"type": "FeatureCollection", "source": "Census TIGERweb, 120th Congressional Districts (Jan 1, 2026 vintage), simplified 0.012 deg", "features": out}, open("electionlab/geo/cd120.json", "w"), separators=(",", ":"))
print("wrote", len(out), "districts", file=sys.stderr)
