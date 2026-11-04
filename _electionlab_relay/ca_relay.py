"""California relay for the Election Night Lab dashboard (runs in the cloud workspace; api.sos.ca.gov is reachable here).

Reads the Secretary of State's feed for the CAPE alum races, the Valley legislative races, governor and every proposition,
and writes ca_live.json shaped for the dashboard's live/ca doc:
  {"races": {"SD4": {"a": votes, "b": votes, "pct": 12, "called": null}, "GOV": {...}},
   "props": {"1": {"yes": n, "no": n, "pct": 12}}, "meta": {"updated": iso, "source": "...", "reporting_time": "..."}}
"a"/"b" follow the dashboard's candidate order in ca_bundle.json (matched by last name).
Before 7:55pm PT Nov 3 the state posts test numbers, so the script refuses to run unless --test is given.
Usage: python3 -I ca_relay.py <ca_bundle.json> <out.json> [--test]
"""
import json, sys, urllib.request, re, datetime

BUNDLE, OUT = sys.argv[1], sys.argv[2]
TEST = "--test" in sys.argv
OPEN = datetime.datetime(2026, 11, 4, 3, 55, tzinfo=datetime.timezone.utc)  # 7:55pm PT Nov 3
now = datetime.datetime.now(datetime.timezone.utc)
if now < OPEN and not TEST:
    sys.exit("Before 7:55pm PT Nov 3 the state's feed shows test numbers; not writing. Use --test to try the pipeline.")

B = json.load(open(BUNDLE))
API = "https://api.sos.ca.gov/returns/"
def get(path):
    with urllib.request.urlopen(API + path, timeout=30) as r:
        x = json.load(r)
    return x[0] if isinstance(x, list) else x
num = lambda s: int(re.sub(r"[^0-9]", "", str(s or "0")) or 0)
def pct_in(rep):
    m = re.match(r"\s*([\d.]+)%", rep or "")
    return round(float(m.group(1))) if m else None
last = lambda s: s.split()[-1].lower().replace("ó", "o").replace("á", "a").replace("í", "i").replace("é", "e")

out = {"races": {}, "props": {}, "meta": {}}
races = {r["id"]: r for r in B["leg"] + B["cape"]}
if B.get("gov"): races["GOV"] = dict(B["gov"], id="GOV")
if B.get("boe"): races["BOE1"] = dict(B["boe"], id="BOE1")
times = []
for rid, r in races.items():
    if not r.get("b"): continue  # one candidate on the ballot
    path = "governor" if rid == "GOV" else "board-of-equalization/district/1" if rid == "BOE1" else ("state-senate" if rid.startswith("SD") else "state-assembly") + "/district/" + rid[2:]
    try: x = get(path)
    except Exception as e: print("skip", rid, e); continue
    votes = {last(c["Name"]): num(c["Votes"]) for c in x.get("candidates", [])}
    a, b = votes.get(last(r["a"]["name"])), votes.get(last(r["b"]["name"]))
    if a is None or b is None: print("name mismatch", rid, list(votes)); continue
    out["races"][rid] = {"a": a, "b": b, "pct": pct_in(x.get("Reporting")), "called": None}
    times.append(x.get("ReportingTime"))
try:
    m = get("ballot-measures")
    pr = pct_in(m.get("Reporting"))
    for p in m.get("ballot-measures", []):
        out["props"][str(int(p["Number"]))] = {"yes": num(p["yesVotes"]), "no": num(p["noVotes"]), "pct": pr}
    times.append(m.get("ReportingTime"))
except Exception as e:
    print("props skipped", e)
out["meta"] = {"updated": now.isoformat(), "source": "California Secretary of State" + (" (TEST)" if TEST else ""), "reporting_time": next((t for t in times if t), None)}
json.dump(out, open(OUT, "w"), separators=(",", ":"))
print("races", len(out["races"]), "props", len(out["props"]), "reporting", out["meta"]["reporting_time"])
