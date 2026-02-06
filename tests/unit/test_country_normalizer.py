import unittest
from database.utils.normalization import CountryNormalizer, normalize_country


class TestCountryNormalizer(unittest.TestCase):
    """Test cases for CountryNormalizer"""
    
    def setUp(self):
        """Set up test normalizer instance"""
        self.normalizer = CountryNormalizer()
    
    def test_normalize_us_codes(self):
        """Test normalizing various US country codes"""
        self.assertEqual(self.normalizer.normalize("US"), "USA")
        self.assertEqual(self.normalizer.normalize("USA"), "USA")
        self.assertEqual(self.normalizer.normalize("United States"), "USA")
        self.assertEqual(self.normalizer.normalize("UNITED STATES"), "USA")
    
    def test_normalize_uk_codes(self):
        """Test normalizing UK country codes"""
        self.assertEqual(self.normalizer.normalize("UK"), "GBR")
        self.assertEqual(self.normalizer.normalize("GBR"), "GBR")
        self.assertEqual(self.normalizer.normalize("United Kingdom"), "GBR")
    
    def test_normalize_china_codes(self):
        """Test normalizing China country codes"""
        self.assertEqual(self.normalizer.normalize("PRC"), "CHN")
        self.assertEqual(self.normalizer.normalize("China"), "CHN")
        self.assertEqual(self.normalizer.normalize("CHN"), "CHN")
    
    def test_normalize_russia_codes(self):
        """Test normalizing Russia/USSR codes"""
        self.assertEqual(self.normalizer.normalize("USSR"), "USSR")
        self.assertEqual(self.normalizer.normalize("Russia"), "RUS")
        self.assertEqual(self.normalizer.normalize("Russian Federation"), "RUS")
        self.assertEqual(self.normalizer.normalize("CIS"), "CIS")
    
    def test_normalize_case_insensitive(self):
        """Test that normalization is case insensitive"""
        self.assertEqual(self.normalizer.normalize("us"), "USA")
        self.assertEqual(self.normalizer.normalize("Us"), "USA")
        self.assertEqual(self.normalizer.normalize("united states"), "USA")
    
    def test_normalize_with_whitespace(self):
        """Test normalization with leading/trailing whitespace"""
        self.assertEqual(self.normalizer.normalize("  US  "), "USA")
        self.assertEqual(self.normalizer.normalize("\tUK\n"), "GBR")
    
    def test_normalize_none_and_empty(self):
        """Test normalization with None and empty strings"""
        self.assertIsNone(self.normalizer.normalize(None))
        self.assertIsNone(self.normalizer.normalize(""))
        self.assertIsNone(self.normalizer.normalize("   "))
    
    def test_normalize_unknown_country(self):
        """Test normalization with unknown country code"""
        self.assertEqual(self.normalizer.normalize("UNKNOWN"), "UNKNOWN")
        self.assertEqual(self.normalizer.normalize("XYZ"), "XYZ")
    
    def test_normalize_organizations(self):
        """Test normalization of space organizations"""
        self.assertEqual(self.normalizer.normalize("ESA"), "ESA")
        self.assertEqual(self.normalizer.normalize("ITSO"), "ITSO")
        self.assertEqual(self.normalizer.normalize("EUTE"), "EUTELSAT")
        self.assertEqual(self.normalizer.normalize("EUME"), "EUMETSAT")
    
    def test_normalize_special_characters(self):
        """Test normalization with special characters"""
        self.assertEqual(self.normalizer.normalize("Türkiye"), "TUR")
        self.assertEqual(self.normalizer.normalize("TÜRKIYE"), "TUR")
    
    def test_get_all_mappings(self):
        """Test getting all country mappings"""
        mappings = self.normalizer.get_all_mappings()
        
        self.assertIsInstance(mappings, dict)
        self.assertGreater(len(mappings), 100)
        self.assertEqual(mappings["USA"], "USA")
        self.assertEqual(mappings["UK"], "GBR")
    
    def test_get_all_mappings_returns_copy(self):
        """Test that get_all_mappings returns a copy"""
        mappings1 = self.normalizer.get_all_mappings()
        mappings1["TEST"] = "TEST"
        
        mappings2 = self.normalizer.get_all_mappings()
        self.assertNotIn("TEST", mappings2)
    
    def test_has_mapping(self):
        """Test checking if mapping exists"""
        self.assertTrue(self.normalizer.has_mapping("US"))
        self.assertTrue(self.normalizer.has_mapping("United States"))
        self.assertTrue(self.normalizer.has_mapping("uk"))
        self.assertFalse(self.normalizer.has_mapping("UNKNOWN"))
        self.assertFalse(self.normalizer.has_mapping(None))
        self.assertFalse(self.normalizer.has_mapping(""))
    
    def test_convenience_function(self):
        """Test normalize_country convenience function"""
        self.assertEqual(normalize_country("US"), "USA")
        self.assertEqual(normalize_country("UK"), "GBR")
        self.assertIsNone(normalize_country(None))
    
    def test_various_countries(self):
        """Test normalization of various countries"""
        test_cases = [
            ("Japan", "JPN"),
            ("Spain", "ESP"),
            ("Germany", "DEU"),
            ("France", "FRA"),
            ("Italy", "ITA"),
            ("India", "IND"),
            ("South Korea", "KOR"),
            ("Canada", "CAN"),
            ("Australia", "AUS"),
            ("Brazil", "BRA"),
            ("Mexico", "MEX"),
            ("Singapore", "SGP"),
            ("Saudi Arabia", "SAU"),
        ]
        
        for input_val, expected in test_cases:
            with self.subTest(country=input_val):
                self.assertEqual(self.normalizer.normalize(input_val), expected)


if __name__ == "__main__":
    unittest.main()
