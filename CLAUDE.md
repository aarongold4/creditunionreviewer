# Working on creditunionreviewer.com

Static credit-union review + directory site (Python/Jinja2 -> dist/, ~192 pages),
pen name **Nathan Blake**. Sibling of onlinebankreview.com; same automation pattern.

Build: `python3 build.py`.  Deploy: push to `main` → GitHub Action builds and
force-pushes `dist/` to the `deploy` branch → Hostinger Git deployment serves it.
Never edit `dist/` by hand. Never add uppercase `{{TOKEN}}` placeholders — the
deploy safety check rejects any `{{...}}` in the built site, and site settings
(ga4_id, gsc_token, bing_token, form_action) live in `data/meta.json`.

## Standing rule from Aaron (every session, scheduled or not)
1. **Check everything systematically.** Every credit union, every rate, every
   membership/eligibility claim, every number in `data/`, `build.py`, templates and
   guides — against the credit union's own page (or two agreeing sources from the
   last 30 days). NCUA insurance + charter facts via the NCUA (ncua.gov "Research a
   Credit Union" / Find a Credit Union). Confirm anyone-can-join paths and their
   donation amounts against the credit union's live membership page.
2. **Correct everything systematically.** Fix confirmed facts and the prose that
   depends on them. Re-score the five-factor ratings with the published rubric
   (methodology page: rates 30 / fees 20 / membership access 20 / digital 15 /
   products 15); let the rankings and star ratings follow. Mark merged/closed credit
   unions with a closed status; apply renames without changing slugs; rewrite a review
   only when its core story no longer holds. Append a dated snapshot to
   `data/rate_history.json` BEFORE changing current numbers in `rates.json`, so the
   sparklines/trends stay honest.
3. **Report.** Every change (old → new, source), a specific "spot-check these" list,
   could-not-verify, needs-your-decision, and quality checks. Save to the Google Drive
   folder "creditunionreviewer.com audits".
4. **Suggest new content.** 3–5 ideas in `data/content_ideas.json` plus one draft
   guide as a `draft/` pull request. Aaron publishes from his Site Approvals page in
   Claude (Publish/Discard), never from GitHub.

Never invent a number; never publish anything unverified. The public "Last verified"
stamp comes only from `verified_date` in `data/meta.json` — bump it ONLY after a real
human/data re-verification, never for a code or design rebuild.

## Data layer (one source of truth each)
- `creditunions.json` — 100 credit unions (26 full reviews + 74 profiles), fields,
  membership, pros/cons, editorial, `anyone_can_join` + join path/cost.
- `rates.json` (+ `rate_history.json`, `rate_sources.json`) — rates for the 26 full
  CUs; monitor config; dated history for trends. **Representative placeholders until
  the first verification pass** — treat as unverified until confirmed and `verified_date`
  reflects it.
- `ratings.json` — five-factor editorial scores + weights.
- `affiliates.json` — per-CU `url` (public) and `affiliate_url`; seasoning controlled
  by `affiliate_mode` in meta.json (false → rel="nofollow noopener" on public url;
  true → rel="nofollow sponsored noopener" on affiliate_url, falling back to url).
- `meta.json` — verified_date, affiliate_mode, update_frequency, and the four settings.

## update.py (what the weekly Action runs)
Audits freshness + bonus/promo expiry, best-effort rate monitor vs `rate_sources.json`,
rebuilds (so date-expired items drop and labels roll over), writes `reports/`. It
**never** edits data and **never** advances `verified_date`. Verification stays human.

## Approvals (Publish/Discard in Claude, never GitHub)
Aaron approves draft guides on his shared **Site Approvals** page in Claude, not on
GitHub. When a run opens a draft PR: add a row with ArtifactData (collection "drafts",
doc_id "creditunionreviewer-<idea id>"; fields site "creditunionreviewer.com", idea_id,
title, why_now, doc_url, pr_url, trigger_id "trig_01XvjfbrWWPm1qm6vXUQbLeL", created, updated,
status "pending", result_url null, result_note null), send a PushNotification
"New creditunionreviewer.com draft ready: <title>. Open Site Approvals in Claude to
publish or discard.", and never tell Aaron to merge a PR, open GitHub, or press Run now.
