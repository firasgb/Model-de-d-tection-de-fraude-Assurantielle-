import sys
sys.path.insert(0, '.')

# Test 1: versioning module
print("=== Test 1: ModelVersionManager ===")
from ml.versioning import ModelVersionManager
m = ModelVersionManager()
print(f"active: {m.get_active_version()}")
print(f"next: {m.get_next_version_number()}")
print(f"versions: {len(m.list_versions())} entries")
info = m.get_version_info(14)
print(f"v14 info present: {info is not None}")
comp = m.compare_versions(1, 2)
print(f"compare 1vs2: {comp}")
print("PASS: ModelVersionManager")

# Test 2: auto_fraud_detector import
print("\n=== Test 2: AutoFraudDetector import ===")
from ml.auto_fraud_detector import AutoFraudDetector
print(f"version_manager type: {type(AutoFraudDetector.__init__.__code__.co_varnames)}")
# Check the class has version_manager reference
import inspect
src = inspect.getsource(AutoFraudDetector.__init__)
assert 'ModelVersionManager' in src, "ModelVersionManager not referenced in __init__"
print("PASS: AutoFraudDetector imports ModelVersionManager")

# Test 3: scoring_config
print("\n=== Test 3: ScoringConfig ===")
from ml.scoring_config import ScoringConfig, ScoringConfigManager
cfg = ScoringConfig()
print(f"thresholds: {cfg.thresholds}")
print(f"group_weights: {cfg.group_weights}")
print("PASS: ScoringConfig")

print("\n=== ALL TESTS PASSED ===")