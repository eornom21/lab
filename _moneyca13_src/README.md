# moneyca13 sources (not published; folder starts with _)

Build for lab.nathanwmonroe.com/moneyca13: where Adam Gray's and Javier Lincoln's 2026 itemized individual money comes from (in-district, rest of California, out of state), by county, ZIP, state and month. Spec: `claude/ca13-page-spec-2026-10-30.md` in the Campaign Contributions Paper project. Saved here 2026-11-08 by data thread 6 at handoff; the page itself is NOT built yet.

Status 2026-11-08: page template and geography done and previewed on SAMPLE data. Real data not yet pulled: FEC bulk `indiv26.zip` / `cn26.zip` / `ccl26.zip` redirect to `cg-519a459a-0ea3-42c2-b7bc-fa1143481f74.s3-us-gov-west-1.amazonaws.com`, which the cloud workspace's allowlist blocks (api.open.fec.gov is blocked too). www.fec.gov itself is reachable.

To finish, once the S3 host is allowed (or from the Mac browser pane):
1. Find the two committees' IDs in cn26/ccl26 (Gray and Lincoln, House CA-13, principal campaign committees) and write `committees.json`: {"gray": {"label": "Adam Gray (D)", "cmte": "C00..."}, "lincoln": {"label": "Javier Lincoln (R)", "cmte": "C00..."}}.
2. Stream indiv26: `curl -L .../indiv26.zip | funzip | grep -E '^(C00…|C00…)\|' > itcont_ca13.txt` (pipe-delimited FEC rows, no header).
3. `python3 build_money.py` -> `ca13_money.json` (rules: types 15/15E, IND, no MEMO_CD X, amount > 0; ZIP centroid inside the Prop 50 / AB604 CD-13 polygon = in-district).
4. `python3 build_page.py ../moneyca13/index.html`, then a separate agent checks totals against the FEC committee summary pages and re-places a sample of ZIPs.
5. Commit and push; give Nate the link for Adam. Keep the noindex meta.

Files: build_money.py, build_page.py, page_template.html (placeholders /*MONEY*/{}, /*CA_COUNTIES*/null, /*CD13*/null), zip_geo.csv (42,789 ZIPs from the `zipcodes` pip package: city, state, county, lat, lon, in_cd13; 51 ZIPs inside the new CD-13), cd13_prop50.geojson (from the Statewide Database AB604 shapefile, EPSG:4269), ca_counties.geojson, ca_state.geojson.
