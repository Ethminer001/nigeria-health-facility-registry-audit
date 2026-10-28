# Audit of Nigeria's health facility registry: GRID3 checked against Healthsites

An audit of two public datasets: the GRID3 Nigeria health facility registry (46,146 records, June 2024 release) and the Nigeria Healthsites export (7,253 records, September 2026 release). It is a retrospective check on public data, not a client engagement. Python and SQL.

## Results

GRID3 registry:

- 786 facilities (1.70%) have a structural, duplicate or coordinate problem. Each is listed in `grid3_structural_and_duplicate_exceptions.csv`.
- 16,461 facilities (35.67%) have a functional status of Unknown or an ownership of Others. 98.55% of the Unknown statuses (11,583 of 11,753) come from two source feeds, eHA Polio and OSGOF. Unknown means unverified, not closed.
- 29,137 facilities (63.14%) have no flags. Their fields are complete and consistent in the registry. Nobody field-checked them.
- 38 rows have a wrong value in the `type` column, and all 38 are in Borno.
- 168 rows have `(X, Y)` and `(longitude, latitude)` more than 10 m apart, by up to 2.29 km.
- 68 rows (34 pairs) share an exact name inside the same ward, and 504 more sit within 100 m of a similarly named facility in the same ward.
- 13 rows share 6 identical GPS points. Two rows are probably one clinic. The other 11 are different clinics given one placeholder point.

Healthsites against GRID3:

- 2,972 records have no coordinates (they are building outlines, not points) and were left out of matching.
- 1,438 records are pharmacies, which GRID3 does not cover.
- 1,961 records are probable matches to a GRID3 facility: 1,580 high confidence, 195 medium and 186 low.
- 343 records sit within 250 m of a GRID3 facility under a different name.
- 153 records are unnamed pins.
- 2 records are exact duplicate rows in the export.
- 384 named clinical facilities sit more than 250 m from any facility in the GRID3 file.

## Limits

- The two files are two years apart. GRID3 later published v2.0 (December 2024) and v3.0 (August 2026) as GeoPackage files, which I did not use. The 384 facilities are missing from the June 2024 file and may already be in a later one.
- Matches are probable. A Healthsites record matches a GRID3 facility if the names are at least 0.60 similar within 1 km, or at least 0.40 similar within 150 m. The comparison drops generic words such as clinic, hospital and PHC, so a general hospital and a primary health centre with the same place name can match. `match_confidence` is high at 50 m or less, medium up to 250 m, and low beyond that or when similarity is under 0.60. Check the low rows before using them.
- The cut-offs are my choices: 100 m and 0.65 similarity for same-ward duplicates, and 10 m for coordinate drift.
- I do not know why the feeds or coordinates look the way they do. The two feeds appear not to have collected status or ownership. The coordinates may disagree because a pin was moved after the text columns were written. Neither is confirmed.
- The Getso pair has different names, categories and owners, so a field check would settle whether it is one clinic.

## Data

| File | Source | Licence |
|---|---|---|
| GRID3 Nigeria health facilities, 46,146 rows, released 2024-06-05 | https://data.humdata.org/dataset/nigeria-health-care-facilities-in-nigeria | CC BY |
| Nigeria Healthsites, 7,253 rows, released 2026-09-29 | https://data.humdata.org/dataset/nigeria-healthsites | ODbL |

GRID3 Nigeria produced the first with partners. Open Healthsite Consulting publishes the second from OpenStreetMap contributors. The raw files are not stored in this repo. HDX replaces the Healthsites file monthly, so a later download will not match these numbers.

## Reproduce it

Python 3, standard library only.

```
python step0_download_data.py                       # downloads both files into data/
python step1_data_quality_check.py
python step2_deep_dive_investigation.py
python step2b_fuzzy_dedup_and_cross_system.py
python step3_build_registry_exception_csvs.py       # writes the four CSV outputs
```

On the original files, step 3 gives the four committed CSVs exactly.

## Files

- `step0_download_data.py`: downloads both files from HDX.
- `step1_data_quality_check.py`: checks each file on its own.
- `step2_deep_dive_investigation.py`: traces the Unknown statuses, the Borno `type` rows, the coordinate drift and the exact-GPS and same-name rows.
- `step2b_fuzzy_dedup_and_cross_system.py`: finds same-ward near duplicates and matches Healthsites to GRID3.
- `step3_build_registry_exception_csvs.py`: puts every record in one bucket and writes the outputs.
- `registry_audit_queries.sql`: SQL checks of the source gaps, the Borno rows, the exact-GPS rows, the same-ward names and the missing coordinates.
- `grid3_master_summary_by_category.csv`: one row per bucket, covering all 46,146 facilities.
- `grid3_structural_and_duplicate_exceptions.csv`: one row per flagged facility (786).
- `healthsites_2026_reconciliation_summary.csv`: one row per bucket, covering all 7,253 records.
- `healthsites_2026_cross_system_register.csv`: one row per matched, co-located, duplicate or unmatched named record (2,690).
