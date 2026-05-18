"""
Géocodage hybride pour la Tunisie — VERSION 1.0

Convertit des adresses textuelles en coordonnées GPS (latitude/longitude) en
trois étapes successives, par ordre de priorité :

  1. Lookup dans un gazetteer offline (gouvernorats + villes/délégations
     tunisiennes connues). Rapide, sans réseau, gratuit.
  2. Cache disque persistant (geocode_cache.json) pour mémoriser les résultats
     déjà résolus (offline ou via API) et éviter de relancer une requête.
  3. Fallback API Nominatim (OpenStreetMap) — facultatif, activable via
     `enable_api=True`. Respecte les CGU (1 req/s + User-Agent identifié).

Utilisation typique dans le pipeline de features :

    from ml.geo_utils import TunisiaGeocoder
    geo = TunisiaGeocoder(cache_path="data/geocode_cache.json", enable_api=False)
    lat, lon = geo.geocode("Avenue Habib Bourguiba, Tunis")
    df['LATITUDE_SINISTRE'], df['LONGITUDE_SINISTRE'] = geo.geocode_series(df['adresse_sinistre'])

Les correspondances offline couvrent l'ensemble des 24 gouvernorats et
~120 délégations / villes principales. Les correspondances sont fuzzy
(suppression des accents, espaces multiples, ponctuation) pour résister
aux fautes d'orthographe et aux variantes (« Ben Gardane » vs « bengardane »).
"""

import os
import re
import json
import time
import unicodedata
from typing import Optional, Tuple, List, Dict, Any

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Gazetteer offline : gouvernorats + grandes villes / délégations tunisiennes
# Coordonnées approximatives (centre ville). Les distances Haversine restent
# fiables à l'échelle d'un sinistre (résolution ≈ quelques km).
# ─────────────────────────────────────────────────────────────────────────────

TUNISIA_GAZETTEER: Dict[str, Tuple[float, float]] = {
    # ─── Gouvernorats ──────────────────────────────────────────────────────
    "tunis":             (36.8065, 10.1815),
    "ariana":            (36.8625, 10.1956),
    "ben arous":         (36.7536, 10.2189),
    "manouba":           (36.8101, 10.0956),
    "nabeul":            (36.4514, 10.7378),
    "zaghouan":          (36.4028, 10.1428),
    "bizerte":           (37.2744, 9.8739),
    "beja":              (36.7256, 9.1817),
    "jendouba":          (36.5011, 8.7803),
    "kef":               (36.1742, 8.7050),
    "le kef":            (36.1742, 8.7050),
    "siliana":           (36.0844, 9.3708),
    "sousse":            (35.8256, 10.6411),
    "monastir":          (35.7681, 10.8264),
    "mahdia":            (35.5047, 11.0622),
    "kairouan":          (35.6781, 10.0961),
    "kasserine":         (35.1675, 8.8364),
    "sidi bouzid":       (35.0381, 9.4858),
    "sfax":              (34.7406, 10.7603),
    "gabes":             (33.8814, 10.0983),
    "medenine":          (33.3548, 10.5055),
    "tataouine":         (32.9295, 10.4517),
    "gafsa":             (34.4256, 8.7842),
    "tozeur":            (33.9197, 8.1335),
    "kebili":            (33.7050, 8.9692),
    # ─── Délégations & villes (Grand Tunis) ────────────────────────────────
    "carthage":          (36.8528, 10.3236),
    "la marsa":          (36.8783, 10.3247),
    "marsa":             (36.8783, 10.3247),
    "le bardo":          (36.8089, 10.1378),
    "bardo":             (36.8089, 10.1378),
    "la goulette":       (36.8181, 10.3056),
    "goulette":          (36.8181, 10.3056),
    "rades":             (36.7681, 10.2747),
    "ezzahra":           (36.7461, 10.3033),
    "hammam lif":        (36.7261, 10.3392),
    "hammam-lif":        (36.7261, 10.3392),
    "mohamedia":         (36.6961, 10.1819),
    "mornag":            (36.6739, 10.2925),
    "fouchana":          (36.6975, 10.1697),
    "el mourouj":        (36.7258, 10.2253),
    "mourouj":           (36.7258, 10.2253),
    "mégrine":           (36.7811, 10.2367),
    "megrine":           (36.7811, 10.2367),
    "el menzah":         (36.8378, 10.1711),
    "menzah":            (36.8378, 10.1711),
    "el omrane":         (36.8267, 10.1731),
    "omrane":            (36.8267, 10.1731),
    "kram":              (36.8417, 10.3194),
    "le kram":           (36.8417, 10.3194),
    "soukra":            (36.8775, 10.2456),
    "la soukra":         (36.8775, 10.2456),
    "raoued":            (36.9119, 10.1928),
    "ettadhamen":        (36.8467, 10.0967),
    "douar hicher":      (36.8267, 10.0875),
    "den den":           (36.8167, 10.1058),
    "oued ellil":        (36.8225, 10.0322),
    "tebourba":          (36.8181, 9.8444),
    "borj louzir":       (36.9039, 10.2225),
    # ─── Cap Bon (Nabeul) ──────────────────────────────────────────────────
    "hammamet":          (36.4006, 10.6225),
    "kelibia":           (36.8478, 11.0939),
    "menzel temime":     (36.7806, 10.9931),
    "korba":             (36.5781, 10.8636),
    "soliman":           (36.7019, 10.4922),
    "grombalia":         (36.6111, 10.5006),
    "beni khalled":      (36.6453, 10.5933),
    "dar chaabane":      (36.4644, 10.7464),
    "menzel bouzelfa":   (36.6850, 10.5839),
    "el haouaria":       (37.0506, 11.0094),
    # ─── Sahel (Sousse, Monastir, Mahdia) ──────────────────────────────────
    "msaken":            (35.7281, 10.5839),
    "kalaa kebira":      (35.8650, 10.5394),
    "kalaa seghira":     (35.8389, 10.5650),
    "akouda":            (35.8689, 10.5792),
    "hammam sousse":     (35.8631, 10.6017),
    "port el kantaoui":  (35.8889, 10.5961),
    "skanes":            (35.7569, 10.7533),
    "moknine":           (35.6378, 10.8950),
    "ksar hellal":       (35.6450, 10.8919),
    "ksibet el mediouni": (35.6736, 10.8669),
    "jemmal":            (35.6256, 10.7553),
    "bekalta":           (35.6175, 10.9925),
    "teboulba":          (35.6692, 10.9544),
    "rejiche":           (35.5183, 11.0617),
    "chebba":            (35.2375, 11.1156),
    "ksour essef":       (35.4117, 10.9892),
    # ─── Sfax & Sud-Est ────────────────────────────────────────────────────
    "sakiet ezzit":      (34.8003, 10.7656),
    "sakiet eddaier":    (34.8108, 10.7833),
    "thyna":             (34.6856, 10.7117),
    "el ain":            (34.7619, 10.7211),
    "gremda":            (34.7589, 10.6739),
    "agareb":            (34.7494, 10.5306),
    "jebeniana":         (35.0339, 10.9008),
    "mahres":            (34.5311, 10.5036),
    "skhira":            (34.3022, 10.0653),
    "kerkennah":         (34.6667, 11.2333),
    "djerba":            (33.8076, 10.8451),
    "houmt souk":        (33.8756, 10.8581),
    "midoun":            (33.8081, 10.9925),
    "ajim":              (33.7239, 10.7397),
    "zarzis":            (33.5039, 11.1122),
    "ben gardane":       (33.1383, 11.2167),
    "bengardane":        (33.1383, 11.2167),
    # ─── Sud (Gabès, Tataouine, Kébili, Tozeur) ────────────────────────────
    "matmata":           (33.5450, 9.9700),
    "el hamma":          (33.8861, 9.7950),
    "mareth":            (33.6325, 10.2944),
    "metouia":           (33.9619, 10.0014),
    "ghannouch":         (33.9342, 10.0961),
    "remada":            (32.3194, 10.3919),
    "dehiba":            (32.0181, 10.7000),
    "douz":              (33.4664, 9.0203),
    "souk lahad":        (33.8472, 8.9472),
    "nefta":             (33.8731, 7.8769),
    "degache":           (33.9806, 8.2089),
    "tamerza":           (34.3853, 7.9483),
    # ─── Centre & Ouest (Kairouan, Kasserine, Sidi Bouzid, Gafsa) ──────────
    "haffouz":           (35.6411, 9.6750),
    "sbeitla":           (35.2400, 9.1228),
    "feriana":           (34.9519, 8.5703),
    "thala":             (35.5650, 8.6700),
    "regueb":            (34.8794, 9.7833),
    "menzel bouzaiane":  (34.6022, 9.4853),
    "metlaoui":          (34.3300, 8.4019),
    "redeyef":            (34.3833, 8.1556),
    "moularès":          (34.4825, 8.2617),
    "moulares":          (34.4825, 8.2617),
    # ─── Nord-Ouest (Béja, Jendouba, Kef, Siliana, Bizerte) ────────────────
    "ras jebel":         (37.2147, 10.1183),
    "menzel bourguiba":  (37.1542, 9.7867),
    "menzel jemil":      (37.2358, 9.9136),
    "mateur":            (37.0408, 9.6628),
    "tabarka":           (36.9544, 8.7589),
    "ain draham":        (36.7775, 8.6864),
    "bou salem":         (36.6086, 8.9719),
    "ghardimaou":        (36.4503, 8.4350),
    "fernana":           (36.6539, 8.6989),
    "nefza":             (36.9667, 9.0833),
    "teboursouk":        (36.4581, 9.2522),
    "testour":           (36.5544, 9.4408),
    "medjez el bab":     (36.6500, 9.6097),
    "sakiet sidi youssef": (36.2231, 8.3536),
    "dahmani":           (35.9589, 8.8228),
    "tajerouine":        (35.8950, 8.5519),
    "makthar":           (35.8556, 9.2061),
    "bargou":            (36.0944, 9.5719),
    "bou arada":         (36.3531, 9.6164),
    "gaafour":           (36.3208, 9.3344),
    "rouhia":            (35.8014, 9.0719),
    # ─── Mots-clés frontières (utilisés aussi par sinistre_frontiere) ─────
    "ras jedir":         (33.1583, 11.5500),
    "ras ajdir":         (33.1583, 11.5500),
    "wazen":             (35.7833, 8.4667),
    "melloula":          (37.0517, 8.8000),
}


# ─────────────────────────────────────────────────────────────────────────────
# Normalisation des adresses (pour matcher dans le gazetteer)
# ─────────────────────────────────────────────────────────────────────────────

def _strip_accents(s: str) -> str:
    """Supprime les accents (é→e, à→a, etc.) — essentiel pour le fuzzy match."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_address(s: Any) -> str:
    """Normalise une adresse pour la comparaison : lowercase, sans accents,
    sans ponctuation, espaces multiples → un seul. Retourne '' si invalide."""
    if s is None:
        return ""
    if isinstance(s, float) and (np.isnan(s) or np.isinf(s)):
        return ""
    s = str(s).strip()
    if not s or s.lower() in ("nan", "none", "inconnu", "unknown", "n/a"):
        return ""
    s = _strip_accents(s).lower()
    # Supprime ponctuation usuelle, garde lettres/chiffres/espaces
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ─────────────────────────────────────────────────────────────────────────────
# Gazetteer pré-normalisé (calculé une fois au chargement du module)
# ─────────────────────────────────────────────────────────────────────────────

_NORMALIZED_GAZETTEER: Dict[str, Tuple[float, float]] = {
    normalize_address(k): v for k, v in TUNISIA_GAZETTEER.items()
}


# ─────────────────────────────────────────────────────────────────────────────
# Géocodeur principal
# ─────────────────────────────────────────────────────────────────────────────

class TunisiaGeocoder:
    """Géocodeur hybride offline + cache + Nominatim (optionnel).

    Args:
        cache_path: chemin du cache JSON disque (lectures/écritures persistantes).
            Si None, le cache reste uniquement en mémoire.
        enable_api: si True, appelle Nominatim en fallback quand le gazetteer
            ne trouve aucune correspondance. Désactivé par défaut (offline only).
        api_min_interval: délai minimal entre 2 requêtes API (CGU Nominatim ≥ 1s).
        user_agent: identifiant requis par Nominatim.
    """

    def __init__(
        self,
        cache_path: Optional[str] = None,
        enable_api: bool = False,
        api_min_interval: float = 1.0,
        user_agent: str = "InsuranceFraudDetector/4.1 (offline-first)",
    ) -> None:
        self.cache_path = cache_path
        self.enable_api = enable_api
        self.api_min_interval = api_min_interval
        self.user_agent = user_agent
        self._memory_cache: Dict[str, Tuple[Optional[float], Optional[float]]] = {}
        self._last_api_call: float = 0.0
        self._stats = {"offline_hits": 0, "cache_hits": 0, "api_hits": 0,
                       "api_failures": 0, "no_match": 0, "empty": 0}

        if cache_path and os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                # On accepte deux formats : [lat, lon] ou {"lat":, "lon":}
                for k, v in raw.items():
                    if isinstance(v, list) and len(v) == 2:
                        self._memory_cache[k] = (
                            float(v[0]) if v[0] is not None else None,
                            float(v[1]) if v[1] is not None else None,
                        )
                    elif isinstance(v, dict) and "lat" in v and "lon" in v:
                        self._memory_cache[k] = (
                            float(v["lat"]) if v["lat"] is not None else None,
                            float(v["lon"]) if v["lon"] is not None else None,
                        )
                print(f"   📍 Geocoder: cache chargé ({len(self._memory_cache)} entrées) depuis {cache_path}")
            except Exception as e:
                print(f"   [WARN]  Geocoder: cache illisible ({e}), démarrage à vide")

    # ── Méthodes internes ────────────────────────────────────────────────

    def _lookup_offline(self, normalized: str) -> Optional[Tuple[float, float]]:
        """Cherche `normalized` dans le gazetteer (correspondance exacte
        puis sous-chaîne — la plus longue gagne pour limiter les faux positifs)."""
        if not normalized:
            return None
        # 1) Match exact (le plus rapide & fiable)
        if normalized in _NORMALIZED_GAZETTEER:
            return _NORMALIZED_GAZETTEER[normalized]
        # 2) Match « cle est dans l'adresse » → la cle la plus longue gagne
        best_key: Optional[str] = None
        for key in _NORMALIZED_GAZETTEER.keys():
            # On exige une correspondance sur un mot complet (pas « tunis » dans « tunisien »)
            pattern = r"(?:^|\s)" + re.escape(key) + r"(?:$|\s)"
            if re.search(pattern, normalized):
                if best_key is None or len(key) > len(best_key):
                    best_key = key
        if best_key:
            return _NORMALIZED_GAZETTEER[best_key]
        return None

    def _lookup_api(self, raw_address: str) -> Optional[Tuple[float, float]]:
        """Appelle Nominatim (OpenStreetMap) pour géocoder une adresse libre.
        Retourne None en cas d'échec, de timeout ou de résultat hors Tunisie."""
        try:
            import urllib.request
            import urllib.parse
        except ImportError:
            return None

        # Throttle pour respecter les CGU
        now = time.time()
        wait = self.api_min_interval - (now - self._last_api_call)
        if wait > 0:
            time.sleep(wait)
        self._last_api_call = time.time()

        try:
            params = urllib.parse.urlencode({
                "q": raw_address + ", Tunisia",
                "format": "json",
                "limit": 1,
                "countrycodes": "tn",
            })
            url = f"https://nominatim.openstreetmap.org/search?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read().decode("utf-8"))
            if not data:
                return None
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            # Borne de sécurité : Tunisie ≈ [30°N, 38°N] × [7°E, 12°E]
            if not (29.0 <= lat <= 38.5 and 6.5 <= lon <= 12.5):
                return None
            return (lat, lon)
        except Exception:
            self._stats["api_failures"] += 1
            return None

    # ── API publique ──────────────────────────────────────────────────────

    def geocode(self, address: Any) -> Tuple[Optional[float], Optional[float]]:
        """Géocode une adresse unique.

        Returns:
            (latitude, longitude) ou (None, None) si non résolue.
        """
        normalized = normalize_address(address)
        if not normalized:
            self._stats["empty"] += 1
            return (None, None)

        # 1) Cache mémoire
        if normalized in self._memory_cache:
            self._stats["cache_hits"] += 1
            return self._memory_cache[normalized]

        # 2) Gazetteer offline
        coords = self._lookup_offline(normalized)
        if coords is not None:
            self._stats["offline_hits"] += 1
            self._memory_cache[normalized] = coords
            return coords

        # 3) Fallback API (si activé)
        if self.enable_api:
            coords = self._lookup_api(str(address))
            if coords is not None:
                self._stats["api_hits"] += 1
                self._memory_cache[normalized] = coords
                return coords

        # 4) Aucun résultat — on mémorise (None, None) pour ne pas re-tenter
        self._stats["no_match"] += 1
        self._memory_cache[normalized] = (None, None)
        return (None, None)

    def geocode_series(self, series: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """Géocode une colonne pandas entière. Retourne (lat_series, lon_series)
        alignées sur l'index de l'entrée."""
        if series is None or len(series) == 0:
            return pd.Series(dtype=float), pd.Series(dtype=float)

        lats: List[Optional[float]] = []
        lons: List[Optional[float]] = []
        for val in series.values:
            lat, lon = self.geocode(val)
            lats.append(lat)
            lons.append(lon)
        return (
            pd.Series(lats, index=series.index, dtype="float64"),
            pd.Series(lons, index=series.index, dtype="float64"),
        )

    def save_cache(self) -> None:
        """Sauvegarde le cache mémoire sur disque (JSON). No-op si pas de path."""
        if not self.cache_path:
            return
        try:
            os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
            serializable = {k: list(v) for k, v in self._memory_cache.items()}
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, ensure_ascii=False, indent=0)
            print(f"   💾 Geocoder: cache sauvegardé ({len(serializable)} entrées) → {self.cache_path}")
        except Exception as e:
            print(f"   [WARN]  Geocoder: échec sauvegarde cache ({e})")

    def stats(self) -> Dict[str, int]:
        """Statistiques d'utilisation depuis l'initialisation."""
        return dict(self._stats)


# ─────────────────────────────────────────────────────────────────────────────
# Distance Haversine (kilomètres) — exposée ici pour éviter une dépendance
# circulaire avec auto_feature_engineering.py
# ─────────────────────────────────────────────────────────────────────────────

def haversine_km(lat1: Any, lon1: Any, lat2: Any, lon2: Any) -> float:
    """Distance Haversine en km entre deux points GPS. NaN si l'un est invalide."""
    import math
    try:
        if any(pd.isna(v) for v in (lat1, lon1, lat2, lon2)):
            return float("nan")
        lat1, lon1, lat2, lon2 = map(math.radians, (float(lat1), float(lon1), float(lat2), float(lon2)))
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 6371.0 * 2 * math.asin(math.sqrt(max(0.0, min(1.0, a))))
    except Exception:
        return float("nan")
