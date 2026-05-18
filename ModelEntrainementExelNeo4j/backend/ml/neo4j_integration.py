"""
neo4j_integration.py  —  Pipeline Neo4j indépendant (ML intégré)
=================================================================
- Détecte automatiquement la clé des nœuds Sinistre (NUM_SINISTRE ou num_sinistre)
- Calcule les indicateurs et le score de fraude pour TOUS les sinistres Neo4j
- Entraîne un modèle non‑supervisé (IsolationForest / LOF / EllipticEnvelope)
- Pousse les scores dans Neo4j
- Génère des notifications pour les sinistres suspects / frauduleux
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from ml.neo4j_fraud_indicators import Neo4jFraudIndicators, Neo4jFraudResult
from ml.neo4j_fraud_detector import Neo4jFraudDetector

# ─── Seuils ──────────────────────────────────────────────────────────────────
SEUIL_NORMAL_MAX  = 49.99
SEUIL_SUSPECT_MIN = 50.0
SEUIL_FRAUDULEUX  = 70.0


def _detect_sinistre_key(driver, database: str) -> str:
    """Détecte la casse de la propriété utilisée comme clé primaire."""
    query = "MATCH (s:Sinistre) RETURN keys(s) AS k LIMIT 1"
    try:
        with driver.session(database=database) as session:
            rec = session.run(query).single()
            if rec:
                keys = rec["k"]
                if "NUM_SINISTRE" in keys:
                    return "NUM_SINISTRE"
                if "num_sinistre" in keys:
                    return "num_sinistre"
                for k in keys:
                    if k.upper() == "NUM_SINISTRE":
                        return k
    except Exception as e:
        print(f"   ⚠️ _detect_sinistre_key error: {e}")
    return "NUM_SINISTRE"


def _find_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


# ─── Fonctions de push (redéfinies ici pour accepter sinistre_key) ───────────
def push_neo4j_scores_to_nodes(
    driver,
    database: str,
    num_sinistre: str,
    result: Neo4jFraudResult,
    score_final: float,
    statut_final: str,
    sinistre_key: str = "NUM_SINISTRE",
) -> bool:
    query = f"""
    MATCH (s:Sinistre {{{sinistre_key}: $num}})
    SET
        s.score_suspicion_neo4j  = $score_neo4j,
        s.score_suspicion_final  = $score_final,
        s.statut_fraude          = $statut_final,
        s.nb_indicateurs_neo4j   = $nb_indicateurs,
        s.indicateurs_neo4j      = $indicateurs_labels,
        s.etat                   = $etat,
        s.updated_at             = $updated_at
    RETURN s.{sinistre_key} AS num
    """
    try:
        indicateurs_labels = [
            f"{i.code}: {i.label} (+{i.points}pts)"
            for i in result.indicateurs
        ]
        etat = "traité" if statut_final == "normal" else "En cours"
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
        print(f"⚠️ push_neo4j_scores_to_nodes error ({num_sinistre}): {e}")
        return False


def push_community_labels_to_sinistres(
    driver,
    database: str,
    communities: List[Dict],
    sinistre_key: str = "NUM_SINISTRE",
) -> int:
    updated = 0
    query = f"""
    MATCH (s:Sinistre {{{sinistre_key}: $num}})
    SET s.community_id     = $community_id,
        s.community_niveau = $niveau,
        s.community_score  = $score
    """
    try:
        with driver.session(database=database) as session:
            for comm in communities:
                comm_id = comm.get("id")
                niveau  = comm.get("niveau", "modéré")
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
        print(f"⚠️ push_community_labels error: {e}")
    return updated


# ─── Tag communautés ─────────────────────────────────────────────────────────
def tag_communities(neo4j_loader, community_detector) -> int:
    if community_detector is None or neo4j_loader is None or neo4j_loader.driver is None:
        print("⚠️ tag_communities: Neo4j non disponible")
        return 0
    print("🔍 Tag communautés suspectes sur les nœuds Sinistre...")
    try:
        analysis = community_detector.get_full_analysis(force_refresh=True)
        communities = analysis.get("communities", [])
        sinistre_key = _detect_sinistre_key(neo4j_loader.driver, neo4j_loader.database)
        n_updated = push_community_labels_to_sinistres(
            neo4j_loader.driver,
            neo4j_loader.database,
            communities,
            sinistre_key=sinistre_key
        )
        print(f"   ✅ {n_updated} nœuds Sinistre taggés ({len(communities)} communautés)")
        return n_updated
    except Exception as e:
        print(f"   ❌ Erreur tag_communities: {e}")
        return 0


# ─── Calcul des scores Neo4j ─────────────────────────────────────────────────
def compute_all_neo4j_scores(
    sinistres_df: pd.DataFrame,
    neo4j_loader,
    batch_size: int = 50,
) -> Dict[str, Neo4jFraudResult]:
    if neo4j_loader is None or neo4j_loader.driver is None:
        print("⚠️ compute_all_neo4j_scores: Neo4j non disponible")
        return {}

    driver   = neo4j_loader.driver
    database = neo4j_loader.database

    # Détection de la clé
    sinistre_key = _detect_sinistre_key(driver, database)
    print(f"   🔑 Clé Sinistre détectée : '{sinistre_key}'")

    print("🔍 Récupération des sinistres existants dans Neo4j...")
    try:
        with driver.session(database=database) as session:
            records = session.run(
                f"MATCH (s:Sinistre) RETURN s.{sinistre_key} AS num"
            )
            neo4j_nums = {rec["num"] for rec in records if rec["num"]}
    except Exception as e:
        print(f"   ❌ Impossible de lister les sinistres Neo4j: {e}")
        return {}

    print(f"   ✅ {len(neo4j_nums)} sinistres trouvés dans Neo4j")

    if not neo4j_nums:
        print("   ⚠️ Aucun sinistre dans Neo4j")
        return {}

    # Vérification optionnelle de l'intersection avec le DataFrame Excel
    col_num = _find_col(sinistres_df, ["NUM_SINISTRE", "num_sinistre"])
    if col_num is not None:
        mask = sinistres_df[col_num].astype(str).isin(neo4j_nums)
        n_commun = mask.sum()
        print(f"   → {n_commun} sinistres en commun avec Excel (info)")
    else:
        print("   ⚠️ Colonne NUM_SINISTRE absente du fichier Excel – les pipelines sont indépendants")

    # Traiter tous les sinistres Neo4j (pas seulement l'intersection)
    analyzer    = Neo4jFraudIndicators()
    results_map = {}

    print(f"🔬 Calcul indicateurs Neo4j pour {len(neo4j_nums)} sinistres...")
    for i, num in enumerate(neo4j_nums):
        if i > 0 and i % batch_size == 0:
            print(f"   → {i}/{len(neo4j_nums)} ({i/len(neo4j_nums)*100:.0f}%)")
        if not num or str(num) == "nan":
            continue
        try:
            result = analyzer.compute(
                num_sinistre=str(num),
                driver=driver,
                database=database,
            )
            results_map[str(num)] = result
        except Exception as e:
            print(f"   ⚠️ Erreur sinistre {num}: {e}")
            continue

    print(f"   ✅ {len(results_map)} scores Neo4j calculés")
    return results_map


# ─── Pipeline complet (indépendant) ──────────────────────────────────────────
def run_neo4j_pipeline(
    fraud_detector,
    sinistres_df: pd.DataFrame,
    neo4j_loader,
    community_detector,
    pending_notifications: Dict[str, List[Dict]],
) -> Dict[str, Any]:
    stats = {
        "communities_tagged": 0,
        "neo4j_scores_computed": 0,
        "nodes_updated": 0,
        "notifications_queued": 0,
        "frauduleux": 0,
        "suspects": 0,
        "normaux": 0,
    }

    if neo4j_loader is None or neo4j_loader.driver is None:
        print("⚠️ run_neo4j_pipeline: Neo4j non disponible – pipeline ignoré")
        return stats

    print("\n" + "═" * 60)
    print("🚀 PIPELINE NEO4J — Démarrage (indépendant, données 100% Neo4j)")
    print("═" * 60)

    # 1. Tag communautés
    stats["communities_tagged"] = tag_communities(neo4j_loader, community_detector)

    # 2. Extraire les indicateurs Neo4j
    neo4j_results = compute_all_neo4j_scores(sinistres_df, neo4j_loader)
    stats["neo4j_scores_computed"] = len(neo4j_results)

    if not neo4j_results:
        print("⚠️ Aucun sinistre Neo4j à traiter, pas de modèle ML entraîné.")
        return stats

    # 3. Entraîner le détecteur ML Neo4j
    print("🧠 Entraînement du modèle ML Neo4j...")
    neo4j_detector = Neo4jFraudDetector()
    neo4j_detector.fit(neo4j_results)
    fraud_detector._neo4j_detector = neo4j_detector
    fraud_detector._neo4j_results = neo4j_results

    # 4. Pousser les scores dans Neo4j (avec la clé détectée)
    sinistre_key = _detect_sinistre_key(neo4j_loader.driver, neo4j_loader.database)
    print(f"📤 Push scores Neo4j (clé = '{sinistre_key}')...")
    updated = 0
    for num, result in neo4j_results.items():
        pred = neo4j_detector.predict(num)
        ok = push_neo4j_scores_to_nodes(
            driver=neo4j_loader.driver,
            database=neo4j_loader.database,
            num_sinistre=num,
            result=result,
            score_final=pred['score'],
            statut_final=pred['statut'],
            sinistre_key=sinistre_key,
        )
        if ok:
            updated += 1
            if pred['score'] >= 70:
                stats["frauduleux"] += 1
            elif pred['score'] >= 50:
                stats["suspects"] += 1
            else:
                stats["normaux"] += 1
    stats["nodes_updated"] = updated

    # 5. Générer les notifications
    print("🔔 Génération des notifications (Neo4j uniquement)...")
    notifications_queued = 0
    for num, result in neo4j_results.items():
        pred = neo4j_detector.predict(num)
        if pred['score'] >= 50:   # suspect ou frauduleux
            email = _fetch_email_for_sinistre(
                neo4j_loader.driver,
                neo4j_loader.database,
                num,
                sinistre_key=sinistre_key,
            )
            if email:
                notif = _build_neo4j_notification(
                    num_sinistre=num,
                    score=pred['score'],
                    statut=pred['statut'],
                    indicateurs=pred.get('indicateurs', [])
                )
                if email not in pending_notifications:
                    pending_notifications[email] = []
                pending_notifications[email].append(notif)
                notifications_queued += 1
    stats["notifications_queued"] = notifications_queued

    # ── Logs récapitulatifs ──────────────────────────────────────────────────
    n = stats["neo4j_scores_computed"]
    print("═" * 60)
    print("✅ PIPELINE NEO4J TERMINÉ")
    print(f"   Communautés taggées  : {stats['communities_tagged']}")
    print(f"   Scores Neo4j calculés: {n}")
    print(f"   Nœuds mis à jour     : {stats['nodes_updated']}")
    print(f"   Notifications        : {stats['notifications_queued']}")
    if n > 0:
        print(f"   Frauduleux Neo4j     : {stats['frauduleux']} ({stats['frauduleux']/n*100:.1f}%)")
        print(f"   Suspects Neo4j       : {stats['suspects']} ({stats['suspects']/n*100:.1f}%)")
        print(f"   Normaux Neo4j        : {stats['normaux']} ({stats['normaux']/n*100:.1f}%)")
    print("═" * 60 + "\n")

    return stats


# ─── Helpers email et notification ───────────────────────────────────────────
def _fetch_email_for_sinistre(driver, database: str, num_sinistre: str,
                              sinistre_key: str = "NUM_SINISTRE") -> Optional[str]:
    query = f"""
    MATCH (s:Sinistre {{{sinistre_key}: $num}})
    OPTIONAL MATCH (a:Tiers)-[:DECLARE]->(s)
    RETURN coalesce(a.email, s.email_assure, '') AS email
    """
    try:
        with driver.session(database=database) as session:
            rec = session.run(query, num=num_sinistre).single()
            return rec["email"] if rec and rec["email"] else None
    except Exception as e:
        print(f"⚠️ _fetch_email_for_sinistre error: {e}")
        return None


def _build_neo4j_notification(num_sinistre: str, score: float, statut: str,
                              indicateurs: list) -> Dict[str, Any]:
    TYPE_MAP = {
        "frauduleux": {
            "type": "sinistre_fraude",
            "title": f"🚨 Fraude détectée — Sinistre N°{num_sinistre}",
            "message": f"Sinistre N°{num_sinistre} signalé frauduleux. Score : {score:.0f}/100. Traitement suspendu.",
            "priority": "high",
        },
        "suspect": {
            "type": "sinistre_suspect",
            "title": f"⚠️ Sinistre suspect — N°{num_sinistre}",
            "message": f"Sinistre N°{num_sinistre} nécessite vérification. Score : {score:.0f}/100. Un expert vous contactera.",
            "priority": "medium",
        },
        "normal": {
            "type": "sinistre_normal",
            "title": f"✅ Sinistre N°{num_sinistre} — En cours de traitement",
            "message": f"Sinistre N°{num_sinistre} enregistré. Score : {score:.0f}/100. Aucune anomalie.",
            "priority": "low",
        },
    }
    tmpl = TYPE_MAP.get(statut, TYPE_MAP["normal"])
    return {
        "id": f"neo4j_{num_sinistre}_{int(datetime.now().timestamp())}",
        "type": tmpl["type"],
        "title": tmpl["title"],
        "message": tmpl["message"],
        "priority": tmpl["priority"],
        "num_sinistre": num_sinistre,
        "score_suspicion": round(score, 1),
        "statut_sinistre": statut,
        "indicateurs": [
            {"code": i["code"], "label": i["label"], "points": i["pts"], "niveau": i.get("niveau", "élevé")}
            for i in indicateurs[:10]
        ],
        "nb_indicateurs": len(indicateurs),
        "date": datetime.now().isoformat(),
        "lu": False,
        "archived": False,
        "source": "neo4j_pipeline",
    }