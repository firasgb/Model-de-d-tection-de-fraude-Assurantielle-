#!/usr/bin/env python3
import os
import sys
import json
import argparse
import numpy as np

# Add repo root to path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

from utils.data_loader import DataLoader
from ml.auto_fraud_detector import AutoFraudDetector

VERSIONS_DIR = os.path.join(ROOT, 'models', 'versions')
SCORING_CFG = os.path.join(VERSIONS_DIR, 'scoring_config.json')

DATA_DTYPE = {
    'NUM_SINISTRE': 'string',
    'NUM_CONTRAT': 'string',
    'IMMATRICULATION': 'string',
    'CDL': 'string',
    'STATUS': 'string',
    'TYPE_SINISTRE': 'string',
    'EXPERT_STAREX': 'string',
    'GARAGES': 'string',
}


def load_scoring_cfg():
    try:
        with open(SCORING_CFG, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print('Could not read scoring_config.json:', e)
        return None


def load_versioned_data(tag: str, data_dir: str):
    sinistres_path = os.path.join(data_dir, f'sinistres_{tag}.xlsx')
    contrats_path = os.path.join(data_dir, f'contrats_{tag}.xlsx')
    tiers_path = os.path.join(data_dir, f'tiers_{tag}.xlsx')

    for path, label in [
        (sinistres_path, 'sinistres'),
        (contrats_path, 'contrats'),
        (tiers_path, 'tiers'),
    ]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Versioned file missing: {label} -> {path}")

    print(f"Loading versioned dataset tag={tag}")
    sin = DataLoader._read_excel_robust(sinistres_path, f'sinistres_{tag}.xlsx', dtype=DATA_DTYPE)
    contrats = DataLoader._read_excel_robust(contrats_path, f'contrats_{tag}.xlsx')
    tiers = DataLoader._read_excel_robust(tiers_path, f'tiers_{tag}.xlsx')

    return sin, contrats, tiers


def main(sample_n=None, sample_fraction=1.0, data_tag=None):
    scoring = load_scoring_cfg()
    if scoring is None:
        print('No scoring config available, aborting')
        return

    loader = DataLoader()
    if data_tag:
        sin, contrats, tiers = load_versioned_data(data_tag, loader.data_dir)
    else:
        loader.load_all()
        sin = loader.get_sinistres()
        contrats = loader.get_contrats()
        tiers = loader.get_tiers()

    if sample_fraction < 1.0:
        sin = sin.sample(frac=sample_fraction, random_state=42)
    elif sample_n is not None and len(sin) > sample_n:
        sin = sin.head(sample_n)

    print(f"Using {len(sin)} sinistres for training (sample_fraction={sample_fraction}, sample_n={sample_n}, data_tag={data_tag})")

    detector = AutoFraudDetector()

    try:
        payload = {}
        if 'group_weights' in scoring:
            payload['group_weights'] = scoring['group_weights']
        if 'indicator_weights' in scoring:
            payload['indicator_weights'] = scoring['indicator_weights']
        if 'thresholds' in scoring:
            payload['thresholds'] = scoring['thresholds']
        if payload:
            detector.update_config(payload)
            print('Applied scoring_config.json to detector.config')
    except Exception as e:
        print('Error applying scoring config:', e)

    detector.heuristic_weight = 1.0
    detector.ml_weight = 0.0
    print('Set heuristic_weight=1.0 and ml_weight=0.0')

    detector.fit(sin, contrats, tiers, sample_fraction=1.0, save_version=False)

    arr = detector._cached_scores
    compact = detector._cached_compact
    heur = np.array([c['heuristic_total'] for c in compact])
    ml = np.array([c.get('ml_score', 0.0) for c in compact])

    print('\n=== Reproduced v57-like run results ===')
    print('n_samples:', len(arr))
    print('score_mean:', float(arr.mean()))
    print('heur_mean:', float(heur.mean()))
    print('ml_mean:', float(ml.mean()))
    print('score_min/max:', float(arr.min()), float(arr.max()))
    print('heur_min/max:', float(heur.min()), float(heur.max()))
    print('ml_min/max:', float(ml.min()), float(ml.max()))
    print('fraud_count >70:', int((arr>70).sum()))
    print('suspect_count 50-70:', int(((arr>=50)&(arr<=70)).sum()))
    print('normal_count <50:', int((arr<50).sum()))
    print('\nSample heuristic (10):', heur[:10].tolist())
    print('Sample ml (10):', ml[:10].tolist())
    print('Sample final (10):', arr[:10].tolist())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Reproduce v57 using explicit dataset files')
    parser.add_argument('--data-tag', help='Dataset suffix tag to load explicit files, e.g. 20260518_175529')
    parser.add_argument('--sample-n', type=int, default=None, help='Limit dataset to the first N rows')
    parser.add_argument('--sample-fraction', type=float, default=1.0, help='Sample fraction of the data')
    args = parser.parse_args()
    main(sample_n=args.sample_n, sample_fraction=args.sample_fraction, data_tag=args.data_tag)
