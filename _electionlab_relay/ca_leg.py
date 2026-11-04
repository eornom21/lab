#!/usr/bin/env python3
"""All California legislative races from the Secretary of State's feed: the 20 Senate seats up (even districts) and all 80 Assembly seats.
Writes {at, reporting_time, senate: [...], assembly: [...]}; each race {d, rep (precinct string), pct, cands: [{n, p, v, inc}]} sorted by votes.
Usage: python3 -I ca_leg.py <out.json>"""
import json, sys, re, urllib.request, datetime
from concurrent.futures import ThreadPoolExecutor
API = "https://api.sos.ca.gov/returns/"
num = lambda s: int(re.sub(r"[^0-9]", "", str(s or "0")) or 0)
def get(path):
    for i in range(3):
        try:
            with urllib.request.urlopen(API + path, timeout=25) as r: x = json.load(r)
            return x[0] if isinstance(x, list) else x
        except Exception: pass
    return None
def race(kind, d):
    j = get(f"{kind}/district/{d}")
    if not j: return {"d": d, "rep": None, "pct": None, "cands": [], "missing": True}
    m = re.match(r"\s*([\d.]+)%", j.get("Reporting") or "")
    cs = sorted([{"n": c.get("Name"), "p": c.get("Party"), "v": num(c.get("Votes")), "inc": bool(c.get("incumbent"))} for c in j.get("candidates") or []], key=lambda c: -c["v"])
    return {"d": d, "rep": j.get("Reporting"), "pct": round(float(m.group(1))) if m else None, "cands": cs, "rt": j.get("ReportingTime")}
jobs = [("state-senate", d) for d in range(2, 41, 2)] + [("state-assembly", d) for d in range(1, 81)]
with ThreadPoolExecutor(max_workers=12) as ex: res = list(ex.map(lambda kd: (kd[0], race(*kd)), jobs))
out = {"at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "senate": [r for k, r in res if k == "state-senate"], "assembly": [r for k, r in res if k == "state-assembly"]}
rts = [r.get("rt") for k, r in res if r.get("rt")]; out["reporting_time"] = max(rts) if rts else None
json.dump(out, open(sys.argv[1], "w"), separators=(",", ":"))
print("senate", sum(1 for r in out["senate"] if r["cands"]), "/20; assembly", sum(1 for r in out["assembly"] if r["cands"]), "/80; missing", [ (k, r["d"]) for k, r in res if r.get("missing")][:10], "| reporting", out["reporting_time"])
