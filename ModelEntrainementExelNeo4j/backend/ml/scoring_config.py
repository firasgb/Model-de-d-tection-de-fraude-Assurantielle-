"""
scoring_config.py — Configuration Dynamique du Scoring v1.0
============================================================
Gère les poids des groupes, poids des indicateurs individuels et seuils de classification.
Permet de re-scorer tous les sinistres sans ré-entraîner les modèles ML.

Architecture:
- ScoringConfig: dataclass avec validation
- ScoringConfigManager: charge/sauve/applique les configs
- Default config: matching SCORE_GROUPS_MAX actuels
"""

import json
import os
from dataclasses import dataclass, asdict, field
from typing import Dict, Optional
from datetime import datetime


@dataclass
class ScoringConfig:
    """Configuration complète du système de scoring."""

    # ── Poids par groupe (somme = 100) ────────────────────────────────────────
    group_weights: Dict[str, int] = field(
        default_factory=lambda: {
            "financial": 35,
            "temporal": 28,
            "frequency": 20,
            "network": 10,
            "driver": 6,
            "profile": 1,
        }
    )

    # ── Poids par indicateur individuel (optionnel, override groupe) ──────────
    # Si non spécifié, utilise les poids par défaut de l'indicateur
    indicator_weights: Optional[Dict[str, float]] = field(default_factory=dict)

    # ── Seuils de classification ─────────────────────────────────────────────
    thresholds: Dict[str, float] = field(
        default_factory=lambda: {
            "normal_max": 49.99,
            "suspect_min": 50.0,
            "frauduleux": 70.0,
        }
    )

    # ── Métadonnées ───────────────────────────────────────────────────────────
    version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""


class ScoringConfigManager:
    """Gère le cycle de vie des configurations de scoring."""

    def __init__(self, config_dir: str = "models/versions"):
        self.config_dir = config_dir
        os.makedirs(config_dir, exist_ok=True)
        self.config_file = os.path.join(config_dir, "scoring_config.json")
        self.history_file = os.path.join(config_dir, "scoring_config_history.json")
        self._current_config: Optional[ScoringConfig] = None
        self._history: list = []

        # Charger la config actuelle ou créer la défaut
        self._load_or_create_default()

    @property
    def current(self) -> ScoringConfig:
        """Retourne la configuration actuelle en rechargeant le fichier si nécessaire."""
        self._load_or_create_default()
        return self._current_config

    def _load_or_create_default(self):
        """Charge la config depuis le fichier ou crée la défaut."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                self._current_config = ScoringConfig(**data)
                print(f"[OK] Configuration chargee: {self.config_file}")
            except Exception as e:
                print(f"[WARN] Erreur chargement config: {e}")
                self._create_default()
        else:
            self._create_default()

    def _create_default(self):
        """Crée et sauvegarde la configuration par défaut."""
        self._current_config = ScoringConfig()
        self.save()
        print(f"[OK] Configuration par defaut creee: {self.config_file}")

    def save(self) -> bool:
        """Sauvegarde la configuration actuelle."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(asdict(self._current_config), f, indent=2)
            return True
        except Exception as e:
            print(f"❌ Erreur sauvegarde config: {e}")
            return False

    def update(self, new_config: Dict[str, any], notes: str = "") -> bool:
        """
        Met à jour la configuration et persiste.

        Args:
            new_config: Dictionnaire partiel ou complet de la nouvelle configuration
            notes: Notes de version pour l'historique

        Returns:
            bool: True si succès
        """
        # Fusion avec config existante
        current = self.current
        current_dict = asdict(current)

        for key, value in new_config.items():
            if value is None:
                continue
            if isinstance(value, dict) and key in ["group_weights", "indicator_weights", "thresholds"]:
                current_dict[key].update(value)
            else:
                current_dict[key] = value

        # Créer nouvelle instance avec données fusionnées
        self._current_config = ScoringConfig(**current_dict)
        self._current_config.notes = notes
        self._current_config.created_at = datetime.now().isoformat()
        self._current_config.version = self._next_version()

        # Sauvegarder
        if not self.save():
            return False

        # Ajouter à l'historique
        self._add_to_history(asdict(self._current_config))

        print(f"Configuration mise à jour: v{self._current_config.version}")
        return True

    def _next_version(self) -> str:
        """Incrémente le numéro de version."""
        try:
            with open(self.config_file, 'r') as f:
                current = json.load(f)
            current_ver = current.get("version", "1.0")
            major, minor = map(int, current_ver.split('.'))
            return f"{major}.{minor + 1}"
        except:
            return "1.1"

    def _add_to_history(self, config_dict: dict):
        """Ajoute la config à l'historique (garde les 10 dernières)."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    history = json.load(f)
            else:
                history = []

            history.append({
                "timestamp": datetime.now().isoformat(),
                "config": config_dict
            })

            # Garder seulement les 10 dernières
            history = history[-10:]

            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            print(f"⚠️ Erreur historique config: {e}")

    def get_history(self, limit: int = 10) -> list:
        """Retourne l'historique des configurations."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    history = json.load(f)
                return history[-limit:]
        except:
            pass
        return []

    def rollback(self, version: str) -> bool:
        """
        Restaure une configuration précédente.

        Args:
            version: Numéro de version à restaurer (ex: "1.2")

        Returns:
            bool: True si succès
        """
        history = self.get_history(limit=50)
        for entry in history:
            if entry["config"].get("version") == version:
                self._current_config = ScoringConfig(**entry["config"])
                self.save()
                print(f"✅ Rollback vers v{version} effectué")
                return True
        return False

    def validate(self, config: ScoringConfig) -> Dict[str, any]:
        """
        Valide une configuration.

        Returns:
            dict: {valid: bool, errors: [], warnings: []}
        """
        errors = []
        warnings = []

        # 1. Somme des poids groupes = 100
        total = sum(config.group_weights.values())
        if total != 100:
            errors.append(f"Somme des poids groupes doit = 100 (actuel: {total})")

        # 2. Chaque groupe ≤ max autorisé
        MAX_GROUP = {
            "financial": 35,
            "temporal": 35,
            "frequency": 30,
            "network": 22,
            "driver": 8,
            "profile": 1,
        }
        for group, max_val in MAX_GROUP.items():
            if group in config.group_weights:
                if config.group_weights[group] > max_val:
                    errors.append(f"Groupe '{group}': {config.group_weights[group]} > max {max_val}")

        # 3. Seuils cohérents
        if config.thresholds.get("normal_max", 0) >= config.thresholds.get("suspect_min", 100):
            errors.append("normal_max doit être < suspect_min")

        if config.thresholds.get("suspect_min", 0) >= config.thresholds.get("frauduleux", 100):
            errors.append("suspect_min doit être < frauduleux")

        # 4. Poids indicateurs entre 0 et 100
        for ind, weight in config.indicator_weights.items():
            if not (0 <= weight <= 100):
                errors.append(f"Indicateur '{ind}': poids {weight} hors [0,100]")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def to_dict(self) -> dict:
        """Retourne la config actuelle comme dict."""
        return asdict(self.current)


# ─── Singleton global ─────────────────────────────────────────────────────────

_config_manager: Optional[ScoringConfigManager] = None


def get_config_manager() -> ScoringConfigManager:
    """Retourne le singleton manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ScoringConfigManager()
    return _config_manager
