import json, os, sys
D = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(D, "page_template.html")).read()
money = open(os.path.join(D, "ca13_money.json")).read()
ca = json.load(open(os.path.join(D, "ca_counties.geojson")))
for f in ca["features"]:   # trim coordinates to 3 decimals to keep the page small
    def rnd(c): return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 3), round(c[1], 3)]
    f["geometry"]["coordinates"] = rnd(f["geometry"]["coordinates"]); f["properties"] = {"name": f["properties"]["name"]}
cd = json.load(open(os.path.join(D, "cd13_prop50.geojson")))
for k, v in (("/*MONEY*/{}", money), ("/*CA_COUNTIES*/null", json.dumps(ca, separators=(",", ":"))), ("/*CD13*/null", json.dumps(cd, separators=(",", ":")))):
    assert t.count(k) == 1, k; t = t.replace(k, v)
open(sys.argv[1], "w").write(t); print("built", len(t))
