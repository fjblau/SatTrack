import unittest
from datetime import datetime, timezone, timedelta
from api.services.propagation_service import PropagationService, PropagationError


class TestPropagationService(unittest.TestCase):
    """Test cases for PropagationService"""
    
    def setUp(self):
        """Set up test data with ISS TLE (NORAD 25544)"""
        self.iss_name = "ISS (ZARYA)"
        self.iss_line1 = "1 25544U 98067A   24038.54586899  .00012769  00000+0  22680-3 0  9996"
        self.iss_line2 = "2 25544  51.6406 302.7583 0001012  95.3523  23.3829 15.50234806439337"
        
        self.test_start_time = datetime(2024, 2, 7, 13, 6, 0, tzinfo=timezone.utc)
    
    def test_propagate_orbit_basic(self):
        """Test basic orbit propagation with ISS TLE"""
        result = PropagationService.propagate_orbit(
            self.iss_line1,
            self.iss_line2,
            start_time=self.test_start_time,
            interval_minutes=1
        )
        
        self.assertIn('tle_epoch_position', result)
        self.assertIn('current_position', result)
        self.assertIn('future_positions', result)
        self.assertIn('orbital_period_minutes', result)
        self.assertIn('interval_minutes', result)
        self.assertIn('num_positions', result)
        
        self.assertEqual(result['interval_minutes'], 1)
        self.assertGreater(result['num_positions'], 0)
        
        self.assertAlmostEqual(result['orbital_period_minutes'], 92.8, delta=2.0)
    
    def test_tle_epoch_position_structure(self):
        """Test that TLE epoch position has correct structure"""
        result = PropagationService.propagate_orbit(
            self.iss_line1,
            self.iss_line2,
            start_time=self.test_start_time
        )
        
        tle_epoch_pos = result['tle_epoch_position']
        
        self.assertIn('timestamp', tle_epoch_pos)
        self.assertIn('eci', tle_epoch_pos)
        self.assertIn('geodetic', tle_epoch_pos)
        
        self.assertIn('x_km', tle_epoch_pos['eci'])
        self.assertIn('y_km', tle_epoch_pos['eci'])
        self.assertIn('z_km', tle_epoch_pos['eci'])
        
        self.assertIn('latitude', tle_epoch_pos['geodetic'])
        self.assertIn('longitude', tle_epoch_pos['geodetic'])
        self.assertIn('altitude_km', tle_epoch_pos['geodetic'])
    
    def test_current_position_structure(self):
        """Test that current position has correct structure"""
        result = PropagationService.propagate_orbit(
            self.iss_line1,
            self.iss_line2,
            start_time=self.test_start_time
        )
        
        current_pos = result['current_position']
        
        self.assertIn('timestamp', current_pos)
        self.assertIn('eci', current_pos)
        self.assertIn('geodetic', current_pos)
        
        self.assertEqual(current_pos['timestamp'], self.test_start_time.isoformat())
    
    def test_future_positions_structure(self):
        """Test that future positions have correct structure"""
        result = PropagationService.propagate_orbit(
            self.iss_line1,
            self.iss_line2,
            start_time=self.test_start_time,
            interval_minutes=5
        )
        
        self.assertGreater(len(result['future_positions']), 0)
        
        for position in result['future_positions']:
            self.assertIn('timestamp', position)
            self.assertIn('eci', position)
            self.assertIn('geodetic', position)
            
            geodetic = position['geodetic']
            self.assertGreaterEqual(geodetic['latitude'], -90)
            self.assertLessEqual(geodetic['latitude'], 90)
            self.assertGreaterEqual(geodetic['longitude'], -180)
            self.assertLessEqual(geodetic['longitude'], 180)
            self.assertGreater(geodetic['altitude_km'], 0)
    
    def test_future_positions_start_from_start_time(self):
        """Test that future positions start from start_time, not TLE epoch"""
        result = PropagationService.propagate_orbit(
            self.iss_line1,
            self.iss_line2,
            start_time=self.test_start_time,
            interval_minutes=1
        )
        
        first_position = result['future_positions'][0]
        first_timestamp = datetime.fromisoformat(first_position['timestamp'])
        
        self.assertEqual(first_timestamp, self.test_start_time)
        
        tle_epoch_timestamp = datetime.fromisoformat(result['tle_epoch_position']['timestamp'])
        
        self.assertNotEqual(first_timestamp, tle_epoch_timestamp)
    
    def test_correct_number_of_positions(self):
        """Test that correct number of positions are calculated"""
        interval = 2
        result = PropagationService.propagate_orbit(
            self.iss_line1,
            self.iss_line2,
            start_time=self.test_start_time,
            interval_minutes=interval
        )
        
        expected_positions = int(result['orbital_period_minutes'] / interval) + 1
        
        self.assertEqual(result['num_positions'], len(result['future_positions']))
        self.assertAlmostEqual(result['num_positions'], expected_positions, delta=1)
    
    def test_different_intervals(self):
        """Test propagation with different time intervals"""
        for interval in [1, 2, 5, 10]:
            with self.subTest(interval=interval):
                result = PropagationService.propagate_orbit(
                    self.iss_line1,
                    self.iss_line2,
                    start_time=self.test_start_time,
                    interval_minutes=interval
                )
                
                self.assertEqual(result['interval_minutes'], interval)
                self.assertGreater(result['num_positions'], 0)
                
                if len(result['future_positions']) >= 2:
                    first_time = datetime.fromisoformat(result['future_positions'][0]['timestamp'])
                    second_time = datetime.fromisoformat(result['future_positions'][1]['timestamp'])
                    time_diff = (second_time - first_time).total_seconds() / 60
                    self.assertAlmostEqual(time_diff, interval, delta=0.1)
    
    def test_custom_start_time(self):
        """Test with custom start times"""
        custom_time = datetime(2024, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = PropagationService.propagate_orbit(
            self.iss_line1,
            self.iss_line2,
            start_time=custom_time,
            interval_minutes=1
        )
        
        current_pos_time = datetime.fromisoformat(result['current_position']['timestamp'])
        self.assertEqual(current_pos_time, custom_time)
        
        first_future_time = datetime.fromisoformat(result['future_positions'][0]['timestamp'])
        self.assertEqual(first_future_time, custom_time)
    
    def test_default_start_time(self):
        """Test that default start time is current UTC time"""
        before = datetime.now(timezone.utc)
        result = PropagationService.propagate_orbit(
            self.iss_line1,
            self.iss_line2,
            interval_minutes=1
        )
        after = datetime.now(timezone.utc)
        
        current_pos_time = datetime.fromisoformat(result['current_position']['timestamp'])
        
        self.assertGreaterEqual(current_pos_time, before)
        self.assertLessEqual(current_pos_time, after)
    
    def test_invalid_tle_line1(self):
        """Test error handling for invalid TLE line 1"""
        with self.assertRaises(PropagationError):
            PropagationService.propagate_orbit(
                "invalid line 1",
                self.iss_line2,
                start_time=self.test_start_time
            )
    
    def test_invalid_tle_line2(self):
        """Test error handling for invalid TLE line 2"""
        with self.assertRaises(PropagationError):
            PropagationService.propagate_orbit(
                self.iss_line1,
                "invalid line 2",
                start_time=self.test_start_time
            )
    
    def test_empty_tle(self):
        """Test error handling for empty TLE lines"""
        with self.assertRaises(PropagationError):
            PropagationService.propagate_orbit(
                "",
                "",
                start_time=self.test_start_time
            )
    
    def test_invalid_interval_zero(self):
        """Test error handling for zero interval"""
        with self.assertRaises(ValueError):
            PropagationService.propagate_orbit(
                self.iss_line1,
                self.iss_line2,
                interval_minutes=0
            )
    
    def test_invalid_interval_negative(self):
        """Test error handling for negative interval"""
        with self.assertRaises(ValueError):
            PropagationService.propagate_orbit(
                self.iss_line1,
                self.iss_line2,
                interval_minutes=-5
            )
    
    def test_invalid_interval_too_large(self):
        """Test error handling for too large interval"""
        with self.assertRaises(ValueError):
            PropagationService.propagate_orbit(
                self.iss_line1,
                self.iss_line2,
                interval_minutes=61
            )
    
    def test_geodetic_coordinates_valid_range(self):
        """Test that all geodetic coordinates are in valid ranges"""
        result = PropagationService.propagate_orbit(
            self.iss_line1,
            self.iss_line2,
            start_time=self.test_start_time,
            interval_minutes=1
        )
        
        all_positions = [
            result['tle_epoch_position'],
            result['current_position'],
            *result['future_positions']
        ]
        
        for position in all_positions:
            geodetic = position['geodetic']
            
            self.assertGreaterEqual(geodetic['latitude'], -90)
            self.assertLessEqual(geodetic['latitude'], 90)
            self.assertGreaterEqual(geodetic['longitude'], -180)
            self.assertLessEqual(geodetic['longitude'], 180)
            self.assertGreater(geodetic['altitude_km'], 0)
    
    def test_tle_epoch_matches_line1(self):
        """Test that TLE epoch extracted matches the one in line 1"""
        result = PropagationService.propagate_orbit(
            self.iss_line1,
            self.iss_line2,
            start_time=self.test_start_time
        )
        
        tle_epoch = datetime.fromisoformat(result['tle_epoch'])
        
        self.assertEqual(tle_epoch.year, 2024)
        
        self.assertGreater(tle_epoch.timetuple().tm_yday, 30)
        self.assertLess(tle_epoch.timetuple().tm_yday, 45)
    
    def test_eci_coordinates_reasonable(self):
        """Test that ECI coordinates are reasonable (near Earth orbit)"""
        result = PropagationService.propagate_orbit(
            self.iss_line1,
            self.iss_line2,
            start_time=self.test_start_time
        )
        
        for position in result['future_positions'][:5]:
            eci = position['eci']
            distance = (eci['x_km']**2 + eci['y_km']**2 + eci['z_km']**2) ** 0.5
            
            self.assertGreater(distance, 6371)
            self.assertLess(distance, 8000)
    
    def test_position_formatting(self):
        """Test that position values are properly formatted/rounded"""
        result = PropagationService.propagate_orbit(
            self.iss_line1,
            self.iss_line2,
            start_time=self.test_start_time
        )
        
        geodetic = result['current_position']['geodetic']
        
        lat_str = str(geodetic['latitude'])
        lon_str = str(geodetic['longitude'])
        alt_str = str(geodetic['altitude_km'])
        
        lat_decimals = len(lat_str.split('.')[-1]) if '.' in lat_str else 0
        lon_decimals = len(lon_str.split('.')[-1]) if '.' in lon_str else 0
        alt_decimals = len(alt_str.split('.')[-1]) if '.' in alt_str else 0
        
        self.assertLessEqual(lat_decimals, 6)
        self.assertLessEqual(lon_decimals, 6)
        self.assertLessEqual(alt_decimals, 2)
    
    def test_geo_satellite_period(self):
        """Test propagation with GEO satellite (should have ~24 hour period)"""
        geo_line1 = "1 23439U 94084A   24038.50000000  .00000000  00000-0  00000-0 0  9999"
        geo_line2 = "2 23439   0.0186  68.4954 0002038 269.7896 240.8516  1.00270176 57896"
        
        result = PropagationService.propagate_orbit(
            geo_line1,
            geo_line2,
            start_time=self.test_start_time,
            interval_minutes=10
        )
        
        self.assertAlmostEqual(result['orbital_period_minutes'], 1440, delta=20)
    
    def test_meo_satellite_propagation(self):
        """Test propagation with MEO satellite (GPS, ~12 hour period)"""
        gps_line1 = "1 40105U 14045A   24038.50000000 -.00000000  00000-0  00000+0 0  9999"
        gps_line2 = "2 40105  55.0000 180.0000 0100000 180.0000 180.0000  2.00000000 12345"
        
        result = PropagationService.propagate_orbit(
            gps_line1,
            gps_line2,
            start_time=self.test_start_time,
            interval_minutes=10
        )
        
        self.assertGreater(result['orbital_period_minutes'], 600)
        self.assertLess(result['orbital_period_minutes'], 800)


class TestPropagationServiceHelpers(unittest.TestCase):
    """Test helper methods in PropagationService"""
    
    def test_julian_date_conversion(self):
        """Test Julian date conversion"""
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        jd, fr = PropagationService._julian_date(dt)
        
        self.assertIsInstance(jd, float)
        self.assertIsInstance(fr, float)
        self.assertGreater(jd, 2400000)
    
    def test_eci_to_geodetic_north_pole(self):
        """Test ECI to geodetic conversion at North Pole"""
        result = PropagationService._eci_to_geodetic(0, 0, 6771)
        
        self.assertAlmostEqual(result['latitude'], 90, delta=1)
        self.assertAlmostEqual(result['altitude_km'], 400, delta=10)
    
    def test_eci_to_geodetic_equator(self):
        """Test ECI to geodetic conversion at equator"""
        result = PropagationService._eci_to_geodetic(6771, 0, 0)
        
        self.assertAlmostEqual(result['latitude'], 0, delta=1)
        self.assertAlmostEqual(result['longitude'], 0, delta=1)
        self.assertAlmostEqual(result['altitude_km'], 400, delta=10)


if __name__ == "__main__":
    unittest.main()
