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

    # every race any group needs, every race with a detail page (for the weather page's county rows), and every statewide race, fetched once
    need = {}
    for g in GROUPS["groups"]:
        for k, *_ in g["races"]:
            if k in idx:
                need[k] = idx[k]["raceId"]
    for k, r in DATA["races"].items():
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
            tl = (h.get("raceData") or {}).get("toplineResults") or []
            same_party = [c for c in tl if (c.get("party") or {}).get("abbrev") == pcode]
            who = pcode if (cparty == party and len(same_party) == 1) else cand.split(" ")[-1].lower()
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
            same = me["oppParty"] == ("D" if cparty == "D" else "R" if cparty == "R" else "I")
            if same:  # Democrat vs. Democrat (CA-4): ticket, presidential, registration and forecast comparisons are meaningless
                ticket = ticket_who = pres = pres_base = reg = cape = exp_margin = None
                lead_abbrev = None
            rows.append(dict(base,
                opp=me["oppName"], opp_party=me["oppParty"], tot=tot, exp=exp,
                inPct=(min(1.0, tot / exp) if exp else None), share=share, margin=margin,
                ticket=ticket, ticketWho=ticket_who, harris=pres, presBase=pres_base, reg=reg,
                cape=cape, expMargin=exp_margin, expWin=(lead_abbrev == pcode) if lead_abbrev else None,
                rating=fc.get("ratingWithParty"), winProb=fc.get("winProbability"),
                sameParty=same, called=me["winner"], lastUpdated=rd.get("lastUpdated")))
        out_groups[g["id"]] = rows

    # national tide so far: Democratic two-way share vs. 2024 presidential, vote-weighted over all House races with county votes
    # (uses only the races already fetched plus the index totals; county detail for all 436 races is the RDD job's business)
    tide = None
    try:
        pairs = []
        for key, h in got.items():
            if key[0] != "house" or not h:
                continue
            tl = (h.get("raceData") or {}).get("toplineResults") or []
            parties = {(c.get("party") or {}).get("abbrev") for c in tl}
            if not ({"DEM", "GOP"} <= parties):
                continue  # uncontested or same-party race: no two-party swing to measure
            s = two_way(h, "DEM")
            if s and s["oppParty"] == "R":
                pairs += [(s["by"][f], pres_share(f, "D"), s["cnt"][f]) for f in s["by"]]
        tide = {"value": wavg(pairs), "counties": sum(1 for p in pairs if p[1] is not None), "basis": "caucus-list races only"}
    except Exception as e:  # noqa: BLE001
        print("tide failed", e, file=sys.stderr)

    # county rows for the weather page (the 53 tracked races): expected vote, live estimate, counted, done, 2024 lean
    try:
        wrows = []
        for k, r in DATA["races"].items():
            h = got.get(("house", k))
            if not h:
                continue
            base = {c["fips"]: c for c in r.get("counties") or []}
            for v in h.get("vcuData") or []:
                vcu = v.get("vcu") or {}
                f = vcu.get("countyFips") or vcu.get("fips")
                g = v.get("voteGoal") or {}
                t = v.get("liveTurnoutEstimate") or {}
                m24 = (base.get(f) or {}).get("m24")
                if m24 is None and LEAN.get(f):
                    m24 = LEAN[f][2]
                wrows.append({"fips": f, "name": vcu.get("county") or vcu.get("name"), "st": r["st"], "race": k, "pre": g.get("preElectionMid"), "live": t.get("estimatedVotesMid"),
                              "counted": t.get("totalVotes") or 0, "done": bool(t.get("completedCounty")), "m24": m24})
        json.dump({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "rows": wrows}, open(os.path.join(HERE, "..", "weather", "counties.json"), "w"), separators=(",", ":"))
    except Exception as e:  # noqa: BLE001
        print("weather counties failed", e, file=sys.stderr)

    # the dashboard relay's output, computed here so the lab thread can copy it into the dashboard database without a browser:
    # races (the 32 board races by dashboard id), house (every district), bluedogs (the Blue Dog list by last name)
    try:
        board_ids = json.load(open(os.path.join(HERE, "..", "..", "_electionnight_src", "races.json")))
        board_ids = [r["id"] for r in board_ids]
    except Exception:
        board_ids = []
    try:
        bd_names = {g_r[0]: g_r[1].split(" ")[-1].lower() for g in GROUPS["groups"] if g["id"] == "bluedogs" for g_r in g["races"]}
        rl = {"races": {}, "house": {}, "bluedogs": {}, "n": 0, "withVotes": 0, "called": 0, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        for k, r in idx.items():
            did = k.replace("-", "")
            cs = (r.get("results") or {}).get("candidates") or []
            d = rr = 0; called = None
            for c in cs:
                pa = (c.get("party") or {}).get("abbrev")
                if pa == "DEM": d += c.get("votes") or 0
                if pa == "GOP": rr += c.get("votes") or 0
                if c.get("winner"): called = "D" if pa == "DEM" else "R" if pa == "GOP" else (pa or "O")
            pct = int(round((r.get("results") or {}).get("percentIn") or 0))
            rl["n"] += 1
            if d + rr > 0: rl["withVotes"] += 1
            if called: rl["called"] += 1
            if d + rr > 0: rl["house"][k] = [d, rr, pct]
            if k in bd_names:
                ln = bd_names[k]; bdv = opp = 0; st = None
                for c in cs:
                    mine = str(c.get("lastName") or "").lower() == ln
                    if mine:
                        bdv = c.get("votes") or 0
                        if c.get("winner"): st = "W"
                    else:
                        opp = max(opp, c.get("votes") or 0)
                        if c.get("winner"): st = st or "L"
                rl["bluedogs"][k] = [bdv, opp, pct, st]
            fc = r.get("forecast") or {}; la = (fc.get("leadingParty") or {}).get("abbrev"); fm = None
            if fc.get("margin") is not None and la in ("DEM", "GOP"): fm = fc["margin"] if la == "DEM" else -fc["margin"]
            if did in board_ids: rl["races"][did] = {"d": d, "r": rr, "pct": pct, "called": called, "fm": fm}
        json.dump(rl, open(os.path.join(HERE, "..", "house_live.json"), "w"), separators=(",", ":"))
    except Exception as e:  # noqa: BLE001
        print("house_live failed", e, file=sys.stderr)

    # Senate: all 35 races from the /senate index, for the dashboard's Senate view and the mirror
    try:
        sj = fetch(BASE + "/senate") or {}
        srows = []
        for r in sj.get("races") or []:
            cs = (r.get("results") or {}).get("candidates") or []
            cands = sorted([{"n": f"{c.get('firstName', '')} {c.get('lastName', '')}".strip(), "p": {"DEM": "D", "GOP": "R"}.get((c.get("party") or {}).get("abbrev"), "I"), "v": c.get("votes") or 0, "w": bool(c.get("winner")), "inc": bool(c.get("incumbent"))} for c in cs], key=lambda c: -c["v"])
            called = next((c["p"] for c in cands if c["w"]), None)
            fc = r.get("forecast") or {}; la = (fc.get("leadingParty") or {}).get("abbrev"); fm = fc.get("margin")
            if fm is not None and la in ("DEM", "GOP"): fm = fm if la == "DEM" else -fm
            elif fm is not None and (fc.get("ratingWithParty") or "").endswith(" R"): fm = -abs(fm)
            srows.append({"id": r.get("raceId"), "st": r.get("stateAbb") or r.get("state"), "name": r.get("displayName") or r.get("name"), "prev": {"DEM": "D", "GOP": "R"}.get((r.get("previousParty") or {}).get("abbrev"), "I"),
                          "rating": fc.get("ratingWithParty") or fc.get("rating"), "fm": fm, "pct": int(round((r.get("results") or {}).get("percentIn") or 0)), "called": called, "cands": cands[:4], "updated": (r.get("results") or {}).get("lastUpdated")})
        json.dump({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "races": srows}, open(os.path.join(HERE, "..", "senate_live.json"), "w"), separators=(",", ":"))
    except Exception as e:  # noqa: BLE001
        print("senate failed", e, file=sys.stderr)

    out = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "seconds": round(time.time() - t0, 1),
           "fetched": sum(1 for v in got.values() if v), "requested": len(got), "groups": out_groups, "tide": tide}
    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    print(json.dumps({"at": out["at"], "fetched": out["fetched"], "requested": out["requested"], "seconds": out["seconds"],
                      "withVotes": {g: sum(1 for r in rows if not r.get("none") and (r.get("tot") or 0) > 0) for g, rows in out_groups.items()}}))


if __name__ == "__main__":
    main()
