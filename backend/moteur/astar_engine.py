import networkx as nx
import numpy as np

from .cost import cout_cellule


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


def construire_graphe(grille, taille, profil, facteur_horaire, mode="normal"):
    G = nx.Graph()
    for (i, j), cell in grille.items():
        cout = cout_cellule(cell, profil, facteur_horaire, mode)
        if cout == float("inf"):
            continue
        G.add_node((i, j), cout=cout, confiance=cell["confiance"])
    for (i, j) in list(G.nodes):
        for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
            voisin = (i + di, j + dj)
            if voisin in G.nodes:
                distance_pas = (di**2 + dj**2) ** 0.5  # Vaut 1.0 ou 1.4142...
                poids = ((G.nodes[(i, j)]["cout"] + G.nodes[voisin]["cout"]) / 2) * distance_pas
                G.add_edge((i, j), voisin, weight=poids)
    return G


def distance_euclidienne(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def calculer_chemin(grille, taille, depart, arrivee, profil, facteur_horaire, mode="normal"):
    G = construire_graphe(grille, taille, profil, facteur_horaire, mode)
    if depart not in G.nodes or arrivee not in G.nodes:
        return None
    cout_min = min(nx.get_node_attributes(G, "cout").values())
    try:
        chemin = nx.astar_path(
            G, depart, arrivee, 
            heuristic=lambda a, b: distance_euclidienne(a, b) * cout_min, 
            weight="weight"
        )
    except nx.NetworkXNoPath:
        return None
    cout_total = sum(G.nodes[n]["cout"] for n in chemin)
    confiance_basse = any(G.nodes[n]["confiance"] == "basse" for n in chemin)
    return {"chemin": chemin, "cout_total": cout_total, "confiance_basse": confiance_basse}