"""
PATCH auto_feature_engineering.py  VERSION 3.9
================================================
Corrections apportes vs v3.8 :

1. MERGE TIERS tendu
   - Jointure via CODE_CLIENT (contrat)  UUID (tiers) POUR TOUS PARTY_TYPE
   - Suppression du filtre PARTY_TYPE == 'ASSURE' ; tous les tiers sont maintenant joints
   - Prfixe chang de 'assure_'  'tiers_' pour reflter la gnralisation
   - Dduplication tiers : garde la ligne avec le plus de valeurs non-nulles

2. MERGE ASSURS corrig
   - Jointure via CODE_CLIENT (contrat)  UUID (tiers) UNIQUEMENT
   - Suppression du merge adverse inutile sur IMMATRICULATION_ADVERSE
     (les adverses ne sont PAS des assurs ; leurs donnes ne devraient
     pas tre jointes ligne--ligne sur le sinistre)
   - Dduplication assurs : garde la ligne avec le plus de valeurs non-nulles

3. INTGRATION DU GOCODEUR (TunisiaGeocoder)
   - Si adresse_sinistre / adresse_residence / adresse_travail prsentes
      coordonnes GPS calcules via gazetteer offline
   - Les colonnes GPS sont injectes dans df AVANT _compute_distances

4. NOUVELLES FEATURES UTILES
   - ratio_montant_prime        : TOTALREGLEMENT / PRIME contrat (corrige biais marque)
   - sinistre_heure_nuit        : survenance entre 0h et 5h (fuite tmoins)
   - sinistre_weekend           : samedi ou dimanche (indpendant de is_weekend_DATE_)
   - avenant_proche_sinistre_30j: avenant sign dans les 30j avant le sinistre

5. FILTRE DE VALIDIT DES FEATURES
   - Nouvelle mthode _validate_features() appele aprs construction de fd
   - Retire les features :
       * variance nulle ou quasi-nulle (< 1e-8)
       * > 95 % de zros (peu informatives pour l'anomalie)
       * corrlation > 0.98 avec une feature dj retenue (redondance)
   - Log dtaill des features retires

6. CORRECTION CLASSEMENT GROUPE "other"
   - expert_cout_anormal, taux_remplacement_garage, freq_sinistres_pv,
     age_vehicule_ans  correctement classs dans financial / network / temporal
     via _infer_feature_group (main.py)  aucun changement ici, mais
     les features sont dsormais correctement nommes pour le mapping.

Usage (aucun changement d'API publique) :
    fe = AutoFeatureEngineer()
    X, raw_df = fe.fit_transform_with_raw(sinistres_df, contrats_df, tiers_df)
"""

import json
import ast
import math
import re
import warnings
from typing import Dict, List, Tuple, Any, Optional

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

# Import du dtecteur de communauts (optionnel)
try:
    from ml.community_detector import CommunityDetector
    COMMUNITY_DETECTOR_AVAILABLE = True
except ImportError:
    COMMUNITY_DETECTOR_AVAILABLE = False
    CommunityDetector = None  # Pour viter les erreurs de rfrence

# Import depuis geo_utils pour viter la duplication
try:
    from ml.geo_utils import haversine_km as haversine_distance
except ImportError:
    # Fallback local si geo_utils absent
    def haversine_distance(lat1, lon1, lat2, lon2):
        try:
            if any(pd.isna(v) for v in [lat1, lon1, lat2, lon2]):
                return np.nan
            R = 6371
            lat1, lon1, lat2, lon2 = map(math.radians,
                                          [float(lat1), float(lon1),
                                           float(lat2), float(lon2)])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = (math.sin(dlat / 2) ** 2
                 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
            return R * 2 * math.asin(math.sqrt(max(0, min(1, a))))
        except Exception:
            return np.nan

warnings.filterwarnings("ignore")


#  Helpers colonnes 

def _find_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _find_col_pattern(df, *patterns):
    for col in df.columns:
        col_l = col.lower()
        for p in patterns:
            if p.lower() in col_l:
                return col
    return None


def _find_tiers_col(df, *patterns):
    for col in df.columns:
        if not col.startswith("tiers_"):
            continue
        col_l = col.lower()
        for p in patterns:
            if p.lower() in col_l:
                return col
    return None


#  Table de directions 

SUSPICIOUS_DIRECTION: Dict[str, str] = {
    "num_totalreglement": "high", "std_totalreglement": "high",
    "ratio_montant_moyen": "high", "ratio_montant_median": "high",
    "ratio_montant_prime": "high",
    "zscore_montant": "high", "montant_3std_suspect": "high",
    "ratio_montant_vs_garage": "high", "ratio_montant_vs_expert": "high",
    "ratio_montant_vs_client": "high", "ratio_cout_expert_global": "high",
    "expert_cout_anormal": "high",
    "montant_moyen_vehicule": "high", "montant_cumule_vehicule": "high",
    "montant_cumule_client": "high", "montant_moyen_expert": "high",
    "ratio_montant_pv_global": "high",
    "ratio_montant_vs_combo_job_marque": "high",
    "incoherence_age_montant": "high",
    "nbr_sinistres_vehicule": "high", "nbr_sinistres_client": "high",
    "nbr_sinistres_expert": "high", "nbr_sinistres_garage": "high",
    "nbr_sinistres_adverse": "high", "nbr_sinistres_contrat": "high",
    "sinistres_client_12mois": "high",
    "client_plus3_sinistres_12m": "high", "client_plus7_sinistres_12m": "high",
    "freq_expert_meme_vehicule": "high", "expert_vehicule_repete": "high",
    "adverse_repete": "high", "freq_sinistres_pv": "high",
    "nb_avenants_contrat": "high", "contrat_avenants_frequents": "high",
    "avenant_proche_sinistre_30j": "high",
    "taux_remplacement_garage": "high", "garage_taux_remplacement_eleve": "high",
    "note_conducteur_faible": "high", "note_conducteur_tres_faible": "high",
    "distance_travail_residence_elevee": "low",
    "distance_sinistre_residence_elevee": "high",
    "distance_sinistre_residence_identical": "high",
    "kilometrage_annuel_eleve": "high",
    "freq_temoin": "high", "temoin_frequent": "high",
    "lieu_sinistre_frequent": "high",
    "decalage_survenance_declaration_jours": "high",
    "declaration_tardive_30j": "high", "declaration_tres_tardive_90j": "high",
    "sinistre_moins_7j_apres_effet": "high",
    "sinistre_moins_30j_apres_effet": "high",
    "sinistre_moins_7j_expiration": "high",
    "sinistre_moins_30j_expiration": "high",
    "cluster_temporel_vehicule": "high", "cluster_temporel_client": "high",
    "velocite_recente_vehicule": "high", "velocite_recente_client": "high",
    "declaration_apres_weekend": "high",
    "sinistre_heure_nuit": "high", "sinistre_weekend": "high",
    "delai_moyen_sinistres": "low",
    "jours_apres_effet": "low", "jours_avant_expiration": "low",
    "profession_risque": "high", "sinistre_grave_sans_services": "high",
    "nb_services_operationnels": "low",
    "age_vehicule_ans": "high", "survenance_mois": "any",
    "sinistre_frontiere": "high",
    "freq_combo_job_marque": "low",
}
_DEFAULT_DIRECTION = "any"


def _get_direction(feature_name: str) -> str:
    key = feature_name.lower()
    if key in SUSPICIOUS_DIRECTION:
        return SUSPICIOUS_DIRECTION[key]
    for kw in ("freq_", "nbr_", "montant", "cumule", "ratio", "zscore",
               "tardive", "repete", "cluster", "velocite", "cout", "avenants",
               "heure_nuit", "weekend", "frontiere"):
        if kw in key:
            return "high"
    for kw in ("jours_apres", "jours_avant", "delai_moyen",
               "freq_combo", "distance_travail"):
        if kw in key:
            return "low"
    return _DEFAULT_DIRECTION


#  Classe principale 

class AutoFeatureEngineer:
    """Extraction automatique de features anti-fraude  v3.8."""

    def __init__(self, geocoder=None, community_detector=None):
        """
        geocoder : instance de TunisiaGeocoder (optionnel).
            Si None, le gocodage textuel (identit adresses) reste actif
            mais aucun appel GPS n'est effectu.
        community_detector : instance de CommunityDetector (optionnel).
            Si None, aucune dtection de communaut n'est effectue.
        """
        self.scaler = StandardScaler()
        self.feature_names: List[str] = []
        self.feature_importance: Dict[str, float] = {}
        self._geocoder = geocoder  # TunisiaGeocoder ou None
        self.community_detector = community_detector  # CommunityDetector ou None

        self._IGNORE = {
            "PACK", "contrat_PACK", "STATUS", "DAMAGE_TYPE",
            "AFFECTED_WARRANTIES", "LISTE_GARANTIESS",
            "contrat_LISTE_GARANTIESS", "ID_POLICE", "contrat_ID_POLICE",
            "NUM_SINISTRE", "NUM_DECLARATION", "NUM_CONTRAT",
            "contrat_NUMERO_POLICE", "contrat_NUM_CONTRAT",
            "CODE_CLIENT", "contrat_CODE_CLIENT",
            "tiers_UUID", "adverse_UUID",
            "tiers_IDENTITY_NUMBER", "adverse_IDENTITY_NUMBER",
            "ORIGINE_DECLARATION", "CAS_BAREME", "USAGE_LIBELLE",
            "contrat_ETAT_CONTRAT", "contrat_STATUT_CONTRAT",
        }

        self._IGNORE_PREFIXES = (
            "ID_", "NUM_", "UUID", "CODE_", "contrat_ID_", "contrat_NUM_",
            "contrat_CODE_", "tiers_ID_", "tiers_NUM_", "tiers_UUID",
            "adverse_ID_", "adverse_NUM_", "adverse_UUID",
                 )

    #  Score de communaut (NOUVEAU) 
    
    def _compute_community_score(self, sinistre_id: str) -> float:
        """
        Calcule un score bas sur l'appartenance  des communauts sospectueuses
        Retourne un score entre 0 et 100
        """
        if self.community_detector is None:
            return 0.0
        
        try:
            # Rcuprer l'analyse complte des communauts
            communities_data = self.community_detector.get_full_analysis()
            
            # Trouver la communaut  laquelle appartient ce sinistre
            for community in communities_data.get("communities", []):
                if str(sinistre_id) in [str(sid) for sid in community.get("sinistres_ids", [])]:
                    # Retourner un score normalis bas sur le niveau de la communaut
                    level_scores = {"modr": 30, "lev": 60, "critique": 90}
                    return level_scores.get(community.get("niveau", "modr"), 30)
            
            return 0.0  # Pas de communaut sospectueuse trouve
        except Exception as e:
            print(f"Erreur lors du calcul du score de communaut : {e}")
            return 0.0

    #  Helpers temporels 

    def _past_count(self, df, key_col):
        if key_col not in df.columns:
            return np.zeros(len(df))
        if "DATE_SURVENANCE" not in df.columns:
            return df.groupby(key_col)[key_col].transform("count").fillna(0).values
        temp = df[[key_col, "DATE_SURVENANCE"]].copy()
        temp["_idx"] = np.arange(len(temp))
        temp["_date"] = pd.to_datetime(temp["DATE_SURVENANCE"], errors="coerce")
        temp = temp.sort_values(["_date", "_idx"])
        temp["_past_count"] = temp.groupby(key_col).cumcount()
        return temp.sort_values("_idx")["_past_count"].fillna(0).values

    def _past_mean(self, df, key_col, val_col):
        if key_col not in df.columns or val_col not in df.columns:
            return np.zeros(len(df))
        if "DATE_SURVENANCE" not in df.columns:
            return df.groupby(key_col)[val_col].transform("mean").fillna(0).values
        temp = df[[key_col, val_col, "DATE_SURVENANCE"]].copy()
        temp["_idx"] = np.arange(len(temp))
        temp["_date"] = pd.to_datetime(temp["DATE_SURVENANCE"], errors="coerce")
        temp["_val"] = pd.to_numeric(temp[val_col], errors="coerce").fillna(0)
        temp = temp.sort_values(["_date", "_idx"])
        grp = temp.groupby(key_col)["_val"]
        temp["_past_mean"] = (
            grp.cumsum().sub(temp["_val"]).div(grp.cumcount().replace(0, np.nan))
        )
        gm = float(temp["_val"].mean()) if len(temp) else 0.0
        return temp.sort_values("_idx")["_past_mean"].fillna(gm).values

    def _past_sum(self, df, key_col, val_col):
        if key_col not in df.columns or val_col not in df.columns:
            return np.zeros(len(df))
        if "DATE_SURVENANCE" not in df.columns:
            return df.groupby(key_col)[val_col].transform("sum").fillna(0).values
        temp = df[[key_col, val_col, "DATE_SURVENANCE"]].copy()
        temp["_idx"] = np.arange(len(temp))
        temp["_date"] = pd.to_datetime(temp["DATE_SURVENANCE"], errors="coerce")
        temp["_val"] = pd.to_numeric(temp[val_col], errors="coerce").fillna(0)
        temp = temp.sort_values(["_date", "_idx"])
        grp = temp.groupby(key_col)["_val"]
        temp["_past_sum"] = grp.cumsum().sub(temp["_val"])
        return temp.sort_values("_idx")["_past_sum"].fillna(0).values

    def _past_median(self, df, key_col, val_col, fallback=0.0):
        if key_col not in df.columns or val_col not in df.columns:
            return np.full(len(df), fallback)
        if "DATE_SURVENANCE" not in df.columns:
            return df.groupby(key_col)[val_col].transform("median").fillna(fallback).values
        temp = df[[key_col, val_col, "DATE_SURVENANCE"]].copy()
        temp["_idx"] = np.arange(len(temp))
        temp["_date"] = pd.to_datetime(temp["DATE_SURVENANCE"], errors="coerce")
        temp["_val"] = pd.to_numeric(temp[val_col], errors="coerce").fillna(0.0)
        temp = temp.sort_values(["_date", "_idx"])
        hist_values: Dict = {}
        past_medians = np.full(len(temp), fallback, dtype=float)
        keys = temp[key_col].values
        vals = temp["_val"].values
        for i, (k, v) in enumerate(zip(keys, vals)):
            prev = hist_values.get(k, [])
            if prev:
                past_medians[i] = float(np.median(prev))
            else:
                past_medians[i] = fallback
            prev.append(v)
            hist_values[k] = prev
        temp["_past_median"] = past_medians
        return temp.sort_values("_idx")["_past_median"].values

    #  API publique 

    def fit_transform(self, sinistres_df, contrats_df=None, tiers_df=None):
        X, _ = self.fit_transform_with_raw(sinistres_df, contrats_df, tiers_df)
        return X

    def fit_transform_with_raw(self, sinistres_df, contrats_df=None, tiers_df=None):
        print(" AUTO-FEATURE v3.8: Extraction des features...")
        n_original = len(sinistres_df)
        df = self._merge(sinistres_df, contrats_df, tiers_df)

        if len(df) != n_original:
            print(f"    MERGE a cr des doublons : {n_original}  {len(df)}, correction...")
            df = df.iloc[:n_original].copy()

        #  Injection des coordonnes GPS via gocodeur 
        df = self._inject_gps(df)

        #  Construction du dictionnaire de features 
        fd: Dict[str, np.ndarray] = {}
        fd.update(self._numeric(df))
        fd.update(self._categorical(df))
        fd.update(self._temporal(df))
        fd.update(self._group(df))
        fd.update(self._frequency(df))
        fd.update(self._fraud_business(df))
        fd.update(self._new_indicators(df))

        #  Assemblage 
        feat = pd.DataFrame(fd).fillna(0).replace([np.inf, -np.inf], 0)
        assert len(feat) == n_original, f"Taille features incohrente : {len(feat)}  {n_original}"

        # --- SCORE DE COMMUNAUT (NOUVEAU) -------------------------------
        if self.community_detector is not None and len(df) > 0:
            print("    Calcul du score de communaut...")
            community_scores = []
            # Utiliser NUM_SINISTRE comme identifiant si disponible, sinon l'index
            sinistre_ids = df['NUM_SINISTRE'].astype(str) if 'NUM_SINISTRE' in df.columns else [str(i) for i in range(len(df))]
            
            for sinistre_id in sinistre_ids:
                community_score = self._compute_community_score(sinistre_id)
                community_scores.append(community_score)
            
            feat['community_score'] = community_scores
            print(f"    Score de communaut calcul : moy={np.mean(community_scores):.2f}, max={np.max(community_scores):.2f}")

        for col in feat.columns:
            if feat[col].dtype == "object":
                feat[col] = pd.to_numeric(feat[col], errors="coerce").fillna(0)

        #  Filtre de validit (NOUVEAU v3.8) 
        feat = self._validate_features(feat)

        raw_df = feat.copy()
        self.feature_names = list(feat.columns)
        X_scaled = self.scaler.fit_transform(feat)

        print(f" AUTO-FEATURE v3.8 : {len(self.feature_names)} features valides, {X_scaled.shape[0]} lignes")
        return X_scaled, raw_df

    #  FILTRE DE VALIDIT (NOUVEAU v3.8) 

    def _validate_features(self, feat: pd.DataFrame) -> pd.DataFrame:
        """
        Supprime les features peu informatives :
          1. Variance nulle (constante)
          2. > 95 % de zros (signal quasi-absent)
          3. Corrlation > 0.98 avec une feature dj retenue (doublon)
        Retourne le DataFrame filtr.
        """
        n = len(feat)
        to_drop = set()

        # 1. Variance nulle
        zero_var = feat.columns[feat.var() < 1e-8].tolist()
        to_drop.update(zero_var)
        if zero_var:
            print(f"     Variance nulle : {len(zero_var)} features supprimes")

        # 2. Trop de zros (> 95 %)
        pct_zero = (feat == 0).mean()
        almost_empty = pct_zero[pct_zero > 0.95].index.tolist()
        # Exception : garder les features binaires importantes mme si rares
        important_binary = {
            "sinistre_moins_7j_apres_effet", "sinistre_moins_7j_expiration",
            "montant_3std_suspect", "client_plus7_sinistres_12m",
            "declaration_tres_tardive_90j", "sinistre_frontiere",
            "sinistre_heure_nuit", "avenant_proche_sinistre_30j",
        }
        almost_empty = [c for c in almost_empty if c not in important_binary]
        to_drop.update(almost_empty)
        if almost_empty:
            print(f"     Quasi-vides (>95% zros) : {len(almost_empty)} features supprimes")

        # 3. Corrlation excessive (ddoublonnage)
        remaining = [c for c in feat.columns if c not in to_drop]
        if len(remaining) > 1:
            corr = feat[remaining].corr().abs()
            upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
            high_corr = [col for col in upper.columns if any(upper[col] > 0.98)]
            to_drop.update(high_corr)
            if high_corr:
                print(f"     Corrlation >0.98 : {len(high_corr)} features supprimes")

        kept_before = len(feat.columns)
        feat = feat.drop(columns=list(to_drop), errors="ignore")
        print(f"    Filtre validit : {kept_before}  {len(feat.columns)} features retenues")
        return feat

    #  MERGE  v3.8 : seulement contrats + assurs 

    def _merge(self, sinistres, contrats, tiers):
        df = sinistres.copy().reset_index(drop=True)

        #  1. Contrats via NUM_CONTRAT  NUMERO_POLICE 
        if contrats is not None and "NUM_CONTRAT" in df.columns:
            contrats_dedup = contrats.drop_duplicates(subset=["NUMERO_POLICE"], keep="first")
            print(f"   Contrats : {len(contrats)}  {len(contrats_dedup)} aprs dduplication")
            n_avant = len(df)
            df = df.merge(
                contrats_dedup.add_prefix("contrat_"),
                left_on="NUM_CONTRAT",
                right_on="contrat_NUMERO_POLICE",
                how="left",
            )
            if len(df) != n_avant:
                print(f"     Doublons contrats : {n_avant}  {len(df)}, correction...")
                df = df.iloc[:n_avant].copy()
            matched = df["contrat_NUMERO_POLICE"].notna().sum()
            print(f"    Merge contrats : {matched}/{n_avant} matchs ({matched/n_avant*100:.1f}%)")

        #  2. Tiers via contrat_CODE_CLIENT  UUID (tous PARTY_TYPE) 
        if (tiers is not None
                and "contrat_CODE_CLIENT" in df.columns
                and "UUID" in tiers.columns):

            tiers_merged = tiers.copy()

            print(f"\n    Diagnostic jointure tiers :")
            print(f"      contrat_CODE_CLIENT dtype : {df['contrat_CODE_CLIENT'].dtype}")
            print(f"      UUID dtype                : {tiers_merged['UUID'].dtype}")

            # Normalisation en Int64 pour viter "12345" vs 12345.0
            df["_join_key"] = pd.to_numeric(
                df["contrat_CODE_CLIENT"], errors="coerce"
            ).astype("Int64")

            tiers_merged["_join_key"] = pd.to_numeric(
                tiers_merged["UUID"], errors="coerce"
            ).astype("Int64")

            # Diagnostic overlap
            codes_sin = set(df["_join_key"].dropna().unique())
            codes_tiers = set(tiers_merged["_join_key"].dropna().unique())
            overlap = codes_sin & codes_tiers
            print(f"      Codes contrat : {len(codes_sin)} | UUIDs tiers : {len(codes_tiers)} | Overlap : {len(overlap)}")

            if len(overlap) == 0:
                print(f"        AUCUN OVERLAP  vrifier que CODE_CLIENT = UUID dans tiers")
            else:
                print(f"       {len(overlap)} valeurs communes")

            # Dduplication tiers : garder la ligne avec le plus de valeurs non-nulles
            tiers_sorted = tiers_merged.copy()
            tiers_sorted["_non_null"] = tiers_sorted.notna().sum(axis=1)
            tiers_sorted = tiers_sorted.sort_values("_non_null", ascending=False)
            tiers_dedup = tiers_sorted.drop_duplicates(subset=["_join_key"], keep="first")
            tiers_dedup = tiers_dedup.drop(columns=["_non_null"])
            print(f"      Tiers ddupliqus (max non-null) : {len(tiers_merged)}  {len(tiers_dedup)}")

            n_avant = len(df)
            df = df.merge(
                tiers_dedup.add_prefix("tiers_"),
                left_on="_join_key",
                right_on="tiers__join_key",
                how="left",
            )
            df.drop(columns=["_join_key", "tiers__join_key"], inplace=True, errors="ignore")
            if len(df) != n_avant:
                print(f"     Doublons tiers : {n_avant}  {len(df)}, correction...")
                df = df.iloc[:n_avant].copy()

            n_matched = df["tiers_UUID"].notna().sum() if "tiers_UUID" in df.columns else 0
            print(f"       Tiers matchs : {n_matched}/{n_avant} ({n_matched/n_avant*100:.1f}%)")

            for col in ["tiers_adresse_residence", "tiers_adresse_travail",
                        "tiers_JOB", "tiers_note_conducteur"]:
                if col in df.columns:
                    nn = df[col].notna().sum()
                    print(f"      {col} : {nn} valeurs non-nulles")
                else:
                    print(f"        {col} absente aprs merge")

        # NOTE : les donnes tiers (tous PARTY_TYPE) sont jointes ici via CODE_CLIENT = UUID.
        # L'indicateur adverse_repete est calcul directement sur
        # IMMATRICULATION_ADVERSE dans _fraud_business.

        return df

    #  Injection GPS via gocodeur 

    def _inject_gps(self, df: pd.DataFrame) -> pd.DataFrame:
        if self._geocoder is None:
            print("     Gocodeur absent  distances GPS dsactives")
            return df

        print("     Gocodage des adresses via TunisiaGeocoder...")

        #  Diagnostic colonnes disponibles 
        print("      Colonnes adresse dtectes :")
        for c in df.columns:
            if any(k in c.lower() for k in ["adresse", "lieu", "residence",
                                             "travail", "sinistre"]):
                nn = df[c].notna().sum()
                print(f"       {c} : {nn}/{len(df)} non-nulles")
        # 

        geo = self._geocoder

        def _geocode_col(src_col, lat_col, lon_col):
            if src_col not in df.columns:
                return
            if lat_col in df.columns and df[lat_col].notna().mean() > 0.5:
                print(f"      {lat_col} dj prsente  skip")
                return
            lats, lons = geo.geocode_series(df[src_col])
            df[lat_col] = lats.values
            df[lon_col] = lons.values
            n_ok = df[lat_col].notna().sum()
            print(f"      {src_col}  {n_ok}/{len(df)} gocods ({n_ok/len(df)*100:.1f}%)")

        # Lieu sinistre
        sin_col = _find_col(df, ["adresse_sinistre", "LIEU_SINISTRE"])
        if sin_col:
            _geocode_col(sin_col, "LATITUDE_SINISTRE", "LONGITUDE_SINISTRE")
        else:
            print("        Colonne lieu sinistre absente  GPS sinistre dsactiv")

        # Rsidence assure
        res_col = _find_tiers_col(df, "adresse_residence", "residence")
        if res_col:
            _geocode_col(res_col, "tiers_LATITUDE_RESIDENCE", "tiers_LONGITUDE_RESIDENCE")
        else:
            print("        Colonne rsidence absente  GPS rsidence dsactiv")

        # Adresse travail
        trv_col = _find_tiers_col(df, "adresse_travail", "travail", "work")
        if trv_col:
            _geocode_col(trv_col, "tiers_LATITUDE_TRAVAIL", "tiers_LONGITUDE_TRAVAIL")
        else:
            print("        Colonne travail absente  GPS travail dsactiv")

        stats = geo.stats()
        print(f"      Stats gocodeur : offline={stats['offline_hits']} "
              f"cache={stats['cache_hits']} "
              f"no_match={stats['no_match']} "
              f"empty={stats['empty']}")
        return df

    #  Features numriques 

    def _numeric(self, df):
        fd = {}
        keep = {"TOTALREGLEMENT"}
        for col in df.select_dtypes(include=[np.number]).columns:
            if col in self._IGNORE:
                continue
            col_upper = col.upper()
            if any(col_upper.startswith(p.upper()) for p in self._IGNORE_PREFIXES):
                continue
            if col not in keep:
                raw_col = (col.split("contrat_")[-1]
                           .split("tiers_")[-1]
                           .split("adverse_")[-1])
                if any(raw_col.upper().startswith(p)
                       for p in ("ID_", "NUM_", "UUID", "CODE_")):
                    continue
            v = df[col].fillna(0)
            fd[f"num_{col}"] = v.values
            if v.std() > 0:
                fd[f"std_{col}"] = ((v - v.mean()) / v.std()).fillna(0).values
        return fd

    #  Features catgorielles 

    def _categorical(self, df):
        fd = {}
        whitelist = ["ACTEUR_IMPLIQUE", "tiers_JOB", "tiers_TYPE"]
        for col in whitelist:
            if col not in df.columns or df[col].nunique() < 2:
                continue
            try:
                values = df[col].fillna("UNKNOWN").astype(str)
                freq = values.map(values.value_counts()).astype(float)
                fd[f"cat_{col}_freq"] = freq.values
            except Exception:
                continue
        return fd

    #  Features temporelles 

    def _temporal(self, df):
        fd = {}
        date_cols = [c for c in df.columns
                     if "DATE" in c.upper() and c not in self._IGNORE]
        for col in date_cols:
            try:
                dates = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
                if col == "DATE_SURVENANCE":
                    fd["survenance_mois"] = dates.dt.month.fillna(0).values

                    has_time = (
                        df["DATE_SURVENANCE"]
                        .astype(str)
                        .str.contains(r'\d{2}:\d{2}:\d{2}', regex=True, na=False)
                    )
                    pct_with_time = has_time.mean()
                    print(f"     DATE_SURVENANCE avec heure : "
                          f"{pct_with_time*100:.1f}% des lignes")

                    if pct_with_time >= 0.5:
                        heure  = dates.dt.hour
                        valide = dates.notna()
                        nuit_mask = (heure >= 0) & (heure < 5) & valide
                        fd["sinistre_heure_nuit"] = nuit_mask.astype(int).values
                        n_nuit = int(nuit_mask.sum())
                        print(f"    sinistre_heure_nuit (00h-04h59) : "
                              f"{n_nuit} ({n_nuit/len(df)*100:.1f}%)")
                        dist = dates[valide].dt.hour.value_counts().sort_index()
                        print(f"    Distribution heures :")
                        for h in range(24):
                            cnt = int(dist.get(h, 0))
                            if cnt > 0:
                                flag = "  NUIT" if h < 5 else ""
                                print(f"      {h:02d}h : {cnt:5d}{flag}")
                    else:
                        print("     DATE_SURVENANCE sans heure  "
                              "sinistre_heure_nuit dsactiv")
                        fd["sinistre_heure_nuit"] = np.zeros(len(df))

                    # WEEKEND
                    fd["sinistre_weekend"] = (
                        dates.dt.dayofweek >= 5
                    ).astype(int).values
                    n_wk = int(fd["sinistre_weekend"].sum())
                    print(f"    sinistre_weekend : "
                          f"{n_wk} ({n_wk/len(df)*100:.1f}%)")

                #  ICI en dehors du if DATE_SURVENANCE  traite TOUTES les dates
                fd[f"is_weekend_{col}"] = (
                    dates.dt.dayofweek >= 5
                ).astype(int).values

            except Exception:
                continue

        pairs = [
            ("DATE_SURVENANCE", "contrat_DATE_EFFET_CONTRAT"),
            ("DATE_SURVENANCE", "contrat_DATE_EXPIRATION"),
            ("DATE_DECLARATION", "contrat_DATE_EFFET_CONTRAT"),
        ]
        for c1, c2 in pairs:
            if c1 in df.columns and c2 in df.columns:
                try:
                    d1 = pd.to_datetime(df[c1], dayfirst=True, errors="coerce")
                    d2 = pd.to_datetime(df[c2], dayfirst=True, errors="coerce")
                    fd[f"diff_days__{c1}__{c2}"] = (d2 - d1).dt.days.fillna(0).values
                except Exception:
                    continue
        return fd

    #  Features par groupe 

    def _group(self, df):
        fd = {}
        client_col = _find_col(
            df,
            ["contrat_CODE_CLIENT", "tiers_UUID", "CODE_CLIENT", "REPORTING_AGENCY"],
        )

        if "IMMATRICULATION" in df.columns:
            fd["nbr_sinistres_vehicule"] = self._past_count(df, "IMMATRICULATION")
            if "TOTALREGLEMENT" in df.columns:
                fd["montant_moyen_vehicule"] = self._past_mean(
                    df, "IMMATRICULATION", "TOTALREGLEMENT"
                )
                fd["montant_cumule_vehicule"] = self._past_sum(
                    df, "IMMATRICULATION", "TOTALREGLEMENT"
                )

        if client_col:
            fd["nbr_sinistres_client"] = self._past_count(df, client_col)
            if "TOTALREGLEMENT" in df.columns:
                fd["montant_cumule_client"] = self._past_sum(
                    df, client_col, "TOTALREGLEMENT"
                )

        if "NUM_CONTRAT" in df.columns:
            fd["nbr_sinistres_contrat"] = self._past_count(df, "NUM_CONTRAT")

        if "EXPERT_STAREX" in df.columns:
            expert_clean = df["EXPERT_STAREX"].fillna("INCONNU").astype(str)
            expert_clean = expert_clean.where(
                expert_clean.str.lower() != "inconnu", "INCONNU_EXPERT"
            )
            tmp_exp = pd.DataFrame({
                "EXPERT": expert_clean,
                "DATE_SURVENANCE": df.get("DATE_SURVENANCE"),
            })
            fd["nbr_sinistres_expert"] = self._past_count(tmp_exp, "EXPERT")
            if "TOTALREGLEMENT" in df.columns:
                df_tmp = df.copy()
                df_tmp["_expert_clean"] = expert_clean
                fd["montant_moyen_expert"] = self._past_mean(
                    df_tmp, "_expert_clean", "TOTALREGLEMENT"
                )

        if "GARAGES" in df.columns:
            fd["nbr_sinistres_garage"] = self._past_count(df, "GARAGES")

        if "IMMATRICULATION" in df.columns and "DATE_SURVENANCE" in df.columns:
            def _mean_diff(grp):
                g = pd.to_datetime(grp, errors="coerce").dropna().sort_values()
                if len(g) <= 1:
                    return 999.0
                d = [(g.iloc[i + 1] - g.iloc[i]).days for i in range(len(g) - 1)]
                return float(np.mean(d)) if d else 999.0

            fd["delai_moyen_sinistres"] = (
                df.groupby("IMMATRICULATION")["DATE_SURVENANCE"]
                .transform(_mean_diff)
                .fillna(999)
                .values
            )

        if "TOTALREGLEMENT" in df.columns:
            m = df["TOTALREGLEMENT"].fillna(0)
            mu = m.mean()
            sigma = m.std()
            med = m.median()

            fd["ratio_montant_moyen"] = (m / (mu + 1)).values
            fd["ratio_montant_median"] = (m / (med + 1)).values

            if sigma > 0:
                fd["zscore_montant"] = ((m - mu) / sigma).values
                fd["montant_3std_suspect"] = (
                    ((m - mu) / sigma) > 3
                ).astype(int).values
            else:
                fd["zscore_montant"] = np.zeros(len(m))
                fd["montant_3std_suspect"] = np.zeros(len(m))

            #  NOUVEAU : ratio vs PRIME contrat 
            prime_col = _find_col(df, ["contrat_PRIME", "PRIME"])
            if prime_col:
                prime_series = pd.to_numeric(df[prime_col], errors="coerce").fillna(0)
                prime_mean = prime_series[prime_series > 0].mean()
                if pd.isna(prime_mean) or prime_mean <= 0:
                    prime_mean = 1.0
                print(f"    prime_mean globale : {prime_mean:.1f} TND")
                prime_indiv = prime_series.clip(lower=1)
                fd["ratio_montant_prime"] = (m / prime_indiv).values
                fd["montant_10x_prime"] = (m > prime_mean * 10).astype(int).values
                n_trigger = fd["montant_10x_prime"].sum()
                print(f"    montant_10x_prime (vs moyenne {prime_mean:.0f} TND) : "
                      f"{n_trigger} sinistres ({n_trigger/len(m)*100:.1f}%)")

            if "GARAGES" in df.columns:
                mg = self._past_median(df, "GARAGES", "TOTALREGLEMENT", fallback=float(med))
                fd["ratio_montant_vs_garage"] = (m / (mg + 1)).values

            if "EXPERT_STAREX" in df.columns:
                me = self._past_median(
                    df, "EXPERT_STAREX", "TOTALREGLEMENT", fallback=float(med)
                )
                fd["ratio_montant_vs_expert"] = (m / (me + 1)).values

            if client_col:
                mc = self._past_median(df, client_col, "TOTALREGLEMENT", fallback=float(med))
                fd["ratio_montant_vs_client"] = (m / (mc + 1)).values

        return fd

    #  Features de frquence 

    def _frequency(self, df):
        fd = {}
        cols = [
            "IMMATRICULATION",
            "IMMATRICULATION_ADVERSE",
            "EXPERT_STAREX",
            "GARAGES",
            "ACTEUR_IMPLIQUE",
            "contrat_POINT_VENTE",
            "tiers_JOB",
        ]
        for col in cols:
            if col not in df.columns or df[col].nunique() < 2:
                continue
            fd[f"freq_{col}"] = df[col].map(df[col].value_counts()).fillna(0).values
        return fd

    #  Features mtier fraude 

    def _fraud_business(self, df):
        fd = {}
        client_col = _find_col(
            df,
            ["contrat_CODE_CLIENT", "tiers_UUID", "CODE_CLIENT", "REPORTING_AGENCY"],
        )

        # Dlais de dclaration
        if "DATE_SURVENANCE" in df.columns and "DATE_DECLARATION" in df.columns:
            delta = (
                pd.to_datetime(df["DATE_DECLARATION"], errors="coerce")
                - pd.to_datetime(df["DATE_SURVENANCE"], errors="coerce")
            ).dt.days.fillna(0)
            fd["decalage_survenance_declaration_jours"] = delta.values
            fd["declaration_tardive_30j"] = (delta > 30).astype(int).values
            fd["declaration_tres_tardive_90j"] = (delta > 90).astype(int).values

        # Sinistre proche prise d'effet
        effet_col = _find_col(df, ["contrat_DATE_EFFET_CONTRAT", "DATE_EFFET_CONTRAT"])
        if "DATE_SURVENANCE" in df.columns and effet_col:
            j = (
                pd.to_datetime(df["DATE_SURVENANCE"], errors="coerce")
                - pd.to_datetime(df[effet_col], errors="coerce")
            ).dt.days.fillna(9999)
            fd["jours_apres_effet"] = j.values
            fd["sinistre_moins_7j_apres_effet"] = (
                (j >= 0) & (j < 7)
            ).astype(int).values
            fd["sinistre_moins_30j_apres_effet"] = (
                (j >= 0) & (j < 30)
            ).astype(int).values

        # Sinistre proche expiration
        exp_col = _find_col(df, ["contrat_DATE_EXPIRATION", "DATE_EXPIRATION"])
        if "DATE_SURVENANCE" in df.columns and exp_col:
            j = (
                pd.to_datetime(df[exp_col], errors="coerce")
                - pd.to_datetime(df["DATE_SURVENANCE"], errors="coerce")
            ).dt.days.fillna(9999)
            fd["jours_avant_expiration"] = j.values
            fd["sinistre_moins_30j_expiration"] = (
                (j >= 0) & (j < 30)
            ).astype(int).values
            fd["sinistre_moins_7j_expiration"] = (
                (j >= 0) & (j < 7)
            ).astype(int).values

        #  NOUVEAU : avenant dans les 30j avant le sinistre 
        av_col = _find_col(df, ["contrat_LISTE_AVENANTS", "LISTE_AVENANTS"])
        if av_col is None:
            av_col = _find_col_pattern(df, "liste_avenant", "avenants", "avenant")

        if av_col and "DATE_SURVENANCE" in df.columns:
            mots_exclus = [
                "rsiliation", "resiliation", "alination",
                "annulation", "resilie",
            ]

            def _av_dates(val):
                """Extrait les dates d'avenants depuis la valeur brute."""
                if pd.isna(val) or str(val).strip() in ("", "[]", "nan", "None"):
                    return []
                s = str(val).strip()
                lst = None
                try:
                    lst = json.loads(s)
                except Exception:
                    pass
                if lst is None:
                    try:
                        lst = ast.literal_eval(s)
                    except Exception:
                        pass
                if lst is None:
                    lst = [p.strip() for p in s.strip("[]").split(",") if p.strip()]
                if not isinstance(lst, list):
                    return []
                return [
                    str(it)
                    for it in lst
                    if not any(e in str(it).lower() for e in mots_exclus)
                ]

            def _nb_av(val):
                return len(_av_dates(val))

            nb_av = df[av_col].apply(_nb_av)
            fd["nb_avenants_contrat"] = nb_av.values
            fd["contrat_avenants_frequents"] = (nb_av > 2).astype(int).values

            # Avenant rcent (< 30j avant le sinistre)
            d_surv = pd.to_datetime(df["DATE_SURVENANCE"], errors="coerce")
            av_recent = pd.Series(0, index=df.index)
            for i, (val, ds) in enumerate(zip(df[av_col].values, d_surv.values)):
                if pd.isna(ds):
                    continue
                for item in _av_dates(val):
                    try:
                        d_av = pd.to_datetime(item, errors="coerce", dayfirst=True)
                        if pd.notna(d_av):
                            diff = (pd.Timestamp(ds) - d_av).days
                            if 0 <= diff <= 30:
                                av_recent.iloc[i] = 1
                                break
                    except Exception:
                        pass
            fd["avenant_proche_sinistre_30j"] = av_recent.values
            print(f"    avenant_proche_sinistre_30j : {av_recent.sum()} ({av_recent.mean()*100:.1f}%)")
            print(f"    avenants_frequents : {(nb_av>2).mean()*100:.1f}%")
        else:
            fd["nb_avenants_contrat"] = np.zeros(len(df))
            fd["contrat_avenants_frequents"] = np.zeros(len(df))
            fd["avenant_proche_sinistre_30j"] = np.zeros(len(df))

        # Sinistres client 12 mois
        if client_col and "DATE_SURVENANCE" in df.columns:
            dates_parsed = pd.to_datetime(df["DATE_SURVENANCE"], errors="coerce")

            def _cnt12_relative(group):
                idx = group.index
                dates_group = dates_parsed[idx]
                result = pd.Series(0, index=idx)
                for i in idx:
                    ref = dates_parsed[i]
                    if pd.isna(ref):
                        continue
                    result[i] = sum(
                        1
                        for d in dates_group
                        if pd.notna(d) and 0 < (ref - d).days <= 365
                    )
                return result

            s12 = df.groupby(client_col)["DATE_SURVENANCE"].transform(
                _cnt12_relative
            ).fillna(0)
            fd["sinistres_client_12mois"] = s12.values
            fd["client_plus3_sinistres_12m"] = (s12 > 3).astype(int).values
            fd["client_plus7_sinistres_12m"] = (s12 >= 7).astype(int).values
            print(
                f"    sinistres_client_12mois "
                f"| >3: {(s12>3).mean()*100:.1f}% | 7: {(s12>=7).mean()*100:.1f}%"
            )

        # Cluster temporel client
        if client_col and "DATE_SURVENANCE" in df.columns:
            dates_parsed = pd.to_datetime(df["DATE_SURVENANCE"], errors="coerce")

            def _delai_relatif(group):
                idx = group.index
                dates_group = dates_parsed[idx].sort_values()
                result = pd.Series(999.0, index=idx)
                for i in idx:
                    ref = dates_parsed[i]
                    if pd.isna(ref):
                        continue
                    prev = [
                        d
                        for d in dates_group
                        if pd.notna(d) and 0 < (ref - d).days <= 365
                    ]
                    if len(prev) >= 2:
                        prev_sorted = sorted(prev)
                        diffs = [
                            (prev_sorted[k + 1] - prev_sorted[k]).days
                            for k in range(len(prev_sorted) - 1)
                        ]
                        result[i] = float(np.mean(diffs)) if diffs else 999.0
                    elif len(prev) == 1:
                        result[i] = (ref - prev[0]).days
                    else:
                        result[i] = 999.0
                return result

            delai_c = df.groupby(client_col)["DATE_SURVENANCE"].transform(
                _delai_relatif
            ).fillna(999)
            fd["cluster_temporel_client"] = (delai_c <= 30).astype(int).values

        # Cluster temporel vhicule
        if "IMMATRICULATION" in df.columns and "DATE_SURVENANCE" in df.columns:
            def _mdd_veh(grp):
                g = pd.to_datetime(grp, errors="coerce").dropna().sort_values()
                if len(g) <= 1:
                    return 999.0
                d = [(g.iloc[i + 1] - g.iloc[i]).days for i in range(len(g) - 1)]
                return float(np.mean(d)) if d else 999.0

            delai_v = (
                df.groupby("IMMATRICULATION")["DATE_SURVENANCE"]
                .transform(_mdd_veh)
                .fillna(999)
            )
            fd["cluster_temporel_vehicule"] = (delai_v <= 30).astype(int).values

        # Expert cot anormal
        if "EXPERT_STAREX" in df.columns and "TOTALREGLEMENT" in df.columns:
            m = df["TOTALREGLEMENT"].fillna(0)
            g_mean = m.mean()
            em = (
                df.groupby("EXPERT_STAREX")["TOTALREGLEMENT"]
                .transform("mean")
                .fillna(g_mean)
            )
            fd["ratio_cout_expert_global"] = (em / (g_mean + 1)).values
            fd["expert_cout_anormal"] = (em > g_mean * 1.5).astype(int).values

        # Expert + vhicule rpts
        if "EXPERT_STAREX" in df.columns and "IMMATRICULATION" in df.columns:
            combo = (
                df["EXPERT_STAREX"].fillna("NA").astype(str)
                + "_"
                + df["IMMATRICULATION"].fillna("NA").astype(str)
            )
            cnt = combo.map(combo.value_counts())
            fd["freq_expert_meme_vehicule"] = cnt.fillna(0).values
            fd["expert_vehicule_repete"] = (cnt > 1).astype(int).fillna(0).values

        # Adverse rpt
        if "IMMATRICULATION_ADVERSE" in df.columns:
            adv_valid = df["IMMATRICULATION_ADVERSE"].fillna("NA")
            adv = adv_valid.map(adv_valid.value_counts())
            fd["nbr_sinistres_adverse"] = adv.fillna(0).values
            fd["adverse_repete"] = (adv > 2).astype(int).fillna(0).values

        # Tmoin frquent
        temoin_col = _find_col(df, ["temoin_id", "TEMOIN_ID", "TEMOIN", "temoin"])
        if temoin_col is None:
            temoin_col = _find_col_pattern(df, "temoin")
        if temoin_col:
            temoin_valid = df[temoin_col].fillna("NA").astype(str)
            temoin_counts = temoin_valid.map(temoin_valid.value_counts())
            fd["freq_temoin"] = temoin_counts.fillna(0).values
            fd["temoin_frequent"] = (temoin_counts > 3).astype(int).fillna(0).values
        else:
            fd["freq_temoin"] = np.zeros(len(df))
            fd["temoin_frequent"] = np.zeros(len(df))

        # Lieu sinistre frquent
        lieu_col = _find_col(df, ["adresse_sinistre", "LIEU_SINISTRE", "LIEU"])
        if lieu_col is None:
            lieu_col = _find_col_pattern(df, "adresse_sinistre")
        if lieu_col:
            lieu_valid = df[lieu_col].fillna("NA").astype(str)
            lieu_counts = lieu_valid.map(lieu_valid.value_counts())
            fd["freq_lieu_sinistre"] = lieu_counts.fillna(0).values
            fd["lieu_sinistre_frequent"] = (lieu_counts > 3).astype(int).fillna(0).values
        else:
            fd["freq_lieu_sinistre"] = np.zeros(len(df))
            fd["lieu_sinistre_frequent"] = np.zeros(len(df))

        # Sinistre proche frontire tunisienne
        frontiere_keywords = [
            "frontire", "douane", "poste frontire",
            "ben gardane", "ras jedir", "dehiba",
            "sakiet sidi youssef", "melloula", "tabarka", "bizerte",
            "jendouba", "kasserine", "gafsa", "tataouine",
            "medenine", "zarzis", "remada", "algerie", "lybie",
            "libye", "algrie", "ras ajdir", "wazen", "dhahra",
            "nefza", "ghardimaou", "fernana",
        ]
        lieu_col_front = _find_col(df, ["adresse_sinistre", "LIEU_SINISTRE"])
        if lieu_col_front:
            lieu_str = df[lieu_col_front].fillna("").astype(str).str.lower()
            fd["sinistre_frontiere"] = lieu_str.apply(
                lambda x: int(any(kw in x for kw in frontiere_keywords))
            ).values
            print(
                f"    sinistre_frontiere : {fd['sinistre_frontiere'].sum()} "
                f"({fd['sinistre_frontiere'].mean()*100:.1f}%)"
            )
        else:
            fd["sinistre_frontiere"] = np.zeros(len(df))

        # Profession  risque
        usage_col = _find_col(df, ["contrat_USAGE", "USAGE"])
        job_col = _find_tiers_col(df, "job")
        if job_col is None:
            job_col = _find_col(df, ["tiers_JOB", "JOB"])

        risque_usage = [
            "taxi", "louage", "location", "transport",
            "autobus", "camion", "utilitaire",
        ]
        risque_job = [
            "taxi", "louage", "location", "transport",
            "chauffeur", "conducteur", "livreur", "vtc",
            "camion", "bus",
        ]
        prof_risque = pd.Series(0, index=df.index)
        if usage_col:
            usage_vals = df[usage_col].fillna("").astype(str).str.lower()
            from_usage = usage_vals.apply(
                lambda x: int(any(p in x for p in risque_usage))
            )
            prof_risque = (prof_risque | from_usage).astype(int)
        if job_col:
            job_vals = df[job_col].fillna("").astype(str).str.lower()
            from_job = job_vals.apply(
                lambda x: (
                    int(any(p in x for p in risque_job))
                    if x not in ("inconnu", "", "nan")
                    else 0
                )
            )
            prof_risque = (prof_risque | from_job).astype(int)
        fd["profession_risque"] = prof_risque.values

        # Combo job  marque
        marque_col = _find_col(df, ["contrat_MARQUE", "MARQUE"])
        if job_col and marque_col and job_col in df.columns:
            job_clean = df[job_col].fillna("INCONNU").astype(str).str.lower().str.strip()
            marque_clean = (
                df[marque_col].fillna("INCONNU").astype(str).str.lower().str.strip()
            )
            combo_jm = job_clean + "_" + marque_clean
            combo_counts = combo_jm.map(combo_jm.value_counts())
            fd["freq_combo_job_marque"] = combo_counts.fillna(0).values
            if "TOTALREGLEMENT" in df.columns:
                m = df["TOTALREGLEMENT"].fillna(0)
                med_combo = (
                    df.groupby(combo_jm)["TOTALREGLEMENT"]
                    .transform("median")
                    .fillna(m.median())
                )
                fd["ratio_montant_vs_combo_job_marque"] = (m / (med_combo + 1)).values

        # ge vhicule + incohrence montant
        circ_col = _find_col(
            df, ["contrat_DATE_MISE_EN_CIRCULATION", "DATE_MISE_EN_CIRCULATION"]
        )
        if circ_col and "DATE_SURVENANCE" in df.columns:
            age = (
                (
                    pd.to_datetime(df["DATE_SURVENANCE"], errors="coerce")
                    - pd.to_datetime(df[circ_col], errors="coerce")
                ).dt.days
                / 365.25
            ).fillna(0).clip(lower=0)
            fd["age_vehicule_ans"] = age.values
            if "TOTALREGLEMENT" in df.columns:
                m = df["TOTALREGLEMENT"].fillna(0)
                fd["incoherence_age_montant"] = (
                    (age > 10) & (m > m.quantile(0.80))
                ).astype(int).values

        # Dclaration aprs weekend  SUPPRIM v3.15
        fd["declaration_apres_weekend"] = np.zeros(len(df))

        # Vlocit rcente
        if "DATE_SURVENANCE" in df.columns:
            def _vel(grp):
                g = pd.to_datetime(grp, errors="coerce").dropna()
                if len(g) == 0:
                    return 0.0
                last = g.max()
                r = sum(1 for d in g if 0 <= (last - d).days <= 30)
                y = sum(1 for d in g if 0 <= (last - d).days <= 365)
                return r / y if y > 0 else 0.0

            if "IMMATRICULATION" in df.columns:
                fd["velocite_recente_vehicule"] = (
                    df.groupby("IMMATRICULATION")["DATE_SURVENANCE"]
                    .transform(_vel)
                    .fillna(0)
                    .values
                )
            if client_col:
                fd["velocite_recente_client"] = (
                    df.groupby(client_col)["DATE_SURVENANCE"]
                    .transform(_vel)
                    .fillna(0)
                    .values
                )

        # Point de vente
        pv_col = _find_col(df, ["contrat_POINT_VENTE", "POINT_VENTE"])
        if pv_col and "TOTALREGLEMENT" in df.columns:
            m = df["TOTALREGLEMENT"].fillna(0)
            g_mean = m.mean()
            pv_mean = (
                df.groupby(pv_col)["TOTALREGLEMENT"].transform("mean").fillna(g_mean)
            )
            pv_cnt = df.groupby(pv_col)[pv_col].transform("count").fillna(1)
            fd["ratio_montant_pv_global"] = (pv_mean / (g_mean + 1)).values
            fd["freq_sinistres_pv"] = pv_cnt.values

        # Garage taux remplacement
        if "GARAGES" in df.columns and "PIECES_REMPLACER" in df.columns:
            taux = df.groupby("GARAGES")["PIECES_REMPLACER"].transform(
                lambda x: (
                    x.notna() & (x.astype(str).str.lower() != "inconnu")
                ).mean()
            ).fillna(0)
            fd["taux_remplacement_garage"] = taux.values
            fd["garage_taux_remplacement_eleve"] = (taux > 0.8).astype(int).values

        # Sinistre grave sans services  SUPPRIM v3.15
        # Faux signal li  des donnes manquantes, pas  la fraude
        fd["nb_services_operationnels"] = np.zeros(len(df))
        fd["sinistre_grave_sans_services"] = np.zeros(len(df))
        return fd

    #  Nouveaux indicateurs 

    def _new_indicators(self, df):
        fd = {}

        # Note conducteur
        note_col = _find_tiers_col(df, "note_conducteur", "note")
        if note_col is None:
            note_col = _find_col(
                df, ["tiers_note_conducteur", "tiers_NOTE_CONDUCTEUR"]
            )
        if note_col:
            note = pd.to_numeric(df[note_col], errors="coerce").fillna(5)
            fd["note_conducteur"] = note.values
            fd["note_conducteur_faible"] = (note < 5).astype(int).values
            fd["note_conducteur_tres_faible"] = (note < 3).astype(int).values
            print(
                f"    Note conducteur : min={note.min():.1f} max={note.max():.1f}"
            )
        else:
            fd["note_conducteur"] = np.full(len(df), 5.0)
            fd["note_conducteur_faible"] = np.zeros(len(df))
            fd["note_conducteur_tres_faible"] = np.zeros(len(df))

        # Distances GPS (si coordonnes disponibles aprs _inject_gps)
        self._compute_distances(df, fd)

        # Distances textuelles (fallback)
        self._compute_text_distances(df, fd)

        # Kilomtrage annuel
        km_col = _find_col(
            df,
            ["contrat_Kilomtrage", "contrat_KILOMETRAGE", "Kilomtrage", "KILOMETRAGE"],
        )
        if km_col is None:
            km_col = _find_col_pattern(df, "kilom")
        circ_col = _find_col(
            df, ["contrat_DATE_MISE_EN_CIRCULATION", "DATE_MISE_EN_CIRCULATION"]
        )
        if km_col and circ_col and "DATE_SURVENANCE" in df.columns:
            km = pd.to_numeric(df[km_col], errors="coerce").fillna(0)
            d_circ = pd.to_datetime(df[circ_col], errors="coerce")
            d_surv = pd.to_datetime(df["DATE_SURVENANCE"], errors="coerce")
            age = ((d_surv - d_circ).dt.days / 365.25).fillna(1).clip(lower=1)
            km_an = km / age
            fd["kilometrage_annuel"] = km_an.fillna(0).values
            fd["kilometrage_annuel_eleve"] = (km_an > 30000).astype(int).values
            mean_km = km_an.mean()
            fd["kilometrage_vs_moyenne"] = (km_an / (mean_km + 1)).fillna(0).values
            print(f"    Kilomtrage : moy annuel={km_an.mean():.0f} km/an")
        else:
            fd["kilometrage_annuel"] = np.zeros(len(df))
            fd["kilometrage_annuel_eleve"] = np.zeros(len(df))
            fd["kilometrage_vs_moyenne"] = np.zeros(len(df))

        return fd

    def _compute_text_distances(self, df, fd):
        n = len(df)
        fd.setdefault("distance_sinistre_residence_identical", np.zeros(n))
        fd.setdefault("distance_travail_residence_identical", np.zeros(n))

        col_res = _find_tiers_col(df, "adresse_residence", "residence")
        col_sin = _find_col(df, ["adresse_sinistre", "LIEU_SINISTRE"])
        col_travail = _find_tiers_col(df, "adresse_travail", "travail", "work")

        if col_res and col_sin:
            res_s = df[col_res].fillna("").astype(str).str.lower().str.strip()
            sin_s = df[col_sin].fillna("").astype(str).str.lower().str.strip()
            identical = (
                (res_s.str.len() > 3) & (sin_s.str.len() > 3) & (res_s == sin_s)
            ).astype(int).values
            fd["distance_sinistre_residence_identical"] = identical
            if np.all(fd.get("distance_sinistre_residence_elevee", np.zeros(n)) == 0):
                fd["distance_sinistre_residence_elevee"] = identical
            print(f"    sinistre_au_domicile : {identical.sum()}")

        if col_res and col_travail:
            res_s = df[col_res].fillna("").astype(str).str.lower().str.strip()
            trv_s = df[col_travail].fillna("").astype(str).str.lower().str.strip()
            identical = (
                (res_s.str.len() > 3) & (trv_s.str.len() > 3) & (res_s == trv_s)
            ).astype(int).values
            fd["distance_travail_residence_identical"] = identical
            if np.all(fd.get("distance_travail_residence_elevee", np.zeros(n)) == 0):
                fd["distance_travail_residence_elevee"] = identical

    def _compute_distances(self, df, fd):
        n = len(df)
        fd["distance_sinistre_residence_km"] = np.zeros(n)
        fd["distance_sinistre_residence_elevee"] = np.zeros(n)
        fd["distance_travail_residence_km"] = np.zeros(n)
        fd["distance_travail_residence_elevee"] = np.zeros(n)

        candidates = {
            "lat_res": ["tiers_LATITUDE_RESIDENCE", "LATITUDE_RESIDENCE"],
            "lon_res": ["tiers_LONGITUDE_RESIDENCE", "LONGITUDE_RESIDENCE"],
            "lat_sin": ["LATITUDE_SINISTRE", "lat_sinistre"],
            "lon_sin": ["LONGITUDE_SINISTRE", "lon_sinistre"],
            "lat_trv": ["tiers_LATITUDE_TRAVAIL", "LATITUDE_TRAVAIL"],
            "lon_trv": ["tiers_LONGITUDE_TRAVAIL", "LONGITUDE_TRAVAIL"],
        }
        cols = {k: _find_col(df, v) for k, v in candidates.items()}

        if not (cols["lat_res"] and cols["lon_res"]):
            return

        lat_res = pd.to_numeric(df[cols["lat_res"]], errors="coerce")
        lon_res = pd.to_numeric(df[cols["lon_res"]], errors="coerce")

        if cols["lat_sin"] and cols["lon_sin"]:
            lat_sin = pd.to_numeric(df[cols["lat_sin"]], errors="coerce")
            lon_sin = pd.to_numeric(df[cols["lon_sin"]], errors="coerce")
            dist_sr = np.array([
                haversine_distance(a, b, c, d)
                for a, b, c, d in zip(lat_res, lon_res, lat_sin, lon_sin)
            ])
            dist_sr = np.nan_to_num(dist_sr, nan=0.0, posinf=0.0, neginf=0.0)
            fd["distance_sinistre_residence_km"] = dist_sr
            fd["distance_sinistre_residence_elevee"] = (dist_sr > 30).astype(int)
            print(f"    GPS sinistre-rsidence : max={dist_sr.max():.0f} km")

        if cols["lat_trv"] and cols["lon_trv"]:
            lat_trv = pd.to_numeric(df[cols["lat_trv"]], errors="coerce")
            lon_trv = pd.to_numeric(df[cols["lon_trv"]], errors="coerce")
            dist_tr = np.array([
                haversine_distance(a, b, c, d)
                for a, b, c, d in zip(lat_res, lon_res, lat_trv, lon_trv)
            ])
            dist_tr = np.nan_to_num(dist_tr, nan=0.0, posinf=0.0, neginf=0.0)
            fd["distance_travail_residence_km"] = dist_tr
            fd["distance_travail_residence_elevee"] = (dist_tr > 40).astype(int)
            print(f"    GPS travail-rsidence : max={dist_tr.max():.0f} km")

    #  Alertes dterministes 

    def compute_deterministic_alerts(self, row, contrat_info=None, prediction=None):
        alerts = []
        contrat = contrat_info or {}
        try:
            d_surv = pd.to_datetime(row.get("DATE_SURVENANCE"), errors="coerce")
            d_decl = pd.to_datetime(row.get("DATE_DECLARATION"), errors="coerce")
            if pd.notna(d_surv) and pd.notna(d_decl):
                delta = (d_decl - d_surv).days
                if delta > 365:
                    alerts.append({
                        "code": "D1_DECL_ULTRA_TARDIVE",
                        "label": f"Dclaration {delta} jours aprs le sinistre",
                        "niveau": "critique", "triggered": True,
                    })
                elif delta > 90:
                    alerts.append({
                        "code": "D1_DECL_TRES_TARDIVE",
                        "label": f"Dclaration {delta} jours aprs le sinistre",
                        "niveau": "lev", "triggered": True,
                    })
        except Exception:
            pass
        try:
            d_surv = pd.to_datetime(row.get("DATE_SURVENANCE"), errors="coerce")
            d_effet = pd.to_datetime(contrat.get("DATE_EFFET_CONTRAT"), errors="coerce")
            if pd.notna(d_surv) and pd.notna(d_effet):
                j = (d_surv - d_effet).days
                if 0 <= j < 7:
                    alerts.append({
                        "code": "D2_SINISTRE_IMMEDIAT",
                        "label": f"Sinistre {j} jours aprs dbut de couverture",
                        "niveau": "critique", "triggered": True,
                    })
        except Exception:
            pass
        return alerts

    def get_top_features(self, n=10):
        if not self.feature_importance:
            return []
        return list(self.feature_importance.items())[:n]
