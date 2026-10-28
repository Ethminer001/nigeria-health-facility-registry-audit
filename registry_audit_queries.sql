-- ============================================================================
-- NIGERIAN MASTER HEALTH FACILITY REGISTRY AUDIT (SQL QUERIES)
-- Tables: grid3_nga_health_facilities (46,146), healthsites_nigeria_2026 (7,253)
-- ============================================================================

-- 1. Root Cause Check: Which data sources caused the 11,753 'Unknown' functional
--    statuses and 9,895 'Others' ownership records in GRID3?
SELECT
    source,
    COUNT(*) AS total_facilities,
    SUM(CASE WHEN func_stats = 'Unknown' THEN 1 ELSE 0 END) AS unknown_func_status_count,
    SUM(CASE WHEN ownership = 'Others' THEN 1 ELSE 0 END) AS others_ownership_count,
    SUM(CASE WHEN func_stats = 'Unknown' AND ownership = 'Others' THEN 1 ELSE 0 END) AS both_unverified_count
FROM grid3_nga_health_facilities
GROUP BY source
HAVING unknown_func_status_count > 0 OR others_ownership_count > 0
ORDER BY unknown_func_status_count DESC;

-- 2. Schema Bug Check: Identify all 38 rows where 'type' is not Primary/Secondary/Tertiary
--    (Proves 100% are in Borno State where category was typed into the 'type' column)
SELECT
    statename,
    source,
    type AS corrupted_type_column,
    category AS category_column,
    COUNT(*) AS row_count
FROM grid3_nga_health_facilities
WHERE type NOT IN ('Primary', 'Secondary', 'Tertiary')
GROUP BY statename, source, type, category
ORDER BY row_count DESC;

-- 3. Exact 5-Decimal GPS Coordinate Collisions in GRID3 (13 rows across 6 GPS points)
WITH coord_clusters AS (
    SELECT
        ROUND(CAST(latitude AS REAL), 5) AS lat_5,
        ROUND(CAST(longitude AS REAL), 5) AS lon_5,
        COUNT(*) AS cluster_size
    FROM grid3_nga_health_facilities
    GROUP BY ROUND(CAST(latitude AS REAL), 5), ROUND(CAST(longitude AS REAL), 5)
    HAVING COUNT(*) > 1
)
SELECT
    g.uniq_id,
    g.statename,
    g.lganame,
    g.wardname,
    g.prmry_name,
    g.category,
    g.source,
    ROUND(CAST(g.latitude AS REAL), 5) AS lat_5,
    ROUND(CAST(g.longitude AS REAL), 5) AS lon_5
FROM grid3_nga_health_facilities g
JOIN coord_clusters c
  ON ROUND(CAST(g.latitude AS REAL), 5) = c.lat_5
 AND ROUND(CAST(g.longitude AS REAL), 5) = c.lon_5
ORDER BY lat_5, lon_5, g.uniq_id;

-- 4. Same-Ward Identical Facility Name Collisions in GRID3 (68 rows across 34 Wards)
WITH ward_name_dups AS (
    SELECT
        wardcode,
        LOWER(TRIM(prmry_name)) AS norm_name,
        COUNT(*) AS dup_count
    FROM grid3_nga_health_facilities
    GROUP BY wardcode, LOWER(TRIM(prmry_name))
    HAVING COUNT(*) > 1
)
SELECT
    g.uniq_id,
    g.statename,
    g.lganame,
    g.wardname,
    g.prmry_name,
    g.source,
    g.latitude,
    g.longitude
FROM grid3_nga_health_facilities g
JOIN ward_name_dups w
  ON g.wardcode = w.wardcode
 AND LOWER(TRIM(g.prmry_name)) = w.norm_name
ORDER BY g.statename, g.wardname, g.prmry_name;

-- 5. Healthsites 2026 Audit: Prove 100% of the 2,972 missing X/Y rows are osm_type = 'way'
SELECT
    osm_type,
    SUM(CASE WHEN TRIM(X) = '' OR TRIM(Y) = '' THEN 1 ELSE 0 END) AS missing_xy_coords,
    SUM(CASE WHEN TRIM(X) != '' AND TRIM(Y) != '' THEN 1 ELSE 0 END) AS valid_xy_coords,
    COUNT(*) AS total_rows
FROM healthsites_nigeria_2026
GROUP BY osm_type;
