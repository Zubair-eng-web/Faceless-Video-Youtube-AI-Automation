"""Live test: asli YouTube se trending titles. Usage: python -m scripts.try_trends "space facts" [--language Urdu]"""
import argparse

from app.services import youtube as yt
from app.services.trends import (any_connected_channel, fetch_with_fallback, niche_category,
                                 region_for_language)

ap = argparse.ArgumentParser()
ap.add_argument("niche", nargs="?", default="space facts")
ap.add_argument("--language", default="English")
a = ap.parse_args()

cid = any_connected_channel()
if cid is None:
    raise SystemExit("[FAIL] Koi YouTube token nahi. Pehle: python -m scripts.connect_youtube 1")
region, cat = region_for_language(a.language), niche_category(a.niche)
print(f"Channel token: {cid} | region: {region} | category: {cat or 'general'}")
items = fetch_with_fallback(yt.build_service(yt.load_credentials(cid)), region, cat)
if not items:
    raise SystemExit("[FAIL] Koi trending video nahi mili (quota, token ya scope ka masla ho sakta hai)")
for i in items[:12]:
    print(f"  {i.views:>12,}  {i.title}  [{i.channel}]")
print(f"[OK] {len(items)} trending videos mile")
