#!/usr/bin/env python3
"""Twice-daily California update for the public election pages (run by .github/workflows/rdd.yml from the repo root).
Pulls the Secretary of State feed (ca_relay.py: governor, props, tracked races; ca_leg.py: every legislative race),
keeps the last good number where the feed returns a partial response (ca_merge.py), writes the "ca" and "caleg" keys of
electionlab/snap.json (everything else in the snapshot is left as it was), and rewrites electionnight/results.json from
the loop's house_live.json. Moved here from the Election Night Lab thread's scratchpad on Nov 4, 2026.
Note: the projector dashboard artifact's California views read its own database and are not updated by this script."""
import json, os, subprocess, sys, datetime, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
snap_p = os.path.join(ROOT, "electionlab", "snap.json")
snap = json.load(open(snap_p))
tmp = tempfile.mkdtemp()
ca_new, ca_old, leg_new = os.path.join(tmp, "ca.json"), os.path.join(tmp, "ca_old.json"), os.path.join(tmp, "caleg.json")
json.dump(snap.get("ca") or {}, open(ca_old, "w"))
r = subprocess.run([sys.executable, os.path.join(HERE, "ca_relay.py"), os.path.join(HERE, "ca_bundle.json"), ca_new], capture_output=True, text=True, timeout=180)
print(r.stdout[-400:], r.stderr[-400:])
changed = False
if os.path.exists(ca_new):
    subprocess.run([sys.executable, os.path.join(HERE, "ca_merge.py"), ca_new, ca_old], timeout=30)
    ca = json.load(open(ca_new))
    if (ca.get("races") or ca.get("props")) and ca != snap.get("ca"): snap["ca"] = ca; changed = True
r = subprocess.run([sys.executable, os.path.join(HERE, "ca_leg.py"), leg_new], capture_output=True, text=True, timeout=240)
if os.path.exists(leg_new):
    leg = json.load(open(leg_new))
    # keep the previous district row when the feed returns no votes for it this time
    old = {(k, x.get("d")): x for k in ("senate", "assembly") for x in ((snap.get("caleg") or {}).get(k) or [])}
    for k in ("senate", "assembly"):
        leg[k] = [x if sum(c.get("v") or 0 for c in x.get("cands") or []) > 0 else old.get((k, x.get("d")), x) for x in leg.get(k) or []]
    if (leg.get("senate") or leg.get("assembly")) and leg != snap.get("caleg"): snap["caleg"] = leg; changed = True
if changed:
    snap["copied"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    json.dump(snap, open(snap_p, "w"), separators=(",", ":"))
print("snap.json", "CHANGED" if changed else "SAME")
# phone page results from the loop's House file
h = json.load(open(os.path.join(ROOT, "electionlab", "house_live.json")))
out = {}
for k, v in (h.get("races") or {}).items():
    tot = (v.get("d") or 0) + (v.get("r") or 0)
    if not tot and not v.get("called"): continue
    x = {"called": v.get("called") if v.get("called") in ("D", "R") else None, "pct_in": v.get("pct")}
    if tot: x["d_pct"] = round(v["d"] / tot * 100, 1); x["r_pct"] = round(v["r"] / tot * 100, 1)
    out[k] = x
json.dump({"races": out, "at": h.get("at")}, open(os.path.join(ROOT, "electionnight", "results.json"), "w"), separators=(",", ":"))
print("results.json", len(out), "races")
