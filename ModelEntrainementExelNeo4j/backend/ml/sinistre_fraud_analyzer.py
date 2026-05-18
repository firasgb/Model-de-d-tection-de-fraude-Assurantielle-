"""
sinistre_fraud_analyzer.py
==========================
Calcule le score de suspicion et le statut (normal / suspect / fraude)
pour chaque sinistre soumis, à partir des données Assure + Sinistre + Neo4j.

Indicateurs individuels :
  1. Distance résidence ↔ sinistre  (> 30 km → flag)
  2. Usage à risque (taxi / louage / location)
  3. Incohérence profession ↔ marque véhicule
  4. Décalage date sinistre / date déclaration  (> 30 j → flag)
  5. Décalage date sinistre / date souscription (sinistre avant souscription)
  6. Décalage date sinistre / date expiration   (≤ 7 j avant/après fin)
  7. Âge véhicule au moment du sinistre         (< 6 mois → flag)
  8. Kilométrage annuel anormal                 (> 40 000 km/an → flag)

Indicateurs réseau (via Neo4j) :
  9. Assuré récurrent dans plusieurs sinistres (≥ 2)
 10. Véhicule impliqué dans plusieurs sinistres (≥ 2)
 11. Tiers (participant ou témoin) présent dans plusieurs sinistres (≥ 2)

Seuils finaux :
  score < 30   → normal
  30 ≤ score < 60 → suspect
  score ≥ 60   → fraude
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

# ══════════════════════════════════════════════════════════════════════════════
# Constantes & tables de référence
# ══════════════════════════════════════════════════════════════════════════════

SEUIL_NORMAL  = 30
SEUIL_SUSPECT = 60

# Usages véhicule considérés à risque élevé
USAGES_A_RISQUE = {
    "taxi", "louage", "location", "transport en commun",
    "transport public", "vtc", "autobus", "camion",
}

# Marques considérées "premium/luxe"
MARQUES_PREMIUM = {
    "bmw", "mercedes", "mercedes-benz", "audi", "porsche",
    "jaguar", "land rover", "lexus", "maserati", "ferrari",
    "lamborghini", "bentley", "rolls-royce", "tesla",
    "volvo", "infiniti", "cadillac", "range rover",
}

# Professions modestes → incohérence avec véhicule premium
PROFESSIONS_MODESTES = {
    "jardinier", "agent d'entretien", "femme de ménage", "ouvrier",
    "manœuvre", "agriculteur", "gardien", "vigile", "plongeur",
    "livreur", "conducteur", "chauffeur", "aide soignant",
    "agent de sécurité", "manutentionnaire", "balayeur", "porteur",
    "peintre en bâtiment", "plâtrier", "carreleur", "soudeur",
    "sans emploi", "chômeur", "retraité modeste",
}

# Kilométrage moyen annuel acceptable (km/an)
KM_ANNUEL_MAX = 40_000

# Âge véhicule minimal en mois avant sinistre (sinistre sur véhicule très neuf = suspect)
AGE_VEHICULE_MIN_MOIS = 6

# Décalage déclaration (jours)
DECALAGE_DECLARATION_MAX = 30

# Fenêtre de risque autour de l'expiration du contrat (jours)
FENETRE_EXPIRATION_JOURS = 7

# Points réseau
POINTS_ASS_RECURRENT = 10
POINTS_VEH_RECURRENT = 10
POINTS_TIERS_RECURRENT = 10


# ══════════════════════════════════════════════════════════════════════════════
# Structures de données résultat
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Indicateur:
    code: str
    label: str
    description: str
    points: int          # Points de suspicion ajoutés
    niveau: str          # "critique" | "élevé" | "modéré"
    valeur: Any = None   # Valeur calculée (pour le rapport)


@dataclass
class FraudAnalysisResult:
    score: float
    statut: str                          # "normal" | "suspect" | "fraude"
    indicateurs: List[Indicateur] = field(default_factory=list)
    details: Dict[str, Any]      = field(default_factory=dict)
    rapport_lignes: List[str]    = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score_suspicion": round(self.score, 1),
            "statut": self.statut,
            "indicateurs": [
                {
                    "code": i.code,
                    "label": i.label,
                    "description": i.description,
                    "points": i.points,
                    "niveau": i.niveau,
                    "valeur": i.valeur,
                }
                for i in self.indicateurs
            ],
            "details": self.details,
            "rapport": self.rapport_lignes,
            "nb_indicateurs": len(self.indicateurs),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Utilitaires
# ══════════════════════════════════════════════════════════════════════════════

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance en km entre deux coordonnées GPS (formule de Haversine)."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlam  = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_date(val: Any) -> Optional[date]:
    """Parse une date depuis str, datetime ou date."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S.%f"):
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


def _diff_days(d1: date, d2: date) -> int:
    """Retourne (d2 - d1).days"""
    return (d2 - d1).days


# ══════════════════════════════════════════════════════════════════════════════
# Analyseur principal
# ══════════════════════════════════════════════════════════════════════════════

class SinistreFraudAnalyzer:
    """
    Utilisation :
        analyzer = SinistreFraudAnalyzer()
        result   = analyzer.analyze(sinistre_data, assure_data, contrat_data,
                                    neo4j_driver=driver, neo4j_database=database)
        print(result.to_dict())
    """

    def analyze(
        self,
        sinistre: Dict[str, Any],
        assure: Dict[str, Any],
        contrat: Dict[str, Any],
        neo4j_driver: Any = None,
        neo4j_database: str = "neo4j",
    ) -> FraudAnalysisResult:
        """
        Parameters
        ----------
        sinistre : dict  — champs du modèle Sinistre
        assure   : dict  — champs du modèle Assure (physique)
        contrat  : dict  — contrat lié (date_debut, date_expiration, usage,
                           marque, date_mise_en_circulation, kilometrage,
                           date_souscription)
        neo4j_driver : driver Neo4j (optionnel) pour les indicateurs réseau
        neo4j_database : str (nom de la base, par défaut "neo4j")
        """
        indicateurs: List[Indicateur] = []
        details: Dict[str, Any] = {}

        # ── 1. Distance résidence ↔ lieu du sinistre ─────────────────────────
        ind = self._check_distance(sinistre, assure)
        if ind:
            indicateurs.append(ind)
            details["distance_km"] = ind.valeur

        # ── 2. Usage à risque ────────────────────────────────────────────────
        ind = self._check_usage(contrat)
        if ind:
            indicateurs.append(ind)

        # ── 3. Incohérence profession ↔ marque ───────────────────────────────
        ind = self._check_profession_marque(assure, contrat)
        if ind:
            indicateurs.append(ind)

        # ── 4. Décalage déclaration ──────────────────────────────────────────
        ind, nb_jours = self._check_decalage_declaration(sinistre)
        if ind:
            indicateurs.append(ind)
            details["decalage_declaration_jours"] = nb_jours

        # ── 5. Sinistre avant souscription ───────────────────────────────────
        ind = self._check_avant_souscription(sinistre, contrat)
        if ind:
            indicateurs.append(ind)

        # ── 6. Fenêtre expiration contrat ────────────────────────────────────
        ind, delta = self._check_fenetre_expiration(sinistre, contrat)
        if ind:
            indicateurs.append(ind)
            details["delta_expiration_jours"] = delta

        # ── 7. Véhicule très neuf ────────────────────────────────────────────
        ind, age_mois = self._check_vehicule_neuf(sinistre, contrat)
        if ind:
            indicateurs.append(ind)
            details["age_vehicule_mois"] = age_mois

        # ── 8. Kilométrage anormal ───────────────────────────────────────────
        ind, km_an = self._check_kilometrage(contrat)
        if ind:
            indicateurs.append(ind)
            details["kilometrage_annuel"] = km_an

        # ── INDICATEURS RÉSEAU (Neo4j) ───────────────────────────────────────
        if neo4j_driver is not None:
            sinistre_num = sinistre.get("num_sinistre")
            email = sinistre.get("email_assure")
            immat = sinistre.get("immatriculation_assure")

            # 9. Assuré récurrent
            ind = self._check_assure_recurrent(neo4j_driver, neo4j_database, sinistre_num, email)
            if ind:
                indicateurs.append(ind)

            # 10. Véhicule récurrent
            ind = self._check_vehicule_recurrent(neo4j_driver, neo4j_database, sinistre_num, immat)
            if ind:
                indicateurs.append(ind)

            # 11. Tiers récurrent
            ind = self._check_tiers_recurrent(neo4j_driver, neo4j_database, sinistre_num)
            if ind:
                indicateurs.append(ind)

        # ── Score final ──────────────────────────────────────────────────────
        score = min(sum(i.points for i in indicateurs), 100)
        statut = self._statut(score)

        # ── Rapport texte ────────────────────────────────────────────────────
        rapport = self._build_rapport(sinistre, assure, contrat, indicateurs, score, statut, details)

        return FraudAnalysisResult(
            score=score,
            statut=statut,
            indicateurs=indicateurs,
            details=details,
            rapport_lignes=rapport,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Indicateurs individuels (inchangés)
    # ─────────────────────────────────────────────────────────────────────────

    def _check_distance(self, sinistre: Dict, assure: Dict) -> Optional[Indicateur]:
        lat_sin = sinistre.get("latitude_sinistre")
        lon_sin = sinistre.get("longitude_sinistre")
        lat_res = assure.get("adresse_latitude") or assure.get("adresse_siege_latitude")
        lon_res = assure.get("adresse_longitude") or assure.get("adresse_siege_longitude")
        if None in (lat_sin, lon_sin, lat_res, lon_res):
            return None
        try:
            dist = _haversine_km(float(lat_res), float(lon_res), float(lat_sin), float(lon_sin))
        except (TypeError, ValueError):
            return None
        if dist > 30:
            niveau = "critique" if dist > 100 else "élevé"
            pts    = 25 if dist > 100 else 15
            return Indicateur(
                code="DIST_SIN_RES",
                label="Distance résidence / sinistre anormale",
                description=f"Le sinistre s'est produit à {dist:.1f} km du domicile de l'assuré (seuil : 30 km).",
                points=pts,
                niveau=niveau,
                valeur=round(dist, 1),
            )
        return None

    def _check_usage(self, contrat: Dict) -> Optional[Indicateur]:
        usage = _normalize(contrat.get("usage") or contrat.get("USAGE") or "")
        for u in USAGES_A_RISQUE:
            if u in usage:
                return Indicateur(
                    code="USAGE_RISQUE",
                    label="Usage véhicule à risque élevé",
                    description=f"L'usage déclaré « {usage} » est associé à un risque de fraude élevé.",
                    points=15,
                    niveau="élevé",
                    valeur=usage,
                )
        return None

    def _check_profession_marque(self, assure: Dict, contrat: Dict) -> Optional[Indicateur]:
        profession = _normalize(assure.get("profession") or assure.get("secteur_activite") or "")
        marque     = _normalize(contrat.get("marque") or contrat.get("MARQUE") or "")
        if not profession or not marque:
            return None
        prof_modeste  = any(p in profession for p in PROFESSIONS_MODESTES)
        marque_premium = any(m in marque for m in MARQUES_PREMIUM)
        if prof_modeste and marque_premium:
            return Indicateur(
                code="INCOHER_PROF_MARQUE",
                label="Incohérence profession / marque du véhicule",
                description=f"La profession « {profession} » semble incompatible avec la marque « {marque} ».",
                points=20,
                niveau="élevé",
                valeur={"profession": profession, "marque": marque},
            )
        return None

    def _check_decalage_declaration(self, sinistre: Dict) -> Tuple[Optional[Indicateur], Optional[int]]:
        d_sin  = _parse_date(sinistre.get("date_sinistre"))
        d_decl = _parse_date(sinistre.get("date_declaration") or sinistre.get("date_ouverture"))
        if not d_sin or not d_decl:
            return None, None
        nb_jours = _diff_days(d_sin, d_decl)
        if nb_jours < 0:
            return Indicateur(
                code="DECL_AVANT_SIN",
                label="Déclaration antérieure au sinistre",
                description=f"La date de déclaration ({d_decl}) est antérieure à la date du sinistre ({d_sin}).",
                points=35,
                niveau="critique",
                valeur=nb_jours,
            ), nb_jours
        if nb_jours > DECALAGE_DECLARATION_MAX:
            pts    = 25 if nb_jours > 90 else 15
            niveau = "critique" if nb_jours > 90 else "élevé"
            return Indicateur(
                code="DECL_TARDIVE",
                label="Déclaration tardive",
                description=f"La déclaration a été effectuée {nb_jours} jours après le sinistre (seuil : {DECALAGE_DECLARATION_MAX} jours).",
                points=pts,
                niveau=niveau,
                valeur=nb_jours,
            ), nb_jours
        return None, nb_jours

    def _check_avant_souscription(self, sinistre: Dict, contrat: Dict) -> Optional[Indicateur]:
        d_sin  = _parse_date(sinistre.get("date_sinistre"))
        d_sous = _parse_date(contrat.get("date_souscription") or contrat.get("date_debut") or contrat.get("DATE_DEBUT"))
        if not d_sin or not d_sous:
            return None
        delta = _diff_days(d_sous, d_sin)
        if delta < 0:
            return Indicateur(
                code="SIN_AVANT_SOUSCRIPTION",
                label="Sinistre antérieur à la souscription",
                description=f"Le sinistre ({d_sin}) est survenu {abs(delta)} jours avant la souscription ({d_sous}).",
                points=40,
                niveau="critique",
                valeur=delta,
            )
        return None

    def _check_fenetre_expiration(self, sinistre: Dict, contrat: Dict) -> Tuple[Optional[Indicateur], Optional[int]]:
        d_sin = _parse_date(sinistre.get("date_sinistre"))
        d_exp = _parse_date(contrat.get("date_expiration") or contrat.get("DATE_EXPIRATION"))
        if not d_sin or not d_exp:
            return None, None
        delta = _diff_days(d_sin, d_exp)
        if abs(delta) <= FENETRE_EXPIRATION_JOURS:
            direction = "avant" if delta >= 0 else "après"
            return Indicateur(
                code="FENETRE_EXPIRATION",
                label="Sinistre dans la fenêtre d'expiration",
                description=f"Le sinistre a eu lieu {abs(delta)} jours {direction} l'expiration ({d_exp}).",
                points=20,
                niveau="élevé",
                valeur=delta,
            ), delta
        return None, delta

    def _check_vehicule_neuf(self, sinistre: Dict, contrat: Dict) -> Tuple[Optional[Indicateur], Optional[float]]:
        d_sin = _parse_date(sinistre.get("date_sinistre"))
        d_cir = _parse_date(contrat.get("date_mise_en_circulation") or contrat.get("DATE_MISE_EN_CIRCULATION") or contrat.get("date_premiere_circulation"))
        if not d_sin or not d_cir:
            return None, None
        age_jours = _diff_days(d_cir, d_sin)
        age_mois  = age_jours / 30.44
        if age_mois < AGE_VEHICULE_MIN_MOIS:
            return Indicateur(
                code="VEHICULE_TRES_NEUF",
                label="Sinistre sur véhicule très neuf",
                description=f"Le véhicule n'avait que {age_mois:.1f} mois (seuil : {AGE_VEHICULE_MIN_MOIS} mois).",
                points=20,
                niveau="élevé",
                valeur=round(age_mois, 1),
            ), round(age_mois, 1)
        return None, round(age_mois, 1)

    def _check_kilometrage(self, contrat: Dict) -> Tuple[Optional[Indicateur], Optional[float]]:
        km_total = contrat.get("kilometrage") or contrat.get("KILOMETRAGE")
        d_cir    = _parse_date(contrat.get("date_mise_en_circulation") or contrat.get("DATE_MISE_EN_CIRCULATION"))
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
            pts    = 25 if km_annuel > 80_000 else 15
            niveau = "critique" if km_annuel > 80_000 else "élevé"
            return Indicateur(
                code="KM_ANORMAL",
                label="Kilométrage annuel anormal",
                description=f"Kilométrage annuel estimé ({km_annuel:,.0f} km/an) dépasse le seuil ({KM_ANNUEL_MAX:,} km/an).",
                points=pts,
                niveau=niveau,
                valeur=round(km_annuel, 0),
            ), round(km_annuel, 0)
        return None, round(km_annuel, 0)

    # ─────────────────────────────────────────────────────────────────────────
    # Indicateurs réseau (Neo4j)
    # ─────────────────────────────────────────────────────────────────────────

    def _check_assure_recurrent(self, driver, database: str, sinistre_num: str, email: str) -> Optional[Indicateur]:
        if not email or driver is None:
            return None
        query = """
        MATCH (a:Tiers {email: $email})-[:DECLARE]->(s:Sinistre)
        WHERE s.NUM_SINISTRE <> $current_num
        RETURN count(s) AS nb
        """
        with driver.session(database=database) as session:
            rec = session.run(query, email=email, current_num=sinistre_num).single()
            nb = rec["nb"] if rec else 0
            if nb >= 2:
                return Indicateur(
                    code="ASS_RECURRENT",
                    label="Assuré récurrent dans plusieurs sinistres",
                    description=f"L'assuré a déjà déclaré {nb} sinistres (hors celui-ci).",
                    points=POINTS_ASS_RECURRENT,
                    niveau="élevé",
                    valeur=nb
                )
        return None

    def _check_vehicule_recurrent(self, driver, database: str, sinistre_num: str, immat: str) -> Optional[Indicateur]:
        if not immat or driver is None:
            return None
        query = """
        MATCH (v:Voiture {immatriculation: $immat})-[:IMPLIQUE_DANS]->(s:Sinistre)
        WHERE s.NUM_SINISTRE <> $current_num
        RETURN count(s) AS nb
        """
        with driver.session(database=database) as session:
            rec = session.run(query, immat=immat, current_num=sinistre_num).single()
            nb = rec["nb"] if rec else 0
            if nb >= 2:
                return Indicateur(
                    code="VEH_RECURRENT",
                    label="Véhicule impliqué dans plusieurs sinistres",
                    description=f"Ce véhicule apparaît dans {nb} autres sinistres.",
                    points=POINTS_VEH_RECURRENT,
                    niveau="élevé",
                    valeur=nb
                )
        return None

    def _check_tiers_recurrent(self, driver, database: str, sinistre_num: str) -> Optional[Indicateur]:
        """
        Cherche tous les tiers liés à ce sinistre (PAR PARTICIPE_DANS ou TEMOIN_DE)
        et vérifie si l'un d'eux a participé à au moins 2 sinistres (hors celui-ci).
        """
        if driver is None:
            return None
        query = """
        MATCH (s:Sinistre {NUM_SINISTRE: $current_num})
        OPTIONAL MATCH (t1:Tiers)-[:PARTICIPE_DANS]->(s)
        OPTIONAL MATCH (t2:Tiers)-[:TEMOIN_DE]->(s)
        WITH s, COLLECT(DISTINCT t1) + COLLECT(DISTINCT t2) AS tiers_list
        UNWIND tiers_list AS tier
        WITH tier WHERE tier IS NOT NULL
        MATCH (tier)-[:PARTICIPE_DANS|TEMOIN_DE]->(otherSinistre)
        WHERE otherSinistre.NUM_SINISTRE <> $current_num
        WITH tier, COUNT(DISTINCT otherSinistre) AS nb
        WHERE nb >= 2
        RETURN COUNT(DISTINCT tier) AS nb_tiers_suspects
        """
        with driver.session(database=database) as session:
            rec = session.run(query, current_num=sinistre_num).single()
            nb_tiers = rec["nb_tiers_suspects"] if rec else 0
            if nb_tiers > 0:
                return Indicateur(
                    code="TIERS_RECURRENT",
                    label="Tiers impliqué dans plusieurs sinistres",
                    description=f"Un ou plusieurs tiers liés à ce sinistre sont apparus dans {nb_tiers} autres sinistres.",
                    points=POINTS_TIERS_RECURRENT,
                    niveau="élevé",
                    valeur=nb_tiers
                )
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Statut et rapport
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _statut(score: float) -> str:
        if score >= SEUIL_SUSPECT:
            return "fraude"
        if score >= SEUIL_NORMAL:
            return "suspect"
        return "normal"

    @staticmethod
    def _build_rapport(sinistre: Dict, assure: Dict, contrat: Dict,
                       indicateurs: List[Indicateur], score: float, statut: str,
                       details: Dict) -> List[str]:
        lignes = []
        num = sinistre.get("num_sinistre", "N/A")
        email = sinistre.get("email_assure", assure.get("email", "N/A"))
        now = datetime.now().strftime("%d/%m/%Y %H:%M")

        lignes.append("=" * 60)
        lignes.append(f"RAPPORT D'ANALYSE — SINISTRE N° {num}")
        lignes.append(f"Généré le : {now}")
        lignes.append("=" * 60)
        lignes.append("")

        lignes.append("── IDENTIFICATION ──────────────────────────────────────")
        lignes.append(f"  Assuré        : {assure.get('nom', '')} {assure.get('prenom', '')}")
        lignes.append(f"  Email         : {email}")
        lignes.append(f"  Immatriculation : {sinistre.get('immatriculation_assure', 'N/A')}")
        lignes.append(f"  Date sinistre : {sinistre.get('date_sinistre', 'N/A')}")
        lignes.append(f"  Lieu          : {sinistre.get('adresse_sinistre', 'N/A')}")
        lignes.append("")

        emoji = {"fraude": "🚨", "suspect": "⚠️", "normal": "✅"}[statut]
        lignes.append("── RÉSULTAT ────────────────────────────────────────────")
        lignes.append(f"  Score de suspicion : {score:.1f} / 100")
        lignes.append(f"  Statut             : {emoji} {statut.upper()}")
        lignes.append("")

        if indicateurs:
            lignes.append(f"── INDICATEURS DÉTECTÉS ({len(indicateurs)}) ──────────────────────")
            for i, ind in enumerate(indicateurs, 1):
                niv_emoji = {"critique": "🔴", "élevé": "🟠", "modéré": "🟡"}.get(ind.niveau, "⚪")
                lignes.append(f"  {i}. {niv_emoji} [{ind.code}] {ind.label} (+{ind.points} pts)")
                lignes.append(f"     → {ind.description}")
            lignes.append("")
        else:
            lignes.append("── INDICATEURS ─────────────────────────────────────────")
            lignes.append("  ✅ Aucun indicateur de fraude détecté.")
            lignes.append("")

        lignes.append("── RECOMMANDATION ──────────────────────────────────────")
        if statut == "fraude":
            lignes.append("  🚨 Ce sinistre présente de forts indices de fraude.")
            lignes.append("     → Transmission immédiate au service anti-fraude.")
            lignes.append("     → Suspension du remboursement en attente d'enquête.")
        elif statut == "suspect":
            lignes.append("  ⚠️  Ce sinistre nécessite une vérification approfondie.")
            lignes.append("     → Demander des justificatifs complémentaires.")
            lignes.append("     → Planifier une expertise sur site.")
        else:
            lignes.append("  ✅ Aucune anomalie majeure détectée.")
            lignes.append("     → Traitement normal du sinistre.")

        lignes.append("")
        lignes.append("=" * 60)
        return lignes