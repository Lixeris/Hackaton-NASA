import json
import math
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request

from moteur.astar_engine import calculer_chemin, grille_factice
from moteur.cost import bonbonnes_necessaires, est_faisable, temps_total_minutes
from moteur.donnees_mnt import (RAYON_MARS_M, cellule_vers_latlon, generer_fond_pente,
                                grille_depuis_pente, latlon_vers_cellule, longueur_chemin_m)

RACINE = Path(__file__).resolve().parent.parent
FRONTEND = RACINE / "frontend"
PENTE = RACINE / "tifs" / "pente.tif"
FICHIER_ETAT = RACINE / "data" / "etat.json"

app = Flask(__name__, static_folder=str(FRONTEND), static_url_path="")

# Charge UNE fois au demarrage
try:
    GRILLE, TAILLE, META = grille_depuis_pente(str(PENTE))
    MODE_DEMO = False
    generer_fond_pente(str(PENTE), str(FRONTEND / "fond.png"))
except FileNotFoundError:
    print("Raster de pentes introuvable -> MODE DEMO (grille factice)")
    GRILLE, TAILLE = grille_factice(100)
    META = {"taille_cellule_m": 100.0, "shape": (100, 100), "origine_xy": (4583443.25, 1098633.14)}
    MODE_DEMO = True
H, W = META["shape"]


# ------------------------------------------------------------------ Etat serveur (abris, reglages, rapports)
ETAT_DEFAUT = {
    "reglages": {"air_bonbonne_kg": 0.55, "autonomie_rover_km": 100},
    # Abris fictifs dans la zone Jezero (a remplacer par les vrais)
    "abris": [
        {"nom": "Abri 1", "lat": 18.50, "lon": 77.35},
        {"nom": "Abri 2", "lat": 18.45, "lon": 77.40},
        {"nom": "Abri 3", "lat": 18.40, "lon": 77.45},
    ],
    "rapports": [],
}


def ecrire_etat(etat):
    FICHIER_ETAT.parent.mkdir(exist_ok=True)
    FICHIER_ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")


def lire_etat():
    if not FICHIER_ETAT.exists():
        ecrire_etat(ETAT_DEFAUT)
    return json.loads(FICHIER_ETAT.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ Calcul d'itineraire
def resoudre(depart, arrivee, profil):
    """depart/arrivee = cellules (i, j)."""
    reglages = lire_etat()["reglages"]
    profil = {"rover": bool(profil.get("rover", True))}
    res = calculer_chemin(GRILLE, TAILLE, depart, arrivee, profil, 1.0)
    if res is None:
        return None
    dist = longueur_chemin_m(res["chemin"], META["taille_cellule_m"])
    duree = temps_total_minutes(dist, profil)
    faisable, causes = est_faisable(dist, profil, reglages["autonomie_rover_km"])
    return {
        "res": res, "dist": dist, "duree": duree, "faisable": faisable, "causes": causes,
        "bonbonnes": bonbonnes_necessaires(duree, reglages["air_bonbonne_kg"]),
    }


def _reponse(r):
    chemin = r["res"]["chemin"]
    return dict(
        chemin=[list(c) for c in chemin],
        chemin_latlon=[list(cellule_vers_latlon(i, j, META)) for i, j in chemin],
        distance_m=round(r["dist"]), temps_min=round(r["duree"], 1), bonbonnes=r["bonbonnes"],
        faisable=r["faisable"],
        message=None if r["faisable"] else "Attention : trajet impossible en rover",
    )


@app.post("/route")  # format lat/lon
def route():
    data = request.get_json()
    depart = latlon_vers_cellule(**data["depart"], meta=META)
    arrivee = latlon_vers_cellule(**data["arrivee"], meta=META)
    if depart is None or arrivee is None:
        return jsonify(faisable=False, message="Point hors de la zone cartographiee"), 400
    r = resoudre(depart, arrivee, data.get("profil", {}))
    if r is None:
        return jsonify(faisable=False, message="Aucun chemin trouve")
    return jsonify(_reponse(r))


@app.post("/api/route")  # format cellules (i, j)
def api_route():
    d = request.get_json()
    r = resoudre(tuple(d["depart"]), tuple(d["arrivee"]), d.get("profil", {}))
    if r is None:
        return jsonify(erreur="Aucun chemin possible (départ/arrivée infranchissable ou isolés)"), 404
    return jsonify(_reponse(r))


# ------------------------------------------------------------------ Pages et infos carte
@app.get("/")
def accueil():
    return app.send_static_file("index.html")


@app.get("/api/info")
def info():
    t = META["taille_cellule_m"]
    x0, y0 = META["origine_xy"]
    return jsonify(
        hauteur=H, largeur=W, taille_cellule_m=t, demo=MODE_DEMO,
        lat0=math.degrees(y0 / RAYON_MARS_M), lon0=math.degrees(x0 / RAYON_MARS_M),   # coin haut-gauche
        dlat=math.degrees(t / RAYON_MARS_M), dlon=math.degrees(t / RAYON_MARS_M),     # degres par cellule
    )


# ------------------------------------------------------------------ Etat : reglages, abris, rapports
@app.get("/api/etat")
def etat():
    return jsonify(lire_etat())


@app.put("/api/reglages")
def maj_reglages():
    d = request.get_json()
    try:
        air, auto = float(d["air_bonbonne_kg"]), float(d["autonomie_rover_km"])
        if air <= 0 or auto <= 0:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return jsonify(erreur="Valeurs positives attendues"), 400
    e = lire_etat()
    e["reglages"] = {"air_bonbonne_kg": air, "autonomie_rover_km": auto}
    ecrire_etat(e)
    return jsonify(e["reglages"])


@app.post("/api/abris")
def ajouter_abri():
    d = request.get_json()
    try:
        lat, lon = float(d["lat"]), float(d["lon"])
    except (KeyError, TypeError, ValueError):
        return jsonify(erreur="Coordonnées invalides"), 400
    if latlon_vers_cellule(lat, lon, META) is None:
        return jsonify(erreur="Point hors de la zone cartographiée"), 400
    e = lire_etat()
    e["abris"].append({"nom": d.get("nom") or f"Abri {len(e['abris']) + 1}", "lat": lat, "lon": lon})
    ecrire_etat(e)
    return jsonify(e["abris"])


@app.delete("/api/abris/<int:k>")
def supprimer_abri(k):
    e = lire_etat()
    if not 0 <= k < len(e["abris"]):
        return jsonify(erreur="Abri introuvable"), 404
    e["abris"].pop(k)
    ecrire_etat(e)
    return jsonify(e["abris"])


@app.post("/api/rapports")
def ajouter_rapport():
    d = request.get_json()
    texte = (d.get("texte") or "").strip()
    if not texte:
        return jsonify(erreur="Rapport vide"), 400
    e = lire_etat()
    e["rapports"].insert(0, {"titre": (d.get("titre") or "").strip(), "texte": texte,
                             "date": datetime.now().strftime("%d/%m/%Y %H:%M")})
    ecrire_etat(e)
    return jsonify(e["rapports"])


if __name__ == "__main__":
    app.run(debug=True, port=5000)