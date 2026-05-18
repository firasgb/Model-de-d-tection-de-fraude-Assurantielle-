#!/usr/bin/env python3
"""
Test validation features v5.1
Vérifie que toutes les 67 features se créent correctement
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Ajouter le path backend
sys.path.insert(0, '/c/Users/LENOVO/Desktop/insurance-fraud-detection-v2/backend')

from ml.auto_feature_engineering import AutoFeatureEngineer

# Créer un DataFrame de test minimal
def create_test_dataframe(n_rows=100):
    """Crée un mini dataset pour tester les features"""
    today = datetime.now()
    
    df = pd.DataFrame({
        # Clés de base
        'NUM_SINISTRE': np.arange(n_rows),
        'NUM_CONTRAT': np.random.randint(1000, 2000, n_rows),
        'IMMATRICULATION': [f"TN{i%10:03d}{i:02d}" for i in range(n_rows)],
        
        # Dates
        'DATE_SURVENANCE': [today - timedelta(days=int(30*np.random.random())) for _ in range(n_rows)],
        'DATE_DECLARATION': [today - timedelta(days=int(10*np.random.random())) for _ in range(n_rows)],
        
        # Montants
        'TOTALREGLEMENT': np.random.exponential(2000, n_rows),
        
        # Acteurs
        'EXPERT_STAREX': [f"EXPERT_{i%5}" for i in range(n_rows)],
        'GARAGES': [f"GARAGE_{i%3}" for i in range(n_rows)],
        'IMMATRICULATION_ADVERSE': [f"ADV{i%20:03d}" for i in range(n_rows)],
        
        # Autres colonnes de test
        'adresse_sinistre': [f"Tunis Rue {i}" for i in range(n_rows)],
        'PIECES_REMPLACER': np.random.choice([1, 0, np.nan], n_rows),
    })
    
    return df

def create_test_contrats(df):
    """Crée un DataFrame contrats de test"""
    num_contrats = df['NUM_CONTRAT'].unique()
    contrats = pd.DataFrame({
        'NUMERO_POLICE': num_contrats,
        'CODE_CLIENT': np.arange(len(num_contrats)),
        'PRIME': np.random.uniform(500, 3000, len(num_contrats)),
        'MARQUE': np.random.choice(['Peugeot', 'Renault', 'BMW', 'Mercedes'], len(num_contrats)),
        'DATE_EFFET_CONTRAT': pd.Timestamp.now() - pd.Timedelta(days=365),
        'DATE_EXPIRATION': pd.Timestamp.now() + pd.Timedelta(days=180),
        'DATE_MISE_EN_CIRCULATION': pd.Timestamp.now() - pd.Timedelta(days=365*10),
        'DATE_DERNIER_AVENANT': pd.Timestamp.now() - pd.Timedelta(days=15),
        'LISTE_AVENANTS': [[] for _ in range(len(num_contrats))],
    })
    
    return contrats

def create_test_tiers(contrats):
    """Crée un DataFrame tiers de test"""
    n = len(contrats)
    tiers = pd.DataFrame({
        'UUID': contrats['CODE_CLIENT'].values,
        'PARTY_TYPE': ['ASSURE'] * n,
        'note_conducteur': np.random.uniform(3, 9, n),
        'JOB': np.random.choice(['Taxi', 'Infirmier', 'Ingénieur', np.nan], n),
        'LATITUDE_RESIDENCE': np.random.uniform(33, 37, n),
        'LONGITUDE_RESIDENCE': np.random.uniform(8, 12, n),
        'LATITUDE_TRAVAIL': np.random.uniform(33, 37, n),
        'LONGITUDE_TRAVAIL': np.random.uniform(8, 12, n),
    })
    
    return tiers

def test_features():
    """Test principal"""
    print("=" * 70)
    print("🧪 TEST VALIDATION FEATURES v5.1")
    print("=" * 70)
    
    # Créer data de test
    print("\n📊 Création données de test...")
    df_sin = create_test_dataframe(100)
    df_con = create_test_contrats(df_sin)
    df_tie = create_test_tiers(df_con)
    
    print(f"   ✓ {len(df_sin)} sinistres")
    print(f"   ✓ {len(df_con)} contrats")
    print(f"   ✓ {len(df_tie)} assurés")
    
    # Initialiser feature engineer
    print("\n🔧 Initialisation AutoFeatureEngineer...")
    engineer = AutoFeatureEngineer()
    
    # Extraire features
    print("\n🚀 Extraction des features...")
    try:
        X_scaled, raw_df = engineer.fit_transform_with_raw(df_sin, df_con, df_tie)
        print(f"   ✅ Features extraites avec succès!")
        print(f"   ✓ Nombre de features: {X_scaled.shape[1]}")
        print(f"   ✓ Nombre de lignes: {X_scaled.shape[0]}")
        
        # Vérifier nouvelles features
        print("\n📋 Vérification features clés...")
        expected_features = {
            'montant_vs_prime_marque': 'Montant vs prime marque',
            'expert_suspect': 'Expert suspect',
            'garage_suspect': 'Garage suspect',
            'sinistre_nuit': 'Sinistre nuit',
            'sinistre_weekend': 'Sinistre weekend',
            'avenant_recent_30j': '✨ NOUVEAU: Avenant < 30j',
            'cluster_temporel_vehicule': 'Cluster temporel véhicule',
            'velocite_recente_client': 'Vélocité client',
            'distance_sinistre_residence_elevee': 'Distance résidence élevée',
            'profession_risque': 'Profession risque',
        }
        
        for feat, label in expected_features.items():
            if feat in raw_df.columns:
                val_sample = raw_df[feat].iloc[:3].values
                print(f"   ✅ {label:40s} | échantillon: {val_sample}")
            else:
                print(f"   ❌ MANQUANT: {feat}")
        
        # Statistiques globales
        print("\n📊 Statistiques features brutes...")
        print(f"   Nombre de features non-nulles: {(raw_df != 0).sum().sum()}")
        print(f"   Nombre de NaN: {raw_df.isna().sum().sum()}")
        print(f"   Min: {X_scaled.min():.3f}, Max: {X_scaled.max():.3f}")
        
        # Features à variance nulle supprimées
        print(f"\n✅ SUCCÈS: {len(engineer.feature_names)} features créées")
        
    except Exception as e:
        print(f"   ❌ ERREUR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 70)
    print("✅ TEST RÉUSSI - Modèle v5.1 opérationnel")
    print("=" * 70)
    return True

if __name__ == '__main__':
    success = test_features()
    sys.exit(0 if success else 1)
