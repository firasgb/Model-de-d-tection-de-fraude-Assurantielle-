"""
Chargement Automatique des Fichiers Excel - Version optimisée mémoire
"""
import pandas as pd
import os
import zipfile
from typing import Optional


class DataLoader:
    """Charge automatiquement les fichiers Excel avec optimisation mémoire"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            # Utiliser le dossier data dans le répertoire courant
            self.data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        else:
            self.data_dir = data_dir

        self._tiers = None
        self._contrats = None
        self._sinistres = None

    @staticmethod
    def _read_excel_robust(path: str, file_label: str, **kwargs) -> pd.DataFrame:
        """Lire un fichier Excel en essayant de détecter les formats invalides ou mal nommés."""
        try:
            return pd.read_excel(path, engine='openpyxl', **kwargs)
        except Exception as exc:
            msg = str(exc).lower()
            if isinstance(exc, zipfile.BadZipFile) or 'not a zip file' in msg:
                print(f"⚠️ {file_label} ne semble pas être un fichier .xlsx valide. Vérification du contenu...")
                with open(path, 'rb') as f:
                    header = f.read(8)

                if header.startswith(b'PK'):
                    if not zipfile.is_zipfile(path):
                        with open(path, 'rb') as f:
                            raw = f.read()
                        if b'PK\x01\x02' not in raw and b'PK\x05\x06' not in raw:
                            raise RuntimeError(
                                f"{file_label} semble être un fichier .xlsx tronqué ou incomplet "
                                "(archive ZIP incomplète / fin de central directory manquante). "
                                "Remplacez-le par un véritable .xlsx valide."
                            ) from exc
                        raise RuntimeError(
                            f"{file_label} est corrompu ou n'est pas un véritable fichier .xlsx. "
                            "Renommez/le convertissez-le en .xlsx valide."
                        ) from exc
                    raise RuntimeError(
                        f"{file_label} est corrompu ou n'est pas un véritable fichier .xlsx. "
                        "Renommez/le convertissez-le en .xlsx valide."
                    ) from exc
                if header.startswith(b'\xd0\xcf\x11\xe0'):
                    raise RuntimeError(
                        f"{file_label} ressemble à un ancien fichier Excel (.xls). "
                        "Convertissez-le en .xlsx ou installez xlrd."
                    ) from exc
                if all(32 <= b < 127 or b in (9, 10, 13) for b in header):
                    print(f"  -> {file_label} semble être un fichier texte. Essai en lecture CSV...")
                    try:
                        return pd.read_csv(path, **kwargs)
                    except Exception as exc_csv:
                        raise RuntimeError(
                            f"Impossible de lire {file_label} comme CSV après échec Excel. "
                            "Vérifiez le format du fichier."
                        ) from exc_csv
            raise

    def load_all(self, base_path: Optional[str] = None) -> bool:
        """Charger tous les fichiers Excel avec optimisation mémoire"""
        data_dir = base_path or self.data_dir
        # Normaliser le chemin
        data_dir = os.path.normpath(data_dir)

        print(f"Tentative de chargement depuis: {data_dir}")
        
        if not os.path.exists(data_dir):
            print(f"DOSSIER INTROUVABLE: {data_dir}")
            return False
            
        print(f"Fichiers dans le dossier: {os.listdir(data_dir)}")

        files_found = []
        errors = []

        # Supprimer le fichier temporaire Excel s'il existe
        temp_file = os.path.join(data_dir, "~$sinistres.xlsx")
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
                print(f"Fichier temporaire supprimé: {temp_file}")
            except:
                pass

        try:
            # Charger sinistres (PRIORITÉ) - AVEC OPTIMISATION
            candidates = ["sinistres.xlsx"]
            candidates.extend(
                sorted(
                    [f for f in os.listdir(data_dir) if f.startswith("sinistres_") and f.endswith(".xlsx")],
                    reverse=True,
                )
            )

            loaded_sinistres = False
            for candidate in candidates:
                sinistres_path = os.path.join(data_dir, candidate)
                if not os.path.exists(sinistres_path):
                    continue

                print(f"Chargement de {candidate}...")

                try:
                    # Forcer le garbage collector avant chargement
                    import gc
                    gc.collect()

                    self._sinistres = self._read_excel_robust(
                        sinistres_path,
                        candidate,
                        dtype={
                            'NUM_SINISTRE': 'string',
                            'NUM_CONTRAT': 'string',
                            'IMMATRICULATION': 'string',
                            'CDL': 'string',
                            'STATUS': 'string',
                            'TYPE_SINISTRE': 'string',
                            'EXPERT_STAREX': 'string',
                            'GARAGES': 'string',
                        }
                    )
                    self._sinistres.columns = [c.strip() if isinstance(c, str) else c for c in self._sinistres.columns]
                    files_found.append(f"{candidate} ({len(self._sinistres)} lignes)")
                    print(f"{candidate} chargé avec succès")
                    loaded_sinistres = True
                    break
                except MemoryError:
                    print("Mémoire insuffisante, tentative de chargement en mode chunks...")
                    chunks = []
                    chunk_size = 10000
                    for chunk in pd.read_excel(
                        sinistres_path,
                        engine='openpyxl',
                        chunksize=chunk_size,
                    ):
                        chunks.append(chunk)
                        gc.collect()
                    self._sinistres = pd.concat(chunks, ignore_index=True)
                    self._sinistres.columns = [c.strip() if isinstance(c, str) else c for c in self._sinistres.columns]
                    files_found.append(f"{candidate} ({len(self._sinistres)} lignes) [chargé par chunks]")
                    print(f"{candidate} chargé par chunks ({len(self._sinistres)} lignes)")
                    loaded_sinistres = True
                    break
                except Exception as exc:
                    print(f"Erreur lecture {candidate} : {exc}")
                    errors.append(f"{candidate} ERREUR")

            if not loaded_sinistres:
                errors.append("sinistres.xlsx NON TROUVE OU INVALIDE")

            # Charger contrats
            contrats_path = os.path.join(data_dir, "contrats.xlsx")
            if os.path.exists(contrats_path):
                print("Chargement de contrats.xlsx...")
                try:
                    self._contrats = self._read_excel_robust(contrats_path, "contrats.xlsx")
                    files_found.append(f"contrats.xlsx ({len(self._contrats)} lignes)")
                    print("contrats.xlsx chargé")
                except Exception as exc:
                    print(f"Erreur lecture contrats.xlsx : {exc}")
                    errors.append("contrats.xlsx ERREUR")
            else:
                errors.append(f"contrats.xlsx NON TROUVE")

            # Charger tiers
            tiers_path = os.path.join(data_dir, "tiers.xlsx")
            if os.path.exists(tiers_path):
                print("Chargement de tiers.xlsx...")
                try:
                    self._tiers = self._read_excel_robust(tiers_path, "tiers.xlsx")
                    files_found.append(f"tiers.xlsx ({len(self._tiers)} lignes)")
                    print("tiers.xlsx chargé")
                except Exception as exc:
                    print(f"Erreur lecture tiers.xlsx : {exc}")
                    errors.append("tiers.xlsx ERREUR")
            else:
                errors.append(f"tiers.xlsx NON TROUVE")

            if errors:
                print(f"ATTENTION: {', '.join(errors)}")

            print(f"Fichiers chargés: {', '.join(files_found) if files_found else 'AUCUN'}")

            # Retourner True si au moins les sinistres sont chargés
            return self._sinistres is not None

        except Exception as e:
            print(f"Erreur chargement: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_tiers(self) -> pd.DataFrame:
        return self._tiers

    def get_contrats(self) -> pd.DataFrame:
        return self._contrats

    def get_sinistres(self) -> pd.DataFrame:
        return self._sinistres

    @property
    def stats(self):
        return {
            "tiers": len(self._tiers) if self._tiers is not None else 0,
            "contrats": len(self._contrats) if self._contrats is not None else 0,
            "sinistres": len(self._sinistres) if self._sinistres is not None else 0,
            "loaded": self._sinistres is not None
        }