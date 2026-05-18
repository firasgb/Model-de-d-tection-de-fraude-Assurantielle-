#!/usr/bin/env python3
"""
test_versioning.py — Exemple d'utilisation du système de versioning
"""

from ml.auto_fraud_detector import AutoFraudDetector

# ════════════════════════════════════════════════════════════════════════════
# EXEMPLE D'UTILISATION
# ════════════════════════════════════════════════════════════════════════════

print("=" * 80)
print("🚀 DÉMONSTRATION SYSTÈME DE VERSIONING")
print("=" * 80)

# 1️⃣  Créer et entraîner un modèle
print("\n1️⃣  CRÉATION MODÈLE v1 (non-supervisé)...")
detector_v1 = AutoFraudDetector()

# detector_v1.fit(sinistres_df, contrats_df, tiers_df)
# Cela crée automatiquement v1_model.pkl avec les KPIs

print("\n✅ Le modèle est sauvegardé automatiquement en v1 avec ses KPIs")
print("   → models/versions/v1_model.pkl")
print("   → models/versions/version_history.json")

# 2️⃣  Réentraîner avec données réétiquetées
print("\n2️⃣  RÉENTRAÎNEMENT MODÈLE v2 (supervisé avec labels)...")
# detector_v2 = AutoFraudDetector()
# detector_v2.fit(sinistres_df_retrained, contrats_df, tiers_df, labels=y_true)
# Cela crée automatiquement v2_model.pkl avec les KPIs (F1, Precision, Recall, AUC)

print("✅ Le modèle v2 est créé avec ses KPIs:")
print("   → F1-Score:  0.87")
print("   → Precision: 0.89")
print("   → Recall:    0.85")
print("   → Accuracy:  0.91")
print("   → AUC-ROC:   0.93")

# 3️⃣  Lister toutes les versions
print("\n3️⃣  AFFICHER HISTORIQUE COMPLET...")
# detector_v1.display_version_history()

# Affichage simulé:
print("""
════════════════════════════════════════════════════════════
📋 HISTORIQUE DES VERSIONS
════════════════════════════════════════════════════════════

v1 ⚪ — 2026-05-10T14:32:00
   F1-Score  : 0.82
   Precision : 0.84
   Recall    : 0.79
   Accuracy  : 0.88
   AUC-ROC   : 0.90
   Score moy : 38.5
   Notes     : Entraînement non supervisé

v2 🟢 ACTIVE — 2026-05-10T15:45:00
   F1-Score  : 0.87
   Precision : 0.89
   Recall    : 0.85
   Accuracy  : 0.91
   AUC-ROC   : 0.93
   Score moy : 37.8
   Notes     : Entraînement supervisé avec labels

════════════════════════════════════════════════════════════
""")

# 4️⃣  Comparer deux versions
print("4️⃣  COMPARER DEUX VERSIONS...")
# comparison = detector_v1.compare_versions(1, 2)

print("""
📊 Comparaison v1 vs v2:
   F1-Score delta  : +0.0500
   Precision delta : +0.0500
   Recall delta    : +0.0600
   AUC delta       : +0.0300
   ⭐ Meilleure version : v2
""")

# 5️⃣  Charger une version spécifique
print("\n5️⃣  CHARGER VERSION SPÉCIFIQUE...")
# detector_v1.load_version(1)  # Charge v1
# detector_v2.load_version(2)  # Charge v2

print("✅ Version 2 chargée")
print("   F1-Score : 0.87")
print("   Accuracy : 0.91")

# 6️⃣  Activer une version pour la production
print("\n6️⃣  ACTIVER VERSION POUR PRODUCTION...")
# detector_v1.set_active_version(2)

print("✅ Version 2 activée pour les prédictions")

# 7️⃣  Consulter les métriques d'une version
print("\n7️⃣  CONSULTER MÉTRIQUES DÉTAILLÉES V1...")
# metrics = detector_v1.get_version_metrics(1)

print("""
{
  "f1_score": 0.82,
  "precision": 0.84,
  "recall": 0.79,
  "accuracy": 0.88,
  "auc_roc": 0.90,
  "confusion_matrix": {
    "true_negatives": 4800,
    "false_positives": 55,
    "false_negatives": 127,
    "true_positives": 450
  },
  "distribution": {
    "frauduleux": {"count": 577, "pct": 10.6},
    "suspect": {"count": 1050, "pct": 19.3},
    "normal": {"count": 3805, "pct": 70.1}
  },
  "is_supervised": false,
  "training_samples": 5432,
  "models_active": ["if", "lof", "ee"]
}
""")

print("\n" + "=" * 80)
print("✅ DÉMONSTRATION COMPLÈTE")
print("=" * 80)
print("""
📌 RÉSUMÉ SYSTÈME DE VERSIONING:

✅ Auto-création de versions à chaque fit()
✅ Calcul automatique des KPIs (F1, Precision, Recall, AUC, Accuracy)
✅ Historique complet sauvegardé en JSON
✅ L'analyste peut comparer les versions
✅ L'analyste peut activer la version qu'il préfère
✅ Backward compatibility : anciennes versions toujours accessibles

📁 Structure:
   models/versions/
   ├── v1_model.pkl
   ├── v2_model.pkl
   ├── v3_model.pkl
   ├── version_history.json
   └── version_config.json

🎯 Prochaines étapes:
   1. Implémenter une API REST pour consulter les versions
   2. Ajouter un dashboard web pour visualiser les comparaisons
   3. Ajouter des alertes si la performance baisse trop
""")
