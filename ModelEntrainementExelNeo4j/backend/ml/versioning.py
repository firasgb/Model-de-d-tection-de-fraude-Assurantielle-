"""
versioning.py — Gestionnaire de versions de modèles
====================================================
Persiste les métadonnées des versions dans models/versions/version_config.json
et version_history.json. Compatible avec le format existant.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional


class ModelVersionManager:
    """Gère les métadonnées des versions de modèles ML."""

    def __init__(self, versions_dir: str = "models/versions"):
        self.versions_dir = versions_dir
        os.makedirs(self.versions_dir, exist_ok=True)
        self.config_file = os.path.join(self.versions_dir, "version_config.json")
        self.history_file = os.path.join(self.versions_dir, "version_history.json")
        self._ensure_files()

    # ── Initialisation ──────────────────────────────────────────────────────

    def _ensure_files(self):
        """Crée les fichiers de métadonnées s'ils n'existent pas."""
        if not os.path.exists(self.config_file):
            with open(self.config_file, 'w') as f:
                json.dump({"active_version": None, "updated_at": None}, f, indent=2)
        if not os.path.exists(self.history_file):
            with open(self.history_file, 'w') as f:
                json.dump({"versions": {}}, f, indent=2)

    def _load_config(self) -> dict:
        with open(self.config_file, 'r') as f:
            return json.load(f)

    def _save_config(self, config: dict):
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)

    def _load_history(self) -> dict:
        with open(self.history_file, 'r') as f:
            return json.load(f)

    def _save_history(self, history: dict):
        with open(self.history_file, 'w') as f:
            json.dump(history, f, indent=2)

    # ── Accesseurs ──────────────────────────────────────────────────────────

    def get_active_version(self) -> Optional[int]:
        """Retourne le numéro de version actif, ou None."""
        config = self._load_config()
        return config.get("active_version")

    def get_next_version_number(self) -> int:
        """Retourne le prochain numéro de version disponible."""
        history = self._load_history()
        versions = history.get("versions", {})
        if not versions:
            return 1
        return max(int(k) for k in versions.keys()) + 1

    def list_versions(self) -> List[Dict]:
        """Retourne la liste ordonnée des versions (du plus récent au plus ancien)."""
        history = self._load_history()
        versions = history.get("versions", {})
        result = []
        for key in sorted(versions.keys(), key=lambda k: int(k), reverse=True):
            entry = dict(versions[key])
            entry["version"] = int(key)
            
            # Flatten metrics for frontend compatibility
            metrics = entry.get("metrics", {})
            entry["f1_score"] = metrics.get("f1_score")
            entry["precision"] = metrics.get("precision")
            entry["recall"] = metrics.get("recall")
            entry["accuracy"] = metrics.get("accuracy")
            entry["auc_roc"] = metrics.get("auc_roc")
            entry["score_moyen"] = metrics.get("score_moyen")
            entry["label_source"] = metrics.get("label_source")

            is_supervised = metrics.get("is_supervised")
            if is_supervised is None:
                supervised_values = [entry["f1_score"], entry["precision"], entry["recall"], entry["accuracy"], entry["auc_roc"]]
                is_supervised = any(
                    isinstance(v, (int, float)) for v in supervised_values
                )
            entry["is_supervised"] = bool(is_supervised)
            
            result.append(entry)
        return result

    def get_version_info(self, version_num: int) -> Optional[Dict]:
        """Retourne les infos d'une version spécifique."""
        history = self._load_history()
        key = str(version_num)
        if key not in history.get("versions", {}):
            return None
        entry = dict(history["versions"][key])
        entry["version"] = int(key)
        entry["label_source"] = entry.get("metrics", {}).get("label_source")

        is_supervised = entry.get("metrics", {}).get("is_supervised")
        if is_supervised is None:
            supervised_values = [
                entry["metrics"].get("f1_score"),
                entry["metrics"].get("precision"),
                entry["metrics"].get("recall"),
                entry["metrics"].get("accuracy"),
                entry["metrics"].get("auc_roc"),
            ]
            is_supervised = any(isinstance(v, (int, float)) for v in supervised_values)
        entry["is_supervised"] = bool(is_supervised)
        return entry

    # ── Mutations ───────────────────────────────────────────────────────────

    def save_version(self, version_num: int, model_path: str, metrics: dict, notes: str = ""):
        """Enregistre une nouvelle version dans l'historique."""
        history = self._load_history()
        if "versions" not in history:
            history["versions"] = {}

        history["versions"][str(version_num)] = {
            "version": version_num,
            "created_at": datetime.now().isoformat(),
            "model_path": model_path,
            "metrics": metrics,
            "notes": notes,
            "active": False,
        }
        self._save_history(history)

    def set_active_version(self, version_num: int) -> bool:
        """Définit la version active. Retourne True si succès."""
        history = self._load_history()
        versions = history.get("versions", {})
        key = str(version_num)

        if key not in versions:
            return False

        # Désactiver toutes les autres versions
        for k in versions:
            versions[k]["active"] = False

        # Activer la version demandée
        versions[key]["active"] = True
        self._save_history(history)

        # Mettre à jour le config
        config = self._load_config()
        config["active_version"] = version_num
        config["updated_at"] = datetime.now().isoformat()
        self._save_config(config)
        return True

    def delete_version(self, version_num: int) -> bool:
        """Supprime une version et son fichier .pkl. Retourne True si succès."""
        history = self._load_history()
        versions = history.get("versions", {})
        key = str(version_num)

        if key not in versions:
            return False

        # Ne pas supprimer la version active
        if versions[key].get("active", False):
            return False

        # Supprimer le fichier .pkl
        model_file = os.path.join(self.versions_dir, f"v{version_num}_model.pkl")
        if os.path.exists(model_file):
            try:
                os.remove(model_file)
            except Exception as e:
                print(f"⚠️ Erreur lors de la suppression du fichier {model_file}: {e}")
                return False

        # Supprimer la métadonnée de la version
        del versions[key]
        history["versions"] = versions
        self._save_history(history)
        return True

    # ── Comparaison ────────────────────────────────────────────────────────

    def compare_versions(self, v1: int, v2: int) -> Dict:
        """Compare deux versions et retourne les deltas et la meilleure."""
        info1 = self.get_version_info(v1)
        info2 = self.get_version_info(v2)

        if not info1 or not info2:
            return {"error": f"Version(s) non trouvée(s): v{v1}, v{v2}"}

        m1 = info1.get("metrics", {})
        m2 = info2.get("metrics", {})

        def _delta(k):
            a = m1.get(k)
            b = m2.get(k)
            if a is None or b is None:
                return None
            try:
                return float(b) - float(a)
            except (TypeError, ValueError):
                return None

        f1_delta = _delta("f1_score")
        precision_delta = _delta("precision")
        recall_delta = _delta("recall")
        accuracy_delta = _delta("accuracy")
        auc_delta = _delta("auc_roc")

        # Déterminer la meilleure version (priorité: F1, puis AUC)
        meilleure = v1  # défaut
        if f1_delta is not None:
            if f1_delta > 0:
                meilleure = v2
            elif f1_delta == 0 and auc_delta is not None and auc_delta > 0:
                meilleure = v2
        elif auc_delta is not None and auc_delta > 0:
            meilleure = v2

        return {
            "v1": {
                "version": v1,
                "f1_score": m1.get("f1_score"),
                "precision": m1.get("precision"),
                "recall": m1.get("recall"),
                "accuracy": m1.get("accuracy"),
                "auc_roc": m1.get("auc_roc"),
                "score_moyen": m1.get("score_moyen"),
                "created_at": info1.get("created_at"),
                "label_source": info1.get("label_source"),
                "is_supervised": info1.get("is_supervised"),
            },
            "v2": {
                "version": v2,
                "f1_score": m2.get("f1_score"),
                "precision": m2.get("precision"),
                "recall": m2.get("recall"),
                "accuracy": m2.get("accuracy"),
                "auc_roc": m2.get("auc_roc"),
                "score_moyen": m2.get("score_moyen"),
                "created_at": info2.get("created_at"),
                "label_source": info2.get("label_source"),
                "is_supervised": info2.get("is_supervised"),
            },
            "f1_delta": f1_delta,
            "precision_delta": precision_delta,
            "recall_delta": recall_delta,
            "accuracy_delta": accuracy_delta,
            "auc_delta": auc_delta,
            "meilleure_version": meilleure,
        }