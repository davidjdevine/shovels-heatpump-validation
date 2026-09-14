# Reconciliation: Philadelphia heat-pump permits, 2025-09-12 → 2026-09-12

Compared on `permitnumber` (open data) vs `number` (Shovels) — Shovels' `number` field
carries the city-issued L&I permit number verbatim (e.g. `MP-2026-004501`), confirmed by
inspection of raw API responses.

## Headline numbers

| | count |
|---|---|
| Open-data rows (heat-pump regex, all permittypes) | 435 |
| Shovels rows (`heat_pump` tag) | 20 |
| **In both** | **20** |
| **Open-data only** | **415** |
| **Shovels only** | **0** |

Every Shovels row is a subset of the open-data set — Shovels found nothing that the regex
missed. All 20 in-both matches are `permittype = Mechanical`; none of the Electrical,
Building, Residential Building, or Plumbing hits from open data are in Shovels' tagged set
at all.

**Not fully resolved — hit the Shovels API's monthly credit cap (402 "Monthly credit limit
exceeded", limit 500) partway through the deeper quantification below.** I could not run
the systematic "how many of the 415 are date-window vs. tagging misses" breakdown I had
planned (comparing `permit_q='heat pump'` text-match counts across tag/date-window
combinations). What follows is based on 6 manually spot-checked examples from the 415,
not the full population — treat the proportions as illustrative, not exhaustive.

## Diagnosis of the 415 open-data-only rows (from 6 spot-checked examples)

I picked 6 random open-data-only permit numbers and searched for them in Shovels directly
(there's no permit-number lookup endpoint, so I used `permit_q` substring search on the
permit description, confirmed against `docs.shovels.ai/api-reference/permits/search-permits.md`
as description-only substring matching):

| Permit | Open-data category | Found in Shovels? | Shovels tags | Diagnosis |
|---|---|---|---|---|
| `MP-2026-003436` | Mechanical, "mini split" mention | Yes | `hvac` | **Tagging miss** — Shovels' classifier tagged it generic HVAC but not `heat_pump`. |
| `MP-2025-004962` | Mechanical, "...ton heat pump with 10kw backup..." | Yes | `hvac` | **Tagging miss** — literal "heat pump" in the text, still not tagged `heat_pump`. |
| `CP-2026-000785` | Building, heat-pump mention buried in a historical-commission approval condition | Yes | `remodel` | **Tagging miss** — plausible given the mention is incidental/buried, but still a miss. |
| `MP-2025-005997` | Mechanical, boilerplate ductless-systems template | Found in a broad 2020–2026 search (tags: `hvac`) | `hvac` | **Unresolved** — see below. |
| `MP-2024-001039` | Mechanical, same template | Found in broad search (tags: `gas`, `hvac`) | `gas`, `hvac` | **Unresolved** — see below. |
| `MP-2025-003062` | Mechanical, same template | Found in broad search (tags: `hvac`, `roofing`); `file_date=2025-06-02` (before window start) | `hvac`, `roofing` | Partly **date-field difference**, see below. |

### Date-field difference is real and documented, but its exact scope is unverified

The brief assumed `permit_from`/`permit_to` filter on file date. I checked the actual docs
(`docs.shovels.ai/api-reference/permits/search-permits.md`) and they say something more
specific: **`permit_from` uses the earliest of (file, issue, start) date; `permit_to` uses
the latest of (file, issue, final) date** — not simply file date. This is a real
disagreement with the brief.

`MP-2025-003062` has `file_date=2025-06-02` (before the 2025-09-12 window start) but
`issue_date=2025-10-13` (inside the window) — open data matched it because it filters on
`permitissuedate`. Under the docs' stated logic this permit's *earliest* qualifying date
is still before the window, which would exclude it from Shovels' `permit_from` filter
regardless of tagging.

However, when I re-ran the same `permit_q` search restricted to the actual reconciliation
window (`permit_from=2025-09-12`, `permit_to=2026-09-12`), **all three** of
`MP-2025-005997`, `MP-2024-001039`, and `MP-2025-003062` disappeared from the results —
including `MP-2025-005997`, whose `file_date` (2025-11-19), `issue_date` (2026-02-16), and
`start_date` (2025-11-19) are all *inside* the window by the docs' own stated rule. That
contradicts the docs' description and I could not chase it down further (credit limit hit
immediately after). **I'm flagging this rather than guessing**: either the real
`permit_from`/`permit_to` semantics are stricter than documented (e.g. requiring all three
date fields non-null and in-range, rather than min/max), or something else about search
pagination/indexing is at play. This needs re-verification once API credits reset.

### Heat-pump water heaters: correctly excluded, not a gap

Open data flags 3 rows as `likely_hpwh` (regex match on "water heater"). All 3 are
open-data-only — Shovels' `heat_pump` tag does not pick them up. Given the tag's own
description ("any type of heat pump installation or repair") arguably *could* cover heat
pump water heaters, this might be an intentional scope narrowing on Shovels' side or a
separate miss — I can't tell without asking Shovels, but functionally it means these 3
water-heater permits are correctly outside Shovels' HVAC-heat-pump tag either way.

## What this means for headline usage

- **Bottom line: the two sources disagree by roughly 20x (20 vs. 435) mostly because
  Shovels' ML tagging is conservative** — it appears to catch a narrower, higher-confidence
  subset of true heat-pump permits (all Mechanical-type, all with unambiguous "heat pump"
  language) rather than the full universe the open-data regex surfaces (Electrical,
  Building, Residential Building, Plumbing permits, and Mechanical permits with less direct
  language).
- A real (but currently unquantified) portion of the gap is a genuine date-window/date-field
  mismatch, not tagging — see above.
- Zero Shovels-only rows means the regex approach has no evidence of false negatives
  relative to Shovels; if anything the concern runs the other way (regex false positives),
  and the 10-sample manual check in Source 1 didn't find any.

## Disagreements with the reference scripts / brief, found during independent verification

1. **`permit_from`/`permit_to` date semantics**: the brief states they filter on "file
   date." The actual docs say `permit_from` = earliest of (file, issue, start) date,
   `permit_to` = latest of (file, issue, final) date — not simply file date. `file_date` is
   null on the two heat_pump-tagged sample records I inspected in full, so this pull is
   effectively issue/start-date-driven for those, but the picture is inconsistent (see
   unresolved discrepancy above).
2. **Mechanical/Electrical split**: the brief's "~93% Mechanical, a few percent Electrical"
   doesn't match what I measured — 90.8% Mechanical / 8.0% Electrical individually, though
   the *combined* 98.9% is close to what "restrict to those two" implies.
3. Everything else in the reference scripts (Carto endpoint/columns, `/list/tags`,
   `/cities/search`, `/permits/search` params, pagination via `next_cursor`, `total_count`
   shape) checked out against live responses.

## Known limitation

Hit the Shovels API's monthly credit cap mid-investigation (402, limit 500 credits). No
further Shovels API calls were possible after that point. The 6-example spot-check above
is not a full audit of all 415 open-data-only rows — re-run with fresh credits for a
complete, quantified breakdown.
