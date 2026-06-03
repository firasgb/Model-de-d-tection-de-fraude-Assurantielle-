import sys, os, json
# Ensure backend dir is on sys.path when script invoked by full path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
from utils.data_loader import DataLoader
from ml.auto_fraud_detector import AutoFraudDetector
import numpy as np

# Thresholds provided by user
normal_max = 49.99
suspect_min = 50.0
fraud_threshold = 70.0

loader = DataLoader()
loaded = loader.load_all()
if not loaded:
    print(json.dumps({"loaded": False, "message": "Aucun fichier sinistres chargé depuis backend/data"}, indent=2))
    sys.exit(0)
else:
    sin = loader.get_sinistres()
    contrats = loader.get_contrats()
    tiers = loader.get_tiers()
    detector = AutoFraudDetector()
    detector.fit(sin, contrats, tiers, sample_fraction=1.0, progress_callback=lambda *a, **k: None)
    scores = detector._cached_scores
    arr = np.array(scores)
    n = arr.size
    fraude = int((arr > fraud_threshold).sum())
    suspect = int(((arr >= suspect_min) & (arr <= fraud_threshold)).sum())
    normal = int((arr < suspect_min).sum())
    result = {
        "loaded": True,
        "total": int(n),
        "fraude": fraude,
        "suspect": suspect,
        "normal": normal,
        "fraude_pct": round(fraude / n * 100, 2) if n else None,
        "suspect_pct": round(suspect / n * 100, 2) if n else None,
        "normal_pct": round(normal / n * 100, 2) if n else None,
    }
    print(json.dumps(result, indent=2))
    # sample preview
    sample = []
    for i, sc in enumerate(arr[:10]):
        label = 1 if sc > fraud_threshold else (2 if sc >= suspect_min else 0)
        sample.append({"index": int(i), "score": float(sc), "is_fraud": int(label)})
    print('\nSample mapping (first 10 rows):')
    print(json.dumps(sample, indent=2))
