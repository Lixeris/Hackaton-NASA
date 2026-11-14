from flask import Flask, jsonify, request

from navigation.astar_engine import calculer_chemin
from navigation.cost import consommation_estimee_pct, est_faisable, temps_total_minutes
from navigation.donnees_mnt import grille_depuis_mnt, longueur_chemin_m
from navigation.weather import recommander_depart

MNT = "data/JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0.tif"

app = Flask(__name__, static_folder="static", static_url_path="")

# Charge UNE fois au demarrage (pas a chaque clic)
GRILLE, TAILLE, META = grille_depuis_mnt(MNT)
H, W = META["shape"]

PROFIL_DEFAUT = {"rover": True, "poids_kg": 50, "nb_personnes": 1,
                 "oxygene_pct": 100, "batterie_pct": 100, "type_trajet": "aller"}


@app.get("/")
def accueil():
    return app.send_static_file("index.html")


@app.get("/api/info")
def info():
    return jsonify(hauteur=H, largeur=W, taille_cellule_m=META["taille_cellule_m"])


@app.post("/api/route")
def route():
    d = request.get_json()
    depart, arrivee = tuple(d["depart"]), tuple(d["arrivee"])           # [i, j]
    profil = {**PROFIL_DEFAUT, **d.get("profil", {})}

    # facteur_horaire = 1.0 : plus de modulation du risque par l'heure
    res = calculer_chemin(GRILLE, TAILLE, depart, arrivee, profil, 1.0, d.get("mode", "normal"))
    if res is None:
        return jsonify(erreur="Aucun chemin possible (départ/arrivée infranchissable ou isolés)"), 404

    dist = longueur_chemin_m(res["chemin"], META["taille_cellule_m"])
    duree = temps_total_minutes(dist, profil)
    faisable, causes = est_faisable(dist, profil)
    return jsonify(
        chemin=[list(c) for c in res["chemin"]],
        distance_m=round(dist),
        temps_min=round(duree, 1),
        conso_pct=round(consommation_estimee_pct(dist, profil), 1),
        faisable=faisable, causes=causes,
        confiance_basse=res["confiance_basse"],
        cout_total=round(res["cout_total"], 2),
        meteo=recommander_depart(duree),
    )


if __name__ == "__main__":
    app.run(debug=True)