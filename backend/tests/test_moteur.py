import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from moteur.astar_engine import grille_factice, calculer_chemin
from moteur.cost import est_faisable
from moteur.weather import facteur_horaire


@pytest.fixture
def grille():
    return grille_factice(taille=10, seed=42)  # seed fixe = resultats reproductibles


def grille_controlee(taille=10):
    """
    Grille deterministe pour les tests de chemin : un depart/arrivee toujours
    praticables, et une bande de pente forte au milieu de la colonne centrale
    (en laissant un passage libre sur les 2 premieres et 2 dernieres lignes,
    pour que l'obstacle soit contournable et non un mur complet infranchissable).
    Seul un profil permissif (rover, poids leger) peut la traverser directement ;
    un profil plus restrictif doit la contourner, d'ou un chemin plus couteux.
    """
    grille = {}
    colonne_bloquee = taille // 2
    for i in range(taille):
        for j in range(taille):
            est_dans_la_bande = (j == colonne_bloquee) and (2 <= i <= taille - 3)
            pente = 25.0 if est_dans_la_bande else 5.0
            grille[(i, j)] = {"pente_deg": pente, "risque_terrain": 0.2, "confiance": "haute"}
    return grille, taille


def profil(poids=45, rover=False, nb=2, oxygene=100, batterie=100, temps_max=None, type_trajet="aller_retour"):
    return {
        "poids_kg": poids, "rover": rover, "nb_personnes": nb,
        "oxygene_pct": oxygene, "batterie_pct": batterie,
        "temps_max_minutes": temps_max, "type_trajet": type_trajet,
    }


def test_chemin_existe():
    g, taille = grille_controlee()
    resultat = calculer_chemin(g, taille, (0, 0), (taille - 1, taille - 1), profil(), facteur_horaire(6))
    assert resultat is not None
    assert len(resultat["chemin"]) > 1


def test_profil_lourd_bloque_par_pente_forte():
    g, taille = grille_controlee()
    depart, arrivee = (0, 0), (taille - 1, taille - 1)
    chemin_leger = calculer_chemin(g, taille, depart, arrivee, profil(poids=10, rover=False), facteur_horaire(6))
    chemin_lourd = calculer_chemin(g, taille, depart, arrivee, profil(poids=140, rover=False), facteur_horaire(6))
    assert chemin_leger is not None and chemin_lourd is not None
    assert chemin_lourd["cout_total"] >= chemin_leger["cout_total"]


def test_rover_plus_permissif_que_a_pied():
    g, taille = grille_controlee()
    depart, arrivee = (0, 0), (taille - 1, taille - 1)
    chemin_pied = calculer_chemin(g, taille, depart, arrivee, profil(poids=140, rover=False), facteur_horaire(6))
    chemin_rover = calculer_chemin(g, taille, depart, arrivee, profil(poids=140, rover=True), facteur_horaire(6))
    assert chemin_pied is not None and chemin_rover is not None
    assert chemin_rover["cout_total"] <= chemin_pied["cout_total"] + 1e-6


def test_ressources_insuffisantes_signalees():
    faisable, causes = est_faisable(distance_m=50000, profil=profil(oxygene=20, batterie=20))
    assert faisable is False and "ressources" in causes


def test_temps_max_depasse():
    faisable, causes = est_faisable(distance_m=100, profil=profil(temps_max=1))
    assert faisable is False and "temps" in causes


def test_sans_contraintes_est_faisable():
    faisable, causes = est_faisable(distance_m=100, profil=profil())
    assert faisable is True and causes == []