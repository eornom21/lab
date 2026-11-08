"""Build ca13_money.json for lab.nathanwmonroe.com/moneyca13.

Inputs (same folder unless noted):
  itcont_ca13.txt   FEC indiv26 rows (pipe-delimited, no header) filtered to the two committees
  dl/indiv_header_file.csv (optional; the column order below is FEC's)
  zip_geo.csv       every ZIP: city, state, county, lat, lon, in_cd13 (point in the Prop 50 CD-13 polygon)
  committees.json   {"gray": {"label":..., "cmte": "C00..."}, "lincoln": {...}}
Rules (the paper's, stated on the page): itemized individual contributions, transaction types 15 and 15E,
entity type IND, no memo rows (MEMO_CD = X), amount > 0. Donor state from the filing's STATE; the
in-district / rest-of-California split from the ZIP's centroid in the AB604 (Prop 50) CD-13 polygon.
"""
import csv, json, os, sys, collections, datetime
D = os.path.dirname(os.path.abspath(__file__))
COLS = ["CMTE_ID","AMNDT_IND","RPT_TP","TRANSACTION_PGI","IMAGE_NUM","TRANSACTION_TP","ENTITY_TP","NAME","CITY","STATE","ZIP_CODE","EMPLOYER","OCCUPATION","TRANSACTION_DT","TRANSACTION_AMT","OTHER_ID","TRAN_ID","FILE_NUM","MEMO_CD","MEMO_TEXT","SUB_ID"]
zg = {}
with open(os.path.join(D, "zip_geo.csv")) as f:
    for r in csv.DictReader(f): zg[r["zip"]] = r
cm = json.load(open(os.path.join(D, "committees.json")))
by_cmte = {v["cmte"]: k for k, v in cm.items()}
out = {k: dict(label=v["label"], committee=v["cmte"], total=0.0, n=0, in_district=0.0, rest_of_ca=0.0, out_of_state=0.0, unmatched=0.0,
               by_county_ca=collections.Counter(), by_zip=collections.defaultdict(lambda: [0.0, 0]), by_state=collections.Counter(),
               by_month=collections.defaultdict(lambda: [0.0, 0.0]), by_size=collections.Counter()) for k, v in cm.items()}
latest = None; dropped = collections.Counter()
with open(os.path.join(D, "itcont_ca13.txt"), encoding="latin1") as f:
    for line in f:
        r = dict(zip(COLS, line.rstrip("\n").split("|")))
        k = by_cmte.get(r["CMTE_ID"])
        if not k: dropped["other_cmte"] += 1; continue
        if r["TRANSACTION_TP"] not in ("15", "15E"): dropped["tp_" + r["TRANSACTION_TP"]] += 1; continue
        if r["ENTITY_TP"] not in ("IND", ""): dropped["entity_" + r["ENTITY_TP"]] += 1; continue
        if r["MEMO_CD"] == "X": dropped["memo"] += 1; continue
        try: amt = float(r["TRANSACTION_AMT"])
        except ValueError: dropped["amt"] += 1; continue
        if amt <= 0: dropped["nonpos"] += 1; continue
        o = out[k]; o["total"] += amt; o["n"] += 1
        dt = r["TRANSACTION_DT"]; m = f"{dt[4:8]}-{dt[0:2]}" if len(dt) == 8 else "unknown"
        if len(dt) == 8:
            d = datetime.date(int(dt[4:8]), int(dt[0:2]), int(dt[2:4])); latest = max(latest, d) if latest else d
        st = r["STATE"].strip().upper(); z5 = r["ZIP_CODE"].strip()[:5]
        g = zg.get(z5)
        if st and st != "CA": o["out_of_state"] += amt; o["by_state"][st] += amt; o["by_month"][m][1] += amt
        elif g and g["state"] == "CA":
            o["by_state"]["CA"] += amt
            if g["in_cd13"] == "True": o["in_district"] += amt; o["by_month"][m][0] += amt
            else: o["rest_of_ca"] += amt; o["by_county_ca"][g["county"]] += amt; o["by_month"][m][1] += amt
            o["by_zip"][z5][0] += amt; o["by_zip"][z5][1] += 1
        else: o["unmatched"] += amt; o["by_month"][m][1] += amt
        o["by_size"]["200-" if amt <= 200 else "201-999" if amt < 1000 else "1000+"] += amt
res = {"asof": latest.isoformat() if latest else "", "built": datetime.date.today().isoformat(), "dropped": dict(dropped), "rules": __doc__.split("Rules")[1].strip()}
for k, o in out.items():
    zips = sorted(({"zip": z, "place": zg[z]["city"], "county": zg[z]["county"], "in_district": zg[z]["in_cd13"] == "True", "amt": round(v[0]), "n": v[1]} for z, v in o["by_zip"].items()), key=lambda x: -x["amt"])
    res[k] = {"label": o["label"], "committee": o["committee"], "total": round(o["total"]), "n": o["n"], "in_district": round(o["in_district"]), "rest_of_ca": round(o["rest_of_ca"]),
              "out_of_state": round(o["out_of_state"]), "unmatched": round(o["unmatched"]),
              "by_county_ca": {c: round(v) for c, v in o["by_county_ca"].most_common()},
              "by_zip": zips[:60], "n_zips_ca": len(zips),
              "by_state": {s: round(v) for s, v in o["by_state"].most_common()},
              "by_month": [{"m": m, "in": round(v[0]), "out": round(v[1])} for m, v in sorted(o["by_month"].items())],
              "by_size": {s: round(v) for s, v in o["by_size"].items()}}
json.dump(res, open(os.path.join(D, "ca13_money.json"), "w"), indent=0)
for k in cm: print(k, {x: res[k][x] for x in ("total", "n", "in_district", "rest_of_ca", "out_of_state", "unmatched")})
print("asof", res["asof"], "dropped", res["dropped"])
