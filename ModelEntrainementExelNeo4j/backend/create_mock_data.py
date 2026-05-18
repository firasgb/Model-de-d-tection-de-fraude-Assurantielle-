"""
Script pour créer des données de test (mock data)
Exécutez ce script pour générer des données de test si vous n'avez pas les vrais fichiers Excel
"""
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import random

print("=" * 60)
print("CREATION DE DONNEES DE TEST")
print("=" * 60)

# Créer le dossier data
data_dir = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(data_dir, exist_ok=True)

# === 1. DONNEES TIERS ===
print("\nCreation des tiers...")
np.random.seed(42)

tiers_data = {
    'UUID': list(range(1, 1001)),
    'NAME': [f'Nom{i}' for i in range(1, 1001)],
    'LASTNAME': [f'Prenom{i}' for i in range(1, 1001)],
    'ORGANIZATION_NAME': [f'Entreprise{i}' if i % 5 == 0 else None for i in range(1, 1001)],
    'CREATION_DATE': [datetime.now() - timedelta(days=random.randint(1, 1000)) for _ in range(1000)],
    'ISSUANCE_AUTHORITY': [random.choice(['Ministere', 'Police', 'Gendarmerie']) for _ in range(1000)],
    'PARTY_TYPE': [random.choice(['ASSURE', 'ADVERSE']) for _ in range(1000)],
    'JOB': [random.choice(['Chauffeur', 'Commercant', 'Fonctionnaire', 'inconnu', 'Enseignant']) for _ in range(1000)],
    'BIRTH_DATE': [datetime(1970, 1, 1) + timedelta(days=random.randint(0, 15000)) for _ in range(1000)],
    'IDENTITY_NUMBER': [f'ID{random.randint(100000, 999999)}' for _ in range(1000)],
    'TYPE': [random.choice(['morale', 'physique']) for _ in range(1000)],
    'CODE_CLIENT': [random.randint(1, 500) for _ in range(1000)]
}

tiers_df = pd.DataFrame(tiers_data)
tiers_df.to_excel(os.path.join(data_dir, 'tiers.xlsx'), index=False)
print(f"   tiers.xlsx cree ({len(tiers_df)} lignes)")

# === 2. DONNEES CONTRATS ===
print("\nCreation des contrats...")

contrats_data = {
    'ID_POLICE': list(range(1, 501)),
    'NUMERO_POLICE': [f'POL{random.randint(10000, 99999)}' for _ in range(500)],
    'TYPE_POLICE': [random.choice(['individuel', 'Collectif']) for _ in range(500)],
    'ETAT_CONTRAT': [random.choice(['FERME', 'RA']) for _ in range(500)],
    'STATUT_CONTRAT': [random.choice(['en vigueur', 'resilie', 'suspendu']) for _ in range(500)],
    'USAGE': [random.choice(['personnel', 'taxi', 'loue', 'commercial']) for _ in range(500)],
    'DATE_SOUSCRIPTION': [datetime(2020, 1, 1) + timedelta(days=random.randint(0, 1000)) for _ in range(500)],
    'DATE_EFFET_CONTRAT': [datetime(2020, 1, 1) + timedelta(days=random.randint(0, 1000)) for _ in range(500)],
    'DATE_EXPIRATION': [datetime(2024, 1, 1) + timedelta(days=random.randint(0, 365)) for _ in range(500)],
    'PACK': [random.choice(['Securite', 'Securite +', 'Serenite', 'Super Securite']) for _ in range(500)],
    'PRODUIT': [random.choice([" Individuel a la carte", 'Trik Esslama', 'Flotte', 'Frontiere']) for _ in range(500)],
    'PRIME': np.random.uniform(500, 5000, 500).tolist(),
    'MARQUE': [random.choice(['Renault', 'Peugeot', 'Citroen', 'Volkswagen', 'Toyota']) for _ in range(500)],
    'MODELE': [random.choice(['Clio', '208', 'C3', 'Golf', 'Yaris']) for _ in range(500)],
    'IMMATRICULATION': [f'{random.randint(100, 999)}TU{random.randint(1000, 9999)}' for _ in range(500)],
    'POINT_VENTE': [random.choice(['Agence1', 'Agence2', 'Agence3', 'Agence4']) for _ in range(500)],
    'CODE_CLIENT': [random.randint(1, 500) for _ in range(500)],
    'DATE_MISE_EN_CIRCULATION': [datetime(2015, 1, 1) + timedelta(days=random.randint(0, 2000)) for _ in range(500)],
    'LISTE_AVENANTS': [','.join(random.choice(['Avenant1', 'Avenant2', 'Avenant3']) for _ in range(random.randint(0, 3))) for _ in range(500)],
    'LISTE_GARANTIES': ['GAR1,GAR2,GAR3' for _ in range(500)]
}

contrats_df = pd.DataFrame(contrats_data)
contrats_df.to_excel(os.path.join(data_dir, 'contrats.xlsx'), index=False)
print(f"   contrats.xlsx cree ({len(contrats_df)} lignes)")

# === 3. DONNEES SINISTRES ===
print("\nCreation des sinistres...")

# Créer des patterns frauduleux intentionnels
sinistres_data = {
    'ID_DECLARATION': list(range(1, 1001)),
    'NUM_DECLARATION': list(range(1, 1001)),
    'CDL': [random.choice(['AUTO HORS IDA', 'AUTO IDA', 'AUTO CORPOREL C', 'AUTO CORPOREL T']) for _ in range(1000)],
    'IMMATRICULATION': [f'{random.randint(100, 999)}TU{random.randint(1000, 9999)}' for _ in range(1000)],
    'TYPE_DECLARATION': [1] * 1000,
    'DATE_SURVENANCE': [datetime(2024, 1, 1) + timedelta(days=random.randint(0, 300)) for _ in range(1000)],
    'ORIGINE_DECLARATION': [random.choice(['Agence', 'Telephone', 'Internet']) for _ in range(1000)],
    'TYPE_SINISTRE': [random.choice(['Collision', 'Vol', 'Incendie', 'Bris de glace']) for _ in range(1000)],
    'NUM_SINISTRE': [f'SIN{random.randint(10000, 99999)}' for _ in range(1000)],
    'CAS_BAREME': [random.choice([f'Cas {i:02d}' for i in range(1, 26)]) for _ in range(1000)],
    'DESCRIPTION_INCIDENT': [random.choice(['Collision avant', 'Accident intersection', 'Manoeuvre parking', 'Toupie']) for _ in range(1000)],
    'IMMATRICULATION_ADVERSE': [f'{random.randint(100, 999)}TU{random.randint(1000, 9999)}' for _ in range(1000)],
    'ACTEURS_IMPLIQUES': [random.choice(['Conducteur', 'Pieton', 'Passager']) for _ in range(1000)],
    'USAGE_CODE': [random.choice(['U1', 'U2', 'U3']) for _ in range(1000)],
    'USAGE_LIBELLE': [random.choice(['Usage personnel', 'Taxi', 'Location']) for _ in range(1000)],
    'DAMAGE_TYPE': [random.choice(['Materiel', 'Corporel']) for _ in range(1000)],
    'INSPECTION_MISSIONS': [random.choice(['inconnu', 'Effectuee', 'Non necessaire']) for _ in range(1000)],
    'STATUS': [random.choice(['Ouvert', 'Ferme', 'Ferme sans suite']) for _ in range(1000)],
    'AFFECTED_WARRANTIES': ['GAR1,GAR2' for _ in range(1000)],
    'REPORTING_AGENCY': [random.randint(1, 10) for _ in range(1000)],
    'GARAGES': [random.choice(['GarageA', 'GarageB', 'GarageC', 'inconnu']) for _ in range(1000)],
    'EXPERT_STAREX': [random.choice(['Expert1', 'Expert2', 'Expert3', 'inconnu']) for _ in range(1000)],
    'PIECES_REMPLACER': [','.join(random.choice(['Pare-brise', 'Phare', 'Porte']) for _ in range(random.randint(0, 3))) for _ in range(1000)]
}

# Ajouter les colonnes manquantes
sinistres_data['DATE_DECLARATION'] = []
sinistres_data['NUM_CONTRAT'] = []
sinistres_data['TOTALREGLEMENT'] = []

# Générer les dates de déclaration avec décalage
date_surv_list = sinistres_data['DATE_SURVENANCE']
for i in range(1000):
    date_surv = date_surv_list[i]
    decalage = random.randint(0, 60)  # Décalage de 0 à 60 jours
    sinistres_data['DATE_DECLARATION'].append(date_surv + timedelta(days=decalage))
    sinistres_data['NUM_CONTRAT'].append(f'POL{random.randint(10000, 99999)}')

    # Créer des patterns frauduleux intentionnels
    if i % 20 == 0:  # 5% de sinistres suspects (montant élevé)
        sinistres_data['TOTALREGLEMENT'].append(random.uniform(5000, 20000))
    elif i % 50 == 0:  # 2% de sinistres très suspects
        sinistres_data['TOTALREGLEMENT'].append(random.uniform(3000, 10000))
    else:
        sinistres_data['TOTALREGLEMENT'].append(random.uniform(500, 5000))

sinistres_df = pd.DataFrame(sinistres_data)
sinistres_df.to_excel(os.path.join(data_dir, 'sinistres.xlsx'), index=False)
print(f"   sinistres.xlsx cree ({len(sinistres_df)} lignes)")

print("\n" + "=" * 60)
print("DONNEES DE TEST CREEES AVEC SUCCES!")
print("=" * 60)
print(f"\nLes fichiers sont dans: {data_dir}")
print("\nLancez maintenant: python run.py")
print("=" * 60)
