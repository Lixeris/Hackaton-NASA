import heapq
import math

import numpy as np

from .cost import cout_cellule

VOISINS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
_CACHE = {}   # couts par cellule, calcules une seule fois par profil (la grille ne change pas)


def grille_factice(taille=20, seed=0):
    """Raster bidon en attendant la sortie QGIS reelle - meme forme de donnees."""
    rng = np.random.default_rng(seed)
    grille = {}
    for i in range(taille):
        for j in range(taille):
            grille[(i, j)] = {
                "pente_deg": float(rng.uniform(0, 25)),
                "risque_terrain": float(rng.uniform(0, 1)),
                "confiance": "basse" if rng.random() < 0.1 else "haute",
            }
    return grille, taille


def _couts(grille, profil, facteur_horaire):
    cle = (id(grille), bool(profil["rover"]), facteur_horaire)
    if cle not in _CACHE:
        couts = {}
        for pos, cell in grille.items():
            c = cout_cellule(cell, profil, facteur_horaire)
            if c != math.inf:
                couts[pos] = c
        _CACHE[cle] = (couts, min(couts.values()) if couts else 0.0)
    return _CACHE[cle]


def calculer_chemin(grille, taille, depart, arrivee, profil, facteur_horaire):
    couts, cout_min = _couts(grille, profil, facteur_horaire)
    if depart not in couts or arrivee not in couts:
        return None

    def h(p):
        return math.hypot(p[0] - arrivee[0], p[1] - arrivee[1]) * cout_min

    g = {depart: 0.0}
    parent = {}
    ferme = set()
    file = [(h(depart), depart)]
    while file:
        _, u = heapq.heappop(file)
        if u == arrivee:
            break
        if u in ferme:
            continue
        ferme.add(u)
        cu = couts[u]
        for di, dj in VOISINS:
            v = (u[0] + di, u[1] + dj)
            cv = couts.get(v)
            if cv is None or v in ferme:
                continue
            nv = g[u] + (cu + cv) / 2 * math.hypot(di, dj)
            if nv < g.get(v, math.inf):
                g[v] = nv
                parent[v] = u
                heapq.heappush(file, (nv + h(v), v))
    else:
        return None
    if arrivee not in g:
        return None

    chemin = [arrivee]
    while chemin[-1] != depart:
        chemin.append(parent[chemin[-1]])
    chemin.reverse()
    cout_total = sum(couts[n] for n in chemin)
    confiance_basse = any(grille[n]["confiance"] == "basse" for n in chemin)
    return {"chemin": chemin, "cout_total": cout_total, "confiance_basse": confiance_basse}