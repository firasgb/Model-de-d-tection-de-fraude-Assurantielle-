# 🚀 QUICK REFERENCE - Feature Engineering v5.1

## Fichiers Clés

```
backend/
├── ml/
│   └── auto_feature_engineering.py    ← CODE PRINCIPAL (modifié)
│       └── 67 features + NEW avenant_recent_30j
├── INDICATORS_DOCUMENTATION.md         ← DOC COMPLET (67 features)
├── CHANGELOG_v51.md                   ← RÉSUMÉ CHANGES
└── test_features_v51.py               ← TESTS
```

## 🎯 Features Clés à Retenir

### Financiers (13)
```
✨ montant_vs_prime_marque    → Montant > 10× prime_moy(marque)
✨ expert_suspect             → moy_expert > 1.5× MÉDIANE
✨ garage_suspect             → moy_garage > 1.5× MÉDIANE
✨ incoherence_age_montant    → (âge > 10 ans) AND (montant > P80)
```

### Temporels (17)
```
⏰ sinistre_nuit              → 00h00-05h59
⏰ sinistre_weekend           → Samedi/Dimanche
⏰ declaration_tardive_*      → >15j, >30j, >90j
⏰ sinistre_moins_*_apres_effet → <7j, <30j après DATE_EFFET
⏰ cluster_temporel_*         → Sinistres rapprochés
⏰ velocite_recente_*         → Accélération sinistres
```

### Fréquence (13)
```
📊 nbr_sinistres_*            → Comptage par clé (véhicule, client, expert, garage)
📊 adverse_repete             → Tiers adverse > 2 fois
📊 client_plus3/7_sinistres   → Comportement abusif 12 mois
📊 contrat_avenants_frequents → nb_avenants > 2
🆕 avenant_recent_30j         → Avenant < 30j avant sinistre
```

### Réseau (6)
```
🕸️ expert_vehicule_repete    → Même expert + véhicule
🕸️ temoin_frequent           → Témoin > 3 occurrences
🕸️ garage_taux_remplacement  → Pièces > 80%
```

### Conducteur (11)
```
👤 note_conducteur_faible     → note < 5
👤 profession_risque          → Taxi, Louage, VTC, Transport
👤 kilometrage_annuel_eleve   → > 30,000 km
👤 distance_*_elevee          → > 30 km
```

## 📐 Calculs Importants

### 1. Expert Suspect (ROBUSTE)
```python
# Utilise MÉDIANE (robuste aux outliers)
moy_expert = montants_par_expert.mean()
median_global = montants_globaux.median()
expert_suspect = moy_expert > 1.5 * median_global  # ← MÉDIANE, pas moyenne!
```

### 2. Montant vs Prime Marque (BIAIS CORRIGÉ)
```python
# Corrige biais BMW (prime 3×) vs Clio (prime 1×)
prime_moy_marque = prime.groupby(marque).mean()
montant_vs_prime_marque = totalreglement > 10 * prime_moy_marque
```

### 3. Avenant Récent (NEW)
```python
# Détecte manipulation contrat pré-fraude
delai = DATE_SURVENANCE - DATE_DERNIER_AVENANT
avenant_recent_30j = (0 <= delai <= 30 jours) ? 1 : 0
```

## 🔗 Merges Simplifiés (2 seulement)

```
sinistres
    ↓ (NUM_CONTRAT → NUMERO_POLICE)
    ↓
contrats [ajoute colonnes contrat_*]
    ↓ (CODE_CLIENT → UUID where PARTY_TYPE='ASSURE')
    ↓
tiers [ajoute colonnes assure_*]

❌ PAS de merge adverse
   → Comptage direct: IMMATRICULATION_ADVERSE.value_counts()
```

## 🤖 Poids ML Adaptatifs

```
Score Final = (Heuristique + ML_Vote) / 2
              └─ Isolation Forest
              └─ Local Outlier Factor
              └─ Elliptic Envelope

Auto-rééquilibrage quand features=NaN
Range: [0, 100]
```

## ✅ Tests Validation

```bash
# Test complet
python backend/test_features_v51.py

# Compilation
python -m py_compile backend/ml/auto_feature_engineering.py
```

**Output attendu**:
```
✅ AUTO-FEATURE v5.0: 29+ features, 100 lignes
✅ avenant_recent_30j créé
✅ TEST RÉUSSI
```

## 📊 Thresholds Reference

| Indicateur | Seuil | Type |
|-----------|-------|------|
| `montant_vs_prime_marque` | >10× | multiplier |
| `expert/garage_suspect` | >1.5× | multiplier (MÉDIANE) |
| `sinistre_moins_*j_apres_effet` | 7, 30j | jours |
| `declaration_tardive_*` | 15, 30, 90j | jours |
| `delai_cluster_temporal` | 30j | jours |
| `distance_*_elevee` | 30 km | km |
| `kilometrage_annuel_eleve` | 30,000 km | km |
| `nb_avenants_frequents` | >2 | count |
| `temoin_frequent` | >3 | count |
| `garage_remplacement` | >80% | percent |
| `client_plus7_sinistres` | ≥7 | count/12m |

## 🎯 Scoring Recommandé

```
0-40   → GREEN   (Normal)
40-60  → YELLOW  (À surveiller)
60-80  → ORANGE  (Probable fraude)
80-90  → RED     (Très probable)
90-100 → CRITICAL (Fraude confirmée)
```

## 📝 Columns à Avoir dans Input

### Sinistres
```
NUM_SINISTRE, NUM_CONTRAT, IMMATRICULATION, IMMATRICULATION_ADVERSE
DATE_SURVENANCE, DATE_DECLARATION
TOTALREGLEMENT
EXPERT_STAREX, GARAGES
adresse_sinistre
PIECES_REMPLACER
```

### Contrats
```
NUMERO_POLICE, CODE_CLIENT
PRIME, MARQUE
DATE_EFFET_CONTRAT, DATE_EXPIRATION, DATE_MISE_EN_CIRCULATION
DATE_DERNIER_AVENANT, LISTE_AVENANTS
```

### Tiers (Assurés)
```
UUID (= CODE_CLIENT)
PARTY_TYPE (= 'ASSURE')
note_conducteur, JOB
LATITUDE_RESIDENCE, LONGITUDE_RESIDENCE
LATITUDE_TRAVAIL, LONGITUDE_TRAVAIL
```

---

**v5.1 - Quick Ref**  
*Garder à portée de main lors du déploiement*
