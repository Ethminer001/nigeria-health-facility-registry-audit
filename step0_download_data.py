import os, urllib.request

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
URLS = {
    # GRID3 Nigeria health facilities, HDX release 2024-06-05 (CC BY)
    "grid3_nga_health_facilities.csv": "https://data.humdata.org/dataset/bfd0888d-ca7f-40ec-b1e7-97eb3fe15dc2/resource/1ad3ca9f-d8f0-4c13-8e57-246c2f834c4e/download/grid3_nga_-_health_facilities_-1.csv",
    # Nigeria Healthsites, HDX release 2026-09-29 (ODbL). HDX replaces this file monthly,
    # so a later download will not match the published numbers.
    "healthsites_nigeria_2026.csv": "https://data.humdata.org/dataset/fea18f4e-0463-4194-a21c-602e48e098e1/resource/1b4b743d-3619-4b42-ba11-f4936b7935d7/download/nigeria.csv",
}

os.makedirs(DATA_DIR, exist_ok=True)
for fname, url in URLS.items():
    fpath = os.path.join(DATA_DIR, fname)
    if os.path.exists(fpath):
        print("exists, skipped:", fname)
        continue
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(fpath, "wb") as out:
        out.write(resp.read())
    print("downloaded:", fname, os.path.getsize(fpath), "bytes")
