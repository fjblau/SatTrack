import unittest
from datetime import datetime, timezone
from api.services.orbital_service import OrbitalService


class TestOrbitalService(unittest.TestCase):
    """Test cases for OrbitalService"""
    
    def setUp(self):
        """Set up test data"""
        self.iss_tle_line1 = "1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927"
        self.iss_tle_line2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537"
        
        self.geo_tle_line2 = "2 23439  0.0186  68.4954 0002038 269.7896 240.8516  1.00270176 57896"
    
    def test_calculate_orbital_parameters(self):
        """Test calculating orbital parameters from TLE"""
        result = OrbitalService.calculate_orbital_parameters(self.iss_tle_line2)
        
        self.assertIn('apogee_km', result)
        self.assertIn('perigee_km', result)
        self.assertIn('inclination_degrees', result)
        self.assertIn('period_minutes', result)
        self.assertIn('semi_major_axis_km', result)
        self.assertIn('eccentricity', result)
        self.assertIn('mean_motion_rev_day', result)
        
        self.assertAlmostEqual(result['inclination_degrees'], 51.64, delta=0.01)
        self.assertAlmostEqual(result['mean_motion_rev_day'], 15.72125391, delta=0.01)
        
        self.assertGreater(result['apogee_km'], 0)
        self.assertGreater(result['perigee_km'], 0)
        self.assertGreater(result['period_minutes'], 0)
    
    def test_calculate_orbital_parameters_geo(self):
        """Test orbital parameters for GEO satellite"""
        result = OrbitalService.calculate_orbital_parameters(self.geo_tle_line2)
        
        self.assertAlmostEqual(result['mean_motion_rev_day'], 1.00270176, delta=0.01)
        
        self.assertGreater(result['apogee_km'], 35000)
        self.assertGreater(result['perigee_km'], 35000)
        
        self.assertAlmostEqual(result['period_minutes'], 1440, delta=10)
    
    def test_calculate_orbital_parameters_invalid(self):
        """Test with invalid TLE line"""
        with self.assertRaises(ValueError):
            OrbitalService.calculate_orbital_parameters("invalid")
        
        with self.assertRaises(ValueError):
            OrbitalService.calculate_orbital_parameters("")
    
    def test_get_orbital_period(self):
        """Test calculating orbital period"""
        period = OrbitalService.get_orbital_period(15.72125391)
        
        self.assertAlmostEqual(period, 91.58, delta=1.0)
    
    def test_get_orbital_period_geo(self):
        """Test calculating GEO orbital period"""
        period = OrbitalService.get_orbital_period(1.0)
        
        self.assertAlmostEqual(period, 1440, delta=0.1)
    
    def test_get_semi_major_axis(self):
        """Test calculating semi-major axis"""
        sma = OrbitalService.get_semi_major_axis(15.72125391)
        
        self.assertGreater(sma, 6700)
        self.assertLess(sma, 7000)
    
    def test_get_semi_major_axis_geo(self):
        """Test calculating GEO semi-major axis"""
        sma = OrbitalService.get_semi_major_axis(1.0)
        
        self.assertAlmostEqual(sma, 42164, delta=100)
    
    def test_calculate_apogee_perigee(self):
        """Test calculating apogee and perigee"""
        semi_major_axis = 6778.0
        eccentricity = 0.0006703
        
        apogee, perigee = OrbitalService.calculate_apogee_perigee(semi_major_axis, eccentricity)
        
        self.assertGreater(apogee, perigee)
        self.assertAlmostEqual(apogee - perigee, 2 * semi_major_axis * eccentricity, delta=1.0)
    
    def test_calculate_apogee_perigee_circular(self):
        """Test with circular orbit (eccentricity = 0)"""
        semi_major_axis = 6778.0
        eccentricity = 0.0
        
        apogee, perigee = OrbitalService.calculate_apogee_perigee(semi_major_axis, eccentricity)
        
        self.assertAlmostEqual(apogee, perigee, delta=0.01)
    
    def test_extract_tle_epoch(self):
        """Test extracting epoch from TLE line 1"""
        epoch = OrbitalService.extract_tle_epoch(self.iss_tle_line1)
        
        self.assertIsNotNone(epoch)
        self.assertIsInstance(epoch, datetime)
        self.assertEqual(epoch.tzinfo, timezone.utc)
        
        self.assertEqual(epoch.year, 2008)
        
        self.assertGreater(epoch.timetuple().tm_yday, 260)
        self.assertLess(epoch.timetuple().tm_yday, 270)
    
    def test_extract_tle_epoch_invalid(self):
        """Test with invalid TLE line 1"""
        result = OrbitalService.extract_tle_epoch("invalid")
        self.assertIsNone(result)
        
        result = OrbitalService.extract_tle_epoch("")
        self.assertIsNone(result)
    
    def test_calculate_orbital_state(self):
        """Test complete orbital state calculation"""
        timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = OrbitalService.calculate_orbital_state(
            self.iss_tle_line1,
            self.iss_tle_line2,
            timestamp
        )
        
        self.assertNotIn('error', result)
        
        self.assertIn('apogee_km', result)
        self.assertIn('perigee_km', result)
        self.assertIn('epoch', result)
        self.assertIn('timestamp', result)
        
        self.assertEqual(result['timestamp'], timestamp.isoformat())
    
    def test_calculate_orbital_state_default_timestamp(self):
        """Test orbital state calculation with default timestamp"""
        result = OrbitalService.calculate_orbital_state(
            self.iss_tle_line1,
            self.iss_tle_line2
        )
        
        self.assertNotIn('error', result)
        self.assertIn('timestamp', result)
    
    def test_classify_orbital_band_leo(self):
        """Test LEO classification"""
        band = OrbitalService.classify_orbital_band(420, 400)
        self.assertEqual(band, "LEO")
    
    def test_classify_orbital_band_meo(self):
        """Test MEO classification"""
        band = OrbitalService.classify_orbital_band(20200, 20000)
        self.assertEqual(band, "MEO")
    
    def test_classify_orbital_band_geo(self):
        """Test GEO classification"""
        band = OrbitalService.classify_orbital_band(35800, 35780)
        self.assertEqual(band, "GEO")
    
    def test_classify_orbital_band_heo(self):
        """Test HEO classification"""
        band = OrbitalService.classify_orbital_band(40000, 500)
        self.assertEqual(band, "HEO")
    
    def test_parse_scientific_notation_negative_exponent(self):
        """Test parsing negative exponent"""
        result = OrbitalService.parse_scientific_notation(" 10270-3")
        self.assertAlmostEqual(result, 0.00010270, delta=0.0000001)
    
    def test_parse_scientific_notation_positive_exponent(self):
        """Test parsing positive exponent"""
        result = OrbitalService.parse_scientific_notation(" 12345+2")
        self.assertAlmostEqual(result, 12.345, delta=0.001)
    
    def test_parse_scientific_notation_zero(self):
        """Test parsing zero values"""
        result = OrbitalService.parse_scientific_notation("00000-0")
        self.assertEqual(result, 0.0)
        
        result = OrbitalService.parse_scientific_notation("00000+0")
        self.assertEqual(result, 0.0)
    
    def test_parse_scientific_notation_empty(self):
        """Test parsing empty string"""
        result = OrbitalService.parse_scientific_notation("")
        self.assertEqual(result, 0.0)
    
    def test_constants(self):
        """Test that constants are properly set"""
        self.assertAlmostEqual(OrbitalService.GM, 398600.4418, delta=0.001)
        self.assertAlmostEqual(OrbitalService.EARTH_RADIUS_KM, 6371.0, delta=1.0)


if __name__ == "__main__":
    unittest.main()
