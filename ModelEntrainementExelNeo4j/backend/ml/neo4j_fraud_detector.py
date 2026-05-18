# ml/neo4j_fraud_detector.py
"""
Neo4jFraudDetector — Détecteur de fraude hybride pour les indicateurs Neo4j
============================================================================
- Règles heuristiques : 12 indicateurs répartis en 4 groupes (Temporel, Comportement, Réseau, Financier)
- Modèles non‑supervisés : Isolation Forest, LOF, Elliptic Envelope entraînés sur les 12 features
- Score final = heuristique * 0.7 + ml_normalisé * 0.3  (poids réglables)
- Bonus de cumul plafonné et seuil plancher (identique Excel v3.12)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.covariance import EllipticEnvelope
import warnings
warnings.filterwarnings('ignore')

# ─── Groupes et poids (repris de Neo4jFraudIndicators) ─────────────────────
GROUPS_NEO4J = {
    'temporal': {'max': 30, 'indicators': ['DECL_TARDIVE', 'DECL_AVANT_SIN', 'FENETRE_EXPIRATION',
                                           'VEHICULE_TRES_NEUF', 'DIST_SIN_RES']},
    'behaviour': {'max': 20, 'indicators': ['USAGE_RISQUE', 'INCOHER_PROF_MARQUE', 'KM_ANORMAL']},
    'network': {'max': 25, 'indicators': ['ASS_RECURRENT', 'VEH_RECURRENT', 'TIERS_RECURRENT',
                                          'COMMUNAUTE_SUSPECTE']},
    'financial': {'max': 15, 'indicators': []},  # pour le moment vide, mais extensible
}

# Points individuels (identiques à ceux de Neo4jFraudIndicators)
POIDS_NEO4J = {
    "DIST_SIN_RES": {"pts_normal": 12, "pts_critique": 20},
    "USAGE_RISQUE": {"pts": 10},
    "INCOHER_PROF_MARQUE": {"pts": 12},
    "DECL_TARDIVE": {"pts_normal": 10, "pts_critique": 18},
    "DECL_AVANT_SIN": {"pts": 25},
    "SIN_AVANT_SOUSCRIPTION": {"pts": 15},
    "FENETRE_EXPIRATION": {"pts": 10},
    "VEHICULE_TRES_NEUF": {"pts": 8},
    "KM_ANORMAL": {"pts_normal": 8, "pts_critique": 15},
    "ASS_RECURRENT": {"pts": 5},
    "VEH_RECURRENT": {"pts": 5},
    "TIERS_RECURRENT": {"pts": 5},
    "COMMUNAUTE_SUSPECTE": {"pts": 8},
}

# Paramètres du bonus de cumul
BONUS_PAR_GROUPE_NEO4J = 0.15
BONUS_MAX_NEO4J = 1.30
SEUIL_BONUS_PLANCHER_NEO4J = 25.0

# Poids du ML dans le score final
ML_WEIGHT_NEO4J = 0.3
HEURISTIC_WEIGHT_NEO4J = 1.0 - ML_WEIGHT_NEO4J


class Neo4jFraudDetector:
    def __init__(self):
        self.models = {}
        self.is_fitted = False
        self._feature_names = []
        self._cached_scores = None
        self._cached_compact = None
        self._data_cache = {}       # X, scores normalisés
        self._raw_results = None    # Dict[str, Neo4jFraudResult]

    def _build_feature_matrix(self, results_map: Dict[str, Any]) -> pd.DataFrame:
        """Convertit un mapping {num_sinistre: Neo4jFraudResult} en DataFrame de features numériques."""
        records = []
        for num, res in results_map.items():
            feats = {}
            # Distance
            dist = res.details.get('distance_km', 0.0) or 0.0
            feats['DIST_SIN_RES'] = dist
            # Usage risque (1 si activé)
            feats['USAGE_RISQUE'] = 1.0 if any(i.code == 'USAGE_RISQUE' for i in res.indicateurs) else 0.0
            # Incohérence prof/marque (1 si activé)
            feats['INCOHER_PROF_MARQUE'] = 1.0 if any(i.code == 'INCOHER_PROF_MARQUE' for i in res.indicateurs) else 0.0
            # Déclaration tardive : nombre de jours (si disponible) sinon 0
            decalage = res.details.get('decalage_declaration_jours', 0) or 0
            feats['DECL_TARDIVE'] = max(0, decalage - 30)  # excédent par rapport au seuil
            feats['DECL_AVANT_SIN'] = 1.0 if any(i.code == 'DECL_AVANT_SIN' for i in res.indicateurs) else 0.0
            # Fenêtre expiration
            delta_exp = res.details.get('delta_expiration_jours', 0) or 0
            feats['FENETRE_EXPIRATION'] = abs(delta_exp)
            # Véhicule neuf
            age_mois = res.details.get('age_vehicule_mois', 12) or 12
            feats['VEHICULE_TRES_NEUF'] = max(0, 6 - age_mois)  # 0 si >=6 mois
            # Kilométrage annuel
            km_an = res.details.get('kilometrage_annuel', 0) or 0
            feats['KM_ANORMAL'] = max(0, km_an - 40000)
            # Réseau
            feats['ASS_RECURRENT'] = float(any(i.code == 'ASS_RECURRENT' for i in res.indicateurs))
            feats['VEH_RECURRENT'] = float(any(i.code == 'VEH_RECURRENT' for i in res.indicateurs))
            feats['TIERS_RECURRENT'] = float(any(i.code == 'TIERS_RECURRENT' for i in res.indicateurs))
            feats['COMMUNAUTE_SUSPECTE'] = float(any(i.code == 'COMMUNAUTE_SUSPECTE' for i in res.indicateurs))
            feats['num_sinistre'] = num
            records.append(feats)

        df = pd.DataFrame(records).set_index('num_sinistre')
        self._feature_names = list(df.columns)
        return df

    def _robust_norm(self, arr, invert=False):
        arr = np.asarray(arr, dtype=float)
        if arr.size == 0:
            return np.array([])
        q_low, q_high = np.percentile(arr, [1, 99])
        if q_high - q_low < 1e-10:
            return np.full(arr.shape, 50.0)
        clipped = np.clip(arr, q_low, q_high)
        out = (clipped - q_low) / (q_high - q_low) * 100.0
        if invert:
            out = 100.0 - out
        return out

    def fit(self, results_map: Dict[str, Any]):
        """
        Entraîne les modèles ML sur les features extraites des résultats Neo4j.
        results_map : {num_sinistre: Neo4jFraudResult}
        """
        print(f"🚀 Neo4jFraudDetector: Entraînement sur {len(results_map)} sinistres...")
        self._raw_results = results_map
        df = self._build_feature_matrix(results_map)
        X = df.values
        n_samples = X.shape[0]

        # Isolation Forest
        self.models['if'] = IsolationForest(n_estimators=200, contamination=0.1,
                                            max_samples=min(2000, n_samples),
                                            random_state=42, n_jobs=-1)
        self.models['if'].fit(X)
        if_scores = self.models['if'].score_samples(X)

        # LOF (avec novelty=True pour pouvoir scorer de nouveaux échantillons)
        try:
            self.models['lof'] = LocalOutlierFactor(n_neighbors=min(20, n_samples-1),
                                                    contamination=0.1, novelty=True, n_jobs=-1)
            self.models['lof'].fit(X)
            lof_scores = -self.models['lof'].negative_outlier_factor_
        except Exception as e:
            print(f"   ⚠️ LOF échoué: {e}, ignoré")
            lof_scores = np.zeros(n_samples)

        # Elliptic Envelope
        try:
            self.models['ee'] = EllipticEnvelope(contamination=0.1, random_state=42)
            self.models['ee'].fit(X)
            ee_scores = self.models['ee'].score_samples(X)
        except Exception as e:
            print(f"   ⚠️ EllipticEnvelope échoué: {e}, ignoré")
            ee_scores = np.zeros(n_samples)

        # Normalisation des scores ML
        if_norm = self._robust_norm(if_scores, invert=True)
        lof_norm = self._robust_norm(lof_scores, invert=False)
        ee_norm = self._robust_norm(ee_scores, invert=True)

        self._data_cache = {
            'X': X,
            'if': if_norm,
            'lof': lof_norm,
            'ee': ee_norm,
            'feature_names': self._feature_names,
            'num_sinistres': list(df.index),
        }

        # Pré‑calcul du score final pour chaque sinistre
        self._precompute_all_scores()
        self.is_fitted = True
        print(f"✅ Neo4jFraudDetector entraîné — {len(self._cached_scores)} scores prêts")

    def _precompute_all_scores(self):
        n = len(self._data_cache['num_sinistres'])
        scores = np.zeros(n)
        compacts = []
        for i in range(n):
            gs = self._calculate_heuristic(i)
            ml_score = np.mean([self._data_cache['if'][i],
                                self._data_cache['lof'][i],
                                self._data_cache['ee'][i]])
            final = round(HEURISTIC_WEIGHT_NEO4J * gs['heuristic_total'] +
                          ML_WEIGHT_NEO4J * ml_score, 1)
            final = min(final, 100.0)
            statut = 'frauduleux' if final >= 70 else ('suspect' if final >= 50 else 'normal')
            niveau = 'critique' if final >= 85 else ('élevé' if final >= 70 else 'modéré')
            scores[i] = final
            compacts.append({
                'total': final,
                'heuristic_total': gs['heuristic_total'],
                'ml_score': round(ml_score, 1),
                'score_brut': gs['score_brut'],
                'statut': statut,
                'niveau': niveau,
                'triggers': gs['all_triggers'],
                'scores_groupes': gs['groups'],
                'groupes_actifs': gs['groupes_actifs'],
                'bonus_cumul': gs['bonus_cumul'],
            })
        self._cached_scores = scores
        self._cached_compact = compacts

    def _calculate_heuristic(self, idx: int) -> Dict:
        """Calcule le score heuristique à partir des valeurs des indicateurs détectés."""
        # Récupération des détails pour le sinistre idx
        num = self._data_cache['num_sinistres'][idx]
        res = self._raw_results[num]
        # Initialiser les compteurs de groupe
        group_points = {'temporal': 0, 'behaviour': 0, 'network': 0, 'financial': 0}
        all_triggers = []
        for ind in res.indicateurs:
            code = ind.code
            pts = ind.points
            # Mapper le code à un groupe
            group = None
            for g, info in GROUPS_NEO4J.items():
                if code in info['indicators']:
                    group = g
                    break
            if group is None:
                continue  # indicateur non catégorisé (ex: SIN_AVANT_SOUSCRIPTION non encore mappé)
            group_points[group] += pts
            all_triggers.append({
                'group': group,
                'code': code,
                'label': ind.label,
                'pts': pts,
            })
        # Plafonner par groupe
        for g, info in GROUPS_NEO4J.items():
            group_points[g] = min(group_points[g], info['max'])
        score_brut = sum(group_points.values())
        groupes_actifs = sum(1 for v in group_points.values() if v > 0)
        bonus = 1.0 + max(0, groupes_actifs - 1) * BONUS_PAR_GROUPE_NEO4J
        bonus = min(bonus, BONUS_MAX_NEO4J)
        if score_brut >= SEUIL_BONUS_PLANCHER_NEO4J:
            heuristic_total = min(round(score_brut * bonus, 1), 100.0)
        else:
            heuristic_total = round(score_brut, 1)
        return {
            'heuristic_total': heuristic_total,
            'score_brut': score_brut,
            'groups': group_points,
            'all_triggers': all_triggers,
            'groupes_actifs': groupes_actifs,
            'bonus_cumul': round(bonus, 2),
        }

    def predict(self, num_sinistre: str) -> Dict:
        """Retourne le score complet pour un sinistre donné (utilisé après fit)."""
        if not self.is_fitted:
            raise RuntimeError("Modèle non entraîné")
        try:
            idx = self._data_cache['num_sinistres'].index(num_sinistre)
        except ValueError:
            # Fallback: calcul heuristique seul
            res = self._raw_results.get(num_sinistre)
            if res is None:
                return {'score': 0, 'statut': 'normal', 'indicateurs': []}
            # simple somme pondérée
            gs = self._calculate_heuristic_direct(res)
            return {
                'score': gs['heuristic_total'],
                'statut': 'frauduleux' if gs['heuristic_total'] >= 70 else 'suspect' if gs['heuristic_total'] >= 50 else 'normal',
                'indicateurs': gs['all_triggers'],
            }
        compact = self._cached_compact[idx]
        return {
            'score': compact['total'],
            'statut': compact['statut'],
            'niveau': compact['niveau'],
            'score_brut': compact['score_brut'],
            'ml_score': compact['ml_score'],
            'indicateurs': compact['triggers'],
            'groupes_actifs': compact['groupes_actifs'],
            'bonus_cumul': compact['bonus_cumul'],
        }

    def _calculate_heuristic_direct(self, res) -> Dict:
        # Juste pour usage sans entraînement
        # On duplique la logique simplifiée
        group_points = {'temporal': 0, 'behaviour': 0, 'network': 0, 'financial': 0}
        all_triggers = []
        for ind in res.indicateurs:
            pts = ind.points
            group = None
            for g, info in GROUPS_NEO4J.items():
                if ind.code in info['indicators']:
                    group = g
                    break
            if group is None:
                continue
            group_points[group] += pts
            all_triggers.append({'group': group, 'code': ind.code, 'label': ind.label, 'pts': pts})
        for g, info in GROUPS_NEO4J.items():
            group_points[g] = min(group_points[g], info['max'])
        score_brut = sum(group_points.values())
        groupes_actifs = sum(1 for v in group_points.values() if v > 0)
        bonus = min(1.0 + max(0, groupes_actifs - 1) * BONUS_PAR_GROUPE_NEO4J, BONUS_MAX_NEO4J)
        if score_brut >= SEUIL_BONUS_PLANCHER_NEO4J:
            total = min(round(score_brut * bonus, 1), 100.0)
        else:
            total = round(score_brut, 1)
        return {'heuristic_total': total, 'all_triggers': all_triggers}