import os, csv, math, re
from collections import defaultdict, Counter
from difflib import SequenceMatcher

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

STOP_WORDS = {
    "primary", "health", "healthcare", "care", "center", "centre", "clinic", "hospital",
    "general", "basic", "comprehensive", "model", "maternity", "home", "dispensary",
    "post", "medical", "ward", "lga", "state", "federal", "specialist", "centre",
    "phc", "chc", "bhc", "fsp", "mdg", "mphc", "h/c", "h/p", "and", "of", "the", "in"
}

def clean_core_name(name):
    s = re.sub(r'[^a-z0-9\s]', ' ', name.lower())
    tokens = [t for t in s.split() if t not in STOP_WORDS and len(t) > 1]
    return " ".join(tokens), set(tokens)

def name_similarity(n1, n2):
    if not n1.strip() or not n2.strip():
        return 0.0
    s1, t1 = clean_core_name(n1)
    s2, t2 = clean_core_name(n2)
    if not s1 or not s2:
        return SequenceMatcher(None, n1.lower().strip(), n2.lower().strip()).ratio()
    if s1 == s2 or (t1 and t2 and (t1.issubset(t2) or t2.issubset(t1))):
        return 0.95
    jacc = len(t1 & t2) / len(t1 | t2) if (t1 | t2) else 0.0
    seq = SequenceMatcher(None, s1, s2).ratio()
    return max(jacc, seq)

print("=== 1. DEEP DIVE ON THE 34 SAME-WARD IDENTICAL-NAME GROUPS (68 ROWS) IN GRID3 ===")
by_ward_name = defaultdict(list)
for r in g3:
    by_ward_name[(r["wardcode"], r["prmry_name"].strip().lower())].append(r)

same_src_count = 0
diff_src_count = 0
for (wc, nm), rows in by_ward_name.items():
    if len(rows) > 1:
        srcs = set(x["source"] for x in rows)
        if len(srcs) == 1:
            same_src_count += 1
        else:
            diff_src_count += 1
print(f"Out of 34 Same-Ward Identical-Name groups (68 rows): {diff_src_count} groups come from DIFFERENT data sources merged together, {same_src_count} come from the same source.")

print("\n=== 2. FUZZY-NAME NEAR-DUPLICATES WITHIN <= 100 METERS INSIDE THE SAME WARD IN GRID3 ===")
by_ward = defaultdict(list)
for r in g3:
    by_ward[r["wardcode"]].append(r)

fuzzy_close_pairs = []
for wc, wrows in by_ward.items():
    n = len(wrows)
    for i in range(n):
        lat1, lon1 = float(wrows[i]["latitude"]), float(wrows[i]["longitude"])
        for j in range(i+1, n):
            lat2, lon2 = float(wrows[j]["latitude"]), float(wrows[j]["longitude"])
            if abs(lat1 - lat2) > 0.001 or abs(lon1 - lon2) > 0.001:
                continue
            d_m = haversine_m(lat1, lon1, lat2, lon2)
            if d_m <= 100.0:
                n1, n2 = wrows[i]["prmry_name"], wrows[j]["prmry_name"]
                sim = name_similarity(n1, n2)
                fuzzy_close_pairs.append((d_m, sim, wrows[i], wrows[j]))

print(f"Total pairs within <= 100m in the same Ward: {len(fuzzy_close_pairs)}")
print(f" - High Name Similarity (sim >= 0.65, likely same facility entered twice): {sum(1 for _, s, _, _ in fuzzy_close_pairs if s >= 0.65)}")
print(f" - Low Name Similarity (sim < 0.65, co-located or stacked GPS points): {sum(1 for _, s, _, _ in fuzzy_close_pairs if s < 0.65)}")
for d_m, sim, r1, r2 in sorted([x for x in fuzzy_close_pairs if x[1] >= 0.65 and x[2]["prmry_name"].lower() != x[3]["prmry_name"].lower()], key=lambda x: x[0])[:10]:
    print(f"   dist={d_m:4.1f}m | sim={sim:.2f} | '{r1['prmry_name']}' ({r1['source']}) <-> '{r2['prmry_name']}' ({r2['source']}) [{r1['statename']}]")

print("\n=== 3. HEALTHSITES 2026: INSPECT THE 2 DUPLICATE OSM_ID ROWS & 2,972 MISSING X/Y ROWS ===")
osm_counts = Counter(r["osm_id"] for r in hs)
for oid, cnt in osm_counts.items():
    if cnt > 1:
        dups = [r for r in hs if r["osm_id"] == oid]
        print(f"Duplicate osm_id={oid} ({cnt} rows): types={[x['osm_type'] for x in dups]}, names={[x['name'] for x in dups]}, coords={[(x['X'], x['Y']) for x in dups]}")
no_xy_types = Counter(r["osm_type"] for r in hs if not r["X"].strip() or not r["Y"].strip())
has_xy_types = Counter(r["osm_type"] for r in hs if r["X"].strip() and r["Y"].strip())
print("Healthsites rows MISSING X/Y by osm_type:", dict(no_xy_types))
print("Healthsites rows WITH valid X/Y by osm_type:", dict(has_xy_types))

print("\n=== 4. CROSS-SYSTEM SPATIAL + FUZZY RECONCILIATION (HEALTHSITES 2026 vs GRID3 MASTER) ===")
# Build spatial grid index (~0.01 deg = ~1.1km cells) on GRID3
grid_index = defaultdict(list)
for r in g3:
    lat, lon = float(r["latitude"]), float(r["longitude"])
    grid_index[(int(lat * 100), int(lon * 100))].append((lat, lon, r))

hs_categories = Counter()
match_examples = []

for r in hs:
    if not r["X"].strip() or not r["Y"].strip():
        hs_categories["HS1_MISSING_COORDINATES_WAY_POLYGON"] += 1
        continue
    lon, lat = float(r["X"]), float(r["Y"])
    amenity = r["amenity"].strip().lower()
    hname = r["name"].strip()

    if amenity == "pharmacy":
        hs_categories["HS2_COMMUNITY_PHARMACY_OUT_OF_GRID3_SCOPE"] += 1
        continue

    # Search nearby GRID3 facilities within ~1.5 km (3x3 grid cells)
    gx, gy = int(lat * 100), int(lon * 100)
    candidates = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for glat, glon, gr in grid_index.get((gx + dx, gy + dy), []):
                d_m = haversine_m(lat, lon, glat, glon)
                if d_m <= 1000.0:
                    sim = name_similarity(hname, gr["prmry_name"])
                    if gr["alt_name"].strip():
                        sim = max(sim, name_similarity(hname, gr["alt_name"]))
                    candidates.append((d_m, sim, gr))

    if not hname:
        # Unnamed Healthsites clinical point
        nearest_d = min((c[0] for c in candidates), default=999999.0)
        if nearest_d <= 300.0:
            hs_categories["HS5_UNNAMED_POINT_NEAR_EXISTING_GRID3_CLINIC_<=300M"] += 1
        else:
            hs_categories["HS6_UNNAMED_UNVERIFIED_CLINICAL_POINT_>300M"] += 1
    else:
        # Named Healthsites clinical facility
        # Match Rule A: High fuzzy name similarity (sim >= 0.60) within <= 1000m OR very close proximity (<= 150m) with moderate similarity
        fuzzy_matches = [c for c in candidates if (c[1] >= 0.60 and c[0] <= 1000.0) or (c[0] <= 150.0 and c[1] >= 0.40)]
        close_any = [c for c in candidates if c[0] <= 250.0]
        if fuzzy_matches:
            best = sorted(fuzzy_matches, key=lambda x: (-x[1], x[0]))[0]
            hs_categories["HS3_PROBABLE_MATCH_IN_GRID3_MASTER (GPS+Fuzzy)"] += 1
            if hname.lower() != best[2]["prmry_name"].lower() and len(match_examples) < 10:
                match_examples.append((best[0], best[1], hname, best[2]["prmry_name"], best[2]["statename"]))
        elif close_any:
            hs_categories["HS4_CO_LOCATED_<=250M_DIFFERENT_FACILITY_NAME"] += 1
        else:
            hs_categories["HS7_NEWLY_MAPPED_NAMED_CLINIC_NOT_IN_GRID3_>250M"] += 1

print("Total Healthsites 2026 rows classified:", sum(hs_categories.values()))
for k, v in sorted(hs_categories.items()):
    print(f"  {k:<55}: {v:>5,} rows ({v/len(hs)*100:.2f}%)")

print("\nSample Cross-System Fuzzy Matches (Different Spelling in Healthsites 2026 vs GRID3 Master):")
for dm, sim, hn, gn, st in match_examples:
    print(f"  dist={dm:5.1f}m | sim={sim:.2f} | Healthsites: '{hn}' <===> GRID3: '{gn}' ({st})")
