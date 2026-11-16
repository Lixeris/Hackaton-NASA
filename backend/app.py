import json
import math
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request

from moteur.calques import construire_calques
from moteur.astar_engine import calculer_chemin, grille_factice
from moteur.cost import bonbonnes_necessaires, est_faisable, temps_total_minutes
from moteur.donnees_mnt import (RAYON_MARS_M, RAYON_X_M, cellule_vers_latlon,
                                grille_depuis_pente, latlon_vers_cellule, longueur_chemin_m)

RACINE = Path(__file__).resolve().parent.parent
FRONTEND = RACINE / "frontend"
TIFS = RACINE / "tifs"
DENIVELE = TIFS / "denivele.tif"      
UNITE_DENIVELE = "pct"                  
FICHIER_ETAT = RACINE / "data" / "etat.json"

app = Flask(__name__, static_folder=str(FRONTEND), static_url_path="")


try:
    GRILLE, TAILLE, META = grille_depuis_pente(str(DENIVELE), unite=UNITE_DENIVELE)
except FileNotFoundError:
    raise SystemExit(f"Raster introuvable : {DENIVELE}")
MODE_DEMO = False
H, W = META["shape"]
CALQUES = construire_calques(TIFS, FRONTEND)   # PNG regeneres a chaque demarrage



ETAT_DEFAUT = {
    "reglages": {"air_bonbonne_kg": 0.55, "autonomie_rover_km": 100},
    
    "abris": [
        {"nom": "Shelter 1", "lat": 18.50, "lon": 77.35},
        {"nom": "Shelter 2", "lat": 18.45, "lon": 77.40},
        {"nom": "Shelter 3", "lat": 18.40, "lon": 77.45},
    ],
    "rapports": [],
}


def ecrire_etat(etat):
    FICHIER_ETAT.parent.mkdir(exist_ok=True)
    FICHIER_ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")


def lire_etat():
    if not FICHIER_ETAT.exists():
        ecrire_etat(ETAT_DEFAUT)
    e = json.loads(FICHIER_ETAT.read_text(encoding="utf-8"))
    migre = False
    for r in e["rapports"]:                      
        if "id" not in r:
            r.update(id=uuid.uuid4().hex[:8], lat=None, lon=None, visible=False)
            migre = True
    if migre:
        ecrire_etat(e)
    return e


# trajet
def resoudre(depart, arrivee, profil):

    reglages = lire_etat()["reglages"]
    profil = {"rover": bool(profil.get("rover", True))}
    res = calculer_chemin(GRILLE, TAILLE, depart, arrivee, profil, 1.0)
    if res is None:
        return None
    dist = longueur_chemin_m(res["chemin"], META["taille_cellule_m"])
    duree = temps_total_minutes(dist, profil)
    faisable, causes = est_faisable(dist, profil, reglages["autonomie_rover_km"])
    etapes = []
    if not faisable and profil["rover"]:
        via = _trajet_par_abris(depart, arrivee, profil, reglages["autonomie_rover_km"])
        if via is not None:
            res, dist, etapes = via["res"], via["dist"], via["etapes"]
            duree = temps_total_minutes(dist, profil)
            faisable, causes = True, []
    return {
        "res": res, "dist": dist, "duree": duree, "faisable": faisable, "causes": causes,
        "bonbonnes": bonbonnes_necessaires(duree, reglages["air_bonbonne_kg"]),
        "etapes": etapes,
    }


def _trajet_par_abris(depart, arrivee, profil, autonomie_km):    
    limite_m = autonomie_km * 1000
    noeuds = [(None, depart)]                                     
    for a in lire_etat()["abris"]:
        c = latlon_vers_cellule(a["lat"], a["lon"], META)
        if c is not None and all(c != n[1] for n in noeuds):
            noeuds.append((a, c))
    noeuds.append((None, arrivee))
    fin = len(noeuds) - 1

    liens = {}
    def lien(u, v):
        
        if (u, v) not in liens:
            r = calculer_chemin(GRILLE, TAILLE, noeuds[u][1], noeuds[v][1], profil, 1.0)
            d = longueur_chemin_m(r["chemin"], META["taille_cellule_m"]) if r else None
            liens[(u, v)] = (r, d) if r and d <= limite_m else None
        return liens[(u, v)]

    best = {0: 0.0}
    prec = {}
    fait = set()
    while True:
        cand = [k for k in best if k not in fait]
        if not cand:
            return None
        u = min(cand, key=best.get)
        if u == fin:
            break
        fait.add(u)
        for v in range(1, len(noeuds)):
            if v == u or v in fait or noeuds[u][1] == noeuds[v][1]:
                continue
            l = lien(u, v)
            if l is not None and best[u] + l[1] < best.get(v, math.inf):
                best[v] = best[u] + l[1]
                prec[v] = u

    ordre = [fin]
    while ordre[-1] != 0:
        ordre.append(prec[ordre[-1]])
    ordre.reverse()

    chemin, etapes = [], []
    cout, confiance_basse = 0.0, False
    for u, v in zip(ordre, ordre[1:]):
        r = lien(u, v)[0]
        if chemin:
            etapes.append({"nom": noeuds[u][0]["nom"], "lat": noeuds[u][0]["lat"], "lon": noeuds[u][0]["lon"],
                           "index": len(chemin) - 1})
        chemin += r["chemin"][1:] if chemin else r["chemin"]
        cout += r["cout_total"]
        confiance_basse = confiance_basse or r["confiance_basse"]
    return {"res": {"chemin": chemin, "cout_total": cout, "confiance_basse": confiance_basse},
            "dist": longueur_chemin_m(chemin, META["taille_cellule_m"]), "etapes": etapes}


def _reponse(r):
    chemin = r["res"]["chemin"]
    etapes = r.get("etapes", [])
    if r["faisable"]:
        message = f"Route via the following shelters: {', '.join(e['nom'] for e in etapes)}" if etapes else None
    else:
        message = "WARNING: route not feasible"
    return dict(
        chemin=[list(c) for c in chemin],
        chemin_latlon=[list(cellule_vers_latlon(i, j, META)) for i, j in chemin],
        distance_m=round(r["dist"]), temps_min=round(r["duree"], 1), bonbonnes=r["bonbonnes"],
        faisable=r["faisable"], etapes=etapes, message=message,
    )


@app.post("/route")  # format lat/lon
def route():
    data = request.get_json()
    depart = latlon_vers_cellule(**data["depart"], meta=META)
    arrivee = latlon_vers_cellule(**data["arrivee"], meta=META)
    if depart is None or arrivee is None:
        return jsonify(faisable=False, message="Point outside the mapped area"), 400
    r = resoudre(depart, arrivee, data.get("profil", {}))
    if r is None:
        return jsonify(faisable=False, message="No path found")
    return jsonify(_reponse(r))


@app.post("/api/route")  # format cellules (i, j)
def api_route():
    d = request.get_json()
    r = resoudre(tuple(d["depart"]), tuple(d["arrivee"]), d.get("profil", {}))
    if r is None:
        return jsonify(erreur="No path possible (start/end impassable or isolated)"), 404
    return jsonify(_reponse(r))



@app.get("/")
def accueil():
    return app.send_static_file("index.html")


@app.get("/api/info")
def info():
    t = META["taille_cellule_m"]
    x0, y0 = META["origine_xy"]
    return jsonify(
        hauteur=H, largeur=W, taille_cellule_m=t, demo=MODE_DEMO,
        lat0=math.degrees(y0 / RAYON_MARS_M), lon0=math.degrees(x0 / RAYON_X_M),      # coin haut-gauche
        dlat=math.degrees(t / RAYON_MARS_M), dlon=math.degrees(t / RAYON_X_M),        
    )



@app.get("/api/calques")
def calques():
    return jsonify(CALQUES)


@app.get("/api/etat")
def etat():
    return jsonify(lire_etat())


@app.put("/api/reglages")
def maj_reglages():
    d = request.get_json()
    try:
        air, auto = float(d["air_bonbonne_kg"]), float(d["autonomie_rover_km"])
        if air <= 0 or auto <= 0:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return jsonify(erreur="Positive values expected"), 400
    e = lire_etat()
    e["reglages"] = {"air_bonbonne_kg": air, "autonomie_rover_km": auto}
    ecrire_etat(e)
    return jsonify(e["reglages"])


@app.post("/api/abris")
def ajouter_abri():
    d = request.get_json()
    try:
        lat, lon = float(d["lat"]), float(d["lon"])
    except (KeyError, TypeError, ValueError):
        return jsonify(erreur="Invalid coordinates"), 400
    if latlon_vers_cellule(lat, lon, META) is None:
        return jsonify(erreur="Point outside the mapped area"), 400
    e = lire_etat()
    e["abris"].append({"nom": d.get("nom") or f"Shelter {len(e['abris']) + 1}", "lat": lat, "lon": lon})
    ecrire_etat(e)
    return jsonify(e["abris"])


@app.delete("/api/abris/<int:k>")
def supprimer_abri(k):
    e = lire_etat()
    if not 0 <= k < len(e["abris"]):
        return jsonify(erreur="Shelter not found"), 404
    e["abris"].pop(k)
    ecrire_etat(e)
    return jsonify(e["abris"])


def _position(d):
    """(lat, lon) valides dans la zone, ou None si aucune position fournie. ValueError sinon."""
    if d.get("lat") in (None, "") and d.get("lon") in (None, ""):
        return None
    lat, lon = float(d["lat"]), float(d["lon"])
    if latlon_vers_cellule(lat, lon, META) is None:
        raise ValueError("hors zone")
    return lat, lon


@app.post("/api/rapports")
def ajouter_rapport():
    d = request.get_json()
    texte = (d.get("texte") or "").strip()
    if not texte:
        return jsonify(erreur="Empty report"), 400
    try:
        pos = _position(d)
    except (TypeError, ValueError):
        return jsonify(erreur="Invalid position or outside the mapped area"), 400
    e = lire_etat()
    e["rapports"].insert(0, {"id": uuid.uuid4().hex[:8], "titre": (d.get("titre") or "").strip(), "texte": texte,
                             "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                             "lat": pos[0] if pos else None, "lon": pos[1] if pos else None, "visible": pos is not None})
    ecrire_etat(e)
    return jsonify(e["rapports"])


@app.patch("/api/rapports/<rid>")
def maj_rapport(rid):
    d = request.get_json()
    e = lire_etat()
    r = next((x for x in e["rapports"] if x["id"] == rid), None)
    if r is None:
        return jsonify(erreur="Report not found"), 404
    try:
        if "lat" in d or "lon" in d:
            pos = _position(d)
            r["lat"], r["lon"] = pos if pos else (None, None)
            r["visible"] = pos is not None
        if "visible" in d:
            r["visible"] = bool(d["visible"]) and r["lat"] is not None
    except (TypeError, ValueError):
        return jsonify(erreur="Invalid position or outside the mapped area"), 400
    ecrire_etat(e)
    return jsonify(e["rapports"])


if __name__ == "__main__":
    app.run(port=5000)