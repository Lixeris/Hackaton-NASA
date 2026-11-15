"""Calques raster : GeoTIFF de tifs/ -> PNG colorises (+ legende) pour la carte Leaflet.

Les PNG sont recadres comme la grille (multiple de `facteur` pixels) pour tomber pile sur les bornes [[0,0],[H,W]].
"""
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

DENIVELE = [(0, (25, 55, 95)), (.5, (215, 185, 80)), (1, (215, 60, 40))]
DANGER = [(0, (60, 170, 90)), (.5, (240, 210, 60)), (1, (215, 50, 40))]
EXPOSITION = [(0, (40, 30, 90)), (.5, (190, 70, 120)), (1, (250, 220, 120))]

# id, titre, fichier, palette, vmin, vmax, unite, (etiquette bas, etiquette haut)
# vmin/vmax = None -> echelle calculee sur les percentiles 2-98 des donnees ; un fichier absent est simplement ignore
DEFINITIONS = [
    ("exposition", "Exposure", "exposition.tif", EXPOSITION, None, None, "", ("low", "high")),
    ("danger", "Danger", "danger.tif", DANGER, None, None, "", ("low", "high")),
    ("denivele", "Elevation", "denivele.tif", DENIVELE, 0, 50, "%", ("flat", "steep")),
]


def _hex(rgb):
    return "#%02x%02x%02x" % rgb


def _lire(chemin):
    im = Image.open(chemin)
    a = np.array(im, dtype="float64")
    nodata = im.tag_v2.get(42113)
    if nodata is not None:
        try:
            a[a == float(nodata)] = np.nan
        except ValueError:
            pass
    a[a < -1e30] = np.nan
    return a


def _recadrer(a, facteur):
    return a[:(a.shape[0] // facteur) * facteur, :(a.shape[1] // facteur) * facteur]


def _coloriser(a, palette, vmin, vmax):
    ok = np.isfinite(a)
    t = np.clip((np.where(ok, a, vmin) - vmin) / max(vmax - vmin, 1e-9), 0, 1)
    pos = [p for p, _ in palette]
    rgb = [np.interp(t, pos, [c[k] for _, c in palette]) for k in range(3)]
    return np.dstack(rgb + [np.where(ok, 255, 0)]).astype("uint8")


def _legende(palette, vmin, vmax, unite, etiquettes, note=None):
    return {"stops": [[p, _hex(c)] for p, c in palette], "min": vmin, "max": vmax,
            "unite": unite, "etiquettes": list(etiquettes), "note": note}


def construire_calques(dossier_tifs, dossier_front, facteur=5):
    """Surcouches : denivele, risque, exposition. Le fond (frontend/fond.png) est charge directement par la page."""
    sortie = dossier_front / "calques"
    sortie.mkdir(exist_ok=True)
    calques = []
    for cid, titre, fichier, palette, vmin, vmax, unite, etiq in DEFINITIONS:
        chemin = dossier_tifs / fichier
        if not chemin.exists():
            continue
        a = _recadrer(_lire(chemin), facteur)
        if vmin is None or vmax is None:
            ok = a[np.isfinite(a)]
            vmin, vmax = (float(x) for x in np.percentile(ok, [2, 98])) if ok.size else (0.0, 1.0)
            if vmax <= vmin:
                vmax = vmin + 1e-9
        Image.fromarray(_coloriser(a, palette, vmin, vmax), "RGBA").save(sortie / f"{cid}.png")
        note = None
        if np.isfinite(a).any() and np.nanmin(a) == np.nanmax(a):
            note = f"Uniform layer (value {np.nanmin(a):g}): check the export"
        calques.append({"id": cid, "titre": titre, "type": "surcouche",
                        "url": f"/calques/{cid}.png?v={int(chemin.stat().st_mtime)}",
                        "legende": _legende(palette, vmin, vmax, unite, etiq, note)})
    return calques