import unittest
from unittest.mock import Mock, patch, MagicMock
from database.graph_analytics import (
    detect_communities,
    detect_communities_label_propagation,
    find_connected_components
)


class TestCommunityDetection(unittest.TestCase):
    """Test cases for community detection algorithms"""
    
    def setUp(self):
        """Set up mock database"""
        self.mock_db = Mock()
        self.mock_cursor = Mock()
    
    @patch('database.graph_analytics.db')
    def test_detect_communities_label_propagation_success(self, mock_db):
        """Test label propagation community detection"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([[
            {
                "community_id": "satellites/SAT1",
                "size": 5,
                "members": [
                    {"satellite_id": "satellites/SAT1", "satellite_name": "Sat 1"},
                    {"satellite_id": "satellites/SAT2", "satellite_name": "Sat 2"},
                    {"satellite_id": "satellites/SAT3", "satellite_name": "Sat 3"},
                    {"satellite_id": "satellites/SAT4", "satellite_name": "Sat 4"},
                    {"satellite_id": "satellites/SAT5", "satellite_name": "Sat 5"}
                ],
                "internal_edges": 8,
                "density": 0.8,
                "algorithm": "label_propagation"
            },
            {
                "community_id": "satellites/SAT6",
                "size": 3,
                "members": [
                    {"satellite_id": "satellites/SAT6", "satellite_name": "Sat 6"},
                    {"satellite_id": "satellites/SAT7", "satellite_name": "Sat 7"},
                    {"satellite_id": "satellites/SAT8", "satellite_name": "Sat 8"}
                ],
                "internal_edges": 3,
                "density": 0.75,
                "algorithm": "label_propagation"
            }
        ]]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = detect_communities_label_propagation(min_community_size=2)
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["size"], 5)
        self.assertEqual(result[1]["size"], 3)
        self.assertEqual(result[0]["algorithm"], "label_propagation")
        mock_db.aql.execute.assert_called_once()
    
    @patch('database.graph_analytics.db')
    def test_detect_communities_label_propagation_with_edge_types(self, mock_db):
        """Test label propagation with specific edge types"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([[]]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = detect_communities_label_propagation(
            edge_types=["orbital_proximity"],
            min_community_size=3
        )
        
        call_args = mock_db.aql.execute.call_args
        query = call_args[0][0]
        self.assertIn("orbital_proximity", query)
        bind_vars = call_args[1]['bind_vars']
        self.assertEqual(bind_vars['min_community_size'], 3)
    
    @patch('database.graph_analytics.db')
    def test_detect_communities_label_propagation_empty_result(self, mock_db):
        """Test label propagation with no communities found"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([[]]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = detect_communities_label_propagation()
        
        self.assertEqual(result, [])
    
    @patch('database.graph_analytics.db')
    def test_detect_communities_label_propagation_error_handling(self, mock_db):
        """Test error handling in label propagation"""
        mock_db.aql.execute.side_effect = Exception("Database error")
        
        result = detect_communities_label_propagation()
        
        self.assertEqual(result, [])
    
    @patch('database.graph_analytics.detect_communities_label_propagation')
    def test_detect_communities_with_label_propagation_algorithm(self, mock_lp):
        """Test detect_communities wrapper with label propagation"""
        mock_lp.return_value = [
            {"community_id": "test", "size": 5, "algorithm": "label_propagation"}
        ]
        
        result = detect_communities(
            algorithm="label_propagation",
            min_community_size=3
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["algorithm"], "label_propagation")
        mock_lp.assert_called_once_with(
            edge_types=None,
            min_community_size=3,
            max_iterations=10,
            limit=100
        )
    
    @patch('database.graph_analytics.detect_communities_label_propagation')
    def test_detect_communities_with_custom_kwargs(self, mock_lp):
        """Test detect_communities with custom kwargs"""
        mock_lp.return_value = []
        
        result = detect_communities(
            algorithm="label_propagation",
            min_community_size=5,
            max_iterations=20,
            limit=50
        )
        
        mock_lp.assert_called_once_with(
            edge_types=None,
            min_community_size=5,
            max_iterations=20,
            limit=50
        )
    
    @patch('database.graph_analytics.find_connected_components')
    @patch('database.graph_analytics.db')
    def test_detect_communities_with_connected_components(self, mock_db, mock_components):
        """Test detect_communities with connected components algorithm"""
        mock_sat = {
            "canonical": {
                "name": "Test Sat",
                "orbital_band": "LEO",
                "country_of_origin": "USA"
            },
            "identifier": "2025-001A"
        }
        
        mock_collection = Mock()
        mock_collection.get.return_value = mock_sat
        mock_db.collection.return_value = mock_collection
        
        mock_components.return_value = [
            {
                "size": 3,
                "members": ["satellites/SAT1", "satellites/SAT2", "satellites/SAT3"]
            }
        ]
        
        result = detect_communities(
            algorithm="connected_components",
            min_community_size=2
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["algorithm"], "connected_components")
        self.assertEqual(result[0]["size"], 3)
        self.assertIn("orbital_band_distribution", result[0])
        self.assertIn("country_distribution", result[0])
        mock_components.assert_called_once()
    
    @patch('database.graph_analytics.find_connected_components')
    @patch('database.graph_analytics.db')
    def test_detect_communities_connected_components_with_edge_types(self, mock_db, mock_components):
        """Test connected components with specific edge types"""
        mock_components.return_value = []
        
        result = detect_communities(
            algorithm="connected_components",
            edge_types=["constellation_membership"],
            min_community_size=5
        )
        
        mock_components.assert_called_once_with(
            edge_types=["constellation_membership"],
            min_component_size=5
        )
    
    def test_detect_communities_invalid_algorithm(self):
        """Test detect_communities with invalid algorithm"""
        result = detect_communities(algorithm="invalid_algorithm")
        
        self.assertEqual(result, [])
    
    @patch('database.graph_analytics.detect_communities_label_propagation')
    def test_detect_communities_error_handling(self, mock_lp):
        """Test error handling in detect_communities"""
        mock_lp.side_effect = Exception("Algorithm error")
        
        result = detect_communities(algorithm="label_propagation")
        
        self.assertEqual(result, [])
    
    @patch('database.graph_analytics.db')
    def test_label_propagation_with_limit(self, mock_db):
        """Test label propagation respects limit parameter"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([[]]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = detect_communities_label_propagation(limit=50)
        
        call_args = mock_db.aql.execute.call_args
        bind_vars = call_args[1]['bind_vars']
        self.assertEqual(bind_vars['limit'], 50)
    
    @patch('database.graph_analytics.db')
    def test_label_propagation_community_statistics(self, mock_db):
        """Test that label propagation returns correct community statistics"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([[
            {
                "community_id": "satellites/SAT1",
                "size": 4,
                "members": [],
                "internal_edges": 5,
                "density": 0.833,
                "dominant_orbital_band": {"band": "LEO", "count": 3},
                "orbital_band_distribution": [
                    {"band": "LEO", "count": 3},
                    {"band": "MEO", "count": 1}
                ],
                "country_distribution": [
                    {"country": "USA", "count": 2},
                    {"country": "Russia", "count": 2}
                ],
                "algorithm": "label_propagation"
            }
        ]]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = detect_communities_label_propagation()
        
        self.assertEqual(len(result), 1)
        community = result[0]
        self.assertIn("density", community)
        self.assertIn("dominant_orbital_band", community)
        self.assertIn("orbital_band_distribution", community)
        self.assertIn("country_distribution", community)
    
    @patch('database.graph_analytics.find_connected_components')
    @patch('database.graph_analytics.db')
    def test_connected_components_enrichment(self, mock_db, mock_components):
        """Test that connected components are enriched with metadata"""
        mock_sat1 = {
            "canonical": {
                "name": "GPS 1",
                "orbital_band": "MEO",
                "country_of_origin": "USA"
            },
            "identifier": "2020-001A"
        }
        
        mock_sat2 = {
            "canonical": {
                "name": "GPS 2",
                "orbital_band": "MEO",
                "country_of_origin": "USA"
            },
            "identifier": "2020-002A"
        }
        
        mock_collection = Mock()
        mock_collection.get.side_effect = [mock_sat1, mock_sat2]
        mock_db.collection.return_value = mock_collection
        
        mock_components.return_value = [
            {
                "size": 2,
                "members": ["satellites/SAT1", "satellites/SAT2"]
            }
        ]
        
        result = detect_communities(algorithm="connected_components")
        
        self.assertEqual(len(result), 1)
        community = result[0]
        self.assertEqual(len(community["members"]), 2)
        self.assertEqual(len(community["orbital_band_distribution"]), 1)
        self.assertEqual(community["orbital_band_distribution"][0]["band"], "MEO")
        self.assertEqual(community["orbital_band_distribution"][0]["count"], 2)


if __name__ == '__main__':
    unittest.main()
