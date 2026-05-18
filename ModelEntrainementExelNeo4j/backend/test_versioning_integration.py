#!/usr/bin/env python3
"""Integration test for AutoFraudDetector versioning."""

import os
import numpy as np
from utils.data_loader import DataLoader
from ml.auto_fraud_detector import AutoFraudDetector


def load_data():
    loader = DataLoader()
    loaded = loader.load_all()
    if not loaded:
        raise RuntimeError("Échec du chargement des données depuis backend/data")
    sinistres = loader.get_sinistres()
    contrats = loader.get_contrats()
    tiers = loader.get_tiers()
    if sinistres is None:
        raise RuntimeError("Sinistres introuvables après chargement")
    return sinistres, contrats, tiers


def build_synthetic_labels(sinistres_df):
    # Utiliser un label simple pour tester le chemin supervisé
    if "STATUS" in sinistres_df.columns:
        return (sinistres_df["STATUS"].astype(str).str.lower() == "fermé").astype(int).values
    if "CAS_BAREME" in sinistres_df.columns:
        return (sinistres_df["CAS_BAREME"].astype(str).str.contains("Cas 0", case=False, na=False)).astype(int).values
    return np.zeros(len(sinistres_df), dtype=int)


def main():
    print("\n=== TEST D'INTÉGRATION : VERSIONING MODÈLE ===\n")

    sinistres, contrats, tiers = load_data()
    print(f"Données chargées : {len(sinistres)} sinistres, "
          f"{len(contrats) if contrats is not None else 0} contrats, "
          f"{len(tiers) if tiers is not None else 0} tiers")

    if len(sinistres) > 30000:
        print("Utilisation d'un échantillon léger pour tester rapidement")
        sample_fraction = 0.25
    else:
        sample_fraction = 1.0

    print("\n--- Entraînement v1 (non supervisé) ---")
    detector_v1 = AutoFraudDetector()
    detector_v1.fit(sinistres, contrats, tiers, sample_fraction=sample_fraction)
    print("v1 entraîné et version sauvegardée.")
    detector_v1.display_version_history()

    print("\n--- Entraînement v2 (supervisé avec labels synthétiques) ---")
    labels = build_synthetic_labels(sinistres)
    detector_v2 = AutoFraudDetector()
    detector_v2.fit(sinistres, contrats, tiers, labels=labels, sample_fraction=sample_fraction)
    print("v2 entraîné et version sauvegardée.")
    detector_v2.display_version_history()

    print("\n--- Comparaison v1 vs v2 ---")
    comparison = detector_v2.compare_versions(1, 2)
    print(comparison)

    print("\n--- Activation de la version 1 ---")
    detector_v2.set_active_version(1)
    print("Version active :", detector_v2.version_manager.get_active_version())

    print("\n--- Vérification du chargement de version 1 ---")
    detector_v2.load_version(1)
    print("Version 1 chargée, modèle prêt pour prédiction ?", detector_v2.is_fitted)

    print("\n=== TEST D'INTÉGRATION TERMINÉ ===")


if __name__ == "__main__":
    main()
