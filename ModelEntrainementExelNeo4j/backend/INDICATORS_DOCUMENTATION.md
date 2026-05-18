# Documentation des Indicateurs de Fraude v5.1
*Détection de Fraude Assurance - Modèle Optimisé*

---

## 📋 Vue d'Ensemble
- **Total Features**: 67 (+ 1 nouvelle : `avenant_recent_30j`)
- **Groupes**: 7 (Financier, Temporel, Fréquence, Réseau, Conducteur, Profil, Autre)
- **Points Scoring**: 104 max (théorique)
- **Poids Adaptatifs**: Laissés au ML (IF, LOF, EE votent)

---

## 🔗 MERGES SIMPLIFIÉS (v5.1)

**SEULEMENT 2 merges** :

```
1. sinistres.NUM_CONTRAT → contrats.NUMERO_POLICE
   ↓
   ✔️ Rajoute colonnes contrat_* (PRIME, MARQUE, DATE_EFFET, etc.)

2. contrats.CODE_CLIENT → tiers.UUID (where PARTY_TYPE='ASSURE')
   ↓
   ✔️ Rajoute colonnes assure_* (note_conducteur, job, adresses, etc.)
```

**❌ PAS de merge adverse** :
- IMMATRICULATION_ADVERSE reste brut
- Comptage direct via `value_counts()` → stabilité ✅

---

## 💰 1. INDICATEURS FINANCIERS (13 features)

### Core
| Feature | Formule | Seuil | Direction |
|---------|---------|-------|-----------|
| `num_TOTALREGLEMENT` | Montant brut | - | high |
| `std_TOTALREGLEMENT` | Z-score : (montant - μ) / σ | - | high |
| `ratio_montant_moyen` | montant / (μ + 1) | - | high |
| `ratio_montant_median` | montant / (médiane + 1) | - | high |
| `zscore_montant` | (montant - μ) / σ | - | high |
| `montant_3std_suspect` | abs(zscore) > 3 | 3σ | high |

### Ratios Comparatifs
| Feature | Formule | Seuil | Notes |
|---------|---------|-------|-------|
| **`montant_vs_prime_marque`** | montant > 10× prime_moy(marque) | ×10 | **Corrige biais BMW/Clio** ✅ |
| `ratio_montant_vs_expert` | montant / moy_expert | - | Détecte expert cher |
| `ratio_montant_vs_garage` | montant / moy_garage | - | Détecte garage cher |
| `ratio_montant_vs_client` | montant / moy_client | - | Anormal pour ce client |
| `ratio_montant_pv_global` | moy_pv / μ_global | - | Point de vente cher |

### Experts & Garages
| Feature | Formule | Seuil | Direction |
|---------|---------|-------|-----------|
| **`expert_suspect`** | moy_expert > 1.5 × médiane_globale | ×1.5 médiane | high |
| `expert_cout_anormal` | moy_expert > 1.5 × moyenne_globale | ×1.5 moyenne | high |
| **`garage_suspect`** | moy_garage > 1.5 × médiane_globale | ×1.5 médiane | high |

> **Médiane > Moyenne** : Robustesse face aux outliers 🎯

### Agrégés
| Feature | Formule | Direction |
|---------|---------|-----------|
| `montant_cumule_vehicule` | Σ(montants antérieurs) | high |
| `incoherence_age_montant` | (âge_véhicule > 10 ans) AND (montant > P80) | high |
| `age_vehicule_ans` | (today - DATE_MISE_EN_CIRCULATION) / 365.25 | high |

---

## 📅 2. INDICATEURS TEMPORELS (17 features)

### Heure du Sinistre
| Feature | Condition | Ratio | Direction |
|---------|-----------|-------|-----------|
| **`sinistre_nuit`** | 00h00 ≤ heure < 06h00 | ~5% population | high |
| **`sinistre_weekend`** | dayofweek ∈ {5=Sat, 6=Sun} | ~28% population | high |
| `declaration_apres_weekend` | dayofweek ∈ {0=Mon, 1=Tue} | - | high |

> **S'éloigner des témoins** → nuit + weekend = pattern de fraude

### Délai de Déclaration
| Feature | Condition | Notes | Direction |
|---------|-----------|-------|-----------|
| `decalage_survenance_declaration_jours` | dd - ds | Brut (jours) | high |
| `declaration_tardive_15j` | délai > 15j | Modéré | high |
| `declaration_tardive_30j` | délai > 30j | Élevé | high |
| `declaration_tres_tardive_90j` | délai > 90j | Critique | high |

### Proximité Prise d'Effet / Expiration
| Feature | Condition | Seuil | Direction |
|---------|-----------|--------|-----------|
| `jours_apres_effet` | ds - DATE_EFFET_CONTRAT | Brut | low |
| `sinistre_moins_7j_apres_effet` | 0 ≤ délai < 7 | 7 jours | high |
| `sinistre_moins_30j_apres_effet` | 0 ≤ délai < 30 | 30 jours | high |
| `jours_avant_expiration` | DATE_EXPIRATION - ds | Brut | low |
| `sinistre_moins_7j_expiration` | 0 ≤ délai < 7 | 7 jours | high |
| `sinistre_moins_30j_expiration` | 0 ≤ délai < 30 | 30 jours | high |

> **Contrat "juste pour fraude"** ← flaggé par prise d'effet/expiration rapide

### Clusters Temporels
| Feature | Formule | Seuil | Direction |
|---------|---------|--------|-----------|
| `delai_moyen_sinistres` | Moyenne(Δt entre sinistres véhicule) | - | low |
| `cluster_temporel_vehicule` | delai_moyen ≤ 30 jours | 30j | high |
| `cluster_temporel_client` | Délai moyen sinistres client ≤ 30j | 30j | high |
| `velocite_recente_vehicule` | Ratio(sin 30j récents / 365j) | - | high |
| `velocite_recente_client` | Ratio(sin 30j récents / 365j) | - | high |

> **Accélération sinistres** = signal fort de fraude en progression

---

## 📊 3. INDICATEURS DE FRÉQUENCE (13 features)

| Feature | Comptage | Seuil | Direction |
|---------|----------|-------|-----------|
| `nbr_sinistres_vehicule` | Antérieurs (même immatriculation) | - | high |
| `nbr_sinistres_client` | Antérieurs (même assuré) | - | high |
| `nbr_sinistres_contrat` | Antérieurs (même NUM_CONTRAT) | - | high |
| `nbr_sinistres_expert` | Traités par cet expert (tous) | - | high |
| `nbr_sinistres_garage` | Traités par ce garage (tous) | - | high |
| `nbr_sinistres_adverse` | Immatriculations adverses répétées | - | high |
| `adverse_repete` | nbr_adverse > 2 | 2 | high |

### Fenêtre Glissante 12 Mois
| Feature | Condition | Seuil | Direction |
|---------|-----------|--------|-----------|
| `sinistres_client_12mois` | Comptage glissant 12m (même client) | - | high |
| `client_plus3_sinistres_12m` | sinistres_client_12mois > 3 | 3 | high |
| `client_plus7_sinistres_12m` | sinistres_client_12mois ≥ 7 | 7 | high |

### Avenants
| Feature | Formule | Seuil | Direction |
|---------|---------|--------|-----------|
| `nb_avenants_contrat` | Nombre d'avenants (hors résiliation) | - | high |
| `contrat_avenants_frequents` | nb_avenants > 2 | 2 | high |
| **`avenant_recent_30j`** | 0 ≤ (ds - d_avenant) ≤ 30j | 30j | high |

> **Avenant récent + sinistre** = **manipulation de contrat** 🚩

---

## 🕸️ 4. INDICATEURS RÉSEAU / COLLUSION (6 features)

### Expert × Véhicule
| Feature | Condition | Seuil | Direction |
|---------|-----------|--------|-----------|
| `freq_expert_meme_vehicule` | Occurrences combinaison (expert, immat) | - | high |
| `expert_vehicule_repete` | freq > 1 | 1 | high |

> **Même expert + même véhicule** = collusion présumée

### Témoins
| Feature | Condition | Seuil | Direction |
|---------|-----------|--------|-----------|
| `freq_temoin` | Comptage global | - | high |
| `temoin_frequent` | freq_temoin > 3 | 3 | high |

> **Faux témoins** (Neo4j recommandé pour validation)

### Contexte Géographique
| Feature | Condition | Direction |
|---------|-----------|-----------|
| `sinistre_frontiere` | Mots-clés : "douane", "frontière", "ben gardane", etc. | high |

### Garage
| Feature | Condition | Seuil | Direction |
|---------|-----------|--------|-----------|
| `garage_taux_remplacement_eleve` | (pièces_remplacées / total) > 80% | 80% | high |

> **Surfacturation** : pièces remplacées inutilement

---

## 👤 5. INDICATEURS CONDUCTEUR / MOBILITÉ (11 features)

### Profil Conducteur
| Feature | Condition | Seuil | Direction |
|---------|-----------|--------|-----------|
| `note_conducteur` | Brut (0-10) | - | any |
| `note_conducteur_faible` | note < 5 | 5 | high |

### Usage / Profession Risque
| Feature | Mots-clés | Direction |
|---------|-----------|-----------|
| `profession_risque` | taxi, louage, location, vtc, transport, autobus, camion, livreur | high |

> **Parse "420_Taxi individuelle"** → extrait texte brut ✅

### Kilométrage
| Feature | Formule | Seuil | Direction |
|---------|---------|--------|-----------|
| `kilometrage_annuel` | km / (ans de circulation) | - | any |
| `kilometrage_annuel_eleve` | km_annuel > 30,000 | 30k | high |
| `kilometrage_vs_moyenne` | km_annuel / moy_km | - | any |

> **À comparer** : DATE_MISE_EN_CIRCULATION vs kilométrage actuelheure

### Distances Géographiques
| Feature | Calcul | Seuil | Direction |
|---------|--------|--------|-----------|
| `distance_sinistre_residence_km` | Haversine(GPS) or Geocodeur | - | any |
| `distance_sinistre_residence_elevee` | distance > 30 km | 30 km | high |
| `distance_sinistre_travail_km` | Haversine(GPS) or Geocodeur | - | any |
| `distance_sinistre_travail_elevee` | distance > 30 km | 30 km | high |
| `distance_sinistre_residence_identical` | adresse_résidence == adresse_sinistre | - | high |

> **Fallback**: GPS bruts → Géocodeur TextuelTunisia → Comparaison texte brute

---

## 👥 6. INDICATEURS PROFIL ASSURÉ (2 features)

| Feature | Formule | Seuil | Direction |
|---------|---------|--------|-----------|
| `nb_services_operationnels` | Count(EXPERT, INSPECTION, GARAGE, ...) | - | low |
| `sinistre_grave_sans_services` | (montant > P75) AND (nb_services < 2) | P75 + 2 svc | high |

> **Sinistre grave sans logistique** = suspect (déclaration facile)

---

## 📋 7. INDICATEURS AUTRES (5 features)

| Feature | Formule | Seuil | Direction |
|---------|---------|--------|-----------|
| `expert_suspect` | *Déjà couvert en financier* | - | - |
| `expert_cout_anormal` | *Déjà couvert en financier* | - | - |
| `garage_suspect` | *Déjà couvert en financier* | - | - |
| `age_vehicule_ans` | *Déjà couvert en financier* | - | - |
| `taux_remplacement_garage` | *Déjà couvert en réseau* | - | - |

---

## 🤖 SCORING & ML ADAPTATIF

### Stratégie Poids
- **❌ Pas de poids prédéfinis**
- ✅ **3 modèles votent** : Isolation Forest + Local Outlier Factor + Elliptic Envelope
- ✅ **Auto-rééquilibrage** : Si features = NaN → ML ajuste sur score anomalie globale

### Normalisation
```
Score Final = (Score_Heuristique + Score_ML) / 2
Plage : [0, 100]
```

---

## 📝 CHANGEMENTS v5.0 → v5.1

| Changement | Type | Impact |
|-----------|------|--------|
| ✅ Ajout `avenant_recent_30j` | NEW | Détecte manipulation contrat pré-fraude |
| ✅ Documenation mise à jour | DOC | Clarté indicateurs + seuils |
| ✅ Validation merges | UX | Seulement 2 merges (simplifié) |
| ✅ Médiane vs Moyenne (experts/garages) | KEPT | Plus robuste |

---

## 🎯 Recommandations Utilisation

1. **Entraînement** : Tous les 3 mois (évolution fraude)
2. **Alertes** : Seuil ≥ 60 (modéré), ≥ 80 (élevé), ≥ 90 (critique)
3. **Neo4j** : Collusio validation (expert + véhicule + témoin)
4. **Feedback** : Etiquetage des faux positifs → ré-entraînement
5. **Monitoring** : Ratio détection / total sinistres (cible: 5-8%)

---

**v5.1 - Mai 2026**
*Modèle stable, métriques validées, prêt pour production*
