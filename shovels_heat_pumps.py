"""
Pull all Philadelphia, PA permits tagged "Heat Pump" for 2025-09-12 through 2026-09-12 from the
Shovels v2 API and write them to JSONL + CSV.

Usage:
    export SHOVELS_API_KEY=...
    python shovels_heat_pumps.py [--tag heat_pump] [--city "Philadelphia"] [--state PA]
                                 [--from 2025-09-12] [--to 2026-09-12]

Endpoints verified against docs.shovels.ai (Sept 2026):
    GET /v2/list/tags          -> {items:[{id, description}], next_cursor}
    GET /v2/cities/search?q=   -> {items:[{geo_id, name, state}], next_cursor}
    GET /v2/permits/search     -> required: geo_id, permit_from, permit_to
                                  optional: permit_tags (repeatable), size (1-100),
                                            cursor, include_count
"""
import argparse, csv, json, os, sys, time
import requests

BASE = "https://api.shovels.ai/v2"
API_KEY = os.environ.get("SHOVELS_API_KEY")
if not API_KEY:
    sys.exit("Set SHOVELS_API_KEY in your environment first.")
H = {"X-API-Key": API_KEY, "accept": "application/json"}


def get(path, **params):
    """GET with retry on 429/5xx. Lists in params become repeated query keys
    (requests does this natively), which is what Shovels expects for arrays."""
    for attempt in range(6):
        r = requests.get(f"{BASE}{path}", params=params, headers=H, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            wait = float(r.headers.get("Retry-After", 2 ** attempt))
            print(f"  {r.status_code} on {path}; sleeping {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)
            continue
        if not r.ok:
            # surface the API's own error message; it's usually specific
            sys.exit(f"HTTP {r.status_code} on {path}: {r.text[:500]}")
        return r.json()
    raise RuntimeError(f"gave up on {path}")


def paginate(path, **params):
    """Yield every item across cursor pages."""
    cursor = None
    while True:
        page = get(path, **({**params, "cursor": cursor} if cursor else params))
        yield from page.get("items", [])
        cursor = page.get("next_cursor")
        if not cursor:
            break


def resolve_tag(wanted):
    """Confirm the tag id exists; if not, show the closest matches and stop."""
    tags = list(paginate("/list/tags", size=100))
    ids = {t["id"] for t in tags}
    if wanted in ids:
        return wanted
    needle = wanted.lower().replace("_", " ")
    hits = [t for t in tags
            if needle in t["id"].replace("_", " ").lower()
            or needle in (t.get("description") or "").lower()]
    print(f"Tag '{wanted}' not found. Similar tags:", file=sys.stderr)
    for t in hits or tags:
        print(f"  {t['id']:<30} {t.get('description','')}", file=sys.stderr)
    sys.exit(1)


def find_geo_id(city, state):
    items = list(paginate("/cities/search", q=city))
    matches = [it for it in items if it.get("state") == state]
    if not matches:
        print("No city match. Candidates were:", file=sys.stderr)
        for it in items:
            print("  ", json.dumps(it), file=sys.stderr)
        sys.exit(1)
    if len(matches) > 1:
        print("Multiple matches; using the first:", file=sys.stderr)
        for it in matches:
            print("  ", json.dumps(it), file=sys.stderr)
    print(f"Using geo_id {matches[0]['geo_id']} = {matches[0]['name']}", file=sys.stderr)
    return matches[0]["geo_id"]


def pull_permits(geo_id, tag, start, end, out_jsonl):
    n = 0
    first = get("/permits/search", geo_id=geo_id, permit_from=start, permit_to=end,
                permit_tags=[tag], size=100, include_count=True)
    tc = first.get("total_count") or {}
    if tc:
        print(f"API reports {tc.get('value')} permits ({tc.get('relation')})", file=sys.stderr)
    with open(out_jsonl, "w") as f:
        page = first
        while True:
            for p in page.get("items", []):
                f.write(json.dumps(p) + "\n"); n += 1
            print(f"  {n} permits so far", file=sys.stderr)
            cursor = page.get("next_cursor")
            if not cursor:
                break
            page = get("/permits/search", geo_id=geo_id, permit_from=start, permit_to=end,
                       permit_tags=[tag], size=100, cursor=cursor)
    return n


def flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        elif isinstance(v, list):
            # list of scalars -> pipe-joined; list of dicts -> JSON string
            out[key] = ("|".join(map(str, v)) if all(not isinstance(x, dict) for x in v)
                        else json.dumps(v))
        else:
            out[key] = v
    return out


def jsonl_to_csv(jsonl, csv_path):
    rows = [flatten(json.loads(l)) for l in open(jsonl) if l.strip()]
    if not rows:
        print("No rows; CSV not written.", file=sys.stderr); return
    cols = sorted({k for r in rows for k in r})
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="heat_pump")
    ap.add_argument("--city", default="Philadelphia")
    ap.add_argument("--state", default="PA")
    ap.add_argument("--from", dest="start", default="2025-09-12")
    ap.add_argument("--to", dest="end", default="2026-09-12")
    ap.add_argument("--out", default="philly_heat_pump_permits_shovels")
    a = ap.parse_args()

    tag = resolve_tag(a.tag)
    geo = find_geo_id(a.city, a.state)
    n = pull_permits(geo, tag, a.start, a.end, a.out + ".jsonl")
    jsonl_to_csv(a.out + ".jsonl", a.out + ".csv")
    print(f"done: {n} permits -> {a.out}.csv")
