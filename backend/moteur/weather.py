"""Heure de depart recommandee.

Pas de donnees thermiques par case -> on centre simplement le trajet sur midi solaire
(le moment le plus chaud / ensoleille de la journee).
"""

FENETRE_CHAUDE = (6.0, 18.0)   # heures locales martiennes "favorables" : a ajuster avec temperatures.csv


def niveau_donnee_utilise():
    # TODO : "MEDA" ou "REMS" quand les vraies donnees seront branchees
    return "modele_simplifie"


def _hhmm(h):
    h = h % 24
    return f"{int(h):02d}:{int(round((h - int(h)) * 60)) % 60:02d}"


def recommander_depart(duree_min, midi_solaire=12.0, fenetre=FENETRE_CHAUDE):
    duree_h = duree_min / 60
    depart = midi_solaire - duree_h / 2
    arrivee = depart + duree_h
    return {
        "depart": _hhmm(depart),
        "arrivee": _hhmm(arrivee),
        "hors_fenetre": depart < fenetre[0] or arrivee > fenetre[1],
        "niveau_donnee": niveau_donnee_utilise(),
    }