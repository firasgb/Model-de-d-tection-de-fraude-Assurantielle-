# sinistre_router.py --- VERSION 4.6 (corrigee)
# ============================================================
# ✅ Gestion type physique/morale pour les coordonnees domicile
# ✅ Logs detailles pour le delai de declaration
# ✅ Correction _parse_dt pour dates ISO avec Z

import json
import math
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from io import BytesIO

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter()
pending_notifications: Dict[str, List[Dict]] = defaultdict(list)

# ─── Zones frontieres Tunisie (lat, lon, rayon_km, label) ─────────────────
ZONES_FRONTIERES = [
    (35.17,  8.13, 15.0, "Frontiere Algerie - Kasserine"),
    (36.45,  8.43, 15.0, "Frontiere Algerie - Ghardimaou"),
    (33.13, 11.22, 15.0, "Frontiere Libye - Ben Guerdane"),
    (32.03, 10.58, 15.0, "Frontiere Libye - Dhiba"),
    (36.82, 10.23, 10.0, "Port de Tunis"),
]

# ─── Helper dates ──────────────────────────────────────────────────────────
def _parse_dt(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=None)
    try:
        s = str(val).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except Exception:
        pass
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"]:
        try:
            return datetime.strptime(str(val), fmt)
        except:
            continue
    return None

def _safe_float(val, default=None):
    try:
        v = float(val)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except:
        return default

def _haversine(lat1, lon1, lat2, lon2) -> float:
    try:
        if any(v is None for v in [lat1, lon1, lat2, lon2]):
            return 0.0
        R = 6371.0
        lat1, lon1, lat2, lon2 = map(math.radians,
                                     [float(lat1), float(lon1),
                                      float(lat2), float(lon2)])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = (math.sin(dlat/2)**2
             + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2)
        return R * 2 * math.asin(math.sqrt(max(0.0, min(1.0, a))))
    except:
        return 0.0

def _is_near_frontiere(lat_sin, lon_sin) -> tuple[float, str]:
    """Retourne (1.0, label_zone) si sinistre dans une zone frontiere, sinon (0.0, '')."""
    if lat_sin is None or lon_sin is None:
        return 0.0, ""
    for zlat, zlon, zrayon, zlabel in ZONES_FRONTIERES:
        dist = _haversine(zlat, zlon, lat_sin, lon_sin)
        if dist <= zrayon:
            return 1.0, zlabel
    return 0.0, ""

# ─── Recuperation des donnees Neo4j ───────────────────────────────────────
def _fetch_sinistre_data(neo4j_loader, num_sinistre: str) -> dict:
    sinistre_data = {}
    if not neo4j_loader or not neo4j_loader.driver:
        return sinistre_data

    with neo4j_loader.driver.session(database=neo4j_loader.database) as session:

        # 1. Sinistre
        r = session.run("""
            MATCH (s:Sinistre)
            WHERE s.num_sinistre = $ns OR s.NUM_SINISTRE = $ns
            RETURN s
        """, ns=num_sinistre)
        rec = r.single()
        if not rec:
            raise ValueError(f"Sinistre {num_sinistre} non trouve")
        sinistre_data.update(dict(rec["s"]))
        print(f"   ✅ Sinistre trouve : {num_sinistre}")

        # 2. Assure via DECLARE
        r2 = session.run("""
            MATCH (a:Assure)-[:DECLARE]->(s:Sinistre)
            WHERE s.num_sinistre = $ns OR s.NUM_SINISTRE = $ns
            RETURN a LIMIT 1
        """, ns=num_sinistre)
        rec2 = r2.single()
        if rec2:
            assure = dict(rec2["a"])
            sinistre_data.update(assure)
            assure_type = assure.get("type", "physique")
            print(f"   ✅ Assure trouve (type={assure_type}) : {assure.get('nom')} {assure.get('prenom')}")
            if assure_type == "morale":
                print(f"      | Siege: lat={assure.get('adresse_siege_latitude')}, lon={assure.get('adresse_siege_longitude')}")
            else:
                print(f"      | Domicile: lat={assure.get('adresse_latitude')}, lon={assure.get('adresse_longitude')}")
        else:
            email_fallback = sinistre_data.get("email_assure") or sinistre_data.get("email")
            if email_fallback:
                r2b = session.run("""
                    MATCH (a:Assure) WHERE a.email = $email RETURN a LIMIT 1
                """, email=email_fallback)
                rec2b = r2b.single()
                if rec2b:
                    assure = dict(rec2b["a"])
                    sinistre_data.update(assure)
                    print(f"   ✅ Assure trouve (fallback email)")
                else:
                    print("   ⚠️ Aucun Assure trouve meme via email")
            else:
                print("   ⚠️ Aucun Assure trouve et pas d'email_assure dans le sinistre")

        # 3. Contrat via Assure-[:SOUSCRIT]->Contrat
        email = sinistre_data.get("email")
        if email:
            r3 = session.run("""
                MATCH (a:Assure)-[:SOUSCRIT]->(c:Contrat)
                WHERE a.email = $email
                RETURN c ORDER BY c.date_souscription DESC LIMIT 1
            """, email=email)
            rec3 = r3.single()
            if rec3:
                contrat = dict(rec3["c"])
                for k, v in contrat.items():
                    sinistre_data[f"contrat_{k}"] = v
                print(f"   ✅ Contrat trouve : {contrat.get('numero_contrat')} | prime={contrat.get('prime_annuelle')} TND")
            else:
                print("   ⚠️ Aucun Contrat trouve pour cet assure")
        else:
            print("   ⚠️ Email manquant --- Contrat non recuperable")

        # 4. Voiture via Contrat-[:COUVRE]->Voiture
        email = sinistre_data.get("email")
        if email:
            r4 = session.run("""
                MATCH (a:Assure)-[:SOUSCRIT]->(c:Contrat)-[:COUVRE]->(v:Voiture)
                WHERE a.email = $email RETURN v LIMIT 1
            """, email=email)
            rec4 = r4.single()
            if rec4:
                voiture = dict(rec4["v"])
                sinistre_data.update(voiture)
                print(f"   ✅ Voiture trouvee (via Contrat) : {voiture.get('immatriculation')}")
            else:
                r4b = session.run("""
                    MATCH (v:Voiture)-[:IMPLIQUE_DANS]->(s:Sinistre)
                    WHERE s.num_sinistre = $ns OR s.NUM_SINISTRE = $ns
                    RETURN v LIMIT 1
                """, ns=num_sinistre)
                rec4b = r4b.single()
                if rec4b:
                    voiture = dict(rec4b["v"])
                    sinistre_data.update(voiture)
                    print(f"   ✅ Voiture trouvee (fallback IMPLIQUE_DANS) : {voiture.get('immatriculation')}")
                else:
                    print("   ⚠️ Aucune Voiture trouvee")

        # 5. Tiers adverses via PARTICIPE_DANS
        r5 = session.run("""
            MATCH (t:Tiers)-[:PARTICIPE_DANS]->(s:Sinistre)
            WHERE s.num_sinistre = $ns OR s.NUM_SINISTRE = $ns
            RETURN collect(t.immatriculation) AS immat_adverses,
                   count(t) AS nb_tiers
        """, ns=num_sinistre)
        rec5 = r5.single()
        if rec5 and rec5["nb_tiers"] > 0:
            sinistre_data["nb_tiers_adverse"] = rec5["nb_tiers"]
            sinistre_data["immatriculations_adverses"] = rec5["immat_adverses"]
            print(f"   ✅ Tiers adverses : {rec5['nb_tiers']}")

        # 6. Temoins via TEMOIN_DE
        r6 = session.run("""
            MATCH (t:Temoin)-[:TEMOIN_DE]->(s:Sinistre)
            WHERE s.num_sinistre = $ns OR s.NUM_SINISTRE = $ns
            RETURN collect(t.cin) AS cins_temoins, count(t) AS nb_temoins
        """, ns=num_sinistre)
        rec6 = r6.single()
        if rec6 and rec6["nb_temoins"] > 0:
            sinistre_data["nb_temoins"] = rec6["nb_temoins"]
            sinistre_data["cins_temoins"] = rec6["cins_temoins"]
            print(f"   ✅ Temoins : {rec6['nb_temoins']} | CINs : {rec6['cins_temoins']}")

    return sinistre_data

# ─── Requetes reseau Neo4j ─────────────────────────────────────────────────
def _fetch_network_features(neo4j_loader, sinistre_data: dict) -> dict:
    """Calcule les features reseau/frequence depuis Neo4j."""
    nf = {}
    if not neo4j_loader or not neo4j_loader.driver:
        return nf

    immat       = sinistre_data.get("immatriculation")
    email       = sinistre_data.get("email")
    cins_temoins = sinistre_data.get("cins_temoins", [])
    immat_adverses = sinistre_data.get("immatriculations_adverses", [])
    date_sin    = _parse_dt(sinistre_data.get("date_sinistre"))
    num_sin     = sinistre_data.get("num_sinistre") or sinistre_data.get("NUM_SINISTRE")
    date_12m_avant = (date_sin - timedelta(days=365)).isoformat() if date_sin else None
    date_30j_avant = (date_sin - timedelta(days=30)).isoformat()  if date_sin else None

    with neo4j_loader.driver.session(database=neo4j_loader.database) as session:

        if immat:
            r = session.run("""
                MATCH (v:Voiture)-[:IMPLIQUE_DANS]->(s:Sinistre)
                WHERE v.immatriculation = $immat
                  AND s.num_sinistre <> $ns
                RETURN count(s) AS nb
            """, immat=immat, ns=num_sin or "")
            rec = r.single()
            nf["nbr_sinistres_vehicule"] = float(rec["nb"]) if rec else 0.0
            print(f"   ✅ nbr_sinistres_vehicule={nf['nbr_sinistres_vehicule']}")

        if cins_temoins:
            r = session.run("""
                MATCH (t:Temoin)-[:TEMOIN_DE]->(s:Sinistre)
                WHERE t.cin IN $cins
                WITH t.cin AS cin, count(DISTINCT s) AS nb_sins
                RETURN max(nb_sins) AS max_freq, count(cin) AS nb_temoins_freq
            """, cins=cins_temoins)
            rec = r.single()
            if rec and rec["max_freq"]:
                nf["freq_temoin"]    = float(rec["max_freq"])
                nf["temoin_frequent"] = 1.0 if rec["max_freq"] >= 3 else 0.0
            else:
                nf["freq_temoin"]    = 0.0
                nf["temoin_frequent"] = 0.0
            print(f"   ✅ freq_temoin={nf['freq_temoin']} | temoin_frequent={nf['temoin_frequent']}")

        if immat_adverses:
            r = session.run("""
                MATCH (t:Tiers)-[:PARTICIPE_DANS]->(s:Sinistre)
                WHERE t.immatriculation IN $immat_adverses
                  AND s.num_sinistre <> $ns
                WITH t.immatriculation AS immat, count(DISTINCT s) AS nb_sins
                RETURN max(nb_sins) AS max_freq
            """, immat_adverses=immat_adverses, ns=num_sin or "")
            rec = r.single()
            if rec and rec["max_freq"]:
                nf["nbr_sinistres_adverse"] = float(rec["max_freq"])
                nf["adverse_repete"]        = 1.0 if rec["max_freq"] >= 2 else 0.0
            else:
                nf["nbr_sinistres_adverse"] = 0.0
                nf["adverse_repete"]        = 0.0
            print(f"   ✅ nbr_sinistres_adverse={nf['nbr_sinistres_adverse']} | adverse_repete={nf['adverse_repete']}")

        if email and date_12m_avant:
            r = session.run("""
                MATCH (a:Assure)-[:DECLARE]->(s:Sinistre)
                WHERE a.email = $email
                  AND s.num_sinistre <> $ns
                  AND s.date_sinistre >= $d12m
                RETURN count(s) AS nb
            """, email=email, ns=num_sin or "", d12m=date_12m_avant)
            rec = r.single()
            nb_12m = float(rec["nb"]) if rec else 0.0
            nf["client_plus3_sinistres_12m"] = 1.0 if nb_12m >= 3 else 0.0
            nf["client_plus7_sinistres_12m"] = 1.0 if nb_12m >= 7 else 0.0
            print(f"   ✅ sinistres client 12m={nb_12m} | plus3={nf['client_plus3_sinistres_12m']} | plus7={nf['client_plus7_sinistres_12m']}")

        if immat and date_30j_avant and date_sin:
            r = session.run("""
                MATCH (v:Voiture)-[:IMPLIQUE_DANS]->(s:Sinistre)
                WHERE v.immatriculation = $immat
                  AND s.num_sinistre <> $ns
                  AND s.date_sinistre >= $d30j
                  AND s.date_sinistre <= $dsin
                RETURN count(s) AS nb
            """, immat=immat, ns=num_sin or "",
                d30j=date_30j_avant, dsin=date_sin.isoformat())
            rec = r.single()
            nf["cluster_temporel_vehicule"] = 1.0 if rec and rec["nb"] >= 1 else 0.0
            print(f"   ✅ cluster_temporel_vehicule={nf['cluster_temporel_vehicule']}")

        if email and date_30j_avant and date_sin:
            r = session.run("""
                MATCH (a:Assure)-[:DECLARE]->(s:Sinistre)
                WHERE a.email = $email
                  AND s.num_sinistre <> $ns
                  AND s.date_sinistre >= $d30j
                  AND s.date_sinistre <= $dsin
                RETURN count(s) AS nb
            """, email=email, ns=num_sin or "",
                d30j=date_30j_avant, dsin=date_sin.isoformat())
            rec = r.single()
            nf["cluster_temporel_client"] = 1.0 if rec and rec["nb"] >= 1 else 0.0
            print(f"   ✅ cluster_temporel_client={nf['cluster_temporel_client']}")

        date_7j_avant = (date_sin - timedelta(days=7)).isoformat() if date_sin else None
        if immat and date_7j_avant and date_sin:
            r = session.run("""
                MATCH (v:Voiture)-[:IMPLIQUE_DANS]->(s:Sinistre)
                WHERE v.immatriculation = $immat
                  AND s.num_sinistre <> $ns
                  AND s.date_sinistre >= $d7j
                  AND s.date_sinistre <= $dsin
                RETURN count(s) AS nb
            """, immat=immat, ns=num_sin or "",
                d7j=date_7j_avant, dsin=date_sin.isoformat())
            rec = r.single()
            nf["velocite_recente_vehicule"] = float(rec["nb"]) if rec else 0.0
            print(f"   ✅ velocite_recente_vehicule={nf['velocite_recente_vehicule']}")

        if email and date_7j_avant and date_sin:
            r = session.run("""
                MATCH (a:Assure)-[:DECLARE]->(s:Sinistre)
                WHERE a.email = $email
                  AND s.num_sinistre <> $ns
                  AND s.date_sinistre >= $d7j
                  AND s.date_sinistre <= $dsin
                RETURN count(s) AS nb
            """, email=email, ns=num_sin or "",
                d7j=date_7j_avant, dsin=date_sin.isoformat())
            rec = r.single()
            nf["velocite_recente_client"] = float(rec["nb"]) if rec else 0.0
            print(f"   ✅ velocite_recente_client={nf['velocite_recente_client']}")

    return nf

# ─── Extraction des features ──────────────────────────────────────────────
def _build_raw_features(sinistre_data: dict, neo4j_loader=None, fraud_detector=None) -> dict:
    fd = {}

    print("\n🔎 [DEBUG] _build_raw_features")
    print(f"   date_sinistre      : {sinistre_data.get('date_sinistre')}")
    print(f"   date_declaration   : {sinistre_data.get('date_declaration')}")
    print(f"   latitude_sinistre  : {sinistre_data.get('latitude_sinistre')}")
    print(f"   longitude_sinistre : {sinistre_data.get('longitude_sinistre')}")
    print(f"   type_assure        : {sinistre_data.get('type')}")
    print(f"   adresse_latitude    (physique): {sinistre_data.get('adresse_latitude')}")
    print(f"   adresse_longitude   (physique): {sinistre_data.get('adresse_longitude')}")
    print(f"   adresse_siege_latitude (morale): {sinistre_data.get('adresse_siege_latitude')}")
    print(f"   adresse_siege_longitude(morale): {sinistre_data.get('adresse_siege_longitude')}")
    print(f"   contrat_usage      : {sinistre_data.get('contrat_usage')}")
    print(f"   montant            : {sinistre_data.get('montant')}")

    # ── Delai declaration (indicateur unique > 15 jours) ──────────────
    date_sin  = _parse_dt(sinistre_data.get("date_sinistre"))
    date_decl = _parse_dt(sinistre_data.get("date_declaration"))

    if date_sin and date_decl:
        delta = (date_decl - date_sin).days
        fd["declaration_tardive_15j"] = 1.0 if delta > 15 else 0.0
        print(f"   ✅ Delai declaration = {delta} jours --> declaration_tardive_15j={fd['declaration_tardive_15j']}")
    else:
        fd["declaration_tardive_15j"] = 0.0
        print(f"   ❌ Dates manquantes pour le delai de declaration (sin={date_sin}, decl={date_decl})")

    # ── Heure / weekend ────────────────────────────────────────────────
    if date_sin:
        fd["sinistre_heure_nuit"] = 1.0 if 0 <= date_sin.hour < 5 else 0.0
        fd["sinistre_weekend"]    = 1.0 if date_sin.weekday() >= 5 else 0.0
        print(f"   Heure={date_sin.hour}h --> sinistre_heure_nuit={fd['sinistre_heure_nuit']} | sinistre_weekend={fd['sinistre_weekend']}")
    else:
        fd["sinistre_heure_nuit"] = 0.0
        fd["sinistre_weekend"]    = 0.0

    # ── Distance GPS domicile --> sinistre (selon type physique/morale) ──
    lat_sin = _safe_float(sinistre_data.get("latitude_sinistre"))
    lon_sin = _safe_float(sinistre_data.get("longitude_sinistre"))

    assure_type = sinistre_data.get("type", "physique")  # par defaut physique
    if assure_type == "morale":
        lat_dom = _safe_float(sinistre_data.get("adresse_siege_latitude"))
        lon_dom = _safe_float(sinistre_data.get("adresse_siege_longitude"))
        print(f"   🏢 Type morale --> utilisation adresse siege")
    else:
        lat_dom = _safe_float(sinistre_data.get("adresse_latitude"))
        lon_dom = _safe_float(sinistre_data.get("adresse_longitude"))
        print(f"   🏠 Type physique --> utilisation adresse residence")

    print(f"   📍 Domicile (type {assure_type}) : lat={lat_dom}, lon={lon_dom}")
    print(f"   📍 Sinistre : lat={lat_sin}, lon={lon_sin}")

    if all(v is not None for v in [lat_sin, lon_sin, lat_dom, lon_dom]):
        dist = _haversine(lat_dom, lon_dom, lat_sin, lon_sin)
        fd["distance_sinistre_residence_km"]     = dist
        fd["distance_sinistre_residence_elevee"] = 1.0 if dist > 30 else 0.0
        print(f"   ✅ Distance = {dist:.2f} km --> elevee={fd['distance_sinistre_residence_elevee']}")
    else:
        fd["distance_sinistre_residence_km"]     = 0.0
        fd["distance_sinistre_residence_elevee"] = 0.0
        print("   ❌ Coordonnees GPS manquantes --> distance a 0")

    # ── Zone frontiere ─────────────────────────────────────────────────
    frontiere_flag, frontiere_label = _is_near_frontiere(lat_sin, lon_sin)
    fd["sinistre_frontiere"] = frontiere_flag
    if frontiere_flag:
        print(f"   🚨 Sinistre en zone frontiere : {frontiere_label}")
    else:
        print("   ✅ Sinistre hors zone frontiere")

    # ── Sinistre proche prise d'effet (7j) ────────────────────────────
    date_effet = _parse_dt(sinistre_data.get("contrat_date_souscription"))
    if date_sin and date_effet:
        jours_apres_effet = (date_sin - date_effet).days
        fd["sinistre_moins_7j_apres_effet"] = 1.0 if 0 <= jours_apres_effet < 7 else 0.0
        print(f"   ✅ Jours apres souscription = {jours_apres_effet} --> moins_7j_effet={fd['sinistre_moins_7j_apres_effet']}")
    else:
        fd["sinistre_moins_7j_apres_effet"] = 0.0

    # ── Sinistre proche expiration (7j) ───────────────────────────────
    date_exp = _parse_dt(sinistre_data.get("contrat_date_expiration"))
    if date_sin and date_exp:
        jours_avant_exp = (date_exp - date_sin).days
        fd["sinistre_moins_7j_expiration"] = 1.0 if 0 <= jours_avant_exp < 7 else 0.0
        print(f"   ✅ Jours avant expiration = {jours_avant_exp} --> moins_7j_exp={fd['sinistre_moins_7j_expiration']}")
    else:
        fd["sinistre_moins_7j_expiration"] = 0.0

    # ── Montant vs moyenne globale des primes ─────────────────────────
    montant = _safe_float(sinistre_data.get("montant"), default=0.0)
    moyenne_primes_globale = 0.0

    if neo4j_loader and neo4j_loader.driver and montant and montant > 0:
        try:
            with neo4j_loader.driver.session(database=neo4j_loader.database) as session:
                r = session.run("""
                    MATCH (c:Contrat)
                    WHERE c.prime_annuelle IS NOT NULL AND c.prime_annuelle > 0
                    RETURN avg(toFloat(c.prime_annuelle)) AS moyenne_primes
                """)
                rec = r.single()
                if rec and rec["moyenne_primes"] is not None:
                    moyenne_primes_globale = float(rec["moyenne_primes"])
                    print(f"   ✅ Moyenne primes globale = {moyenne_primes_globale:.2f} TND")
                else:
                    print("   ⚠️ Aucune prime trouvee dans Neo4j")
        except Exception as e:
            print(f"   ⚠️ Erreur lecture moyenne primes : {e}")

# APRÈS
    if moyenne_primes_globale <= 0:
        print("   ⚠️ Moyenne primes globale indisponible --> FIN_10X_PRIME desactive")
        fd["ratio_montant_prime"] = 0.0
        fd["montant_10x_prime"]   = 0.0
    elif montant > 0:
        ratio = montant / moyenne_primes_globale
        fd["ratio_montant_prime"] = ratio
        fd["montant_10x_prime"]   = 1.0 if montant > moyenne_primes_globale * 10 else 0.0
        print(f"   ✅ Montant={montant} / MoyenneGlobale={moyenne_primes_globale:.2f} --> ratio={ratio:.2f} | montant_10x={fd['montant_10x_prime']}")
    else:
        fd["ratio_montant_prime"] = 0.0
        fd["montant_10x_prime"]   = 0.0
        print(f"   ⚠️ Montant=0 --> ratio=0")
    # ── Usage a risque (contrat_usage uniquement) ──────────────────────
    usage_risque_keywords = ["taxi", "location", "louage", "transport"]
    contrat_usage = str(sinistre_data.get("contrat_usage") or "").lower().strip()
    fd["usage_risque"] = 1.0 if any(k in contrat_usage for k in usage_risque_keywords) else 0.0
    print(f"   contrat_usage='{contrat_usage}' --> usage_risque={fd['usage_risque']}")

    # ── Features reseau/frequence (requetes Neo4j dediees) ────────────
    network_defaults = {
        "nbr_sinistres_vehicule":   0.0,
        "freq_temoin":              0.0,
        "temoin_frequent":          0.0,
        "nbr_sinistres_adverse":    0.0,
        "adverse_repete":           0.0,
        "cluster_temporel_vehicule":0.0,
        "cluster_temporel_client":  0.0,
        "client_plus3_sinistres_12m":0.0,
        "client_plus7_sinistres_12m":0.0,
        "velocite_recente_vehicule":0.0,
        "velocite_recente_client":  0.0,
        "sinistre_frontiere":       0.0,
    }
    for k, v in network_defaults.items():
        fd.setdefault(k, v)

    if neo4j_loader and neo4j_loader.driver:
        try:
            nf = _fetch_network_features(neo4j_loader, sinistre_data)
            fd.update(nf)
        except Exception as e:
            print(f"   ⚠️ Erreur features reseau : {e}")

    # ── Features desactivees --- forcees a 0 ────────────────────────────
    for k in [
        "montant_3std_suspect", "ratio_montant_moyen", "ratio_montant_median",
        "expert_cout_anormal", "ratio_montant_pv_global", "incoherence_age_montant",
        "note_conducteur_faible", "note_conducteur_tres_faible",
    ]:
        fd[k] = 0.0

    return fd

# ─── Mise a jour Neo4j ─────────────────────────────────────────────────────
def _update_sinistre_neo4j(neo4j_loader, num_sinistre: str, score_result: dict):
    if not neo4j_loader or not neo4j_loader.driver:
        return
    try:
        with neo4j_loader.driver.session(database=neo4j_loader.database) as session:
            indicateurs_json_list = [
                json.dumps({
                    "code":   ind.get("code", ""),
                    "label":  ind.get("label", ""),
                    "pts":    ind.get("pts", 0),
                    "group":  ind.get("group", ""),
                    "niveau": ind.get("niveau", "modere")
                }, ensure_ascii=False)
                for ind in score_result.get("indicateurs_detectes", [])
            ]
            scores_groupes_json = json.dumps(
                score_result.get("scores_groupes", {}), ensure_ascii=False
            )
            statut_raw = score_result["statut_fraude"]
            statut_normalise = "normal" if statut_raw == "non_frauduleux" else statut_raw

            session.run("""
                MATCH (s:Sinistre)
                WHERE s.num_sinistre = $ns OR s.NUM_SINISTRE = $ns
                SET s.score_suspicion_final = $score,
                    s.statut_fraude         = $statut,
                    s.niveau_risque         = $niveau,
                    s.etat                  = 'traite',
                    s.date_traitement       = $now,
                    s.nb_indicateurs        = $nb,
                    s.indicateurs_detectes  = $indicateurs,
                    s.score_groupes         = $groupes
            """, {
                "ns":          num_sinistre,
                "score":       score_result["score_suspicion"],
                "statut":      statut_normalise,
                "niveau":      score_result["niveau_risque"],
                "now":         datetime.now().isoformat(),
                "nb":          len(score_result.get("indicateurs_detectes", [])),
                "indicateurs": indicateurs_json_list,
                "groupes":     scores_groupes_json,
            })
            print(f"   ✅ Neo4j mis a jour : {num_sinistre} --> score={score_result['score_suspicion']} | statut={statut_normalise}")
    except Exception as e:
        print(f"   ⚠️ Erreur mise a jour Neo4j : {e}")

# ─── Generation PDF ────────────────────────────────────────────────────────
def _generate_pdf_report(num_sinistre: str, sinistre_data: dict, score_result: dict) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle, HRFlowable)
        from reportlab.lib.enums import TA_CENTER
    except ImportError:
        return b""

    PAGE_W = A4[0] - 4 * cm
    score  = score_result["score_suspicion"]
    statut = score_result["statut_fraude"]
    niveau = score_result["niveau_risque"]
    scores_groupes = score_result.get("scores_groupes", {})
    indicateurs    = score_result.get("indicateurs_detectes", [])

    GROUP_LABELS = {
        "financial": "Financier", "temporal": "Temporel",
        "frequency": "Frequence", "network": "Reseau / Collusion",
        "driver":    "Conducteur / Mobilite", "profile": "Profil Assure",
    }
    GROUP_CAPS = {
        "financial": 35, "temporal": 35, "frequency": 30,
        "network": 22,   "driver": 8,   "profile": 1,
    }

    if statut == "frauduleux":
        c_main = colors.HexColor("#C53030"); c_bg = colors.HexColor("#FED7D7")
        label_statut = f"🚨 FRAUDULEUX --- Score {score:.1f}/100"
    elif statut == "suspect":
        c_main = colors.HexColor("#C05621"); c_bg = colors.HexColor("#FEEBC8")
        label_statut = f"⚠️ SUSPECT --- Score {score:.1f}/100"
    else:
        c_main = colors.HexColor("#276749"); c_bg = colors.HexColor("#C6F6D5")
        label_statut = f"✅ NON FRAUDULEUX --- Score {score:.1f}/100"

    styles = getSampleStyleSheet()
    def sty(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    s_title  = sty("T", fontSize=16, textColor=colors.HexColor("#1A365D"),
                   alignment=TA_CENTER, spaceAfter=4, fontName="Helvetica-Bold")
    s_sub    = sty("S", fontSize=9,  textColor=colors.HexColor("#718096"),
                   alignment=TA_CENTER, spaceAfter=16)
    s_footer = sty("F", fontSize=7,  textColor=colors.HexColor("#9CA3AF"),
                   alignment=TA_CENTER)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=1.8*cm, bottomMargin=1.8*cm,
                            title=f"Rapport Fraude Sinistre {num_sinistre}")
    story = []

    story.append(Paragraph("RAPPORT DE DÉTECTION DE FRAUDE", s_title))
    story.append(Paragraph(
        f"Sinistre N°{num_sinistre}  |  {datetime.now().strftime('%d/%m/%Y %H:%M')}", s_sub))
    story.append(HRFlowable(width="100%", thickness=2, color=c_main))
    story.append(Spacer(1, 10))

    st_table = Table([[label_statut],
                      [f"Niveau de risque : {niveau.upper()}"]],
                     colWidths=[PAGE_W])
    st_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), c_bg),
        ("TEXTCOLOR",     (0,0), (-1,0), c_main),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("BOX",           (0,0), (-1,-1), 1.5, c_main),
    ]))
    story.append(st_table)
    story.append(Spacer(1, 14))

    if scores_groupes:
        story.append(Paragraph("📊 SCORE PAR GROUPE",
            sty("H2", fontSize=12, fontName="Helvetica-Bold", spaceAfter=8)))
        gdata = [["Groupe", "Score", "Max", "Utilisation"]]
        for g, sc in scores_groupes.items():
            cap = GROUP_CAPS.get(g, 0)
            pct = f"{sc/cap*100:.0f}%" if cap > 0 else "0%"
            gdata.append([GROUP_LABELS.get(g, g), f"{sc:.1f}", str(cap), pct])
        gt = Table(gdata, colWidths=[5.5*cm, 2.5*cm, 2.5*cm, 2.5*cm])
        gt.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), colors.HexColor("#4A5568")),
            ("TEXTCOLOR",     (0,0), (-1,0), colors.white),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 9),
            ("ALIGN",         (1,0), (-1,-1), "CENTER"),
            ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#E2E8F0")),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(gt)
        story.append(Spacer(1, 14))

    sin_data = [
        ["N° Sinistre",      str(num_sinistre)],
        ["Date survenance",  str(sinistre_data.get("date_sinistre", "-"))],
        ["Date declaration", str(sinistre_data.get("date_declaration", "-"))],
        ["Immatriculation",  str(sinistre_data.get("immatriculation_assure", "-"))],
        ["Montant declare",  f"{sinistre_data.get('montant', 0):,.0f} TND"],
        ["Prime contrat",    f"{sinistre_data.get('contrat_prime_annuelle', 0):,.0f} TND"],
        ["Score final",      f"{score:.1f} / 100"],
        ["Statut",           statut.upper()],
    ]
    sin_table = Table(sin_data, colWidths=[5*cm, PAGE_W - 5*cm])
    sin_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (0,-1), colors.HexColor("#EDF2F7")),
        ("FONTNAME",      (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 9),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#E2E8F0")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(sin_table)
    story.append(Spacer(1, 14))

    if indicateurs:
        story.append(Paragraph(
            f"⚠️ INDICATEURS DÉTECTÉS ({len(indicateurs)})",
            sty("H2", fontSize=12, fontName="Helvetica-Bold", spaceAfter=8,
                textColor=colors.HexColor("#C05621"))))
        ind_data = [["Groupe", "Code", "Indicateur", "Points"]]
        total_pts = 0
        for ind in indicateurs:
            pts = ind.get("pts", 0)
            total_pts += pts
            ind_data.append([
                GROUP_LABELS.get(ind.get("group", "-"), ind.get("group", "-")),
                ind.get("code", "-"),
                ind.get("label", "-"),
                f"+{pts}",
            ])
        ind_data.append(["", "TOTAL", f"Score final : {score:.1f} / 100", str(total_pts)])

        ind_table = Table(ind_data,
                          colWidths=[3*cm, 3.2*cm, PAGE_W - 8.2*cm, 2*cm])
        ind_style = TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), colors.HexColor("#C05621")),
            ("TEXTCOLOR",     (0,0), (-1,0), colors.white),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 8),
            ("ALIGN",         (3,0), (3,-1), "CENTER"),
            ("GRID",          (0,0), (-1,-2), 0.4, colors.HexColor("#E2E8F0")),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("BACKGROUND",    (0,-1), (-1,-1), colors.HexColor("#2D3748")),
            ("TEXTCOLOR",     (0,-1), (-1,-1), colors.white),
            ("FONTNAME",      (0,-1), (-1,-1), "Helvetica-Bold"),
        ])
        for i in range(1, len(ind_data)-1):
            if i % 2 == 0:
                ind_style.add("BACKGROUND", (0,i), (-1,i), colors.HexColor("#FFF5F0"))
        ind_table.setStyle(ind_style)
        story.append(ind_table)
        story.append(Spacer(1, 14))
    else:
        story.append(Paragraph(
            "✅ Aucun indicateur de fraude detecte.",
            sty("OK", fontSize=10, textColor=colors.HexColor("#276749"), spaceAfter=14)))

    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor("#CBD5E0")))
    story.append(Spacer(1, 5))
    story.append(Paragraph(
        f"Rapport genere le {datetime.now().strftime('%d/%m/%Y a %H:%M:%S')} "
        f"| AutoFraud v4.6 --- Sinistre {num_sinistre}", s_footer))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ════════════════════════════════════════════════════════════════════════════
# ROUTES PRINCIPALES
# ════════════════════════════════════════════════════════════════════════════

@router.post("/process/{num_sinistre}")
async def process_sinistre(num_sinistre: str, request: Request):
    fraud_detector = request.app.state.fraud_detector
    neo4j_loader   = request.app.state.neo4j_loader

    if fraud_detector is None or not fraud_detector.is_fitted:
        raise HTTPException(503, "Modele non entraîne")
    if neo4j_loader is None or not neo4j_loader.driver:
        raise HTTPException(503, "Neo4j non connecte")

    try:
        sinistre_data = _fetch_sinistre_data(neo4j_loader, num_sinistre)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erreur lecture Neo4j : {e}")

    raw_features = _build_raw_features(sinistre_data, neo4j_loader, fraud_detector)
    score_result = fraud_detector.score_single(raw_features)

    print("\n🔎 FEATURES NON NULLES :")
    for k, v in raw_features.items():
        if v not in (0, 0.0, None):
            print(f"   {k}: {v}")

    print(f"\n🔍 SCORING {num_sinistre} --> "
          f"score={score_result['score_suspicion']} | "
          f"statut={score_result['statut_fraude']} | "
          f"nb_indicateurs={len(score_result['indicateurs_detectes'])}")
    for ind in score_result['indicateurs_detectes']:
        print(f"   - {ind['code']}: {ind['label']} (+{ind['pts']})")

    _update_sinistre_neo4j(neo4j_loader, num_sinistre, score_result)

    email_assure = sinistre_data.get("email") or sinistre_data.get("email_assure")
    if email_assure:
        notif = {
            "id":              f"sinistre_{num_sinistre}_{uuid.uuid4().hex[:8]}",
            "type":            "sinistre_normal",
            "title":           "✅ Sinistre enregistre avec succes",
            "message":         (f"Votre sinistre N°{num_sinistre} a ete enregistre "
                                f"(score : {score_result['score_suspicion']}/100)."),
            "priority":        "low",
            "num_sinistre":    num_sinistre,
            "score_suspicion": score_result['score_suspicion'],
            "statut_sinistre": score_result['statut_fraude'],
            "niveau_risque":   score_result['niveau_risque'],
            "nb_indicateurs":  len(score_result['indicateurs_detectes']),
            "indicateurs": [
                {
                    "code":   ind.get("code", "?"),
                    "label":  ind.get("label", ""),
                    "points": ind.get("pts", 0),
                    "niveau": ind.get("niveau", "modere")
                }
                for ind in score_result['indicateurs_detectes'][:10]
            ],
            "date":     datetime.now().isoformat(),
            "lu":       False,
            "archived": False,
        }
        pending_notifications[email_assure].append(notif)
        print(f"   📧 Notification mise en file pour : {email_assure}")

    return {
        "success":      True,
        "num_sinistre": num_sinistre,
        "score_result": score_result,
        "notified":     bool(email_assure),
    }

@router.get("/pending-notifications/{email}")
async def get_pending_notifications(email: str):
    notifs = pending_notifications.pop(email, [])
    return {"success": True, "email": email, "notifications": notifs, "count": len(notifs)}

@router.get("/rapport/{num_sinistre}/pdf")
async def get_sinistre_neo4j_pdf(num_sinistre: str, request: Request):
    fraud_detector = request.app.state.fraud_detector
    neo4j_loader   = request.app.state.neo4j_loader

    if not neo4j_loader or not neo4j_loader.driver:
        raise HTTPException(503, "Neo4j non connecte")
    if fraud_detector is None or not fraud_detector.is_fitted:
        raise HTTPException(503, "Modele non entraîne")

    try:
        sinistre_data = _fetch_sinistre_data(neo4j_loader, num_sinistre)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erreur lecture Neo4j : {e}")

    raw_features = _build_raw_features(sinistre_data, neo4j_loader, fraud_detector)
    score_result = fraud_detector.score_single(raw_features)
    pdf_bytes    = _generate_pdf_report(num_sinistre, sinistre_data, score_result)

    if not pdf_bytes:
        raise HTTPException(500, "Erreur generation PDF (reportlab manquant ?)")

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition":
                 f"attachment; filename=rapport_sinistre_{num_sinistre}.pdf"},
    )

@router.get("/{num_sinistre}/pdf")
async def get_sinistre_pdf_alias(num_sinistre: str, request: Request):
    return await get_sinistre_neo4j_pdf(num_sinistre, request)

@router.get("/neo4j-list")
async def list_neo4j_sinistres(request: Request):
    neo4j_loader = request.app.state.neo4j_loader
    if not neo4j_loader or not neo4j_loader.driver:
        raise HTTPException(503, "Neo4j non connecte")
    try:
        with neo4j_loader.driver.session(database=neo4j_loader.database) as session:
            result = session.run("""
                MATCH (s:Sinistre)
                RETURN s.num_sinistre           AS num_sinistre,
                       s.date_sinistre          AS date_sinistre,
                       s.immatriculation_assure AS immatriculation_assure,
                       s.type_degat             AS type_degat,
                       s.montant                AS montant,
                       s.score_suspicion_final  AS score,
                       s.statut_fraude          AS statut_fraude,
                       s.etat                   AS etat
                ORDER BY s.date_sinistre DESC
            """)
            sinistres = []
            for record in result:
                sinistres.append({
                    "num_sinistre":           record["num_sinistre"],
                    "date_sinistre":          record["date_sinistre"],
                    "immatriculation_assure": record["immatriculation_assure"],
                    "type_degat":             record["type_degat"],
                    "montant":                record["montant"] or 0,
                    "score":                  record["score"]   or 0,
                    "statut_fraude":          record["statut_fraude"] or "normal",
                    "etat":                   record["etat"]    or "En cours",
                })
            return {"success": True, "sinistres": sinistres}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/{num_sinistre}/rapport")
async def get_sinistre_rapport(num_sinistre: str, request: Request):
    neo4j_loader = request.app.state.neo4j_loader
    if not neo4j_loader or not neo4j_loader.driver:
        raise HTTPException(503, "Neo4j non connecte")
    try:
        sinistre_data = _fetch_sinistre_data(neo4j_loader, num_sinistre)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erreur lecture Neo4j : {e}")

    return {
        "num_sinistre":  num_sinistre,
        "score":         sinistre_data.get("score_suspicion_final", 0),
        "statut_fraude": sinistre_data.get("statut_fraude", "normal"),
        "niveau_risque": sinistre_data.get("niveau_risque", "faible"),
        "nb_indicateurs":sinistre_data.get("nb_indicateurs", 0),
        "indicateurs":   sinistre_data.get("indicateurs_detectes", []),
        "score_groupes": sinistre_data.get("score_groupes", {}),
    }