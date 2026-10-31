"""Build lab.nathanwmonroe.com/ca13 from ca13_data.json and ca13_geo.json in this folder.
Usage (from the repo root): python3 _ca13_src/build_page.py ca13/index.html
Live 2026 results come straight from api.sos.ca.gov in the viewer's browser (the feed allows it), every minute.
"""
import json, os, sys
D = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(D, "page_template.html")).read()
data = json.load(open(os.path.join(D, "ca13_data.json")))
geo = json.load(open(os.path.join(D, "ca13_geo.json")))
for key, val in (("/*DATA*/{}", json.dumps(data, ensure_ascii=False, separators=(",", ":"))), ("/*GEO*/{}", json.dumps(geo, separators=(",", ":")))):
    assert t.count(key) == 1, key
    t = t.replace(key, val.replace("</", "<\\/"))
out = sys.argv[1]
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, "w").write(t)
print("built", out, len(t))
