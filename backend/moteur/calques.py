"""Calques raster : GeoTIFF de tifs/ -> PNG colorises (+ legende) pour la carte Leaflet.

Les PNG sont recadres comme la grille (multiple de `facteur` pixels) pour tomber pile sur les bornes [[0,0],[H,W]].
"""
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

PENTE = [(0, (25, 55, 95)), (.5, (215, 185, 80)), (1, (215, 60, 40))]      # = fond.png (donnees_mnt.generer_fond_pente)
RISQUE = [(0, (60, 170, 90)), (.5, (240, 210, 60)), (1, (215, 50, 40))]
CONFIANCE = [(0, (215, 50, 40)), (.5, (240, 210, 60)), (1, (60, 170, 90))]
GRIS = [(0, (0, 0, 0)), (1, (255, 255, 255))]

# id, titre, fichier, type, palette, vmin, vmax, unite, (etiquette bas, etiquette haut)
DEFINITIONS = [
    ("ombrage", "Ombrage", "ombrage.tif", "fond", GRIS, 0, 255, "", ("ombre", "lumière")),
    ("risque", "Risque", "calcul_risque.tif", "surcouche", RISQUE, 0, 1, "", ("faible", "élevé")),
    ("confiance", "Confiance", "confiance.tif", "surcouche", CONFIANCE, 0, 1, "", ("basse", "haute")),
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


def construire_calques(dossier_tifs, dossier_front, plage_pente=None, facteur=5):
    sortie = dossier_front / "calques"
    sortie.mkdir(exist_ok=True)
    calques = []
    fond = dossier_front / "fond.png"
    if fond.exists():
        lo, hi = plage_pente if plage_pente else (None, None)
        calques.append({"id": "pente", "titre": "Pente", "type": "fond",
                        "url": f"/fond.png?v={int(fond.stat().st_mtime)}",
                        "legende": _legende(PENTE, lo, hi, "°", ("plat", "raide"),
                                            "contraste étiré sur les percentiles 2-98" if plage_pente else None)})
    for cid, titre, fichier, type_, palette, vmin, vmax, unite, etiq in DEFINITIONS:
        chemin = dossier_tifs / fichier
        if not chemin.exists():
            continue
        a = _recadrer(_lire(chemin), facteur)
        if cid == "ombrage":
            a[a == 0] = np.nan                       # 0 = pas de donnee
        Image.fromarray(_coloriser(a, palette, vmin, vmax), "RGBA").save(sortie / f"{cid}.png")
        note = None
        if np.isfinite(a).any() and np.nanmin(a) == np.nanmax(a):
            note = f"Calque uniforme (valeur {np.nanmin(a):g}) : export à vérifier"
        calques.append({"id": cid, "titre": titre, "type": type_,
                        "url": f"/calques/{cid}.png?v={int(chemin.stat().st_mtime)}",
                        "legende": _legende(palette, vmin, vmax, unite, etiq, note)})
    return calques