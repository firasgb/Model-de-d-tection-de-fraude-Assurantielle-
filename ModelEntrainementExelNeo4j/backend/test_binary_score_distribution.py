#!/usr/bin/env python
import pandas as pd
import numpy as np
from ml.auto_fraud_detector import AutoFraudDetector

np.random.seed(42)
n = 100
labels = np.random.choice([0, 1], size=n, p=[0.9, 0.1])

df = pd.DataFrame({
    'id': range(n),
    'is_fraud': labels,
    'amount': np.random.uniform(100, 5000, n),
    'age': np.random.randint(18, 80, n),
    'contrat_PRIME': np.random.uniform(100, 10000, n),
    'DATE_EFFET_CONTRAT': pd.date_range('2024-01-01', periods=n, freq='D'),
    'contrat_CODE_CLIENT': [f'C{i:03d}' for i in range(n)]
})

detector = AutoFraudDetector()
detector.fit(df, label_column='is_fraud', label_source='manual')

scores = detector._cached_scores
print('Mode multiclasses ?', detector._is_multiclass)
print('Label unique:', np.unique(labels))
print('Total scores:', len(scores))
print(f'Mean: {scores.mean():.2f}')
print(f'Min/max: {scores.min():.2f} / {scores.max():.2f}')
print('Count frauduleux >70:', np.sum(scores > 70))
print('Count suspect 50-70:', np.sum((scores >= 50) & (scores <= 70)))
print('Count normal <50:', np.sum(scores < 50))
print('Score distribution binned:')
for low, high in [(0,10),(10,20),(20,30),(30,40),(40,50),(50,60),(60,70),(70,80),(80,90),(90,100)]:
    if high < 100:
        cnt = np.sum((scores >= low) & (scores < high))
    else:
        cnt = np.sum((scores >= low) & (scores <= high))
    print(f'  {low}-{high}: {cnt}')
print('Some scores:', np.round(scores[:20], 1))
