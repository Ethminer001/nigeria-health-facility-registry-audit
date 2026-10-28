import os, csv, math, re
from collections import Counter, defaultdict

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def read_csv(fname):
    with open(os.path.join(DATA_DIR, fname), encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

g3 = read_csv("grid3_nga_health_facilities.csv")
hs = read_csv("healthsites_nigeria_2026.csv")

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

print("=== CHECK 1: ROWS IN GRID3 WHERE (X,Y) DIFFERS FROM (LON,LAT) BY MORE THAN 10 M ===")
xy_diffs = []
for r in g3:
    x, y = float(r["X"]), float(r["Y"])
    lon, lat = float(r["longitude"]), float(r["latitude"])
    d_m = haversine_m(y, x, lat, lon)
    if d_m > 10.0: # more than 10 meters apart
        xy_diffs.append((d_m, r))

print(f"Total rows where (X,Y) and (longitude,latitude) differ by >10 meters: {len(xy_diffs)}")
print("By source:", dict(Counter(r["source"] for _, r in xy_diffs)))
print("By state:", dict(Counter(r["statename"] for _, r in xy_diffs)))
for d_m, r in sorted(xy_diffs, key=lambda x: -x[0])[:8]:
    print(f"  dist={d_m/1000:.2f} km | state={r['statename']} | lga={r['lganame']} | name={r['prmry_name'][:30]} | X,Y=({float(r['X']):.4f},{float(r['Y']):.4f}) vs lon,lat=({float(r['longitude']):.4f},{float(r['latitude']):.4f}) | src={r['source']}")

print("\n=== CHECK 2: ROWS WITH A WRONG 'type' VALUE (32 CATEGORY NAMES AND 6 'Unknown') ===")
bad_types = [r for r in g3 if r["type"] not in ["Primary", "Secondary", "Tertiary"]]
print(f"Total rows where type not in Primary/Secondary/Tertiary: {len(bad_types)}")
for t_val, cnt in Counter((r["type"], r["category"], r["source"], r["statename"]) for r in bad_types).most_common():
    print(f"  type='{t_val[0]}' | category='{t_val[1]}' | source='{t_val[2]}' | state='{t_val[3]}': {cnt} rows")

print("\n=== CHECK 3: ROOT CAUSE OF 11,753 'Unknown' FUNCTIONAL STATUS & 9,895 'Others' OWNERSHIP ===")
unk_func = [r for r in g3 if r["func_stats"] == "Unknown"]
oth_own = [r for r in g3 if r["ownership"] == "Others"]
both_unk_oth = [r for r in g3 if r["func_stats"] == "Unknown" and r["ownership"] == "Others"]
print(f"func_stats == 'Unknown': {len(unk_func):,} | ownership == 'Others': {len(oth_own):,} | BOTH on same row: {len(both_unk_oth):,}")
print("Top sources for func_stats == 'Unknown':", Counter(r["source"] for r in unk_func).most_common(8))
print("Top sources for ownership == 'Others':", Counter(r["source"] for r in oth_own).most_common(8))
print("Top states for func_stats == 'Unknown':", Counter(r["statename"] for r in unk_func).most_common(8))

print("\n=== CHECK 4: THE 13 ROWS (6 PAIRS) SHARING EXACT 5-DECIMAL GPS COORDINATES IN GRID3 ===")
by_coord = defaultdict(list)
for r in g3:
    by_coord[(round(float(r["latitude"]), 5), round(float(r["longitude"]), 5))].append(r)
for coord, rows in by_coord.items():
    if len(rows) > 1:
        print(f"  Coord {coord} ({len(rows)} rows):")
        for r in rows:
            print(f"    -> id={r['uniq_id']} | name='{r['prmry_name']}' | cat='{r['category']}' | own='{r['ownership']}' | ward='{r['wardname']}' | src='{r['source']}'")

print("\n=== CHECK 5: THE 68 ROWS (34 WARD GROUPS) WITH IDENTICAL NAME IN THE SAME WARD ===")
by_ward_name = defaultdict(list)
for r in g3:
    by_ward_name[(r["wardcode"], r["prmry_name"].strip().lower())].append(r)

same_bldg_dups = 0 # < 250m
diff_village_generic = 0 # >= 250m
for (wcode, nm), rows in by_ward_name.items():
    if len(rows) > 1:
        r0, r1 = rows[0], rows[1]
        d_m = haversine_m(float(r0["latitude"]), float(r0["longitude"]), float(r1["latitude"]), float(r1["longitude"]))
        if d_m < 250:
            same_bldg_dups += len(rows)
        else:
            diff_village_generic += len(rows)
        print(f"  Ward={r0['wardname']} ({r0['statename']}) | Name='{r0['prmry_name']}' | count={len(rows)} | GPS dist={d_m:.1f} m | cats={[x['category'] for x in rows]}")

print(f"Summary of 68 Same-Ward Same-Name rows: {same_bldg_dups} rows are <250m apart (same site), {diff_village_generic} rows are >=250m apart (different sites in same ward sharing generic/duplicate name)!")
