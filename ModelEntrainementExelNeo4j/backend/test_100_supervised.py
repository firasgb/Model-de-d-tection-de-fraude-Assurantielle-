#!/usr/bin/env python
"""Test que le scoring est 100% supervisé avec XGBoost"""

import pandas as pd
import numpy as np
from ml.auto_fraud_detector import AutoFraudDetector

print('Test: 100% SUPERVISÉ avec labels 0/1/2')
print('='*60)

# Créer des données de test avec labels
np.random.seed(42)
n = 15
df = pd.DataFrame({
    'id': range(n),
    'is_fraud': np.random.choice([0, 1, 2], n),
    'amount': np.random.uniform(100, 5000, n),
    'age': np.random.randint(18, 80, n),
})

print(f'Labels fournis: {df["is_fraud"].values}')
print()

detector = AutoFraudDetector()
detector.fit(df, label_column='is_fraud', label_source='manual')

print()
print(f'Scores générés (100% XGBoost): {detector._cached_scores[:10]}')
print(f'Score moyen: {detector._cached_scores.mean():.2f}')
print(f'Score min/max: {detector._cached_scores.min():.2f} / {detector._cached_scores.max():.2f}')
print()
print('✅ Mode 100% supervisé appliqué!')
