"""
Script d'entraînement avec barre de progression - À exécuter UNE SEULE FOIS
"""
import sys
import time
from ml.auto_fraud_detector import AutoFraudDetector
from utils.data_loader import DataLoader

print("=" * 60)
print("ENTRAÎNEMENT DU MODÈLE DE DÉTECTION DE FRAUDE (3 MODÈLES)")
print("=" * 60)

# 1. Chargement des données
print("\n📂 Chargement des fichiers Excel...")
start = time.time()
dl = DataLoader()
dl.load_all()
sinistres = dl.get_sinistres()
contrats = dl.get_contrats()
tiers = dl.get_tiers()
print(f"   ✅ Données chargées en {time.time()-start:.1f}s")
print(f"      - Sinistres: {len(sinistres)}")
print(f"      - Contrats: {len(contrats) if contrats is not None else 0}")
print(f"      - Tiers: {len(tiers) if tiers is not None else 0}")

# 2. Entraînement (3 modèles: IF + LOF optimisé + EE)
print("\n🤖 Entraînement du modèle avec 3 modèles...")
print("   (Cela peut prendre 2-5 minutes sur 60k sinistres)")
start = time.time()
detector = AutoFraudDetector()

# sample_fraction=1.0 = toutes les données
# Pour un test rapide, mettez sample_fraction=0.3
detector.fit(sinistres, contrats, tiers, sample_fraction=1.0)

print(f"\n   ✅ Entraînement terminé en {time.time()-start:.1f}s")

# 3. Sauvegarde
print("\n💾 Sauvegarde du modèle...")
detector.save()
print("   ✅ Modèle sauvegardé dans models/auto_fraud_model.pkl")

# 4. Statistiques
stats = detector.get_global_statistics()
print("\n📊 STATISTIQUES GLOBALES:")
print(f"   Total sinistres analysés: {stats['total_sinistres']}")
print(f"   Score moyen: {stats['score_moyen']}/100")
print(f"   Distribution:")
print(f"      - Frauduleux (>70): {stats['distribution']['frauduleux']['count']} ({stats['distribution']['frauduleux']['percentage']}%)")
print(f"      - Suspects (50-70): {stats['distribution']['suspect']['count']} ({stats['distribution']['suspect']['percentage']}%)")
print(f"      - Normaux (<50): {stats['distribution']['normal']['count']} ({stats['distribution']['normal']['percentage']}%)")

print("\n" + "=" * 60)
print("✅ MODÈLE PRÊT !")
print("   Lancez l'API avec: uvicorn main:app --reload")
print("=" * 60)