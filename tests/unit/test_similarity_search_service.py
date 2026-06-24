import math
import unittest
from api.services.similarity_search_service import (
    build_profile,
    compute_similarity,
    find_similar_objects,
    _weighted_euclidean_distance,
    _cosine_similarity,
    _FEATURE_NAMES,
    _DEFAULT_WEIGHTS,
)


def _iss_profile():
    return build_profile(
        inclination_deg=51.6,
        eccentricity=0.001,
        mean_altitude_km=415.0,
        decay_rate_km_day=0.01,
        maneuvers_per_year=5.0,
        orbital_period_min=92.8,
    )


def _geo_profile():
    return build_profile(
        inclination_deg=0.1,
        eccentricity=0.0002,
        mean_altitude_km=35786.0,
        decay_rate_km_day=0.0,
        maneuvers_per_year=1.0,
        orbital_period_min=1436.0,
    )


class TestBuildProfile(unittest.TestCase):
    def test_returns_required_keys(self):
        p = _iss_profile()
        self.assertIn("features", p)
        self.assertIn("feature_names", p)
        self.assertIn("raw", p)

    def test_feature_length(self):
        p = _iss_profile()
        self.assertEqual(len(p["features"]), 6)

    def test_feature_names_correct(self):
        p = _iss_profile()
        self.assertEqual(p["feature_names"], list(_FEATURE_NAMES))

    def test_features_in_unit_range(self):
        p = _iss_profile()
        for f in p["features"]:
            self.assertGreaterEqual(f, 0.0)
            self.assertLessEqual(f, 1.0)

    def test_extreme_values_clamped(self):
        p = build_profile(
            inclination_deg=200.0,
            eccentricity=2.0,
            mean_altitude_km=1e9,
            decay_rate_km_day=1000.0,
            maneuvers_per_year=1000.0,
            orbital_period_min=99999.0,
        )
        for f in p["features"]:
            self.assertLessEqual(f, 1.0)
            self.assertGreaterEqual(f, 0.0)

    def test_zero_values_produce_zero_features(self):
        p = build_profile(
            inclination_deg=0.0,
            eccentricity=0.0,
            mean_altitude_km=0.0,
            decay_rate_km_day=0.0,
            maneuvers_per_year=0.0,
            orbital_period_min=0.0,
        )
        self.assertEqual(p["features"], [0.0] * 6)


class TestWeightedEuclideanDistance(unittest.TestCase):
    def test_identical_vectors_distance_zero(self):
        v = [0.5, 0.3, 0.1, 0.0, 0.2, 0.4]
        w = [1.0] * 6
        self.assertAlmostEqual(_weighted_euclidean_distance(v, v, w), 0.0, places=10)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        w = [1.0, 1.0]
        self.assertAlmostEqual(_weighted_euclidean_distance(a, b, w), math.sqrt(2), places=10)

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            _weighted_euclidean_distance([1.0, 2.0], [1.0], [1.0, 1.0])


class TestCosineSimilarity(unittest.TestCase):
    def test_identical_vectors_score_one(self):
        v = [0.5, 0.3, 0.1]
        self.assertAlmostEqual(_cosine_similarity(v, v), 1.0, places=10)

    def test_zero_vector_returns_zero(self):
        self.assertEqual(_cosine_similarity([0.0, 0.0], [1.0, 0.0]), 0.0)

    def test_orthogonal_vectors_score_zero(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        self.assertAlmostEqual(_cosine_similarity(a, b), 0.0, places=10)


class TestComputeSimilarity(unittest.TestCase):
    def test_identical_profiles_max_similarity(self):
        p = _iss_profile()
        result = compute_similarity(p, p)
        self.assertAlmostEqual(result["similarity_score"], 1.0, delta=0.01)
        self.assertAlmostEqual(result["cosine_similarity"], 1.0, delta=1e-6)
        self.assertAlmostEqual(result["euclidean_distance"], 0.0, delta=1e-6)

    def test_different_regimes_lower_similarity(self):
        iss = _iss_profile()
        geo = _geo_profile()
        result = compute_similarity(iss, geo)
        self.assertLess(result["similarity_score"], 0.9)

    def test_result_has_required_keys(self):
        p1 = _iss_profile()
        p2 = _geo_profile()
        result = compute_similarity(p1, p2)
        for key in ("cosine_similarity", "euclidean_distance", "similarity_score"):
            self.assertIn(key, result)

    def test_similarity_score_in_range(self):
        p1 = _iss_profile()
        p2 = _geo_profile()
        result = compute_similarity(p1, p2)
        self.assertGreaterEqual(result["similarity_score"], 0.0)
        self.assertLessEqual(result["similarity_score"], 1.0)

    def test_custom_weights(self):
        p1 = _iss_profile()
        p2 = _geo_profile()
        default_result = compute_similarity(p1, p2)
        custom_result = compute_similarity(p1, p2, weights=[0.0, 0.0, 2.0, 0.0, 0.0, 0.0])
        self.assertNotAlmostEqual(
            default_result["euclidean_distance"],
            custom_result["euclidean_distance"],
            places=4,
        )


class TestFindSimilarObjects(unittest.TestCase):
    def _make_catalog(self):
        return [
            {
                "norad_id": "25544",
                "profile": _iss_profile(),
            },
            {
                "norad_id": "00001",
                "profile": _geo_profile(),
            },
            {
                "norad_id": "99999",
                "profile": build_profile(
                    inclination_deg=52.0,
                    eccentricity=0.002,
                    mean_altitude_km=420.0,
                    decay_rate_km_day=0.01,
                    maneuvers_per_year=4.5,
                    orbital_period_min=93.0,
                ),
            },
        ]

    def test_returns_list(self):
        catalog = self._make_catalog()
        results = find_similar_objects(_iss_profile(), catalog)
        self.assertIsInstance(results, list)

    def test_top_result_is_most_similar(self):
        catalog = self._make_catalog()
        query = _iss_profile()
        results = find_similar_objects(query, catalog, top_k=3)
        scores = [r["similarity"]["similarity_score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_top_k_respected(self):
        catalog = self._make_catalog()
        results = find_similar_objects(_iss_profile(), catalog, top_k=2)
        self.assertLessEqual(len(results), 2)

    def test_min_similarity_filter(self):
        catalog = self._make_catalog()
        results = find_similar_objects(_iss_profile(), catalog, min_similarity=0.99)
        for r in results:
            self.assertGreaterEqual(r["similarity"]["similarity_score"], 0.99)

    def test_profile_key_excluded_from_result(self):
        catalog = self._make_catalog()
        results = find_similar_objects(_iss_profile(), catalog)
        for r in results:
            self.assertNotIn("profile", r)

    def test_missing_profile_entry_skipped(self):
        catalog = self._make_catalog()
        catalog.append({"norad_id": "bad", "no_profile": True})
        results = find_similar_objects(_iss_profile(), catalog)
        norad_ids = [r.get("norad_id") for r in results]
        self.assertNotIn("bad", norad_ids)

    def test_empty_catalog_returns_empty(self):
        results = find_similar_objects(_iss_profile(), [])
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
