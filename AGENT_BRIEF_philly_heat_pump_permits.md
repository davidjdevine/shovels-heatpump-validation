# Agent brief: Philadelphia heat-pump permits, 2025-09-12 → 2026-09-12

## Goal

Independently locate and pull every City of Philadelphia, PA permit that involves a
heat pump, issued between **2025-09-12 and 2026-09-12 inclusive**, from two sources,
and produce one CSV per source plus a short reconciliation note.

1. **Philadelphia open data** (Licenses & Inspections permits) — no key needed.
2. **Shovels API v2** — key in env var `SHOVELS_API_KEY`. Never print or commit the key.

Reference implementations exist (`phila_opendata_heat_pumps.py`, `shovels_heat_pumps.py`).
You may read them, but verify every endpoint and field yourself before relying on them —
the point of this task is an independent pull. Report any place where your findings
disagree with them.

## Source 1: Philadelphia open data

- Dataset: "Licenses and Inspections Building and Zoning Permits", City of Philadelphia.
  Landing page: https://opendataphilly.org/datasets/licenses-and-inspections-building-and-zoning-permits/
- Access: Carto SQL API, `https://phl.carto.com/api/v2/sql`, table `permits`, Postgres SQL,
  GET (`?q=...`) or POST (`q` form field). `format=csv` returns CSV directly. Updated daily.
  Alternative: ArcGIS FeatureServer `.../fLeGjb7u4uXqeF9q/arcgis/rest/services/PERMITS/FeatureServer/0`
  (2,000 rows per query; paginate with resultOffset).
- Key columns (Carto lowercases): `permitnumber`, `permittype`, `permitdescription`,
  `typeofwork`, `commercialorresidential`, `approvedscopeofwork` (the only free text),
  `permitissuedate` (timestamptz), `permitcompleteddate`, `status`, `address`, `zip`,
  `opa_account_num`, `contractorname`, `the_geom` (use `ST_X`/`ST_Y` for lng/lat).
- Date filter: use `permitissuedate`. Values are local midnight stored as UTC
  (e.g. `2025-05-07T04:00:00Z`), so cast with `AT TIME ZONE 'America/New_York'` before
  comparing dates. Do NOT rely on the year in the permit number — that's the
  application year.
- **There is no structured HVAC/equipment field.** `typeofwork` is generic
  ("Addition and/or Alterations", etc.). Identify heat pumps via case-insensitive regex on
  `approvedscopeofwork`, e.g. `~* '(heat[ -]?pump|mini[ -]?split|ductless|(multi|split)[ -]?zone|hyper[ -]?heat)'`.
  Text is messy and has typos; sanity-check with a sample.
- ~93% of heat-pump mentions are `permittype = 'Mechanical'` (legacy `BP_MECH`), a few
  percent `Electrical`. Restrict to those two unless you have a reason not to, and say so.
- Watch for "heat pump water heater" (plumbing appliance, not space heating). Flag it in
  a column rather than silently dropping.
- Deliverable: `philly_heat_pump_permits_opendata.csv`. Report: total rows, counts by
  `permittype`, count flagged as water heaters, `max(permitissuedate)` in the table (data
  freshness), and total permits of all kinds in the window (denominator).

## Source 2: Shovels API v2

- Base `https://api.shovels.ai/v2`, header `X-API-Key`. Docs: https://docs.shovels.ai
- Steps:
  1. `GET /list/tags` (paginated, `size`≤100, `cursor`) — confirm the exact heat pump tag
     id (expected `heat_pump`; ids are snake_case). If absent, list tags containing
     "heat" and stop.
  2. `GET /cities/search?q=Philadelphia` → pick the item with `state == "PA"`; use its `geo_id`.
  3. `GET /permits/search` with `geo_id`, `permit_from=2025-09-12`, `permit_to=2026-09-12`,
     `permit_tags=heat_pump` (repeat the key for multiple tags), `size=100`,
     `include_count=true` on the first call, then follow `next_cursor` until null.
- Respect `Retry-After` on 429. Note that `permit_from/to` filter on the permit's file
  date per the docs — record which date field you actually filtered on.
- Deliverable: `philly_heat_pump_permits_shovels.csv` (flatten nested JSON; keep raw JSONL too).
  Report: `total_count` from the API vs rows actually received.

## Reconciliation (required)

The two sources will not match, and the note should explain why, not hide it:

- Shovels tags come from its own ML classification of the same L&I text; open data uses
  your regex. Compare on `permitnumber` (Shovels should carry the city permit number —
  find the field). Report: in both / open-data only / Shovels only, with a handful of
  examples from each "only" bucket and your read on why (tagging miss, regex miss, water
  heater, date-field difference).
- If Shovels' date filter is application date and yours is issue date, quantify how many
  rows that alone explains.

## Constraints

- Print progress to stderr; keep stdout for final summary.
- Do not hard-code the API key. Do not modify the reference scripts; write your own.
- Flag anything you could not verify rather than guessing.
