import json
import os
import urllib.request
from pystac_client import Client

DOWNLOAD = True   # first run: only list the files. Set to True to download.

catalog = Client.open("https://stac.astrogeology.usgs.gov/api/")

# Read the area of interest from aoi.geojson
with open("aoi.geojson") as f:
    aoi = json.load(f)

search = catalog.search(
    collections=["mro_hirise_uncontrolled_observations"],
    intersects=aoi,
    max_items=10,
)
items = list(search.items())
print(len(items), "items found")

for item in items:
    folder = os.path.join(item.collection_id, item.id)
    for key, asset in item.assets.items():
        print(item.id, key, asset.href)
        if DOWNLOAD:
            os.makedirs(folder, exist_ok=True)
            filename = os.path.join(folder, os.path.basename(asset.href))
            if not os.path.exists(filename):
                print("  downloading...")
                urllib.request.urlretrieve(asset.href, filename)




