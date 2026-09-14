# Shovels API validation study: heat pump permits, Philadelphia, 2025

A customer-style question answered with the Shovels API, then checked against the city's own permit records. Built in a day with an AI agent driving. Numbers, limits, and unresolved items are reported as found.

## The question
An HVAC contractor asks: *how many heat pump permits were pulled in Philadelphia in the last 12 months, and who's doing the work?*

## The answer
Filtering the Shovels API on the `heat_pump` tag returns **20** permits for Philadelphia in 2025/26. The city's open permit data, keyword-filtered for heat pump work, holds **435**. All 20 Shovels results appear in the city data; none are Shovels-only.
The gap is classification, not coverage. Of six open-data-only permits spot-checked by hand, five were already present in Shovels under adjacent tags (`hvac`, `gas`, `remodel`). The records are there; a customer filtering on `heat_pump` would not see them.

**Confidence statement:** the 20 are correct but not complete. The true count of heat pump permits in Shovels' Philadelphia data is likely closer to the city's 435 than to 20, but this study did not quantify it (see [Limits](#limits)).

## Why Philadelphia

It's my hometown! Though I now live in Pittsburgh. I also chose Philadelphia because Shovels' coverage dashboard shows deeper coverage there, which makes a reconciliation meaningful rather than a test of whether the jurisdiction is ingested at all.

## Method

### Source 1 — City of Philadelphia open data

- Dataset: [OpenDataPhilly](https://opendataphilly.org/datasets/licenses-and-inspections-building-and-zoning-permits/)
- Scope: all permit types, 2025 issue dates
- Filter: description keyword search for heat pump work — `(heat[ -]?pump|mini[ -]?split|ductless|(multi|split)[ -]?zone|hyper[ -]?heat|\mVRF\M)`
- Freshness: table current through 2026-09-13
- Result: 435 records → `data/summary_counts.csv` (aggregates only; raw city data is linked)

### Source 2 — Shovels API v2

- Endpoint: `/permits/search`
- Parameters: `geo_id=Zq5jws7cUfs` (Philadelphia), `permit_from=2025-09-12`, `permit_to=2026-09-12`, `permit_tags=heat_pump`
- Result: `total_count` = 20, all rows retrieved
- Raw Shovels records are **not** committed to this repo

### Reconciliation

Match on permit number, with normalized address + issue date as fallback. Full detail in [`RECONCILIATION.md`](RECONCILIATION.md).

| | Count |
|---|---|
| Matched (in both) | 20 |
| Open-data-only | 415 |
| Shovels-only | 0 |

### Spot check

Six open-data-only permits looked up individually in Shovels: five present under other tags, one [NOT FOUND / UNRESOLVED].

## Findings

1. **Coverage is good; tagging is the customer-visible gap.** Heat pump permits are in Shovels' Philadelphia data, but a `heat_pump` filter surfaces a fraction of them.
2. **Heat pump work is frequently tagged `hvac`, `gas`, or `remodel`** rather than `heat_pump`, based on the sample.
3. **`permit_from` / `permit_to` do not filter on file date alone.** Per the docs, they apply to the earliest and latest of file, issue, start, and final dates. Any comparison against a single-date source has to account for this; my initial pull assumed otherwise.

## Limits

- **Credit ceiling.** The Shovels API returned `402 Monthly credit limit exceeded` (500/month) partway through the planned per-permit lookup of the 415. The tagging-versus-date breakdown therefore rests on six manual examples, not the population. It is reported that way rather than extrapolated.
- **Unresolved anomaly.** Three permits with in-window dates did not surface in a narrow-window `/permits/search`. Not explained; needs fresh credits to chase.
- **Denominator.** The city has no heat pump tag. The 435 depends on my keyword filter and will include some false positives and miss some true heat pump work described differently.

## What I'd build next

A reclassification pass over permits tagged `hvac`, `gas`, and `remodel` whose descriptions mention heat pumps (or model numbers, refrigerant types, and "mini split"), so that a `heat_pump` filter returns the population rather than a fraction of it. Philadelphia's 435 gives a ready-made labeled set to validate against.

## Agent workflow

See [`agent/WORKFLOW.md`](agent/WORKFLOW.md): what I asked the agent to do, where it was wrong, and what I'd build to make it reliable.

## Repo layout

```
├── README.md              # this report
├── RECONCILIATION.md      # match detail and samples
├── pull_shovels.py        # Shovels API pull → JSONL / CSV
├── compare.py             # reconciliation against the city export
├── agent/WORKFLOW.md      # agent prompts, failures, and next build
├── data/summary_counts.csv
└── .gitignore
```

## Running it

```bash
export SHOVELS_API_KEY=your_key_here
python pull_shovels.py   # pulls Shovels permits to JSONL / CSV
python compare.py        # reconciles against the city export
```

Requires Python 3.10+, `requests`, and `pandas`.
