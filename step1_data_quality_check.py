import os, csv
from collections import Counter

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def read_csv(fname):
    with open(os.path.join(DATA_DIR, fname), encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

g3 = read_csv("grid3_nga_health_facilities.csv")
hs = read_csv("healthsites_nigeria_2026.csv")

print("=== 1. TABLE 1: GRID3 NIGERIA MASTER HEALTH FACILITY REGISTRY (46,146 rows) ===")
print("Unique globalid:", len(set(r["globalid"] for r in g3)))
print("Unique uniq_id:", len(set(r["uniq_id"] for r in g3)))
print("States count:", len(set(r["statename"] for r in g3)))
print("LGAs count:", len(set((r["statename"], r["lganame"]) for r in g3)))
print("Functional status breakdown:", dict(Counter(r["func_stats"] for r in g3)))
print("Ownership breakdown:", dict(Counter(r["ownership"] for r in g3)))
print("Type breakdown:", dict(Counter(r["type"] for r in g3)))
print("Category breakdown:", dict(Counter(r["category"] for r in g3).most_common(10)))

# Check missing names, bad coordinates, duplicate coordinates, duplicate names in same ward
missing_name = sum(1 for r in g3 if not r["prmry_name"].strip() or r["prmry_name"].strip().lower() in ["unknown", "nil", "none", "n/a"])
# Nigeria bounding box: Lat 4.2 to 13.9 N, Lon 2.6 to 14.7 E
out_of_nga = sum(1 for r in g3 if not (4.0 <= float(r["latitude"]) <= 14.0 and 2.5 <= float(r["longitude"]) <= 15.0))
xy_mismatch = sum(1 for r in g3 if abs(float(r["X"]) - float(r["longitude"])) > 0.001 or abs(float(r["Y"]) - float(r["latitude"])) > 0.001)
coord_counts = Counter((round(float(r["latitude"]), 5), round(float(r["longitude"]), 5)) for r in g3)
exact_coord_dups = sum(cnt for cnt in coord_counts.values() if cnt > 1)
exact_coord_clusters = sum(1 for cnt in coord_counts.values() if cnt > 1)

ward_name_counts = Counter((r["wardcode"], r["prmry_name"].strip().lower()) for r in g3 if r["prmry_name"].strip())
same_ward_same_name = sum(cnt for cnt in ward_name_counts.values() if cnt > 1)
same_ward_same_name_groups = sum(1 for cnt in ward_name_counts.values() if cnt > 1)

print(f" - Missing/blank primary facility name: {missing_name}")
print(f" - Coordinates outside Nigeria bounding box: {out_of_nga}")
print(f" - X/Y vs Longitude/Latitude mismatch: {xy_mismatch}")
print(f" - Facilities sharing exact 5-decimal GPS coordinates: {exact_coord_dups} rows ({exact_coord_clusters} coordinate pairs)")
print(f" - Facilities with identical name inside the exact same Ward: {same_ward_same_name} rows ({same_ward_same_name_groups} groups)")

print("\n=== 2. TABLE 2: HEALTHSITES.IO NIGERIA DIGITAL REGISTRY (7,253 rows, updated Sept 2026) ===")
hs_dates = sorted(r["changeset_timestamp"] for r in hs if r["changeset_timestamp"].strip())
print(f"Changeset timestamp range: {hs_dates[0]} to {hs_dates[-1]}")
print("Unique osm_id:", len(set(r["osm_id"] for r in hs)))
print("Unique (osm_type, osm_id):", len(set((r["osm_type"], r["osm_id"]) for r in hs)))
print("Amenity breakdown:", dict(Counter(r["amenity"] for r in hs).most_common(10)))
hs_missing_name = sum(1 for r in hs if not r["name"].strip())
hs_missing_op = sum(1 for r in hs if not r["operator_type"].strip())
hs_missing_status = sum(1 for r in hs if not r["operational_status"].strip())
hs_no_coords = sum(1 for r in hs if not r["X"].strip() or not r["Y"].strip())
hs_out_nga = sum(1 for r in hs if r["X"].strip() and r["Y"].strip() and not (4.0 <= float(r["Y"]) <= 14.0 and 2.5 <= float(r["X"]) <= 15.0))
print(f" - Missing GPS coordinates (X or Y blank): {hs_no_coords}")
hs_coord_counts = Counter((round(float(r["Y"]), 5), round(float(r["X"]), 5)) for r in hs if r["X"].strip() and r["Y"].strip())
hs_coord_dups = sum(cnt for cnt in hs_coord_counts.values() if cnt > 1)
print(f" - Unnamed facilities/pharmacies (name is blank!): {hs_missing_name:,} ({hs_missing_name/len(hs)*100:.1f}%)")
print(f" - Missing operator_type (public/private unknown): {hs_missing_op:,} ({hs_missing_op/len(hs)*100:.1f}%)")
print(f" - Missing operational_status: {hs_missing_status:,} ({hs_missing_status/len(hs)*100:.1f}%)")
print(f" - Coordinates outside Nigeria bounding box: {hs_out_nga}")
print(f" - Facilities sharing exact 5-decimal GPS coordinates: {hs_coord_dups}")
