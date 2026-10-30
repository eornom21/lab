"""Build lab.nathanwmonroe.com/electionnight from races.json and money.json in this folder.
Usage (from the repo root): python3 _electionnight_src/build_page.py electionnight/index.html
results.json (live winners, edited on election night) is published beside the page and read by it every minute.
"""
import json, os, sys
D = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(D, "page_template.html")).read()
css = open(os.path.join(D, "base.css")).read()
races = json.load(open(os.path.join(D, "races.json")))
money = json.load(open(os.path.join(D, "money.json")))
keep = ["id", "label", "d", "r", "incumbent", "inc_party", "open_seat", "blurb", "cook", "sabato", "inside", "d_case", "r_case", "talk8"]
races = [{k: r.get(k) for k in keep} for r in races]
m = {k: {kk: v[kk] for kk in ("receipts", "itemized", "home", "out_share", "nstates", "states", "map_cov")} for k, v in money.items()}
for k in m: m[k]["out"] = m[k].pop("out_share")
for k in m: m[k]["cov"] = m[k].pop("map_cov")
for key, val in (("/*BASECSS*/", css), ("/*RACES*/[]", json.dumps(races, separators=(",", ":"))), ("/*MONEY*/{}", json.dumps(m, separators=(",", ":")))):
    assert t.count(key) == 1, key
    t = t.replace(key, val)
out = sys.argv[1]
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, "w").write(t)
rp = os.path.join(os.path.dirname(out), "results.json")
if not os.path.exists(rp):
    json.dump({"updated": None, "races": {}}, open(rp, "w"))
print("built", out, len(t))
