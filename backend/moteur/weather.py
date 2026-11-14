import math
import time

import marstime

LAT_JEZERO = 18.4
LON_JEZERO = 77.7


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


def _elevation_a(utc_timestamp_s, lat=LAT_JEZERO, lon=LON_JEZERO):
    ms = utc_timestamp_s * 1000
    jday_utc = marstime.julian(ms)
    jday_tt = marstime.julian_tt(jday_utc)
    j2000_ott = marstime.j2000_offset_tt(jday_tt)
    return marstime.solar_elevation(lon, lat, j2000_ott)


def lever_coucher(lat=LAT_JEZERO, lon=LON_JEZERO, reference=None):
    """
    Calcule le lever/coucher du soleil (en heures decimales depuis `reference`)
    en balayant 25h par pas de 5 min et en reperant les passages par zero
    de l'elevation solaire. `reference` par defaut = maintenant.
    Retourne (lever, coucher) en heures decimales, ou (None, None) si
    aucun passage n'a ete trouve (jour polaire/nuit polaire, ou erreur de calcul).
    """
    now = reference if reference is not None else time.time()
    lever, coucher = None, None
    prev_e = _elevation_a(now, lat, lon)
    for i in range(1, 25 * 12):
        h = i * 5 / 60
        t = now + h * 3600
        e = _elevation_a(t, lat, lon)
        if prev_e < 0 <= e and lever is None:
            lever = h
        if prev_e >= 0 > e and lever is not None and coucher is None:
            coucher = h
        prev_e = e
    return lever, coucher


def heures_du_jour(pas_minutes=30, lat=LAT_JEZERO, lon=LON_JEZERO):
    """
    Liste des heures decimales (depuis maintenant, pas depuis minuit) couvrant
    la fenetre de jour reelle a Jezero, par pas de `pas_minutes`.
    Fallback sur 6h-18h (bornes fixes) si marstime ne trouve pas de lever/coucher.
    """
    lever, coucher = lever_coucher(lat, lon)
    if lever is None or coucher is None or coucher <= lever:
        lever, coucher = 6.0, 18.0
    pas_h = pas_minutes / 60
    heures = []
    h = lever
    while h <= coucher:
        # heure du jour sur 24h (et non l'offset brut depuis l'appel), pour
        # rester compatible avec facteur_horaire() qui attend 0-24.
        heures.append(round(h % 24, 2))
        h += pas_h
    return heures