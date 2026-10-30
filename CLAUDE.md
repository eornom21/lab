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
followthemoney (Scholar Showcase talk companion, Oct 30, 2026; also live at popcornlove.net/followthemoney, where its sources live in `_followthemoney_src/`. Rebuild there, then copy `followthemoney/index.html` here).
