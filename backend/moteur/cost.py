import math

# ---- Seuils de pente (contraintes dures) ----

def pente_max(profil):
    return 30 if profil["rover"] else 20


# ---- Vitesse et duree ----

VITESSE_PIETON_M_MIN = 55    # m/min, a calibrer avec le groupe Donnees
VITESSE_ROVER_M_MIN = 160


def vitesse(profil):
    return VITESSE_ROVER_M_MIN if profil["rover"] else VITESSE_PIETON_M_MIN


def temps_total_minutes(distance_m, profil):
    return distance_m / vitesse(profil)


# ---- Air : un astronaute consomme 60 g d'air par heure ----

CONSO_AIR_KG_H = 0.06


def bonbonnes_necessaires(temps_min, air_bonbonne_kg):
    return math.ceil(temps_min / 60 * CONSO_AIR_KG_H / air_bonbonne_kg)


# ---- Faisabilite : uniquement le rover (distance vs autonomie sans recharge) ----

def est_faisable(distance_m, profil, autonomie_km):
    if profil["rover"] and distance_m / 1000 > autonomie_km:
        return False, ["autonomie"]
    return True, []


# ---- Cout A* ----

W_RISQUE = 0.7
W_PENTE = 0.3


def cout_cellule(cell, profil, facteur_horaire=1.0):
    p_max = pente_max(profil)
    if cell["pente_deg"] > p_max:
        return math.inf
    risque_reel = cell["risque_terrain"] * facteur_horaire
    return W_RISQUE * risque_reel + W_PENTE * (cell["pente_deg"] / p_max)