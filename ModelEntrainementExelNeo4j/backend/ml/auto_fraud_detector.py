"""
Minimal AutoFraudDetector fallback implementation.

This stub provides a lightweight, deterministic scoring mechanism so the API
can run even if the full implementation is not present. It is intentionally
simple: scores are generated deterministically from the row index using MD5
so behaviour is reproducible across runs.

The real project should replace this file with the full `AutoFraudDetector`.
"""
import os
import pickle
from hashlib import md5
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


class SimpleVersionManager:
    def __init__(self, models_dir: str = None):
        self.models_dir = models_dir or os.path.join(os.path.dirname(__file__), '..', 'models', 'versions')
        self.active = None

    def get_active_version(self):
        return self.active

    def get_next_version_number(self) -> int:
        try:
            files = os.listdir(self.models_dir)
        except Exception:
            return 1
        nums = []
        for f in files:
            if f.startswith('v') and f.endswith('_model.pkl'):
                try:
                    n = int(f[1:].split('_')[0])
                    nums.append(n)
                except Exception:
                    continue
        return max(nums) + 1 if nums else 1

    def save_version(self, *args, **kwargs):
        return True

    def set_active_version(self, v: int):
        self.active = v
        return True

    def list_all_versions(self):
        return []

    def get_version_info(self, version_num: int):
        return {}

    def delete_version(self, version_num: int):
        return False


class AutoFraudDetector:
    def __init__(self):
        self.is_fitted = False
        self._cached_scores: Optional[np.ndarray] = None
        self._cached_compact: Optional[List[Dict[str, Any]]] = None
        self._data_cache: Dict[str, Any] = {}
        self.version_manager = SimpleVersionManager()
        # simple default config
        self.config = type('C', (), {})()
        self.config.thresholds = {"normal_max": 49.99, "suspect_min": 50.0, "frauduleux": 70.0}
        self.config.group_weights = {"financial": 35, "temporal": 35, "frequency": 30, "network": 22}

    def _make_scores_from_index(self, df: pd.DataFrame) -> np.ndarray:
        # deterministic pseudo-random score per row using md5 of the index/key
        scores = []
        for idx in df.index:
            s = str(idx).encode('utf-8')
            h = md5(s).hexdigest()[:8]
            val = int(h, 16) % 101
            scores.append(float(val))
        return np.array(scores, dtype=float)

    def fit(self, sinistres_df: pd.DataFrame, contrats_df=None, tiers_df=None, geocoder=None, label_column: Optional[str] = None, label_source: Optional[str] = None, sample_fraction: float = 1.0, progress_callback=None):
        # Generate deterministic scores and compact structures
        if sinistres_df is None:
            raise ValueError('sinistres_df is required')
        df = sinistres_df.copy()
        n = len(df)
        self._cached_scores = self._make_scores_from_index(df)
        self._cached_compact = []
        for sc in self._cached_scores:
            statut = 'frauduleux' if sc >= 70 else ('suspect' if sc >= 50 else 'normal')
            niveau = 'critique' if sc >= 85 else ('élevé' if sc >= 70 else 'modéré')
            self._cached_compact.append({'total': float(sc), 'statut': statut, 'niveau': niveau})
        self._data_cache = {'scores': list(self._cached_scores)}
        self.is_fitted = True

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump({'_cached_scores': self._cached_scores, '_cached_compact': self._cached_compact}, f)

    def load(self, path: str) -> bool:
        try:
            with open(path, 'rb') as f:
                obj = pickle.load(f)
            self._cached_scores = obj.get('_cached_scores')
            self._cached_compact = obj.get('_cached_compact')
            self.is_fitted = self._cached_scores is not None
            return True
        except Exception:
            return False

    def get_current_version_metrics(self) -> Dict[str, Any]:
        return {"score_mean": float(np.mean(self._cached_scores)) if self._cached_scores is not None else None}

    def get_current_config(self) -> Dict[str, Any]:
        return {"thresholds": self.config.thresholds, "group_weights": self.config.group_weights}

    def update_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # naive update
        if 'thresholds' in payload:
            self.config.thresholds.update(payload['thresholds'])
        if 'group_weights' in payload:
            self.config.group_weights.update(payload['group_weights'])
        return {"success": True, "config_snapshot": self.get_current_config()}

    def get_cached_compact(self, idx: int) -> Dict[str, Any]:
        if self._cached_compact is None:
            return {}
        if idx < 0 or idx >= len(self._cached_compact):
            return {}
        return self._cached_compact[idx]

    def _status_from_score(self, score: float):
        if score >= 70:
            return 'frauduleux', 'élevé'
        if score >= 50:
            return 'suspect', 'modéré'
        return 'normal', 'faible'

    def predict(self, sinistre_id: Any, sinistres_df: pd.DataFrame, contrats_df=None, tiers_df=None):
        # Return a minimal prediction dict
        if self._cached_scores is None:
            raise RuntimeError('Detector not fitted')
        try:
            idx = list(sinistres_df.index).index(sinistre_id)
        except Exception:
            idx = 0
        score = float(self._cached_scores[idx])
        statut, niveau = self._status_from_score(score)
        return {"score": score, "statut": statut, "niveau": niveau}

    def get_global_statistics(self):
        if self._cached_scores is None:
            return {"count": 0}
        arr = np.array(self._cached_scores)
        return {
            "count": int(arr.size),
            "score_mean": float(arr.mean()),
            "distribution": {
                "frauduleux": int((arr >= 70).sum()),
                "suspect": int(((arr >= 50) & (arr < 70)).sum()),
                "normal": int((arr < 50).sum()),
            }
        }

    # Placeholder implementations for methods expected elsewhere
    def list_all_versions(self):
        return []

    def set_active_version(self, v: int):
        self.version_manager.set_active_version(v)
        return True

    def validate_scoring(self):
        return {"success": True}

    def calculate_grouped_score(self, i: int):
        return {}
"""
auto_fraud_detector.py --- VERSION 3.14.1
=======================================
Corrections v3.14.1 :
  1. is_fitted = True ajoute dans fit() (cause du score 0.0 en post-fit)
  2. Calcul de feature_importance restaure
  3. validate_scoring() protegee contre cache absent
Version precedente : 3.14
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Callable
from datetime import datetime
from dataclasses import asdict
import pickle
import os
import json
import warnings

from sklearn.ensemble import IsolationForest
from sklearn.covariance import EllipticEnvelope
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    f1_score, precision_score, recall_score, accuracy_score,
    roc_auc_score, confusion_matrix, roc_curve, auc
)

# Import du gestionnaire de configuration dynamique
from .scoring_config import ScoringConfigManager, ScoringConfig
from .versioning import ModelVersionManager

FEATURE_NAME_MAPPING = {
    "num_TOTALREGLEMENT":                  "💰 Montant du sinistre",
    "std_TOTALREGLEMENT":                  "📊 Écart-type du montant",
    "ratio_montant_moyen":                 "📈 Ratio montant / moyenne",
    "ratio_montant_median":                "📈 Ratio montant / mediane",
    "ratio_montant_prime":                 "💰 Ratio montant / prime contrat",
    "montant_10x_prime":                   "🚨 Montant > 10x la prime",
    "zscore_montant":                      "📊 Écart normalise du montant",
    "montant_3std_suspect":                "⚠️ Montant anormal (>3σ)",
    "ratio_montant_vs_garage":             "🔧 Montant vs garage",
    "ratio_montant_vs_expert":             "🔍 Montant vs expert",
    "ratio_montant_vs_client":             "👤 Montant vs client moyen",
    "expert_cout_anormal":                 "💰 Cout expert anormal",
    "incoherence_age_montant":             "🚗 Vehicule age + montant eleve",
    "ratio_montant_pv_global":             "🏪 Montant vs point de vente",
    "ratio_montant_vs_combo_job_marque":   "🔄 Montant anormal combo job/marque",
    "decalage_survenance_declaration_jours": "⏰ Delai de declaration",
    "sinistre_moins_7j_apres_effet":       "⚠️ Sinistre <7j apres effet",
    "declaration_tardive_15j":             "⏰ Declaration >15 jours",
    "sinistre_moins_7j_expiration":        "⚠️ Sinistre <7j avant expiration",
    "declaration_apres_weekend":           "📅 Declaration post-weekend",
    "sinistre_heure_nuit":                 "🌙 Sinistre entre 0h et 5h",
    "sinistre_weekend":                    "📅 Sinistre samedi/dimanche",
    "survenance_mois":                     "📅 Mois de survenance",
    "is_weekend_DATE_SURVENANCE":          "📅 Sinistre weekend",
    "nbr_sinistres_vehicule":              "🚗 Sinistres par vehicule",
    "nbr_sinistres_contrat":               "📄 Sinistres par contrat",
    "nbr_sinistres_client":                "👤 Sinistres par assure",
    "nbr_sinistres_expert":                "🔍 Sinistres par expert",
    "nbr_sinistres_garage":                "🔧 Sinistres par garage",
    "nbr_sinistres_adverse":               "🚗 Sinistres par tiers adverse",
    "sinistres_client_12mois":             "📊 Sinistres/12 mois",
    "client_plus3_sinistres_12m":          "⚠️ >3 sinistres/an",
    "client_plus7_sinistres_12m":          "🚨 +7 sinistres/an",
    "delai_moyen_sinistres":               "⏱️ Delai moyen sinistres",
    "cluster_temporel_vehicule":           "🕐 Sinistres rapproches vehicule",
    "cluster_temporel_client":             "🕐 Sinistres rapproches client",
    "velocite_recente_vehicule":           "⚡ Acceleration sinistres vehicule",
    "velocite_recente_client":             "⚡ Acceleration sinistres client",
    "nb_avenants_contrat":                 "📄 Nombre d'avenants",
    "contrat_avenants_frequents":          "📄 Avenants frequents (>2)",
    "avenant_proche_sinistre_30j":         "⚠️ Avenant <30j avant sinistre",
    "freq_IMMATRICULATION":                "🚗 Frequence par immatriculation",
    "freq_EXPERT_STAREX":                  "🔍 Frequence par expert",
    "freq_GARAGES":                        "🔧 Frequence par garage",
    "freq_expert_meme_vehicule":           "🔄 Expert-vehicule recurrent",
    "expert_vehicule_repete":              "🔄 Expert + vehicule repetes",
    "adverse_repete":                      "🚗 Tiers adverse recurrent",
    "freq_temoin":                         "👥 Frequence temoin",
    "temoin_frequent":                     "👥 Temoin frequent (>3x)",
    "lieu_sinistre_frequent":              "📍 Lieu sinistre recurrent",
    "garage_taux_remplacement_eleve":      "🔧 Taux remplacement >80%",
    "freq_combo_job_marque":               "🔄 Combo job-marque suspect",
    "note_conducteur_faible":              "👤 Note conducteur <5/10",
    "note_conducteur_tres_faible":         "🚨 Note conducteur <3/10",
    "kilometrage_annuel_eleve":            "📊 Kilometrage >30k/an",
    "distance_sinistre_residence_elevee":  "📍 Distance sinistre >30km",
    "distance_sinistre_residence_identical": "📍 Sinistre a domicile",
    "distance_travail_residence_elevee":   "🏢 Travail eloigne residence",
    "profession_risque":                   "⚠️ Profession a risque",
    "sinistre_frontiere":                  "🌍 Sinistre frontiere tunisienne",
    "montant_cumule_vehicule":             "💰 Montant cumule vehicule",
}


class AutoFraudDetector:
    """
    Detecteur de fraude --- VERSION 3.14.1
    Seuils : normal<50, suspect 50-70, frauduleux>70
    Poids recalibres pour donnees tunisiennes (score moyen cible 35-45).
    """

    def __init__(self):
        self.feature_engineer = None
        self.models: Dict[str, Any] = {}
        self.is_fitted = False
        self.feature_importance: Dict[str, float] = {}

        # ── CONFIGURATION DYNAMIQUE ─────────────────────────────────────────────
        from .scoring_config import ScoringConfigManager, ScoringConfig
        self.config_manager = ScoringConfigManager()
        self.config = self.config_manager.current  # ScoringConfig

        # Poids par defaut pour chaque indicateur (modifiables via config)
        self._indicator_defaults: Dict[str, float] = {
            # Financial
            "FIN_3STD": 25, "FIN_3STD_PLUS": 3, "FIN_RATIO_5X": 14,
            "FIN_RATIO_3X": 10, "FIN_RATIO_2X": 7, "FIN_RATIO_15X": 4,
            "FIN_10X_PRIME": 20, "FIN_5X_PRIME": 10, "FIN_3X_PRIME": 6,
            "FIN_EXPERT_COUT": 8, "FIN_AGE_MONTANT": 6, "FIN_PV_RATIO": 5,
            # Temporal
            "TMP_15J": 18, "TMP_7J_EFFET": 28, "TMP_7J_EXP": 18,
            "TMP_NUIT": 8, "TMP_WEEKEND": 5, "TMP_CLUSTER_VEH": 7, "TMP_CLUSTER_CLI": 7,
            # Frequency
            "FRQ_7": 25, "FRQ_3": 16, "FRQ_VEH5": 12, "FRQ_VEH3": 8,
            "FRQ_VEH2": 5, "FRQ_AVENANTS": 7, "FRQ_AVENANT_RECENT": 12,
            # Network
            "NET_FRONTIERE": 10, "NET_ADVERSE": 10, "NET_TEMOIN": 7,
            "NET_EXPERT_VEH": 4, "NET_GARAGE": 5, "NET_LIEU": 4, "NET_COMBO_JOB": 3,
            # Driver
            "DRV_NOTE_TF": 4, "DRV_NOTE_F": 2, "DRV_KM": 2,
            "DRV_DIST_SIN": 2, "DRV_DIST_TRV": 1,
            # Profile
            "PRF_JOB": 2,
        }

        # Retrocompatibilite: expose les seuils comme attributs
        self.seuil_normal_max   = self.config.thresholds["normal_max"]
        self.seuil_suspect_min  = self.config.thresholds["suspect_min"]
        self.seuil_frauduleux   = self.config.thresholds["frauduleux"]

        self.heuristic_weight = 1.0
        self.ml_weight        = 0.0

        self._cached_scores:  Optional[np.ndarray] = None
        self._cached_compact: Optional[List[Dict]] = None

        self._data_cache: Dict = {}
        self.selected_feature_indices: List[int] = []
        self._raw_sinistres:      Optional[pd.DataFrame] = None
        self._true_sinistres_count: int = 0
        self._raw_feature_matrix: Optional[pd.DataFrame] = None
        self._supervised_labels: Optional[np.ndarray] = None
        self._label_encoder: Optional[LabelEncoder] = None
        self._is_multiclass: bool = False

        self._active_models: List[str] = []
        self._ee_available: bool = True

        # ── VERSIONING ─────────────────────────────────────────────────────
        self.version_manager = ModelVersionManager()
        self.current_version_num = self.version_manager.get_next_version_number()
        self._training_metrics: Dict = {}

    # ── CONFIGURATION DYNAMIQUE ──────────────────────────────────────────────

    def _get_indicator_weight(self, code: str, default: float) -> float:
        """Retourne le poids d'un indicateur (configure ou par defaut)."""
        # 1. Check config utilisateur
        if self.config.indicator_weights and code in self.config.indicator_weights:
            return self.config.indicator_weights[code]
        # 2. Check defaut interne
        return self._indicator_defaults.get(code, default)

    def update_config(self, new_config: Dict) -> Dict[str, any]:
        """
        Met a jour la configuration de scoring.

        Args:
            new_config: Dict avec cles optionnelles:
                - group_weights: {"financial": 30, ...}
                - indicator_weights: {"montant_vs_prime": 5.0, ...}
                - thresholds: {"normal_max": 49.99, ...}

        Returns:
            dict: {success, errors, new_config_snapshot}
        """
        from .scoring_config import ScoringConfig

        # Charger la config actuelle depuis le manager
        self.config = self.config_manager.current

        # Construire la configuration fusionnée pour validation
        current_dict = asdict(self.config)
        merged_dict = current_dict.copy()
        for key, value in new_config.items():
            if key in ["group_weights", "indicator_weights", "thresholds"] and isinstance(value, dict):
                merged_dict[key].update(value)
            else:
                merged_dict[key] = value

        merged_config = ScoringConfig(**merged_dict)

        # Valider la configuration fusionnée
        validation = self.config_manager.validate(merged_config)
        if not validation["valid"]:
            return {
                "success": False,
                "errors": validation["errors"],
                "config_snapshot": self.config_manager.to_dict()
            }

        # Appliquer les modifications partielles
        success = self.config_manager.update(new_config, notes="Update from dashboard")
        if success:
            # Recharger la config
            self.config = self.config_manager.current

            # Mettre a jour les attributs retrocompatibles
            self.seuil_normal_max  = self.config.thresholds["normal_max"]
            self.seuil_suspect_min = self.config.thresholds["suspect_min"]
            self.seuil_frauduleux  = self.config.thresholds["frauduleux"]

            print(f"Configuration mise a jour: groupes={self.config.group_weights}, seuils={self.config.thresholds}")

        return {
            "success": success,
            "errors": validation["errors"] if not success else [],
            "config_snapshot": self.config_manager.to_dict()
        }

    def get_current_config(self) -> Dict:
        """Retourne la configuration actuelle."""
        self.config = self.config_manager.current
        self.seuil_normal_max  = self.config.thresholds["normal_max"]
        self.seuil_suspect_min = self.config.thresholds["suspect_min"]
        self.seuil_frauduleux  = self.config.thresholds["frauduleux"]
        return self.config_manager.to_dict()

    # ── Utilitaires ──────────────────────────────────────────────────────────

    def _get_group_cap(self, group: str) -> int:
        """Retourne le cap maximum pour un groupe selon la config actuelle."""
        return self.config.group_weights.get(group, 0)

    def _robust_norm(self, arr: np.ndarray, invert: bool = False) -> np.ndarray:
        arr = np.asarray(arr, dtype=float)
        if arr.size == 0:
            return np.array([])
        q_low, q_high = np.percentile(arr, [1, 99])
        if q_high - q_low < 1e-10:
            out = np.full(arr.shape, 50.0, dtype=float)
        else:
            clipped = np.clip(arr, q_low, q_high)
            out = (clipped - q_low) / (q_high - q_low) * 100.0
        return 100.0 - out if invert else out

    def _to_native(self, obj):
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return self._to_native(obj.tolist())
        if isinstance(obj, dict):
            return {k: self._to_native(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._to_native(i) for i in obj]
        return obj

    # ── fit ──────────────────────────────────────────────────────────────────

    def fit(self, sinistres_df, contrats_df=None, tiers_df=None,
            feature_engineer=None, geocoder=None, labels=None,
            label_column: str = None, label_source: str = None, sample_fraction: float = 1.0,
            progress_callback: Optional[Callable[[int, str], None]] = None,
            save_version: bool = True, **kwargs):
        from ml.auto_feature_engineering import AutoFeatureEngineer

        print("=" * 60)
        print("🚀 AUTO-FRAUD v3.14.1 : Debut de l'apprentissage")
        print(f"   Seuils --> Frauduleux > {self.seuil_frauduleux} "
              f"| Suspect [{self.seuil_suspect_min}-{self.seuil_frauduleux:.0f}] "
              f"| Normal < {self.seuil_suspect_min}")
        print("   Mode : poids recalibres v3.14.1 (cible score moyen 35-45)")
        print("=" * 60)

        self._raw_sinistres = sinistres_df.copy()
        self._true_sinistres_count = len(sinistres_df)

        if progress_callback is not None:
            progress_callback(5, "Preparation des donnees et extraction des features...")

        print("\n📊 Étape 1 : Extraction des features...")
        if feature_engineer is not None:
            self.feature_engineer = feature_engineer
        else:
            self.feature_engineer = AutoFeatureEngineer(geocoder=geocoder)

        X, raw_df = self.feature_engineer.fit_transform_with_raw(
            sinistres_df, contrats_df, tiers_df
        )

        if X.shape[0] != self._true_sinistres_count:
            X = X[:self._true_sinistres_count]
            raw_df = raw_df.iloc[:self._true_sinistres_count].reset_index(drop=True)

        self._raw_feature_matrix = raw_df
        if progress_callback is not None:
            progress_callback(20, "Features extraites, preparation du jeu d'entraînement...")

        self._supervised_labels = None
        self._label_source = label_source or "manual"
        if labels is not None:
            self._supervised_labels = np.asarray(labels)
        elif label_column:
            if label_column in sinistres_df.columns:
                self._supervised_labels = sinistres_df[label_column].values
                if label_source == 'auto':
                    print(f"   ✅ Labels supervises generes automatiquement dans la colonne '{label_column}'")
                else:
                    print(f"   ✅ Labels supervises extraits depuis la colonne manuelle '{label_column}'")
            else:
                print(f"   ⚠️ Colonne de labels explicite '{label_column}' non trouvee dans sinistres_df. Recherche automatique...")
        if self._supervised_labels is None:
            for col in [
                "fraud_label", "is_fraud", "target", "y", "label",
                "statut_fraude", "frauduleux", "suspect"
            ]:
                if col in sinistres_df.columns:
                    self._supervised_labels = sinistres_df[col].values
                    self._label_source = "auto"
                    print(f"   ℹ️ Labels supervises extraits depuis la colonne '{col}' (détection automatique)")
                    break

        if self._supervised_labels is not None:
            if len(self._supervised_labels) != self._true_sinistres_count:
                raise ValueError(
                    f"Labels supervises ({len(self._supervised_labels)}) different du nombre "
                    f"de sinistres ({self._true_sinistres_count})"
                )
            y = pd.Series(self._supervised_labels)
            if y.dtype == object or y.dtype.name == "category":
                y = y.astype(str).str.lower().map({
                    "normal": 0,
                    "non_frauduleux": 0,
                    "non frauduleux": 0,
                    "suspect": 1,
                    "frauduleux": 1,
                    "fraud": 1,
                    "fraudulent": 1,
                    "oui": 1,
                    "non": 0,
                }).fillna(y)
            y = pd.to_numeric(y, errors="coerce")
            if y.isna().any():
                raise ValueError("Labels supervises invalides apres conversion en numerique.")
            self._supervised_labels = y.astype(int).values

        self.selected_feature_indices = list(range(X.shape[1]))
        if X.shape[1] > 100:
            top_idx = np.argsort(np.var(X, axis=0))[-100:]
            X = X[:, top_idx]
            self.selected_feature_indices = top_idx.tolist()

        # Échantillonnage pour accelerer l'entraînement si demande
        if sample_fraction is None:
            sample_fraction = 1.0
        if sample_fraction < 1.0 and sample_fraction > 0.0:
            n_samples = X.shape[0]
            sample_count = max(10, int(n_samples * sample_fraction))
            rng = np.random.RandomState(42)
            sample_idx = rng.choice(n_samples, size=sample_count, replace=False)
            X_fit = X[sample_idx]
            if self._supervised_labels is not None:
                y_fit = self._supervised_labels[sample_idx]
            else:
                y_fit = None
            print(f"\n📊 Échantillonnage entraînement : {sample_count}/{n_samples} exemples")
        else:
            X_fit = X
            y_fit = self._supervised_labels

        if progress_callback is not None:
            progress_callback(25, "Debut de l'entraînement des modeles de detection...")

        print("\n📊 Étape 2 : Entraînement des modeles ML...")
        n_samples = X.shape[0]
        self._active_models = []

        self.models["isolation_forest"] = IsolationForest(
            n_estimators=200, contamination=0.10,
            max_samples=min(2000, n_samples), random_state=42, n_jobs=-1
        )
        self.models["isolation_forest"].fit(X_fit)
        scores_if_raw = self.models["isolation_forest"].score_samples(X)
        self._active_models.append("if")
        print("   ✓ Isolation Forest")
        if progress_callback is not None:
            progress_callback(40, "Isolation Forest entraîne")

        try:
            self.models["lof"] = LocalOutlierFactor(
                n_neighbors=min(20, n_samples - 1),
                contamination=0.10, novelty=True, n_jobs=-1
            )
            self.models["lof"].fit(X_fit)
            scores_lof_raw = -self.models["lof"].score_samples(X)
            self._active_models.append("lof")
            print("   ✓ LOF")
            if progress_callback is not None:
                progress_callback(50, "LOF entraîne")
        except Exception as e:
            print(f"   ⚠️ LOF echoue : {e}")
            scores_lof_raw = np.zeros(n_samples)

        try:
            self.models["elliptic_envelope"] = EllipticEnvelope(
                contamination=0.10, random_state=42
            )
            self.models["elliptic_envelope"].fit(X_fit)
            scores_ee_raw = self.models["elliptic_envelope"].score_samples(X)
            self._active_models.append("ee")
            print("   ✓ Elliptic Envelope")
            if progress_callback is not None:
                progress_callback(60, "Elliptic Envelope entraîne")
        except Exception as e:
            print(f"   ⚠️ EE echoue : {e}")
            scores_ee_raw = np.zeros(n_samples)
            self._ee_available = False

        self._data_cache = {
            "X": X,
            "scores_if":  self._robust_norm(scores_if_raw,  invert=True),
            "scores_lof": self._robust_norm(scores_lof_raw, invert=False),
            "scores_ee":  self._robust_norm(scores_ee_raw,  invert=True),
            "active_models": self._active_models.copy(),
        }

        if self._supervised_labels is not None:
            if progress_callback is not None:
                progress_callback(65, "Entraînement supervise XGBoost en cours...")
            try:
                from xgboost import XGBClassifier
            except ImportError as e:
                raise ImportError(
                    "XGBoost requis pour l'entraînement supervise. "
                    "Installez la bibliotheque xgboost."
                ) from e

            y_unique = np.unique(y_fit)
            self._is_multiclass = len(y_unique) > 2
            self._label_encoder = None
            if self._is_multiclass:
                self._label_encoder = LabelEncoder()
                y_fit = self._label_encoder.fit_transform(y_fit)
                objective = "multi:softprob"
                num_class = len(self._label_encoder.classes_)
            else:
                objective = "binary:logistic"
                num_class = None

            xgb_params = {
                "objective": objective,
                "n_estimators": 200,
                "max_depth": 6,
                "learning_rate": 0.1,
                "eval_metric": "auc",
                "n_jobs": -1,
                "verbosity": 0,
            }
            if num_class is not None:
                xgb_params["num_class"] = num_class

            self.models["xgb"] = XGBClassifier(**xgb_params)
            self.models["xgb"].fit(X_fit, y_fit)

            if self._is_multiclass:
                probs = self.models["xgb"].predict_proba(X)
                # Score = prob(fraud) *100 + prob(suspect)*50 ; assumes classes are ordered by severity
                if probs.shape[1] == 3:
                    self._data_cache["scores_xgb"] = np.clip(
                        probs[:, 2] * 100.0 + probs[:, 1] * 50.0,
                        0.0, 100.0,
                    )
                else:
                    weights = np.arange(probs.shape[1], 0, -1)
                    weights = weights / np.sum(weights)
                    self._data_cache["scores_xgb"] = np.clip(
                        (probs * weights).sum(axis=1) * 100.0,
                        0.0, 100.0,
                    )
                self._data_cache["scores_xgb_probs"] = probs
            else:
                self._data_cache["scores_xgb"] = self.models["xgb"].predict_proba(X)[:, 1] * 100.0
            self._active_models.append("xgb")
            print("   ✓ XGBoost supervise")
            if progress_callback is not None:
                progress_callback(75, "XGBoost supervise entraîne")

        print("\n📊 Étape 3 : Pre-calcul des scores (cache)...")
        if progress_callback is not None:
            progress_callback(80, "Pre-calcul des scores...")
        self._precompute_all_scores()

        # ── CORRECTIF v3.14.1 : is_fitted positionne ICI ─────────────────
        self.is_fitted = True

        # ── Importance des features (restauree) ──────────────────────────
        print("\n📊 Étape 4 : Importance des features...")
        if progress_callback is not None:
            progress_callback(90, "Calcul de l'importance des features...")
        active = self._data_cache.get("active_models", self._active_models)
        s_if  = self._data_cache["scores_if"]
        s_lof = self._data_cache["scores_lof"]
        s_ee  = self._data_cache["scores_ee"]
        if len(active) == 3:
            combined = (s_if + s_lof + s_ee) / 3
        elif len(active) == 2:
            if "if" in active and "lof" in active:
                combined = (s_if + s_lof) / 2
            else:
                combined = (s_if + s_ee) / 2
        else:
            combined = s_if
        self.feature_importance = self._calc_importance(
            self._data_cache["X"], combined
        )

        # ── Validation post-fit ───────────────────────────────────────────
        arr = self._cached_scores
        pct_fraud   = (arr > self.seuil_frauduleux).mean() * 100
        pct_suspect = ((arr >= self.seuil_suspect_min) & (arr <= self.seuil_frauduleux)).mean() * 100
        pct_normal  = (arr < self.seuil_normal_max).mean() * 100
        print(f"\n📊 VALIDATION SCORING v3.14.1 :")
        print(f"   Score moyen    : {arr.mean():.1f}/100  (cible : 35-45)")
        print(f"   Frauduleux >{self.seuil_frauduleux:.0f} : {pct_fraud:.1f}%  (cible : 5-15%)")
        print(f"   Suspects        : {pct_suspect:.1f}%  (cible : 15-25%)")
        print(f"   Normaux         : {pct_normal:.1f}%")

        if arr.mean() < 25:
            print("\n   ⚠️  Score moyen encore tres bas --> verifier que les colonnes")
            print("        DATE_EFFET_CONTRAT, contrat_PRIME, contrat_CODE_CLIENT")
            print("        sont bien presentes dans vos donnees apres merge.")

        if progress_callback is not None:
            progress_callback(95, "Calcul final et validation...")
        print("\n✅ AUTO-FRAUD v3.14.1 : Apprentissage termine !")
        print("=" * 60)
        
        # ── CALCUL DES KPIs ET SAUVEGARDE DE VERSION ───────────────────────
        if save_version:
            self._compute_and_save_version_metrics()
        else:
            self._training_metrics = {
                "is_supervised": False,
                "label_source": None,
                "score_moyen": round(float(self._cached_scores.mean()), 2) if self._cached_scores is not None else None,
                "score_median": round(float(np.median(self._cached_scores)), 2) if self._cached_scores is not None else None,
                "score_std": round(float(self._cached_scores.std()), 2) if self._cached_scores is not None else None,
            }
        if progress_callback is not None:
            progress_callback(100, "Entraînement termine")
        
        return self

    def _precompute_all_scores(self):
        n = self._true_sinistres_count
        scores  = np.zeros(n)
        compact = []

        for i in range(n):
            if i % 1000 == 0 and i > 0:
                print(f"      --> {i}/{n} ({i/n*100:.0f}%)")

            gs = self.calculate_grouped_score(i)

            if_score  = float(self._data_cache["scores_if"][i])
            lof_score = float(self._data_cache["scores_lof"][i])
            ee_score  = float(self._data_cache["scores_ee"][i])

            if "scores_xgb" in self._data_cache:
                ml_score = float(self._data_cache["scores_xgb"][i])
                final_score = round(min(100.0, gs["score_brut"] * 0.6 + ml_score * 0.4), 1)
            else:
                final_score = round(min(100.0, gs["score_brut"]), 1)
                if len(self._active_models) == 3:
                    ml_score = round((if_score + lof_score + ee_score) / 3.0, 1)
                elif len(self._active_models) == 2:
                    if "if" in self._active_models and "lof" in self._active_models:
                        ml_score = round((if_score + lof_score) / 2.0, 1)
                    else:
                        ml_score = round((if_score + ee_score) / 2.0, 1)
                else:
                    ml_score = round(if_score, 1)

            statut, niveau = self._status_from_score(final_score)
            scores[i] = final_score
            compact.append({
                "total":           final_score,
                "heuristic_total": round(min(100.0, gs["score_brut"]), 1),
                "score_brut":      gs["score_brut"],
                "ml_score":        ml_score,
                "statut":          statut,
                "niveau":          niveau,
                "triggers":        gs["all_triggers"],
                "scores_groupes":  {k: gs["groups"][k]["score"] for k in gs["groups"]},
                "groupes_actifs":  gs["groupes_actifs"],
                "bonus_cumul":     1.0,
                "bonus_applique":  False,
                "n_models_actifs": len(self._active_models),
            })
        self._cached_scores  = scores
        self._cached_compact = compact
        print(f"   ✅ Cache pret ({n} scores)")

    # ── Calcul des KPIs et versioning ────────────────────────────────────────

    def _compute_and_save_version_metrics(self):
        """Calcule les KPIs (F1, Precision, Recall, AUC) et sauvegarde la version."""
        print("\n📊 Calcul des KPIs de validation...")
        
        metrics = {}
        
        # Utiliser les labels supervises s'ils existent
        if self._supervised_labels is not None:
            y_true = self._supervised_labels
            if self._label_encoder is not None:
                y_true = self._label_encoder.transform(y_true)

            try:
                y_pred = None
                y_prob = None
                if "xgb" in self.models:
                    if self._is_multiclass and hasattr(self.models["xgb"], "classes_"):
                        y_pred = self.models["xgb"].predict(self._data_cache["X"])
                        if self._label_encoder is not None and hasattr(self._label_encoder, "inverse_transform"):
                            y_pred = self._label_encoder.transform(self._label_encoder.inverse_transform(y_pred))
                        if "scores_xgb_probs" in self._data_cache:
                            y_prob = self._data_cache["scores_xgb_probs"]
                    else:
                        y_pred = (self._cached_scores > self.seuil_frauduleux).astype(int)
                        y_prob = np.clip(self._cached_scores / 100.0, 0, 1)
                else:
                    y_pred = (self._cached_scores > self.seuil_frauduleux).astype(int)
                    y_prob = np.clip(self._cached_scores / 100.0, 0, 1)

                if self._is_multiclass:
                    metrics["f1_score"] = round(float(f1_score(y_true, y_pred, average="macro")), 4)
                    metrics["precision"] = round(float(precision_score(y_true, y_pred, average="macro", zero_division=0)), 4)
                    metrics["recall"] = round(float(recall_score(y_true, y_pred, average="macro", zero_division=0)), 4)
                    metrics["accuracy"] = round(float(accuracy_score(y_true, y_pred)), 4)
                    if y_prob is not None and y_prob.ndim == 2:
                        try:
                            metrics["auc_roc"] = round(float(roc_auc_score(y_true, y_prob, multi_class="ovo", average="macro")), 4)
                        except Exception:
                            metrics["auc_roc"] = None
                    cm = confusion_matrix(y_true, y_pred)
                    metrics["confusion_matrix"] = cm.tolist()
                else:
                    y_pred_binary = y_pred if y_pred is not None else (self._cached_scores > self.seuil_frauduleux).astype(int)
                    metrics["f1_score"] = round(float(f1_score(y_true, y_pred_binary)), 4)
                    metrics["precision"] = round(float(precision_score(y_true, y_pred_binary, zero_division=0)), 4)
                    metrics["recall"] = round(float(recall_score(y_true, y_pred_binary, zero_division=0)), 4)
                    metrics["accuracy"] = round(float(accuracy_score(y_true, y_pred_binary)), 4)
                    metrics["auc_roc"] = round(float(roc_auc_score(y_true, self._cached_scores)), 4)
                    tn, fp, fn, tp = confusion_matrix(y_true, y_pred_binary).ravel()
                    metrics["confusion_matrix"] = {
                        "true_negatives": int(tn),
                        "false_positives": int(fp),
                        "false_negatives": int(fn),
                        "true_positives": int(tp),
                    }
                metrics["is_supervised"] = True
            except Exception as e:
                print(f"   ⚠️ Erreur calcul metriques supervisees : {e}")
                metrics["is_supervised"] = False
        else:
            metrics["is_supervised"] = False

        if metrics["is_supervised"]:
            metrics["label_source"] = self._label_source or "manual"
        
        # Toujours calculer les stats de distribution
        metrics["score_moyen"] = round(float(self._cached_scores.mean()), 2)
        metrics["score_median"] = round(float(np.median(self._cached_scores)), 2)
        metrics["score_std"] = round(float(self._cached_scores.std()), 2)
        metrics["score_min"] = round(float(self._cached_scores.min()), 2)
        metrics["score_max"] = round(float(self._cached_scores.max()), 2)
        metrics["training_samples"] = self._true_sinistres_count
        metrics["models_active"] = self._active_models.copy()
        metrics["heuristic_weight"] = self.heuristic_weight
        metrics["ml_weight"] = self.ml_weight
        
        # Distribution
        fraude = int((self._cached_scores > self.seuil_frauduleux).sum())
        suspect = int(((self._cached_scores >= self.seuil_suspect_min) & 
                      (self._cached_scores <= self.seuil_frauduleux)).sum())
        normal = int((self._cached_scores < self.seuil_normal_max).sum())
        
        metrics["distribution"] = {
            "frauduleux": {"count": fraude, "pct": round(fraude / self._true_sinistres_count * 100, 2)},
            "suspect": {"count": suspect, "pct": round(suspect / self._true_sinistres_count * 100, 2)},
            "normal": {"count": normal, "pct": round(normal / self._true_sinistres_count * 100, 2)},
        }
        
        self._training_metrics = metrics
        
        # Sauvegarder la version
        version_path = f"models/versions/v{self.current_version_num}_model.pkl"
        self.save(version_path)
        
        # Enregistrer dans l'historique
        notes = f"Auto-entraînement supervise" if metrics["is_supervised"] else "Entraînement non supervise"
        self.version_manager.save_version(
            self.current_version_num, 
            version_path, 
            metrics,
            notes
        )
        self.version_manager.set_active_version(self.current_version_num)
        self.current_version_num = self.version_manager.get_next_version_number()
        
        print(f"\n✅ VERSION {self.current_version_num - 1} sauvegardee !")
        print(f"   📊 F1-Score      : {metrics.get('f1_score', 'N/A')}")
        print(f"   🎯 Precision     : {metrics.get('precision', 'N/A')}")
        print(f"   🔍 Recall        : {metrics.get('recall', 'N/A')}")
        print(f"   ✔️  Accuracy      : {metrics.get('accuracy', 'N/A')}")
        print(f"   📈 AUC-ROC       : {metrics.get('auc_roc', 'N/A')}")
        print(f"   Score moyen      : {metrics['score_moyen']}/100")

    # ── Accesseurs cache ──────────────────────────────────────────────────────

    def get_cached_score(self, idx: int) -> float:
        if self._cached_scores is None:
            raise RuntimeError("Cache non initialise.")
        return float(self._cached_scores[idx])

    def get_cached_compact(self, idx: int) -> Dict:
        if self._cached_compact is None:
            raise RuntimeError("Cache non initialise.")
        return self._cached_compact[idx]

    def _get_raw(self, idx: int, feature: str, default: float = 0.0) -> float:
        if (self._raw_feature_matrix is None
                or feature not in self._raw_feature_matrix.columns):
            return default
        try:
            val = self._raw_feature_matrix.iloc[idx][feature]
            if pd.isna(val) or np.isinf(val):
                return default
            return float(val)
        except Exception:
            return default

    # ════════════════════════════════════════════════════════════════════
    # CALCUL DU SCORE HEURISTIQUE --- v3.14 (inchange)
    # ════════════════════════════════════════════════════════════════════

    def calculate_grouped_score(self, sinistre_idx: int) -> Dict:
        g = self._get_raw

        # ── 1) FINANCIER (max 35 pts) ─────────────────────────────────────
        fin, fin_t = 0.0, []
        group = "financial"

        is_3std = g(sinistre_idx, "montant_3std_suspect") > 0.5
        rmm     = g(sinistre_idx, "ratio_montant_moyen", 1.0)

        if is_3std:
            fin += self._get_indicator_weight("FIN_3STD", 25)
            fin_t.append({"code": "FIN_3STD",
                           "label": "Montant > µ+3σ (anomalie statistique extreme)",
                           "pts": 25, "group": group})
            if rmm > 5.0:
                fin += self._get_indicator_weight("FIN_3STD_PLUS", 3)
                fin_t.append({"code": "FIN_3STD_PLUS",
                               "label": f"Et montant = {rmm:.1f}x la moyenne (aggravant)",
                               "pts": 3, "group": group})
        else:
            if rmm > 5.0:
                fin += self._get_indicator_weight("FIN_RATIO_5X", 14)
                fin_t.append({"code": "FIN_RATIO_5X",
                               "label": f"Montant = {rmm:.1f}x la moyenne",
                               "pts": 14, "group": group})
            elif rmm > 3.0:
                fin += self._get_indicator_weight("FIN_RATIO_3X", 10)
                fin_t.append({"code": "FIN_RATIO_3X",
                               "label": f"Montant = {rmm:.1f}x la moyenne",
                               "pts": 10, "group": group})
            elif rmm > 2.0:
                fin += self._get_indicator_weight("FIN_RATIO_2X", 7)
                fin_t.append({"code": "FIN_RATIO_2X",
                               "label": f"Montant = {rmm:.1f}x la moyenne",
                               "pts": 7, "group": group})
            elif rmm > 1.5:
                fin += self._get_indicator_weight("FIN_RATIO_15X", 4)
                fin_t.append({"code": "FIN_RATIO_15X",
                               "label": f"Montant = {rmm:.1f}x la moyenne",
                               "pts": 4, "group": group})

        # ── NOUVEAU : ratio montant / prime contrat ───────────────────────
        if g(sinistre_idx, "montant_10x_prime") > 0.5:
            fin += self._get_indicator_weight("FIN_10X_PRIME", 20)
            fin_t.append({"code": "FIN_10X_PRIME",
                           "label": "Montant > 10x la prime moyenne ",
                           "pts": 20, "group": group})
        else:
            rmp = g(sinistre_idx, "ratio_montant_prime", 1.0)
            if rmp > 5.0:
                fin += self._get_indicator_weight("FIN_5X_PRIME", 10)
                fin_t.append({"code": "FIN_5X_PRIME",
                               "label": f"Montant = {rmp:.1f}x la prime",
                               "pts": 10, "group": group})
            elif rmp > 3.0:
                fin += self._get_indicator_weight("FIN_3X_PRIME", 6)
                fin_t.append({"code": "FIN_3X_PRIME",
                               "label": f"Montant = {rmp:.1f}x la prime",
                               "pts": 6, "group": group})

        if g(sinistre_idx, "expert_cout_anormal") > 0.5:
            fin += self._get_indicator_weight("FIN_EXPERT_COUT", 8)
            fin_t.append({"code": "FIN_EXPERT_COUT",
                           "label": "Cout expert > 1.5x la moyenne",
                           "pts": 8, "group": group})

        if g(sinistre_idx, "incoherence_age_montant") > 0.5:
            fin += self._get_indicator_weight("FIN_AGE_MONTANT", 6)
            fin_t.append({"code": "FIN_AGE_MONTANT",
                           "label": "Vehicule >10 ans + montant eleve (P80)",
                           "pts": 6, "group": group})

        rpv = g(sinistre_idx, "ratio_montant_pv_global", 1.0)
        if rpv > 2.5:
            fin += self._get_indicator_weight("FIN_PV_RATIO", 5)
            fin_t.append({"code": "FIN_PV_RATIO",
                           "label": f"Montant = {rpv:.1f}x la moyenne du point de vente",
                           "pts": 5, "group": group})

        fin = min(fin, self._get_group_cap("financial"))

        # ── 2) TEMPOREL (max 35 pts) ──────────────────────────────────────
        temp, temp_t = 0.0, []
        group = "temporal"

        if g(sinistre_idx, "declaration_tardive_15j") > 0.5:
            temp += self._get_indicator_weight("TMP_15J", 18)
            temp_t.append({"code": "TMP_15J",
                    "label": "Declaration > 15 j apres survenance",
                    "pts": 18, "group": group})
            if g(sinistre_idx, "sinistre_moins_7j_apres_effet") > 0.5:
                temp += self._get_indicator_weight("TMP_7J_EFFET", 28)
            temp_t.append({"code": "TMP_7J_EFFET",
                            "label": "Sinistre < 7 j apres prise d'effet",
                            "pts": 28, "group": group})

        if g(sinistre_idx, "sinistre_moins_7j_expiration") > 0.5:
            temp += self._get_indicator_weight("TMP_7J_EXP", 18)
            temp_t.append({"code": "TMP_7J_EXP",
                            "label": "Sinistre < 7 j avant expiration",
                            "pts": 18, "group": group})

        # ── NOUVEAU : heure de nuit ───────────────────────────────────────
        if g(sinistre_idx, "sinistre_heure_nuit") > 0.5:
            temp += self._get_indicator_weight("TMP_NUIT", 8)
            temp_t.append({"code": "TMP_NUIT",
                            "label": "Sinistre declare entre 0h et 5h",
                            "pts": 8, "group": group})

        # ── NOUVEAU : weekend ─────────────────────────────────────────────
        if g(sinistre_idx, "sinistre_weekend") > 0.5:
            temp += self._get_indicator_weight("TMP_WEEKEND", 5)
            temp_t.append({"code": "TMP_WEEKEND",
                            "label": "Sinistre samedi ou dimanche",
                            "pts": 5, "group": group})

        if g(sinistre_idx, "cluster_temporel_vehicule") > 0.5:
            temp += self._get_indicator_weight("TMP_CLUSTER_VEH", 7)
            temp_t.append({"code": "TMP_CLUSTER_VEH",
                            "label": "Delai moyen ≤ 30 j entre sinistres vehicule",
                            "pts": 7, "group": group})

        if g(sinistre_idx, "cluster_temporel_client") > 0.5:
            temp += self._get_indicator_weight("TMP_CLUSTER_CLI", 7)
            temp_t.append({"code": "TMP_CLUSTER_CLI",
                            "label": "Delai moyen ≤ 30 j entre sinistres client",
                            "pts": 7, "group": group})

        temp = min(temp, self._get_group_cap("temporal"))

        # ── 3) FRÉQUENCE (max 30 pts) ─────────────────────────────────────
        freq, freq_t = 0.0, []
        group = "frequency"

        if g(sinistre_idx, "client_plus7_sinistres_12m") > 0.5:
            freq += self._get_indicator_weight("FRQ_7", 25)
            freq_t.append({"code": "FRQ_7",
                            "label": "≥ 7 sinistres/12 mois (meme client)",
                            "pts": 25, "group": group})
        elif g(sinistre_idx, "client_plus3_sinistres_12m") > 0.5:
            freq += self._get_indicator_weight("FRQ_3", 16)
            freq_t.append({"code": "FRQ_3",
                            "label": "> 3 sinistres/12 mois (meme client)",
                            "pts": 16, "group": group})

        nbv = g(sinistre_idx, "nbr_sinistres_vehicule", 1.0)
        if nbv >= 5:
            freq += self._get_indicator_weight("FRQ_VEH5", 12)
            freq_t.append({"code": "FRQ_VEH5",
                            "label": f"{int(nbv)} sinistres sur ce vehicule",
                            "pts": 12, "group": group})
        elif nbv >= 3:
            freq += self._get_indicator_weight("FRQ_VEH3", 8)
            freq_t.append({"code": "FRQ_VEH3",
                            "label": f"{int(nbv)} sinistres sur ce vehicule",
                            "pts": 8, "group": group})
        elif nbv >= 2:
            freq += self._get_indicator_weight("FRQ_VEH2", 5)
            freq_t.append({"code": "FRQ_VEH2",
                            "label": f"{int(nbv)} sinistres sur ce vehicule",
                            "pts": 5, "group": group})

        if g(sinistre_idx, "contrat_avenants_frequents") > 0.5:
            freq += self._get_indicator_weight("FRQ_AVENANTS", 7)
            freq_t.append({"code": "FRQ_AVENANTS",
                            "label": "> 2 avenants suspects sur le contrat",
                            "pts": 7, "group": group})

        # ── NOUVEAU : avenant proche du sinistre ──────────────────────────
        if g(sinistre_idx, "avenant_proche_sinistre_30j") > 0.5:
            freq += self._get_indicator_weight("FRQ_AVENANT_RECENT", 12)
            freq_t.append({"code": "FRQ_AVENANT_RECENT",
                            "label": "Avenant signe < 30j avant le sinistre",
                            "pts": 12, "group": group})

        vr = max(g(sinistre_idx, "velocite_recente_vehicule", 0.0),
                 g(sinistre_idx, "velocite_recente_client",   0.0))
        if vr > 0.5:
            pts = min(6, max(1, int(vr * 6)))
            freq += pts
            freq_t.append({"code": "FRQ_VELOCITE",
                            "label": f"Acceleration recente sinistres ({vr:.0%} en 30j)",
                            "pts": pts, "group": group})

        freq = min(freq, self._get_group_cap("frequency"))

        # ── 4) RÉSEAU / COLLUSION (max 22 pts) ────────────────────────────
        net, net_t = 0.0, []
        group = "network"

        if g(sinistre_idx, "sinistre_frontiere") > 0.5:
            net += self._get_indicator_weight("NET_FRONTIERE", 10)
            net_t.append({"code": "NET_FRONTIERE",
                           "label": "Sinistre a proximite de la frontiere tunisienne",
                           "pts": 10, "group": group})

        if g(sinistre_idx, "adverse_repete") > 0.5:
            net += self._get_indicator_weight("NET_ADVERSE", 10)
            net_t.append({"code": "NET_ADVERSE",
                           "label": "Tiers adverse recurrent (>2 sinistres)",
                           "pts": 10, "group": group})

        if g(sinistre_idx, "temoin_frequent") > 0.5:
            net += self._get_indicator_weight("NET_TEMOIN", 7)
            net_t.append({"code": "NET_TEMOIN",
                           "label": "Temoin present dans > 3 sinistres",
                           "pts": 7, "group": group})

        if g(sinistre_idx, "expert_vehicule_repete") > 0.5:
            net += self._get_indicator_weight("NET_EXPERT_VEH", 4)
            net_t.append({"code": "NET_EXPERT_VEH",
                           "label": "Expert + vehicule repetes ensemble",
                           "pts": 4, "group": group})

        if g(sinistre_idx, "garage_taux_remplacement_eleve") > 0.5:
            net += self._get_indicator_weight("NET_GARAGE", 5)
            net_t.append({"code": "NET_GARAGE",
                           "label": "Garage taux remplacement pieces > 80%",
                           "pts": 5, "group": group})

        if g(sinistre_idx, "lieu_sinistre_frequent") > 0.5:
            net += self._get_indicator_weight("NET_LIEU", 4)
            net_t.append({"code": "NET_LIEU",
                           "label": "Lieu de sinistre recurrent (> 3 fois)",
                           "pts": 4, "group": group})

        fjm = g(sinistre_idx, "freq_combo_job_marque", 0.0)
        if fjm > 5:
            net += self._get_indicator_weight("NET_COMBO_JOB", 3)
            net_t.append({"code": "NET_COMBO_JOB",
                           "label": f"Combo job-marque tres frequent ({int(fjm)} fois)",
                           "pts": 3, "group": group})

        net = min(net, self._get_group_cap("network"))

        # ── 5) CONDUCTEUR / MOBILITÉ (max 8 pts) ──────────────────────────
        drv, drv_t = 0.0, []
        group = "driver"

        if g(sinistre_idx, "note_conducteur_tres_faible") > 0.5:
            drv += self._get_indicator_weight("DRV_NOTE_TF", 4)
            drv_t.append({"code": "DRV_NOTE_TF",
                           "label": "Note conducteur < 3/10",
                           "pts": 4, "group": group})
        elif g(sinistre_idx, "note_conducteur_faible") > 0.5:
            drv += self._get_indicator_weight("DRV_NOTE_F", 2)
            drv_t.append({"code": "DRV_NOTE_F",
                           "label": "Note conducteur < 5/10",
                           "pts": 2, "group": group})

        if g(sinistre_idx, "kilometrage_annuel_eleve") > 0.5:
            drv += self._get_indicator_weight("DRV_KM", 2)
            drv_t.append({"code": "DRV_KM",
                           "label": "Kilometrage annuel > 30 000 km/an",
                           "pts": 2, "group": group})

        if g(sinistre_idx, "distance_sinistre_residence_elevee") > 0.5:
            drv += self._get_indicator_weight("DRV_DIST_SIN", 2)
            drv_t.append({"code": "DRV_DIST_SIN",
                           "label": "Sinistre au domicile ou distance > 30 km",
                           "pts": 2, "group": group})

        if g(sinistre_idx, "distance_travail_residence_elevee") > 0.5:
            drv += self._get_indicator_weight("DRV_DIST_TRV", 1)
            drv_t.append({"code": "DRV_DIST_TRV",
                           "label": "Travail tres eloigne de la residence",
                           "pts": 1, "group": group})

        drv = min(drv, self._get_group_cap("driver"))

        # ── 6) PROFIL ASSURÉ (max 4 pts) ──────────────────────────────────
        prof, prof_t = 0.0, []
        group = "profile"

        if g(sinistre_idx, "profession_risque") > 0.5:
            prof += self._get_indicator_weight("PRF_JOB", 2)
            prof_t.append({"code": "PRF_JOB",
                            "label": "Profession a risque (taxi, transport…)",
                            "pts": 2, "group": group})


        prof = min(prof, self._get_group_cap("profile"))

        # ── TOTAL ─────────────────────────────────────────────────────────
        groupes_actifs = sum(1 for s in [fin, temp, freq, net, drv, prof] if s > 0)
        score_brut     = fin + temp + freq + net + drv + prof
        total          = round(min(score_brut, 100.0), 1)

        statut, niveau = self._status_from_score(total)
        all_triggers   = fin_t + temp_t + freq_t + net_t + drv_t + prof_t

        return {
            "total":           total,
            "heuristic_total": total,
            "score_brut":      score_brut,
            "statut":          statut,
            "niveau":          niveau,
            "groups": {
                "financial": {"score": round(fin, 1),  "max": self._get_group_cap("financial"),
                              "label": "Financier",          "triggers": fin_t},
                "temporal":  {"score": round(temp, 1), "max": self._get_group_cap("temporal"),
                              "label": "Temporel",           "triggers": temp_t},
                "frequency": {"score": round(freq, 1), "max": self._get_group_cap("frequency"),
                              "label": "Frequence",          "triggers": freq_t},
                "network":   {"score": round(net, 1),  "max": self._get_group_cap("network"),
                              "label": "Reseau / Collusion", "triggers": net_t},
                "driver":    {"score": round(drv, 1),  "max": self._get_group_cap("driver"),
                              "label": "Conducteur / Mobilite", "triggers": drv_t},
                "profile":   {"score": round(prof, 1), "max": self._get_group_cap("profile"),
                              "label": "Profil Assure",      "triggers": prof_t},
            },
            "all_triggers":   all_triggers,
            "groupes_actifs": groupes_actifs,
            "bonus_cumul":    1.0,
            "bonus_applique": False,
        }

    def _status_from_score(self, score: float):
        if score > self.seuil_frauduleux:
            return "frauduleux", "critique" if score >= 85 else "eleve"
        if score >= self.seuil_suspect_min:
            return "suspect", "modere"
        return "non_frauduleux", "faible"

    def predict(self, sinistre_idx, sinistres_df=None, contrats_df=None, tiers_df=None):
        if not self.is_fitted:
            raise ValueError("Modele non entraîne !")
        if sinistre_idx >= len(self._data_cache["X"]):
            raise ValueError(f"Index {sinistre_idx} hors limites !")
        c = self.get_cached_compact(sinistre_idx)
        result = {
            "sinistre_id":          int(sinistre_idx),
            "score_suspicion":      c["total"],
            "score_brut":           c.get("score_brut", c["total"]),
            "statut_fraude":        c["statut"],
            "niveau_risque":        c["niveau"],
            "scores_groupes":       c["scores_groupes"],
            "indicateurs_detectes": c["triggers"],
            "groupes_actifs":       c["groupes_actifs"],
            "bonus_cumul":          1.0,
            "bonus_applique":       False,
            "timestamp":            datetime.now().isoformat(),
        }
        return self._to_native(result)
    def score_single(self, raw_features: dict) -> dict:
        """
        Score un sinistre individuel a partir d'un dict de features brutes.
        
        Utilise pour les nouveaux sinistres venant de Neo4j (sinistre_router).
        N'utilise PAS le cache --- travaille directement sur raw_features.
        
        raw_features doit contenir les cles utilisees par _get_raw(), ex :
            {
              "sinistre_heure_nuit": 1.0,
              "sinistre_weekend": 0.0,
              "declaration_tardive_30j": 1.0,
              "sinistre_moins_7j_apres_effet": 0.0,
              "montant_10x_prime": 1.0,
              "ratio_montant_prime": 12.5,
              "ratio_montant_moyen": 3.2,
              "montant_3std_suspect": 0.0,
              "distance_sinistre_residence_elevee": 1.0,
              "nbr_sinistres_vehicule": 2.0,
              "adverse_repete": 0.0,
              "temoin_frequent": 1.0,
              "incoherence_age_montant": 1.0,
              "profession_risque": 0.0,
              ...
            }
        
        Retourne le meme format que predict() :
            {
              "score_suspicion": 72.5,
              "statut_fraude": "frauduleux",
              "niveau_risque": "eleve",
              "scores_groupes": {...},
              "indicateurs_detectes": [...],
              "groupes_actifs": 3,
            }
        """
        if not self.is_fitted:
            raise ValueError("Modele non entraîne !")
 
        # Injecter les features dans un acces local (pas d'index cache)
        _raw = raw_features  # alias local
 
        def _g(feature: str, default: float = 0.0) -> float:
            """Équivalent de _get_raw() mais sur le dict local."""
            val = _raw.get(feature, default)
            try:
                v = float(val)
                import numpy as np
                return default if (np.isnan(v) or np.isinf(v)) else v
            except Exception:
                return default
 
        # ── 1) FINANCIER (max 35 pts) ─────────────────────────────────────
        fin, fin_t = 0.0, []
        group = "financial"
 
        is_3std = _g("montant_3std_suspect") > 0.5
        rmm     = _g("ratio_montant_moyen", 1.0)
 
        if is_3std:
            fin += self._get_indicator_weight("FIN_3STD", 25)
            fin_t.append({"code": "FIN_3STD",
                           "label": "Montant > µ+3σ (anomalie statistique extreme)",
                           "pts": 25, "group": group, "niveau": "critique"})
            if rmm > 5.0:
                fin += self._get_indicator_weight("FIN_3STD_PLUS", 3)
                fin_t.append({"code": "FIN_3STD_PLUS",
                               "label": f"Et montant = {rmm:.1f}x la moyenne",
                               "pts": 3, "group": group, "niveau": "eleve"})
        else:
            if rmm > 5.0:
                fin += self._get_indicator_weight("FIN_RATIO_5X", 14)
                fin_t.append({"code": "FIN_RATIO_5X",
                               "label": f"Montant = {rmm:.1f}x la moyenne",
                               "pts": 14, "group": group, "niveau": "eleve"})
            elif rmm > 3.0:
                fin += self._get_indicator_weight("FIN_RATIO_3X", 10)
                fin_t.append({"code": "FIN_RATIO_3X",
                               "label": f"Montant = {rmm:.1f}x la moyenne",
                               "pts": 10, "group": group, "niveau": "modere"})
            elif rmm > 2.0:
                fin += self._get_indicator_weight("FIN_RATIO_2X", 7)
                fin_t.append({"code": "FIN_RATIO_2X",
                               "label": f"Montant = {rmm:.1f}x la moyenne",
                               "pts": 7, "group": group, "niveau": "modere"})
            elif rmm > 1.5:
                fin += self._get_indicator_weight("FIN_RATIO_15X", 4)
                fin_t.append({"code": "FIN_RATIO_15X",
                               "label": f"Montant = {rmm:.1f}x la moyenne",
                               "pts": 4, "group": group, "niveau": "faible"})

        if _g("montant_10x_prime") > 0.5:
            fin += self._get_indicator_weight("FIN_10X_PRIME", 20)
            fin_t.append({"code": "FIN_10X_PRIME",
                           "label": "Montant > 10x la prime du contrat",
                           "pts": 20, "group": group, "niveau": "critique"})
        else:
            rmp = _g("ratio_montant_prime", 1.0)
            if rmp > 5.0:
                fin += self._get_indicator_weight("FIN_5X_PRIME", 10)
                fin_t.append({"code": "FIN_5X_PRIME",
                               "label": f"Montant = {rmp:.1f}x la prime",
                               "pts": 10, "group": group, "niveau": "eleve"})
            elif rmp > 3.0:
                fin += self._get_indicator_weight("FIN_3X_PRIME", 6)
                fin_t.append({"code": "FIN_3X_PRIME",
                               "label": f"Montant = {rmp:.1f}x la prime",
                               "pts": 6, "group": group, "niveau": "modere"})

        if _g("expert_cout_anormal") > 0.5:
            fin += self._get_indicator_weight("FIN_EXPERT_COUT", 8)
            fin_t.append({"code": "FIN_EXPERT_COUT",
                           "label": "Cout expert > 1.5x la moyenne",
                           "pts": 8, "group": group, "niveau": "eleve"})

        if _g("incoherence_age_montant") > 0.5:
            fin += self._get_indicator_weight("FIN_AGE_MONTANT", 6)
            fin_t.append({"code": "FIN_AGE_MONTANT",
                           "label": "Vehicule >10 ans + montant eleve",
                           "pts": 6, "group": group, "niveau": "modere"})

        rpv = _g("ratio_montant_pv_global", 1.0)
        if rpv > 2.5:
            fin += self._get_indicator_weight("FIN_PV_RATIO", 5)
            fin_t.append({"code": "FIN_PV_RATIO",
                           "label": f"Montant = {rpv:.1f}x moyenne du point de vente",
                           "pts": 5, "group": group, "niveau": "modere"})

        fin = min(fin, self._get_group_cap("financial"))
 
        # ── 2) TEMPOREL (max 35 pts) ──────────────────────────────────────
        temp, temp_t = 0.0, []
        group = "temporal"
 
# APRÈS
        if _g("declaration_tardive_15j") > 0.5:
            temp += self._get_indicator_weight("TMP_15J", 18)
            temp_t.append({"code": "TMP_15J",
                    "label": "Declaration > 15 j apres survenance",
                    "pts": 18, "group": group, "niveau": "eleve"})

        if _g("sinistre_moins_7j_apres_effet") > 0.5:
            temp += self._get_indicator_weight("TMP_7J_EFFET", 28)
            temp_t.append({"code": "TMP_7J_EFFET",
                            "label": "Sinistre < 7 j apres souscription du contrat",
                            "pts": 28, "group": group, "niveau": "critique"})

        if _g("sinistre_moins_7j_expiration") > 0.5:
            temp += self._get_indicator_weight("TMP_7J_EXP", 18)
            temp_t.append({"code": "TMP_7J_EXP",
                            "label": "Sinistre < 7 j avant expiration du contrat",
                            "pts": 18, "group": group, "niveau": "critique"})
        if _g("sinistre_heure_nuit") > 0.5:
            temp += self._get_indicator_weight("TMP_NUIT", 8)
            temp_t.append({"code": "TMP_NUIT",
                            "label": "Sinistre declare entre 0h et 5h du matin",
                            "pts": 8, "group": group, "niveau": "eleve"})

        if _g("sinistre_weekend") > 0.5:
            temp += self._get_indicator_weight("TMP_WEEKEND", 5)
            temp_t.append({"code": "TMP_WEEKEND",
                            "label": "Sinistre survenu un samedi ou dimanche",
                            "pts": 5, "group": group, "niveau": "modere"})

        if _g("cluster_temporel_vehicule") > 0.5:
            temp += self._get_indicator_weight("TMP_CLUSTER_VEH", 7)
            temp_t.append({"code": "TMP_CLUSTER_VEH",
                            "label": "Delai moyen ≤ 30 j entre sinistres du vehicule",
                            "pts": 7, "group": group, "niveau": "eleve"})

        if _g("cluster_temporel_client") > 0.5:
            temp += self._get_indicator_weight("TMP_CLUSTER_CLI", 7)
            temp_t.append({"code": "TMP_CLUSTER_CLI",
                            "label": "Delai moyen ≤ 30 j entre sinistres de l'assure",
                            "pts": 7, "group": group, "niveau": "eleve"})
 
        temp = min(temp, self._get_group_cap("temporal"))
 
        # ── 3) FRÉQUENCE (max 30 pts) ─────────────────────────────────────
        freq, freq_t = 0.0, []
        group = "frequency"
 
        if _g("client_plus7_sinistres_12m") > 0.5:
            freq += self._get_indicator_weight("FRQ_7", 25)
            freq_t.append({"code": "FRQ_7",
                            "label": "≥ 7 sinistres en 12 mois (meme assure)",
                            "pts": 25, "group": group, "niveau": "critique"})
        elif _g("client_plus3_sinistres_12m") > 0.5:
            freq += self._get_indicator_weight("FRQ_3", 16)
            freq_t.append({"code": "FRQ_3",
                            "label": "> 3 sinistres en 12 mois (meme assure)",
                            "pts": 16, "group": group, "niveau": "eleve"})

        nbv = _g("nbr_sinistres_vehicule", 0.0)
        if nbv >= 5:
            freq += self._get_indicator_weight("FRQ_VEH5", 12)
            freq_t.append({"code": "FRQ_VEH5",
                            "label": f"{int(nbv)} sinistres passes sur ce vehicule",
                            "pts": 12, "group": group, "niveau": "critique"})
        elif nbv >= 3:
            freq += self._get_indicator_weight("FRQ_VEH3", 8)
            freq_t.append({"code": "FRQ_VEH3",
                            "label": f"{int(nbv)} sinistres passes sur ce vehicule",
                            "pts": 8, "group": group, "niveau": "eleve"})
        elif nbv >= 2:
            freq += self._get_indicator_weight("FRQ_VEH2", 5)
            freq_t.append({"code": "FRQ_VEH2",
                            "label": f"{int(nbv)} sinistres passes sur ce vehicule",
                            "pts": 5, "group": group, "niveau": "modere"})

        if _g("contrat_avenants_frequents") > 0.5:
            freq += self._get_indicator_weight("FRQ_AVENANTS", 7)
            freq_t.append({"code": "FRQ_AVENANTS",
                            "label": "> 2 avenants suspects sur le contrat",
                            "pts": 7, "group": group, "niveau": "modere"})

        if _g("avenant_proche_sinistre_30j") > 0.5:
            freq += self._get_indicator_weight("FRQ_AVENANT_RECENT", 12)
            freq_t.append({"code": "FRQ_AVENANT_RECENT",
                            "label": "Avenant signe dans les 30j avant le sinistre",
                            "pts": 12, "group": group, "niveau": "eleve"})

        vr = max(_g("velocite_recente_vehicule", 0.0),
                 _g("velocite_recente_client",   0.0))
        if vr > 0.5:
            pts = min(6, max(1, int(vr * 6)))
            freq += pts
            freq_t.append({"code": "FRQ_VELOCITE",
                            "label": f"Acceleration recente des sinistres ({vr:.0%} en 30j)",
                            "pts": pts, "group": group, "niveau": "modere"})

        freq = min(freq, self._get_group_cap("frequency"))
 
        # ── 4) RÉSEAU / COLLUSION (max 22 pts) ────────────────────────────
        net, net_t = 0.0, []
        group = "network"

        if _g("sinistre_frontiere") > 0.5:
            net += self._get_indicator_weight("NET_FRONTIERE", 10)
            net_t.append({"code": "NET_FRONTIERE",
                           "label": "Sinistre a proximite d'une frontiere tunisienne",
                           "pts": 10, "group": group, "niveau": "eleve"})

        if _g("adverse_repete") > 0.5:
            net += self._get_indicator_weight("NET_ADVERSE", 10)
            net_t.append({"code": "NET_ADVERSE",
                           "label": "Tiers adverse deja implique dans > 2 sinistres",
                           "pts": 10, "group": group, "niveau": "eleve"})

        if _g("temoin_frequent") > 0.5:
            net += self._get_indicator_weight("NET_TEMOIN", 7)
            net_t.append({"code": "NET_TEMOIN",
                           "label": "Temoin present dans plus de 3 sinistres distincts",
                           "pts": 7, "group": group, "niveau": "eleve"})

        if _g("expert_vehicule_repete") > 0.5:
            net += self._get_indicator_weight("NET_EXPERT_VEH", 4)
            net_t.append({"code": "NET_EXPERT_VEH",
                           "label": "Expert + vehicule recurrents ensemble",
                           "pts": 4, "group": group, "niveau": "modere"})

        if _g("garage_taux_remplacement_eleve") > 0.5:
            net += self._get_indicator_weight("NET_GARAGE", 5)
            net_t.append({"code": "NET_GARAGE",
                           "label": "Garage avec taux de remplacement de pieces > 80%",
                           "pts": 5, "group": group, "niveau": "eleve"})

        if _g("lieu_sinistre_frequent") > 0.5:
            net += self._get_indicator_weight("NET_LIEU", 4)
            net_t.append({"code": "NET_LIEU",
                           "label": "Lieu de sinistre recurrent (> 3 fois)",
                           "pts": 4, "group": group, "niveau": "modere"})

        # Indicateur combo job/marque (si dispo)
        fjm = _g("freq_combo_job_marque", 0.0)
        if fjm > 5:
            net += self._get_indicator_weight("NET_COMBO_JOB", 3)
            net_t.append({"code": "NET_COMBO_JOB",
                           "label": f"Combo job-marque tres frequent ({int(fjm)} fois)",
                           "pts": 3, "group": group, "niveau": "modere"})

        net = min(net, self._get_group_cap("network"))
 
        # ── 5) CONDUCTEUR / MOBILITÉ (max 8 pts) ──────────────────────────
        drv, drv_t = 0.0, []
        group = "driver"

        if _g("note_conducteur_tres_faible") > 0.5:
            drv += self._get_indicator_weight("DRV_NOTE_TF", 4)
            drv_t.append({"code": "DRV_NOTE_TF",
                           "label": "Note conducteur < 3/10",
                           "pts": 4, "group": group, "niveau": "eleve"})
        elif _g("note_conducteur_faible") > 0.5:
            drv += self._get_indicator_weight("DRV_NOTE_F", 2)
            drv_t.append({"code": "DRV_NOTE_F",
                           "label": "Note conducteur < 5/10",
                           "pts": 2, "group": group, "niveau": "modere"})

        if _g("kilometrage_annuel_eleve") > 0.5:
            drv += self._get_indicator_weight("DRV_KM", 2)
            drv_t.append({"code": "DRV_KM",
                           "label": "Kilometrage annuel superieur a 30 000 km/an",
                           "pts": 2, "group": group, "niveau": "modere"})

        if _g("distance_sinistre_residence_elevee") > 0.5:
            drv += self._get_indicator_weight("DRV_DIST_SIN", 2)
            drv_t.append({"code": "DRV_DIST_SIN",
                           "label": "Sinistre a plus de 30 km du domicile",
                           "pts": 2, "group": group, "niveau": "modere"})

        if _g("distance_travail_residence_elevee") > 0.5:
            drv += self._get_indicator_weight("DRV_DIST_TRV", 1)
            drv_t.append({"code": "DRV_DIST_TRV",
                           "label": "Lieu de travail tres eloigne de la residence",
                           "pts": 1, "group": group, "niveau": "faible"})

        drv = min(drv, self._get_group_cap("driver"))
 
        # ── 6) PROFIL ASSURÉ (max 1 pt) ───────────────────────────────────
        prof, prof_t = 0.0, []
        group = "profile"

        if _g("profession_risque") > 0.5:
            prof += self._get_indicator_weight("PRF_JOB", 2)
            prof_t.append({"code": "PRF_JOB",
                            "label": "Usage a risque : taxi, louage, location",
                            "pts": 2, "group": group, "niveau": "modere"})

        if _g("usage_risque") > 0.5 and prof == 0.0:
            prof += self._get_indicator_weight("PRF_USAGE", 1)
            prof_t.append({"code": "PRF_USAGE",
                            "label": "Contrat usage taxi ou location",
                            "pts": 1, "group": group, "niveau": "faible"})

        prof = min(prof, self._get_group_cap("profile"))
 
        # ── TOTAL ─────────────────────────────────────────────────────────
        groupes_actifs = sum(1 for s in [fin, temp, freq, net, drv, prof] if s > 0)
        score_brut     = fin + temp + freq + net + drv + prof
        total          = round(min(score_brut, 100.0), 1)
 
        statut, niveau = self._status_from_score(total)
        all_triggers   = fin_t + temp_t + freq_t + net_t + drv_t + prof_t
 
        return {
            "score_suspicion":   total,
            "score_brut":        score_brut,
            "statut_fraude":     statut,
            "niveau_risque":     niveau,
            "scores_groupes": {
                "financial": round(fin,  1),
                "temporal":  round(temp, 1),
                "frequency": round(freq, 1),
                "network":   round(net,  1),
                "driver":    round(drv,  1),
                "profile":   round(prof, 1),
            },
            "indicateurs_detectes": all_triggers,
            "groupes_actifs":       groupes_actifs,
        }

    def get_global_statistics(self):
        if not self.is_fitted:
            raise ValueError("Modele non entraîne !")
        n      = self._true_sinistres_count
        scores = self._cached_scores
        fraude  = int((scores > self.seuil_frauduleux).sum())
        suspect = int(((scores >= self.seuil_suspect_min) & (scores <= self.seuil_frauduleux)).sum())
        normal  = int((scores < self.seuil_normal_max).sum())
        return {
            "total_sinistres": n,
            "score_moyen":     round(float(scores.mean()), 2),
            "score_median":    round(float(np.median(scores)), 2),
            "score_std":       round(float(scores.std()), 2),
            "score_min":       round(float(scores.min()), 2),
            "score_max":       round(float(scores.max()), 2),
            "seuil_frauduleux":  self.seuil_frauduleux,
            "seuil_suspect_min": self.seuil_suspect_min,
            "distribution": {
                "frauduleux": {"count": fraude,  "percentage": round(fraude / n * 100, 2)},
                "suspect":    {"count": suspect, "percentage": round(suspect / n * 100, 2)},
                "normal":     {"count": normal,  "percentage": round(normal / n * 100, 2)},
            },
            "percentiles": {
                "p25": round(float(np.percentile(scores, 25)), 2),
                "p50": round(float(np.percentile(scores, 50)), 2),
                "p75": round(float(np.percentile(scores, 75)), 2),
                "p90": round(float(np.percentile(scores, 90)), 2),
                "p95": round(float(np.percentile(scores, 95)), 2),
                "p99": round(float(np.percentile(scores, 99)), 2),
            },
            "models_actifs": {"total": len(self._active_models), "list": self._active_models},
            "scoring_params": {
                "bonus_actif": False,
                "version":     "3.14.1",
                "note":        "Poids recalibres v3.14.1 pour score moyen 35-45",
            },
        }

    def get_current_version_metrics(self) -> Dict:
        stats = self.validate_scoring()
        metrics = {
            "score_moyen": stats.get("score_moyen", 0.0),
            "pct_frauduleux": stats.get("pct_frauduleux", 0.0),
            "pct_suspect": stats.get("pct_suspect", 0.0),
            "pct_normal": stats.get("pct_normal", 0.0),
            "seuil_frauduleux": self.seuil_frauduleux,
            "seuil_suspect_min": self.seuil_suspect_min,
        }

        if self._supervised_labels is not None and self._cached_scores is not None:
            try:
                y_true = self._supervised_labels
                y_pred = (self._cached_scores >= self.seuil_frauduleux).astype(int)
                metrics.update({
                    "f1_score": round(float(f1_score(y_true, y_pred)), 4),
                    "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
                    "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
                    "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
                    "auc_roc": round(float(roc_auc_score(y_true, np.clip(self._cached_scores / 100.0, 0, 1))), 4),
                })
            except Exception:
                metrics.update({
                    "f1_score": "N/A",
                    "precision": "N/A",
                    "recall": "N/A",
                    "accuracy": "N/A",
                    "auc_roc": "N/A",
                })
        else:
            metrics.update({
                "f1_score": "N/A",
                "precision": "N/A",
                "recall": "N/A",
                "accuracy": "N/A",
                "auc_roc": "N/A",
            })
        return metrics

    def validate_scoring(self, sample_size: int = None):
        """Retourne les metriques de scoring sur le cache pre-calcule."""
        if not self.is_fitted:
            return {
                "error": "Modele non entraîne",
                "score_moyen": 0.0, "score_min": 0.0, "score_max": 0.0,
                "pct_frauduleux": 0.0, "pct_suspect": 0.0, "pct_normal": 0.0,
                "total_analyse": 0,
            }
        if self._cached_scores is None:
            return {
                "error": "Cache scores absent --- relancer fit()",
                "score_moyen": 0.0, "score_min": 0.0, "score_max": 0.0,
                "pct_frauduleux": 0.0, "pct_suspect": 0.0, "pct_normal": 0.0,
                "total_analyse": 0,
            }
        scores = self._cached_scores
        n = len(scores) if sample_size is None else min(sample_size, len(scores))
        sample = scores[:n]
        return {
            "score_moyen":    round(float(sample.mean()), 2),
            "score_min":      round(float(sample.min()), 2),
            "score_max":      round(float(sample.max()), 2),
            "pct_frauduleux": round(float((sample > self.seuil_frauduleux).mean() * 100), 2),
            "pct_suspect":    round(float(((sample >= self.seuil_suspect_min) & (sample <= self.seuil_frauduleux)).mean() * 100), 2),
            "pct_normal":     round(float((sample < self.seuil_normal_max).mean() * 100), 2),
            "total_analyse":  n,
            "seuil_frauduleux":  self.seuil_frauduleux,
            "seuil_suspect_min": self.seuil_suspect_min,
            "bonus_actif":       False,
            "version":           "3.14.1",
        }

    def evaluate_temporal_stability(self, recent_ratio: float = 0.2) -> Dict:
        if self._cached_scores is None or len(self._cached_scores) < 20:
            return {"error": "Donnees insuffisantes"}
        n      = len(self._cached_scores)
        split  = max(1, int(n * (1.0 - recent_ratio)))
        hist   = self._cached_scores[:split]
        recent = self._cached_scores[split:]
        if len(recent) == 0:
            return {"error": "Segment recent vide"}

        def _pct(arr, cond):
            return round(float(cond(arr).mean() * 100), 2)

        delta_moyen = float(np.mean(recent) - np.mean(hist))
        return {
            "n_historique":           int(len(hist)),
            "n_recent":               int(len(recent)),
            "score_moyen_historique": round(float(np.mean(hist)), 2),
            "score_moyen_recent":     round(float(np.mean(recent)), 2),
            "delta_score_moyen":      round(delta_moyen, 2),
            "pct_fraud_historique":   _pct(hist,   lambda a: a > self.seuil_frauduleux),
            "pct_fraud_recent":       _pct(recent, lambda a: a > self.seuil_frauduleux),
            "pct_suspect_historique": _pct(hist,   lambda a: (a >= self.seuil_suspect_min) & (a <= self.seuil_frauduleux)),
            "pct_suspect_recent":     _pct(recent, lambda a: (a >= self.seuil_suspect_min) & (a <= self.seuil_frauduleux)),
            "drift_alert":            abs(delta_moyen) > 5.0,
        }

    def _calc_importance(self, X, scores):
        importance = {}
        threshold  = np.percentile(scores, 90)
        is_anomaly = scores >= threshold
        feat_names = (
            self.feature_engineer.feature_names
            if self.feature_engineer
            else [f"feature_{i}" for i in range(X.shape[1])]
        )
        for i, name in enumerate(feat_names):
            if i >= X.shape[1]:
                continue
            va = X[is_anomaly,  i] if is_anomaly.sum()  > 0 else np.array([0])
            vn = X[~is_anomaly, i] if (~is_anomaly).sum() > 0 else np.array([0])
            md  = abs(np.mean(va) - np.mean(vn))
            std = (np.std(va) + np.std(vn)) / 2 + 1e-10
            importance[name] = md / std
        total = sum(importance.values())
        if total > 0:
            importance = {k: v / total for k, v in importance.items()}
        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

    def get_top_features(self, n: int = 10):
        if not self.feature_importance:
            return [
                ("💰 Montant anormalement eleve", 0.16),
                ("⏰ Delai declaration >30 jours", 0.14),
                ("🚗 Multi-sinistres par vehicule", 0.11),
                ("🌍 Sinistre frontiere",           0.09),
                ("🔍 Expert recurrent",             0.08),
                ("🔧 Garage suspect",               0.07),
                ("🏠 Sinistre au domicile",         0.06),
                ("⚠️ Sinistre proche fin contrat",  0.05),
                ("👥 Temoin frequent",              0.04),
                ("📊 Kilometrage annuel eleve",     0.03),
            ][:n]
        result = []
        for name, imp in list(self.feature_importance.items())[:n]:
            readable = FEATURE_NAME_MAPPING.get(name, name)
            if readable == name:
                if readable.startswith("num_"):    readable = readable[4:]
                elif readable.startswith("std_"):  readable = f"📊 Écart-type {readable[4:]}"
                elif readable.startswith("freq_"): readable = f"🔄 Frequence {readable[5:]}"
                elif readable.startswith("cat_"):  readable = f"📋 Categorie {readable[4:]}"
            if len(readable) > 40:
                readable = readable[:37] + "..."
            result.append((readable, round(imp, 4)))
        return result

    def get_info(self):
        return {
            "type":            "Auto-Fraud Detection v3.14.1",
            "est_entraine":    self.is_fitted,
            "nb_features":     len(self.feature_engineer.feature_names) if self.feature_engineer else 0,
            "nb_models":       len(self.models),
            "models_actifs":   self._active_models,
            "seuil_frauduleux":  self.seuil_frauduleux,
            "seuil_suspect_min": self.seuil_suspect_min,
            "seuil_normal_max":  self.seuil_normal_max,
            "grille_scoring":    self.config.group_weights,
            "calibration": {
                "1_signal_fort":     "15-28 pts (normal)",
                "2_3_signaux_forts": "40-60 pts (suspect)",
                "4_5_signaux_forts": "70-90 pts (frauduleux)",
                "cas_extreme":       "90-100 pts",
            },
            "version": "3.14.1",
        }

    def save(self, path: str = "models/auto_fraud_model.pkl"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "feature_engineer":         self.feature_engineer,
                "models":                   self.models,
                "seuil_normal_max":         self.seuil_normal_max,
                "seuil_suspect_min":        self.seuil_suspect_min,
                "seuil_frauduleux":         self.seuil_frauduleux,
                "feature_importance":       self.feature_importance,
                "is_fitted":                self.is_fitted,
                "selected_feature_indices": self.selected_feature_indices,
                "_data_cache":              self._data_cache,
                "_raw_sinistres":           self._raw_sinistres,
                "_raw_feature_matrix":      self._raw_feature_matrix,
                "_true_sinistres_count":    self._true_sinistres_count,
                "_cached_scores":           self._cached_scores,
                "_cached_compact":          self._cached_compact,
                "_active_models":           self._active_models,
                "saved_at":                 datetime.now().isoformat(),
                "version":                  "3.14.1",
            }, f)
        print(f"✅ Modele v3.14.1 sauvegarde : {path}")

    def load(self, path: str = "models/auto_fraud_model.pkl"):
        if not os.path.exists(path):
            print(f"⚠️ Modele non trouve : {path}")
            return False
        try:
            with open(path, "rb") as f:
                d = pickle.load(f)
            print(f"📖 Pickle charge depuis {path}")
        except Exception as e:
            print(f"❌ Erreur lors du chargement pickle : {e}")
            return False
        self.feature_engineer          = d["feature_engineer"]
        self.models                    = d["models"]
        self.seuil_normal_max          = d.get("seuil_normal_max", 50.0)
        self.seuil_suspect_min         = d.get("seuil_suspect_min", 50.0)
        self.seuil_frauduleux          = d.get("seuil_frauduleux", 70.0)
        self.feature_importance        = d.get("feature_importance", {})
        self.is_fitted                 = d.get("is_fitted", False)
        self.selected_feature_indices  = d.get("selected_feature_indices", [])
        self._data_cache               = d.get("_data_cache", {})
        self._raw_sinistres            = d.get("_raw_sinistres")
        self._raw_feature_matrix       = d.get("_raw_feature_matrix")
        self._true_sinistres_count     = d.get("_true_sinistres_count", 0)
        self._cached_scores            = d.get("_cached_scores")
        self._cached_compact           = d.get("_cached_compact")
        self._active_models            = d.get("_active_models", [])
        if not self._active_models and self.is_fitted:
            self._active_models = ["if", "lof", "ee"]

        # ── Recalculer le cache si necessaire ───────────────────────────────
        if self.is_fitted and (self._cached_scores is None or len(self._cached_scores) == 0):
            print("🔄 Recalcul du cache des scores apres chargement...")
            self._recompute_cache()

        print(f"✅ Modele v{d.get('version', '?')} charge : {path}")
        return True

    def _recompute_cache(self):
        """Recalcule le cache des scores apres chargement du modele."""
        if not self.is_fitted or self._raw_sinistres is None:
            print("⚠️ Impossible de recalculer le cache : modele non entraîne")
            return

        print(f"🔄 Recalcul du cache pour {len(self._raw_sinistres)} sinistres...")
        scores = np.zeros(len(self._raw_sinistres))
        compact = []

        for i in range(len(self._raw_sinistres)):
            gs = self.get_cached_compact(i)
            final_score = gs["total"]
            scores[i] = final_score
            compact.append(gs)

        self._cached_scores = scores
        self._cached_compact = compact
        print(f"   ✅ Cache recalcule ({len(scores)} scores)")

    def get_human_readable_indicators(self, n: int = 10) -> List[Dict]:
        if (not self.is_fitted
                or self._raw_feature_matrix is None
                or self._cached_scores is None):
            return self._get_default_indicators()
        df_raw  = self._raw_feature_matrix
        n_samp  = min(len(df_raw), 5000)
        scores  = self._cached_scores[:n_samp]
        high_idx = np.where(scores >= self.seuil_suspect_min)[0]
        low_idx  = np.where(scores < self.seuil_suspect_min)[0]
        high_df  = df_raw.iloc[high_idx] if len(high_idx) > 0 else pd.DataFrame()
        low_df   = df_raw.iloc[low_idx]  if len(low_idx)  > 0 else pd.DataFrame()
        indicators = []

        def _try_add(col, nom, seuil_ratio=1.2, seuil_abs=0, max_pts=25, base_pts=12, scale=1.0):
            if col not in df_raw.columns:
                return
            d_h = high_df[col].fillna(0).mean() if len(high_df) > 0 else 0
            d_l = low_df[col].fillna(0).mean()  if len(low_df)  > 0 else 0
            if d_h > d_l * seuil_ratio and d_h > seuil_abs:
                indicators.append({
                    "nom": nom,
                    "pourcentage_contribution": round(
                        min(max_pts, base_pts * (d_h / max(d_l, 1) - 0.8) * scale), 1
                    ),
                    "description": f"Haute: {d_h:.1f} vs normale: {d_l:.1f}",
                })

        _try_add("declaration_tardive_15j", "⏰ Declaration tardive (>15 j)", base_pts=10, seuil_abs=0.5)
        _try_add("num_TOTALREGLEMENT",                   "💰 Montant anormalement eleve",   seuil_abs=10000)
        _try_add("ratio_montant_prime",                  "💰 Montant vs prime du contrat",   seuil_abs=3)
        _try_add("sinistre_frontiere",                   "🌍 Sinistre a proximite frontiere", base_pts=8)
        _try_add("nbr_sinistres_vehicule",               "🚗 Vehicules multi-sinistres",      seuil_abs=2)
        _try_add("sinistre_heure_nuit",                  "🌙 Sinistre entre 0h et 5h",        base_pts=6)
        _try_add("avenant_proche_sinistre_30j",          "⚠️ Avenant avant sinistre",         base_pts=8)
        _try_add("distance_sinistre_residence_identical","🏠 Sinistre declare au domicile",   base_pts=5)
        _try_add("freq_EXPERT_STAREX",                   "🔍 Expert recurrent",               seuil_abs=2)
        _try_add("montant_cumule_vehicule",              "💰 Historique montants eleve",      base_pts=8)

        total = sum(i["pourcentage_contribution"] for i in indicators)
        if total > 0:
            for i in indicators:
                i["pourcentage_contribution"] = round(
                    i["pourcentage_contribution"] / total * 100, 1
                )
        indicators.sort(key=lambda x: x["pourcentage_contribution"], reverse=True)
        return indicators[:n]

    def _get_default_indicators(self) -> List[Dict]:
        return [
            {"nom": "⏰ Delai declaration >30 jours",    "pourcentage_contribution": 18.0},
            {"nom": "💰 Montant >10x la prime contrat",  "pourcentage_contribution": 16.0},
            {"nom": "🚗 Vehicule >2 sinistres/an",       "pourcentage_contribution": 13.0},
            {"nom": "⚠️ Avenant avant sinistre",         "pourcentage_contribution": 11.0},
            {"nom": "🌍 Sinistre frontiere",              "pourcentage_contribution":  9.0},
            {"nom": "🔧 Garage taux remplacement eleve",  "pourcentage_contribution":  8.0},
            {"nom": "🏠 Sinistre au domicile",            "pourcentage_contribution":  7.0},
            {"nom": "🌙 Sinistre la nuit (0h--5h)",        "pourcentage_contribution":  6.0},
            {"nom": "🔍 Expert recurrent",                "pourcentage_contribution":  5.0},
            {"nom": "📊 Kilometrage annuel eleve",        "pourcentage_contribution":  4.0},
        ]

    # ════════════════════════════════════════════════════════════════════════
    # GESTION DES VERSIONS --- v1.0
    # ════════════════════════════════════════════════════════════════════════

    def list_all_versions(self) -> List[Dict]:
        """Liste toutes les versions avec leurs KPIs."""
        return self.version_manager.list_versions()

    def get_version_metrics(self, version_num: int) -> Optional[Dict]:
        """Retourne les KPIs d'une version."""
        info = self.version_manager.get_version_info(version_num)
        return info["metrics"] if info else None

    def load_version(self, version_num: int) -> bool:
        """Charge une version specifique."""
        info = self.version_manager.get_version_info(version_num)
        if not info:
            print(f"❌ Version {version_num} non trouvee")
            return False
        
        model_path = info["model_path"]
        if self.load(model_path):
            self.current_version_num = self.version_manager.get_next_version_number()
            print(f"✅ Version {version_num} chargee")
            print(f"   F1-Score : {info['metrics'].get('f1_score', 'N/A')}")
            print(f"   Accuracy : {info['metrics'].get('accuracy', 'N/A')}")
            return True
        return False

    def set_active_version(self, version_num: int) -> bool:
        """Definit la version active pour les predictions."""
        if self.version_manager.set_active_version(version_num):
            print(f"✅ Version {version_num} activee")
            return self.load_version(version_num)
        return False

    def delete_version(self, version_num: int) -> bool:
        """Supprime une version non-active. Retourne True si succès."""
        if self.version_manager.delete_version(version_num):
            print(f"✅ Version {version_num} supprimee avec succes")
            return True
        else:
            print(f"❌ Impossible de supprimer la version {version_num} (version active ou non trouvee)")
            return False

    def compare_versions(self, v1: int, v2: int) -> Dict:
        """Compare deux versions et indique la meilleure."""
        comparison = self.version_manager.compare_versions(v1, v2)
        if "error" not in comparison:
            def _format_delta(value):
                return f"{value:+.4f}" if value is not None else "N/A"

            print(f"\n📊 Comparaison v{v1} vs v{v2}:")
            print(f"   F1-Score delta  : {_format_delta(comparison.get('f1_delta'))}")
            print(f"   Precision delta : {_format_delta(comparison.get('precision_delta'))}")
            print(f"   Recall delta    : {_format_delta(comparison.get('recall_delta'))}")
            print(f"   AUC delta       : {_format_delta(comparison.get('auc_delta'))}")
            print(f"   ⭐ Meilleure version : v{comparison.get('meilleure_version')}")
        return comparison

    def display_version_history(self):
        """Affiche l'historique complet des versions."""
        versions = self.list_all_versions()
        print("\n" + "="*100)
        print("📋 HISTORIQUE DES VERSIONS")
        print("="*100)
        for v in versions:
            status = "🟢 ACTIVE" if v["active"] else "⚪"
            print(f"\nv{v['version']} {status} --- {v['created_at']}")
            print(f"   F1-Score  : {v['f1_score']}")
            print(f"   Precision : {v['precision']}")
            print(f"   Recall    : {v['recall']}")
            print(f"   Accuracy  : {v['accuracy']}")
            print(f"   AUC-ROC   : {v['auc_roc']}")
            print(f"   Score moy : {v['score_moyen']}")
            if v['notes']:
                print(f"   Notes     : {v['notes']}")
        print("="*100)
    