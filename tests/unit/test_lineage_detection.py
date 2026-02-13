import unittest
from unittest.mock import Mock, patch, MagicMock
from api.services.lineage_service import (
    detect_satellite_family,
    extract_numeric_series,
    calculate_lineage_similarity,
    detect_lineage_relationships,
    get_satellite_lineage,
    get_lineage_statistics,
    get_satellite_family_tree
)


class TestSatelliteFamilyDetection(unittest.TestCase):
    
    def test_detect_gps_family(self):
        """Test GPS family detection"""
        result = detect_satellite_family("GPS IIA-15")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "GPS")
        self.assertIsNotNone(result[2])
    
    def test_detect_iridium_family(self):
        """Test Iridium family detection"""
        result = detect_satellite_family("IRIDIUM 33")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "IRIDIUM")
    
    def test_detect_starlink_family(self):
        """Test Starlink family detection"""
        result = detect_satellite_family("STARLINK-1234")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "STARLINK")
    
    def test_detect_glonass_family(self):
        """Test GLONASS family detection"""
        result = detect_satellite_family("GLONASS M")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "GLONASS")
        self.assertIsNotNone(result[2])
    
    def test_detect_galileo_family(self):
        """Test Galileo family detection"""
        result = detect_satellite_family("Galileo FOC-3")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "GALILEO")
    
    def test_detect_oneweb_family(self):
        """Test OneWeb family detection"""
        result = detect_satellite_family("OneWeb 0123")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "ONEWEB")
    
    def test_no_family_match(self):
        """Test satellite name with no family match"""
        result = detect_satellite_family("Random Satellite 1")
        self.assertIsNone(result)
    
    def test_empty_name(self):
        """Test empty name"""
        result = detect_satellite_family("")
        self.assertIsNone(result)
    
    def test_none_name(self):
        """Test None name"""
        result = detect_satellite_family(None)
        self.assertIsNone(result)


class TestNumericSeriesExtraction(unittest.TestCase):
    
    def test_extract_number_from_iridium(self):
        """Test extracting number from Iridium satellite"""
        result = extract_numeric_series("IRIDIUM 33")
        self.assertEqual(result, 33)
    
    def test_extract_number_from_starlink(self):
        """Test extracting number from Starlink satellite"""
        result = extract_numeric_series("STARLINK-1234")
        self.assertEqual(result, 1234)
    
    def test_no_number_in_name(self):
        """Test name with no number"""
        result = extract_numeric_series("GPS Block IIA")
        self.assertIsNone(result)
    
    def test_extract_first_number(self):
        """Test extracting first number when multiple exist"""
        result = extract_numeric_series("GPS IIA-15")
        self.assertIsNotNone(result)


class TestLineageSimilarity(unittest.TestCase):
    
    def test_same_family_high_similarity(self):
        """Test satellites from same family have high similarity"""
        score = calculate_lineage_similarity(
            "GPS IIA-1",
            "GPS IIA-2"
        )
        self.assertGreater(score, 0.6)
    
    def test_same_family_different_generation(self):
        """Test satellites from same family but different generations"""
        score = calculate_lineage_similarity(
            "GPS IIA-1",
            "GPS III-1"
        )
        self.assertGreater(score, 0.5)
    
    def test_different_families_low_similarity(self):
        """Test satellites from different families have low similarity"""
        score = calculate_lineage_similarity(
            "GPS IIA-1",
            "IRIDIUM 33"
        )
        self.assertEqual(score, 0.0)
    
    def test_same_manufacturer_bonus(self):
        """Test manufacturer matching adds to similarity"""
        score_with_mfr = calculate_lineage_similarity(
            "GPS IIA-1",
            "GPS IIA-2",
            "Lockheed Martin",
            "Lockheed Martin"
        )
        score_without_mfr = calculate_lineage_similarity(
            "GPS IIA-1",
            "GPS IIA-2"
        )
        self.assertGreater(score_with_mfr, score_without_mfr)
    
    def test_empty_names(self):
        """Test similarity with empty names"""
        score = calculate_lineage_similarity("", "")
        self.assertEqual(score, 0.0)


class TestLineageRelationshipDetection(unittest.TestCase):
    
    def test_detect_gps_lineage(self):
        """Test detecting GPS lineage relationships"""
        satellites = [
            {
                "_id": "satellites/sat1",
                "name": "GPS IIA-1",
                "manufacturer": "Lockheed"
            },
            {
                "_id": "satellites/sat2",
                "name": "GPS IIA-2",
                "manufacturer": "Lockheed"
            },
            {
                "_id": "satellites/sat3",
                "name": "GPS III-1",
                "manufacturer": "Lockheed"
            }
        ]
        
        edges = detect_lineage_relationships(satellites)
        
        self.assertGreater(len(edges), 0)
        for edge in edges:
            self.assertIn("_from", edge)
            self.assertIn("_to", edge)
            self.assertEqual(edge["relationship_type"], "successor")
            self.assertEqual(edge["family_name"], "GPS")
    
    def test_no_lineage_for_single_satellite(self):
        """Test no edges created for single satellite"""
        satellites = [
            {
                "_id": "satellites/sat1",
                "name": "GPS IIA-1",
                "manufacturer": "Lockheed"
            }
        ]
        
        edges = detect_lineage_relationships(satellites)
        self.assertEqual(len(edges), 0)
    
    def test_no_lineage_for_different_families(self):
        """Test no edges between different families"""
        satellites = [
            {
                "_id": "satellites/sat1",
                "name": "GPS IIA-1",
                "manufacturer": "Lockheed"
            },
            {
                "_id": "satellites/sat2",
                "name": "IRIDIUM 33",
                "manufacturer": "Motorola"
            }
        ]
        
        edges = detect_lineage_relationships(satellites)
        self.assertEqual(len(edges), 0)


class TestLineageService(unittest.TestCase):
    
    @patch('api.services.lineage_service.db')
    def test_get_satellite_lineage_both_directions(self, mock_db):
        """Test getting lineage in both directions"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([
            {
                "_id": "satellites/sat1",
                "_key": "sat1",
                "identifier": "2020-001A",
                "canonical": {
                    "name": "GPS III-1"
                }
            }
        ]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = get_satellite_lineage("sat1", direction="both", max_depth=5)
        
        self.assertIn("root", result)
        self.assertIn("ancestors", result)
        self.assertIn("descendants", result)
        self.assertIn("stats", result)
    
    @patch('api.services.lineage_service.db')
    def test_get_satellite_lineage_not_found(self, mock_db):
        """Test getting lineage for non-existent satellite"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([None]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = get_satellite_lineage("nonexistent", direction="both")
        
        self.assertIsNone(result["root"])
        self.assertIn("error", result)
    
    @patch('api.services.lineage_service.db')
    def test_get_lineage_statistics(self, mock_db):
        """Test getting lineage statistics"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([
            {
                "total_edges": 100,
                "families": [
                    {"family": "GPS", "edge_count": 50},
                    {"family": "IRIDIUM", "edge_count": 30}
                ],
                "generation_gap_distribution": [
                    {"generation_gap": 1, "count": 80},
                    {"generation_gap": 2, "count": 20}
                ],
                "gap_stats": {
                    "average": 1.2,
                    "maximum": 2
                }
            }
        ]))
        mock_db.aql.execute.return_value = mock_cursor
        
        stats = get_lineage_statistics()
        
        self.assertEqual(stats["total_edges"], 100)
        self.assertIn("families", stats)
        self.assertIn("gap_stats", stats)
    
    @patch('api.services.lineage_service.db')
    def test_get_satellite_family_tree(self, mock_db):
        """Test getting complete family tree"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([
            {
                "family_name": "GPS",
                "nodes": [
                    {"id": "satellites/sat1", "name": "GPS IIA-1"},
                    {"id": "satellites/sat2", "name": "GPS III-1"}
                ],
                "edges": [
                    {
                        "id": "edge1",
                        "source": "satellites/sat1",
                        "target": "satellites/sat2",
                        "relationship_type": "successor"
                    }
                ],
                "stats": {
                    "total_satellites": 2,
                    "total_edges": 1
                }
            }
        ]))
        mock_db.aql.execute.return_value = mock_cursor
        
        tree = get_satellite_family_tree("GPS")
        
        self.assertEqual(tree["family_name"], "GPS")
        self.assertEqual(len(tree["nodes"]), 2)
        self.assertEqual(len(tree["edges"]), 1)
    
    @patch('api.services.lineage_service.db')
    def test_get_family_tree_empty_family(self, mock_db):
        """Test getting family tree for non-existent family"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([
            {
                "family_name": "UNKNOWN",
                "nodes": [],
                "edges": [],
                "stats": {"total_satellites": 0, "total_edges": 0}
            }
        ]))
        mock_db.aql.execute.return_value = mock_cursor
        
        tree = get_satellite_family_tree("UNKNOWN")
        
        self.assertEqual(len(tree["nodes"]), 0)
        self.assertEqual(len(tree["edges"]), 0)


if __name__ == '__main__':
    unittest.main()
