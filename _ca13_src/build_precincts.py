"""Precinct layer for /ca13: 2022 and 2024 results carried onto the Prop 50 (AB 604) CD-13 lines.

Unit: 2024 SRPREC precincts (Statewide Database), cut to the census blocks inside new CD-13.
- 2024 numbers: precinct totals x share of the precinct's registration in in-district blocks.
- 2022 numbers: 2022 precinct results spread to blocks by registration (SWDB sr_blk_map),
  then gathered into 2024 precincts by each block's share (pctblk), in-district blocks only.
Usage: python3 _ca13_src/build_precincts.py <swdb download dir> ca13/precincts.json _ca13_src/precinct_checks.txt
Inputs (statewidedatabase.org): raw/c{019,039,047,077,099}_g{22,24}_sov_data_by_g{22,24}_srprec.csv, raw/c*_g*_sr_blk_map.csv,
raw/srprec_*_g24_v01.geojson, ab604/AB604.csv (pub/data/d25/AB604.zip, Prop 50 block assignment).
"""
import csv, json, sys, os
from collections import defaultdict
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

SW, OUT, CHK = sys.argv[1], sys.argv[2], sys.argv[3]
R = os.path.join(SW, "raw")
COUNTIES = {"019": "Fresno", "039": "Madera", "047": "Merced", "077": "San Joaquin", "099": "Stanislaus"}
log = []
def say(*a):
    s = " ".join(str(x) for x in a); print(s); log.append(s)

# 1. blocks in new CD-13
inblk = set(); allblk = {}
with open(os.path.join(SW, "ab604", "AB604.csv"), encoding="utf-8-sig") as f:
    for geoid, dist in csv.reader(f):
        if geoid[2:5] in COUNTIES:
            allblk[geoid] = dist
            if dist.strip() == "13": inblk.add(geoid)
say("blocks in the five counties:", len(allblk), "| in new CD-13:", len(inblk))

def geoid(c, tract, block): return "06" + c + tract.zfill(6) + block.zfill(4)

def num(x):
    try: return float(x)
    except: return 0.0

def sov(c, y):
    rows = {}
    with open(os.path.join(R, f"c{c}_g{y}_sov_data_by_g{y}_srprec.csv")) as f:
        for r in csv.DictReader(f):
            k = r["srprec"]
            hd = sum(num(v) for kk, v in r.items() if kk.startswith("CNGDEM"))
            hr = sum(num(v) for kk, v in r.items() if kk.startswith("CNGREP"))
            if y == "24": td, tr = num(r.get("PRSDEM01")), num(r.get("PRSREP01"))
            else: td, tr = num(r.get("GOVDEM01")), num(r.get("GOVREP01"))
            rows[k] = dict(reg=num(r["TOTREG"]), vote=num(r["TOTVOTE"]), hd=hd, hr=hr, td=td, tr=tr, cd=r.get("cddist", ""))
    return rows

def blkmap(c, y):
    out = []
    with open(os.path.join(R, f"c{c}_g{y}_sr_blk_map.csv")) as f:
        for r in csv.DictReader(f):
            out.append((r["srprec"], geoid(c, r["tract"], r["block"]), num(r["pctsrprec"]) / 100, num(r["pctblk"]) / 100))
    return out

FIELDS = ["reg", "vote", "hd", "hr", "td", "tr"]
prec = {}  # (county, srprec24) -> dict
oldchk = defaultdict(lambda: [0, 0])
for c, cname in COUNTIES.items():
    s24, s22 = sov(c, "24"), sov(c, "22")
    m24, m22 = blkmap(c, "24"), blkmap(c, "22")
    # sanity: block ids resolve
    miss = sum(1 for _, g, _, _ in m24 if g not in allblk)
    say(f"{cname}: 2024 block-map rows {len(m24)}, ids not in AB604 file {miss}")
    # old-lines check (CD-13 race by county)
    for y, S in (("24", s24), ("22", s22)):
        for k, v in S.items():
            if v["cd"].strip() in ("13", "013"): oldchk[(y, cname)][0] += v["hd"]; oldchk[(y, cname)][1] += v["hr"]
    # 2024 in-district share per srprec
    frac = defaultdict(float)
    for sp, g, ps, pb in m24:
        if g in inblk: frac[sp] += ps
    for sp, fr in frac.items():
        if fr <= 0 or sp not in s24: continue
        v = s24[sp]
        prec[(c, sp)] = {"c": cname, "sp": sp, "frac": min(1.0, fr), "y24": {k: v[k] * min(1.0, fr) for k in FIELDS}, "cd24": v["cd"].strip(), "y22": {k: 0.0 for k in FIELDS}}
    # 2022: srprec22 -> blocks -> srprec24 (in-district blocks only)
    blk22 = defaultdict(lambda: {k: 0.0 for k in FIELDS})
    for sp, g, ps, pb in m22:
        if g in inblk and sp in s22:
            for k in FIELDS: blk22[g][k] += s22[sp][k] * ps
    to24 = defaultdict(list)
    for sp, g, ps, pb in m24:
        if g in inblk: to24[g].append((sp, pb))
    lost = {k: 0.0 for k in FIELDS}
    for g, v in blk22.items():
        tgt = [(sp, pb) for sp, pb in to24.get(g, []) if (c, sp) in prec]
        tot = sum(pb for _, pb in tgt)
        if not tgt or tot <= 0:
            for k in FIELDS: lost[k] += v[k]
            continue
        for sp, pb in tgt:
            for k in FIELDS: prec[(c, sp)]["y22"][k] += v[k] * pb / tot
    say(f"  2022 votes in district blocks with no 2024 precinct to land in: {lost['vote']:.0f}")

# checks
say("\nOld-lines check: CD-13 race summed from precinct files vs. the page's county results (Gray, Duarte)")
D = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ca13_data.json")))
for y in ("24", "22"):
    for cname in COUNTIES.values():
        a = oldchk[(y, cname)]; b = D["results"]["20" + y]["by"][cname]
        say(f"  20{y} {cname}: precincts {a[0]:.0f}/{a[1]:.0f} vs page {b[0]}/{b[1]}")
for y in ("24", "22"):
    t = {k: sum(p["y" + y][k] for p in prec.values()) for k in FIELDS}
    say(f"\nNew CD-13 total, 20{y}: registered {t['reg']:.0f}, voted {t['vote']:.0f}, top of ticket D {t['td']:.0f} R {t['tr']:.0f} (D two-party {t['td']/(t['td']+t['tr']):.3f}), House D {t['hd']:.0f} R {t['hr']:.0f}")
    for cname in COUNTIES.values():
        tc = {k: sum(p["y" + y][k] for p in prec.values() if p["c"] == cname) for k in FIELDS}
        say(f"   {cname}: reg {tc['reg']:.0f}, voted {tc['vote']:.0f}, top D share {tc['td']/max(1,tc['td']+tc['tr']):.3f}")
say("\nPrecincts with any part in new CD-13:", len(prec), "| fully inside:", sum(1 for p in prec.values() if p["frac"] > 0.999))
say("2024 House districts these precincts were in:", dict(sorted(defaultdict(int, {k: sum(1 for p in prec.values() if p['cd24'] == k) for k in set(p['cd24'] for p in prec.values())}).items())))

# geometry: simplify, round, delta-encode
feats = []
for c in COUNTIES:
    g = json.load(open(os.path.join(R, f"srprec_{c}_g24_v01.geojson")))
    for f in g["features"]:
        key = (c, f["properties"]["srprec"])
        if key not in prec: continue
        geom = shape(f["geometry"]).buffer(0).simplify(0.0012, preserve_topology=True)
        polys = [geom] if geom.geom_type == "Polygon" else list(getattr(geom, "geoms", []))
        rings = []
        for p in polys:
            if p.area < 2e-7: continue
            co = [(round(x, 4), round(y, 4)) for x, y in p.exterior.coords]
            enc = [[int(round(co[0][0] * 1e4)), int(round(co[0][1] * 1e4))]]
            for i in range(1, len(co)):
                enc.append([int(round((co[i][0] - co[i - 1][0]) * 1e4)), int(round((co[i][1] - co[i - 1][1]) * 1e4))])
            rings.append(enc)
        if not rings:
            p = max(polys, key=lambda q: q.area) if polys else None
            if p is None: continue
            co = [(round(x, 4), round(y, 4)) for x, y in p.exterior.coords]
            enc = [[int(round(co[0][0] * 1e4)), int(round(co[0][1] * 1e4))]] + [[int(round((co[i][0] - co[i-1][0]) * 1e4)), int(round((co[i][1] - co[i-1][1]) * 1e4))] for i in range(1, len(co))]
            rings.append(enc)
        p = prec[key]
        r = lambda v: int(round(v))
        feats.append({"id": p["sp"], "c": p["c"], "f": round(p["frac"], 3), "cd": p["cd24"], "r": rings,
                      "a": [r(p["y24"][k]) for k in FIELDS], "b": [r(p["y22"][k]) for k in FIELDS]})
say("features written:", len(feats), "| points:", sum(len(x) for f in feats for x in f["r"]))
json.dump({"fields": FIELDS, "built": "2026-10-31", "p": feats}, open(OUT, "w"), separators=(",", ":"))
say("bytes:", os.path.getsize(OUT))
open(CHK, "w").write("\n".join(log) + "\n")
