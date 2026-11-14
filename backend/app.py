from flask import Flask, request, jsonify

from moteur.astar_engine import grille_factice, calculer_chemin
from moteur.weather import facteur_horaire, niveau_donnee_utilise, heures_du_jour
from moteur.cost import est_faisable, trouver_destination_faisable

app = Flask(__name__)
GRILLE, TAILLE = grille_factice()


def cellule_depuis_coords(lat, lon):
    # TODO : conversion reelle lat/lon -> indices de grille via la georeference QGIS
    i = int(abs(lat) * 2) % TAILLE
    j = int(abs(lon) * 2) % TAILLE
    return (i, j)


@app.route("/route", methods=["POST"])
def route():
    data = request.get_json()
    profil = data["profil"]
    depart = cellule_depuis_coords(**data["depart"])
    arrivee = cellule_depuis_coords(**data["arrivee"])

    meilleur, meilleure_heure = None, None
    for h in heures_du_jour():
        f = facteur_horaire(h)
        resultat = calculer_chemin(GRILLE, TAILLE, depart, arrivee, profil, f)
        if resultat and (meilleur is None or resultat["cout_total"] < meilleur["cout_total"]):
            meilleur, meilleure_heure = resultat, h

    if meilleur is None:
        return jsonify({"faisable": False, "message": "Aucun chemin trouve"})

    distance_m = len(meilleur["chemin"]) * 50  # TODO : vraie distance georeferencee
    faisable, causes = est_faisable(distance_m, profil)

    destination_recommandee = None
    message = None

    if not faisable:
        f = facteur_horaire(meilleure_heure)
        chemin_repli, destination_choisie, message_repli, causes_repli = trouver_destination_faisable(
            depart, arrivee, profil, calculer_chemin, GRILLE, TAILLE, f
        )
        if chemin_repli:
            meilleur = chemin_repli
            destination_recommandee = destination_choisie
            distance_m = len(meilleur["chemin"]) * 50
            faisable, causes = True, []
            message = message_repli
        else:
            causes = causes_repli
            message = message_repli

    alternatif = None
    if meilleur["confiance_basse"]:
        alt = calculer_chemin(GRILLE, TAILLE, depart, arrivee, profil, facteur_horaire(meilleure_heure), mode="alternatif")
        if alt and alt["chemin"] != meilleur["chemin"]:
            alternatif = {"chemin": alt["chemin"], "cout_total": alt["cout_total"]}

    return jsonify({
        "chemin": meilleur["chemin"],
        "destination_recommandee": destination_recommandee,
        "message": message,
        "distance_m": distance_m,
        "risque": meilleur["cout_total"],
        "heure_recommandee": f"{int(meilleure_heure):02d}:{int((meilleure_heure % 1) * 60):02d}",
        "niveau_donnee": niveau_donnee_utilise(),
        "confiance_donnee": "basse" if meilleur["confiance_basse"] else "haute",
        "chemin_alternatif": alternatif,
        "faisable": faisable,
        "cause_infaisabilite": causes if causes else None,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)