"""
Independent pull of Philadelphia, PA permits tagged heat_pump from Shovels API v2.
Verified myself (not trusting shovels_heat_pumps.py blindly):
  - GET /v2/list/tags -> confirmed tag id is exactly "heat_pump" (23 tags total, one page).
  - GET /v2/cities/search?q=Philadelphia -> confirmed geo_id "Zq5jws7cUfs" for
    "Philadelphia, Philadelphia, PA" (only PA match; other PA hit is "New Philadelphia").
  - Docs (docs.shovels.ai/api-reference/permits/search-permits.md) say permit_from is the
    EARLIEST of (file, issue, start) date and permit_to is the LATEST of (file, issue,
    final) date -- NOT simply "file date" as the brief states. file_date is null on every
    sampled record, so in practice this pull is date-filtering on issue/start/final dates.
"""
import csv, json, os, sys, time
import requests
from dotenv import load_dotenv

load_dotenv()
BASE = "https://api.shovels.ai/v2"
API_KEY = os.environ.get("SHOVELS_API_KEY")
if not API_KEY:
    sys.exit("Set SHOVELS_API_KEY in .env first.")
H = {"X-API-Key": API_KEY, "accept": "application/json"}

GEO_ID = "Zq5jws7cUfs"  # Philadelphia, Philadelphia, PA -- confirmed via /cities/search
TAG = "heat_pump"       # confirmed via /list/tags
START, END = "2025-09-12", "2026-09-12"


def get(path, **params):
    for attempt in range(6):
        r = requests.get(f"{BASE}{path}", params=params, headers=H, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            wait = float(r.headers.get("Retry-After", 2 ** attempt))
            print(f"  {r.status_code} on {path}; sleeping {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)
            continue
        if not r.ok:
            sys.exit(f"HTTP {r.status_code} on {path}: {r.text[:500]}")
        return r.json()
    raise RuntimeError(f"gave up on {path}")


def flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        elif isinstance(v, list):
            out[key] = ("|".join(map(str, v)) if all(not isinstance(x, dict) for x in v)
                        else json.dumps(v))
        else:
            out[key] = v
    return out


if __name__ == "__main__":
    print(f"Pulling Shovels permits: geo_id={GEO_ID} tag={TAG} {START}..{END}", file=sys.stderr)
    n = 0
    first = get("/permits/search", geo_id=GEO_ID, permit_from=START, permit_to=END,
                permit_tags=[TAG], size=100, include_count=True)
    tc = first.get("total_count") or {}
    print(f"API total_count: {tc}", file=sys.stderr)

    jsonl_path = "philly_heat_pump_permits_shovels.jsonl"
    with open(jsonl_path, "w") as f:
        page = first
        while True:
            items = page.get("items", [])
            for p in items:
                f.write(json.dumps(p) + "\n")
                n += 1
            print(f"  {n} permits so far (page size {len(items)})", file=sys.stderr)
            cursor = page.get("next_cursor")
            if not cursor:
                break
            page = get("/permits/search", geo_id=GEO_ID, permit_from=START, permit_to=END,
                       permit_tags=[TAG], size=100, cursor=cursor)

    rows = [flatten(json.loads(l)) for l in open(jsonl_path) if l.strip()]
    csv_path = "philly_heat_pump_permits_shovels.csv"
    if rows:
        cols = sorted({k for r in rows for k in r})
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    print(f"done: total_count.value={tc.get('value')} rows_received={n} -> {csv_path}", file=sys.stderr)
