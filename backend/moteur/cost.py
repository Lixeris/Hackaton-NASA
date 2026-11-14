import math

# ---- Seuils de faisabilite par profil (contraintes dures) ----

def pente_max(profil):
    # Meme base pour les deux profils : ce qui differe, c'est l'effet du poids.
    # Le rover porte l'essentiel du materiel, donc le poids transporte penalise
    # bien moins sa tolerance de pente que celle d'un astronaute qui porte tout
    # sur lui -> le rover reste la version "plus permissive" face a un equipement lourd.
    base = 20
    poids_effectif = profil["poids_kg"] * (0.3 if profil["rover"] else 1.0)
    penalite_poids = 0.05 * poids_effectif
    return max(base - penalite_poids, 5)


def marge_securite(profil):
    return 3 if profil["rover"] else 1


# ---- Vitesse et consommation ----

VITESSE_BASE_M_MIN = 50  # m/min, valeur de depart a calibrer avec le groupe Donnees


def vitesse_groupe(profil):
    return VITESSE_BASE_M_MIN / (1 + 0.1 * (profil["nb_personnes"] - 1))


def temps_total_minutes(distance_m, profil):
    distance_totale = distance_m * 2 if profil.get("type_trajet") == "aller_retour" else distance_m
    return distance_totale / vitesse_groupe(profil)


TAUX_BASE_CONSO_PCT_MIN = 1.0


def consommation_estimee_pct(distance_m, profil):
    taux = TAUX_BASE_CONSO_PCT_MIN * (1 + 0.005 * profil["poids_kg"]) * (0.8 if profil["rover"] else 1.0)
    return taux * temps_total_minutes(distance_m, profil)


# ---- Faisabilite (ressources + temps impose) ----

def est_faisable(distance_m, profil, marge=0.15):
    causes = []
    conso = consommation_estimee_pct(distance_m, profil)
    ressources_dispo = min(profil.get("oxygene_pct", 100), profil.get("batterie_pct", 100))
    if conso > ressources_dispo * (1 - marge):
        causes.append("ressources")

    temps_max = profil.get("temps_max_minutes")
    if temps_max:
        temps_estime = temps_total_minutes(distance_m, profil)
        if temps_estime > temps_max * (1 - marge):
            causes.append("temps")

    return (len(causes) == 0), causes


# ---- Cout A* ----

W_RISQUE = 0.7
W_PENTE = 0.3


def cout_cellule(cell, profil, facteur_horaire=1.0, mode="normal"):
    p_max = pente_max(profil)
    if cell["pente_deg"] > p_max:
        return math.inf
    risque_reel = cell["risque_terrain"] * facteur_horaire
    cout = W_RISQUE * risque_reel + W_PENTE * (cell["pente_deg"] / p_max)
    if mode == "alternatif" and cell.get("confiance") == "basse":
        cout += 10
    return cout


# ---- Repli sur destination connue si la demandee n'est pas faisable ----

DESTINATIONS_CONNUES = {
    "abri_1": (2, 8),
    "abri_2": (7, 2),
    "point_eleve": (9, 9),
}


def trouver_destination_faisable(depart, destination_demandee, profil, calculer_chemin_fn, grille, taille, facteur_horaire):
    chemin = calculer_chemin_fn(grille, taille, depart, destination_demandee, profil, facteur_horaire)
    if chemin:
        faisable, causes = est_faisable(len(chemin["chemin"]) * 50, profil)
        if faisable:
            return chemin, destination_demandee, None, []

    for nom, coords in DESTINATIONS_CONNUES.items():
        if coords == destination_demandee:
            continue
        alt = calculer_chemin_fn(grille, taille, depart, coords, profil, facteur_horaire)
        if alt:
            faisable, causes = est_faisable(len(alt["chemin"]) * 50, profil)
            if faisable:
                return alt, coords, f"Destination demandee hors de portee ; repli sur '{nom}'", []

    return None, None, "Aucune destination connue n'est atteignable avec ces ressources", ["ressources"]