🧠 Système de Détection de Fraude Assurantielle
📌 Présentation du projet

Ce projet est une application intelligente de détection de fraude dans les sinistres assurantiels, basée sur des techniques de Machine Learning, une architecture FastAPI (backend) et React (frontend), ainsi qu’une exploitation de Neo4j (graph database) pour l’analyse des relations entre entités.

L’objectif est de classifier les sinistres en :

✅ Normal
⚠️ Suspect
❌ Fraude
🎯 Objectifs
Automatiser la détection de fraude dans les assurances
Réduire les pertes financières des compagnies
Améliorer la précision des décisions d’expertise
Exploiter les relations entre assurés, véhicules et sinistres via graphes
🏗️ Architecture du projet
Frontend (React)
      │
      ▼
Backend API (FastAPI)
      │
      ├── Machine Learning Model (XGBoost / Sklearn)
      ├── Neo4j Graph Database
      └── Data Processing Layer
⚙️ Technologies utilisées
Backend
FastAPI
Python
Scikit-learn / XGBoost
Pandas / NumPy
Neo4j
Frontend
React.js
TypeScript
Axios
TailwindCSS (ou CSS classique)
Base de données
Neo4j (Graph database)
🧠 Modèle de Machine Learning

Le système utilise un modèle supervisé entraîné sur des données de sinistres :

Features : données assurantielles, véhicule, client
Modèle : classification multi-classes
Sortie :
0 → Normal
1 → Suspect
2 → Fraude

📁 Versioning des modèles :

models/versions/
├── v1_model.pkl
├── v2_model.pkl
├── scoring_config.json
└── version_history.json
🔗 Neo4j (Analyse Graphique)

Le système exploite Neo4j pour :

Identifier les relations entre clients
Détecter les clusters suspects
Analyser les connexions entre sinistres
Améliorer la détection de fraude via graphe

🚀 Lancement du projet
1️⃣ Backend (FastAPI)
cd backend
pip install -r requirements.txt
python main.py
2️⃣ Frontend (React)
cd fraud-v2-frontend
npm install
npm run dev

📊 Fonctionnalités principales
🔍 Prédiction de fraude en temps réel
📊 Dashboard d’analyse des sinistres
🧾 Historique des prédictions
🔗 Analyse des relations via Neo4j
📁 Versioning des modèles ML

📦 Structure du projet
ModelEntrainementExelNeo4j/
│
├── backend/        # API FastAPI
├── frontend/       # Interface React
├── models/         # Modèles ML versionnés
├── scripts/        # Scripts d'entraînement
├── .kilo/          # Config interne
└── README.md
