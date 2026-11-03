"""Hypothesis testing in real time: weather, voting rules and turnout at state lines, election night 2026.

Runs on a loop (GitHub Actions, every ~10 minutes). Each run:
  1. pulls every county's turnout from Decision Desk HQ's public results feed (all 435 House races):
     the pre-election expected vote, the live expected vote (revised as the count comes in), votes counted, and D/R votes;
  2. pulls today's precipitation at each county's center from Open-Meteo (cached for an hour);
  3. estimates three things from the literature and writes tables + figures to electionlab/rdd/ for the weather page:
     H1  Rain lowers Election-Day turnout (Gomez, Hansford & Krause 2007).
     H2  Convenience voting (no-excuse mail, early voting) blunts the rain effect: a geographic RDD at state lines where the
         rules change, comparing counties that got the same rain on both sides of the line.
     H3  Rain helps Republicans (the partisan half of Gomez et al. 2007), and less so where mail/early voting is easy.
Outcome for H1/H2: the turnout surprise = (live expected vote / pre-election expected vote - 1) x 100, in points.
Outcome for H3: the county's Democratic two-way share in the House race tonight minus Harris's 2024 two-way share, in points.
Usage: python3 rdd.py [--sample] [--out DIR]
"""
import json, sys, os, math, time, datetime, urllib.request, urllib.parse, concurrent.futures, random
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = HERE
SAMPLE = "--sample" in sys.argv
if "--out" in sys.argv: OUT = sys.argv[sys.argv.index("--out") + 1]
DDHQ = "https://race-api-proxy-production.decisiondeskhq.workers.dev"
UA = {"User-Agent": "election-night-lab-rdd/1.0 (UC Merced CAPE; research)"}
now = datetime.datetime.now(datetime.timezone.utc)
PT = datetime.timezone(datetime.timedelta(hours=-8))

def fetch(url, timeout=40, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r: return json.load(r)
        except Exception as e:
            if i == tries - 1: raise
            time.sleep(1.5 * (i + 1))

C = json.load(open(os.path.join(HERE, "counties.json")))["counties"]
RULES = json.load(open(os.path.join(HERE, "rules.json")))["states"]
byfips = {c["fips"]: c for c in C}

# ---------- 1. turnout by county ----------
def turnout():
    """fips -> {pre, live, counted, dem, rep, parts, done}; aggregated over every House race that touches the county."""
    agg = {}
    if SAMPLE:
        random.seed(int(time.time()) // 600)
        for c in C:
            pre = random.randint(3000, 400000); rain_fake = 0
            r = RULES.get(c["st"], {"mail": 1, "early_days": 10})
            # synthetic truth: rain hurts turnout, less so where mail is easy; built from the county's position so it is reproducible
            rain = max(0, (math.sin(c["lat"] / 3) + math.cos(c["lon"] / 5)) * 8)
            eff = -0.35 * rain * (1.0 if r["mail"] == 0 else 0.4) + random.gauss(0, 2.5)
            live = pre * (1 + eff / 100); frac = random.random()
            dsh = 0.5 - (c["m24"] or 0) / 200 + (0.0008 * rain * (1.0 if r["mail"] == 0 else 0.3)) * -1 + random.gauss(0, 0.02)
            cnt = int(live * frac); agg[c["fips"]] = {"pre": pre, "live": live, "counted": cnt, "dem": cnt * dsh, "rep": cnt * (1 - dsh), "parts": 1, "done": frac > 0.95}
        return agg, {"races": 435, "fetched": 435}
    idx = fetch(DDHQ + "/house")
    ids = [r["raceId"] for r in idx.get("races", []) if r.get("raceId")]
    got = 0
    def one(rid):
        try: return fetch(DDHQ + "/house/" + str(rid), timeout=30, tries=2)
        except Exception: return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        for x in ex.map(one, ids):
            if not x: continue
            got += 1
            tl = x.get("raceData", {}).get("toplineResults") or []
            party = {c.get("candId"): (c.get("party") or {}).get("abbrev") for c in tl}
            for v in x.get("vcuData") or []:
                f = (v.get("vcu") or {}).get("countyFips") or (v.get("vcu") or {}).get("fips")
                if not f or len(f) != 5: continue
                g = v.get("voteGoal") or {}; t = v.get("liveTurnoutEstimate") or {}
                pre = g.get("preElectionMid") or 0; live = t.get("estimatedVotesMid") or pre; cnt = t.get("totalVotes") or 0
                dem = sum((c.get("votes") or 0) for c in v.get("candidateResults") or [] if party.get(c.get("id")) == "DEM")
                rep = sum((c.get("votes") or 0) for c in v.get("candidateResults") or [] if party.get(c.get("id")) == "GOP")
                a = agg.setdefault(f, {"pre": 0, "live": 0, "counted": 0, "dem": 0, "rep": 0, "parts": 0, "done": True})
                a["pre"] += pre; a["live"] += live; a["counted"] += cnt; a["dem"] += dem; a["rep"] += rep; a["parts"] += 1; a["done"] = a["done"] and bool(t.get("completedCounty"))
    return agg, {"races": len(ids), "fetched": got}

# ---------- 2. precipitation today ----------
def rain():
    cache = os.path.join(OUT, "rain_cache.json")
    try:
        rc = json.load(open(cache))
        if time.time() - rc.get("at", 0) < 3600 and len(rc.get("mm", {})) > 2000: return rc["mm"], rc.get("asof")
    except Exception: pass
    mm = {}
    if SAMPLE:
        for c in C: mm[c["fips"]] = round(max(0, (math.sin(c["lat"] / 3) + math.cos(c["lon"] / 5)) * 8), 1)
        return mm, now.isoformat()
    batch = 150
    for i in range(0, len(C), batch):
        chunk = C[i:i + batch]
        q = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({"latitude": ",".join(str(c["lat"]) for c in chunk), "longitude": ",".join(str(c["lon"]) for c in chunk), "daily": "precipitation_sum", "timezone": "auto", "forecast_days": 1})
        try:
            res = fetch(q, timeout=60)
            res = res if isinstance(res, list) else [res]
            for c, r in zip(chunk, res):
                v = ((r.get("daily") or {}).get("precipitation_sum") or [None])[0]
                mm[c["fips"]] = float(v) if v is not None else None
        except Exception as e:
            print("rain batch failed", i, e, file=sys.stderr)
        time.sleep(0.3)
    json.dump({"at": time.time(), "asof": now.isoformat(), "mm": mm}, open(cache, "w"))
    return mm, now.isoformat()

# ---------- 3. estimation ----------
def ols(y, X, names, cluster=None):
    """OLS with heteroskedasticity-robust (HC1) or cluster-robust standard errors. Returns rows for the named columns."""
    y = np.asarray(y, float); X = np.asarray(X, float); n, k = X.shape
    XtX = X.T @ X
    try: XtXi = np.linalg.pinv(XtX)
    except Exception: return None
    b = XtXi @ X.T @ y; e = y - X @ b
    if cluster is None:
        meat = (X * (e[:, None] ** 2)).T @ X * (n / max(1, n - k))
    else:
        cl = np.asarray(cluster); meat = np.zeros((k, k)); G = len(set(cl.tolist()))
        for g in set(cl.tolist()):
            m = cl == g; s = X[m].T @ e[m]; meat += np.outer(s, s)
        meat *= (G / max(1, G - 1)) * ((n - 1) / max(1, n - k))
    V = XtXi @ meat @ XtXi; se = np.sqrt(np.maximum(np.diag(V), 0))
    rows = []
    for i, nm in enumerate(names):
        if nm is None: continue
        t = b[i] / se[i] if se[i] > 0 else float("nan"); p = 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2)))) if np.isfinite(t) else float("nan")
        rows.append({"term": nm, "est": float(b[i]), "se": float(se[i]), "t": float(t) if np.isfinite(t) else None, "p": float(p) if np.isfinite(p) else None})
    r2 = 1 - float(e @ e) / float(((y - y.mean()) ** 2).sum()) if n > 1 and ((y - y.mean()) ** 2).sum() > 0 else None
    return {"rows": rows, "n": int(n), "r2": r2}

def fe(cols, keys):
    """append fixed-effect dummies (drop one) to a design matrix list of columns"""
    ks = sorted(set(keys)); X = []
    for k in ks[1:]: X.append([1.0 if kk == k else 0.0 for kk in keys])
    return X

def build(agg, mm):
    rows = []
    for c in C:
        a = agg.get(c["fips"]); r = RULES.get(c["st"])
        if not a or not r or not a["pre"]: continue
        rain_mm = mm.get(c["fips"]);
        rows.append({"fips": c["fips"], "st": c["st"], "name": c["name"], "lat": c["lat"], "lon": c["lon"], "m24": c["m24"], "pre": a["pre"], "live": a["live"], "counted": a["counted"],
                     "dem": a["dem"], "rep": a["rep"], "rain": rain_mm, "mail": r["mail"], "early": r["early_days"], "conv": 1 if r["mail"] >= 1 else 0, "borders": c["borders"]})
    return rows

def analyze(rows, meta):
    R = {"run_at": now.isoformat(), "run_at_pt": now.astimezone(PT).strftime("%-I:%M %p PT"), "sample": SAMPLE, "feed": meta, "hypotheses": []}
    have = [r for r in rows if r["counted"] > 0 and r["pre"] > 0 and r["rain"] is not None]
    for r in have: r["short"] = (r["live"] / r["pre"] - 1) * 100; r["rain_cm"] = r["rain"] / 10
    wet = [r for r in have if r["rain"] >= 1]
    R["data"] = {"counties_in_feed": len(rows), "counties_with_votes": len(have), "counties_wet_1mm": len(wet), "rain_asof": meta.get("rain_asof"), "states_with_votes": len(set(r["st"] for r in have))}
    early = len(have) < 150 or len(wet) < 25
    # ----- H1: rain lowers turnout -----
    h1 = {"id": "H1", "title": "Rain lowers Election-Day turnout", "claim": "Each inch of rain cuts turnout by about one percentage point (Gomez, Hansford & Krause 2007, Journal of Politics).",
          "design": "All counties with votes counted. Turnout surprise (live expected vote vs. pre-election expectation, in points) regressed on today's precipitation, with state fixed effects, standard errors clustered by state."}
    if not early and len(set(r["st"] for r in have)) >= 2:
        X = [[1.0] * len(have), [r["rain_cm"] for r in have]] + fe(None, [r["st"] for r in have])
        res = ols([r["short"] for r in have], np.array(X).T, ["const", "rain (per cm)"] + [None] * (len(X) - 2), cluster=[r["st"] for r in have])
        if res:
            b = next(x for x in res["rows"] if x["term"].startswith("rain")); b_in = {"term": "rain (per inch)", "est": b["est"] * 2.54, "se": b["se"] * 2.54, "t": b["t"], "p": b["p"]}
            h1.update({"n": res["n"], "r2": res["r2"], "table": [b, b_in], "verdict": verdict(b, expect="neg"), "reading": f"Across {res['n']} counties with votes, each inch of rain today is associated with a {b['est']*2.54:+.2f}-point change in turnout against expectations ({sig(b)})."})
    else: h1.update({"verdict": "Too early", "reading": f"Needs more counties reporting ({len(have)} with votes, {len(wet)} with at least 1 mm of rain)."})
    R["hypotheses"].append(h1)
    # ----- H2: border RDD, rules blunt the rain effect -----
    h2 = {"id": "H2", "title": "Easy mail and early voting blunt the rain effect", "claim": "Where most votes are cast before Election Day, a rainy Tuesday matters less (the convenience-voting argument: Gronke et al. 2008; Gomez, Hansford & Krause 2007 on absentee states; Thompson, Wu, Yoder & Hall 2020 on vote-by-mail).",
          "design": "Counties within 100 km of a state line where the mail rule changes (no-excuse or all-mail on one side, excuse-required on the other). Turnout surprise regressed on which side of the line the county is on, distance to the line (separately on each side), rain, and side x rain, with a fixed effect for each state pair; standard errors clustered by state pair. The side x rain term is the test: a negative number means rain costs more turnout on the restrictive side of the same storm."}
    bs = []
    for r in have:
        best = None
        for other, km in r["borders"].items():
            ro = RULES.get(other);
            if not ro: continue
            if (1 if ro["mail"] >= 1 else 0) == r["conv"]: continue
            if km <= 100 and (best is None or km < best[1]): best = (other, km)
        if best:
            treat = 1 - r["conv"]  # 1 = restrictive (excuse-required) side
            bs.append(dict(r, pair="-".join(sorted([r["st"], best[0]])), dist=best[1], sd=(best[1] if treat else -best[1]), treat=treat))
    R["data"]["border_sample"] = len(bs); R["data"]["border_pairs"] = len(set(b["pair"] for b in bs))
    if not early and len(bs) >= 60 and len(set(b["treat"] for b in bs)) == 2 and sum(1 for b in bs if b["rain"] >= 1) >= 15:
        X = [[1.0] * len(bs), [b["treat"] for b in bs], [b["sd"] / 10 for b in bs], [b["treat"] * b["sd"] / 10 for b in bs], [b["rain_cm"] for b in bs], [b["treat"] * b["rain_cm"] for b in bs]] + fe(None, [b["pair"] for b in bs])
        names = ["const", "restrictive side (at the line, dry)", "distance (per 10 km)", "restrictive x distance", "rain (per cm)", "restrictive x rain (per cm)"] + [None] * (len(X) - 6)
        res = ols([b["short"] for b in bs], np.array(X).T, names, cluster=[b["pair"] for b in bs])
        if res:
            key = next(x for x in res["rows"] if x["term"].startswith("restrictive x rain"))
            h2.update({"n": res["n"], "r2": res["r2"], "pairs": len(set(b["pair"] for b in bs)), "table": [x for x in res["rows"] if x["term"] != "const"], "verdict": verdict(key, expect="neg"),
                       "reading": f"In {res['n']} counties within 100 km of a rules line ({len(set(b['pair'] for b in bs))} state pairs), each centimeter of rain costs {abs(key['est']):.2f} points {'more' if key['est'] < 0 else 'less'} turnout on the excuse-required side than on the no-excuse side of the same line ({sig(key)})."})
    else: h2.update({"verdict": "Too early", "reading": f"Border sample so far: {len(bs)} counties with votes within 100 km of a rules line, {sum(1 for b in bs if b['rain'] >= 1)} of them wet. Needs about 60 and 15."})
    # early-voting-days version (moderation, not RDD)
    if not early:
        X = [[1.0] * len(have), [r["rain_cm"] for r in have], [r["rain_cm"] * r["early"] / 10 for r in have]] + fe(None, [r["st"] for r in have])
        res = ols([r["short"] for r in have], np.array(X).T, ["const", "rain (per cm)", "rain x early-voting days (per 10 days)"] + [None] * (len(X) - 2 - 1), cluster=[r["st"] for r in have])
        if res: h2["early_days_table"] = [x for x in res["rows"] if x["term"] != "const"]; h2["early_days_n"] = res["n"]
    R["hypotheses"].append(h2)
    # ----- H3: rain helps Republicans -----
    h3 = {"id": "H3", "title": "Rain helps Republicans", "claim": "Rain shifts the vote toward Republicans because the voters it keeps home lean Democratic (Gomez, Hansford & Krause 2007); the newer argument is that the effect shrinks or reverses where Democrats vote by mail.",
          "design": "Counties with votes counted. The county's Democratic two-way share in the House race tonight minus Harris's 2024 two-way share, regressed on rain and rain x convenience-voting state, with state fixed effects; errors clustered by state. A negative rain coefficient means rain is moving the count toward Republicans in excuse-required states."}
    h3s = [r for r in have if r["m24"] is not None and r["dem"] + r["rep"] > 50]
    for r in h3s: r["dshift"] = r["dem"] / (r["dem"] + r["rep"]) * 100 - (50 - r["m24"] / 2)
    if not early and len(h3s) >= 150:
        X = [[1.0] * len(h3s), [r["rain_cm"] for r in h3s], [r["rain_cm"] * r["conv"] for r in h3s]] + fe(None, [r["st"] for r in h3s])
        res = ols([r["dshift"] for r in h3s], np.array(X).T, ["const", "rain (per cm)", "rain x convenience-voting state"] + [None] * (len(X) - 3), cluster=[r["st"] for r in h3s])
        if res:
            b = next(x for x in res["rows"] if x["term"] == "rain (per cm)"); i = next(x for x in res["rows"] if x["term"].startswith("rain x"))
            h3.update({"n": res["n"], "r2": res["r2"], "table": [x for x in res["rows"] if x["term"] != "const"], "verdict": verdict(b, expect="neg"),
                       "reading": f"In excuse-required states, each centimeter of rain moves the Democratic share {b['est']:+.2f} points against its 2024 baseline ({sig(b)}); in no-excuse states the rain effect is {b['est'] + i['est']:+.2f} points per cm."})
    else: h3.update({"verdict": "Too early", "reading": f"Needs about 150 counties with both parties' votes counted ({len(h3s)} so far)."})
    R["hypotheses"].append(h3)
    return R, have, bs, h3s

def sig(b):
    p = b.get("p");
    if p is None: return "no standard error"
    return "p < 0.01" if p < 0.01 else "p < 0.05" if p < 0.05 else "p < 0.10" if p < 0.10 else f"p = {p:.2f}, not significant"
def verdict(b, expect):
    p = b.get("p"); e = b["est"]
    if p is None: return "Inconclusive"
    right = (e < 0) if expect == "neg" else (e > 0)
    if p < 0.05: return "Supported" if right else "Contradicted"
    if p < 0.10: return "Weak support" if right else "Weak evidence against"
    return "Not supported so far"

# ---------- 4. figures ----------
def figures(have, bs, h3s):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none"})
    D, Rc, INK, MUTED = "#2E5E9E", "#B5451B", "#1B2A41", "#6B7280"
    def binned(xs, ys, nb=12):
        xs = np.array(xs); ys = np.array(ys);
        if len(xs) < 5: return [], [], []
        qs = np.unique(np.quantile(xs, np.linspace(0, 1, nb + 1))); mx, my, ms = [], [], []
        for a, b in zip(qs[:-1], qs[1:]):
            m = (xs >= a) & (xs <= b) if b == qs[-1] else (xs >= a) & (xs < b)
            if m.sum() >= 3: mx.append(xs[m].mean()); my.append(ys[m].mean()); ms.append(ys[m].std(ddof=1) / math.sqrt(m.sum()))
        return mx, my, ms
    # F1
    fig, ax = plt.subplots(figsize=(7, 4.2))
    if len(have) >= 5:
        x = [r["rain"] for r in have]; y = [r["short"] for r in have]; mx, my, ms = binned(x, y)
        ax.scatter(x, y, s=8, color=MUTED, alpha=.25, label="counties")
        if mx: ax.errorbar(mx, my, yerr=ms, fmt="o", color=INK, label="bin means ± s.e.")
        if len(x) > 2:
            b1, b0 = np.polyfit(x, y, 1); xx = np.linspace(min(x), max(x), 50); ax.plot(xx, b0 + b1 * xx, color=Rc, label=f"fit: {b1*25.4:+.2f} pts per inch")
        ax.legend(frameon=False, fontsize=9)
    else: ax.text(.5, .5, "Waiting for counties to report", ha="center", va="center", transform=ax.transAxes, color=MUTED)
    ax.axhline(0, color=MUTED, lw=.8); ax.set_xlabel("precipitation today at the county center (mm)"); ax.set_ylabel("turnout vs. expectations (points)"); ax.set_title("H1 · Rain and turnout, all counties with votes", loc="left", color=INK)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_h1.svg")); plt.close(fig)
    # F2: RD plot
    fig, ax = plt.subplots(figsize=(7, 4.2))
    if len(bs) >= 10:
        for lab, col, sel in [("dry (< 1 mm)", INK, lambda b: b["rain"] < 1), ("wet (≥ 1 mm)", D, lambda b: b["rain"] >= 1)]:
            sub = [b for b in bs if sel(b)]
            if len(sub) < 4: continue
            edges = np.arange(-100, 101, 20); xs, ys, es = [], [], []
            for a, c in zip(edges[:-1], edges[1:]):
                g = [b["short"] for b in sub if a <= b["sd"] < c]
                if len(g) >= 3: xs.append((a + c) / 2); ys.append(np.mean(g)); es.append(np.std(g, ddof=1) / math.sqrt(len(g)))
            if xs: ax.errorbar(xs, ys, yerr=es, fmt="o-", color=col, label=f"{lab}, n={len(sub)}")
        ax.axvline(0, color=Rc, lw=1.2); ax.text(-98, ax.get_ylim()[1], "← no-excuse / all-mail side", va="top", fontsize=9, color=MUTED); ax.text(98, ax.get_ylim()[1], "excuse-required side →", va="top", ha="right", fontsize=9, color=MUTED)
        ax.legend(frameon=False, fontsize=9, loc="lower left")
    else: ax.text(.5, .5, "Waiting for counties near rules lines to report", ha="center", va="center", transform=ax.transAxes, color=MUTED)
    ax.axhline(0, color=MUTED, lw=.8); ax.set_xlabel("km from the state line (rules change at 0)"); ax.set_ylabel("turnout vs. expectations (points)"); ax.set_title("H2 · Same storm, different rules: turnout at the line", loc="left", color=INK)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_h2.svg")); plt.close(fig)
    # F3
    fig, ax = plt.subplots(figsize=(7, 4.2))
    if len(h3s) >= 10:
        for lab, col, sel in [("excuse-required states", Rc, lambda r: r["conv"] == 0), ("no-excuse / all-mail states", D, lambda r: r["conv"] == 1)]:
            sub = [r for r in h3s if sel(r)]
            if len(sub) < 5: continue
            mx, my, ms = binned([r["rain"] for r in sub], [r["dshift"] for r in sub], 8)
            if mx: ax.errorbar(mx, my, yerr=ms, fmt="o-", color=col, label=f"{lab}, n={len(sub)}")
        ax.legend(frameon=False, fontsize=9)
    else: ax.text(.5, .5, "Waiting for counties to report", ha="center", va="center", transform=ax.transAxes, color=MUTED)
    ax.axhline(0, color=MUTED, lw=.8); ax.set_xlabel("precipitation today (mm)"); ax.set_ylabel("Democratic share vs. Harris 2024 (points)"); ax.set_title("H3 · Rain and the partisan shift, by voting rules", loc="left", color=INK)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_h3.svg")); plt.close(fig)

if __name__ == "__main__":
    t0 = time.time()
    agg, meta = turnout()
    mm, asof = rain(); meta["rain_asof"] = asof
    rows = build(agg, mm)
    R, have, bs, h3s = analyze(rows, meta)
    try: figures(have, bs, h3s); R["figures"] = {"H1": "fig_h1.svg", "H2": "fig_h2.svg", "H3": "fig_h3.svg"}
    except Exception as e: R["figure_error"] = str(e)
    R["seconds"] = round(time.time() - t0, 1)
    # a compact per-run history of the headline coefficients, for the page's "how the estimate moved tonight" strip
    hist_p = os.path.join(OUT, "history.json")
    try: hist = json.load(open(hist_p))
    except Exception: hist = []
    hist.append({"t": R["run_at"], "n": R["data"]["counties_with_votes"], "H1": (R["hypotheses"][0].get("table") or [{}])[0].get("est"), "H2": next((x["est"] for x in R["hypotheses"][1].get("table", []) if x["term"].startswith("restrictive x rain")), None), "H3": (R["hypotheses"][2].get("table") or [{}])[0].get("est")})
    json.dump(hist[-200:], open(hist_p, "w"))
    json.dump(R, open(os.path.join(OUT, "results.json"), "w"), indent=1)
    print(json.dumps({"counties": R["data"], "verdicts": [h.get("verdict") for h in R["hypotheses"]], "seconds": R["seconds"]}))
