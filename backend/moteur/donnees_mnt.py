"""Construit la grille (pente + risque) directement depuis le MNT CTX 20 m de Jezero.

Dependances : numpy + Pillow (pas besoin de GDAL / rasterio).
"""
import math

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

# Ancienne zone 10 km x 10 km (inutilisee : les nouveaux TIF sont deja decoupes)
ZONE_10KM = (4583443.25, 1088613.14, 4593463.25, 1098633.14)  # xmin, ymin, xmax, ymax


def lire_mnt(chemin):
    """Retourne (altitudes[m], taille_pixel_m, (x_ouest, y_nord)) depuis un GeoTIFF float32."""
    im = Image.open(chemin)
    tags = im.tag_v2
    pixel = float(tags[33550][0])              # ModelPixelScale
    x0, y0 = tags[33922][3], tags[33922][4]    # ModelTiepoint (coin haut-gauche)
    z = np.array(im, dtype="float64")
    nodata = float(tags[42113]) if 42113 in tags else None
    if nodata is not None:
        z[z == nodata] = np.nan
    return z, pixel, (x0, y0)


def decouper(z, pixel, origine, zone):
    xmin, ymin, xmax, ymax = zone
    x0, y0 = origine
    c0, c1 = int(round((xmin - x0) / pixel)), int(round((xmax - x0) / pixel))
    r0, r1 = int(round((y0 - ymax) / pixel)), int(round((y0 - ymin) / pixel))
    return z[r0:r1, c0:c1], (x0 + c0 * pixel, y0 - r0 * pixel)


def pente_degres(z, pixel):
    """Pente de Horn (meme methode que l'outil 'Pente' de QGIS/GDAL), en degres."""
    p = np.pad(z, 1, mode="edge")
    a, b, c = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]
    d, f = p[1:-1, :-2], p[1:-1, 2:]
    g, h, i = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * pixel)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * pixel)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy)))


def _blocs(a, f):
    h, w = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    return a[:h, :w].reshape(h // f, f, w // f, f).transpose(0, 2, 1, 3).reshape(h // f, w // f, f * f)


def _grille_depuis_pente(pente, pixel, origine, facteur):
    """Coeur commun : pente (degres, pixel d'origine) -> grille agregee + metadonnees."""
    b = _blocs(pente, facteur)
    pente_cell = np.nanpercentile(b, 90, axis=2)   # pente "pessimiste" du bloc
    rugosite = np.nanstd(b, axis=2)                # variabilite de pente = terrain accidente
    # Risque proxy 0..1 : rugosite normalisee (a remplacer par une vraie couche de risque si dispo)
    risque = np.clip(rugosite / np.nanpercentile(rugosite, 98), 0, 1)

    grille = {}
    for i in range(pente_cell.shape[0]):
        for j in range(pente_cell.shape[1]):
            ok = not (np.isnan(pente_cell[i, j]) or np.isnan(risque[i, j]))
            grille[(i, j)] = {
                "pente_deg": float(pente_cell[i, j]) if ok else 90.0,
                "risque_terrain": float(risque[i, j]) if ok else 1.0,
                "confiance": "haute" if ok else "basse",
            }
    meta = {
        "taille_cellule_m": pixel * facteur,
        "origine_xy": origine,   # coin haut-gauche de la grille (m)
        "shape": pente_cell.shape,
    }
    return grille, max(pente_cell.shape), meta


def grille_depuis_mnt(chemin_mnt, zone=ZONE_10KM, facteur=5):
    """Si tu as le MNT (altitudes) : la pente est calculee ici (methode de Horn)."""
    z, pixel, origine = lire_mnt(chemin_mnt)
    if zone is not None:
        z, origine = decouper(z, pixel, origine, zone)
    return _grille_depuis_pente(pente_degres(z, pixel), pixel, origine, facteur)


def grille_depuis_pente(chemin_pente, zone=None, facteur=5, unite="deg"):
    """Si tu as DIRECTEMENT le raster de pentes (ex. 'pente jerezo 10km.tif' exporte de QGIS).

    unite : "deg" (degres) ou "pct" (pourcentage de pente, converti en degres).
    zone  : None si le raster est deja decoupe sur la zone voulue.
    """
    p, pixel, origine = lire_mnt(chemin_pente)
    if zone is not None:
        p, origine = decouper(p, pixel, origine, zone)
    if unite == "pct":
        p = np.degrees(np.arctan(p / 100.0))
    return _grille_depuis_pente(p, pixel, origine, facteur)


def generer_fond_pente(chemin_pente, sortie_png, zone=None, facteur=5, unite="deg"):
    """Fond de carte colore a partir des pentes : bleu = plat, jaune = moyen, rouge = raide.

    Contraste etire sur les percentiles 2-98 pour que le relief soit bien visible.
    """
    p, pixel, origine = lire_mnt(chemin_pente)
    if zone is not None:
        p, origine = decouper(p, pixel, origine, zone)
    if unite == "pct":
        p = np.degrees(np.arctan(p / 100.0))
    h, w = (p.shape[0] // facteur) * facteur, (p.shape[1] // facteur) * facteur
    p = p[:h, :w]
    valide = np.isfinite(p)
    lo, hi = np.nanpercentile(p, [2, 98])
    t = np.clip((np.where(valide, p, lo) - lo) / max(hi - lo, 1e-6), 0, 1)
    arret = [0.0, 0.5, 1.0]
    rgb = np.dstack([
        np.interp(t, arret, [25, 215, 215]),    # R
        np.interp(t, arret, [55, 185, 60]),     # G
        np.interp(t, arret, [95, 80, 40]),      # B
    ])
    rgb[~valide] = (20, 20, 20)                 # donnees manquantes : gris fonce
    Image.fromarray(rgb.astype("uint8")).save(sortie_png)
    return float(lo), float(hi)   # plage de pente (deg) pour la legende


def cellule_vers_xy(i, j, meta):
    """Centre de la cellule (i, j) en coordonnees projetees (m)."""
    t = meta["taille_cellule_m"]
    x0, y0 = meta["origine_xy"]
    return x0 + (j + 0.5) * t, y0 - (i + 0.5) * t


def xy_vers_cellule(x, y, meta):
    t = meta["taille_cellule_m"]
    x0, y0 = meta["origine_xy"]
    return int((y0 - y) // t), int((x - x0) // t)


def longueur_chemin_m(chemin, taille_cellule_m):
    return taille_cellule_m * sum(
        ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 for a, b in zip(chemin, chemin[1:])
    )


def generer_fond(chemin_mnt, sortie_png, zone=ZONE_10KM, facteur=5):
    """Ombrage du relief (PNG) pour l'afficher sous la carte Leaflet.

    L'image couvre exactement la grille (shape * facteur pixels de MNT).
    """
    z, pixel, origine = lire_mnt(chemin_mnt)
    if zone is not None:
        z, origine = decouper(z, pixel, origine, zone)
    h, w = (z.shape[0] // facteur) * facteur, (z.shape[1] // facteur) * facteur
    z = z[:h, :w]
    p = np.pad(z, 1, mode="edge")
    a, b, c = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]
    d, f = p[1:-1, :-2], p[1:-1, 2:]
    g, hh, i = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * pixel)   # est - ouest
    dzdy = ((g + 2 * hh + i) - (a + 2 * b + c)) / (8 * pixel)  # sud - nord
    normale = np.dstack([-dzdx, dzdy, np.ones_like(dzdx)])
    normale /= np.linalg.norm(normale, axis=2, keepdims=True)
    az, alt = np.radians(315), np.radians(45)                  # soleil au nord-ouest
    lumiere = np.array([np.cos(alt) * np.sin(az), np.cos(alt) * np.cos(az), np.sin(alt)])
    ombre = np.clip(normale @ lumiere, 0, 1)
    Image.fromarray((ombre * 255).astype("uint8")).save(sortie_png)


# ---- Conversions latitude/longitude (Mars 2000, equidistante cylindrique, parallele standard LAT_TS, lon0=0) ----
RAYON_MARS_M = 3396190.0
LAT_TS_DEG = 18.38                                           # parallele standard des TIF (cf. GeoTIFF)
RAYON_X_M = RAYON_MARS_M * math.cos(math.radians(LAT_TS_DEG))  # metres par radian de longitude


def latlon_vers_cellule(lat, lon, meta):
    """lat/lon (degres, longitude Est positive) -> (i, j), ou None si hors de la grille."""
    x = RAYON_X_M * math.radians(lon)
    y = RAYON_MARS_M * math.radians(lat)
    x0, y0 = meta["origine_xy"]
    t = meta["taille_cellule_m"]
    i, j = int((y0 - y) // t), int((x - x0) // t)
    hauteur, largeur = meta["shape"]
    return (i, j) if 0 <= i < hauteur and 0 <= j < largeur else None


def cellule_vers_latlon(i, j, meta):
    """Centre de la cellule (i, j) -> (lat, lon) en degres."""
    x, y = cellule_vers_xy(i, j, meta)
    return math.degrees(y / RAYON_MARS_M), math.degrees(x / RAYON_X_M)