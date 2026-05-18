# 📋 MAPPING COLONNES - Input/Output v5.1

## 📥 COLONNES REQUISES EN INPUT

### TABLE: `sinistres` (obligatoire)

```sql
-- Clés
NUM_SINISTRE              VARCHAR(50)      -- Identifiant sinistre
NUM_CONTRAT               VARCHAR(50)      -- FK→contrats.NUMERO_POLICE
NUM_DECLARATION           VARCHAR(50)      -- Optionnel

-- Acteurs
EXPERT_STAREX             VARCHAR(100)     -- Expert (ou NULL/INCONNU)
GARAGES                   VARCHAR(100)     -- Garage (ou NULL/INCONNU)
IMMATRICULATION           VARCHAR(20)      -- Véhicule assuré
IMMATRICULATION_ADVERSE   VARCHAR(20)      -- Véhicule tiers

-- Dates (YYYY-MM-DD HH:MM:SS)
DATE_SURVENANCE           DATETIME         -- Date+heure sinistre
DATE_DECLARATION          DATETIME         -- Date déclaration
PIECES_REMPLACER          INT/VARCHAR      -- 0/1 ou liste

-- Montants
TOTALREGLEMENT            DECIMAL(12,2)    -- Montant réglé

-- Lieu
adresse_sinistre          VARCHAR(500)     -- Adresse texte ou GPS
```

### TABLE: `contrats` (fortement recommandé)

```sql
-- Clés
NUMERO_POLICE             VARCHAR(50)      -- PK, FK←sinistres.NUM_CONTRAT
CODE_CLIENT               INT/VARCHAR      -- FK→tiers.UUID

-- Caractéristiques assurance
PRIME                     DECIMAL(12,2)    -- Prime annuelle
MARQUE                    VARCHAR(50)      -- Marque véhicule (Peugeot, Renault, BMW...)
USAGE                     VARCHAR(100)     -- Usage (ex: "420_Taxi individuelle")

-- Dates contrat
DATE_EFFET_CONTRAT        DATE             -- Prise d'effet
DATE_EXPIRATION           DATE             -- Fin couverture
DATE_MISE_EN_CIRCULATION  DATE             -- 1ère mise en circulation

-- Avenants
DATE_DERNIER_AVENANT      DATE             -- ← CRITIQUE pour avenant_recent_30j
LISTE_AVENANTS            JSON/ARRAY/TEXT  -- Ex: ["avenant_1", "avenant_2"]

-- Optionnel
ETAT_CONTRAT              VARCHAR(20)      -- ACTIF, RESILIE, etc.
STATUT_CONTRAT            VARCHAR(20)      -- SUSPENDU, etc.
KILOMETRAGE               INT               -- Kilométrage estimé
```

### TABLE: `tiers` (fortement recommandé)

```sql
-- Clés (join)
UUID                      INT/VARCHAR      -- PK, FK←contrats.CODE_CLIENT
PARTY_TYPE                VARCHAR(20)      -- ASSURE, TIERS, etc.

-- Conducteur
note_conducteur           DECIMAL(3,1)     -- 0-10
JOB                       VARCHAR(100)     -- Profession/métier

-- Localisations
LATITUDE_RESIDENCE        DECIMAL(10,8)    -- GPS résidence
LONGITUDE_RESIDENCE       DECIMAL(11,8)    
LATITUDE_TRAVAIL          DECIMAL(10,8)    -- GPS lieu de travail
LONGITUDE_TRAVAIL         DECIMAL(11,8)    
adresse_residence         VARCHAR(500)     -- Adresse texte
adresse_travail           VARCHAR(500)     -- Adresse texte
```

---

## 📤 COLONNES EN OUTPUT

### Format: DataFrame avec 67 Features

#### Financières (13)
```
num_TOTALREGLEMENT              FLOAT  -- Montant brut
std_TOTALREGLEMENT              FLOAT  -- Z-score
ratio_montant_moyen             FLOAT
ratio_montant_median            FLOAT
zscore_montant                  FLOAT
montant_3std_suspect            INT    -- 0/1
montant_vs_prime_marque         INT    -- 0/1 ← Corrige biais marque
ratio_montant_vs_expert         FLOAT
ratio_montant_vs_garage         FLOAT
ratio_montant_vs_client         FLOAT
ratio_montant_pv_global         FLOAT
montant_cumule_vehicule         FLOAT
incoherence_age_montant         INT    -- 0/1
```

#### Temporelles (17)
```
sinistre_nuit                   INT    -- 0/1 (00h-05h59)
sinistre_weekend                INT    -- 0/1 (Sat/Sun)
declaration_apres_weekend       INT    -- 0/1 (Mon/Tue)
decalage_survenance_declaration_jours  FLOAT  -- Jours
declaration_tardive_15j         INT    -- 0/1
declaration_tardive_30j         INT    -- 0/1
declaration_tres_tardive_90j    INT    -- 0/1
jours_apres_effet               FLOAT
sinistre_moins_7j_apres_effet   INT    -- 0/1
sinistre_moins_30j_apres_effet  INT    -- 0/1
jours_avant_expiration          FLOAT
sinistre_moins_7j_expiration    INT    -- 0/1
sinistre_moins_30j_expiration   INT    -- 0/1
delai_moyen_sinistres           FLOAT  -- Jours
cluster_temporel_vehicule       INT    -- 0/1
cluster_temporel_client         INT    -- 0/1
velocite_recente_vehicule       FLOAT  -- Ratio
velocite_recente_client         FLOAT  -- Ratio
```

#### Fréquence (13)
```
nbr_sinistres_vehicule          INT    -- Comptage antérieurs
nbr_sinistres_client            INT    -- Comptage antérieurs
nbr_sinistres_contrat           INT    -- Comptage antérieurs
nbr_sinistres_expert            INT    -- Comptage (tous)
nbr_sinistres_garage            INT    -- Comptage (tous)
nbr_sinistres_adverse           INT    -- Comptage immatriculations
adverse_repete                  INT    -- 0/1
sinistres_client_12mois         INT    -- Comptage glissant
client_plus3_sinistres_12m      INT    -- 0/1
client_plus7_sinistres_12m      INT    -- 0/1
nb_avenants_contrat             INT    -- Comptage
contrat_avenants_frequents      INT    -- 0/1 (>2)
avenant_recent_30j              INT    -- 0/1 🆕 NEW!
```

#### Réseau (6)
```
freq_expert_meme_vehicule       INT    -- Comptage combinaison
expert_vehicule_repete          INT    -- 0/1
freq_temoin                     INT    -- Comptage
temoin_frequent                 INT    -- 0/1 (>3)
sinistre_frontiere              INT    -- 0/1
garage_taux_remplacement_eleve  INT    -- 0/1
```

#### Conducteur (11)
```
note_conducteur                 FLOAT  -- 0-10
note_conducteur_faible          INT    -- 0/1 (<5)
profession_risque               INT    -- 0/1
kilometrage_annuel              FLOAT  -- km/an
kilometrage_annuel_eleve        INT    -- 0/1 (>30k)
kilometrage_vs_moyenne          FLOAT
distance_sinistre_residence_km  FLOAT  -- Km
distance_sinistre_residence_elevee  INT  -- 0/1 (>30km)
distance_sinistre_travail_km    FLOAT  -- Km
distance_sinistre_travail_elevee    INT  -- 0/1 (>30km)
distance_sinistre_residence_identical  INT  -- 0/1
```

#### Profil (2)
```
nb_services_operationnels       INT    -- Comptage
sinistre_grave_sans_services    INT    -- 0/1
```

#### Expert/Garage (3)
```
expert_suspect                  INT    -- 0/1
expert_cout_anormal             INT    -- 0/1
garage_suspect                  INT    -- 0/1
```

#### Âge (1)
```
age_vehicule_ans                FLOAT  -- Années
```

---

## 🔧 TRANSFORMATIONS INTERNES

### Normalisation
```
X_scaled = StandardScaler().fit_transform(features_brutes)
Range: [-∞, +∞] (centré réduit)
```

### Gestion NaN
- ✅ Remplacé par 0 (nulle valeur)
- ✅ Inf / -Inf remplacé par 0
- ✅ Variance nulle supprimée

### Détails Colonnes Calculées

#### expert_suspect
```python
# Par expert (EXPERT_STAREX)
moyenne_expert = montants.groupby(expert).mean()
median_global = montants.median()
expert_suspect = moyenne_expert > 1.5 * median_global
```

#### montant_vs_prime_marque
```python
# Par marque (contrat_MARQUE)
prime_moy_marque = prime.groupby(marque).mean()
flag = totalreglement > 10 * prime_moy_marque
```

#### Distances Géographiques
```python
# 1. GPS bruts si disponibles
# 2. Géocodage textuel TunisiaGeocoder
# 3. Comparaison texte adresses si pas GPS
Formule Haversine: d = 2*R*arcsin(sqrt(sin²(Δlat/2) + cos(lat1)*cos(lat2)*sin²(Δlon/2)))
```

#### Clusters Temporels
```python
# Délai moyen entre sinistres (même clé)
delai_moyen = mean(Δt entre sinistres successifs)
cluster = delai_moyen <= 30 jours
```

---

## 🚀 EXEMPLE UTILISATION

```python
from ml.auto_feature_engineering import AutoFeatureEngineer

# Charger données
sinistres = pd.read_csv('sinistres.csv')
contrats = pd.read_csv('contrats.csv')
tiers = pd.read_csv('tiers.csv')

# Extraire features
engineer = AutoFeatureEngineer()
X_scaled, X_raw = engineer.fit_transform_with_raw(
    sinistres, contrats, tiers
)

print(f"Shape: {X_scaled.shape}")
# Output: (n_sinistres, 67)

# Features brutes (avant normalisation)
print(X_raw.columns.tolist())
# Voir toutes les colonnes ci-dessus
```

---

## ⚠️ COLONNES OPTIONNELLES

Si manquantes → Feature remplie par 0 (défaut sûr):

```
Plutôt recommandées (sinon comportement par défaut):
- LATITUDE/LONGITUDE (GPS → fallback géocodeur)
- DATE_DERNIER_AVENANT (sinon 0 pour avenant_recent_30j)
- JOB / USAGE (profession_risque)
- PIECES_REMPLACER (garage_taux_remplacement)
```

---

## 📊 DONNÉES DE TEST

Voir `test_features_v51.py` pour exemple complet de création de données.

```python
# Mini dataset généré avec:
df_sin = pd.DataFrame(...)  # 100 lignes
df_con = pd.DataFrame(...)  # 97 contrats
df_tie = pd.DataFrame(...)  # 97 assurés

# Résultat: 29+ features actives (avec données aléatoires)
```

---

**v5.1 - Mapping Colonnes**  
*À jour avec version courante*
