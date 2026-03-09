import unittest
from api.services.tle_service import parse_tle_fields


ISS_NAME = "ISS (ZARYA)"
ISS_LINE1 = "1 25544U 98067A   24038.54586899  .00012769  00000+0  22680-3 0  9996"
ISS_LINE2 = "2 25544  51.6406 302.7583 0001012  95.3523  23.3829 15.50234806439337"


class TestParseTleFields(unittest.TestCase):

    def setUp(self):
        self.result = parse_tle_fields(ISS_NAME, ISS_LINE1, ISS_LINE2)

    def test_raw_lines_preserved(self):
        self.assertEqual(self.result["line1"], ISS_LINE1)
        self.assertEqual(self.result["line2"], ISS_LINE2)
        self.assertEqual(self.result["name"], ISS_NAME)

    def test_inclination(self):
        self.assertAlmostEqual(self.result["inclination_deg"], 51.6406, delta=0.01)

    def test_eccentricity(self):
        self.assertAlmostEqual(self.result["eccentricity"], 0.0001012, delta=1e-5)

    def test_mean_motion_range(self):
        mm = self.result["mean_motion_rev_per_day"]
        self.assertGreater(mm, 15.0)
        self.assertLess(mm, 16.0)

    def test_raan(self):
        self.assertAlmostEqual(self.result["raan_deg"], 302.7583, delta=0.01)

    def test_arg_of_perigee(self):
        self.assertAlmostEqual(self.result["arg_of_perigee_deg"], 95.3523, delta=0.01)

    def test_mean_anomaly(self):
        self.assertAlmostEqual(self.result["mean_anomaly_deg"], 23.3829, delta=0.01)

    def test_required_keys_present(self):
        required = [
            "line1", "line2", "name", "epoch_year", "epoch_day", "bstar",
            "inclination_deg", "raan_deg", "eccentricity", "arg_of_perigee_deg",
            "mean_anomaly_deg", "mean_motion_rev_per_day", "rev_number",
            "ndot", "nddot", "fetched_at",
        ]
        for key in required:
            self.assertIn(key, self.result, msg=f"Missing key: {key}")

    def test_fetched_at_is_iso_string(self):
        from datetime import datetime
        fetched_at = self.result["fetched_at"]
        self.assertIsInstance(fetched_at, str)
        datetime.fromisoformat(fetched_at)

    def test_epoch_year(self):
        self.assertEqual(self.result["epoch_year"], 24)


if __name__ == "__main__":
    unittest.main()
