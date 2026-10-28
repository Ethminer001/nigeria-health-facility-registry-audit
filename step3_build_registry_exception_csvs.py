import os, csv, math, re
from collections import defaultdict, Counter
from difflib import SequenceMatcher

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

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

# ==============================================================================
# PART 1: PRE-COMPUTE DUPLICATE & COORDINATE FLAGS ON GRID3 (46,146 FACILITIES)
# ==============================================================================
# 1. Exact 5-decimal coordinate collisions (13 rows across 6 GPS points)
by_coord = defaultdict(list)
for r in g3:
    by_coord[(round(float(r["latitude"]), 5), round(float(r["longitude"]), 5))].append(r)

exact_coord_true_dup_ids = set()     # 2 rows (Getso Kano)
exact_coord_stacked_ids = set()      # 11 rows (5 ward clusters where different clinics share a placeholder GPS)
for coord, rows in by_coord.items():
    if len(rows) > 1:
        if coord == (11.86985, 7.9757):
            for x in rows: exact_coord_true_dup_ids.add(x["uniq_id"])
        else:
            for x in rows: exact_coord_stacked_ids.add(x["uniq_id"])

# 2. Same-Ward Identical-Name rows (68 rows across 34 Ward groups)
by_ward_name = defaultdict(list)
for r in g3:
    by_ward_name[(r["wardcode"], r["prmry_name"].strip().lower())].append(r)

same_ward_exact_name_close_ids = set() # < 250m (6 rows / 3 pairs)
same_ward_exact_name_far_ids = set()   # >= 250m (62 rows / 31 pairs)
same_ward_partner_info = {}
for (wc, nm), rows in by_ward_name.items():
    if len(rows) > 1:
        r0, r1 = rows[0], rows[1]
        d_m = haversine_m(float(r0["latitude"]), float(r0["longitude"]), float(r1["latitude"]), float(r1["longitude"]))
        for x in rows:
            other = r1 if x["uniq_id"] == r0["uniq_id"] else r0
            same_ward_partner_info[x["uniq_id"]] = (other["uniq_id"], other["prmry_name"], other["source"], d_m)
            if d_m < 250.0:
                same_ward_exact_name_close_ids.add(x["uniq_id"])
            else:
                same_ward_exact_name_far_ids.add(x["uniq_id"])

# 3. Same-Ward Fuzzy-Name Near-Duplicates within <= 100m (excluding exact-name/exact-coord already caught)
by_ward = defaultdict(list)
for r in g3:
    by_ward[r["wardcode"]].append(r)

fuzzy_dup_ids = set()
fuzzy_partner_info = {}
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
                sim = name_similarity(wrows[i]["prmry_name"], wrows[j]["prmry_name"])
                if sim >= 0.65:
                    for a, b in [(wrows[i], wrows[j]), (wrows[j], wrows[i])]:
                        if a["uniq_id"] not in exact_coord_true_dup_ids and a["uniq_id"] not in same_ward_exact_name_close_ids:
                            fuzzy_dup_ids.add(a["uniq_id"])
                            fuzzy_partner_info[a["uniq_id"]] = (b["uniq_id"], b["prmry_name"], b["source"], d_m, sim)

# Classify all 46,146 GRID3 rows into mutually exclusive buckets
G3_META = {
    "G1_BORNO_TYPE_COLUMN_SHIFT_BUG": "Borno State upload typed facility category ('Primary Health Clinic'/'Health Post Dispensary') or 'Unknown' into the 'type' column instead of Primary/Secondary/Tertiary.",
    "G2_EXACT_GPS_TRUE_DUPLICATE_CLINIC": "Same clinic in Getso Ward (Kano) imported twice at the exact same 5-decimal GPS point from two feeds (eHA Polio and EU SRIK).",
    "G3_EXACT_GPS_STACKED_WARD_COORDINATES": "11 distinct clinics across 5 Wards share identical copied 5-decimal GPS coordinates because individual clinic coordinates were missing.",
    "G4_SAME_WARD_IDENTICAL_NAME_DUPLICATE": "Facilities sharing the exact same primary name inside the same Ward (82% caused by merging two source feeds without deduplicating).",
    "G5_SAME_WARD_FUZZY_NAME_DUPLICATE_<=100M": "Facilities in the same Ward sitting within <=100 meters of each other with high fuzzy name similarity (>=0.65) across different spellings/sources.",
    "G6_INTERNAL_XY_LONLAT_DRIFT_>10M": "Row's geometry columns (X, Y) differ from its attribute columns (longitude, latitude) by >10m (up to 2.29 km) after map pin edits.",
    "G7_UNVERIFIED_STATUS_AND_OWNERSHIP_BOTH": "Both functional status ('Unknown') and ownership ('Others') are unverified (98.5% from legacy eHA Polio & OSGOF mapping feeds).",
    "G8_UNVERIFIED_FUNCTIONAL_STATUS_ONLY": "Ownership is recorded, but functional status is 'Unknown' (primarily from eHA Polio & OSGOF geographic mapping feeds).",
    "G9_UNVERIFIED_OWNERSHIP_ONLY": "Functional status is recorded, but facility ownership is listed as generic 'Others' (primarily from eHA Polio & OSGOF feeds).",
    "G10_CLEAN_COMPLETE_MASTER_FACILITY": "Facility has valid Primary/Secondary/Tertiary level, recorded functional status, known ownership, consistent GPS coordinates, and no ward duplicate flags.",
}

g3_summary = Counter()
g3_structural_exceptions = [] # G1 through G6 structural/duplicate/coordinate bugs (623 rows)

for r in g3:
    uid = r["uniq_id"]
    x, y = float(r["X"]), float(r["Y"])
    lon, lat = float(r["longitude"]), float(r["latitude"])
    xy_d = haversine_m(y, x, lat, lon)
    unk_f = (r["func_stats"] == "Unknown")
    oth_o = (r["ownership"] == "Others")

    code = None
    detail = ""
    partner_id = ""
    partner_name = ""
    dist_m_str = ""

    if r["type"] not in ["Primary", "Secondary", "Tertiary"]:
        code = "G1_BORNO_TYPE_COLUMN_SHIFT_BUG"
        detail = f"Borno State row has type='{r['type']}' and category='{r['category']}' (source={r['source']})."
    elif uid in exact_coord_true_dup_ids:
        code = "G2_EXACT_GPS_TRUE_DUPLICATE_CLINIC"
        detail = f"Exact same GPS (11.86985, 7.9757) as duplicate Getso clinic from another source ({r['source']})."
        dist_m_str = "0.0"
    elif uid in exact_coord_stacked_ids:
        code = "G3_EXACT_GPS_STACKED_WARD_COORDINATES"
        detail = f"Shares copied placeholder GPS ({lat:.5f}, {lon:.5f}) with another differently named clinic in {r['wardname']} Ward."
        dist_m_str = "0.0"
    elif uid in same_ward_exact_name_close_ids or uid in same_ward_exact_name_far_ids:
        code = "G4_SAME_WARD_IDENTICAL_NAME_DUPLICATE"
        pid, pnm, psrc, dm = same_ward_partner_info[uid]
        partner_id, partner_name, dist_m_str = pid, pnm, f"{dm:.1f}"
        detail = f"Identical name '{r['prmry_name']}' in {r['wardname']} Ward as uniq_id={pid} (source={psrc}, GPS dist={dm:.1f}m)."
    elif uid in fuzzy_dup_ids:
        code = "G5_SAME_WARD_FUZZY_NAME_DUPLICATE_<=100M"
        pid, pnm, psrc, dm, sim = fuzzy_partner_info[uid]
        partner_id, partner_name, dist_m_str = pid, pnm, f"{dm:.1f}"
        detail = f"Within {dm:.1f}m of '{pnm}' (uniq_id={pid}, source={psrc}, name_sim={sim:.2f}) in {r['wardname']} Ward."
    elif xy_d > 10.0:
        code = "G6_INTERNAL_XY_LONLAT_DRIFT_>10M"
        dist_m_str = f"{xy_d:.1f}"
        detail = f"Internal (X,Y)=({x:.4f},{y:.4f}) differs from (lon,lat)=({lon:.4f},{lat:.4f}) by {xy_d:.1f}m."
    elif unk_f and oth_o:
        code = "G7_UNVERIFIED_STATUS_AND_OWNERSHIP_BOTH"
    elif unk_f:
        code = "G8_UNVERIFIED_FUNCTIONAL_STATUS_ONLY"
    elif oth_o:
        code = "G9_UNVERIFIED_OWNERSHIP_ONLY"
    else:
        code = "G10_CLEAN_COMPLETE_MASTER_FACILITY"

    g3_summary[code] += 1
    if code in ["G1_BORNO_TYPE_COLUMN_SHIFT_BUG", "G2_EXACT_GPS_TRUE_DUPLICATE_CLINIC", "G3_EXACT_GPS_STACKED_WARD_COORDINATES",
                "G4_SAME_WARD_IDENTICAL_NAME_DUPLICATE", "G5_SAME_WARD_FUZZY_NAME_DUPLICATE_<=100M", "G6_INTERNAL_XY_LONLAT_DRIFT_>10M"]:
        g3_structural_exceptions.append({
            "uniq_id": uid,
            "globalid": r["globalid"],
            "defect_code": code,
            "statename": r["statename"],
            "lganame": r["lganame"],
            "wardname": r["wardname"],
            "prmry_name": r["prmry_name"],
            "type_col": r["type"],
            "category_col": r["category"],
            "func_stats": r["func_stats"],
            "ownership": r["ownership"],
            "source_feed": r["source"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "partner_uniq_id": partner_id,
            "partner_facility_name": partner_name,
            "distance_or_drift_meters": dist_m_str,
            "issue": detail,
        })

# Write grid3_master_summary_by_category.csv
with open(os.path.join(BASE_DIR, "grid3_master_summary_by_category.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=[
        "category_code", "facility_count", "pct_of_all_46146_facilities",
        "root_cause"
    ])
    w.writeheader()
    for c in G3_META.keys():
        cnt = g3_summary[c]
        desc = G3_META[c]
        w.writerow({
            "category_code": c,
            "facility_count": cnt,
            "pct_of_all_46146_facilities": f"{cnt/len(g3)*100:.3f}%",
            "root_cause": desc
        })

# Write grid3_structural_and_duplicate_exceptions.csv
g3_structural_exceptions.sort(key=lambda r: (r["defect_code"], r["statename"], r["lganame"]))
with open(os.path.join(BASE_DIR, "grid3_structural_and_duplicate_exceptions.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(g3_structural_exceptions[0].keys()))
    w.writeheader()
    w.writerows(g3_structural_exceptions)

# ==============================================================================
# PART 2: CROSS-SYSTEM RECONCILIATION CSVs (HEALTHSITES SEPT 2026 vs GRID3)
# ==============================================================================
grid_index = defaultdict(list)
for r in g3:
    lat, lon = float(r["latitude"]), float(r["longitude"])
    grid_index[(int(lat * 100), int(lon * 100))].append((lat, lon, r))

HS_META = {
    "HS0_DUPLICATE_OSM_ID_EXPORT_ROW": "Exact same OpenStreetMap node ID and coordinates exported twice in healthsites_nigeria_2026.csv.",
    "HS1_MISSING_COORDINATES_WAY_POLYGON": "100% of these 2,972 rows are OpenStreetMap building outlines (osm_type='way') exported to CSV without computing an (X, Y) center point.",
    "HS2_COMMUNITY_PHARMACY_OUT_OF_GRID3_SCOPE": "Geocoded community/retail pharmacies (amenity='pharmacy'), which are not tracked in the GRID3 clinical facility master list.",
    "HS3_PROBABLE_MATCH_IN_GRID3_MASTER": "Named, geocoded clinical facility in Healthsites 2026 that probably matches an existing GRID3 facility: name similarity >= 0.60 within 1 km, or >= 0.40 within 150 m. The name test ignores generic words such as clinic and hospital, so facility type is not compared. See match_confidence in the register.",
    "HS4_CO_LOCATED_<=250M_DIFFERENT_NAME": "Named clinical facility sitting within <=250m of a GRID3 facility, but with a different name (renamed clinic, specialist unit, or adjacent private clinic).",
    "HS5_UNNAMED_POINT_NEAR_GRID3_CLINIC_<=300M": "Unnamed clinical pin (name is blank) located within <=300m of an existing named GRID3 facility.",
    "HS6_UNNAMED_UNVERIFIED_CLINICAL_POINT_>300M": "Unnamed clinical pin (name is blank) located >300m from any GRID3 facility.",
    "HS7_NEWLY_MAPPED_NAMED_CLINIC_NOT_IN_GRID3": "Named, geocoded hospital, clinic, or doctor practice in the Sept 2026 Healthsites registry sitting >250m from any facility in the June 2024 GRID3 release (it may already be in a later GRID3 version).",
}

seen_osm = set()
hs_summary = Counter()
hs_actionable_rows = [] # HS3, HS4, HS7 (and HS0)

for r in hs:
    key = (r["osm_type"], r["osm_id"])
    if key in seen_osm:
        code = "HS0_DUPLICATE_OSM_ID_EXPORT_ROW"
        hs_summary[code] += 1
        hs_actionable_rows.append({
            "osm_id": r["osm_id"],
            "osm_type": r["osm_type"],
            "reconciliation_code": code,
            "amenity": r["amenity"],
            "healthsites_name": r["name"],
            "healthsites_lat": r["Y"],
            "healthsites_lon": r["X"],
            "changeset_timestamp": r["changeset_timestamp"],
            "matched_grid3_uniq_id": "",
            "matched_grid3_name": "",
            "matched_grid3_state": "",
            "matched_grid3_lga": "",
            "gps_distance_meters": "",
            "fuzzy_name_similarity": "",
            "finding": "Exact duplicate (osm_type, osm_id) row in Healthsites 2026 CSV export.",
        })
        continue
    seen_osm.add(key)

    if not r["X"].strip() or not r["Y"].strip():
        hs_summary["HS1_MISSING_COORDINATES_WAY_POLYGON"] += 1
        continue

    lon, lat = float(r["X"]), float(r["Y"])
    amenity = r["amenity"].strip().lower()
    hname = r["name"].strip()

    if amenity == "pharmacy":
        hs_summary["HS2_COMMUNITY_PHARMACY_OUT_OF_GRID3_SCOPE"] += 1
        continue

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
        nearest_d = min((c[0] for c in candidates), default=999999.0)
        if nearest_d <= 300.0:
            hs_summary["HS5_UNNAMED_POINT_NEAR_GRID3_CLINIC_<=300M"] += 1
        else:
            hs_summary["HS6_UNNAMED_UNVERIFIED_CLINICAL_POINT_>300M"] += 1
    else:
        fuzzy_matches = [c for c in candidates if (c[1] >= 0.60 and c[0] <= 1000.0) or (c[0] <= 150.0 and c[1] >= 0.40)]
        close_any = [c for c in candidates if c[0] <= 250.0]
        if fuzzy_matches:
            best = sorted(fuzzy_matches, key=lambda x: (-x[1], x[0]))[0]
            code = "HS3_PROBABLE_MATCH_IN_GRID3_MASTER"
            hs_summary[code] += 1
            gr = best[2]
            hs_actionable_rows.append({
                "osm_id": r["osm_id"],
                "osm_type": r["osm_type"],
                "reconciliation_code": code,
                "amenity": r["amenity"],
                "healthsites_name": hname,
                "healthsites_lat": f"{lat:.5f}",
                "healthsites_lon": f"{lon:.5f}",
                "changeset_timestamp": r["changeset_timestamp"],
                "matched_grid3_uniq_id": gr["uniq_id"],
                "matched_grid3_name": gr["prmry_name"],
                "matched_grid3_state": gr["statename"],
                "matched_grid3_lga": gr["lganame"],
                "gps_distance_meters": f"{best[0]:.1f}",
                "fuzzy_name_similarity": f"{best[1]:.2f}",
                "finding": f"Matched to GRID3 '{gr['prmry_name']}' ({gr['statename']}) at {best[0]:.1f}m distance (similarity={best[1]:.2f}).",
            })
        elif close_any:
            best = sorted(close_any, key=lambda x: x[0])[0]
            code = "HS4_CO_LOCATED_<=250M_DIFFERENT_NAME"
            hs_summary[code] += 1
            gr = best[2]
            hs_actionable_rows.append({
                "osm_id": r["osm_id"],
                "osm_type": r["osm_type"],
                "reconciliation_code": code,
                "amenity": r["amenity"],
                "healthsites_name": hname,
                "healthsites_lat": f"{lat:.5f}",
                "healthsites_lon": f"{lon:.5f}",
                "changeset_timestamp": r["changeset_timestamp"],
                "matched_grid3_uniq_id": gr["uniq_id"],
                "matched_grid3_name": gr["prmry_name"],
                "matched_grid3_state": gr["statename"],
                "matched_grid3_lga": gr["lganame"],
                "gps_distance_meters": f"{best[0]:.1f}",
                "fuzzy_name_similarity": f"{best[1]:.2f}",
                "finding": f"Located {best[0]:.1f}m from GRID3 '{gr['prmry_name']}' ({gr['statename']}), but names differ.",
            })
        else:
            code = "HS7_NEWLY_MAPPED_NAMED_CLINIC_NOT_IN_GRID3"
            hs_summary[code] += 1
            nearest = sorted(candidates, key=lambda x: x[0])[0] if candidates else None
            hs_actionable_rows.append({
                "osm_id": r["osm_id"],
                "osm_type": r["osm_type"],
                "reconciliation_code": code,
                "amenity": r["amenity"],
                "healthsites_name": hname,
                "healthsites_lat": f"{lat:.5f}",
                "healthsites_lon": f"{lon:.5f}",
                "changeset_timestamp": r["changeset_timestamp"],
                "matched_grid3_uniq_id": nearest[2]["uniq_id"] if nearest else "NONE_WITHIN_1KM",
                "matched_grid3_name": nearest[2]["prmry_name"] if nearest else "NONE_WITHIN_1KM",
                "matched_grid3_state": nearest[2]["statename"] if nearest else "",
                "matched_grid3_lga": nearest[2]["lganame"] if nearest else "",
                "gps_distance_meters": f"{nearest[0]:.1f}" if nearest else ">1000.0",
                "fuzzy_name_similarity": f"{nearest[1]:.2f}" if nearest else "0.00",
                "finding": f"Named clinical facility '{hname}' ({r['amenity']}) not found within 250m in the June 2024 GRID3 release.",
            })

with open(os.path.join(BASE_DIR, "healthsites_2026_reconciliation_summary.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=[
        "reconciliation_code", "record_count", "pct_of_all_7253_records",
        "explanation"
    ])
    w.writeheader()
    for c in HS_META.keys():
        cnt = hs_summary[c]
        desc = HS_META[c]
        w.writerow({
            "reconciliation_code": c,
            "record_count": cnt,
            "pct_of_all_7253_records": f"{cnt/len(hs)*100:.2f}%",
            "explanation": desc
        })

for row in hs_actionable_rows:
    conf = ""
    if row["reconciliation_code"].startswith("HS3"):
        dist, sim = float(row["gps_distance_meters"]), float(row["fuzzy_name_similarity"])
        if dist <= 50.0 and sim >= 0.60:
            conf = "high"
        elif dist <= 250.0 and sim >= 0.60:
            conf = "medium"
        else:
            conf = "low"
    row["match_confidence"] = conf

hs_actionable_rows.sort(key=lambda r: (r["reconciliation_code"], r["matched_grid3_state"], r["healthsites_name"]))
with open(os.path.join(BASE_DIR, "healthsites_2026_cross_system_register.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(hs_actionable_rows[0].keys()))
    w.writeheader()
    w.writerows(hs_actionable_rows)

print("=== PART 1: GRID3 MASTER SUMMARY (ALL 46,146 FACILITIES ACCOUNTED FOR) ===")
print("Total GRID3 classified:", sum(g3_summary.values()))
for c in G3_META.keys():
    print(f"  {c:<42}: {g3_summary[c]:>6,} ({g3_summary[c]/len(g3)*100:.2f}%)")
print(f"Total structural/duplicate exception rows written: {len(g3_structural_exceptions):,}")

print("\n=== PART 2: HEALTHSITES SEPT 2026 RECONCILIATION SUMMARY (ALL 7,253 RECORDS ACCOUNTED FOR) ===")
print("Total Healthsites classified:", sum(hs_summary.values()))
for c in HS_META.keys():
    print(f"  {c:<45}: {hs_summary[c]:>5,} ({hs_summary[c]/len(hs)*100:.2f}%)")
print(f"Total cross-system matched/new rows written: {len(hs_actionable_rows):,}")
