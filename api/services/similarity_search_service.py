"""
Similarity search service for RSO behavioral profiling.

Builds multi-factor behavioral feature vectors from orbital parameters and
operational history, then computes pairwise similarity scores to identify
objects with analogous on-orbit behaviour.

Feature vector (6 dimensions, all normalised to [0, 1]):
  0  inclination_norm   – inclination / 180°
  1  eccentricity       – raw value (already ≤ 1)
  2  altitude_norm      – mean altitude / 36000 km  (capped at 1)
  3  decay_rate_norm    – perigee decay rate / 10 km/day (capped at 1)
  4  maneuver_freq_norm – maneuver count / 10 per year (capped at 1)
  5  period_norm        – orbital period / 1440 min  (capped at 1)
"""
import math
from typing import Any, Dict, List, Optional, Tuple


_FEATURE_DIMS = 6
_FEATURE_NAMES = [
    "inclination_norm",
    "eccentricity",
    "altitude_norm",
    "decay_rate_norm",
    "maneuver_freq_norm",
    "period_norm",
]

_DEFAULT_WEIGHTS = [1.0, 1.0, 1.0, 1.5, 1.0, 0.5]


def build_profile(
    inclination_deg: float,
    eccentricity: float,
    mean_altitude_km: float,
    decay_rate_km_day: float = 0.0,
    maneuvers_per_year: float = 0.0,
    orbital_period_min: float = 90.0,
) -> Dict[str, Any]:
    """
    Build a normalised behavioral feature profile for a single RSO.

    Args:
        inclination_deg: Orbital inclination in degrees (0 – 180).
        eccentricity: Orbital eccentricity (0 – 1).
        mean_altitude_km: Average of apogee and perigee altitudes in km.
        decay_rate_km_day: Perigee altitude decay rate in km/day (positive = decaying).
        maneuvers_per_year: Estimated number of maneuvers per year.
        orbital_period_min: Orbital period in minutes.

    Returns:
        Dict with keys:
          - ``features``: list of 6 normalised floats
          - ``feature_names``: list of feature name strings
          - ``raw``: dict of the original input values
    """
    features = [
        min(1.0, max(0.0, inclination_deg / 180.0)),
        min(1.0, max(0.0, eccentricity)),
        min(1.0, max(0.0, mean_altitude_km / 36000.0)),
        min(1.0, max(0.0, decay_rate_km_day / 10.0)),
        min(1.0, max(0.0, maneuvers_per_year / 10.0)),
        min(1.0, max(0.0, orbital_period_min / 1440.0)),
    ]
    return {
        "features": [round(f, 6) for f in features],
        "feature_names": list(_FEATURE_NAMES),
        "raw": {
            "inclination_deg": inclination_deg,
            "eccentricity": eccentricity,
            "mean_altitude_km": mean_altitude_km,
            "decay_rate_km_day": decay_rate_km_day,
            "maneuvers_per_year": maneuvers_per_year,
            "orbital_period_min": orbital_period_min,
        },
    }


def _weighted_euclidean_distance(
    a: List[float],
    b: List[float],
    weights: List[float],
) -> float:
    """Weighted Euclidean distance between two feature vectors."""
    if len(a) != len(b) or len(a) != len(weights):
        raise ValueError("Feature vectors and weight vector must have the same length")
    return math.sqrt(sum(weights[i] * (a[i] - b[i]) ** 2 for i in range(len(a))))


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity in [−1, 1]; returns 0 for zero-magnitude vectors."""
    dot = sum(a[i] * b[i] for i in range(len(a)))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def compute_similarity(
    profile_a: Dict[str, Any],
    profile_b: Dict[str, Any],
    weights: Optional[List[float]] = None,
) -> Dict[str, float]:
    """
    Compute similarity between two profiles returned by :func:`build_profile`.

    Args:
        profile_a: Profile dict as returned by :func:`build_profile`.
        profile_b: Profile dict as returned by :func:`build_profile`.
        weights: Optional list of 6 feature weights for Euclidean metric.
                 Defaults to ``_DEFAULT_WEIGHTS``.

    Returns:
        Dict with keys:
          - ``cosine_similarity``: float in [-1, 1]; higher is more similar
          - ``euclidean_distance``: weighted Euclidean distance; lower is more similar
          - ``similarity_score``: normalised score in [0, 1] combining both metrics
    """
    if weights is None:
        weights = _DEFAULT_WEIGHTS

    fa = profile_a["features"]
    fb = profile_b["features"]

    cos_sim = _cosine_similarity(fa, fb)
    euc_dist = _weighted_euclidean_distance(fa, fb, weights)

    max_possible_dist = math.sqrt(sum(w for w in weights))
    euc_score = 1.0 - min(1.0, euc_dist / max_possible_dist) if max_possible_dist > 0 else 0.0

    cos_score = (cos_sim + 1.0) / 2.0

    similarity_score = round(0.5 * cos_score + 0.5 * euc_score, 4)

    return {
        "cosine_similarity": round(cos_sim, 4),
        "euclidean_distance": round(euc_dist, 4),
        "similarity_score": similarity_score,
    }


def find_similar_objects(
    query_profile: Dict[str, Any],
    catalog: List[Dict[str, Any]],
    top_k: int = 10,
    min_similarity: float = 0.0,
    weights: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    """
    Find the most similar objects in *catalog* to *query_profile*.

    Args:
        query_profile: Profile dict as returned by :func:`build_profile`.
        catalog: List of dicts each containing a ``"profile"`` key (built by
            :func:`build_profile`) plus any additional metadata keys (e.g. ``norad_id``).
        top_k: Maximum number of results to return.
        min_similarity: Minimum ``similarity_score`` threshold (0 – 1).
        weights: Optional feature weights forwarded to :func:`compute_similarity`.

    Returns:
        List of result dicts sorted by descending ``similarity_score``, each containing:
          - ``similarity``: the similarity metrics dict from :func:`compute_similarity`
          - all other keys from the catalog entry (excluding ``"profile"``)
    """
    results: List[Dict[str, Any]] = []
    for entry in catalog:
        profile = entry.get("profile")
        if profile is None:
            continue
        sim = compute_similarity(query_profile, profile, weights)
        if sim["similarity_score"] < min_similarity:
            continue
        result = {k: v for k, v in entry.items() if k != "profile"}
        result["similarity"] = sim
        results.append(result)

    results.sort(key=lambda r: r["similarity"]["similarity_score"], reverse=True)
    return results[:top_k]
