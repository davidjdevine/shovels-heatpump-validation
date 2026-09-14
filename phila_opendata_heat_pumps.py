"""
Pull City of Philadelphia L&I permits that mention heat pumps, from Philadelphia's
open data (Carto SQL API) — no API key needed.

Dataset: "Licenses and Inspections Building and Zoning Permits" (OpenDataPhilly)
    https://opendataphilly.org/datasets/licenses-and-inspections-building-and-zoning-permits/
Endpoint: https://phl.carto.com/api/v2/sql   (table: permits; Postgres SQL; updated daily)

Usage:
    python phila_opendata_heat_pumps.py [--from 2025-09-12] [--to 2026-09-12]
                                        [--all-types] [--out philly_heat_pump_permits_opendata]

Notes:
  * There is no structured "equipment" field, so heat pumps are found with a
    case-insensitive regex on the free-text approvedscopeofwork column.
  * By default only Mechanical and Electrical permits are returned (~97% of all
    heat-pump mentions). --all-types drops that filter.
  * "Heat pump water heater" mentions are flagged in a likely_hpwh column rather
    than excluded, so you can decide.
  * permitissuedate is a timestamptz stored as local-midnight-in-UTC (e.g.
    2025-05-07T04:00:00Z); the filter compares on the date part in local time.
"""
import argparse, csv, io, sys
import requests

CARTO = "https://phl.carto.com/api/v2/sql"

HP_REGEX = r"(heat[ -]?pump|mini[ -]?split|ductless|(multi|split)[ -]?zone|hyper[ -]?heat|\mVRF\M)"
HPWH_REGEX = r"water[ -]?heater"

COLS = """
    permitnumber, permittype, permitdescription, typeofwork, commercialorresidential,
    status, applicanttype,
    (permitissuedate AT TIME ZONE 'America/New_York')::date      AS permit_issue_date,
    (permitcompleteddate AT TIME ZONE 'America/New_York')::date  AS permit_completed_date,
    (mostrecentinsp AT TIME ZONE 'America/New_York')::date       AS most_recent_insp_date,
    address, unit_type, unit_num, zip, council_district, censustract,
    opa_account_num, opa_owner, parcel_id_num, addressobjectid,
    contractorname, contractoraddress1,
    numberofunits, occupancytype, usecategories,
    ST_X(the_geom) AS lng, ST_Y(the_geom) AS lat,
    approvedscopeofwork,
    (approvedscopeofwork ~* '{hpwh}') AS likely_hpwh
""".format(hpwh=HPWH_REGEX)


def build_sql(start, end, all_types):
    type_filter = "" if all_types else "AND permittype IN ('Mechanical','Electrical')"
    return f"""
        SELECT {COLS}
        FROM permits
        WHERE (permitissuedate AT TIME ZONE 'America/New_York')::date
              BETWEEN '{start}' AND '{end}'
          AND approvedscopeofwork ~* '{HP_REGEX}'
          {type_filter}
        ORDER BY permitissuedate, permitnumber
    """


def run_csv(sql):
    # POST keeps long SQL out of the URL; format=csv streams straight to disk.
    r = requests.post(CARTO, data={"q": sql, "format": "csv"}, timeout=300)
    if not r.ok:
        sys.exit(f"Carto error {r.status_code}: {r.text[:500]}")
    return r.text


def run_json(sql):
    r = requests.post(CARTO, data={"q": sql}, timeout=120)
    r.raise_for_status()
    return r.json()["rows"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default="2025-09-12")
    ap.add_argument("--to", dest="end", default="2026-09-12")
    ap.add_argument("--all-types", action="store_true")
    ap.add_argument("--out", default="philly_heat_pump_permits_opendata")
    a = ap.parse_args()

    # Sanity check: how fresh is the table, and how many rows in the window overall?
    meta = run_json(f"""
        SELECT max(permitissuedate)::date AS latest_issue_date,
               count(*) FILTER (WHERE (permitissuedate AT TIME ZONE 'America/New_York')::date
                                      BETWEEN '{a.start}' AND '{a.end}') AS permits_in_window
        FROM permits""")[0]
    print(f"Table current through {meta['latest_issue_date']}; "
          f"{meta['permits_in_window']} permits issued {a.start}..{a.end}", file=sys.stderr)

    text = run_csv(build_sql(a.start, a.end, a.all_types))
    out = a.out + ".csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        f.write(text)

    rows = list(csv.DictReader(io.StringIO(text)))
    by_type = {}
    for r in rows:
        by_type[r["permittype"]] = by_type.get(r["permittype"], 0) + 1
    hpwh = sum(r["likely_hpwh"] in ("t", "true", "True") for r in rows)
    print(f"done: {len(rows)} heat-pump permits -> {out}", file=sys.stderr)
    print(f"  by permittype: {by_type}", file=sys.stderr)
    print(f"  flagged as possible heat-pump water heaters: {hpwh}", file=sys.stderr)
