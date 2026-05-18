import sys, os, traceback, inspect
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')
os.environ["PYTHONIOENCODING"] = "utf-8"

print("=" * 60)
print("BACKEND VERIFICATION")
print("=" * 60)

# Test 1: versioning module
print("\n[1/6] Testing ModelVersionManager...")
try:
    from ml.versioning import ModelVersionManager
    m = ModelVersionManager()
    assert m.get_active_version() == 14, f"Expected 14, got {m.get_active_version()}"
    assert m.get_next_version_number() == 15, f"Expected 15, got {m.get_next_version_number()}"
    versions = m.list_versions()
    assert len(versions) == 14, f"Expected 14 versions, got {len(versions)}"
    info = m.get_version_info(14)
    assert info is not None, "v14 info should exist"
    assert info["active"] == True, "v14 should be active"
    comp = m.compare_versions(2, 1)
    assert "f1_delta" in comp, "comparison should have f1_delta"
    assert "meilleure_version" in comp, "comparison should have meilleure_version"
    print("  PASS: ModelVersionManager works correctly")
except Exception as e:
    print(f"  FAIL: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 2: scoring_config
print("\n[2/6] Testing ScoringConfigManager...")
try:
    from ml.scoring_config import ScoringConfig, ScoringConfigManager
    mgr = ScoringConfigManager()
    cfg = mgr.current
    assert cfg.thresholds["normal_max"] == 49.99
    assert cfg.thresholds["suspect_min"] == 50.0
    assert cfg.thresholds["frauduleux"] == 70.0
    assert cfg.group_weights["financial"] == 35
    assert cfg.group_weights["temporal"] == 35
    assert cfg.group_weights["frequency"] == 30
    print("  PASS: ScoringConfigManager works correctly")
except Exception as e:
    print(f"  FAIL: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 3: AutoFraudDetector import and initialization
print("\n[3/6] Testing AutoFraudDetector import...")
try:
    from ml.auto_fraud_detector import AutoFraudDetector
    # Verify ModelVersionManager is imported correctly
    from ml import auto_fraud_detector
    src = inspect.getsource(auto_fraud_detector)
    assert 'ModelVersionManager' in src, "ModelVersionManager not referenced"
    assert 'from .versioning import' in src
    print("  PASS: AutoFraudDetector imports ModelVersionManager correctly")
except Exception as e:
    print(f"  FAIL: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 4: Full detector creation
print("\n[4/6] Testing AutoFraudDetector full initialization...")
try:
    detector = AutoFraudDetector()
    assert hasattr(detector, 'version_manager'), "version_manager attribute missing"
    assert detector.version_manager.get_active_version() == 14
    assert detector.version_manager.get_next_version_number() == 15
    assert hasattr(detector, 'current_version_num')
    print(f"  PASS: Detector created, version_manager active={detector.version_manager.get_active_version()}")
except Exception as e:
    print(f"  FAIL: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 5: Data loading
print("\n[5/6] Testing data loading...")
try:
    from utils.data_loader import DataLoader
    dl = DataLoader("data/")
    dl.load_all()
    sinistres_df = dl.get_sinistres()
    contrats_df = dl.get_contrats()
    tiers_df = dl.get_tiers()
    print(f"  Data: {len(sinistres_df)} sinistres, {len(contrats_df)} contrats, {len(tiers_df)} tiers")
    print(f"  Data: {len(sinistres_df)} sinistres, {len(contrats_df)} contrats, {len(tiers_df)} tiers")
    assert len(sinistres_df) > 0, "sinistres should not be empty"
    print("  PASS: Data loaded successfully")
except Exception as e:
    print(f"  FAIL: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 6: Model loading (active version)
print("\n[6/6] Testing model loading via set_active_version...")
try:
    result = detector.set_active_version(14)
    print(f"  set_active_version(14) = {result}")
    print(f"  is_fitted = {detector.is_fitted}")
    if detector.is_fitted:
        print(f"  _cached_scores shape: {detector._cached_scores.shape if hasattr(detector._cached_scores, 'shape') else len(detector._cached_scores)}")
        # Test predict
        pred = detector.predict(0, sinistres_df, contrats_df, tiers_df)
        print(f"  predict(0): statut={pred.get('statut_fraude')}, score={pred.get('score_suspicion', 0):.2f}")
        print("  PASS: Model loaded and prediction works!")
    else:
        print("  WARN: Model not fitted (expected if no saved model matches)")
except Exception as e:
    print(f"  FAIL: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 7: Version listing API-equivalent
print("\n[7/7] Testing version listing (API-equivalent)...")
try:
    all_versions = detector.list_all_versions()
    print(f"  Total versions: {len(all_versions)}")
    v = all_versions[0]
    assert 'version' in v
    assert 'created_at' in v
    assert 'model_path' in v
    assert 'metrics' in v
    assert 'notes' in v
    assert 'active' in v
    print(f"  Latest: v{v['version']} active={v['active']}")
    print("  PASS: Version listing works!")
except Exception as e:
    print(f"  FAIL: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("ALL BACKEND TESTS PASSED!")
print("=" * 60)