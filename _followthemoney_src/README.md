# Sources for popcornlove.net/followthemoney (Scholar Showcase talk, Oct 30 2026)
Not published (underscore folder). Rebuild the page: `python3 build_page.py ../followthemoney/index.html` (from inside `_followthemoney_src/` in the eornom21/lab repo)
(reads page_template.html + races.json, and money.json / meta.json once the data thread delivers them).
- races.json: the 8 poll races (CA-13, CA-22, AZ-6, PA-10, NC-1, AL-2, TX-15, NY-17).
- races_to_watch_2026.md, tossups_2026.csv: sourced 2026 battlefield research (10/29).
- maps/: maps.js (d3-geo + us-atlas, `npm i us-atlas@3.0.1 d3-geo@3.1.1 topojson-client@3.1.0`), render.js (playwright SVG->PNG).
- photos/: official House portraits (unitedstates/images, by bioguide ID) of the 8 incumbents.
- Poll backend: ntfy.sh topic ucm-ftm-2026-k7q3vz (public, anonymous; messages cached ~12h).
