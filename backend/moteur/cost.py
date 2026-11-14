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