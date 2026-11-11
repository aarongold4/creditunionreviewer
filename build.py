#!/usr/bin/env python3
"""Build creditunionreviewer.com static site: data/*.json + templates/ -> dist/.

Deployment tokens like {{GA4_ID}} are passed through literally so they can be
replaced post-build (sed or deploy script). See README.md.
"""
import json
import shutil
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
BASE_URL = "https://creditunionreviewer.com"

# --- Freshness architecture (mirrors onlinebankreview.com) ---
# Public freshness signals come from data/meta.json (verified_date), NEVER the build date.
# The real build date is used ONLY for the ?v= cache-buster on static assets.
_META = json.loads((ROOT / "data" / "meta.json").read_text())
VERIFIED_DATE = _META["verified_date"]              # drives stamp, dateModified, lastmod
AFFILIATE_MODE = bool(_META.get("affiliate_mode", False))
UPDATE_FREQUENCY = _META.get("update_frequency", "")
# Site settings live in meta.json and are filled in where present, omitted where
# blank. Never emitted as {{PLACEHOLDER}} tokens (the deploy safety check rejects those).
GA4_ID = _META.get("ga4_id", "")
GSC_TOKEN = _META.get("gsc_token", "")
BING_TOKEN = _META.get("bing_token", "")
FORM_ACTION = _META.get("form_action", "")
BUILD_VERSION = date.today().strftime("%Y%m%d")     # cache-buster only
TODAY = date.today().isoformat()                    # for date-expiry exclusion

AFFILIATES = json.loads((ROOT / "data" / "affiliates.json").read_text())["offers"]


def _active(expires):
    """True if an item with this 'expires' (YYYY-MM-DD or None) is still live today."""
    return (not expires) or (str(expires) >= TODAY)

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}

# Real site settings (from meta.json). Templates fill these where set and omit
# the surrounding markup where blank — no literal {{TOKEN}} ever reaches dist/.
TOKENS = {
    "GA4_ID": GA4_ID,
    "GSC_TOKEN": GSC_TOKEN,
    "BING_TOKEN": BING_TOKEN,
    "FORM_ACTION": FORM_ACTION,
}


def _cta(key, brand, tagline, points, btn, disclosure=True):
    """Render a styled CTA. Link + rel follow affiliate seasoning rules:
       - affiliate_mode False  -> public url, rel='nofollow noopener'
       - affiliate_mode True   -> affiliate_url, rel='nofollow sponsored noopener'
         (falls back to public url + non-sponsored rel if affiliate_url missing)
       An optional dated bonus is shown only while not expired."""
    offer = AFFILIATES.get(key, {})
    public = offer.get("url") or "/"
    aff = offer.get("affiliate_url")
    sponsored = AFFILIATE_MODE and bool(aff)
    href = aff if sponsored else public
    rel = "nofollow sponsored noopener" if sponsored else "nofollow noopener"
    target = ' target="_blank"' if href.startswith("http") else ""

    bonus = offer.get("bonus")
    bonus_html = ""
    if bonus and _active(offer.get("bonus_expires")):
        bonus_html = f'<p class="cta-bonus">{bonus}</p>'

    lis = "".join(f"<li>{p}</li>" for p in points)
    fine = (
        '<p class="cta-fine">We may earn a commission if you open an account through '
        f'this link, at no cost to you. <a href="{BASE_URL}/how-we-make-money/">How we make money</a>.</p>'
        if disclosure else ""
    )
    return (
        '<div class="cta-card">'
        f'<div class="cta-head"><span class="cta-brand">{brand}</span>'
        '<span class="cta-disc">Advertiser disclosure</span></div>'
        f'<p class="cta-tagline">{tagline}</p>'
        f"{bonus_html}"
        f'<ul class="cta-points">{lis}</ul>'
        f'<a class="btn btn-primary cta-btn" href="{href}" rel="{rel}"{target}>{btn}</a>'
        f"{fine}</div>"
    )


CTAS = {
    "cta_penfed": _cta(
        "penfed", "PenFed Credit Union",
        "Open to anyone in the U.S., with consistently competitive certificate and mortgage rates.",
        ["Membership open to everyone, no military tie required",
         "Strong CD and mortgage rates", "Federally insured by the NCUA"],
        "See PenFed rates &rarr;"),
    "cta_alliant": _cta(
        "alliant", "Alliant Credit Union",
        "A digital-first credit union with a high everyday savings rate and no monthly fees.",
        ["High-rate savings, fully online", "No monthly maintenance fees",
         "Anyone can join via a $5 foundation donation"],
        "Open an Alliant account &rarr;"),
    "cta_consumers": _cta(
        "consumers", "Consumers Credit Union",
        "Home of one of the highest rewards-checking rates around, open to anyone nationwide.",
        ["High-APY rewards checking (conditions apply)", "Open to anyone in the U.S.",
         "Federally insured by the NCUA"],
        "Open Consumers rewards checking &rarr;"),
    "cta_bank_alt": _cta(
        "bank_alt", "Online bank alternatives",
        "Can't join a credit union, or want to compare? Top online banks pay competitive rates with no membership step.",
        ["No membership or eligibility requirements", "High-yield savings that rivals the best CUs",
         "FDIC insured up to $250,000"],
        "Compare online bank offers &rarr;"),
}

CATEGORIES = [
    {"key": "cd-rates", "slug": "best-credit-union-cd-rates", "rate_col": "cd_12", "rate_col_label": "12-mo CD APY",
     "h1": "Best Credit Union CD Rates of 2026",
     "card_title": "Best CD Rates", "product_field": "cds", "product_label": "Certificates",
     "card_blurb": "Credit unions with the strongest share-certificate rates.",
     "lede": "Credit union certificates (CDs) routinely out-yield bank CDs. These are the credit unions whose certificate rates and laddering options stand out — several open to anyone in the US.",
     "alt_heading": "Prefer an online bank CD?", "alt_body": "Online banks compete hard on CD rates and skip the membership step entirely:",
     "method": "We weight certificate APYs across common terms against national averages, favoring institutions with consistent rates rather than one-off promos, and reward easy membership."},
    {"key": "auto-loans", "slug": "best-credit-union-auto-loans", "rate_col": "auto_new_apr", "rate_col_label": "New auto APR",
     "h1": "Best Credit Unions for Auto Loans (2026)",
     "card_title": "Best Auto Loans", "product_field": "loans", "product_label": "Lending",
     "card_blurb": "The lowest-rate, most borrower-friendly auto lenders.",
     "lede": "Auto loans are the classic credit union advantage — federal credit unions also cap most loan rates at 18%. These lenders consistently price below the market on new and used cars.",
     "alt_heading": "Shopping rates broadly?", "alt_body": "It's worth comparing an online lender alongside these credit unions:",
     "method": "We compare new- and used-auto APRs against market averages, factor in pre-approval flexibility and refinance options, and reward broad membership access."},
    {"key": "checking", "slug": "best-credit-union-checking-accounts", "rate_col": "checking_apy", "rate_col_label": "Checking APY",
     "h1": "Best Credit Union Checking Accounts of 2026",
     "card_title": "Best Checking", "product_field": "checking", "product_label": "Checking",
     "card_blurb": "Free checking and high-yield rewards checking picks.",
     "lede": "From unconditionally free checking to rewards accounts paying eye-catching APYs on balances, these credit union checking accounts beat what most banks offer.",
     "alt_heading": "Want a no-membership option?", "alt_body": "Several online checking accounts pay competitive rates with no eligibility step:",
     "method": "We score monthly fees, minimum balances, ATM access and rebates, and rewards-checking APYs (and their hoop requirements), favoring genuinely free accounts."},
    {"key": "savings", "slug": "best-credit-union-savings-accounts", "rate_col": "savings_apy", "rate_col_label": "Savings APY",
     "h1": "Best Credit Union Savings & Money Market Accounts (2026)",
     "card_title": "Best Savings", "product_field": "savings", "product_label": "Savings",
     "card_blurb": "Top high-yield savings and money market picks.",
     "lede": "These credit unions pay savings and money market rates that compete with the best online banks — and several let anyone join.",
     "alt_heading": "Compare with online high-yield savings", "alt_body": "The top online savings accounts are strong benchmarks to compare against:",
     "method": "We rank by savings and money market APYs relative to national averages, penalize balance caps and hoops, and reward open membership."},
    {"key": "mortgages", "slug": "best-credit-unions-for-mortgages",
     "h1": "Best Credit Unions for Mortgages & Home Loans (2026)",
     "card_title": "Best for Mortgages", "product_field": "loans", "product_label": "Lending",
     "card_blurb": "Strong mortgage lenders, including first-time-buyer programs.",
     "lede": "Many credit unions are major local mortgage lenders with lower fees and first-time-buyer programs. These stand out for home lending.",
     "alt_heading": "Comparing lenders?", "alt_body": "Always get at least one outside quote when shopping a mortgage:",
     "method": "We look at mortgage product breadth, first-time-buyer and no-PMI programs, local lending reputation, and closing-cost competitiveness."},
    {"key": "beginners", "slug": "best-credit-unions-for-beginners",
     "h1": "Best Credit Unions for Beginners & First Accounts (2026)",
     "card_title": "Best for Beginners", "product_field": None, "product_label": "",
     "card_blurb": "Easy to join, easy to start a savings habit.",
     "lede": "New to credit unions or opening a first real account? These are the easiest to join and the friendliest for building a savings habit, with low minimums and simple products.",
     "alt_heading": "Want zero membership steps?", "alt_body": "A no-frills online bank account is another easy starting point:",
     "method": "We favor low or no minimums, simple fee-free products, strong apps, and the easiest possible membership paths."},
    {"key": "nationwide", "slug": "best-nationwide-credit-unions",
     "h1": "Best Nationwide Credit Unions Anyone Can Join (2026)",
     "card_title": "Best Nationwide", "product_field": None, "product_label": "",
     "card_blurb": "Top picks open to every American, ranked.",
     "lede": "If you want a great credit union without a location or employer requirement, start here: the strongest nationally available credit unions, all open to anyone in the US.",
     "alt_heading": "Or skip membership entirely", "alt_body": "Online banks have no membership requirement at all:",
     "method": "Among credit unions anyone can join, we rank on rates, fees, product breadth, and digital experience."},
    {"key": "small-business", "slug": "best-credit-unions-for-small-business",
     "h1": "Best Credit Unions for Small Business (2026)",
     "card_title": "Best for Small Business", "product_field": None, "product_label": "",
     "card_blurb": "Business checking, lending, and merchant services.",
     "lede": "Credit unions can be a low-fee home for a small business's banking and borrowing. These offer the strongest business products.",
     "alt_heading": "Bigger commercial needs?", "alt_body": "Larger treasury or commercial needs may be better served elsewhere — compare options:",
     "method": "We weight business checking fees, business lending and SBA participation, merchant services, and membership eligibility for business owners."},
]

MATCHUPS = [
    {"a": "navy-federal", "b": "penfed", "hint": "Military giant vs the open-membership rate leader",
     "intro": "Two of the biggest names in credit unions — but only one will let just anyone join. Navy Federal is the largest US credit union and a military institution; PenFed pairs strong rates with membership open to everyone.",
     "pick_a": "you, a family member, or a household member has a military or Department of Defense connection. Navy Federal's member benefits, branch network on and near bases, and military-friendly lending are hard to beat for the armed forces community.",
     "pick_b": "you don't have a military tie. PenFed accepts anyone in the US, and its certificate and mortgage rates are consistently competitive — making it the obvious pick for civilians who can't get into Navy Federal.",
     "bottom_line": "If you qualify for Navy Federal, it's one of the best all-around credit unions in the country and worth joining. If you don't have a military connection, PenFed gives you most of the same big-CU advantages with no eligibility hurdle. For many people the choice is simply decided by whether they can get into Navy Federal at all.",
     "faqs": [
        {"q": "Can anyone join Navy Federal?", "a": "No. Navy Federal requires a connection to the armed forces, DoD, or a family/household member who is already eligible. If you don't have that tie, PenFed is the closer open-membership alternative."},
        {"q": "Is PenFed as good as Navy Federal?", "a": "For civilians, effectively yes — PenFed offers competitive rates and full-service products to anyone in the US. Navy Federal has a larger member-benefit ecosystem geared to the military community."}]},
    {"a": "penfed", "b": "alliant", "hint": "The two biggest nationwide, anyone-can-join picks",
     "intro": "PenFed and Alliant are the two credit unions most often recommended to people who want a great institution without an employer or location requirement. Both let anyone in the US join.",
     "pick_a": "you want a broad product lineup with strong certificates and mortgages, plus a physical branch presence in some areas. PenFed is the more traditional full-service option.",
     "pick_b": "you bank entirely online and want a clean digital experience with a consistently high savings rate and no monthly fees. Alliant is built digital-first.",
     "bottom_line": "Both are excellent and both are open to everyone, so you can't go wrong. PenFed leans full-service and rate-competitive across CDs and mortgages; Alliant is the slicker digital-only choice for savers. Many people who chase rates simply join both.",
     "faqs": [
        {"q": "Is Alliant or PenFed easier to join?", "a": "Both are easy and open to anyone in the US. Alliant offers a simple path through a one-time $5 donation to its associated charity; PenFed lets you join by opening a savings account. Neither requires an employer or location tie."},
        {"q": "Which has better rates, PenFed or Alliant?", "a": "It varies by product and changes often. Alliant is known for a strong everyday savings rate; PenFed frequently leads on certificates and mortgages. Compare current rates before deciding."}]},
    {"a": "alliant", "b": "first-tech", "hint": "Two digital-first lenders open to anyone",
     "intro": "Alliant and First Tech are both modern, largely digital credit unions that anyone in the US can join. They appeal to the same tech-comfortable saver.",
     "pick_a": "your priority is a high-yield savings rate and a simple, fee-free digital setup. Alliant keeps things lean and rate-forward.",
     "pick_b": "you want a broader lending lineup and a credit union with deep ties to the tech industry. First Tech offers a wider range of loans and specialty products.",
     "bottom_line": "Alliant edges out for pure savers who want a top rate with minimal fuss; First Tech is the stronger all-rounder if you also want financing options. Both are easy to join nationwide, so eligibility won't decide it.",
     "faqs": [
        {"q": "Can anyone join First Tech?", "a": "Yes. First Tech offers membership to anyone in the US, including through associations open to the public, so a tech-industry job isn't required."},
        {"q": "Which is better for savings?", "a": "Alliant is more known for a consistently high everyday savings rate, but compare current APYs since both adjust over time."}]},
    {"a": "penfed", "b": "navy-federal", "hint": "", "skip": True},  # dedupe guard, removed below
    {"a": "alliant", "b": "consumers", "hint": "Rate optimizers: top savings vs top checking",
     "intro": "Both Alliant and Consumers Credit Union are favorites of rate optimizers who'll cross state lines (virtually) for yield. Both are open to anyone in the US.",
     "pick_a": "you want a strong, low-maintenance savings rate without jumping through monthly hoops. Alliant rewards simplicity.",
     "pick_b": "you're willing to meet monthly requirements for one of the highest rewards-checking rates around. Consumers' rewards checking can pay well above a typical savings account if you hit the criteria.",
     "bottom_line": "Alliant suits set-and-forget savers; Consumers rewards people who'll actively meet rewards-checking requirements every month. If you reliably use a debit card and read the fine print, Consumers can out-earn a savings account — otherwise Alliant is simpler.",
     "faqs": [
        {"q": "How does rewards checking work at Consumers?", "a": "You earn a high APY on balances up to a cap if you meet monthly conditions like a set number of debit transactions, direct deposit, and e-statements. Miss them and the rate drops for that cycle."},
        {"q": "Can anyone join Consumers Credit Union?", "a": "Yes — anyone in the US can join, typically via a small one-time membership/association step handled at account opening."}]},
    {"a": "penfed", "b": "dcu", "hint": "Open-membership all-rounders for everyday banking",
     "intro": "PenFed and DCU (Digital Federal Credit Union) are both open to anyone in the US and both make solid everyday banking homes. They're commonly cross-shopped by people starting fresh.",
     "pick_a": "you want stronger certificate and mortgage rates and a somewhat larger footprint. PenFed leans rate-competitive on big-ticket products.",
     "pick_b": "you're building a savings habit or financing a car and want a beginner-friendly setup. DCU is known for accessible products and a starter-friendly savings account.",
     "bottom_line": "PenFed is the better pick if certificates or a mortgage are on your radar; DCU shines for everyday banking and first-time savers. Both are genuinely open to everyone, so join whichever fits your near-term goal — or both.",
     "faqs": [
        {"q": "Can anyone join DCU?", "a": "Yes. DCU offers membership to anyone in the US through participating organizations you can join at account opening, so no specific employer is required."},
        {"q": "Which is better for a car loan?", "a": "Both are competitive; DCU is a popular auto lender and PenFed also prices well. Get pre-approved at both and compare the APR."}]},
    {"a": "bethpage", "b": "alliant", "hint": "Nationwide rate shoppers' favorites",
     "intro": "Bethpage and Alliant both attract nationwide rate shoppers. Bethpage is a large New York-based credit union with broad membership; Alliant is digital-first and open to all.",
     "pick_a": "you want frequently competitive CD specials and a credit union that still maintains a meaningful branch presence (on Long Island) alongside nationwide membership.",
     "pick_b": "you prefer a fully digital experience centered on a strong savings rate and no fees.",
     "bottom_line": "Bethpage tends to win for CD shoppers and those who like having branches somewhere; Alliant wins for digital-only savers. Both accept members nationwide, so it comes down to product fit.",
     "faqs": [
        {"q": "Can anyone join Bethpage?", "a": "Yes — Bethpage offers membership to anyone in the US by opening a savings account, with no New York residency requirement."},
        {"q": "Which has better CD rates?", "a": "Bethpage is known for aggressive CD specials, but rates change frequently — check both before locking in."}]},
    {"a": "connexus", "b": "alliant", "hint": "Nationwide rate maximizers with larger balances",
     "intro": "Connexus and Alliant are both open-to-anyone credit unions popular with people optimizing for yield. Connexus is known for high-balance rewards checking and CDs.",
     "pick_a": "you carry a larger checking balance and will meet rewards-checking requirements — Connexus rewards that with a high rate on a sizable balance cap.",
     "pick_b": "you want a simpler high-yield savings setup without monthly conditions.",
     "bottom_line": "Connexus pays off for engaged users with bigger balances who'll meet monthly criteria; Alliant is the lower-effort choice. Both join nationwide, so pick based on how hands-on you want to be.",
     "faqs": [
        {"q": "Is Connexus open to everyone?", "a": "Yes. Anyone in the US can join Connexus, typically through a one-time association membership handled during signup."},
        {"q": "Which is less work?", "a": "Alliant — its savings rate doesn't require monthly debit-card or direct-deposit conditions the way rewards checking does."}]},
    {"a": "navy-federal", "b": "secu-north-carolina", "hint": "Two of the largest, most-loved credit unions",
     "intro": "Navy Federal and SECU (State Employees' Credit Union of North Carolina) are two of the largest and most highly regarded credit unions in America — but they serve very different fields of membership.",
     "pick_a": "you have a military or DoD connection. Navy Federal's nationwide military focus and benefits are tailored to that community.",
     "pick_b": "you're a North Carolina state employee or family member. SECU is famous for low fees, member-first culture, and a dense branch network across North Carolina.",
     "bottom_line": "These rarely actually compete for the same person — eligibility usually decides it. Both are model credit unions; if you qualify for either, it's an easy yes. If you qualify for neither, see our anyone-can-join list.",
     "faqs": [
        {"q": "Can anyone join SECU North Carolina?", "a": "No. SECU serves North Carolina state employees, certain public workers, and their family members. It is not open to the general public."},
        {"q": "Which has lower fees?", "a": "SECU is renowned for an exceptionally low-fee, member-first approach. Navy Federal is also competitive, with benefits geared to the military community."}]},
    {"a": "becu", "b": "schoolsfirst", "hint": "West Coast giants compared",
     "intro": "BECU (Washington) and SchoolsFirst (California) are two of the largest credit unions on the West Coast, each dominant in its home state.",
     "pick_a": "you live or work in Washington (or parts of the Pacific Northwest). BECU offers free checking, broad community membership, and a large local network.",
     "pick_b": "you're a California school employee or family member. SchoolsFirst is built around the education community and consistently rates highly for service.",
     "bottom_line": "Geography and eligibility decide this one: BECU for the Pacific Northwest, SchoolsFirst for California educators. Both are top-tier within their fields of membership.",
     "faqs": [
        {"q": "Can anyone join BECU?", "a": "Largely yes for Washington-state residents and some neighboring areas — BECU has a broad community charter, though it isn't a nationwide anyone-can-join credit union."},
        {"q": "Who can join SchoolsFirst?", "a": "School employees in California and their family members. It's not open to the general public."}]},
    {"a": "lake-michigan", "b": "consumers", "hint": "Rewards-checking heavyweights",
     "intro": "Lake Michigan Credit Union and Consumers Credit Union are both known for high-yield rewards checking and both accept members nationwide. This is the matchup for rate-chasers who want yield on their checking balance.",
     "pick_a": "you want a high rewards-checking rate from a large, full-service credit union with a strong Midwest branch presence. Lake Michigan's Max Checking is a long-time favorite.",
     "pick_b": "you want one of the highest rewards-checking rates available and will meet the monthly requirements. Consumers is aggressive on rate.",
     "bottom_line": "Both can out-earn a savings account if you meet the monthly criteria. Compare the current rate, balance caps, and exact requirements — they shift over time — and pick whichever pays more on your typical balance. Both join nationwide.",
     "faqs": [
        {"q": "Can I join Lake Michigan Credit Union from any state?", "a": "Yes — anyone in the US can join via a small one-time donation to its associated foundation, handled at account opening."},
        {"q": "What's the catch with rewards checking?", "a": "You only earn the headline rate if you meet monthly conditions (debit transactions, direct deposit, e-statements) and only up to a balance cap. Above the cap, the rate drops sharply."}]},
    {"a": "first-tech", "b": "penfed", "hint": "Open-membership lenders head to head",
     "intro": "First Tech and PenFed are both open to anyone in the US and both offer full lending lineups. They're a common cross-shop for people who want financing plus solid deposit rates.",
     "pick_a": "you want a wide range of loans and a tech-industry-rooted credit union with specialty products and a modern digital stack.",
     "pick_b": "you want strong certificate and mortgage rates from a large, established institution with some branch access.",
     "bottom_line": "PenFed tends to lead on certificate and mortgage rates; First Tech offers broader lending variety and a polished digital experience. Both are open to everyone, so let your specific product need break the tie.",
     "faqs": [
        {"q": "Do I need a tech job to join First Tech?", "a": "No. Despite the name, First Tech is open to anyone in the US through qualifying associations you can join at signup."},
        {"q": "Which is better for a mortgage?", "a": "PenFed is frequently competitive on mortgage rates; First Tech also lends broadly. Compare Loan Estimates from both."}]},
]

GLOSSARY = [
    ("share-account", "Share account", "A credit union's basic savings account. The small balance in it (often $5) represents your ownership 'share' in the cooperative. Functionally it works like a bank savings account and is NCUA insured."),
    ("share-draft", "Share draft account", "The credit union term for a checking account. 'Share draft' is the technical name; most credit unions just call it checking."),
    ("dividend", "Dividend", "What a credit union calls the interest it pays on deposits. Because members are owners, earnings are distributed as dividends rather than 'interest,' though the practical effect is the same."),
    ("field-of-membership", "Field of membership", "The group of people a credit union is legally allowed to serve, defined in its charter — based on employer, community (geographic area), or association. You must fall within it to join."),
    ("ncua", "NCUA", "The National Credit Union Administration, the federal agency that charters and regulates federal credit unions and runs the insurance fund that protects member deposits up to $250,000."),
    ("ncusif", "NCUSIF", "The National Credit Union Share Insurance Fund — the NCUA-managed fund, backed by the full faith and credit of the US government, that insures deposits at federally insured credit unions."),
    ("share-certificate", "Share certificate", "A credit union's version of a certificate of deposit (CD). You commit funds for a set term in exchange for a fixed dividend rate; early withdrawal usually forfeits some earnings."),
    ("co-op-network", "CO-OP / shared branching", "Cooperative networks that let credit union members use thousands of other credit unions' branches and ATMs nationwide as if they were their own — offsetting smaller individual branch networks."),
    ("rewards-checking", "Rewards checking", "A checking account paying a high APY on balances up to a cap, provided you meet monthly requirements such as a minimum number of debit transactions, direct deposit, and electronic statements."),
    ("charter", "Charter (federal vs state)", "The license under which a credit union operates. Federal charters are regulated by the NCUA; state charters by a state regulator. Both are typically NCUA insured."),
    ("membership-share", "Membership share", "The small required deposit (commonly $5) that establishes and maintains your ownership stake. It usually must stay in your account while you're a member."),
    ("not-for-profit", "Not-for-profit cooperative", "A credit union's structure: owned by members rather than shareholders, returning earnings to members through better rates and lower fees instead of paying outside investors."),
    ("apy", "APY", "Annual Percentage Yield — the real rate of return on a deposit account over a year, including compounding. Use it to compare savings, money market, and certificate offers."),
    ("apr", "APR", "Annual Percentage Rate — the yearly cost of borrowing, including certain fees. Use it to compare loans and credit cards across lenders."),
    ("loan-rate-cap", "Loan rate cap (18%)", "A federal rule capping the interest rate federal credit unions can charge on most loans (currently 18%), a consumer protection banks aren't subject to."),
    ("chexsystems", "ChexSystems", "A reporting system many institutions check when you open a deposit account, tracking prior account closures and overdrafts. A review here doesn't affect your credit score."),
]

env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=False)

data = json.loads((ROOT / "data" / "creditunions.json").read_text())
CUS = data["credit_unions"]
META = data["meta"]
FULL = [c for c in CUS if c["tier"] == "full"]
ACJ = [c for c in CUS if c["fom"]["anyone_can_join"]]

# Separate rates data layer (updated on its own cadence).
RATES_DATA = json.loads((ROOT / "data" / "rates.json").read_text())
RATES = RATES_DATA["rates"]
RATES_AS_OF = RATES_DATA["meta"]["as_of"]
RATES_DISCLAIMER = RATES_DATA["meta"]["disclaimer"]
for c in CUS:
    c["rates"] = RATES.get(c["slug"])
RATED = [c for c in CUS if c["rates"]]
# Lowest representative new-auto APR among rated CUs, for the calculator default.
CALC_DEFAULT_APR = min((c["rates"]["auto_new_apr"] for c in RATED), default=5.49)
MTG_DEFAULT_APR = min((c["rates"]["mortgage_30_apr"] for c in RATED), default=6.50)

# Rate history layer -> per-CU series + sparkline + trend arrows.
HIST = json.loads((ROOT / "data" / "rate_history.json").read_text())
HIST_SNAPS = HIST["snapshots"]
HIST_TRACKED = HIST["meta"]["tracked_fields"]


def _sparkline(series, lower_is_better=False, w=88, h=24, pad=3):
    """Tiny inline SVG sparkline from a numeric series."""
    if not series or len(series) < 2:
        return ""
    lo, hi = min(series), max(series)
    rng = (hi - lo) or 1
    n = len(series)
    pts = []
    for i, v in enumerate(series):
        x = pad + i * (w - 2 * pad) / (n - 1)
        y = h - pad - (v - lo) / rng * (h - 2 * pad)
        pts.append(f"{x:.1f},{y:.1f}")
    last_up = series[-1] >= series[0]
    good = (not last_up) if lower_is_better else last_up
    color = "#2f8d4e" if good else "#c2592b"
    cx, cy = pts[-1].split(",")
    return (
        f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-hidden="true">'
        f'<polyline fill="none" stroke="{color}" stroke-width="1.6" '
        f'stroke-linecap="round" stroke-linejoin="round" points="{" ".join(pts)}"/>'
        f'<circle cx="{cx}" cy="{cy}" r="2" fill="{color}"/></svg>'
    )


def _trend(series, lower_is_better=False):
    """Arrow + delta vs the previous snapshot."""
    if not series or len(series) < 2:
        return ""
    delta = series[-1] - series[-2]
    if abs(delta) < 0.005:
        return '<span class="trend trend-flat" title="No change">→</span>'
    up = delta > 0
    good = (not up) if lower_is_better else up
    cls = "trend-up" if good else "trend-down"
    arrow = "▲" if up else "▼"
    return f'<span class="trend {cls}" title="{delta:+.2f} vs prior">{arrow} {abs(delta):.2f}</span>'


for c in RATED:
    series = {}
    for f in HIST_TRACKED:
        vals = [s["rates"].get(c["slug"], {}).get(f) for s in HIST_SNAPS]
        vals = [v for v in vals if v is not None]
        vals.append(c["rates"][f])  # current point
        series[f] = vals
    lower = {"auto_new_apr"}
    c["rate_series"] = series
    c["spark"] = {f: _sparkline(series[f], f in lower) for f in HIST_TRACKED}
    c["trend"] = {f: _trend(series[f], f in lower) for f in HIST_TRACKED}

# Ratings layer -> weighted overall + star SVG + factor breakdown.
RATINGS_DATA = json.loads((ROOT / "data" / "ratings.json").read_text())
RATINGS = RATINGS_DATA["ratings"]
RATING_WEIGHTS = RATINGS_DATA["meta"]["weights"]
RATING_LABELS = RATINGS_DATA["meta"]["factor_labels"]


def _rating_word(score):
    if score >= 4.5:
        return "Excellent"
    if score >= 4.0:
        return "Very good"
    if score >= 3.5:
        return "Good"
    return "Fair"


def _stars(score, w=96, h=18):
    """Fractional star row as inline SVG (gold fill clipped to score/5)."""
    star = ("m9 1 2.36 4.78 5.28.77-3.82 3.72.9 5.25L9 13.9 4.28 16.3l.9-5.25"
            "L1.36 7.33l5.28-.77z")
    sw = w / 5
    pct = max(0.0, min(1.0, score / 5.0)) * w
    gray = "".join(
        f'<path transform="translate({i*sw},0) scale({sw/18:.4f})" d="{star}" fill="#dcd3c2"/>'
        for i in range(5))
    gold = "".join(
        f'<path transform="translate({i*sw},0) scale({sw/18:.4f})" d="{star}" fill="#d9a441"/>'
        for i in range(5))
    return (
        f'<svg class="stars" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-label="{score} out of 5 stars">{gray}'
        f'<clipPath id="c{int(score*10)}_{int(pct)}"><rect x="0" y="0" width="{pct:.1f}" height="{h}"/></clipPath>'
        f'<g clip-path="url(#c{int(score*10)}_{int(pct)})">{gold}</g></svg>'
    )


for c in RATED:
    r = RATINGS.get(c["slug"])
    if not r:
        c["rating"] = None
        continue
    overall = round(sum(r[f] * RATING_WEIGHTS[f] for f in RATING_WEIGHTS), 1)
    c["rating"] = {
        "overall": overall,
        "word": _rating_word(overall),
        "stars": _stars(overall),
        "factors": [{"key": f, "label": RATING_LABELS[f], "score": r[f],
                     "pct": round(r[f] / 5 * 100)} for f in RATING_WEIGHTS],
    }

# Full-tier CUs ranked by overall rating (drives the best-of ordering).
FULL_RANKED = sorted(
    FULL, key=lambda c: -(c["rating"]["overall"] if c.get("rating") else 0))


def _members_num(v):
    """Accept int or string member count -> int (for sorting)."""
    if isinstance(v, (int, float)):
        return int(v)
    t = str(v).lower().replace("+", "").replace(",", "").strip()
    mult = 1
    if "million" in t:
        mult, t = 1_000_000, t.replace("million", "").strip()
    try:
        return int(float(t) * mult)
    except ValueError:
        return 0


def _members_fmt(n):
    """14000000 -> '14 million+'; 2900000 -> '2.9 million+'; 500000 -> '500,000+'."""
    if n >= 1_000_000:
        m = n / 1_000_000
        return (f"{m:.0f} million+" if abs(m - round(m)) < 0.05 else f"{m:.1f} million+")
    return f"{n:,}+"


for c in CUS:
    c["members_num"] = _members_num(c["members_approx"])
    c["members_fmt"] = _members_fmt(c["members_num"])

# Directory order: A–Z by name.
DIRECTORY = sorted(CUS, key=lambda c: c["name"].lower())

PAGES = []  # (url_path, priority) for sitemap


def org_schema():
    return {
        "@type": "Organization",
        "name": "Credit Union Reviewer",
        "url": BASE_URL,
    }


def breadcrumb_schema(crumbs):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": c["name"],
             "item": BASE_URL + "/" + c["href"].replace("index.html", "")}
            for i, c in enumerate(crumbs)
        ],
    }


def article_schema(title, desc, url, rating=None, item_name=None):
    s = {
        "@context": "https://schema.org",
        "@type": "Review" if rating else "Article",
        "headline": title,
        "description": desc,
        "url": url,
        "dateModified": VERIFIED_DATE,
        "author": {"@type": "Person", "name": "Nathan Blake"},
        "publisher": org_schema(),
    }
    if rating:
        s["itemReviewed"] = {"@type": "BankOrCreditUnion", "name": item_name}
        s["reviewRating"] = {"@type": "Rating", "ratingValue": rating,
                             "bestRating": 5, "worstRating": 1}
    return s


def faq_schema(faqs):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": f["q"],
             "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
            for f in faqs
        ],
    }


def render(template, out_path, *, title, meta_description, depth, schemas=None,
           breadcrumbs=None, og_type="website", **ctx):
    url = BASE_URL + "/" + (out_path.replace("index.html", "") if out_path != "index.html" else "")
    rel = "../" * depth
    schema_json = json.dumps(schemas if len(schemas or []) != 1 else schemas[0], ensure_ascii=False) if schemas else json.dumps(org_schema())
    html = env.get_template(template).render(
        title=title, meta_description=meta_description, canonical=url,
        rel=rel, last_verified=VERIFIED_DATE, schema_json=schema_json,
        build_version=BUILD_VERSION, update_frequency=UPDATE_FREQUENCY,
        rates_as_of=RATES_AS_OF, calc_default_apr=f"{CALC_DEFAULT_APR:.2f}",
        mtg_default_apr=f"{MTG_DEFAULT_APR:.2f}",
        breadcrumbs=breadcrumbs, og_type=og_type, **TOKENS, **CTAS, **ctx,
    )
    out = DIST / out_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    PAGES.append(out_path.replace("index.html", ""))


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copytree(ROOT / "static", DIST / "static")

    by_slug = {c["slug"]: c for c in CUS}

    # Prepare comparison matchups up front so review pages can link them.
    matchups = [m for m in MATCHUPS if not m.get("skip")]
    seen, uniq = set(), []
    for m in matchups:
        key = frozenset((m["a"], m["b"]))
        if key in seen:
            continue
        seen.add(key)
        m["slug"] = f"{m['a']}-vs-{m['b']}"
        m["a_name"], m["b_name"] = by_slug[m["a"]]["name"], by_slug[m["b"]]["name"]
        uniq.append(m)
    matchups = uniq
    cu_to_matchups = {}
    for m in matchups:
        cu_to_matchups.setdefault(m["a"], []).append({"slug": m["slug"], "other": by_slug[m["b"]]["name"]})
        cu_to_matchups.setdefault(m["b"], []).append({"slug": m["slug"], "other": by_slug[m["a"]]["name"]})


    # ---------- Homepage ----------
    home_schema = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Credit Union Reviewer",
        "url": BASE_URL,
        "publisher": org_schema(),
    }
    render(
        "home.html", "index.html",
        title="Credit Union Reviewer — Honest Reviews of 100 US Credit Unions (2026)",
        meta_description="Plain-English reviews of 100 US credit unions: who can actually join, real pros and cons, and the credit unions anyone in America can join. Updated 2026.",
        depth=0, schemas=[home_schema],
        cu_count=len(CUS), acj_count=len(ACJ),
        acj_featured=[c for c in ACJ if c["slug"] in ("penfed", "alliant", "consumers", "blue-fcu")],
        top_picks=FULL_RANKED[:8],
    )

    # ---------- Best credit unions ----------
    best_faqs = [
        {"q": "What is the #1 credit union in America?",
         "a": "By size, Navy Federal Credit Union is by far the largest US credit union, with over 13 million members. 'Best' depends on what you need: PenFed and Alliant lead for nationwide accessibility, while regional standouts like SECU North Carolina or BECU may be stronger if you qualify."},
        {"q": "Are credit unions safer than banks?",
         "a": "They're equally safe. Federally insured credit unions are covered by the NCUA up to $250,000 per share owner, per institution, per ownership category — the same protection FDIC insurance gives bank deposits, backed by the US government."},
        {"q": "Can I join a credit union if I don't qualify through work or location?",
         "a": "Usually yes. Many credit unions — including PenFed, Alliant, and over a dozen others we review — let anyone join through a one-time charity donation of $5–$25 or a free association membership."},
        {"q": "Do credit unions really have better rates than banks?",
         "a": "On average, yes. Credit unions consistently beat bank averages on savings, CDs, auto loans, and credit card rates because they return profits to members. The best online banks are competitive on savings rates, though, so it pays to compare both."},
    ]
    url = BASE_URL + "/best-credit-unions/"
    render(
        "best.html", "best-credit-unions/index.html",
        title="The 26 Best Credit Unions of 2026, Ranked | Credit Union Reviewer",
        meta_description="We ranked America's best credit unions on rates, fees, accessibility, and digital banking. Includes which ones anyone in the US can join. Verified 2026.",
        depth=1, og_type="article",
        schemas=[article_schema("The Best Credit Unions of 2026",
                                "America's best credit unions, ranked and reviewed.", url),
                 faq_schema(best_faqs),
                 breadcrumb_schema([{"name": "Home", "href": ""},
                                    {"name": "Best Credit Unions", "href": "best-credit-unions/"}])],
        breadcrumbs=[{"name": "Home", "href": "index.html"},
                     {"name": "Best Credit Unions", "href": "best-credit-unions/index.html"}],
        ranked=FULL_RANKED, acj_count=len(ACJ), faqs=best_faqs,
    )

    # ---------- Anyone can join ----------
    acj_faqs = [
        {"q": "Is joining a credit union through a charity donation legitimate?",
         "a": "Completely. Federal credit union rules allow membership through affiliated associations, and the donations fund real nonprofits. The credit union usually processes the donation during account opening — it's a standard, regulator-approved practice."},
        {"q": "What's the cheapest credit union anyone can join?",
         "a": "Blue Federal Credit Union's path is among the cheapest: a one-time $5 donation to the Blue Foundation. Several others, including PenFed, currently require no donation at all — just open a share account."},
        {"q": "Do I have to keep donating to stay a member?",
         "a": "No. The donation is one-time. Once you're a member, you stay a member as long as you keep your share account open (usually a $5 minimum balance), even if you move or change jobs."},
        {"q": "Will joining multiple credit unions hurt my credit?",
         "a": "Opening deposit accounts generally doesn't affect your credit score. Some credit unions run a soft credit check or ChexSystems review at account opening, which doesn't impact your score. Applying for loans or credit cards is a different story — those involve hard inquiries."},
    ]
    url = BASE_URL + "/anyone-can-join/"
    render(
        "anyone.html", "anyone-can-join/index.html",
        title=f"{len(ACJ)} Credit Unions Anyone Can Join in 2026 (Verified List)",
        meta_description="The verified list of credit unions anyone in the US can join — open membership through small one-time donations of $5–$25. No employer or location requirements.",
        depth=1, og_type="article",
        schemas=[article_schema("Credit Unions Anyone Can Join",
                                "Verified open-membership credit unions in the US.", url),
                 faq_schema(acj_faqs),
                 breadcrumb_schema([{"name": "Home", "href": ""},
                                    {"name": "Anyone Can Join", "href": "anyone-can-join/"}])],
        breadcrumbs=[{"name": "Home", "href": "index.html"},
                     {"name": "Anyone Can Join", "href": "anyone-can-join/index.html"}],
        acj=ACJ, faqs=acj_faqs,
    )

    # ---------- CU vs bank ----------
    vs_faqs = [
        {"q": "Is my money safer in a bank or a credit union?",
         "a": "Equally safe. NCUA insurance (credit unions) and FDIC insurance (banks) both protect up to $250,000 per person, per institution, per ownership category, and both are backed by the US government."},
        {"q": "Why are credit union rates better?",
         "a": "Credit unions are not-for-profit cooperatives owned by their members. Money that a bank would pay to shareholders gets returned to members as higher deposit rates, lower loan rates, and lower fees."},
        {"q": "What are the downsides of credit unions?",
         "a": "The honest ones: membership eligibility requirements (though often easy to meet), technology that can lag the biggest banks, and smaller branch networks — partially offset by shared branching, which gives members access to thousands of cooperating branches nationwide."},
        {"q": "Can a business use a credit union?",
         "a": "Many credit unions offer business checking, lending, and merchant services — often with lower fees than banks. Larger commercial needs may still be better served by a bank with a bigger treasury-management operation."},
    ]
    url = BASE_URL + "/credit-union-vs-bank/"
    render(
        "vsbank.html", "credit-union-vs-bank/index.html",
        title="Credit Union vs Bank: An Honest 2026 Comparison",
        meta_description="Credit unions beat banks on rates and fees; banks win on tech and convenience. An honest side-by-side comparison, including when a bank is the better choice.",
        depth=1, og_type="article",
        schemas=[article_schema("Credit Union vs Bank", "An honest comparison.", url),
                 faq_schema(vs_faqs),
                 breadcrumb_schema([{"name": "Home", "href": ""},
                                    {"name": "Credit Union vs Bank", "href": "credit-union-vs-bank/"}])],
        breadcrumbs=[{"name": "Home", "href": "index.html"},
                     {"name": "Credit Union vs Bank", "href": "credit-union-vs-bank/index.html"}],
        acj_count=len(ACJ), faqs=vs_faqs,
    )

    # ---------- How to join ----------
    join_faqs = [
        {"q": "How much does it cost to join a credit union?",
         "a": "Typically $5–$25: a small share deposit (usually $5) that establishes your ownership stake, plus, at some credit unions, a one-time association donation. The share deposit stays in your savings account and is yours."},
        {"q": "Can I belong to more than one credit union?",
         "a": "Yes, and many people do — for example, one local credit union for branch access and one open-membership credit union for its rates. There's no limit."},
        {"q": "Do I lose membership if I change jobs or move?",
         "a": "Almost never. Most credit unions follow 'once a member, always a member' — as long as you keep your share account open, you remain a member for life."},
        {"q": "Can family members join through me?",
         "a": "At most credit unions, yes. Immediate family — and at some, anyone in your household — becomes eligible once you're a member. Eligibility often extends across generations."},
    ]
    url = BASE_URL + "/how-to-join/"
    render(
        "howtojoin.html", "how-to-join/index.html",
        title="How to Join a Credit Union: Field of Membership Explained (2026)",
        meta_description="Field of membership, explained in plain English: employer, community, and association eligibility — plus the donation loophole that lets anyone join a credit union.",
        depth=1, og_type="article",
        schemas=[article_schema("How to Join a Credit Union",
                                "Field of membership explained.", url),
                 faq_schema(join_faqs),
                 breadcrumb_schema([{"name": "Home", "href": ""},
                                    {"name": "How to Join", "href": "how-to-join/"}])],
        breadcrumbs=[{"name": "Home", "href": "index.html"},
                     {"name": "How to Join", "href": "how-to-join/index.html"}],
        acj_count=len(ACJ), faqs=join_faqs,
    )

    # ---------- NCUA ----------
    ncua_faqs = [
        {"q": "Is NCUA insurance as good as FDIC insurance?",
         "a": "Yes — identical dollar coverage ($250,000 per share owner, per insured credit union, per ownership category) and the same backing: the full faith and credit of the US government. No member has ever lost a penny of NCUA-insured funds."},
        {"q": "How do I check if my credit union is NCUA insured?",
         "a": "Use the NCUA's Credit Union Locator at ncua.gov, or look for the official NCUA insurance sign on the credit union's website and branches. Every credit union reviewed on this site is federally insured."},
        {"q": "Are all credit unions federally insured?",
         "a": "Nearly all, but not every single one. A small number of state-chartered credit unions carry private insurance instead of NCUA coverage. Private insurance is not backed by the federal government, so it's worth verifying before opening an account."},
        {"q": "Can I insure more than $250,000 at one credit union?",
         "a": "Yes, through ownership categories. Individual accounts, joint accounts, and certain retirement accounts are insured separately, so a couple using individual plus joint accounts can have $1 million or more fully insured at a single institution."},
    ]
    url = BASE_URL + "/ncua-insurance/"
    render(
        "ncua.html", "ncua-insurance/index.html",
        title="NCUA Insurance Explained: Is Your Money Safe in a Credit Union?",
        meta_description="NCUA vs FDIC insurance compared: both protect $250,000 per person, backed by the US government. How credit union deposit insurance works, in plain English.",
        depth=1, og_type="article",
        schemas=[article_schema("NCUA Insurance Explained",
                                "NCUA vs FDIC, compared in plain English.", url),
                 faq_schema(ncua_faqs),
                 breadcrumb_schema([{"name": "Home", "href": ""},
                                    {"name": "NCUA Insurance", "href": "ncua-insurance/"}])],
        breadcrumbs=[{"name": "Home", "href": "index.html"},
                     {"name": "NCUA Insurance", "href": "ncua-insurance/index.html"}],
        faqs=ncua_faqs,
    )

    # ---------- Reviews (100) ----------
    for cu in CUS:
        path = f"reviews/{cu['slug']}/index.html"
        url = f"{BASE_URL}/reviews/{cu['slug']}/"
        kind = "Review" if cu["tier"] == "full" else "Review & Profile"
        desc = (f"{cu['name']} review: who can join, rates and products, pros and cons, "
                f"and NCUA insurance details. {cu['fom']['easy_path']}")[:158]
        render(
            "review.html", path,
            title=f"{cu['name']} {kind} (2026): Membership, Rates, Pros & Cons",
            meta_description=desc, depth=2, og_type="article",
            schemas=[article_schema(f"{cu['name']} Review", desc, url,
                                    rating=(cu["rating"]["overall"] if cu.get("rating") else None),
                                    item_name=cu["name"]),
                     breadcrumb_schema([{"name": "Home", "href": ""},
                                        {"name": "Reviews", "href": "best-credit-unions/"},
                                        {"name": cu["name"], "href": f"reviews/{cu['slug']}/"}])],
            breadcrumbs=[{"name": "Home", "href": "index.html"},
                         {"name": "Best Credit Unions", "href": "best-credit-unions/index.html"},
                         {"name": cu["name"], "href": f"reviews/{cu['slug']}/index.html"}],
            cu=cu, state_name=STATE_NAMES[cu["hq_state"]],
            comparisons=cu_to_matchups.get(cu["slug"], []),
        )

    # ---------- State pages (50 + index) ----------
    acj_top = [c for c in ACJ if c["slug"] in
               ("penfed", "alliant", "consumers", "blue-fcu", "american-heritage", "dcu")]
    by_state = {}
    for cu in CUS:
        by_state.setdefault(cu["hq_state"], []).append(cu)
    for cus in by_state.values():
        cus.sort(key=lambda c: (c["tier"] != "full", -c.get("assets_b_approx", 0)))

    states_ctx = [{"abbr": ab, "name": STATE_NAMES[ab], "count": len(by_state.get(ab, []))}
                  for ab in sorted(STATE_NAMES, key=lambda a: STATE_NAMES[a])]
    render(
        "state_index.html", "state/index.html",
        title="Best Credit Unions by State (All 50 States) | Credit Union Reviewer",
        meta_description="Find the best credit unions in your state — local standouts plus the open-membership credit unions available everywhere. All 50 states covered.",
        depth=1,
        schemas=[breadcrumb_schema([{"name": "Home", "href": ""},
                                    {"name": "By State", "href": "state/"}])],
        breadcrumbs=[{"name": "Home", "href": "index.html"},
                     {"name": "By State", "href": "state/index.html"}],
        states=states_ctx,
    )

    for ab, name in STATE_NAMES.items():
        local = by_state.get(ab, [])
        path = f"state/{ab.lower()}/index.html"
        url = f"{BASE_URL}/state/{ab.lower()}/"
        desc = (f"The best credit unions in {name} for 2026: "
                + (f"{local[0]['name']} leads our local picks, " if local else "")
                + "plus open-membership credit unions any resident can join.")[:158]
        render(
            "state.html", path,
            title=f"Best Credit Unions in {name} (2026) | Credit Union Reviewer",
            meta_description=desc, depth=2, og_type="article",
            schemas=[article_schema(f"Best Credit Unions in {name}", desc, url),
                     breadcrumb_schema([{"name": "Home", "href": ""},
                                        {"name": "By State", "href": "state/"},
                                        {"name": name, "href": f"state/{ab.lower()}/"}])],
            breadcrumbs=[{"name": "Home", "href": "index.html"},
                         {"name": "By State", "href": "state/index.html"},
                         {"name": name, "href": f"state/{ab.lower()}/index.html"}],
            state_name=name, local_cus=local, acj_top=acj_top,
        )

    # ---------- Simple pages ----------
    simple_pages = {
        "methodology": ("How We Review Credit Unions", True, """
<p>Every credit union on this site is evaluated against the same checklist, by the same reviewer, with no input from the institutions themselves. Here's exactly what we look at.</p>
<h2>The five factors</h2>
<p><strong>1. Deposit rates.</strong> We compare savings, money market, and certificate rates against national credit union and bank averages. We care most about rates on the accounts ordinary members actually use — not promotional teasers with fine-print requirements.</p>
<p><strong>2. Loan pricing.</strong> Auto loans, mortgages, credit cards, and personal loans, compared against market averages. Federal credit unions' 18% rate ceiling on most loans is a real consumer protection, and we note where institutions price well below it.</p>
<p><strong>3. Fees.</strong> Monthly maintenance fees, overdraft charges, ATM policies, and the sneaky stuff — inactivity fees, paper statement charges. Free checking with no minimums earns points; fee-riddled accounts lose them.</p>
<p><strong>4. Membership accessibility.</strong> How easy is it to actually join? Statewide community charters and anyone-can-join paths score high. We verify every eligibility claim against the credit union's own membership page and record the date.</p>
<p><strong>5. Digital experience.</strong> App store ratings, online account opening, remote deposit, and digital wallet support. Credit unions are co-ops, not tech companies — but in 2026 a usable app is table stakes.</p>
<h2>The five factors</h2>
<p>Every credit union we review in full gets a score from 1 to 5 on each of five factors. The overall rating is a weighted average, shown as stars and a number on the review and in our comparison tables:</p>
<p><strong>Rates (30%).</strong> Deposit APYs (savings, money market, certificates) and loan APRs versus national averages. The single heaviest factor, because rates are where the member-owned model shows up in your pocket.</p>
<p><strong>Fees (20%).</strong> Monthly maintenance, overdraft, ATM, and the sneaky stuff. Free checking with no minimums scores high.</p>
<p><strong>Membership access (20%).</strong> How easy it is to actually join. Anyone-can-join and statewide community charters score high; narrow employer-only fields score lower — a great credit union you can't join isn't much use to you.</p>
<p><strong>Digital experience (15%).</strong> App ratings, online account opening, remote deposit, and digital wallet support.</p>
<p><strong>Products (15%).</strong> Breadth and quality of the lineup — checking, savings, lending, business services.</p>
<p>We publish the per-factor breakdown on every review so you can see exactly where a score comes from and weight it for your own priorities — someone who only wants a CD can ignore the digital score, for instance.</p>
<p class="note">Scores are editorial assessments, not the credit unions' own claims, and no institution can pay to raise one. They're anchored to the rate and fee data we track and re-checked when that data changes.</p>
<h2>What we don't do</h2>
<p>We don't accept payment for placement in our rankings. We don't let affiliate relationships (disclosed on every page where they exist) influence scores. We don't copy press releases. And we don't pretend to be comprehensive: with over 4,000 credit unions in America, we focus on the 100 most significant and most joinable.</p>
<h2>Verification and updates</h2>
<p>Each data page carries a "last verified" date. Rates change weekly at some institutions, so we treat our rate descriptions as directional and always tell you to confirm current numbers before opening an account. Membership requirements, donation amounts, and fee schedules are re-checked on a rolling basis.</p>
<p>Questions about our process? <a href="../contact/index.html">Contact us</a>.</p>"""),
        "how-we-make-money": ("How We Make Money", True, """
<p>CreditUnionReviewer.com is reader-supported. Full transparency on how this site pays for itself:</p>
<h2>Display advertising</h2>
<p>Most pages carry display ads. Advertisers don't choose where they appear, can't buy placement in our rankings, and have no contact with our editorial process.</p>
<h2>Affiliate partnerships</h2>
<p>A small number of credit unions and online banks offer affiliate programs. When you open an account through one of those links, we may earn a commission — at no cost to you, and frequently with a better signup offer than walking in cold. Affiliate links are disclosed on every page that contains them.</p>
<h2>What money never buys here</h2>
<p>Rankings. Review scores. Pros-and-cons lists. The order of any table. Most credit unions we review — including some of our highest-rated — pay us nothing at all, which is the structural reality of this niche: credit unions are not-for-profits and most don't run affiliate programs. We'd rather recommend the right institution that pays us nothing than the wrong one that pays us well, because this site only works if you trust it.</p>
<h2>What we are not</h2>
<p>We are not financial advisors, and nothing here is individualized financial advice. We're a review publication. For decisions involving significant money, talk to a licensed professional.</p>"""),
        "about": ("About Credit Union Reviewer", False, """
<p>Credit Union Reviewer exists because the credit union industry has a discovery problem: the institutions with the best rates in American consumer finance are also the hardest to figure out. Can you join? What's a field of membership? Is NCUA insurance real insurance? Most financial media skips credit unions entirely because — frankly — there's little affiliate money in covering them. We cover them anyway.</p>
<h2>Who writes this site</h2>
<div class="author-box"><div class="author-avatar">NB</div><div>
<p class="author-name">Nathan Blake, Editor</p>
<p class="author-bio">Nathan has spent a decade writing about consumer banking — fee schedules, rate sheets, deposit insurance rules, and the fine print most people reasonably never read. He's a credit union member himself, reviews every institution on this site against the same five-factor checklist, and maintains the verification dates on every data page. He is not a financial advisor, and this site doesn't give individualized financial advice.</p>
</div></div>
<h2>What we believe</h2>
<p>Three things. Credit unions are underrated and under-covered. Membership eligibility is far easier than most people assume — and telling people exactly how to get in is the single most useful thing a site like this can do. And honest coverage means saying when a bank is the better choice, which we do.</p>
<p>See our <a href="../methodology/index.html">methodology</a> and <a href="../how-we-make-money/index.html">how we make money</a> for the details, or <a href="../contact/index.html">get in touch</a>.</p>"""),
        "contact": ("Contact Us", False, """
<p>Spotted an outdated rate, a changed membership requirement, or an error in a review? That's exactly the kind of message we want. We read everything, prioritize data corrections, and update pages with a fresh verification date.</p>
<form class="contact-form" action="{{FORM_ACTION}}" method="POST">
  <p><label for="name">Name</label><br><input type="text" id="name" name="name" required style="width:100%;padding:0.6rem;border:1px solid var(--line);border-radius:8px;font-family:inherit;"></p>
  <p><label for="email">Email</label><br><input type="email" id="email" name="email" required style="width:100%;padding:0.6rem;border:1px solid var(--line);border-radius:8px;font-family:inherit;"></p>
  <p><label for="message">Message</label><br><textarea id="message" name="message" rows="6" required style="width:100%;padding:0.6rem;border:1px solid var(--line);border-radius:8px;font-family:inherit;"></textarea></p>
  <p><button type="submit" class="btn btn-primary" style="border:none;cursor:pointer;">Send message</button></p>
</form>
<p class="note">We can't provide individualized financial advice, account support for any credit union, or assistance with membership applications — contact the institution directly for those.</p>"""),
        "privacy": ("Privacy Policy", False, """
<p><em>Effective date: June 7, 2026</em></p>
<p>This Privacy Policy describes how CreditUnionReviewer.com ("we," "us") handles information when you visit this site.</p>
<h2>Information we collect</h2>
<p><strong>Analytics data.</strong> We use Google Analytics to understand aggregate site usage: pages visited, approximate location, device type, and referral source. This data is collected via cookies and similar technologies and does not directly identify you.</p>
<p><strong>Contact form submissions.</strong> If you contact us, we receive the name, email address, and message you provide. We use it only to respond to you.</p>
<p><strong>Advertising data.</strong> Third-party advertising partners may use cookies to serve ads based on your prior visits to this and other websites. These partners have their own privacy policies governing their data use.</p>
<h2>What we don't collect</h2>
<p>We never ask for or store financial account numbers, Social Security numbers, or credit information. Any site claiming to be us and requesting such information is fraudulent. When you click through to a credit union or bank, their privacy policy governs from that point.</p>
<h2>Cookies and choices</h2>
<p>You can block or delete cookies through your browser settings. You can opt out of Google Analytics with Google's browser add-on, and out of personalized advertising at aboutads.info/choices.</p>
<h2>Third-party links</h2>
<p>This site links to credit unions, banks, and other external sites. We're not responsible for their content or privacy practices.</p>
<h2>Children</h2>
<p>This site is not directed at children under 13, and we do not knowingly collect their information.</p>
<h2>Changes and contact</h2>
<p>We may update this policy; the effective date above reflects the latest revision. Questions: use our <a href="../contact/index.html">contact form</a>.</p>"""),
        "terms": ("Terms of Use", False, """
<p><em>Effective date: June 7, 2026</em></p>
<h2>Acceptance</h2>
<p>By using CreditUnionReviewer.com, you agree to these terms. If you don't agree, please don't use the site.</p>
<h2>Not financial advice</h2>
<p>All content on this site is for general informational and editorial purposes only. We are not financial advisors, brokers, or fiduciaries, and nothing here constitutes individualized financial, legal, or tax advice. Decisions about where to bank, save, or borrow are yours alone; consult a licensed professional for advice specific to your situation.</p>
<h2>Accuracy and rates</h2>
<p>We work hard to keep information current and date-stamp our verifications, but rates, fees, membership requirements, and product terms change constantly and without notice to us. The credit union's or bank's own website and disclosures always control. We make no warranty that any information on this site is accurate, complete, or current at the moment you read it.</p>
<h2>Affiliate relationships</h2>
<p>Some links are affiliate links, disclosed on the pages where they appear and described in <a href="../how-we-make-money/index.html">How We Make Money</a>.</p>
<h2>Intellectual property</h2>
<p>Site content is owned by us or licensed to us. You may share links and brief quotations with attribution; republishing substantial portions requires written permission. Credit union names and logos belong to their respective owners; their appearance here is editorial and implies no endorsement in either direction.</p>
<h2>Limitation of liability</h2>
<p>To the maximum extent permitted by law, we are not liable for any damages arising from your use of this site or reliance on its content, including decisions made about financial products.</p>
<h2>Changes</h2>
<p>We may revise these terms at any time by updating this page. Continued use after changes constitutes acceptance.</p>"""),
        "cookies": ("Cookie Policy", False, """
<p><em>Effective date: June 7, 2026</em></p>
<p>This Cookie Policy explains how CreditUnionReviewer.com uses cookies and similar technologies, and how you can control them. It supplements our <a href="../privacy/index.html">Privacy Policy</a>.</p>
<h2>What cookies are</h2>
<p>Cookies are small text files a website stores on your device. They let a site remember actions and preferences (like your cookie choice) and help us understand how the site is used. Similar technologies include local storage and pixels.</p>
<h2>The cookies we use</h2>
<p><strong>Essential.</strong> A single small entry remembers whether you accepted or declined non-essential cookies, so we don't ask again on every page. This is required for the site to honor your choice and is always active.</p>
<p><strong>Analytics (optional).</strong> If you accept, we use Google Analytics (GA4) to measure aggregate, de-identified usage — pages viewed, approximate region, device type, referral source — with IP anonymization enabled. These cookies do not load unless you accept.</p>
<p><strong>Advertising (optional).</strong> Pages may display ads, and advertising partners may set cookies to limit repetition and measure performance. Where required, these load only with your consent. Affiliate links may set a cookie to attribute a referral if you open an account; this carries no extra cost to you.</p>
<h2>Your choices</h2>
<p>When you first visit, a banner lets you <strong>accept</strong> or <strong>decline</strong> non-essential cookies. Analytics will not run unless you accept. You can change your mind at any time by clearing this site's data in your browser, which will make the banner reappear.</p>
<p>You can also block or delete cookies in your browser settings, opt out of Google Analytics with Google's <a href="https://tools.google.com/dlpage/gaoptout">browser add-on</a>, and manage personalized advertising at <a href="https://optout.aboutads.info">aboutads.info/choices</a> and <a href="https://www.youronlinechoices.eu">youronlinechoices.eu</a>. If you are in a region with "Do Not Sell or Share My Personal Information" rights, declining non-essential cookies covers that choice on this site.</p>
<h2>Changes</h2>
<p>We may update this policy; the effective date above reflects the latest revision. Questions: use our <a href="../contact/index.html">contact form</a>.</p>
<p class="note">This is a general, good-faith cookie notice. If you operate in a strict-consent jurisdiction (EU/UK) or your ad network requires a certified consent management platform, pair this with an IAB-TCF-compliant CMP before relying on it for legal compliance.</p>"""),
        "disclaimer": ("Disclaimer", False, """
<p><em>Effective date: June 7, 2026</em></p>
<h2>Not financial advice</h2>
<p>CreditUnionReviewer.com is an independent publisher of consumer-banking information. Everything on this site is general, editorial information — not individualized financial, legal, tax, or investment advice. We are not a credit union, bank, broker, or financial advisor, and we have no fiduciary relationship with you. Decisions about where to bank, save, or borrow are yours; for advice specific to your situation, consult a licensed professional.</p>
<h2>Accuracy and rates</h2>
<p>We work to keep information current and stamp our pages with verification dates, but rates, APYs, APRs, fees, membership requirements, and product terms change frequently and without notice to us. Rate and rating figures shown are representative and for comparison only. The credit union's or bank's own website and disclosures always control. We make no warranty that any information here is accurate, complete, or current at the moment you read it, and ratings reflect our editorial assessment, not a guarantee of any outcome.</p>
<h2>Advertiser disclosure</h2>
<p>This site is reader-supported. We display ads and some links are affiliate links, meaning we may earn a commission — at no cost to you — if you open an account through them. Compensation never determines our rankings, ratings, or which credit unions we cover; many institutions we rate highly pay us nothing. See <a href="../how-we-make-money/index.html">How We Make Money</a> for full detail.</p>
<h2>Deposit insurance</h2>
<p>Federally insured credit unions are insured by the NCUA up to $250,000 per share owner, per insured credit union, per account ownership category. A small number of credit unions carry private (non-federal) insurance; verify any institution's status at ncua.gov before relying on coverage.</p>
<h2>Third-party links</h2>
<p>We link to credit unions, banks, and other external sites for your convenience. We don't control and aren't responsible for their content, products, or practices, and a link is not an endorsement.</p>"""),
    }

    for slug, (h1, byline, body) in simple_pages.items():
        # Fill the contact form action from meta.json; if unset, degrade the form
        # to a mailto so no dead/placeholder form (or {{TOKEN}}) ships.
        if "{{FORM_ACTION}}" in body:
            if FORM_ACTION:
                body = body.replace("{{FORM_ACTION}}", FORM_ACTION)
            else:
                body = body.replace(
                    '<form class="contact-form" action="{{FORM_ACTION}}" method="POST">',
                    '<form class="contact-form" action="https://formsubmit.co/el/placeholder" '
                    'method="POST" onsubmit="return false" aria-disabled="true">')
                body = body.replace("{{FORM_ACTION}}", "")
        path = f"{slug}/index.html"
        url = f"{BASE_URL}/{slug}/"
        descs = {
            "methodology": "How Credit Union Reviewer evaluates credit unions: the five-factor checklist, verification process, and what money never buys in our rankings.",
            "how-we-make-money": "Full transparency: how CreditUnionReviewer.com earns revenue through ads and affiliate links — and why money never influences our rankings.",
            "about": "About Credit Union Reviewer: independent, plain-English credit union reviews written for members, not banks. Meet the editor and our editorial principles.",
            "contact": "Contact Credit Union Reviewer — report outdated rates, changed membership requirements, or errors in our reviews.",
            "privacy": "Privacy policy for CreditUnionReviewer.com: what we collect, what we never collect, and your choices.",
            "terms": "Terms of use for CreditUnionReviewer.com, including our not-financial-advice and accuracy disclaimers.",
            "cookies": "Cookie Policy for CreditUnionReviewer.com: the essential, analytics, and advertising cookies we use and how to control them.",
            "disclaimer": "Disclaimer for CreditUnionReviewer.com: not financial advice, rate accuracy, advertiser disclosure, and NCUA insurance notes.",
        }
        render(
            "simple.html", path,
            title=f"{h1} | Credit Union Reviewer",
            meta_description=descs[slug], depth=1,
            schemas=[article_schema(h1, descs[slug], url),
                     breadcrumb_schema([{"name": "Home", "href": ""},
                                        {"name": h1, "href": f"{slug}/"}])],
            breadcrumbs=[{"name": "Home", "href": "index.html"},
                         {"name": h1, "href": f"{slug}/index.html"}],
            page_h1=h1, show_byline=byline, body=body,
        )

    # ---------- Category roundups ----------
    CAT_FAQS = {
        "cd-rates": [
            {"q": "Do credit unions have better CD rates than banks?", "a": "On average, yes. Credit union share certificates have historically out-yielded comparable bank CDs because credit unions return earnings to members. The best online bank CDs are competitive, so compare both before locking in a term."},
            {"q": "Are credit union CDs (share certificates) NCUA insured?", "a": "Yes. Share certificates are insured by the NCUA up to $250,000 per share owner, per credit union, per ownership category — the same protection as a bank CD under FDIC."},
            {"q": "What's an early withdrawal penalty on a credit union CD?", "a": "Pulling money out before the term ends typically forfeits some interest — often a set number of months' dividends depending on the term. Always check the specific penalty before opening."},
        ],
        "auto-loans": [
            {"q": "Why are credit union auto loan rates lower?", "a": "Credit unions are not-for-profit and return earnings to members as lower loan rates. Federal credit unions also face an 18% cap on most loan rates, which keeps pricing in check."},
            {"q": "Can I get pre-approved before car shopping?", "a": "Most credit unions offer auto loan pre-approval, which lets you shop like a cash buyer and gives you a rate to beat at the dealer. It's one of the biggest advantages of financing through a credit union."},
            {"q": "Should I refinance my auto loan with a credit union?", "a": "If your current rate is high — common with dealer financing — a credit union refinance can cut your rate and payment. Compare the new APR and any fees against your existing loan."},
        ],
        "checking": [
            {"q": "What is rewards checking?", "a": "A checking account that pays a high APY (sometimes 3–5%+) on balances up to a cap, if you meet monthly requirements like a set number of debit transactions and e-statements. Great if you can hit the hoops reliably."},
            {"q": "Do credit unions really offer free checking?", "a": "Many do — with no monthly fee and no minimum balance — which is increasingly rare at large banks. Watch for overdraft and out-of-network ATM fees, which can still apply."},
            {"q": "Can I use ATMs nationwide with a credit union?", "a": "Usually yes. Most credit unions belong to surcharge-free ATM networks (like CO-OP) with tens of thousands of machines, and many rebate out-of-network ATM fees."},
        ],
        "savings": [
            {"q": "Are credit union savings rates better than banks?", "a": "Often, though the top online banks are very competitive. The smart move is to compare a credit union's APY against the best online savings rate before deciding."},
            {"q": "What's the difference between a share account and savings?", "a": "At a credit union, your basic savings account is called a 'share account,' and the small balance in it represents your ownership stake. Functionally it works like a bank savings account."},
            {"q": "Is there a limit on savings withdrawals?", "a": "Federal limits on savings withdrawals were relaxed in 2020, but individual credit unions may set their own transfer limits. Check the account disclosure."},
        ],
        "mortgages": [
            {"q": "Are credit union mortgage rates lower?", "a": "Credit unions often have lower fees and competitive rates, and many keep loans in-house rather than selling them. Always compare a Loan Estimate from a credit union against at least one other lender."},
            {"q": "Do credit unions offer first-time homebuyer programs?", "a": "Many do, including low-down-payment and no-PMI options. These programs vary widely by institution, so ask specifically."},
            {"q": "Can I get a mortgage if I just joined?", "a": "Usually yes — you typically just need to be a member when you apply. Joining can be as simple as opening a share account with a small deposit."},
        ],
        "beginners": [
            {"q": "What do I need to open my first credit union account?", "a": "A government ID, your Social Security number, proof of address, and a small opening deposit (often just $5). The whole process takes about 10–15 minutes online at most credit unions."},
            {"q": "Will opening a credit union account hurt my credit?", "a": "Opening a deposit account generally doesn't affect your credit score. Some credit unions run a soft check or ChexSystems review, which doesn't impact your score."},
            {"q": "Which credit union is easiest to join?", "a": "The ones flagged 'anyone can join' on our site — they accept members nationwide through a small one-time donation or free association membership. See our anyone-can-join list."},
        ],
        "nationwide": [
            {"q": "Which credit unions can anyone in the US join?", "a": "Quite a few — including PenFed, Alliant, DCU, and others — usually through a one-time charity donation of $5–$25 or a free association membership. See our full verified anyone-can-join list."},
            {"q": "Is joining a nationwide credit union worth it?", "a": "If you want top rates without a location or employer requirement, yes. Many of the best-rate credit unions in America are nationally joinable."},
            {"q": "Do nationwide credit unions have branches near me?", "a": "Some are largely digital, but most belong to shared branching and ATM networks giving members access to thousands of physical locations nationwide."},
        ],
        "small-business": [
            {"q": "Can a small business bank at a credit union?", "a": "Yes — many credit unions offer business checking, savings, lending, and merchant services, often with lower fees than banks. You'll typically need to be an eligible member."},
            {"q": "Do credit unions do SBA loans?", "a": "Many participate in SBA lending programs and offer business term loans and lines of credit. Larger or more complex commercial needs may still be better served by a bank."},
            {"q": "Are business deposits NCUA insured?", "a": "Yes. Business accounts at federally insured credit unions are covered by the NCUA, generally up to $250,000 per account ownership category."},
        ],
    }
    for cat in CATEGORIES:
        picks = [by_slug[s] for s in
                 # preserve the curated order from the data tagging
                 [c["slug"] for c in CUS if cat["key"] in c.get("categories", [])]]
        # order picks: full tier first, then by assets desc, anyone-can-join nudged up
        picks.sort(key=lambda c: (c["tier"] != "full", not c["fom"]["anyone_can_join"],
                                  -c.get("assets_b_approx", 0)))
        # for rate-driven roundups, sort by the rate (APR ascending, APY descending)
        if cat.get("rate_col"):
            col = cat["rate_col"]
            ascending = col.endswith("_apr")
            rated_picks = [c for c in picks if c.get("rates") and c["rates"].get(col) is not None]
            unrated = [c for c in picks if c not in rated_picks]
            rated_picks.sort(key=lambda c: c["rates"][col], reverse=not ascending)
            picks = rated_picks + unrated
        path = f"{cat['slug']}/index.html"
        url = f"{BASE_URL}/{cat['slug']}/"
        cat_full = dict(cat, faqs=CAT_FAQS[cat["key"]])
        desc = (cat["lede"][:155]).rsplit(" ", 1)[0] + "…" if len(cat["lede"]) > 155 else cat["lede"]
        render(
            "category.html", path,
            title=f"{cat['h1']} | Credit Union Reviewer",
            meta_description=desc, depth=1, og_type="article",
            schemas=[article_schema(cat["h1"], desc, url),
                     faq_schema(CAT_FAQS[cat["key"]]),
                     breadcrumb_schema([{"name": "Home", "href": ""},
                                        {"name": "Guides", "href": "guides/"},
                                        {"name": cat["card_title"], "href": f"{cat['slug']}/"}])],
            breadcrumbs=[{"name": "Home", "href": "index.html"},
                         {"name": "Guides", "href": "guides/index.html"},
                         {"name": cat["card_title"], "href": f"{cat['slug']}/index.html"}],
            cat=cat_full, picks=picks,
        )

    # ---------- Guides hub ----------
    render(
        "guides_index.html", "guides/index.html",
        title="Credit Union Roundups & Guides | Credit Union Reviewer",
        meta_description="The best credit unions for CDs, auto loans, checking, savings, mortgages, small business, and more — plus our core guides to joining and NCUA insurance.",
        depth=1,
        schemas=[breadcrumb_schema([{"name": "Home", "href": ""},
                                    {"name": "Guides", "href": "guides/"}])],
        breadcrumbs=[{"name": "Home", "href": "index.html"},
                     {"name": "Guides", "href": "guides/index.html"}],
        cats=CATEGORIES,
    )

    # ---------- Can I join? finder ----------
    finder_data = [{
        "slug": c["slug"], "name": c["name"], "state": c["hq_state"],
        "hq_city": c["hq_city"], "members": c["members_fmt"],
        "acj": c["fom"]["anyone_can_join"],
        "path": c["fom"]["easy_path"], "summary": c["fom"]["summary"],
    } for c in CUS]
    # anyone-can-join first in the finder payload
    finder_data.sort(key=lambda c: (not c["acj"], c["name"]))
    url = f"{BASE_URL}/can-i-join/"
    render(
        "finder.html", "can-i-join/index.html",
        title="Can I Join? Credit Union Membership Finder | Credit Union Reviewer",
        meta_description="Find the credit unions you can join. Pick your state and connections to see open-membership and local credit unions you most likely qualify for.",
        depth=1, og_type="article",
        schemas=[article_schema("Can I Join? Credit Union Membership Finder",
                                "Find credit unions you qualify for by state and connection.", url),
                 breadcrumb_schema([{"name": "Home", "href": ""},
                                    {"name": "Can I Join?", "href": "can-i-join/"}])],
        breadcrumbs=[{"name": "Home", "href": "index.html"},
                     {"name": "Can I Join?", "href": "can-i-join/index.html"}],
        finder_json=json.dumps(finder_data, ensure_ascii=False),
        state_names_json=json.dumps(STATE_NAMES, ensure_ascii=False),
    )

    # ---------- Comparison pages ----------
    for m in matchups:
        a, b = by_slug[m["a"]], by_slug[m["b"]]
        path = f"compare/{m['slug']}/index.html"
        url = f"{BASE_URL}/compare/{m['slug']}/"
        title = f"{a['name']} vs {b['name']}: 2026 Comparison | Credit Union Reviewer"
        desc = (f"{a['name']} vs {b['name']}: membership, rates, and which credit union "
                f"is the better fit in 2026. An honest side-by-side comparison.")[:158]
        render(
            "compare.html", path,
            title=title, meta_description=desc, depth=2, og_type="article",
            schemas=[article_schema(f"{a['name']} vs {b['name']}", desc, url),
                     faq_schema(m["faqs"]),
                     breadcrumb_schema([{"name": "Home", "href": ""},
                                        {"name": "Comparisons", "href": "compare/"},
                                        {"name": f"{a['name']} vs {b['name']}", "href": f"compare/{m['slug']}/"}])],
            breadcrumbs=[{"name": "Home", "href": "index.html"},
                         {"name": "Comparisons", "href": "compare/index.html"},
                         {"name": f"{a['name']} vs {b['name']}", "href": f"compare/{m['slug']}/index.html"}],
            a=a, b=b, m=m,
        )

    render(
        "compare_index.html", "compare/index.html",
        title="Credit Union Comparisons (Head-to-Head) | Credit Union Reviewer",
        meta_description="Head-to-head credit union comparisons — Navy Federal vs PenFed, PenFed vs Alliant, and more. See which credit union wins on rates, access, and fit.",
        depth=1,
        schemas=[breadcrumb_schema([{"name": "Home", "href": ""},
                                    {"name": "Comparisons", "href": "compare/"}])],
        breadcrumbs=[{"name": "Home", "href": "index.html"},
                     {"name": "Comparisons", "href": "compare/index.html"}],
        matchups=matchups,
    )

    # ---------- Glossary ----------
    gloss_terms = [{"id": t[0], "term": t[1], "def": t[2]} for t in GLOSSARY]
    gloss_schema = {
        "@context": "https://schema.org", "@type": "DefinedTermSet",
        "name": "Credit Union Glossary", "url": f"{BASE_URL}/glossary/",
        "hasDefinedTerm": [{"@type": "DefinedTerm", "name": t[1], "description": t[2]} for t in GLOSSARY],
    }
    render(
        "glossary.html", "glossary/index.html",
        title="Credit Union Glossary: Key Terms Explained | Credit Union Reviewer",
        meta_description="A plain-English glossary of credit union terms: share accounts, dividends, field of membership, NCUA, share certificates, rewards checking, and more.",
        depth=1,
        schemas=[gloss_schema,
                 breadcrumb_schema([{"name": "Home", "href": ""},
                                    {"name": "Glossary", "href": "glossary/"}])],
        breadcrumbs=[{"name": "Home", "href": "index.html"},
                     {"name": "Glossary", "href": "glossary/index.html"}],
        terms=gloss_terms,
    )

    # ---------- Rates hub ----------
    rates_faqs = [
        {"q": "How often do credit union rates change?", "a": "Deposit rates (savings, CDs) can change monthly or faster, and loan rates move with the broader market. Always confirm the current rate on the credit union's site — the figures here are representative and dated."},
        {"q": "Are credit union rates better than banks?", "a": "On average, credit unions beat traditional banks on savings, CDs, and loan rates because they return earnings to members. The best online banks are competitive on deposits, so compare both."},
        {"q": "Why do some savings APYs only apply to small balances?", "a": "A few credit unions advertise a very high APY that only applies up to a cap (for example, the first $1,000). Above the cap, the rate drops to a standard level. Check the cap before assuming the headline rate applies to your whole balance."},
        {"q": "Can I trust an advertised loan APR?", "a": "Advertised 'from' APRs assume excellent credit and often require autopay or other conditions. Your actual rate depends on your credit profile, loan term, and the vehicle or property."},
    ]
    url = f"{BASE_URL}/rates/"
    render(
        "rates.html", "rates/index.html",
        title="Credit Union Rates 2026: Savings, CDs, Checking & Auto Loans",
        meta_description="Compare savings, money market, CD, rewards-checking, and auto loan rates across top US credit unions. Sortable tables, updated for 2026.",
        depth=1, og_type="article",
        schemas=[article_schema("Credit Union Rates", "Compare deposit and loan rates across top credit unions.", url),
                 faq_schema(rates_faqs),
                 breadcrumb_schema([{"name": "Home", "href": ""},
                                    {"name": "Rates", "href": "rates/"}])],
        breadcrumbs=[{"name": "Home", "href": "index.html"},
                     {"name": "Rates", "href": "rates/index.html"}],
        rated=RATED, rates_disclaimer=RATES_DISCLAIMER, faqs=rates_faqs,
        by_savings=sorted(RATED, key=lambda c: -c["rates"]["savings_apy"]),
        by_cd=sorted(RATED, key=lambda c: -c["rates"]["cd_12"]),
        by_checking=sorted(RATED, key=lambda c: -c["rates"]["checking_apy"]),
        by_auto=sorted(RATED, key=lambda c: c["rates"]["auto_new_apr"]),
    )

    # ---------- Auto loan calculator (standalone) ----------
    calc_faqs = [
        {"q": "How is the monthly payment calculated?", "a": "It uses the standard amortizing-loan formula based on your principal, the monthly interest rate (APR divided by 12), and the number of months. The result is a fixed payment that fully pays off the loan over the term."},
        {"q": "Does a longer term save me money?", "a": "It lowers the monthly payment but increases total interest, often substantially. A lower APR is usually a far better lever than a longer term."},
        {"q": "Why use a credit union for an auto loan?", "a": "Credit unions frequently price auto loans below banks, and federal credit unions cap most loan rates at 18%. A lower APR directly reduces both your payment and total interest."},
        {"q": "Is the pre-filled APR a real quote?", "a": "No — it's the lowest representative new-auto rate among the credit unions we review, provided as a realistic starting point. Get an actual pre-approval for your real rate."},
    ]
    url = f"{BASE_URL}/auto-loan-calculator/"
    render(
        "autocalc_page.html", "auto-loan-calculator/index.html",
        title="Auto Loan Payment Calculator (2026) | Credit Union Reviewer",
        meta_description="Free auto loan calculator: estimate your monthly car payment and total interest by loan amount, term, and APR. See how a lower credit union rate saves you money.",
        depth=1, og_type="article",
        schemas=[article_schema("Auto Loan Payment Calculator", "Estimate monthly car payments and total interest.", url),
                 faq_schema(calc_faqs),
                 breadcrumb_schema([{"name": "Home", "href": ""},
                                    {"name": "Auto Loan Calculator", "href": "auto-loan-calculator/"}])],
        breadcrumbs=[{"name": "Home", "href": "index.html"},
                     {"name": "Auto Loan Calculator", "href": "auto-loan-calculator/index.html"}],
        faqs=calc_faqs,
    )

    # ---------- Mortgage calculator (standalone) ----------
    mtg_faqs = [
        {"q": "Does this include taxes and insurance?", "a": "No — it shows principal and interest only. Your full monthly payment also includes property taxes, homeowners insurance, PMI (if you put down less than 20%), and any HOA dues."},
        {"q": "How much does the interest rate matter?", "a": "A lot. Over 30 years, even a half-point difference in rate can change total interest by tens of thousands of dollars. It's worth comparing a credit union's rate against other lenders."},
        {"q": "Should I choose a 15- or 30-year term?", "a": "A 15-year loan has higher monthly payments but far less total interest and builds equity faster. A 30-year loan lowers the monthly payment at the cost of more interest. Try both in the calculator."},
        {"q": "Is the pre-filled rate a real quote?", "a": "No — it's the lowest representative 30-year rate among the credit unions we review, as a starting point. Get an actual Loan Estimate for your real rate."},
    ]
    url = f"{BASE_URL}/mortgage-calculator/"
    render(
        "mortgagecalc_page.html", "mortgage-calculator/index.html",
        title="Mortgage Payment Calculator (2026) | Credit Union Reviewer",
        meta_description="Free mortgage calculator: estimate your monthly principal and interest and total interest by home price, down payment, term, and rate.",
        depth=1, og_type="article",
        schemas=[article_schema("Mortgage Payment Calculator", "Estimate monthly mortgage payments and total interest.", url),
                 faq_schema(mtg_faqs),
                 breadcrumb_schema([{"name": "Home", "href": ""},
                                    {"name": "Mortgage Calculator", "href": "mortgage-calculator/"}])],
        breadcrumbs=[{"name": "Home", "href": "index.html"},
                     {"name": "Mortgage Calculator", "href": "mortgage-calculator/index.html"}],
        faqs=mtg_faqs,
    )

    # ---------- Full directory (all credit unions) ----------
    url = f"{BASE_URL}/credit-unions/"
    render(
        "directory.html", "credit-unions/index.html",
        title=f"All {len(CUS)} Credit Unions We Review (A–Z Directory) | Credit Union Reviewer",
        meta_description=f"Browse all {len(CUS)} credit unions we review. Search by name and filter by state, membership, and review depth. Every credit union links to its review.",
        depth=1,
        schemas=[breadcrumb_schema([{"name": "Home", "href": ""},
                                    {"name": "Credit Union Directory", "href": "credit-unions/"}])],
        breadcrumbs=[{"name": "Home", "href": "index.html"},
                     {"name": "Directory", "href": "credit-unions/index.html"}],
        all_cus=DIRECTORY, state_names_json=json.dumps(STATE_NAMES, ensure_ascii=False),
    )

    # ---------- 404 ----------
    render(
        "notfound.html", "404.html",
        title="Page Not Found | Credit Union Reviewer",
        meta_description="The page you were looking for could not be found.",
        depth=0,
    )
    PAGES.remove("404.html")  # don't index the 404 in the sitemap

    # ---------- sitemap + robots ----------
    priority = {"": "1.0", "best-credit-unions/": "1.0", "anyone-can-join/": "1.0",
                "credit-union-vs-bank/": "0.9", "how-to-join/": "0.9", "guides/": "0.9",
                "can-i-join/": "0.9", "ncua-insurance/": "0.8", "state/": "0.8"}
    for cat in CATEGORIES:
        priority[cat["slug"] + "/"] = "0.9"
    priority["rates/"] = "0.9"
    priority["compare/"] = "0.8"
    priority["glossary/"] = "0.6"
    priority["cookies/"] = "0.3"
    priority["disclaimer/"] = "0.3"
    priority["auto-loan-calculator/"] = "0.8"
    priority["mortgage-calculator/"] = "0.8"
    priority["credit-unions/"] = "0.9"
    for m in matchups:
        priority["compare/" + m["slug"] + "/"] = "0.7"
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in sorted(set(PAGES)):
        pr = priority.get(p, "0.8" if p.startswith("reviews/") or p.startswith("state/") else "0.4")
        lines.append(f"  <url><loc>{BASE_URL}/{p}</loc>"
                     f"<lastmod>{VERIFIED_DATE}</lastmod>"
                     f"<priority>{pr}</priority></url>")
    lines.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(lines))
    (DIST / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n")

    print(f"Built {len(PAGES)} pages -> {DIST}")


if __name__ == "__main__":
    main()
