# lab.nathanwmonroe.com

Nate's professional public pages: talk companion pages, dashboards, small tools. GitHub Pages, custom domain lab.nathanwmonroe.com (CNAME record in Wix DNS for nathanwmonroe.com points to eornom21.github.io), branch `main`. Every top-level folder is a page: `lab.nathanwmonroe.com/<folder>/`.

## Publishing a new page
1. Pick a short slug. Don't reuse an existing folder unless Nate asked to replace that page.
2. Copy `_template/index.html` to `<slug>/index.html` and build the page there. One self-contained file; images and data go in `<slug>/`.
3. Commit and push straight to `main` (`git fetch origin main && git rebase origin/main` first).
4. Wait until `https://lab.nathanwmonroe.com/<slug>/` serves the new page (usually 1–2 minutes), then give Nate the link.

## Rules
- Pages are public to anyone with the link. No student info, finances, addresses, or anything Nate calls private.
- Keep `<meta name="robots" content="noindex, nofollow">` unless Nate asks for the page to show up in Google.
- Folders starting with `_` are not published (Jekyll skips them). `_template/` is the starter.
- Leave the root `index.html` and `CNAME` alone unless Nate asks.
- Updating a page: edit it in place, push, same URL. Deleting a page: only after Nate says yes.
- Personal and non-professional pages (parlays, HUSL, podcast) stay on popcornlove.net.

## Existing pages
followthemoney (Scholar Showcase talk companion, Oct 30, 2026; the deck's QR code points here). Sources live in `_followthemoney_src/` in this repo: rebuild with `python3 _followthemoney_src/build_page.py followthemoney/index.html`. popcornlove.net/followthemoney only forwards here (Nate, 10/29: no work pages on popcornlove).

electionnight (Election Night 2026 watch-party phone page: Ask the lab (questions + the lab's answers), 32 races with each side's case and winners, money explorer; picks and the room tally removed Nov 3). Answers: `electionnight/answers.json`, copied from the dashboard's `answers` collection by the Election Night Lab thread with scratchpad relay/sync_answers.py; the page re-reads it every minute. Sources in `_electionnight_src/`: rebuild with `python3 _electionnight_src/build_page.py electionnight/index.html`. Winners: edit `electionnight/results.json` ({"races": {"PA10": {"called": "D", "d_pct": 51, "r_pct": 49, "pct_in": 95}}}); the page re-reads it every minute. The old picks poll topic (ntfy.sh/ucm-eln-2026-a03f51) is no longer used. Ask tab sends questions to ntfy.sh/ucm-eln-2026-q-6525225a; Nate reads them at electionnight/questions.html ("Nate's desk", unlinked, noindex), which also has a Talking points tab fed by `electionnight/talking.json` ({"items": [{id, t, section, title, body, show}]}), written by the Election Night Lab thread every 15 min 7–9:30pm on election night. Owned by the Election Night Lab thread from Oct 30, 2026.

electionlab (public read-only mirror of the Election Night Lab watch-party dashboard, Nov 3, 2026, for people not in the room: same views and Asked & answered cards, no Ask box). Built from the dashboard source in the Election Night Lab thread's scratchpad (scripts/build_mirror.py); numbers come from `electionlab/snap.json`, rewritten by that thread with each feed update (relay/snap_build.py); the page re-reads it every minute. Not linked from the phone page (Nate, Nov 3: keep them separate).

ca13 (CA-13 race watcher, Gray vs. Lincoln, Nov 3, 2026: the race, election night, news and the room; no money tab, the money is /moneyca13 from data thread 6). Sources in `_ca13_src/`: rebuild with `python3 _ca13_src/build_page.py ca13/index.html`. 2026 results come live from api.sos.ca.gov in each viewer's browser (the feed allows cross-site reads), every minute. News is a snapshot in `_ca13_src/ca13_data.json` (`news`, `news_asof`). Poll topic ntfy.sh/ucm-ca13-2026-a6cfce. Built by the Election Night Lab thread.
