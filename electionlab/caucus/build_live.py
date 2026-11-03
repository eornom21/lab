#!/usr/bin/env python3
"""Build electionlab/caucus/live.json for the caucus scoreboards.

Runs on GitHub Actions every few minutes (see .github/workflows/rdd.yml) so the
Decision Desk HQ feed is read once per cycle here instead of once per viewer:
the public page then only reads this small file.  The page keeps a fallback
that reads the feed directly if this file is missing or stale.

For every race in every group in groups.json:
  share, margin   the group's candidate's two-way share (vs. their main opponent)
  tot, exp, inPct votes counted, expected total (DDHQ turnout estimate), fraction counted
  ticket          candidate's two-way share minus the same-party Senate (else governor)
                  candidate's two-way share in the same counties, weighted by this
                  race's county votes, in points
  pres            same, minus the party's 2024 presidential two-way share in those counties
  presBase        the party's 2024 presidential two-way share in the counties with votes
  reg             share minus the party's share of two-party registration (DDHQ figures)
  cape            two-way margin minus Decision Desk HQ's pre-election forecast margin,
                  signed from the candidate's party's side (the "CAPE score")
  expWin          whether the forecast had the candidate's party ahead
  called          "W" / "L" / null
Also `tide`: the national swing so far, vote-weighted across every House race
with county votes: Democratic two-way share minus the 2024 presidential
Democratic two-way share in the same counties, in points.
"""
import json, os, sys, time, urllib.request, concurrent.futures as cf
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "live.json")
DATA = json.load(open(os.path.join(HERE, "..", "race", "data.json")))
GROUPS = json.load(open(os.path.join(HERE, "groups.json")))
BASE = DATA["ddhq_base"]
LEAN = DATA["county_lean"]          # fips -> [name, state, m24] where m24 = Republican minus Democratic 2024 margin, points
SW = GROUPS["statewide"]


def fetch(url, timeout=40, tries=3):
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "cape-election-lab/1.0"}), timeout=timeout) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    print(f"fetch failed {url}: {last}", file=sys.stderr)
    return None


def norm(name):
    """DDHQ displayName 'AL-01' / 'AK-AL' -> 'AL-1' / 'AK-AL' (the key groups.json uses)."""
    st, d = name.split("-")
    return st + "-" + (d if d == "AL" else str(int(d)))


def two_way(race, who):
    """Two-way results for one side of a race: who = 'DEM'/'GOP' (party) or a lower-case last name."""
    tl = (race.get("raceData") or {}).get("toplineResults") or []
    if who in ("DEM", "GOP"):
        me = next((c for c in tl if (c.get("party") or {}).get("abbrev") == who), None)
    else:
        me = next((c for c in tl if who in str(c.get("lastName") or "").lower()), None)
    if not me:
        return None
    others = [c for c in tl if c is not me]
    major = [c for c in others if (c.get("party") or {}).get("abbrev") in ("DEM", "GOP")]
    pool = major or others
    if not pool:
        return None
    opp = max(pool, key=lambda c: c.get("votes") or 0)
    by, cnt = {}, {}
    for v in race.get("vcuData") or []:
        vcu = v.get("vcu") or {}
        f = vcu.get("countyFips") or vcu.get("fips")
        cr = {c.get("id"): c for c in v.get("candidateResults") or []}
        a = (cr.get(me.get("candId")) or {}).get("votes") or 0
        b = (cr.get(opp.get("candId")) or {}).get("votes") or 0
        if f and a + b:
            by[f] = a / (a + b)
            cnt[f] = a + b
    return {
        "name": f"{me.get('firstName', '')} {me.get('lastName', '')}".strip(),
        "oppName": f"{opp.get('firstName', '')} {opp.get('lastName', '')}".strip(),
        "oppParty": {"DEM": "D", "GOP": "R"}.get((opp.get("party") or {}).get("abbrev"), "I"),
        "by": by, "cnt": cnt,
        "votes": me.get("votes") or 0, "oppVotes": opp.get("votes") or 0,
        "winner": "W" if me.get("winner") else ("L" if opp.get("winner") else None),
    }


def wavg(pairs):
    """Vote-weighted mean of (a - b) over counties, in points; None if nothing to compare."""
    w = s = 0.0
    for a, b, wt in pairs:
        if a is None or b is None or not wt:
            continue
        w += wt
        s += (a - b) * wt
    return s / w * 100 if w else None


def pres_share(fips, party):
    l = LEAN.get(fips)
    if not l:
        return None
    return 0.5 - l[2] / 200 if party == "D" else 0.5 + l[2] / 200


def main():
    t0 = time.time()
    idx_raw = fetch(BASE + "/house") or {}
    idx = {}
    for r in idx_raw.get("races") or []:
        try:
            idx[norm(r["displayName"])] = r
        except Exception:  # noqa: BLE001
            pass
    if not idx:
        print("no house index; keeping the old live.json", file=sys.stderr)
        sys.exit(1)

    # every race any group needs, and every statewide race, fetched once
    need = {}
    for g in GROUPS["groups"]:
        for k, *_ in g["races"]:
            if k in idx:
                need[k] = idx[k]["raceId"]
    sw_keys = set()
    for k in need:
        st = k[:2]
        for sid in SW["senate"].get(st, []):
            sw_keys.add(("senate", sid))
        if SW["gov"].get(st):
            sw_keys.add(("gov", SW["gov"][st]))
    urls = {("house", k): f"{BASE}/house/{rid}" for k, rid in need.items()}
    urls.update({key: f"{BASE}/{key[0]}/{key[1]}" for key in sw_keys})
    got = {}
    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        for key, res in zip(urls, ex.map(lambda u: fetch(u), urls.values())):
            got[key] = res

    out_groups = {}
    for g in GROUPS["groups"]:
        party = g["party"]
        pcode = "DEM" if party == "D" else "GOP"
        rows = []
        for k, cand, cparty, held, inc, note in g["races"]:
            base = {"id": k, "cand": cand, "party": cparty, "held": held, "inc": bool(inc), "note": note}
            h = got.get(("house", k))
            ir = idx.get(k)
            if not h or not ir:
                rows.append(dict(base, none=True))
                continue
            who = pcode if cparty == party else cand.split(" ")[-1].lower()
            me = two_way(h, who)
            if not me:
                rows.append(dict(base, none=True))
                continue
            rd = h.get("raceData") or {}
            tu = rd.get("turnout") or {}
            tot = sum((c.get("votes") or 0) for c in rd.get("toplineResults") or [])
            exp = tu.get("estimated_votes_mid") or None
            two = me["votes"] + me["oppVotes"]
            share = me["votes"] / two if two else None
            margin = (share - 0.5) * 200 if share is not None else None
            # ahead of the ticket: Senate first, then governor, same party, same counties
            ticket = ticket_who = None
            st = k[:2]
            cands = [("senate", sid) for sid in SW["senate"].get(st, [])]
            if SW["gov"].get(st):
                cands.append(("gov", SW["gov"][st]))
            for key in cands:
                s = got.get(key) and two_way(got[key], pcode)
                if not s:
                    continue
                d = wavg([(me["by"][f], s["by"].get(f), me["cnt"][f]) for f in me["by"]])
                if d is not None:
                    ticket, ticket_who = d, s["name"] + (" (Senate)" if key[0] == "senate" else " (governor)")
                    break
            pres = wavg([(me["by"][f], pres_share(f, party), me["cnt"][f]) for f in me["by"]])
            wb = sum(me["cnt"][f] for f in me["by"] if pres_share(f, party) is not None)
            pres_base = (sum(pres_share(f, party) * me["cnt"][f] for f in me["by"] if pres_share(f, party) is not None) / wb) if wb else None
            reg_d = reg_r = 0
            for v in h.get("vcuData") or []:
                vg = v.get("voteGoal") or {}
                reg_d += vg.get("democraticRegistration") or 0
                reg_r += vg.get("republicanRegistration") or 0
            own = reg_d if party == "D" else reg_r
            reg = (share - own / (reg_d + reg_r)) * 100 if share is not None and reg_d + reg_r else None
            fc = ir.get("forecast") or {}
            lead_abbrev = (fc.get("leadingParty") or {}).get("abbrev")
            fmargin = fc.get("margin")
            exp_margin = None
            if fmargin is not None and lead_abbrev in ("DEM", "GOP"):
                exp_margin = fmargin if lead_abbrev == pcode else -fmargin
            cape = (margin - exp_margin) if (margin is not None and exp_margin is not None) else None
            if cparty != party:  # an independent on a party's list: no party forecast to score against
                cape = exp_margin = None
                lead_abbrev = None
            rows.append(dict(base,
                opp=me["oppName"], opp_party=me["oppParty"], tot=tot, exp=exp,
                inPct=(min(1.0, tot / exp) if exp else None), share=share, margin=margin,
                ticket=ticket, ticketWho=ticket_who, harris=pres, presBase=pres_base, reg=reg,
                cape=cape, expMargin=exp_margin, expWin=(lead_abbrev == pcode) if lead_abbrev else None,
                rating=fc.get("ratingWithParty"), winProb=fc.get("winProbability"),
                called=me["winner"], lastUpdated=rd.get("lastUpdated")))
        out_groups[g["id"]] = rows

    # national tide so far: Democratic two-way share vs. 2024 presidential, vote-weighted over all House races with county votes
    # (uses only the races already fetched plus the index totals; county detail for all 436 races is the RDD job's business)
    tide = None
    try:
        pairs = []
        for key, h in got.items():
            if key[0] != "house" or not h:
                continue
            s = two_way(h, "DEM")
            if s:
                pairs += [(s["by"][f], pres_share(f, "D"), s["cnt"][f]) for f in s["by"]]
        tide = {"value": wavg(pairs), "counties": sum(1 for p in pairs if p[1] is not None), "basis": "caucus-list races only"}
    except Exception as e:  # noqa: BLE001
        print("tide failed", e, file=sys.stderr)

    out = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "seconds": round(time.time() - t0, 1),
           "fetched": sum(1 for v in got.values() if v), "requested": len(got), "groups": out_groups, "tide": tide}
    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    print(json.dumps({"at": out["at"], "fetched": out["fetched"], "requested": out["requested"], "seconds": out["seconds"],
                      "withVotes": {g: sum(1 for r in rows if not r.get("none") and (r.get("tot") or 0) > 0) for g, rows in out_groups.items()}}))


if __name__ == "__main__":
    main()
