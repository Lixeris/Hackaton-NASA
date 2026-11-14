import math


def facteur_horaire(heure_decimale):
    """
    Niveau 3 (dernier recours) : modele diurne simplifie.
    Pic de risque vers midi, minimum a l'aube/crepuscule.
    A remplacer par MEDA puis REMS des que les vraies donnees sont exploitables -
    meme signature de fonction, donc rien d'autre a changer ailleurs.
    """
    return 0.6 + 0.7 * math.sin(math.pi * heure_decimale / 24) ** 2


def niveau_donnee_utilise():
    # TODO (Phase 1) : brancher MEDA reel, sinon REMS reel, sinon garder ce modele
    return "modele_simplifie"