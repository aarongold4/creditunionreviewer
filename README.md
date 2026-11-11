# creditunionreviewer.com

Static review/directory site for US credit unions. 163 pages built from a single JSON data file.

## Build

```bash
pip install -r requirements.txt
python3 build.py        # data/ + templates/ -> dist/ (163 pages + sitemap.xml + robots.txt)
```

## Structure

- `data/creditunions.json` — single source of truth. 100 credit unions: 26 `tier:"full"` (editorial reviews), 74 `tier:"regional"` (profiles). All 50 states have at least one HQ'd credit union. 17 flagged `fom.anyone_can_join: true`.
- `templates/` — Jinja2. `base.html` carries head tokens, nav, footer, schema hooks.
- `static/` — style.css (teal/cream, Fraunces + Public Sans) and site.js (mobile nav, table sort).
- `build.py` — renders all pages, generates sitemap.xml, robots.txt, JSON-LD (Article, FAQPage, BreadcrumbList, WebSite/Organization).
- `dist/` — upload contents to Hostinger public_html.

## Pages (186)

Home · /best-credit-unions/ · /anyone-can-join/ · /credit-union-vs-bank/ · /how-to-join/ · /ncua-insurance/ · 8 product roundups under their own slugs · /guides/ hub · /can-i-join/ finder · /compare/ hub + 11 head-to-head pages · /glossary/ · 100× /reviews/{slug}/ · /state/ index + 50 state pages · methodology, how-we-make-money, about, contact, privacy, terms · 404.html (excluded from sitemap).

### Comparisons & categories

- Head-to-head matchups live in the `MATCHUPS` list in `build.py` (slugs, editorial verdicts, FAQs). Add a dict with two existing `full`-tier slugs to create a new `/compare/{a}-vs-{b}/` page; review pages auto-link any matchup they appear in.
- Product roundups live in the `CATEGORIES` list + the `categories` array on each CU in the JSON. Add a slug to a category's membership (via the tagging step) and rebuild.

### 404 handling on Hostinger (Apache)

`dist/404.html` exists but a static host won't serve it automatically. Add to `.htaccess` in your web root:

```apache
ErrorDocument 404 /404.html
```


## Site settings (no tokens)

Analytics/verification/form settings live in `data/meta.json` and are filled in where
present, omitted where blank — the build never emits a literal `{{TOKEN}}` (the deploy
safety check rejects any that survive). Set and rebuild:

| meta.json field | Value |
|---|---|
| `ga4_id` | GA4 measurement ID (G-XXXXXXX) — loads only after cookie consent |
| `gsc_token` | Google Search Console verification content value |
| `bing_token` | Bing Webmaster verification content value |
| `form_action` | Contact-form endpoint (Formspree/Web3Forms URL); blank → form degrades to inert |

Affiliate links come from `data/affiliates.json` and the `affiliate_mode` flag (below).

## Data-freshness architecture

This mirrors the onlinebankreview.com setup so both sites behave identically.

### `data/meta.json` — the single source of public freshness

- `verified_date` (YYYY-MM-DD) — drives the visible "Last verified" stamp, JSON-LD `dateModified`, and sitemap `<lastmod>`. **Never derived from the build date.**
- `affiliate_mode` (bool) — flips affiliate link behavior (below).
- `update_frequency` (sentence) — shown in the footer.

The real build date is used **only** for the `?v=YYYYMMDD` cache-buster on `style.css`/`site.js`, so deploys bust caches without touching any freshness signal.

### Date-expiry exclusion

Any dated item is auto-hidden once expired, based on the **real calendar date** at build time, while staying in the data file. Implemented for affiliate `bonus`/`bonus_expires` via the `_active()` helper; reuse it for any future promos. Expired bonuses simply don't render — no edit required.

### Affiliate seasoning (`data/affiliates.json`)

Per offer: `url` (public), `affiliate_url` (nullable), optional `bonus` + `bonus_expires`.

- `affiliate_mode: false` → CTA links to `url` with `rel="nofollow noopener"`.
- `affiliate_mode: true` → CTA links to `affiliate_url` with `rel="nofollow sponsored noopener"`, **falling back** to `url` (non-sponsored rel) if `affiliate_url` is null.

To go live with affiliates: set each `affiliate_url`, flip `affiliate_mode` to `true` in `meta.json`, rebuild.

### Weekly automation — `update.py`

Read-only job (run by CI or manually). It:
1. Reports how stale `verified_date` is.
2. Flags bonuses expired or expiring within 14 days.
3. Runs a best-effort rate monitor from `data/rate_sources.json` (fetch page + regex, compare to `rates.json`, report mismatches — selectors are fragile, so failures mean "verify manually").
4. Writes a dated report to `reports/`.
5. Calls `build.py` (skip with `--no-build`).

It **never** edits JSON or advances `verified_date`.

```bash
python update.py            # audit + monitor + report + build (CI)
python update.py --no-build # audit + monitor + report only (monthly review)
```

### Monthly human workflow (the only thing that moves the public stamp)

1. `python update.py --no-build`
2. Read `reports/report-<date>.md`.
3. Verify flagged items against the institutions' own pages.
4. Edit the JSON (`rates.json`, `affiliates.json`, etc.) as warranted.
5. Bump `verified_date` in `data/meta.json`.
6. `python build.py`.

Only step 5 changes the public "Last verified" date.

### CI / deploy (mirrors onlinebankreview.com)

`.github/workflows/weekly.yml` runs on a Monday cron, on every push to `main`, and on
manual dispatch. It runs `update.py`, enforces a safety gate (≥150 pages, `index.html`
present, **no `{{PLACEHOLDER}}` anywhere in `dist/`**), then force-pushes the built
`dist/` to the **`deploy`** branch. Hostinger's Git deployment watches `deploy` and
serves it — no FTP, no passwords. The weekly review report is uploaded as a workflow
artifact. `.gitignore` excludes `dist/` and `__pycache__/`.

One-time setup: create the repo, push `main`, then in Hostinger hPanel → Git connect
the repo and set the deployed branch to `deploy` with the web root as the target.

## ⚠️ Before launch

1. **Verify rates, ratings, and membership details.** Rates/ratings ship as
   representative placeholders. Confirm against each credit union's own page — especially
   the anyone-can-join donation paths — then bump `verified_date` in `data/meta.json`.
2. Fill `ga4_id` / `gsc_token` / `bing_token` / `form_action` in `data/meta.json` (blank
   is fine; they're simply omitted).
3. Submit `sitemap.xml` in Search Console and Bing after the first deploy.

## Pages (190)

Home · /best-credit-unions/ · /anyone-can-join/ · /credit-union-vs-bank/ · /how-to-join/ · /ncua-insurance/ · /rates/ · 8 product roundups · /guides/ · /can-i-join/ finder · /credit-unions/ A–Z directory · /compare/ + 11 head-to-head pages · /glossary/ · /auto-loan-calculator/ · /mortgage-calculator/ · 100× /reviews/{slug}/ · /state/ index + 50 state pages · methodology, how-we-make-money, about, contact, privacy, terms · 404.html.

**Every credit union has its own page** (`/reviews/{slug}/`) — full reviews for the 26 flagship CUs, profiles for the other 74 — and the `/credit-unions/` directory lists all 100 with client-side search + filters (state, review depth, anyone-can-join) over a server-rendered table, so every CU is one click from a central hub and all 100 links are in the HTML for crawlers.

### Member counts

Source data stores member counts inconsistently (some integers, some strings like `"500,000+"`). The build normalizes both into `members_num` (for sorting) and `members_fmt` (humanized display, e.g. `14 million+`, `2.9 million+`, `500,000+`). Templates use `members_fmt` everywhere; you don't need to clean the source.

## Calculators

Two dependency-free vanilla-JS calculators, each embedded on its roundup and on a standalone page:
- `/auto-loan-calculator/` (partial `templates/_autocalc.html`) — APR pre-fills with `CALC_DEFAULT_APR` (lowest rated new-auto rate).
- `/mortgage-calculator/` (partial `templates/_mortgagecalc.html`) — principal & interest, APR pre-fills with `MTG_DEFAULT_APR` (lowest rated 30-yr rate).

## Ratings (`data/ratings.json`)

Each full-review credit union has a 1–5 score on five factors (`rates`, `fees`, `access`, `digital`, `products`); the build computes a weighted overall (weights in `meta.weights`, currently 30/20/20/15/15) and renders it as a fractional-fill SVG star row + number + word label. Ratings drive the ordering of the best-credit-unions page and homepage top picks, appear as a sortable column in the best-page and roundup comparison tables, and get a full factor-bar breakdown on each review. Review pages also emit `schema.org/Review` with `reviewRating` for rich results.

To re-score a credit union or retune weights: edit `data/ratings.json` and rebuild — the stars, ordering, tables, and schema all update. Regional (profile-tier) CUs are intentionally unrated and show "—".

### ⚠️ Ratings are editorial scores you should own before launch

Like the rates, the shipped scores are defensible editorial assessments anchored to each CU's profile — but you are publishing them under the Nathan Blake byline, so review them and make sure you stand behind the numbers and the weights. The `/methodology/` page explains the five factors and weighting publicly; keep it consistent with `meta.weights` if you change them.

## Rate history & trends (`data/rate_history.json`)

Trend arrows and inline sparklines (on /rates/ and full reviews) come from dated snapshots. The file holds an array of prior `snapshots` (each a dated map of `{slug: {savings_apy, cd_12, checking_apy, auto_new_apr}}`); the current values from `rates.json` form the latest point. The build computes deltas (arrow vs the previous snapshot) and renders dependency-free SVG sparklines (green = favorable direction, clay = unfavorable; for auto APR, *down* is favorable).

**Workflow each rate update:** before editing `rates.json`, append its current tracked values as a new dated snapshot in `rate_history.json`, then update `rates.json` and rebuild. That keeps the trend honest. The shipped snapshots are representative scaffolding like the rates themselves.

## Auto loan calculator

A dependency-free vanilla-JS calculator (`templates/_autocalc.html`) is embedded on the auto-loans roundup and on a standalone `/auto-loan-calculator/` page. APR pre-fills with the lowest representative new-auto rate across rated CUs (computed in `build.py` as `CALC_DEFAULT_APR`). It uses the standard amortization formula entirely client-side.

## Rates data layer (`data/rates.json`)

Rates live in their **own file**, separate from `creditunions.json`, because they change far more often than editorial content. The build merges them onto each credit union at render time, so a rate page is `/rates/`, every full review shows a rates-at-a-glance table, and the savings/CD/checking/auto roundups gain a sortable rate column.

- `meta.as_of` — the date stamped on every rate display. **Update this whenever you touch rates.**
- `meta.disclaimer` — shown on the /rates/ hub.
- `rates.{slug}` — one record per credit union (currently the 26 full-profile CUs). Fields: `savings_apy`, `checking_apy` (+ `checking_note` for caps/conditions), `mm_apy`, `cd_12`, `cd_36`, `cd_60`, `auto_new_apr`, `card_apr_low`, `mortgage_30_apr`. Deposits are APY, loans are APR.

To update rates: edit `data/rates.json`, bump `meta.as_of`, run `python3 build.py`. No template or editorial changes needed. Sorting is automatic (APY high→low, APR low→high). To rate a credit union that has none (e.g. a regional one), add a `rates` record under its slug — it appears in the tables and on its review automatically.

### ⚠️ The rate numbers shipped are REPRESENTATIVE scaffolding

The figures in `data/rates.json` are realistic, internally-coherent placeholders for layout and structure — **not live quotes**. Verify every value against each credit union's current rate sheet before launch, then set `meta.as_of` to the real date. This is the single most important pre-launch task: publishing wrong financial rates is both a trust and a liability problem. The site is built to make this a one-file edit precisely so it stays honest.

## Extending with NCUA call-report data

Each credit union record has `ncua_charter: null` as the join key. Populate with NCUA charter numbers, then merge quarterly call-report fields (assets, members, net worth ratio) from NCUA.gov data downloads into new fields — templates can surface them in the review factbox. `meta.schema_version` tracks data shape changes.

## Author

All editorial content bylined Nathan Blake (site pen name).
