"""
neo4j_fraud_indicators.py    VERSION CORRIGE
================================================
CORRECTION PRINCIPALE :
  - compute() fetche TOUT depuis Neo4j (Sinistre, Tiers, Contrat, Voiture)
  - sinistre_node (ligne Excel) n'est utilis QUE pour extraire NUM_SINISTRE
  - Aucun indicateur n'utilise les colonnes Excel comme source de donnes
  - _fetch_sinistre_node() ajout pour rcuprer les attributs du nud Sinistre
    directement depuis Neo4j (date_sinistre, date_declaration, lat/lon, etc.)

Poids par indicateur (somme = 100 pts max) :
  1. Distance rsidence/sinistre > 30 km           12-20 pts
  2. Usage  risque (taxi/louage/location)          10 pts
  3. Incohrence profession / marque               12 pts
  4. Dcalage dclaration > 30 j                   10-18 pts
  5. Sinistre avant souscription                   15 pts (critique)
  6. Fentre expiration contrat (7 j)             10 pts
  7. Vhicule trs neuf (< 6 mois)                8 pts
  8. Kilomtrage annuel > 40 000 km               8-15 pts
  9. Assur rcurrent ( 2 sinistres)             5 pts
 10. Vhicule rcurrent ( 2 sinistres)           5 pts
 11. Tiers rcurrent ( 2 sinistres)              5 pts
 12. Communaut suspecte dtecte                8-12 pts

Seuils finaux :
  score < 30    normal
  30  score < 60  suspect
  score  60    fraude
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple


# 
# Constantes & Poids
# 

SEUIL_NORMAL  = 30
SEUIL_SUSPECT = 60

POIDS = {
    "DIST_SIN_RES":            {"pts_normal": 12, "pts_critique": 20, "label": "Distance rsidence/sinistre"},
    "USAGE_RISQUE":            {"pts": 10,         "label": "Usage  risque"},
    "INCOHER_PROF_MARQUE":     {"pts": 12,         "label": "Incohrence profession/marque"},
    "DECL_TARDIVE":            {"pts_normal": 10,  "pts_critique": 18, "label": "Dclaration tardive"},
    "DECL_AVANT_SIN":          {"pts": 25,         "label": "Dclaration avant sinistre"},  #  CORRECTION ajoute
    "SIN_AVANT_SOUSCRIPTION":  {"pts": 15,         "label": "Sinistre avant souscription"},
    "FENETRE_EXPIRATION":      {"pts": 10,         "label": "Fentre expiration contrat"},
    "VEHICULE_TRES_NEUF":      {"pts": 8,          "label": "Vhicule trs neuf"},
    "KM_ANORMAL":              {"pts_normal": 8,   "pts_critique": 15, "label": "Kilomtrage anormal"},
    "ASS_RECURRENT":           {"pts": 5,          "label": "Assur rcurrent"},
    "VEH_RECURRENT":           {"pts": 5,          "label": "Vhicule rcurrent"},
    "TIERS_RECURRENT":         {"pts": 5,          "label": "Tiers rcurrent"},
    "COMMUNAUTE_SUSPECTE":     {"pts": 8,          "label": "Membre d'une communaut suspecte"},
}

USAGES_A_RISQUE = {
    "taxi", "louage", "location", "transport en commun",
    "transport public", "vtc", "autobus", "camion",
}

MARQUES_PREMIUM = {
    "bmw", "mercedes", "mercedes-benz", "audi", "porsche",
    "jaguar", "land rover", "lexus", "maserati", "ferrari",
    "lamborghini", "bentley", "rolls-royce", "tesla",
    "volvo", "infiniti", "cadillac", "range rover",
}

PROFESSIONS_MODESTES = {
    "jardinier", "agent d'entretien", "femme de mnage", "ouvrier",
    "manuvre", "agriculteur", "gardien", "vigile", "plongeur",
    "livreur", "conducteur", "chauffeur", "aide soignant",
    "agent de scurit", "manutentionnaire", "balayeur", "porteur",
    "peintre en btiment", "pltrier", "carreleur", "soudeur",
    "sans emploi", "chmeur", "retrait modeste",
}

KM_ANNUEL_MAX           = 40_000
AGE_VEHICULE_MIN_MOIS   = 6
DECALAGE_DECLARATION_MAX = 30
FENETRE_EXPIRATION_JOURS = 7
DISTANCE_SEUIL_KM        = 30
DISTANCE_CRITIQUE_KM     = 100


# 
# Structures de donnes
# 

@dataclass
class Neo4jIndicateur:
    code: str
    label: str
    description: str
    points: int
    niveau: str
    valeur: Any = None
    source: str = "neo4j"


@dataclass
class Neo4jFraudResult:
    score_neo4j: float
    statut: str
    indicateurs: List[Neo4jIndicateur] = field(default_factory=list)
    details: Dict[str, Any]           = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score_neo4j": round(self.score_neo4j, 1),
            "statut": self.statut,
            "nb_indicateurs_neo4j": len(self.indicateurs),
            "indicateurs_neo4j": [
                {
                    "code": i.code,
                    "label": i.label,
                    "description": i.description,
                    "points": i.points,
                    "niveau": i.niveau,
                    "valeur": i.valeur,
                    "source": i.source,
                }
                for i in self.indicateurs
            ],
            "details_neo4j": self.details,
        }


# 
# Utilitaires
# 

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_date(val: Any) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(str(val)[:19], fmt[:len(str(val)[:19])]).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00")).date()
    except Exception:
        return None


def _normalize(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s).lower().strip())


# 
# Analyseur Neo4j Principal  CORRIG
# 

class Neo4jFraudIndicators:
    """
    Calcule tous les indicateurs de fraude depuis Neo4j UNIQUEMENT.

    CORRECTION : compute() ne lit plus sinistre_node (ligne Excel).
    Il fetche le nud Sinistre + Tiers + Contrat + Voiture depuis Neo4j,
    puis calcule chaque indicateur sur ces donnes Neo4j.

    Utilisation :
        analyzer = Neo4jFraudIndicators()
        result = analyzer.compute(
            num_sinistre="SIN-2024-00001",
            driver=neo4j_driver,
            database="neo4j"
        )
    """

    def compute(
        self,
        num_sinistre: str,
        driver: Any,
        database: str = "neo4j",
        #  DPRCI  gard pour compatibilit ascendante mais IGNOR 
        sinistre_node: Dict[str, Any] = None,
    ) -> Neo4jFraudResult:
        """
        Calcule le score Neo4j pour un sinistre donn.
        Toutes les donnes viennent de Neo4j  sinistre_node est ignor.
        """
        if sinistre_node is not None:
            # On log un avertissement si l'appelant passe encore sinistre_node
            print(
                f"     [Neo4jFraudIndicators] sinistre_node ignor pour {num_sinistre} "
                f" toutes les donnes sont lues depuis Neo4j."
            )

        indicateurs: List[Neo4jIndicateur] = []
        details: Dict[str, Any] = {}

        #  Fetch TOUT depuis Neo4j 
        sinistre = self._fetch_sinistre_node(driver, database, num_sinistre)
        assure   = self._fetch_assure(driver, database, num_sinistre)
        contrat  = self._fetch_contrat(driver, database, num_sinistre)
        vehicle  = self._fetch_vehicle(driver, database, num_sinistre)

        details["sinistre_found"] = bool(sinistre)
        details["assure_found"]   = bool(assure)
        details["contrat_found"]  = bool(contrat)
        details["vehicle_found"]  = bool(vehicle)

        if not sinistre:
            print(f"     Sinistre {num_sinistre} introuvable dans Neo4j  score = 0")
            return Neo4jFraudResult(score_neo4j=0.0, statut="normal", details=details)

        #  1. Distance rsidence / sinistre 
        ind = self._check_distance(sinistre, assure)
        if ind:
            indicateurs.append(ind)
            details["distance_km"] = ind.valeur

        #  2. Usage  risque 
        ind = self._check_usage(contrat, vehicle)
        if ind:
            indicateurs.append(ind)

        #  3. Incohrence profession / marque 
        ind = self._check_profession_marque(assure, vehicle)
        if ind:
            indicateurs.append(ind)

        #  4. Dcalage dclaration 
        ind, nb_jours = self._check_decalage_declaration(sinistre)
        if ind:
            indicateurs.append(ind)
            details["decalage_declaration_jours"] = nb_jours

        #  5. Sinistre avant souscription 
        ind = self._check_avant_souscription(sinistre, contrat)
        if ind:
            indicateurs.append(ind)

        #  6. Fentre expiration contrat 
        ind, delta = self._check_fenetre_expiration(sinistre, contrat)
        if ind:
            indicateurs.append(ind)
            details["delta_expiration_jours"] = delta

        #  7. Vhicule trs neuf 
        ind, age_mois = self._check_vehicule_neuf(sinistre, vehicle)
        if ind:
            indicateurs.append(ind)
            details["age_vehicule_mois"] = age_mois

        #  8. Kilomtrage anormal 
        ind, km_an = self._check_kilometrage(vehicle)
        if ind:
            indicateurs.append(ind)
            details["kilometrage_annuel"] = km_an

        #  9. Assur rcurrent 
        ind = self._check_assure_recurrent(driver, database, num_sinistre)
        if ind:
            indicateurs.append(ind)

        #  10. Vhicule rcurrent 
        ind = self._check_vehicule_recurrent(driver, database, num_sinistre)
        if ind:
            indicateurs.append(ind)

        #  11. Tiers rcurrent 
        ind = self._check_tiers_recurrent(driver, database, num_sinistre)
        if ind:
            indicateurs.append(ind)

        #  12. Communaut suspecte 
        ind = self._check_communaute_suspecte(driver, database, num_sinistre)
        if ind:
            indicateurs.append(ind)
            details["communaute_id"] = ind.valeur

        score  = min(sum(i.points for i in indicateurs), 100.0)
        statut = self._statut(score)

        return Neo4jFraudResult(
            score_neo4j=score,
            statut=statut,
            indicateurs=indicateurs,
            details=details,
        )

    # 
    #  NOUVEAU  Fetch du nud Sinistre depuis Neo4j
    # C'est ce fetch qui remplace l'usage de sinistre_node (ligne Excel)
    # 

    def _fetch_sinistre_node(self, driver, database: str, num_sinistre: str) -> Dict:
        """
        Rcupre les proprits du nud Sinistre depuis Neo4j.
        C'est LA source de vrit pour les dates et coordonnes GPS.
        """
        # Essayer NUM_SINISTRE ou num_sinistre
        queries = [
            "MATCH (s:Sinistre {NUM_SINISTRE: $num}) RETURN s",
            "MATCH (s:Sinistre {num_sinistre: $num}) RETURN s",
            "MATCH (s:Sinistre) WHERE s.NUM_SINISTRE = $num OR s.num_sinistre = $num RETURN s LIMIT 1"
        ]
        try:
            with driver.session(database=database) as session:
                for q in queries:
                    rec = session.run(q, num=num_sinistre).single()
                    if rec:
                        s = dict(rec["s"])
                        # Uniformiser la cl principale
                        if "NUM_SINISTRE" in s and "num_sinistre" not in s:
                            s["num_sinistre"] = s["NUM_SINISTRE"]
                        return s
        except Exception as e:
            print(f" _fetch_sinistre_node error ({num_sinistre}): {e}")
        return {}

    # 
    # Fetch donnes lies (inchangs dans leur logique, source = Neo4j)
    # 

    def _fetch_assure(self, driver, database: str, num_sinistre: str) -> Dict:
        query = """
        MATCH (s:Sinistre {NUM_SINISTRE: $num})
        OPTIONAL MATCH (a:Tiers)-[:DECLARE]->(s)
        RETURN
            coalesce(a.nom, '')              AS nom,
            coalesce(a.prenom, '')           AS prenom,
            coalesce(a.profession, '')       AS profession,
            coalesce(a.secteur_activite, '') AS secteur_activite,
            coalesce(a.email, '')            AS email,
            a.adresse_latitude               AS adresse_latitude,
            a.adresse_longitude              AS adresse_longitude,
            a.adresse_siege_latitude         AS adresse_siege_latitude,
            a.adresse_siege_longitude        AS adresse_siege_longitude
        LIMIT 1
        """
        try:
            with driver.session(database=database) as session:
                rec = session.run(query, num=num_sinistre).single()
                return dict(rec) if rec else {}
        except Exception as e:
            print(f" _fetch_assure error ({num_sinistre}): {e}")
            return {}

    def _fetch_contrat(self, driver, database: str, num_sinistre: str) -> Dict:
        query = """
        MATCH (s:Sinistre {NUM_SINISTRE: $num})
        OPTIONAL MATCH (a:Tiers)-[:DECLARE]->(s)
        OPTIONAL MATCH (a)-[:SOUSCRIT]->(c:Contrat)
        RETURN
            coalesce(c.date_debut, c.date_souscription, '') AS date_souscription,
            coalesce(c.date_expiration, '')                  AS date_expiration,
            coalesce(c.usage, '')                            AS usage,
            coalesce(c.numero_contrat, '')                   AS numero_contrat
        LIMIT 1
        """
        try:
            with driver.session(database=database) as session:
                rec = session.run(query, num=num_sinistre).single()
                return dict(rec) if rec else {}
        except Exception as e:
            print(f" _fetch_contrat error ({num_sinistre}): {e}")
            return {}

    def _fetch_vehicle(self, driver, database: str, num_sinistre: str) -> Dict:
        query = """
        MATCH (s:Sinistre {NUM_SINISTRE: $num})
        OPTIONAL MATCH (v:Voiture)-[:IMPLIQUE_DANS]->(s)
        RETURN
            coalesce(v.immatriculation, '') AS immatriculation,
            coalesce(v.marque, '')          AS marque,
            coalesce(v.usage, '')           AS usage,
            v.date_mise_en_circulation      AS date_mise_en_circulation,
            v.kilometrage                   AS kilometrage
        LIMIT 1
        """
        try:
            with driver.session(database=database) as session:
                rec = session.run(query, num=num_sinistre).single()
                return dict(rec) if rec else {}
        except Exception as e:
            print(f" _fetch_vehicle error ({num_sinistre}): {e}")
            return {}

    # 
    # Indicateurs individuels  utilisent UNIQUEMENT les donnes fetches Neo4j
    # 

    def _check_distance(self, sinistre: Dict, assure: Dict) -> Optional[Neo4jIndicateur]:
        # Coordonnes du sinistre : depuis le nud Sinistre Neo4j
        lat_sin = sinistre.get("latitude_sinistre")
        lon_sin = sinistre.get("longitude_sinistre")
        # Coordonnes de rsidence : depuis le nud Tiers Neo4j
        lat_res = assure.get("adresse_latitude") or assure.get("adresse_siege_latitude")
        lon_res = assure.get("adresse_longitude") or assure.get("adresse_siege_longitude")

        if None in (lat_sin, lon_sin, lat_res, lon_res):
            return None
        try:
            dist = _haversine_km(float(lat_res), float(lon_res), float(lat_sin), float(lon_sin))
        except (TypeError, ValueError):
            return None

        if dist > DISTANCE_SEUIL_KM:
            is_critique = dist > DISTANCE_CRITIQUE_KM
            pts    = POIDS["DIST_SIN_RES"]["pts_critique"] if is_critique else POIDS["DIST_SIN_RES"]["pts_normal"]
            niveau = "critique" if is_critique else "lev"
            return Neo4jIndicateur(
                code="DIST_SIN_RES",
                label="Distance rsidence / sinistre anormale",
                description=f"Sinistre  {dist:.1f} km du domicile (seuil : {DISTANCE_SEUIL_KM} km).",
                points=pts,
                niveau=niveau,
                valeur=round(dist, 1),
            )
        return None

    def _check_usage(self, contrat: Dict, vehicle: Dict) -> Optional[Neo4jIndicateur]:
        # Usage : depuis nud Contrat ou Voiture Neo4j
        usage = _normalize(contrat.get("usage") or vehicle.get("usage") or "")
        for u in USAGES_A_RISQUE:
            if u in usage:
                return Neo4jIndicateur(
                    code="USAGE_RISQUE",
                    label="Usage vhicule  risque lev",
                    description=f"Usage dclar  {usage}  associ  un risque de fraude lev.",
                    points=POIDS["USAGE_RISQUE"]["pts"],
                    niveau="lev",
                    valeur=usage,
                )
        return None

    def _check_profession_marque(self, assure: Dict, vehicle: Dict) -> Optional[Neo4jIndicateur]:
        # Profession : depuis nud Tiers Neo4j | Marque : depuis nud Voiture Neo4j
        profession = _normalize(assure.get("profession") or assure.get("secteur_activite") or "")
        marque     = _normalize(vehicle.get("marque") or "")
        if not profession or not marque:
            return None
        prof_modeste   = any(p in profession for p in PROFESSIONS_MODESTES)
        marque_premium = any(m in marque for m in MARQUES_PREMIUM)
        if prof_modeste and marque_premium:
            return Neo4jIndicateur(
                code="INCOHER_PROF_MARQUE",
                label="Incohrence profession / marque du vhicule",
                description=f"Profession  {profession}  incompatible avec marque  {marque} .",
                points=POIDS["INCOHER_PROF_MARQUE"]["pts"],
                niveau="lev",
                valeur={"profession": profession, "marque": marque},
            )
        return None

    def _check_decalage_declaration(self, sinistre: Dict) -> Tuple[Optional[Neo4jIndicateur], Optional[int]]:
        # Dates : depuis nud Sinistre Neo4j (_fetch_sinistre_node)
        d_sin  = _parse_date(sinistre.get("date_sinistre"))
        d_decl = _parse_date(sinistre.get("date_declaration"))
        if not d_sin or not d_decl:
            return None, None
        nb_jours = (d_decl - d_sin).days

        if nb_jours < 0:
            return Neo4jIndicateur(
                code="DECL_AVANT_SIN",
                label="Dclaration antrieure au sinistre",
                description=f"Dclaration ({d_decl}) antrieure au sinistre ({d_sin}) : impossible.",
                points=POIDS["DECL_AVANT_SIN"]["pts"],
                niveau="critique",
                valeur=nb_jours,
            ), nb_jours

        if nb_jours > DECALAGE_DECLARATION_MAX:
            is_critique = nb_jours > 90
            pts    = POIDS["DECL_TARDIVE"]["pts_critique"] if is_critique else POIDS["DECL_TARDIVE"]["pts_normal"]
            niveau = "critique" if is_critique else "lev"
            return Neo4jIndicateur(
                code="DECL_TARDIVE",
                label="Dclaration tardive",
                description=f"Dclaration {nb_jours} jours aprs le sinistre (seuil : {DECALAGE_DECLARATION_MAX} j).",
                points=pts,
                niveau=niveau,
                valeur=nb_jours,
            ), nb_jours
        return None, nb_jours

    def _check_avant_souscription(self, sinistre: Dict, contrat: Dict) -> Optional[Neo4jIndicateur]:
        # date_sinistre : nud Sinistre Neo4j | date_souscription : nud Contrat Neo4j
        d_sin  = _parse_date(sinistre.get("date_sinistre"))
        d_sous = _parse_date(contrat.get("date_souscription"))
        if not d_sin or not d_sous:
            return None
        delta = (d_sin - d_sous).days
        if delta < 0:
            return Neo4jIndicateur(
                code="SIN_AVANT_SOUSCRIPTION",
                label="Sinistre antrieur  la souscription",
                description=f"Sinistre ({d_sin}) survenu {abs(delta)} j avant la souscription ({d_sous}).",
                points=POIDS["SIN_AVANT_SOUSCRIPTION"]["pts"],
                niveau="critique",
                valeur=delta,
            )
        return None

    def _check_fenetre_expiration(self, sinistre: Dict, contrat: Dict) -> Tuple[Optional[Neo4jIndicateur], Optional[int]]:
        d_sin = _parse_date(sinistre.get("date_sinistre"))
        d_exp = _parse_date(contrat.get("date_expiration"))
        if not d_sin or not d_exp:
            return None, None
        delta = (d_exp - d_sin).days
        if abs(delta) <= FENETRE_EXPIRATION_JOURS:
            direction = "avant" if delta >= 0 else "aprs"
            return Neo4jIndicateur(
                code="FENETRE_EXPIRATION",
                label="Sinistre dans la fentre d'expiration",
                description=f"Sinistre {abs(delta)} j {direction} l'expiration du contrat ({d_exp}).",
                points=POIDS["FENETRE_EXPIRATION"]["pts"],
                niveau="lev",
                valeur=delta,
            ), delta
        return None, delta

    def _check_vehicule_neuf(self, sinistre: Dict, vehicle: Dict) -> Tuple[Optional[Neo4jIndicateur], Optional[float]]:
        # date_sinistre : nud Sinistre Neo4j | date_mise_en_circulation : nud Voiture Neo4j
        d_sin = _parse_date(sinistre.get("date_sinistre"))
        d_cir = _parse_date(vehicle.get("date_mise_en_circulation"))
        if not d_sin or not d_cir:
            return None, None
        age_mois = (d_sin - d_cir).days / 30.44
        if age_mois < AGE_VEHICULE_MIN_MOIS:
            return Neo4jIndicateur(
                code="VEHICULE_TRES_NEUF",
                label="Sinistre sur vhicule trs neuf",
                description=f"Vhicule g de {age_mois:.1f} mois au moment du sinistre (seuil : {AGE_VEHICULE_MIN_MOIS} mois).",
                points=POIDS["VEHICULE_TRES_NEUF"]["pts"],
                niveau="lev",
                valeur=round(age_mois, 1),
            ), round(age_mois, 1)
        return None, round(age_mois, 1)

    def _check_kilometrage(self, vehicle: Dict) -> Tuple[Optional[Neo4jIndicateur], Optional[float]]:
        # kilometrage + date_mise_en_circulation : nud Voiture Neo4j
        km_total = vehicle.get("kilometrage")
        d_cir    = _parse_date(vehicle.get("date_mise_en_circulation"))
        if km_total is None or not d_cir:
            return None, None
        try:
            km_total = float(km_total)
        except (TypeError, ValueError):
            return None, None
        age_ans = (date.today() - d_cir).days / 365.25
        if age_ans <= 0:
            return None, None
        km_annuel = km_total / age_ans
        if km_annuel > KM_ANNUEL_MAX:
            is_critique = km_annuel > 80_000
            pts    = POIDS["KM_ANORMAL"]["pts_critique"] if is_critique else POIDS["KM_ANORMAL"]["pts_normal"]
            niveau = "critique" if is_critique else "lev"
            return Neo4jIndicateur(
                code="KM_ANORMAL",
                label="Kilomtrage annuel anormal",
                description=f"Kilomtrage annuel estim {km_annuel:,.0f} km/an (seuil : {KM_ANNUEL_MAX:,} km/an).",
                points=pts,
                niveau=niveau,
                valeur=round(km_annuel, 0),
            ), round(km_annuel, 0)
        return None, round(km_annuel, 0)

    # 
    # Indicateurs rseau  relations Neo4j (inchangs)
    # 

    def _check_assure_recurrent(self, driver, database: str, num_sinistre: str) -> Optional[Neo4jIndicateur]:
        query = """
        MATCH (s:Sinistre {NUM_SINISTRE: $num})
        OPTIONAL MATCH (a:Tiers)-[:DECLARE]->(s)
        WITH a WHERE a IS NOT NULL
        MATCH (a)-[:DECLARE]->(other:Sinistre)
        WHERE other.NUM_SINISTRE <> $num
        RETURN count(DISTINCT other) AS nb
        """
        try:
            with driver.session(database=database) as session:
                rec = session.run(query, num=num_sinistre).single()
                nb = rec["nb"] if rec else 0
                if nb >= 2:
                    return Neo4jIndicateur(
                        code="ASS_RECURRENT",
                        label="Assur rcurrent dans plusieurs sinistres",
                        description=f"L'assur a dj dclar {nb} autres sinistres.",
                        points=POIDS["ASS_RECURRENT"]["pts"],
                        niveau="lev",
                        valeur=nb,
                        source="reseau",
                    )
        except Exception as e:
            print(f" _check_assure_recurrent error ({num_sinistre}): {e}")
        return None

    def _check_vehicule_recurrent(self, driver, database: str, num_sinistre: str) -> Optional[Neo4jIndicateur]:
        query = """
        MATCH (s:Sinistre {NUM_SINISTRE: $num})
        OPTIONAL MATCH (v:Voiture)-[:IMPLIQUE_DANS]->(s)
        WITH v WHERE v IS NOT NULL
        MATCH (v)-[:IMPLIQUE_DANS]->(other:Sinistre)
        WHERE other.NUM_SINISTRE <> $num
        RETURN count(DISTINCT other) AS nb
        """
        try:
            with driver.session(database=database) as session:
                rec = session.run(query, num=num_sinistre).single()
                nb = rec["nb"] if rec else 0
                if nb >= 2:
                    return Neo4jIndicateur(
                        code="VEH_RECURRENT",
                        label="Vhicule impliqu dans plusieurs sinistres",
                        description=f"Ce vhicule apparat dans {nb} autres sinistres.",
                        points=POIDS["VEH_RECURRENT"]["pts"],
                        niveau="lev",
                        valeur=nb,
                        source="reseau",
                    )
        except Exception as e:
            print(f" _check_vehicule_recurrent error ({num_sinistre}): {e}")
        return None

    def _check_tiers_recurrent(self, driver, database: str, num_sinistre: str) -> Optional[Neo4jIndicateur]:
        query = """
        MATCH (s:Sinistre {NUM_SINISTRE: $num})
        OPTIONAL MATCH (t1:Tiers)-[:PARTICIPE_DANS]->(s)
        OPTIONAL MATCH (t2:Tiers)-[:TEMOIN_DE]->(s)
        WITH s, COLLECT(DISTINCT t1) + COLLECT(DISTINCT t2) AS tiers_list
        UNWIND tiers_list AS tier
        WITH tier WHERE tier IS NOT NULL
        MATCH (tier)-[:PARTICIPE_DANS|TEMOIN_DE]->(other:Sinistre)
        WHERE other.NUM_SINISTRE <> $num
        WITH tier, COUNT(DISTINCT other) AS nb
        WHERE nb >= 2
        RETURN COUNT(DISTINCT tier) AS nb_suspects, SUM(nb) AS total_liens
        """
        try:
            with driver.session(database=database) as session:
                rec = session.run(query, num=num_sinistre).single()
                nb_suspects = rec["nb_suspects"] if rec else 0
                if nb_suspects > 0:
                    return Neo4jIndicateur(
                        code="TIERS_RECURRENT",
                        label="Tiers rcurrent dans plusieurs sinistres",
                        description=f"{nb_suspects} tiers li(s)  ce sinistre prsent(s) dans d'autres sinistres.",
                        points=POIDS["TIERS_RECURRENT"]["pts"],
                        niveau="lev",
                        valeur=nb_suspects,
                        source="reseau",
                    )
        except Exception as e:
            print(f" _check_tiers_recurrent error ({num_sinistre}): {e}")
        return None

    def _check_communaute_suspecte(self, driver, database: str, num_sinistre: str) -> Optional[Neo4jIndicateur]:
        query = """
        MATCH (s:Sinistre {NUM_SINISTRE: $num})
        RETURN s.community_id     AS community_id,
               s.community_niveau AS community_niveau,
               s.community_score  AS community_score
        """
        try:
            with driver.session(database=database) as session:
                rec = session.run(query, num=num_sinistre).single()
                if rec and rec["community_id"] is not None:
                    comm_niveau = rec.get("community_niveau") or "lev"
                    comm_id     = rec["community_id"]
                    pts_bonus   = POIDS["COMMUNAUTE_SUSPECTE"]["pts"]
                    if comm_niveau == "critique":
                        pts_bonus = int(pts_bonus * 1.5)
                    return Neo4jIndicateur(
                        code="COMMUNAUTE_SUSPECTE",
                        label="Membre d'une communaut suspecte",
                        description=f"Ce sinistre appartient  la communaut suspecte #{comm_id} (niveau : {comm_niveau}).",
                        points=pts_bonus,
                        niveau=comm_niveau if comm_niveau in ("critique", "lev", "modr") else "lev",
                        valeur=comm_id,
                        source="reseau",
                    )
        except Exception as e:
            print(f" _check_communaute_suspecte error ({num_sinistre}): {e}")
        return None

    @staticmethod
    def _statut(score: float) -> str:
        if score >= SEUIL_SUSPECT:
            return "fraude"
        if score >= SEUIL_NORMAL:
            return "suspect"
        return "normal"


# 
# Fonctions utilitaires push (inchanges)
# 

def push_neo4j_scores_to_nodes(
    driver,
    database: str,
    num_sinistre: str,
    result: Neo4jFraudResult,
    score_final: float,
    statut_final: str,
) -> bool:
    query = """
    MATCH (s:Sinistre {NUM_SINISTRE: $num})
    SET
        s.score_suspicion_neo4j  = $score_neo4j,
        s.score_suspicion_final  = $score_final,
        s.statut_fraude          = $statut_final,
        s.nb_indicateurs_neo4j   = $nb_indicateurs,
        s.indicateurs_neo4j      = $indicateurs_labels,
        s.etat                   = $etat,
        s.updated_at             = $updated_at
    RETURN s.NUM_SINISTRE AS num
    """
    try:
        indicateurs_labels = [
            f"{i.code}: {i.label} (+{i.points}pts)"
            for i in result.indicateurs
        ]
        etat = "trait" if statut_final == "normal" else "En cours"
        with driver.session(database=database) as session:
            rec = session.run(
                query,
                num=num_sinistre,
                score_neo4j=round(result.score_neo4j, 1),
                score_final=round(score_final, 1),
                statut_final=statut_final,
                nb_indicateurs=len(result.indicateurs),
                indicateurs_labels=indicateurs_labels,
                etat=etat,
                updated_at=datetime.now().isoformat(),
            ).single()
            return rec is not None
    except Exception as e:
        print(f" push_neo4j_scores_to_nodes error ({num_sinistre}): {e}")
        return False


def push_community_labels_to_sinistres(
    driver,
    database: str,
    communities: List[Dict],
) -> int:
    updated = 0
    query = """
    MATCH (s:Sinistre {NUM_SINISTRE: $num})
    SET s.community_id     = $community_id,
        s.community_niveau = $niveau,
        s.community_score  = $score
    """
    try:
        with driver.session(database=database) as session:
            for comm in communities:
                comm_id = comm.get("id")
                niveau  = comm.get("niveau", "modr")
                score   = comm.get("score_max", 0)
                for sin_id in comm.get("sinistres_ids", []):
                    try:
                        session.run(
                            query,
                            num=str(sin_id),
                            community_id=comm_id,
                            niveau=niveau,
                            score=score,
                        )
                        updated += 1
                    except Exception:
                        pass
    except Exception as e:
        print(f" push_community_labels error: {e}")
    return updated
