#!/usr/bin/env python
import pandas as pd
import numpy as np
from ml.auto_fraud_detector import AutoFraudDetector

np.random.seed(0)
n = 50
labels = np.random.choice([0, 1], size=n, p=[0.85, 0.15])

df = pd.DataFrame({
    'id': range(n),
    'is_fraud': labels,
    'amount': np.random.uniform(100, 5000, n),
    'age': np.random.randint(18, 80, n),
    'contrat_PRIME': np.random.uniform(100, 10000, n),
    'DATE_EFFET_CONTRAT': pd.date_range('2024-01-01', periods=n, freq='D'),
    'contrat_CODE_CLIENT': [f'C{i:03d}' for i in range(n)]
})

# Entraîner
D = AutoFraudDetector()
D.fit(df, label_column='is_fraud', label_source='manual')

# Préparer un DataFrame non étiqueté (meme structure sans is_fraud)
new_df = df.drop(columns=['is_fraud']).iloc[:10].copy()
scored = D.score_df(new_df)
print(scored[["id","score_suspicion","statut_fraude"]])
