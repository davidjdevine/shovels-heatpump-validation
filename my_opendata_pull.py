"""
Independent pull of City of Philadelphia L&I permits mentioning heat pumps, from the
Carto SQL API (open data, no key). Verified endpoint/schema against a live SELECT * LIMIT 1
against https://phl.carto.com/api/v2/sql rather than trusting the reference script blindly.

Decision vs. the brief's stated default: keeps ALL permittypes (not just Mechanical/
Electrical) because the excluded 5 rows (2 Building, 2 Residential Building, 1 Plumbing)
include 4 genuine heat-pump mentions and 1 correctly-flagged heat-pump water heater.
User confirmed this choice interactively.
"""
import csv, io, sys
import requests

CARTO = "https://phl.carto.com/api/v2/sql"
START, END = "2025-09-12", "2026-09-12"

HP_REGEX = r"(heat[ -]?pump|mini[ -]?split|ductless|(multi|split)[ -]?zone|hyper[ -]?heat|\mVRF\M)"
HPWH_REGEX = r"water[ -]?heater"

COLS = f"""
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
    (approvedscopeofwork ~* '{HPWH_REGEX}') AS likely_hpwh
"""

SQL = f"""
    SELECT {COLS}
    FROM permits
    WHERE (permitissuedate AT TIME ZONE 'America/New_York')::date BETWEEN '{START}' AND '{END}'
      AND approvedscopeofwork ~* '{HP_REGEX}'
    ORDER BY permitissuedate, permitnumber
"""


def run_csv(sql):
    r = requests.post(CARTO, data={"q": sql, "format": "csv"}, timeout=300)
    if not r.ok:
        sys.exit(f"Carto error {r.status_code}: {r.text[:500]}")
    return r.text


if __name__ == "__main__":
    print("Pulling open-data heat-pump permits, all permittypes...", file=sys.stderr)
    text = run_csv(SQL)
    out = "philly_heat_pump_permits_opendata.csv"
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
