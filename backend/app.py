from pathlib import Path

from flask import Flask, jsonify, request

from moteur.astar_engine import calculer_chemin, grille_factice
from moteur.cost import consommation_estimee_pct, est_faisable, temps_total_minutes
from moteur.donnees_mnt import (cellule_vers_latlon, generer_fond_pente, grille_depuis_pente,
                                latlon_vers_cellule, longueur_chemin_m)
from moteur.weather import niveau_donnee_utilise, recommander_depart

RACINE = Path(__file__).resolve().parent.parent
FRONTEND = RACINE / "frontend"
PENTE = RACINE / "tifs" / "pente.tif"

app = Flask(__name__, static_folder=str(FRONTEND), static_url_path="")

# Charge UNE fois au demarrage (pas a chaque requete)
try:
    GRILLE, TAILLE, META = grille_depuis_pente(str(PENTE))
    MODE_DEMO = False
    generer_fond_pente(str(PENTE), str(FRONTEND / "fond.png"))   # regenere a chaque demarrage
except FileNotFoundError:
    print("Raster de pentes introuvable -> MODE DEMO (grille factice)")
    GRILLE, TAILLE = grille_factice(100)
    # georeference de la zone Jezero 10 km, pour que lat/lon fonctionne quand meme
    META = {"taille_cellule_m": 100.0, "shape": (100, 100), "origine_xy": (4583443.25, 1098633.14)}
    MODE_DEMO = True
H, W = META["shape"]

PROFIL_DEFAUT = {"rover": True, "poids_kg": 50, "nb_personnes": 1,
                 "oxygene_pct": 100, "batterie_pct": 100, "type_trajet": "aller"}


def _latlon(chemin):
    return [list(cellule_vers_latlon(i, j, META)) for i, j in chemin]


def resoudre(depart, arrivee, profil):
    """Coeur commun aux deux routes : depart/arrivee = cellules (i, j)."""
    profil = {**PROFIL_DEFAUT, **profil}
    # facteur_horaire = 1.0 : l'heure ne module plus le risque (decision d'equipe)
    res = calculer_chemin(GRILLE, TAILLE, depart, arrivee, profil, 1.0)
    if res is None:
        return None
    dist = longueur_chemin_m(res["chemin"], META["taille_cellule_m"])
    duree = temps_total_minutes(dist, profil)
    faisable, causes = est_faisable(dist, profil)

    alternatif = None
    if res["confiance_basse"]:
        alt = calculer_chemin(GRILLE, TAILLE, depart, arrivee, profil, 1.0, mode="alternatif")
        if alt and alt["chemin"] != res["chemin"]:
            alternatif = {"chemin": alt["chemin"], "chemin_latlon": _latlon(alt["chemin"]),
                          "cout_total": alt["cout_total"]}
    return {
        "res": res, "dist": dist, "duree": duree, "profil": profil,
        "conso": consommation_estimee_pct(dist, profil),
        "faisable": faisable, "causes": causes,
        "meteo": recommander_depart(duree), "alternatif": alternatif,
    }


# ------------------------------------------------------------------ /route : format de ton frontend (lat/lon)
@app.route("/route", methods=["POST"])
def route():
    data = request.get_json()
    depart = latlon_vers_cellule(**data["depart"], meta=META)
    arrivee = latlon_vers_cellule(**data["arrivee"], meta=META)
    if depart is None or arrivee is None:
        return jsonify({"faisable": False, "message": "Point hors de la zone cartographiee"}), 400

    r = resoudre(depart, arrivee, data.get("profil", {}))
    if r is None:
        return jsonify({"faisable": False, "message": "Aucun chemin trouve"})

    chemin = r["res"]["chemin"]
    return jsonify({
        "chemin": chemin,
        "chemin_latlon": _latlon(chemin),
        "distance_m": round(r["dist"]),
        "temps_min": round(r["duree"], 1),
        "conso_pct": round(r["conso"], 1),
        "risque": r["res"]["cout_total"],
        "heure_recommandee": r["meteo"]["depart"],
        "heure_arrivee": r["meteo"]["arrivee"],
        "hors_fenetre_chaude": r["meteo"]["hors_fenetre"],
        "niveau_donnee": niveau_donnee_utilise(),
        "confiance_donnee": "basse" if r["res"]["confiance_basse"] else "haute",
        "chemin_alternatif": r["alternatif"],
        "faisable": r["faisable"],
        "cause_infaisabilite": r["causes"] if r["causes"] else None,
    })


# ------------------------------------------------------------------ /api/* : pour index.html (clics sur la grille)
@app.get("/")
def accueil():
    return app.send_static_file("index.html")


@app.get("/api/info")
def info():
    return jsonify(hauteur=H, largeur=W, taille_cellule_m=META["taille_cellule_m"], demo=MODE_DEMO)


@app.post("/api/route")
def api_route():
    d = request.get_json()
    mode = d.get("mode", "normal")
    depart, arrivee = tuple(d["depart"]), tuple(d["arrivee"])
    r = resoudre(depart, arrivee, d.get("profil", {}))
    if r is None:
        return jsonify(erreur="Aucun chemin possible (départ/arrivée infranchissable ou isolés)"), 404
    res = r["res"]
    if mode == "alternatif" and r["alternatif"]:
        res = {**res, "chemin": r["alternatif"]["chemin"], "cout_total": r["alternatif"]["cout_total"]}
    return jsonify(
        chemin=[list(c) for c in res["chemin"]],
        distance_m=round(r["dist"]), temps_min=round(r["duree"], 1), conso_pct=round(r["conso"], 1),
        faisable=r["faisable"], causes=r["causes"], confiance_basse=res["confiance_basse"],
        cout_total=round(res["cout_total"], 2), meteo=r["meteo"],
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)