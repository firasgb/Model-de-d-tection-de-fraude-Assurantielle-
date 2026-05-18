"""
main.py --- API unifiee de detection de fraude (v3.14)
✅ Demarrage automatique Excel + Neo4j (ML integre)
✅ Toutes les routes pour le dashboard AIMLDashboard.jsx
✅ Gestion des notifications via sinistre_router
✅ v3.14 : poids recalibres, geocoder TunisiaGeocoder integre
✅ v3.14 : nouveaux triggers (heure nuit, weekend, avenant recent, ratio prime)
✅ v3.14 : SCORE_GROUPS_MAX mis a jour (temporal 35, frequency 30, network 22)
✅ CORRECTION : pipeline Neo4j supprime --> scoring sinistre par sinistre (sinistre_router)
"""

import sys
import os
from hashlib import md5
from io import BytesIO
from datetime import datetime
from typing import List, Optional, Dict, Any
from collections import defaultdict

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import pandas as pd
import numpy as np
from uuid import uuid4
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ml.auto_fraud_detector import AutoFraudDetector
from ml.scoring_config import ScoringConfig, ScoringConfigManager
from ml.auto_feature_engineering import _get_direction
from utils.data_loader import DataLoader

try:
    from ml.community_detector import CommunityDetector
    from utils.neo4j_loader import PFE2026Neo4jLoader
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    print("⚠️ Neo4j non disponible")

# ── Geocodeur Tunisia (optionnel) ─────────────────────────────────────────────
try:
    from ml.geo_utils import TunisiaGeocoder
    GEO_AVAILABLE = True
except ImportError:
    GEO_AVAILABLE = False
    print("⚠️ TunisiaGeocoder non disponible")

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.enums import TA_CENTER

from sinistre_router import router as sinistre_router, pending_notifications

app = FastAPI(title="API Detection de Fraude Automatique", version="3.14.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sinistre_router, prefix="/sinistres", tags=["sinistres"])

# ─── Variables globales ───────────────────────────────────────────────────────
fraud_detector: Optional[AutoFraudDetector] = None
data_loader = DataLoader()
sinistres_df = None
contrats_df  = None
tiers_df     = None
neo4j_loader = None
community_detector = None
geocoder = None  # TunisiaGeocoder instance

PAGE_W            = A4[0] - 4 * cm
SEUIL_NORMAL_MAX  = 49.99
SEUIL_SUSPECT_MIN = 50.0
SEUIL_FRAUDULEUX  = 70.0
PDF_REPORT_CACHE  = {}

# ── v3.14 : caps mis a jour ───────────────────────────────────────────────────
GROUP_CAPS = {
    "financial": 35,
    "temporal":  35,   # +5 vs v3.13
    "frequency": 30,   # +5 vs v3.13
    "network":   22,   # +2 vs v3.13
    "driver":     8,
    "profile":    1,
}
GROUP_LABELS = {
    "financial": "Financier",
    "temporal":  "Temporel",
    "frequency": "Frequence",
    "network":   "Reseau / Collusion",
    "driver":    "Conducteur / Mobilite",
    "profile":   "Profil Assure",
}

# ── v3.14 : mapping enrichi (nouveaux triggers) ───────────────────────────────
FEATURE_NAME_MAPPING = {
    "num_TOTALREGLEMENT":                    "💰 Montant du sinistre",
    "std_TOTALREGLEMENT":                    "📊 Écart-type du montant",
    "ratio_montant_moyen":                   "📈 Ratio montant / moyenne",
    "ratio_montant_median":                  "📈 Ratio montant / mediane",
    "ratio_montant_prime":                   "💰 Ratio montant / prime contrat",
    "montant_10x_prime":                     "🚨 Montant > 10x la prime",
    "zscore_montant":                        "📊 Écart normalise du montant",
    "montant_3std_suspect":                  "⚠️ Montant anormal (>3σ)",
    "ratio_montant_vs_garage":               "🔧 Montant vs garage",
    "ratio_montant_vs_expert":               "🔍 Montant vs expert",
    "ratio_montant_vs_client":               "👤 Montant vs client moyen",
    "expert_cout_anormal":                   "💰 Cout expert anormal",
    "incoherence_age_montant":               "🚗 Vehicule age + montant eleve",
    "ratio_montant_pv_global":               "🏪 Montant vs point de vente",
    "ratio_montant_vs_combo_job_marque":     "🔄 Montant anormal combo job/marque",
    "decalage_survenance_declaration_jours": "⏰ Delai de declaration",
    "declaration_tardive_30j":               "⚠️ Declaration >30 jours",
    "declaration_tres_tardive_90j":          "🚨 Declaration >90 jours",
    "sinistre_moins_7j_apres_effet":         "⚠️ Sinistre <7j apres effet",
    "sinistre_moins_30j_apres_effet":        "⚠️ Sinistre <30j apres effet",
    "sinistre_moins_7j_expiration":          "⚠️ Sinistre <7j avant expiration",
    "sinistre_moins_30j_expiration":         "⚠️ Sinistre <30j avant expiration",
    "declaration_apres_weekend":             "📅 Declaration post-weekend",
    "sinistre_heure_nuit":                   "🌙 Sinistre entre 0h et 5h",
    "sinistre_weekend":                      "📅 Sinistre samedi/dimanche",
    "survenance_mois":                       "📅 Mois de survenance",
    "is_weekend_DATE_SURVENANCE":            "📅 Sinistre weekend",
    "nbr_sinistres_vehicule":                "🚗 Sinistres par vehicule",
    "nbr_sinistres_contrat":                 "📄 Sinistres par contrat",
    "nbr_sinistres_client":                  "👤 Sinistres par assure",
    "nbr_sinistres_expert":                  "🔍 Sinistres par expert",
    "nbr_sinistres_garage":                  "🔧 Sinistres par garage",
    "nbr_sinistres_adverse":                 "🚗 Sinistres par tiers adverse",
    "sinistres_client_12mois":               "📊 Sinistres/12 mois",
    "client_plus3_sinistres_12m":            "⚠️ >3 sinistres/an",
    "client_plus7_sinistres_12m":            "🚨 +7 sinistres/an",
    "delai_moyen_sinistres":                 "⏱️ Delai moyen sinistres",
    "cluster_temporel_vehicule":             "🕐 Sinistres rapproches vehicule",
    "cluster_temporel_client":               "🕐 Sinistres rapproches client",
    "velocite_recente_vehicule":             "⚡ Acceleration sinistres vehicule",
    "velocite_recente_client":               "⚡ Acceleration sinistres client",
    "nb_avenants_contrat":                   "📄 Nombre d'avenants",
    "contrat_avenants_frequents":            "📄 Avenants frequents (>2)",
    "avenant_proche_sinistre_30j":           "⚠️ Avenant <30j avant sinistre",
    "freq_IMMATRICULATION":                  "🚗 Frequence par immatriculation",
    "freq_EXPERT_STAREX":                    "🔍 Frequence par expert",
    "freq_GARAGES":                          "🔧 Frequence par garage",
    "freq_expert_meme_vehicule":             "🔄 Expert-vehicule recurrent",
    "expert_vehicule_repete":                "🔄 Expert + vehicule repetes",
    "adverse_repete":                        "🚗 Tiers adverse recurrent",
    "freq_temoin":                           "👥 Frequence temoin",
    "temoin_frequent":                       "👥 Temoin frequent (>3x)",
    "lieu_sinistre_frequent":                "📍 Lieu sinistre recurrent",
    "garage_taux_remplacement_eleve":        "🔧 Taux remplacement >80%",
    "freq_combo_job_marque":                 "🔄 Combo job-marque suspect",
    "note_conducteur_faible":                "👤 Note conducteur <5/10",
    "note_conducteur_tres_faible":           "🚨 Note conducteur <3/10",
    "kilometrage_annuel_eleve":              "📊 Kilometrage >30k/an",
    "distance_sinistre_residence_elevee":    "📍 Distance sinistre >30km",
    "distance_sinistre_residence_identical": "📍 Sinistre a domicile",
    "distance_travail_residence_elevee":     "🏢 Travail eloigne residence",
    "distance_travail_residence_identical":  "🏢 Travail = residence",
    "profession_risque":                     "⚠️ Profession a risque",
    "sinistre_grave_sans_services":          "🚨 Sinistre grave sans services",
    "nb_services_operationnels":             "📋 Services operationnels",
    "contrat_avenants_frequents":            "📄 Avenants frequents (>2)",
    "sinistre_frontiere":                    "🌍 Sinistre frontiere tunisienne",
    "montant_cumule_vehicule":               "💰 Montant cumule vehicule",
}


# ─── Helper : mapping feature --> groupe heuristique ───────────────────────────
def _infer_feature_group(feature_name: str) -> str:
    f = feature_name.lower()

    if any(k in f for k in (
        "montant", "reglement", "zscore", "3std", "ratio_montant",
        "cout_expert", "incoherence_age", "ratio_pv", "ratio_combo",
        "ratio_montant_vs", "montant_cumule", "montant_moyen",
        "ratio_prime", "10x_prime",
    )):
        return "financial"

    if any(k in f for k in (
        "date", "decalage", "declaration_tardive", "declaration_tres_tardive",
        "sinistre_moins", "jours_apres", "jours_avant", "cluster_temporel",
        "velocite_recente", "declaration_apres_weekend", "survenance_mois",
        "is_weekend", "diff_days",
        "heure_nuit", "sinistre_weekend",
    )):
        return "temporal"

    if any(k in f for k in (
        "nbr_sinistres", "sinistres_client", "client_plus",
        "contrat_avenants", "nb_avenants", "velocite", "delai_moyen",
        "nbr_sinistres_contrat", "nbr_sinistres_vehicule",
        "avenant_proche",
    )):
        return "frequency"

    if any(k in f for k in (
        "adverse", "temoin", "expert_vehicule", "garage_taux",
        "lieu_sinistre", "freq_combo", "frontiere", "freq_expert",
        "freq_garage", "freq_immatriculation", "sinistre_frontiere",
        "nbr_sinistres_adverse", "nbr_sinistres_expert", "nbr_sinistres_garage",
    )):
        return "network"

    if any(k in f for k in (
        "note_conducteur", "kilometrage", "distance_sinistre",
        "distance_travail", "profession_risque",
    )):
        return "driver"

    if any(k in f for k in (
        "sinistre_grave", "nb_services", "cat_assure", "assure_type",
        "assure_job", "freq_acteur",
    )):
        return "profile"

    return "other"


def _build_features_catalog(feature_names: list, raw_df=None) -> dict:
    groups: dict = {g: [] for g in list(GROUP_LABELS.keys()) + ["other"]}

    for feat in feature_names:
        group     = _infer_feature_group(feat)
        label     = FEATURE_NAME_MAPPING.get(feat, feat)
        direction = _get_direction(feat)

        entry = {
            "feature":   feat,
            "label":     label,
            "direction": direction,
        }

        if raw_df is not None and feat in raw_df.columns:
            col = raw_df[feat].dropna()
            entry["stats"] = {
                "mean":       round(float(col.mean()), 4)  if len(col) > 0 else None,
                "pct_nonzero": round(float((col != 0).mean() * 100), 2) if len(col) > 0 else None,
            }

        groups[group].append(entry)

    return {g: v for g, v in groups.items() if v}


# ─── Helpers generaux ─────────────────────────────────────────────────────────
def clean_for_json(obj):
    if isinstance(obj, float) and (np.isinf(obj) or np.isnan(obj)):
        return 0
    if isinstance(obj, pd.Timestamp):
        return str(obj)
    return obj

def safe_float(val, default=0.0):
    try:
        v = float(val)
        return 0.0 if np.isnan(v) or np.isinf(v) else v
    except Exception:
        return default

def safe_str(val, default="N/A"):
    return default if val is None or (isinstance(val, float) and np.isnan(val)) else str(val)

def fmt_date(s):
    return (str(s).split(" ")[0].split("T")[0]) if s else "-"

def fmt_tnd(n):
    return "0 TND" if n is None or n <= 0 else f"{n:,.0f} TND"


class RetrainRequest(BaseModel):
    seuil_frauduleux: Optional[float] = None
    seuil_suspect_min: Optional[float] = None
    sample_fraction: Optional[float] = 1.0
    label_column: Optional[str] = None  # Ex: "is_fraud", "fraud_label"
    notes: Optional[str] = None


class TrainingStatus(BaseModel):
    job_id: Optional[str] = None
    status: str = "idle"
    progress: int = 0
    message: str = "En attente"
    active_version: Optional[int] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    updated_at: Optional[str] = None


def _now_iso():
    return datetime.utcnow().isoformat() + "Z"


def _initialize_training_status():
    return {
        "job_id": None,
        "status": "idle",
        "progress": 0,
        "message": "Aucun entraînement en cours",
        "active_version": None,
        "error": None,
        "started_at": None,
        "updated_at": None,
    }


def _set_training_status(job_id: Optional[str], status: str, progress: int, message: str, active_version: Optional[int] = None, error: Optional[str] = None, **extras):
    # Build base status
    base = {
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "message": message,
        "active_version": active_version,
        "error": error,
        "started_at": app.state.training_status.get("started_at") if app.state.training_status else (_now_iso() if status != "idle" else None),
        "updated_at": _now_iso(),
    }
    # Merge any extra keys (e.g. label_source)
    if extras:
        base.update(extras)
    app.state.training_status = base


def _get_training_status():
    return app.state.training_status


def _find_supervised_label_column(df: pd.DataFrame, requested_label_column: Optional[str] = None):
    candidate_cols = ["fraud_label", "is_fraud", "target", "y", "label", "statut_fraude"]
    if requested_label_column:
        if requested_label_column in df.columns:
            return requested_label_column, True
        raise ValueError(f"Colonne de label explicite introuvable: {requested_label_column}")
    for col in candidate_cols:
        if col in df.columns:
            return col, True
    return None, False


def _ensure_auto_is_fraud_label(detector: AutoFraudDetector, df: pd.DataFrame, contrats_df, tiers_df, sample_fraction: float):
    if "is_fraud" in df.columns:
        return "is_fraud"

    if not getattr(detector, "is_fitted", False) or getattr(detector, "_cached_scores", None) is None or len(getattr(detector, "_cached_scores", [])) != len(df):
        detector.fit(
            df,
            contrats_df,
            tiers_df,
            geocoder=geocoder,
            sample_fraction=sample_fraction,
            progress_callback=lambda *_: None,
            save_version=False,
        )

    scores = getattr(detector, "_cached_scores", None)
    if scores is None:
        raise RuntimeError("Impossible de generer les scores pour creer is_fraud")

    df["is_fraud"] = np.where(
        scores > SEUIL_FRAUDULEUX,
        1,
        np.where(scores >= SEUIL_SUSPECT_MIN, 2, 0),
    )
    return "is_fraud"


def _run_training_job(job_id: str, payload: RetrainRequest):
    try:
        _set_training_status(job_id, "running", 0, "Preparation du reentraînement...", app.state.training_status.get("active_version") if app.state.training_status else None)

        detector = getattr(app.state, "fraud_detector", fraud_detector)
        if detector is None:
            raise RuntimeError("Aucun detecteur de fraude disponible pour l'entraînement")
        if sinistres_df is None:
            raise RuntimeError("Donnees sinistres non disponibles pour l'entraînement")

        def progress_callback(progress_pct: int, message: str):
            _set_training_status(
                job_id,
                "running",
                max(0, min(100, int(progress_pct))),
                message,
                active_version=detector.version_manager.get_active_version(),
            )

        progress_callback(5, "Demarrage du reentraînment")
        label_column = None
        explicit_label = False
        try:
            label_column, explicit_label = _find_supervised_label_column(sinistres_df, payload.label_column)
        except ValueError as e:
            raise RuntimeError(str(e)) from e

        if not explicit_label:
            progress_callback(10, "Aucun label supervise trouve, generation automatique de is_fraud...")
            label_column = _ensure_auto_is_fraud_label(
                detector,
                sinistres_df,
                contrats_df,
                tiers_df,
                payload.sample_fraction if payload.sample_fraction is not None else 1.0,
            )
            progress_callback(15, f"Colonne supervisee auto-creee: {label_column}")
            # Indiquer la source des labels dans le statut du job
            _set_training_status(job_id, "running", app.state.training_status.get("progress", 0) if app.state.training_status else 15, f"Colonne supervisee auto-creee: {label_column}", active_version=detector.version_manager.get_active_version(), label_source="auto")
        else:
            progress_callback(10, f"Utilisation du label supervise existant: {label_column}")
            _set_training_status(job_id, "running", app.state.training_status.get("progress", 0) if app.state.training_status else 10, f"Utilisation du label supervise existant: {label_column}", active_version=detector.version_manager.get_active_version(), label_source="manual")

        before_active_version = detector.version_manager.get_active_version()

        detector.fit(
            sinistres_df,
            contrats_df,
            tiers_df,
            geocoder=geocoder,
            label_column=label_column,
            label_source='auto' if not explicit_label else 'manual',
            sample_fraction=payload.sample_fraction if payload.sample_fraction is not None else 1.0,
            progress_callback=progress_callback,
        )

        version_num = detector.version_manager.get_active_version()
        if version_num is None or version_num == before_active_version:
            # Le détecteur n'a pas créé de version automatiquement pendant fit(),
            # on la crée ici.
            version_num = detector.version_manager.get_next_version_number()
            version_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "models",
                "versions",
                f"v{version_num}_model.pkl",
            )
            detector.save(version_path)

            metrics = detector.get_current_version_metrics()
            detector.version_manager.save_version(
                version_num,
                version_path,
                metrics,
                notes=payload.notes or "Reentrainement declenche depuis l'API",
            )
            detector.version_manager.set_active_version(version_num)
        else:
            # Le détecteur a déjà sauvegardé la version durant fit().
            version_num = int(version_num)

        default_model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "auto_fraud_model.pkl")
        detector.save(default_model_path)

        _set_training_status(job_id, "completed", 100, f"Reentrainement termine, version active v{version_num}", active_version=version_num)
    except Exception as e:
        error_message = str(e)
        _set_training_status(
            job_id,
            "failed",
            app.state.training_status.get("progress", 0) if app.state.training_status else 0,
            "Échec du reentraînement : " + error_message,
            active_version=app.state.training_status.get("active_version") if app.state.training_status else None,
            error=error_message,
        )
        raise


# ─── DÉMARRAGE ────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    global fraud_detector, sinistres_df, contrats_df, tiers_df
    global neo4j_loader, community_detector, geocoder

    print("\n" + "=" * 70)
    print("SYSTÈME AUTO DE DÉTECTION DE FRAUDE ")
    print(f"Seuils --> Frauduleux > {SEUIL_FRAUDULEUX} | Suspect {SEUIL_SUSPECT_MIN}-{SEUIL_FRAUDULEUX} | Normal < {SEUIL_SUSPECT_MIN}")
    print("Mode : poids recalibres v3.14 --- score moyen cible 35-45")
    print("=" * 70)

    # ── Initialisation du geocodeur ───────────────────────────────────────
    if GEO_AVAILABLE:
        try:
            geocoder = TunisiaGeocoder(
                cache_path="data/geocode_cache.json",
                enable_api=False,
            )
            print("✅ TunisiaGeocoder initialise (offline)")
        except Exception as e:
            print(f"⚠️ TunisiaGeocoder echoue : {e}")
            geocoder = None
    else:
        geocoder = None

    try:
        data_loader.load_all()
        sinistres_df = data_loader.get_sinistres()
        contrats_df  = data_loader.get_contrats()
        tiers_df     = data_loader.get_tiers()

        if sinistres_df is None or len(sinistres_df) == 0:
            print("❌ Aucun fichier sinistres.xlsx valide n'a pu être chargé depuis /data")
            return

        print(
            f"✅ Sinistres : {len(sinistres_df)} "
            f"| Contrats : {len(contrats_df) if contrats_df is not None else 0} "
            f"| Tiers : {len(tiers_df) if tiers_df is not None else 0}"
        )

        # ── Tentative de chargement du modele sauvegarde ─────────────────────
        import os
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "auto_fraud_model.pkl")
        fraud_detector = AutoFraudDetector()

        # ── Verifier s'il y a une version active ──────────────────────────────
        active_version = fraud_detector.version_manager.get_active_version()
        if active_version is not None:
            print(f"🔄 Version active detectee : v{active_version}")
            if fraud_detector.set_active_version(active_version):
                print(f"✅ Version active v{active_version} chargee")
                model_loaded = True  # Version active chargee avec succes
            else:
                print(f"⚠️ Impossible de charger la version active v{active_version}, chargement du modele par defaut")
                model_loaded = fraud_detector.load(model_path)
        else:
            print(f"🔍 Aucune version active, tentative de chargement du modele par defaut depuis : {model_path}")
            model_loaded = fraud_detector.load(model_path)

        if model_loaded:
            print("✅ Modele charge depuis le fichier sauvegarde")
            print(f"   Modele entraîne: {fraud_detector.is_fitted}")
            print(f"   Cache scores: {fraud_detector._cached_scores is not None}")
            if fraud_detector._cached_scores is not None:
                print(f"   Taille cache: {len(fraud_detector._cached_scores)}")

            if fraud_detector.version_manager.get_active_version() is None:
                version_num = fraud_detector.version_manager.get_next_version_number()
                version_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "models",
                    "versions",
                    f"v{version_num}_model.pkl",
                )
                fraud_detector.save(version_path)
                metrics = fraud_detector.get_current_version_metrics()
                fraud_detector.version_manager.save_version(
                    version_num,
                    version_path,
                    metrics,
                    notes="Version initiale non supervisee",
                )
                fraud_detector.version_manager.set_active_version(version_num)
                print(f"✅ Version initiale v{version_num} creee et activee")
        else:
            print("📈 Aucun modele sauvegarde trouve --- entraînement d'un nouveau modele")
            fraud_detector.fit(sinistres_df, contrats_df, tiers_df, geocoder=geocoder)
            version_num = fraud_detector.version_manager.get_next_version_number()
            version_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "models",
                "versions",
                f"v{version_num}_model.pkl",
            )
            fraud_detector.save(version_path)
            metrics = fraud_detector.get_current_version_metrics()
            fraud_detector.version_manager.save_version(
                version_num,
                version_path,
                metrics,
                notes="Version initiale non supervisee",
            )
            fraud_detector.version_manager.set_active_version(version_num)
            fraud_detector.save(model_path)

        if geocoder is not None:
            geocoder.save_cache()

        validation = fraud_detector.validate_scoring()
        print(f"\n📊 VALIDATION DU SCORING :")
        print(f"   Score moyen    : {validation.get('score_moyen', 0):.1f}/100  (cible : 35-45)")
        print(f"   % Frauduleux   : {validation.get('pct_frauduleux', 0):.2f}%  (cible : 5-15%)")
        print(f"   % Suspects     : {validation.get('pct_suspect', 0):.2f}%")
        print(f"   % Normaux      : {validation.get('pct_normal', 0):.2f}%")

    except Exception as e:
        import traceback
        print(f"❌ Erreur ML Excel : {e}")
        traceback.print_exc()

    # ── Neo4j : initialisation mais PAS de pipeline batch ───────────────────
    if NEO4J_AVAILABLE:
        try:
            neo4j_loader = PFE2026Neo4jLoader()
            if neo4j_loader.driver:
                community_detector = CommunityDetector(neo4j_loader.driver, neo4j_loader.database)
                print("✅ Neo4j AuraDB Community Detector pret")
                # Plus d'appel a run_neo4j_pipeline() -> scoring sinistre par sinistre
            else:
                print("⚠️ Connexion Neo4j echouee")
        except Exception as e:
            import traceback
            print(f"❌ Erreur Neo4j startup : {e}")
            traceback.print_exc()
    else:
        print("⚠️ Modules Neo4j non importes")

    # ─── STOCKAGE DANS app.state POUR PARTAGE AVEC sinistre_router ─────────
    app.state.fraud_detector = fraud_detector
    app.state.neo4j_loader = neo4j_loader
    app.state.community_detector = community_detector
    app.state.training_status = _initialize_training_status()

    print("✅ SYSTÈME PRÊT --- http://127.0.0.1:8000/docs")


@app.on_event("shutdown")
async def shutdown():
    if neo4j_loader:
        neo4j_loader.close()
    if geocoder is not None:
        geocoder.save_cache()


def _check_model():
    detector = getattr(app.state, "fraud_detector", fraud_detector)
    if detector is None or not getattr(detector, "is_fitted", False):
        raise HTTPException(503, "Modele non entraîne --- demarrage en cours")
    return detector


# ═════════════════════════════════════════════════════════════════════════════
# ROUTES API (inchangees)
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    return JSONResponse({
        "message": "API Detection Fraude v3.14",
        "status": "operationnel" if fraud_detector else "en_attente",
        "neo4j": "connecte" if community_detector else "non_connecte",
        "geocoder": "actif" if geocoder else "inactif",
        "seuils": {
            "normal":     f"<{SEUIL_SUSPECT_MIN}",
            "suspect":    f"{SEUIL_SUSPECT_MIN}-{SEUIL_FRAUDULEUX}",
            "frauduleux": f">{SEUIL_FRAUDULEUX}",
        },
        "version": "3.14",
    })


@app.get("/health")
async def health():
    return JSONResponse({
        "status":            "healthy" if fraud_detector else "no_data",
        "sinistres_count":   len(sinistres_df) if sinistres_df is not None else 0,
        "neo4j_available":   community_detector is not None,
        "geocoder_active":   geocoder is not None,
        "seuil_frauduleux":  SEUIL_FRAUDULEUX,
        "seuil_suspect_min": SEUIL_SUSPECT_MIN,
        "seuil_normal_max":  SEUIL_NORMAL_MAX,
        "version":           "3.14",
    })


@app.get("/sinistres")
async def list_sinistres(page: int = 1, limit: int = 50):
    if sinistres_df is None:
        raise HTTPException(404, "Donnees non chargees")
    total = len(sinistres_df)
    start = (page - 1) * limit
    end   = min(start + limit, total)
    if start >= total:
        start = max(0, total - limit)
        end   = total
    items = sinistres_df.iloc[start:end].to_dict("records")
    for i, s in enumerate(items):
        s["index"] = start + i
        for k in ["DATE_SURVENANCE", "DATE_DECLARATION"]:
            if k in s and pd.notna(s.get(k)):
                s[k] = str(s[k])
        for k, v in list(s.items()):
            s[k] = clean_for_json(v)
    return {
        "total": total, "page": page, "limit": limit,
        "total_pages": (total + limit - 1) // limit,
        "sinistres": items,
    }


@app.get("/sinistres/{sinistre_id}")
async def get_sinistre(sinistre_id: int):
    if sinistres_df is None:
        raise HTTPException(404)
    if sinistre_id < 0 or sinistre_id >= len(sinistres_df):
        raise HTTPException(404, f"Sinistre {sinistre_id} non trouve")
    row = sinistres_df.iloc[sinistre_id].to_dict()
    for k, v in row.items():
        if isinstance(v, pd.Timestamp):
            row[k] = str(v)
        row[k] = clean_for_json(v)
    return row


@app.get("/predict/{sinistre_id}")
async def predict(sinistre_id: int):
    _check_model()
    if sinistre_id < 0 or sinistre_id >= len(sinistres_df):
        raise HTTPException(404)
    return fraud_detector.predict(sinistre_id, sinistres_df, contrats_df, tiers_df)


@app.post("/predict/batch")
async def predict_batch(sinistre_ids: List[int]):
    _check_model()
    results = []
    for idx in sinistre_ids:
        if sinistres_df is not None and 0 <= idx < len(sinistres_df):
            try:
                results.append(fraud_detector.predict(idx, sinistres_df, contrats_df, tiers_df))
            except Exception as e:
                print(f"Erreur sinistre {idx}: {e}")
    return {
        "total_demandes": len(sinistre_ids),
        "total_traites":  len(results),
        "resultats":      results,
    }


@app.get("/frauds")
async def get_fraudulent_sinistres():
    _check_model()
    if sinistres_df is None:
        raise HTTPException(404)

    cached_scores    = fraud_detector._cached_scores
    results          = []
    frauduleux_count = 0
    suspect_count    = 0

    for idx in range(len(sinistres_df)):
        score = float(cached_scores[idx])
        if score < SEUIL_SUSPECT_MIN:
            continue
        try:
            gs  = fraud_detector.get_cached_compact(idx)
            row = sinistres_df.iloc[idx]
            results.append({
                "index":           idx,
                "NUM_SINISTRE":    safe_str(row.get("NUM_SINISTRE")),
                "NUM_CONTRAT":     safe_str(row.get("NUM_CONTRAT")),
                "IMMATRICULATION": safe_str(row.get("IMMATRICULATION")),
                "DATE_SURVENANCE": fmt_date(row.get("DATE_SURVENANCE")),
                "TOTALREGLEMENT":  safe_float(row.get("TOTALREGLEMENT", 0)),
                "STATUS":          safe_str(row.get("STATUS")),
                "CDL":             safe_str(row.get("CDL")),
                "score_suspicion": score,
                "statut_fraude":   gs["statut"],
                "niveau_risque":   gs["niveau"],
            })
            if score > SEUIL_FRAUDULEUX:
                frauduleux_count += 1
            else:
                suspect_count += 1
        except Exception:
            continue

    results.sort(key=lambda x: x["score_suspicion"], reverse=True)
    return {
        "total":             len(sinistres_df),
        "frauduleux_count":  frauduleux_count,
        "suspect_count":     suspect_count,
        "seuil_frauduleux":  SEUIL_FRAUDULEUX,
        "seuil_suspect_min": SEUIL_SUSPECT_MIN,
        "sinistres":         results[:2000],
    }


@app.get("/statistics")
async def get_statistics():
    _check_model()
    if sinistres_df is None:
        raise HTTPException(404)

    cached_scores    = fraud_detector._cached_scores
    total            = len(cached_scores)
    frauduleux_count = int(np.sum(cached_scores > SEUIL_FRAUDULEUX))
    suspect_count    = int(np.sum((cached_scores >= SEUIL_SUSPECT_MIN) & (cached_scores <= SEUIL_FRAUDULEUX)))
    normal_count     = int(np.sum(cached_scores < SEUIL_SUSPECT_MIN))
    score_moyen      = float(np.mean(cached_scores))

    return JSONResponse(content={
        "total_sinistres":   total,
        "score_moyen":       round(score_moyen, 2),
        "score_median":      round(float(np.median(cached_scores)), 2),
        "score_std":         round(float(np.std(cached_scores)), 2),
        "score_min":         round(float(np.min(cached_scores)), 2),
        "score_max":         round(float(np.max(cached_scores)), 2),
        "seuil_frauduleux":  SEUIL_FRAUDULEUX,
        "seuil_suspect_min": SEUIL_SUSPECT_MIN,
        "seuil_normal_max":  SEUIL_NORMAL_MAX,
        "distribution": {
            "frauduleux": {"count": frauduleux_count, "percentage": round(frauduleux_count / total * 100, 2)},
            "suspect":    {"count": suspect_count,    "percentage": round(suspect_count    / total * 100, 2)},
            "normal":     {"count": normal_count,     "percentage": round(normal_count     / total * 100, 2)},
        },
        "percentiles": {
            "p90": round(float(np.percentile(cached_scores, 90)), 2),
            "p95": round(float(np.percentile(cached_scores, 95)), 2),
            "p98": round(float(np.percentile(cached_scores, 98)), 2),
            "p99": round(float(np.percentile(cached_scores, 99)), 2),
        },
        "seuil_anomalie": round(float(np.percentile(cached_scores, 98)), 2),
        "version":        "3.14",
    })


@app.get("/statistics/evolution")
async def get_evolution_statistics():
    if sinistres_df is None:
        raise HTTPException(404)
    df = sinistres_df.copy()
    df["DATE_SURVENANCE"] = pd.to_datetime(df["DATE_SURVENANCE"], errors="coerce")
    df["ANNEE"] = df["DATE_SURVENANCE"].dt.year
    df = df[df["ANNEE"].notna() & (df["ANNEE"] >= 2000) & (df["ANNEE"] <= 2030)]
    df["ANNEE"] = df["ANNEE"].astype(int)
    ev = (
        df.groupby("ANNEE")
        .agg(
            nb_sinistres=("NUM_SINISTRE", "count"),
            montant_total=("TOTALREGLEMENT", "sum"),
            montant_moyen=("TOTALREGLEMENT", "mean"),
        )
        .reset_index()
        .sort_values("ANNEE")
    )
    return [
        {
            "ANNEE":         int(r["ANNEE"]),
            "nb_sinistres":  int(r["nb_sinistres"]),
            "montant_total": safe_float(r["montant_total"]),
            "montant_moyen": safe_float(r["montant_moyen"]),
        }
        for _, r in ev.iterrows()
    ]


@app.get("/statistics/global-enriched")
async def get_global_enriched_statistics():
    if sinistres_df is None:
        raise HTTPException(404)
    df     = sinistres_df.copy()
    result = {}

    if "TYPE_SINISTRE" in df.columns:
        ts = df["TYPE_SINISTRE"].value_counts().head(10)
        result["sinistres_par_type"] = [
            {"type": str(k), "count": int(v), "pct": round(v / len(df) * 100, 2)}
            for k, v in ts.items()
        ]

    if "STATUS" in df.columns:
        ss = df["STATUS"].value_counts()
        result["sinistres_par_statut"] = [
            {"statut": str(k), "count": int(v), "pct": round(v / len(df) * 100, 2)}
            for k, v in ss.items()
        ]

    if "CDL" in df.columns:
        cdl = df["CDL"].value_counts().head(10)
        result["sinistres_par_cdl"] = [{"cdl": str(k), "count": int(v)} for k, v in cdl.items()]

    if "TOTALREGLEMENT" in df.columns:
        m = df["TOTALREGLEMENT"].fillna(0)
        result["montants"] = {
            "total":   round(float(m.sum()), 2),
            "moyen":   round(float(m.mean()), 2),
            "median":  round(float(m.median()), 2),
            "max":     round(float(m.max()), 2),
            "min":     round(float(m[m > 0].min()), 2) if (m > 0).any() else 0,
            "nb_nuls": int((m == 0).sum()),
        }

    if "ACTEUR_IMPLIQUE" in df.columns:
        ai = df["ACTEUR_IMPLIQUE"].value_counts().head(10)
        result["acteurs_impliques"] = [{"acteur": str(k), "count": int(v)} for k, v in ai.items()]

    if "DATE_SURVENANCE" in df.columns and "DATE_DECLARATION" in df.columns:
        d_surv = pd.to_datetime(df["DATE_SURVENANCE"], errors="coerce")
        d_decl = pd.to_datetime(df["DATE_DECLARATION"], errors="coerce")
        delta  = (d_decl - d_surv).dt.days.dropna()
        if len(delta) > 0:
            result["delais_declaration"] = {
                "moyen_jours":        round(float(delta.mean()), 1),
                "median_jours":       round(float(delta.median()), 1),
                "tardifs_30j":        int((delta > 30).sum()),
                "tres_tardifs_90j":   int((delta > 90).sum()),
                "ultra_tardifs_365j": int((delta > 365).sum()),
                "pct_tardifs":        round((delta > 30).sum() / len(delta) * 100, 2),
            }

    if contrats_df is not None:
        if "MARQUE" in contrats_df.columns:
            mk = contrats_df["MARQUE"].dropna().value_counts().head(10)
            result["top_marques"] = [{"marque": str(k), "count": int(v)} for k, v in mk.items()]
        if "PRODUIT" in contrats_df.columns:
            prod = contrats_df["PRODUIT"].dropna().value_counts().head(10)
            result["top_produits"] = [{"produit": str(k), "count": int(v)} for k, v in prod.items()]
        if "USAGE" in contrats_df.columns:
            usage = contrats_df["USAGE"].dropna().value_counts().head(10)
            result["usages"] = [
                {"usage": str(k), "count": int(v), "pct": round(v / len(contrats_df) * 100, 2)}
                for k, v in usage.items()
            ]

    result["total_sinistres_exact"] = len(df)
    return result


@app.get("/statistics/top-garages")
async def get_top_garages(limit: int = 10):
    if sinistres_df is None or "GARAGES" not in sinistres_df.columns:
        return []
    df = sinistres_df[sinistres_df["GARAGES"].notna()]
    df = df[~df["GARAGES"].astype(str).str.lower().isin(["inconnu", "nan", "", "none"])]
    if len(df) == 0:
        return []
    stats = (
        df.groupby("GARAGES")
        .agg(
            nb_sinistres=("NUM_SINISTRE", "count"),
            montant_total=("TOTALREGLEMENT", "sum"),
            montant_moyen=("TOTALREGLEMENT", "mean"),
        )
        .reset_index()
        .sort_values("nb_sinistres", ascending=False)
        .head(limit)
    )
    return stats.to_dict("records")


@app.get("/statistics/top-points-vente")
async def get_top_points_vente(limit: int = 10):
    if contrats_df is None or sinistres_df is None:
        return []
    try:
        if "POINT_VENTE" not in contrats_df.columns or "NUM_CONTRAT" not in sinistres_df.columns:
            return []
        df_merged = sinistres_df.merge(
            contrats_df[["NUMERO_POLICE", "POINT_VENTE"]],
            left_on="NUM_CONTRAT", right_on="NUMERO_POLICE", how="left"
        )
        df_valid = df_merged[df_merged["POINT_VENTE"].notna()]
        df_valid = df_valid[~df_valid["POINT_VENTE"].astype(str).str.lower().isin(["inconnu", "nan", "", "none"])]
        if len(df_valid) == 0:
            return []
        stats = (
            df_valid.groupby("POINT_VENTE")
            .agg(
                nb_sinistres=("NUM_SINISTRE", "count"),
                montant_total=("TOTALREGLEMENT", "sum"),
                montant_moyen=("TOTALREGLEMENT", "mean"),
            )
            .reset_index()
            .rename(columns={"POINT_VENTE": "point_vente"})
            .sort_values("nb_sinistres", ascending=False)
            .head(limit)
        )
        return stats.to_dict("records")
    except Exception as e:
        print(f"⚠️ Erreur top-points-vente: {e}")
        return []


@app.get("/statistics/top-experts")
async def get_top_experts(limit: int = 10):
    if sinistres_df is None or "EXPERT_STAREX" not in sinistres_df.columns:
        return []
    df = sinistres_df[sinistres_df["EXPERT_STAREX"].notna()]
    df = df[~df["EXPERT_STAREX"].astype(str).str.lower().isin(["inconnu", "nan", "", "none"])]
    if len(df) == 0:
        return []
    stats = (
        df.groupby("EXPERT_STAREX")
        .agg(
            nb_sinistres=("NUM_SINISTRE", "count"),
            montant_total=("TOTALREGLEMENT", "sum"),
            montant_moyen=("TOTALREGLEMENT", "mean"),
        )
        .reset_index()
        .sort_values("nb_sinistres", ascending=False)
        .head(limit)
    )
    return stats.to_dict("records")


@app.get("/indicators")
async def get_indicators():
    _check_model()
    indicators = fraud_detector.get_human_readable_indicators(10)
    formatted  = [
        {
            "nom":                      i["nom"],
            "pourcentage_contribution": i["pourcentage_contribution"],
            "description":              i.get("description", ""),
        }
        for i in indicators
    ]
    return {
        "total_indicateurs": len(formatted),
        "indicateurs":       formatted,
        "seuils":            {"frauduleux": SEUIL_FRAUDULEUX, "suspect_min": SEUIL_SUSPECT_MIN},
        "version":           "3.14",
    }


@app.get("/scoring/groups")
async def get_scoring_groups():
    return {
        "version": "3.14",
        "groups": {
            "financial": {"max_score": GROUP_CAPS["financial"], "label": "Financier"},
            "temporal":  {"max_score": GROUP_CAPS["temporal"],  "label": "Temporel"},
            "frequency": {"max_score": GROUP_CAPS["frequency"], "label": "Frequence"},
            "network":   {"max_score": GROUP_CAPS["network"],   "label": "Reseau / Collusion"},
            "driver":    {"max_score": GROUP_CAPS["driver"],    "label": "Conducteur / Mobilite"},
            "profile":   {"max_score": GROUP_CAPS["profile"],   "label": "Profil Assure"},
        },
        "thresholds": {
            "normal":     {"min": 0,                "max": SEUIL_NORMAL_MAX,         "label": "NON FRAUDULEUX"},
            "suspect":    {"min": SEUIL_SUSPECT_MIN, "max": SEUIL_FRAUDULEUX,       "label": "SUSPECT"},
            "fraudulent": {"min": SEUIL_FRAUDULEUX,  "max": 100,                     "label": "FRAUDULEUX"},
        },
        "nouveaux_triggers_v314": [
            "ratio_montant_prime / montant_10x_prime",
            "sinistre_heure_nuit",
            "sinistre_weekend",
            "avenant_proche_sinistre_30j",
        ],
        "note": "v3.14 --- poids recalibres, score moyen cible 35-45",
    }


@app.get("/scoring/validate")
async def validate_scoring():
    _check_model()
    return fraud_detector.validate_scoring()


@app.get("/scoring/temporal-stability")
async def scoring_temporal_stability(recent_ratio: float = 0.2):
    _check_model()
    recent_ratio = min(max(recent_ratio, 0.05), 0.5)
    return fraud_detector.evaluate_temporal_stability(recent_ratio=recent_ratio)


@app.get("/model/info")
async def model_info():
    _check_model()
    info = fraud_detector.get_info()
    info["neo4j_available"] = community_detector is not None
    info["geocoder_active"] = geocoder is not None
    return info


@app.get("/model/versions")
async def model_versions():
    detector = _check_model()

    cached_scores = getattr(detector, "_cached_scores", None)
    if cached_scores is None:
        current_stats = None
    else:
        total = len(cached_scores)
        if total > 0:
            frauduleux_count = int(np.sum(cached_scores > SEUIL_FRAUDULEUX))
            suspect_count = int(np.sum((cached_scores >= SEUIL_SUSPECT_MIN) & (cached_scores <= SEUIL_FRAUDULEUX)))
            normal_count = int(np.sum(cached_scores < SEUIL_SUSPECT_MIN))
            score_moyen = float(np.mean(cached_scores))

            current_stats = {
                "score_moyen": round(score_moyen, 1),
                "frauduleux_percent": round(frauduleux_count / total * 100, 1),
                "suspects_percent": round(suspect_count / total * 100, 1),
                "normaux_percent": round(normal_count / total * 100, 1),
            }
        else:
            current_stats = None

    return {
        "active_version": detector.version_manager.get_active_version(),
        "versions": detector.list_all_versions(),
        "current_stats": current_stats,
    }


@app.get("/model/versions/compare")
async def compare_model_versions(v1: int = Query(...), v2: int = Query(...)):
    _check_model()
    return fraud_detector.compare_versions(v1, v2)


@app.get("/model/versions/{version_num}")
async def model_version_detail(version_num: int):
    _check_model()
    info = fraud_detector.version_manager.get_version_info(version_num)
    if not info:
        raise HTTPException(404, f"Version {version_num} non trouvee")
    return info


@app.post("/model/versions/{version_num}/activate")
async def activate_model_version(version_num: int):
    _check_model()
    if not fraud_detector.set_active_version(version_num):
        raise HTTPException(404, f"Version {version_num} non trouvee ou impossible a activer")
    return {
        "status": "active",
        "active_version": version_num,
    }


@app.delete("/model/versions/{version_num}")
async def delete_model_version(version_num: int):
    _check_model()
    if not fraud_detector.delete_version(version_num):
        raise HTTPException(404, f"Version {version_num} non trouvee, non supprimable (version active?) ou erreur de suppression")
    return {
        "status": "deleted",
        "deleted_version": version_num,
        "message": f"Version {version_num} supprimee avec succes"
    }


@app.post("/model/train")
async def retrain_model(payload: RetrainRequest, background_tasks: BackgroundTasks):
    _check_model()
    current_status = _get_training_status()
    if current_status["status"] == "running":
        raise HTTPException(409, "Un entraînement est deja en cours")

    job_id = str(uuid4())
    _set_training_status(job_id, "running", 0, "Demarrage du reentraînement...", None)
    background_tasks.add_task(_run_training_job, job_id, payload)

    return {
        "status": "started",
        "job_id": job_id,
        "message": "Reentraînement lance en arriere-plan",
        "progress_url": "/model/train/status",
    }


@app.get("/model/train/status")
async def train_status():
    return _get_training_status()


# ════════════════════════════════════════════════════════════════════════════
# CONFIGURATION DYNAMIQUE DU SCORING
# ════════════════════════════════════════════════════════════════════════════

@app.get("/model/current-config")
async def get_current_config():
    """
    Retourne la configuration actuelle du scoring:
    - group_weights: poids par groupe (somme = 100)
    - thresholds: seuils de classification
    - indicator_weights: poids par indicateur (si personnalises)
    """
    _check_model()
    config = fraud_detector.get_current_config()
    return {
        "success": True,
        "config": config,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/model/reconfigure")
async def reconfigure_scoring(
    payload: dict,
    background_tasks: BackgroundTasks
):
    """
    Reconfigure les seuils de scoring.
    - Les modifications de poids (group_weights, indicator_weights) déclenchent un réentraînement du modèle.
    - Les modifications de seuils peuvent être appliquées directement via un re-score.

    Body attendu:
    {
        "group_weights": {"financial": 30, "temporal": 30, ...},  // optionnel
        "indicator_weights": {"montant_vs_prime": 5.0, ...},    // optionnel
        "thresholds": {"normal_max": 50.0, "suspect_min": 50.0, "frauduleux": 70.0},  // optionnel
        "notes": "Raison de la modification"
    }

    Retourne:
    {
        "success": bool,
        "version": "1.1",
        "message": string,
        "job_id": string,
        "config_snapshot": {...},
        "progress_url": "/model/train/status" or "/model/rescore/status?job_id=..."
    }
    """
    _check_model()

    # 1. Valider et appliquer la configuration
    result = fraud_detector.update_config(payload)

    if not result["success"]:
        raise HTTPException(400, {
            "error": "Configuration invalide",
            "details": result["errors"]
        })

    # 2. Mettre a jour les seuils globaux immediatement pour les endpoints de stats
    global SEUIL_NORMAL_MAX, SEUIL_SUSPECT_MIN, SEUIL_FRAUDULEUX
    SEUIL_NORMAL_MAX = fraud_detector.config.thresholds["normal_max"]
    SEUIL_SUSPECT_MIN = fraud_detector.config.thresholds["suspect_min"]
    SEUIL_FRAUDULEUX = fraud_detector.config.thresholds["frauduleux"]

    # 3. Si les poids ont change, lancer un ré-entraînement complet en arrière-plan
    weight_change = bool(payload.get("group_weights")) or bool(payload.get("indicator_weights"))
    job_id = str(uuid4())
    if weight_change:
        _set_training_status(job_id, "running", 0, "Modification des poids détectée, lancement du ré-entraînement...", None)
        retrain_payload = RetrainRequest(notes="Ré-entraînement suite à modification des poids du scoring")
        background_tasks.add_task(_run_training_job, job_id, retrain_payload)
        progress_url = "/model/train/status"
        message = "Modification des poids détectée, ré-entraînement du modèle lancé en arrière-plan"
    else:
        _set_training_status(job_id, "running", 0, "Re-scoring avec nouvelle configuration...", None)
        background_tasks.add_task(_run_rescoring_and_save_version, job_id, result["config_snapshot"])
        progress_url = f"/model/rescore/status?job_id={job_id}"
        message = "Configuration appliquee, re-scoring et sauvegarde en arrière-plan"

    return {
        "success": True,
        "version": result["config_snapshot"].get("version", "1.0"),
        "message": message,
        "job_id": job_id,
        "config_snapshot": result["config_snapshot"],
        "progress_url": progress_url
    }


@app.get("/model/rescore/status")
async def rescore_status(job_id: str = Query(...)):
    """Statut du job de re-scoring."""
    status = _get_training_status()
    # Simplification: on reutilise le meme systeme que training
    return status


# ════════════════════════════════════════════════════════════════════════════
# UPLOAD DE NOUVELLES DONNÉES EXCEL
# ════════════════════════════════════════════════════════════════════════════

@app.post("/model/upload-data")
async def upload_data(files: List[UploadFile] = File(...)):
    """
    Upload de nouveaux fichiers Excel (sinistres, contrats, tiers).

    Args:
        files: Liste de 2 ou 3 fichiers (sinistres.xlsx, contrats.xlsx, tiers.xlsx)

    Retourne:
        {
            "success": bool,
            "files_received": ["sinistres.xlsx", ...],
            "saved_to": ["data/sinistres_20260511_143022.xlsx", ...],
            "next_step": "POST /model/train pour re-entraîner"
        }
    """
    global sinistres_df, contrats_df, tiers_df

    _check_model()
    _check_model()

    if len(files) < 2 or len(files) > 3:
        raise HTTPException(400, "4-6 fichiers attendus: sinistres, contrats, tiers (optionnel)")

    # 1. Valider les noms de fichiers
    expected_names = {"sinistres", "contrats", "tiers"}
    uploaded_names = set()
    saved_paths = []

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)

    for file in files:
        name_lower = file.filename.lower()
        # Trouver a quel fichier ca correspond
        matched = None
        for expected in expected_names:
            if expected in name_lower:
                matched = expected
                break
        if not matched:
            raise HTTPException(400, f"Fichier non reconnu: {file.filename}. Attendus: sinistres, contrats, tiers")

        uploaded_names.add(matched)

        # 2. Sauvegarder avec timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = os.path.splitext(file.filename)[1] or ".xlsx"
        save_name = f"{matched}_{timestamp}{ext}"
        save_path = os.path.join(data_dir, save_name)

        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)

        # Sauvegarder également sous le nom fixe attendu par DataLoader
        fixed_path = os.path.join(data_dir, f"{matched}.xlsx")
        with open(fixed_path, "wb") as f_fixed:
            f_fixed.write(content)

        saved_paths.append(save_path)
        print(f"✅ Fichier sauvegarde: {save_path}")
        print(f"✅ Fichier fixe mis a jour: {fixed_path}")

    # 3. Recharger DataLoader avec les nouveaux fichiers uploadés
    data_loader.load_all(base_path=data_dir)
    sinistres_df = data_loader.get_sinistres()
    contrats_df = data_loader.get_contrats()
    tiers_df = data_loader.get_tiers()

    print(
        f"✅ Donnees rechargees apres upload : "
        f"Sinistres={len(sinistres_df) if sinistres_df is not None else 0}, "
        f"Contrats={len(contrats_df) if contrats_df is not None else 0}, "
        f"Tiers={len(tiers_df) if tiers_df is not None else 0}"
    )

    return {
        "success": True,
        "files_received": list(uploaded_names),
        "saved_to": saved_paths,
        "note": "Fichiers uploades et donnes rechargees. Lancez POST /model/train pour ré-entraîner.",
        "next_step": "POST /model/train"
    }


# ════════════════════════════════════════════════════════════════════════════
# COMPARAISON DE CONFIGURATIONS
# ════════════════════════════════════════════════════════════════════════════

@app.get("/model/config-history")
async def get_config_history(limit: int = 10):
    """Historique des configurations de scoring."""
    manager = ScoringConfigManager()
    history = manager.get_history(limit)
    return {
        "success": True,
        "history": history,
        "count": len(history)
    }


@app.get("/model/labels/preview")
def labels_preview(sample: int = 10):
    """
    Aperçu des labels supervisés disponibles ou générés automatiquement.

    Retourne:
      - label_source: 'manual'|'auto'
      - label_column: nom de la colonne utilisée
      - summary: counts par valeur
      - samples: échantillon des premières lignes avec le label
    """
    _check_model()
    if sinistres_df is None:
        raise HTTPException(400, "Données sinistres non disponibles. Upload des fichiers requis.")

    # 1) Vérifier présence d'un label manuel
    try:
        col, explicit = _find_supervised_label_column(sinistres_df)
    except Exception as e:
        raise HTTPException(500, f"Erreur lors de la détection des labels: {e}")

    if explicit and col is not None:
        summary = sinistres_df[col].value_counts().to_dict()
        samples = sinistres_df[[col]].head(sample).to_dict(orient='records')
        return {
            "success": True,
            "label_source": "manual",
            "label_column": col,
            "summary": summary,
            "samples": samples,
        }

    # 2) Pas de label manuel -> générer un aperçu sans modifier la table principale
    tmp = sinistres_df.copy()
    detector = getattr(app.state, "fraud_detector", fraud_detector)
    try:
        label_col = _ensure_auto_is_fraud_label(detector, tmp, contrats_df, tiers_df, 1.0)
    except Exception as e:
        raise HTTPException(500, f"Impossible de générer labels auto: {e}")

    summary = tmp[label_col].value_counts().to_dict()
    samples = tmp[[label_col]].head(sample).to_dict(orient='records')
    return {
        "success": True,
        "label_source": "auto",
        "label_column": label_col,
        "summary": summary,
        "samples": samples,
    }


@app.post("/data/reload")
def reload_data():
    """Force le rechargement des fichiers dans `backend/data` en appelant `DataLoader.load_all()`.

    Retourne l'état du chargement et les counts de lignes si succès.
    """
    try:
        ok = data_loader.load_all()
        # Mettre à jour les DataFrames en mémoire
        global sinistres_df, contrats_df, tiers_df
        sinistres_df = data_loader.get_sinistres()
        contrats_df = data_loader.get_contrats()
        tiers_df = data_loader.get_tiers()

        return {
            "success": bool(ok),
            "message": "Données rechargées" if ok else "Échec du rechargement",
            "stats": data_loader.stats,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/model/config-rollback")
async def rollback_config(version: str):
    """
    Restaure une configuration precedente.

    Args:
        version: Numero de version (ex: "1.2")
    """
    _check_model()

    manager = fraud_detector.config_manager
    success = manager.rollback(version)

    if not success:
        raise HTTPException(404, f"Version {version} non trouvee")

    # Appliquer la configuration restauree a fraud_detector
    fraud_detector.config = manager.current
    fraud_detector.seuil_normal_max  = manager.current.thresholds["normal_max"]
    fraud_detector.seuil_suspect_min = manager.current.thresholds["suspect_min"]
    fraud_detector.seuil_frauduleux  = manager.current.thresholds["frauduleux"]
    global SEUIL_NORMAL_MAX, SEUIL_SUSPECT_MIN, SEUIL_FRAUDULEUX
    SEUIL_NORMAL_MAX = manager.current.thresholds["normal_max"]
    SEUIL_SUSPECT_MIN = manager.current.thresholds["suspect_min"]
    SEUIL_FRAUDULEUX = manager.current.thresholds["frauduleux"]

    return {
        "success": True,
        "message": f"Configuration restauree vers v{version}",
        "config": manager.to_dict()
    }


# ════════════════════════════════════════════════════════════════════════════
# PRÉVISUALISATION AVANT APPLICATION
# ════════════════════════════════════════════════════════════════════════════

@app.post("/model/preview-reconfigure")
async def preview_reconfigure(payload: dict):
    """
    Prend une configuration et montre l'impact sur un echantillon de sinistres
    SANS appliquer les modifications.

    Retourne:
    - Distribution avant/apres
    - Nombre de sinistres qui changent de categorie
    - Delta moyen de score
    """
    _check_model()

    # 1. Valider la config (sans appliquer)
    from ml.scoring_config import ScoringConfig
    new_config = ScoringConfig(**payload)
    validation = ScoringConfigManager().validate(new_config)

    if not validation["valid"]:
        raise HTTPException(400, {"errors": validation["errors"]})

    # 2. Prendre un echantillon de 100 sinistres
    sample_size = min(100, len(fraud_detector._cached_scores))
    indices = np.random.choice(len(fraud_detector._cached_scores), sample_size, replace=False)

    before_scores = []
    after_scores = []
    before_status = []
    after_status = []

    for idx in indices:
        # Score avant (deja en cache)
        before = float(fraud_detector._cached_scores[idx])
        before_scores.append(before)
        before_status.append(fraud_detector._status_from_score(before)[0])

        # Simuler score apres avec nouvelle config
        # On ne peut pas facilement sans recalculer le grouped_score
        # On approxime en re-callant calculate_grouped_score() avec les nouveaux poids
        # Mais cela necessite d'avoir les features brutes
        # Pour le POC, on peut simplement montrer l'impact des seuils
        after = before  # À implementer: vrai re-scoring simule
        after_scores.append(after)
        after_status.append(fraud_detector._status_from_score(after)[0])

    # 3. Comparaison
    changes = sum(1 for b, a in zip(before_status, after_status) if b != a)

    return {
        "sample_size": sample_size,
        "distribution_before": {
            "normal": before_status.count("normal"),
            "suspect": before_status.count("suspect"),
            "frauduleux": before_status.count("frauduleux"),
        },
        "distribution_after": {
            "normal": after_status.count("normal"),
            "suspect": after_status.count("suspect"),
            "frauduleux": after_status.count("frauduleux"),
        },
        "crossover_count": changes,
        "mean_delta": float(np.mean([a - b for a, b in zip(after_scores, before_scores)])),
        "note": "Preview simplifiee (score identique). À implementer: calcul reel avec nouvelles features."
    }


# ════════════════════════════════════════════════════════════════════════════
# HELPER: RE-SCORING ASYNCHRONE
# ════════════════════════════════════════════════════════════════════════════

async def _run_rescoring_job(job_id: str, new_config: dict):
    """
    Re-score tous les sinistres avec la nouvelle configuration.

    Étapes:
    1. Met a jour la config du fraud_detector
    2. Pour chaque sinistre: calcule grouped_score + nouveau score final
    3. Met a jour le cache
    4. Recalcule les statistiques globales
    5. Marque le job comme termine
    """
    try:
        _set_training_status(job_id, "running", 10, "Application de la nouvelle configuration...", None)

        # Recharger la config depuis le manager (deja fait dans update_config)
        # On s'assure que fraud_detector a la bonne config
        fraud_detector.config = fraud_detector.config_manager.current
        fraud_detector.seuil_normal_max  = fraud_detector.config.thresholds["normal_max"]
        fraud_detector.seuil_suspect_min = fraud_detector.config.thresholds["suspect_min"]
        fraud_detector.seuil_frauduleux  = fraud_detector.config.thresholds["frauduleux"]
        global SEUIL_NORMAL_MAX, SEUIL_SUSPECT_MIN, SEUIL_FRAUDULEUX
        SEUIL_NORMAL_MAX = fraud_detector.config.thresholds["normal_max"]
        SEUIL_SUSPECT_MIN = fraud_detector.config.thresholds["suspect_min"]
        SEUIL_FRAUDULEUX = fraud_detector.config.thresholds["frauduleux"]

        n = len(fraud_detector._cached_scores)
        _set_training_status(job_id, "running", 20, f"Re-scoring de {n} sinistres...", None)

        # Recalculer tous les scores
        new_scores = np.zeros(n)
        compact_scores = []

        for i in range(n):
            if i % 1000 == 0 and i > 0:
                pct = int(i / n * 100)
                _set_training_status(job_id, "running", 20 + int(pct * 0.7), f"Re-scoring: {i}/{n}", None)

            # Recalculer grouped_score avec nouvelle config
            gs = fraud_detector.calculate_grouped_score(i)

            # ML score reste le meme (pas de re-entraînement)
            if_score  = fraud_detector._data_cache["scores_if"][i]
            lof_score = fraud_detector._data_cache["scores_lof"][i]
            ee_score  = fraud_detector._data_cache["scores_ee"][i]

            if len(fraud_detector._active_models) == 3:
                ml_score = round((if_score + lof_score + ee_score) / 3.0, 1)
            elif len(fraud_detector._active_models) == 2:
                if "if" in fraud_detector._active_models and "lof" in fraud_detector._active_models:
                    ml_score = round((if_score + lof_score) / 2.0, 1)
                else:
                    ml_score = round((if_score + ee_score) / 2.0, 1)
            else:
                ml_score = round(if_score, 1)

            # Nouveau score final (heuristic only, pas de ML weight par defaut)
            final_score = round(min(100.0, gs["score_brut"]), 1)
            statut, niveau = fraud_detector._status_from_score(final_score)

            new_scores[i] = final_score
            compact_scores.append({
                "total": final_score,
                "heuristic_total": round(min(100.0, gs["score_brut"]), 1),
                "score_brut": gs["score_brut"],
                "ml_score": ml_score,
                "statut": statut,
                "niveau": niveau,
                "triggers": gs["all_triggers"],
                "scores_groupes": {k: gs["groups"][k]["score"] for k in gs["groups"]},
                "groupes_actifs": gs["groupes_actifs"],
            })

        # 3. Mettre a jour les caches
        fraud_detector._cached_scores = new_scores
        fraud_detector._cached_compact = compact_scores

        _set_training_status(job_id, "running", 90, "Sauvegarde de la configuration...", None)

        # 4. Sauvegarder la config comme versionnee
        # (deja fait dans update_config, mais on le refait pour etre sur)
        fraud_detector.config_manager.save()

        _set_training_status(job_id, "completed", 100, "Re-scoring termine", None)
        print(f"✅ Re-scoring termine: {n} sinistres mis a jour (job {job_id})")

    except Exception as e:
        _set_training_status(job_id, "failed", 0, f"Erreur: {str(e)}", None)
        print(f"❌ Erreur re-scoring job {job_id}: {e}")


async def _run_rescoring_and_save_version(job_id: str, new_config: dict):
    """
    Re-score tous les sinistres et sauvegarde une nouvelle version du modele.
    
    Étapes:
    1. Execute le rescoring
    2. Calcule les metriques
    3. Sauvegarde le modele comme nouvelle version
    4. Active la nouvelle version
    5. Marque le job comme termine avec le numero de version
    """
    try:
        # 1. Executer le rescoring (reutiliser la logique existante)
        _set_training_status(job_id, "running", 10, "Application de la nouvelle configuration...", None)

        fraud_detector.config = fraud_detector.config_manager.current
        fraud_detector.seuil_normal_max  = fraud_detector.config.thresholds["normal_max"]
        fraud_detector.seuil_suspect_min = fraud_detector.config.thresholds["suspect_min"]
        fraud_detector.seuil_frauduleux  = fraud_detector.config.thresholds["frauduleux"]
        global SEUIL_NORMAL_MAX, SEUIL_SUSPECT_MIN, SEUIL_FRAUDULEUX
        SEUIL_NORMAL_MAX = fraud_detector.config.thresholds["normal_max"]
        SEUIL_SUSPECT_MIN = fraud_detector.config.thresholds["suspect_min"]
        SEUIL_FRAUDULEUX = fraud_detector.config.thresholds["frauduleux"]

        n = len(fraud_detector._cached_scores)
        _set_training_status(job_id, "running", 20, f"Re-scoring de {n} sinistres...", None)

        # Recalculer tous les scores
        new_scores = np.zeros(n)
        compact_scores = []

        for i in range(n):
            if i % 1000 == 0 and i > 0:
                pct = int(i / n * 100)
                _set_training_status(job_id, "running", 20 + int(pct * 0.7), f"Re-scoring: {i}/{n}", None)

            gs = fraud_detector.calculate_grouped_score(i)
            if_score  = fraud_detector._data_cache["scores_if"][i]
            lof_score = fraud_detector._data_cache["scores_lof"][i]
            ee_score  = fraud_detector._data_cache["scores_ee"][i]

            if len(fraud_detector._active_models) == 3:
                ml_score = round((if_score + lof_score + ee_score) / 3.0, 1)
            elif len(fraud_detector._active_models) == 2:
                if "if" in fraud_detector._active_models and "lof" in fraud_detector._active_models:
                    ml_score = round((if_score + lof_score) / 2.0, 1)
                else:
                    ml_score = round((if_score + ee_score) / 2.0, 1)
            else:
                ml_score = round(if_score, 1)

            final_score = round(min(100.0, gs["score_brut"]), 1)
            statut, niveau = fraud_detector._status_from_score(final_score)

            new_scores[i] = final_score
            compact_scores.append({
                "total": final_score,
                "heuristic_total": round(min(100.0, gs["score_brut"]), 1),
                "score_brut": gs["score_brut"],
                "ml_score": ml_score,
                "statut": statut,
                "niveau": niveau,
                "triggers": gs["all_triggers"],
                "scores_groupes": {k: gs["groups"][k]["score"] for k in gs["groups"]},
                "groupes_actifs": gs["groupes_actifs"],
            })

        # Mettre a jour les caches
        fraud_detector._cached_scores = new_scores
        fraud_detector._cached_compact = compact_scores
        fraud_detector.config_manager.save()

        _set_training_status(job_id, "running", 90, "Sauvegarde de la nouvelle version du modele...", None)

        # 2. Sauvegarder comme nouvelle version
        version_num = fraud_detector.version_manager.get_next_version_number()
        version_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "models",
            "versions",
            f"v{version_num}_model.pkl",
        )
        
        # Sauvegarder le modele
        fraud_detector.save(version_path)
        
        # Calculer les metriques
        metrics = {
            "score_moyen": float(np.mean(new_scores)),
            "score_median": float(np.median(new_scores)),
            "score_std": float(np.std(new_scores)),
            "pct_frauduleux": float(np.sum(new_scores > SEUIL_FRAUDULEUX) / len(new_scores) * 100),
            "pct_suspect": float(np.sum((new_scores >= SEUIL_SUSPECT_MIN) & (new_scores <= SEUIL_FRAUDULEUX)) / len(new_scores) * 100),
            "pct_normal": float(np.sum(new_scores < SEUIL_SUSPECT_MIN) / len(new_scores) * 100),
        }

        # Sauvegarder la version avec metriques
        notes = f"Reconfiguration appliquee: seuils={fraud_detector.config.thresholds}, poids_groupes={fraud_detector.config.group_weights}"
        fraud_detector.version_manager.save_version(
            version_num,
            version_path,
            metrics,
            notes=notes
        )

        # Activer la nouvelle version
        fraud_detector.version_manager.set_active_version(version_num)

        # Sauvegarder aussi le modele par defaut
        default_model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "auto_fraud_model.pkl")
        fraud_detector.save(default_model_path)

        _set_training_status(
            job_id, 
            "completed", 
            100, 
            f"Nouvelle version v{version_num} creee et activee avec succes",
            version_num
        )
        print(f"✅ Rescoring + Version {version_num} sauvegardee et activee (job {job_id})")

    except Exception as e:
        _set_training_status(job_id, "failed", 0, f"Erreur: {str(e)}", None)
        print(f"❌ Erreur rescoring+sauvegarde job {job_id}: {e}")


@app.get("/diagnostic")
async def get_diagnostic():
    if sinistres_df is None:
        raise HTTPException(404, "Donnees non chargees")
    result = {
        "donnees": {
            "nb_sinistres": len(sinistres_df),
            "nb_contrats":  len(contrats_df) if contrats_df is not None else 0,
            "nb_tiers":     len(tiers_df)    if tiers_df    is not None else 0,
        },
        "geocoder": {
            "actif":  geocoder is not None,
            "stats":  geocoder.stats() if geocoder else {},
        },
        "seuils": {"frauduleux": SEUIL_FRAUDULEUX, "suspect_min": SEUIL_SUSPECT_MIN},
        "version": "3.14",
    }
    if fraud_detector and fraud_detector.is_fitted:
        stats = fraud_detector.get_global_statistics()
        result["scoring"] = {
            "score_moyen":    stats.get("score_moyen", 0),
            "pct_frauduleux": stats.get("distribution", {}).get("frauduleux", {}).get("percentage", 0),
            "pct_suspect":    stats.get("distribution", {}).get("suspect",    {}).get("percentage", 0),
            "pct_normal":     stats.get("distribution", {}).get("normal",     {}).get("percentage", 0),
        }
    return result


# ════════════════════════════════════════════════════════════════════════════
# RAPPORT PDF SINISTRE --- v3.14
# ════════════════════════════════════════════════════════════════════════════
@app.get("/rapport/{sinistre_id}/pdf")
async def get_rapport_pdf(sinistre_id: int):
    _check_model()
    if sinistres_df is None:
        raise HTTPException(404, "Donnees non chargees")
    if sinistre_id < 0 or sinistre_id >= len(sinistres_df):
        raise HTTPException(404, f"Sinistre {sinistre_id} non trouve")

    row = sinistres_df.iloc[sinistre_id].to_dict()
    for k, v in row.items():
        if isinstance(v, pd.Timestamp):
            row[k] = str(v)

    compact           = fraud_detector.get_cached_compact(sinistre_id)
    score_total       = compact["total"]
    score_brut        = compact.get("score_brut", compact["total"])
    statut            = compact["statut"]
    niveau            = compact["niveau"]
    scores_par_groupe = compact.get("scores_groupes", {})
    indicateurs       = compact.get("triggers", [])

    cache_key = md5(f"{sinistre_id}|{score_total}|v3.14".encode()).hexdigest()
    if cache_key in PDF_REPORT_CACHE:
        return StreamingResponse(
            BytesIO(PDF_REPORT_CACHE[cache_key]), media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=rapport_sinistre_{sinistre_id}.pdf"},
        )

    if statut == "frauduleux":
        c_main, c_bg, label_statut = (
            colors.HexColor("#C53030"), colors.HexColor("#FED7D7"),
            f"🚨 FRAUDULEUX --- Score {score_total:.1f}/100 > {SEUIL_FRAUDULEUX:.0f}",
        )
    elif statut == "suspect":
        c_main, c_bg, label_statut = (
            colors.HexColor("#C05621"), colors.HexColor("#FEEBC8"),
            f"⚠️ SUSPECT --- Score {score_total:.1f}/100 ∈ [{SEUIL_SUSPECT_MIN:.0f}--{SEUIL_FRAUDULEUX:.0f}]",
        )
    else:
        c_main, c_bg, label_statut = (
            colors.HexColor("#276749"), colors.HexColor("#C6F6D5"),
            f"✅ NON FRAUDULEUX --- Score {score_total:.1f}/100 < {SEUIL_SUSPECT_MIN:.0f}",
        )

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
    doc    = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=1.8*cm, bottomMargin=1.8*cm,
        title=f"Rapport Fraude #{sinistre_id}",
    )
    story = []

    story.append(Paragraph("RAPPORT DE DÉTECTION DE FRAUDE", s_title))
    story.append(Paragraph("Systeme Automatique v3.14", s_sub))
    story.append(Paragraph(
        f"Sinistre #{sinistre_id}  |  {datetime.now().strftime('%d/%m/%Y %H:%M')}", s_sub
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=c_main))
    story.append(Spacer(1, 10))

    st_table = Table([[label_statut], [f"Niveau de risque : {niveau.upper()}"]], colWidths=[PAGE_W])
    st_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), c_bg),
        ("TEXTCOLOR",     (0, 0), (-1, 0), c_main),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BOX",           (0, 0), (-1, -1), 1.5, c_main),
    ]))
    story.append(st_table)
    story.append(Spacer(1, 14))

    # Score par groupe
    if scores_par_groupe:
        story.append(Paragraph(
            "📊 SCORE PAR GROUPE",
            sty("H2", fontSize=12, fontName="Helvetica-Bold", spaceAfter=8),
        ))
        group_data = [["Groupe", "Score", "Max", "Utilisation"]]
        for group, score in scores_par_groupe.items():
            max_score = GROUP_CAPS.get(group, 0)
            pct       = (score / max_score * 100) if max_score > 0 else 0
            pct_label = f"{pct:.0f}%" if pct <= 100 else f"{pct:.0f}% ⚠"
            group_data.append([GROUP_LABELS.get(group, group), f"{score:.1f}", str(max_score), pct_label])

        group_table = Table(group_data, colWidths=[5.5*cm, 2.5*cm, 2.5*cm, 2.5*cm])
        group_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#4A5568")),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
            ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(group_table)
        story.append(Spacer(1, 14))

    # Score final
    story.append(Paragraph(
        "📌 SCORE FINAL DE SUSPICION",
        sty("H2", fontSize=12, fontName="Helvetica-Bold", spaceAfter=8),
    ))
    final_score_data = [
        ["Score brut (somme groupes apres caps)", f"{score_brut:.1f} pts"],
        ["Score final",                           f"{score_total:.1f} / 100"],
        ["Statut",                                statut.upper()],
    ]
    final_table = Table(final_score_data, colWidths=[8*cm, PAGE_W - 8*cm])
    final_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 1), (-1, 1), colors.HexColor("#2D3748")),
        ("TEXTCOLOR",     (0, 1), (-1, 1), colors.white),
        ("FONTNAME",      (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("BACKGROUND",    (0, 0), (0, -1), colors.HexColor("#EDF2F7")),
        ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(final_table)
    story.append(Spacer(1, 14))

    # Informations sinistre
    story.append(Paragraph(
        "📋 INFORMATIONS SINISTRE",
        sty("H2", fontSize=12, fontName="Helvetica-Bold", spaceAfter=8),
    ))
    sin_data = [
        ["N° Sinistre",      safe_str(row.get("NUM_SINISTRE"))],
        ["N° Contrat",       safe_str(row.get("NUM_CONTRAT"))],
        ["Immatriculation",  safe_str(row.get("IMMATRICULATION"))],
        ["Date survenance",  fmt_date(row.get("DATE_SURVENANCE"))],
        ["Date declaration", fmt_date(row.get("DATE_DECLARATION"))],
        ["Montant",          fmt_tnd(safe_float(row.get("TOTALREGLEMENT", 0)))],
        ["Statut",           safe_str(row.get("STATUS"))],
        ["Expert",           safe_str(row.get("EXPERT_STAREX"))],
        ["Garage",           safe_str(row.get("GARAGES"))],
    ]
    sin_table = Table(sin_data, colWidths=[5*cm, PAGE_W - 5*cm])
    sin_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, -1), colors.HexColor("#EDF2F7")),
        ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(sin_table)
    story.append(Spacer(1, 14))

    # Indicateurs detectes
    if indicateurs:
        story.append(Paragraph(
            f"⚠️ INDICATEURS DÉTECTÉS ({len(indicateurs)})",
            sty("H2", fontSize=12, fontName="Helvetica-Bold", spaceAfter=8,
                textColor=colors.HexColor("#C05621")),
        ))

        pts_brut_par_groupe: Dict = defaultdict(int)
        for ind in indicateurs:
            pts_brut_par_groupe[ind.get("group", "-")] += ind.get("pts", 0)

        group_scales = {}
        for g, brut in pts_brut_par_groupe.items():
            cap = GROUP_CAPS.get(g, brut)
            group_scales[g] = cap / brut if brut > cap else 1.0

        ind_data = [["Groupe", "Code", "Indicateur", "Points"]]
        for ind in indicateurs:
            grp      = ind.get("group", "-")
            pts_brut = ind.get("pts", 0)
            scale    = group_scales.get(grp, 1.0)
            pts_eff  = round(pts_brut * scale)
            ind_data.append([
                GROUP_LABELS.get(grp, grp),
                ind.get("code", "-"),
                ind.get("label", "-"),
                f"+{pts_eff}",
            ])

        for g, brut in pts_brut_par_groupe.items():
            cap = GROUP_CAPS.get(g, brut)
            if brut <= cap:
                continue
            idxs    = [i for i, ind in enumerate(indicateurs) if ind.get("group", "-") == g]
            cur_eff = [int(ind_data[i + 1][3].lstrip("+")) for i in idxs]
            diff    = cap - sum(cur_eff)
            if diff == 0:
                continue
            sorted_idxs = sorted(idxs, key=lambda i: indicateurs[i].get("pts", 0), reverse=(diff > 0))
            for i in sorted_idxs:
                if diff == 0:
                    break
                row_idx = i + 1
                old_val = int(ind_data[row_idx][3].lstrip("+"))
                if diff > 0:
                    ind_data[row_idx][3] = f"+{old_val + 1}"
                    diff -= 1
                elif old_val > 0:
                    ind_data[row_idx][3] = f"+{old_val - 1}"
                    diff += 1

        total_effectif = sum(int(ind_data[i][3].lstrip("+")) for i in range(1, len(ind_data)))

        groupes_capes = [
            f"{GROUP_LABELS.get(k, k)} ({pts_brut_par_groupe[k]}-->{GROUP_CAPS[k]})"
            for k in pts_brut_par_groupe
            if pts_brut_par_groupe[k] > GROUP_CAPS.get(k, pts_brut_par_groupe[k])
        ]
        note_caps = f"  (* caps : {', '.join(groupes_capes)})" if groupes_capes else ""

        ind_data.append([
            "",
            "TOTAL",
            f"Score final : {score_total:.1f} / 100{note_caps}",
            str(total_effectif),
        ])

        ind_table = Table(ind_data, colWidths=[3*cm, 3.2*cm, PAGE_W - 8.2*cm, 2*cm])
        ind_style = TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#C05621")),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("ALIGN",         (3, 0), (3, -1), "CENTER"),
            ("GRID",          (0, 0), (-1, -2), 0.4, colors.HexColor("#E2E8F0")),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("BACKGROUND",    (0, -1), (-1, -1), colors.HexColor("#2D3748")),
            ("TEXTCOLOR",     (0, -1), (-1, -1), colors.white),
            ("FONTNAME",      (0, -1), (-1, -1), "Helvetica-Bold"),
            ("LINEABOVE",     (0, -1), (-1, -1), 1.5, colors.HexColor("#C05621")),
        ])
        for row_idx in range(1, len(ind_data) - 1):
            if row_idx % 2 == 0:
                ind_style.add("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#FFF5F0"))
        ind_table.setStyle(ind_style)
        story.append(ind_table)

        if groupes_capes:
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                "* Plafond de groupe applique --- les points affiches tiennent compte du plafond par groupe.",
                sty("NOTE", fontSize=7, textColor=colors.HexColor("#718096"), spaceAfter=0),
            ))
        story.append(Spacer(1, 14))
    else:
        story.append(Paragraph(
            "✅ Aucun indicateur de fraude detecte.",
            sty("OK", fontSize=10, textColor=colors.HexColor("#276749"), spaceAfter=14),
        ))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E0")))
    story.append(Spacer(1, 5))
    story.append(Paragraph(
        f"Rapport genere le {datetime.now().strftime('%d/%m/%Y a %H:%M:%S')} | "
        f"v3.14 --- Score brut {score_brut:.1f} pts --> score final {score_total:.1f}/100",
        s_footer,
    ))

    doc.build(story)
    buffer.seek(0)
    PDF_REPORT_CACHE[cache_key] = buffer.getvalue()
    if len(PDF_REPORT_CACHE) > 200:
        PDF_REPORT_CACHE.pop(next(iter(PDF_REPORT_CACHE)))

    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=rapport_sinistre_{sinistre_id}.pdf"},
    )


@app.get("/rapport/evolution/pdf")
async def get_evolution_pdf():
    if sinistres_df is None:
        raise HTTPException(404)
    df = sinistres_df.copy()
    df["DATE_SURVENANCE"] = pd.to_datetime(df["DATE_SURVENANCE"], errors="coerce")
    df["ANNEE"] = df["DATE_SURVENANCE"].dt.year
    df = df[df["ANNEE"].notna() & (df["ANNEE"] >= 2000) & (df["ANNEE"] <= 2030)]
    df["ANNEE"] = df["ANNEE"].astype(int)
    evo = (
        df.groupby("ANNEE")
        .agg(
            nb_sinistres=("NUM_SINISTRE", "count"),
            montant_total=("TOTALREGLEMENT", "sum"),
            montant_moyen=("TOTALREGLEMENT", "mean"),
        )
        .reset_index()
        .sort_values("ANNEE")
    )

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
    doc    = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
        topMargin=1.8*cm, bottomMargin=1.8*cm, title="Rapport Évolution",
    )
    story = []
    story.append(Paragraph("RAPPORT D'ÉVOLUTION ANNUELLE", s_title))
    story.append(Paragraph(f"v3.14  |  {datetime.now().strftime('%d/%m/%Y %H:%M')}", s_sub))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#2D3748")))
    story.append(Spacer(1, 14))

    if len(evo) > 0:
        detail = [["Annee", "Nb sinistres", "Montant total (TND)", "Montant moyen (TND)"]]
        for _, r in evo.iterrows():
            detail.append([
                str(int(r["ANNEE"])),
                f"{int(r['nb_sinistres']):,}",
                f"{r['montant_total']:,.0f}",
                f"{r['montant_moyen']:,.0f}",
            ])
        dt = Table(detail, colWidths=[3*cm, 4*cm, 5*cm, 4*cm])
        dt.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#2D3748")),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
            ("ALIGN",         (1, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(dt)

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E0")))
    story.append(Spacer(1, 5))
    story.append(Paragraph(
        f"Rapport genere le {datetime.now().strftime('%d/%m/%Y a %H:%M:%S')} | v3.14",
        s_footer,
    ))
    doc.build(story)
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=rapport_evolution.pdf"},
    )


@app.get("/rapport/dashboard/pdf")
async def get_dashboard_pdf():
    if sinistres_df is None:
        raise HTTPException(404)
    stats = fraud_detector.get_global_statistics() if fraud_detector else {}
    total = len(sinistres_df)

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
    doc    = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
        topMargin=1.8*cm, bottomMargin=1.8*cm, title="Dashboard",
    )
    story = []
    story.append(Paragraph("TABLEAU DE BORD - DÉTECTION DE FRAUDE", s_title))
    story.append(Paragraph(
        f"v3.14  |  {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  {total:,} sinistres",
        s_sub,
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#2D3748")))
    story.append(Spacer(1, 14))

    kpi_data = [["Indicateur", "Valeur"]]
    kpi_data.append(["Total sinistres", f"{total:,}"])
    if "TOTALREGLEMENT" in sinistres_df.columns:
        m = sinistres_df["TOTALREGLEMENT"].fillna(0)
        kpi_data.append(["Montant total regle", f"{m.sum():,.0f} TND"])
        kpi_data.append(["Montant moyen",       f"{m.mean():,.0f} TND"])
    if stats:
        dist = stats.get("distribution", {})
        kpi_data.append(["Score moyen suspicion", f"{stats.get('score_moyen', 0):.1f}/100"])
        kpi_data.append(["Frauduleux",  f"{dist.get('frauduleux', {}).get('count', 0):,} ({dist.get('frauduleux', {}).get('percentage', 0):.2f}%)"])
        kpi_data.append(["Suspects",    f"{dist.get('suspect',    {}).get('count', 0):,} ({dist.get('suspect',    {}).get('percentage', 0):.2f}%)"])
        kpi_data.append(["Normaux",     f"{dist.get('normal',     {}).get('count', 0):,} ({dist.get('normal',     {}).get('percentage', 0):.2f}%)"])
        kpi_data.append(["Seuil frauduleux", f"{SEUIL_FRAUDULEUX}"])
        kpi_data.append(["Seuil suspect",    f"{SEUIL_SUSPECT_MIN}"])
    kpi_data.append(["Version scoring", "3.14 --- poids recalibres"])

    kpi_table = Table(kpi_data, colWidths=[6*cm, PAGE_W - 6*cm])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#2D3748")),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E0")))
    story.append(Spacer(1, 5))
    story.append(Paragraph(
        f"Rapport genere le {datetime.now().strftime('%d/%m/%Y a %H:%M:%S')} | v3.14",
        s_footer,
    ))
    doc.build(story)
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=rapport_dashboard.pdf"},
    )


# ─── Communautes ──────────────────────────────────────────────────────────────
@app.get("/communities")
async def get_communities(refresh: bool = False):
    if community_detector is None:
        raise HTTPException(503, "Neo4j AuraDB non connecte")
    try:
        return community_detector.get_full_analysis(force_refresh=refresh)
    except Exception as e:
        raise HTTPException(500, f"Erreur analyse communautes : {e}")


@app.get("/communities/graph")
async def get_communities_graph(refresh: bool = False):
    if community_detector is None:
        raise HTTPException(503, "Neo4j AuraDB non connecte")
    try:
        data = community_detector.get_full_analysis(force_refresh=refresh)
        return data.get("graph", {"nodes": [], "edges": [], "communities": [],
                                   "total_nodes": 0, "total_edges": 0})
    except Exception as e:
        raise HTTPException(500, f"Erreur donnees graphe : {e}")


@app.get("/communities/stats")
async def get_communities_stats():
    if community_detector is None:
        raise HTTPException(503, "Neo4j AuraDB non connecte")
    try:
        return community_detector.get_full_analysis()["stats"]
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/communities/{community_id}")
async def get_community_detail(community_id: int):
    if community_detector is None:
        raise HTTPException(503, "Neo4j AuraDB non connecte")
    data  = community_detector.get_full_analysis()
    match = next((c for c in data.get("communities", []) if c["id"] == community_id), None)
    if not match:
        raise HTTPException(404, f"Communaute {community_id} non trouvee")
    return match


# ─── Features ─────────────────────────────────────────────────────────────────
@app.get("/features")
async def get_all_features(
    group: Optional[str] = None,
    with_stats: bool = False,
):
    """
    Retourne les features auto-extraites (v3.8), groupees par dimension de scoring.

    Query params :
      - group       : filtre sur un groupe (financial, temporal, frequency,
                      network, driver, profile, other)
      - with_stats  : si true, inclut moyenne et % non-nul par feature
    """
    _check_model()
    if not fraud_detector.feature_engineer:
        raise HTTPException(500, "Feature engineer non initialise")

    feature_names = fraud_detector.feature_engineer.feature_names
    raw_df = fraud_detector._raw_feature_matrix if with_stats else None

    catalog = _build_features_catalog(feature_names, raw_df)

    valid_groups = list(GROUP_LABELS.keys()) + ["other"]
    if group:
        group = group.lower()
        if group not in valid_groups:
            raise HTTPException(
                400,
                f"Groupe '{group}' invalide. Valeurs acceptees : {valid_groups}",
            )
        filtered = catalog.get(group, [])
        return JSONResponse({
            "group":           group,
            "group_label":     GROUP_LABELS.get(group, group.capitalize()),
            "group_max_score": GROUP_CAPS.get(group, 0),
            "total_features":  len(filtered),
            "features":        filtered,
        })

    summary = []
    for g, feats in catalog.items():
        summary.append({
            "group":           g,
            "group_label":     GROUP_LABELS.get(g, g.capitalize()),
            "group_max_score": GROUP_CAPS.get(g, 0),
            "total_features":  len(feats),
            "features":        feats,
        })

    order = list(GROUP_LABELS.keys()) + ["other"]
    summary.sort(key=lambda x: order.index(x["group"]) if x["group"] in order else 99)

    return JSONResponse({
        "total_features": len(feature_names),
        "total_groups":   len(summary),
        "version":        "3.14",
        "note":           "Features auto-extraites v3.8, groupees selon la grille de scoring v3.14.",
        "groups":         summary,
    })


# ─── Prediction combinee Excel + Neo4j ───────────────────────────────────────
@app.get("/predict-combined/{sinistre_id}")
async def predict_combined(sinistre_id: int):
    _check_model()
    if sinistres_df is None or sinistre_id < 0 or sinistre_id >= len(sinistres_df):
        raise HTTPException(404, f"Sinistre {sinistre_id} non trouve")

    row   = sinistres_df.iloc[sinistre_id].to_dict()
    num_s = str(row.get("NUM_SINISTRE", sinistre_id))

    excel_pred = fraud_detector.predict(sinistre_id, sinistres_df, contrats_df, tiers_df)

    neo4j_pred = None
    if hasattr(fraud_detector, "_neo4j_detector") and fraud_detector._neo4j_detector is not None:
        try:
            neo4j_pred = fraud_detector._neo4j_detector.predict(num_s)
        except Exception:
            neo4j_pred = None

    return JSONResponse({
        "sinistre_id":  sinistre_id,
        "num_sinistre": num_s,
        "excel":        excel_pred,
        "neo4j":        neo4j_pred,
    })


@app.get("/statistics/fraud-scores")
async def get_fraud_score_statistics():
    """
    Statistiques completes centrees sur les scores de fraude et statuts generes.
    Couvre : distribution des scores, contribution par groupe heuristique,
    triggers les plus frequents, statuts, niveaux de risque, percentiles.
    """
    _check_model()
    if sinistres_df is None:
        raise HTTPException(404)

    scores   = fraud_detector._cached_scores
    compact  = fraud_detector._cached_compact
    n        = len(scores)

    # 1. KPIs globaux
    frauduleux = int((scores > SEUIL_FRAUDULEUX).sum())
    suspect    = int(((scores >= SEUIL_SUSPECT_MIN) & (scores <= SEUIL_FRAUDULEUX)).sum())
    normal     = int((scores < SEUIL_SUSPECT_MIN).sum())

    kpis = {
        "total":              n,
        "score_moyen":        round(float(scores.mean()), 2),
        "score_median":       round(float(np.median(scores)), 2),
        "score_std":          round(float(scores.std()), 2),
        "score_min":          round(float(scores.min()), 2),
        "score_max":          round(float(scores.max()), 2),
        "frauduleux_count":   frauduleux,
        "suspect_count":      suspect,
        "normal_count":       normal,
        "frauduleux_pct":     round(frauduleux / n * 100, 2),
        "suspect_pct":        round(suspect    / n * 100, 2),
        "normal_pct":         round(normal     / n * 100, 2),
        "seuil_frauduleux":   SEUIL_FRAUDULEUX,
        "seuil_suspect_min":  SEUIL_SUSPECT_MIN,
    }

    # 2. Distribution des scores par tranche de 10
    dist_scores = []
    for lo in range(0, 100, 10):
        hi    = lo + 10
        count = int(((scores >= lo) & (scores < hi)).sum())
        dist_scores.append({
            "tranche": f"{lo}-{hi}",
            "lo": lo, "hi": hi,
            "count": count,
            "pct": round(count / n * 100, 2),
        })

    # 3. Percentiles
    percentiles = {
        f"p{p}": round(float(np.percentile(scores, p)), 2)
        for p in [10, 25, 50, 75, 90, 95, 99]
    }

    # 4. Niveaux de risque (critique / eleve / modere / faible)
    niveaux = {}
    for c in compact:
        nv = c.get("niveau", "faible")
        niveaux[nv] = niveaux.get(nv, 0) + 1
    niveaux_list = [
        {"niveau": k, "count": v, "pct": round(v / n * 100, 2)}
        for k, v in sorted(niveaux.items(), key=lambda x: -x[1])
    ]

    # 5. Score moyen par groupe heuristique + sinistres touches
    group_keys = list(fraud_detector.config.group_weights.keys())
    group_totals = {g: 0.0 for g in group_keys}
    group_nonzero = {g: 0   for g in group_keys}
    group_max_seen = {g: 0.0 for g in group_keys}

    for c in compact:
        for g, s in c.get("scores_groupes", {}).items():
            if g not in group_totals:
                continue
            group_totals[g]  += s
            group_max_seen[g] = max(group_max_seen[g], s)
            if s > 0:
                group_nonzero[g] += 1

    groupes_stats = [
        {
            "groupe":            g,
            "label":             GROUP_LABELS.get(g, g),
            "score_moyen":       round(group_totals[g] / n, 2),
            "score_moyen_actif": round(group_totals[g] / group_nonzero[g], 2) if group_nonzero[g] > 0 else 0,
            "score_max_vu":      round(group_max_seen[g], 1),
            "cap":               fraud_detector.config.group_weights.get(g, 0),
            "sinistres_touches": group_nonzero[g],
            "pct_touches":       round(group_nonzero[g] / n * 100, 2),
            "saturation_moy":    round(group_totals[g] / n / fraud_detector.config.group_weights.get(g, 1) * 100, 1),
        }
        for g in fraud_detector.config.group_weights
    ]

    # 6. Triggers les plus frequents (top 20)
    trigger_counts = {}
    trigger_pts    = {}
    for c in compact:
        for t in c.get("triggers", []):
            code = t.get("code", "?")
            trigger_counts[code] = trigger_counts.get(code, 0) + 1
            trigger_pts[code]    = trigger_pts.get(code, t.get("pts", 0))

    top_triggers = sorted(trigger_counts.items(), key=lambda x: -x[1])[:20]
    triggers_list = [
        {
            "code":    code,
            "count":   cnt,
            "pct":     round(cnt / n * 100, 2),
            "pts":     trigger_pts.get(code, 0),
            "groupe":  next((t.get("group","?") for c in compact for t in c.get("triggers",[]) if t.get("code")==code), "?"),
            "label":   next((t.get("label","?") for c in compact for t in c.get("triggers",[]) if t.get("code")==code), code),
        }
        for code, cnt in top_triggers
    ]

    # 7. Nombre de groupes actifs simultanement (profondeur de fraude)
    groupes_actifs_dist = {}
    for c in compact:
        ga = c.get("groupes_actifs", 0)
        groupes_actifs_dist[ga] = groupes_actifs_dist.get(ga, 0) + 1
    groupes_actifs_list = [
        {"nb_groupes": k, "count": v, "pct": round(v / n * 100, 2)}
        for k, v in sorted(groupes_actifs_dist.items())
    ]

    # 8. Score brut vs score final (impact des caps)
    score_bruts = [c.get("score_brut", c.get("total", 0)) for c in compact]
    caps_impact = {
        "score_brut_moyen":  round(float(np.mean(score_bruts)), 2),
        "score_final_moyen": round(float(scores.mean()), 2),
        "diff_moyenne":      round(float(np.mean(score_bruts)) - float(scores.mean()), 2),
        "nb_sinistres_plafonnes": int(sum(1 for sb, sf in zip(score_bruts, scores) if sb > sf + 0.5)),
    }

    return JSONResponse(content={
        "kpis":                kpis,
        "distribution_scores": dist_scores,
        "percentiles":         percentiles,
        "niveaux_risque":      niveaux_list,
        "groupes_stats":       groupes_stats,
        "top_triggers":        triggers_list,
        "groupes_actifs_dist": groupes_actifs_list,
        "caps_impact":         caps_impact,
        "version":             "3.14.1",
    })


if __name__ == "__main__":
    import uvicorn
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 0)
    sock.bind(("0.0.0.0", 8000))
    sock.close()
    uvicorn.run(app, host="0.0.0.0", port=8000)