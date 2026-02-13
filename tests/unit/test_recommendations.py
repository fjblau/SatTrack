import unittest
from unittest.mock import Mock, patch, MagicMock
from database.graph_analytics import (
    calculate_jaccard_similarity,
    get_similar_satellites,
    get_neighbor_based_recommendations,
    get_collaborative_filtering_recommendations
)


class TestRecommendations(unittest.TestCase):
    """Test cases for recommendation functions"""
    
    def setUp(self):
        """Set up mock database"""
        self.mock_db = Mock()
        self.mock_cursor = Mock()
    
    @patch('database.graph_analytics.db')
    def test_calculate_jaccard_similarity_basic(self, mock_db):
        """Test calculating Jaccard similarity between two satellites"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([0.5]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = calculate_jaccard_similarity(
            "satellites/SAT1",
            "satellites/SAT2"
        )
        
        self.assertEqual(result, 0.5)
        mock_db.aql.execute.assert_called_once()
    
    @patch('database.graph_analytics.db')
    def test_calculate_jaccard_similarity_no_common_neighbors(self, mock_db):
        """Test Jaccard similarity with no common neighbors"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([0.0]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = calculate_jaccard_similarity(
            "satellites/SAT1",
            "satellites/SAT3"
        )
        
        self.assertEqual(result, 0.0)
    
    @patch('database.graph_analytics.db')
    def test_calculate_jaccard_similarity_with_edge_types(self, mock_db):
        """Test Jaccard similarity with specific edge types"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([0.75]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = calculate_jaccard_similarity(
            "satellites/SAT1",
            "satellites/SAT2",
            edge_types=["orbital_proximity"]
        )
        
        self.assertEqual(result, 0.75)
        call_args = mock_db.aql.execute.call_args
        query = call_args[0][0]
        self.assertIn("orbital_proximity", query)
    
    @patch('database.graph_analytics.db')
    def test_get_similar_satellites_basic(self, mock_db):
        """Test finding similar satellites"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([
            {
                "_id": "satellites/SAT2",
                "identifier": "2025-002A",
                "name": "Test Sat 2",
                "country": "USA",
                "orbital_band": "LEO",
                "similarity_score": 0.8,
                "common_neighbors": 4,
                "total_neighbors": 5
            },
            {
                "_id": "satellites/SAT3",
                "identifier": "2025-003A",
                "name": "Test Sat 3",
                "country": "USA",
                "orbital_band": "LEO",
                "similarity_score": 0.6,
                "common_neighbors": 3,
                "total_neighbors": 5
            }
        ]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = get_similar_satellites("satellites/SAT1", limit=2)
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["similarity_score"], 0.8)
        self.assertEqual(result[1]["similarity_score"], 0.6)
        self.assertGreater(result[0]["similarity_score"], result[1]["similarity_score"])
    
    @patch('database.graph_analytics.db')
    def test_get_similar_satellites_with_min_similarity(self, mock_db):
        """Test finding similar satellites with minimum similarity threshold"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([
            {
                "_id": "satellites/SAT2",
                "identifier": "2025-002A",
                "name": "Test Sat 2",
                "country": "USA",
                "orbital_band": "LEO",
                "similarity_score": 0.8,
                "common_neighbors": 4,
                "total_neighbors": 5
            }
        ]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = get_similar_satellites(
            "satellites/SAT1",
            min_similarity=0.5,
            limit=10
        )
        
        self.assertEqual(len(result), 1)
        self.assertGreaterEqual(result[0]["similarity_score"], 0.5)
        call_args = mock_db.aql.execute.call_args
        bind_vars = call_args[1]['bind_vars']
        self.assertEqual(bind_vars['min_similarity'], 0.5)
    
    @patch('database.graph_analytics.db')
    def test_get_similar_satellites_empty_result(self, mock_db):
        """Test finding similar satellites when none exist"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = get_similar_satellites("satellites/SAT_ISOLATED", limit=10)
        
        self.assertEqual(len(result), 0)
    
    @patch('database.graph_analytics.db')
    def test_get_neighbor_based_recommendations_similar_neighbors(self, mock_db):
        """Test neighbor-based recommendations with similar_neighbors strategy"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([
            {
                "_id": "satellites/SAT4",
                "identifier": "2025-004A",
                "name": "Test Sat 4",
                "country": "USA",
                "orbital_band": "LEO",
                "relevance_score": 3,
                "recommendation_type": "similar_neighbors"
            }
        ]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = get_neighbor_based_recommendations(
            "satellites/SAT1",
            strategy="similar_neighbors",
            limit=5
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["recommendation_type"], "similar_neighbors")
        self.assertEqual(result[0]["relevance_score"], 3)
    
    @patch('database.graph_analytics.db')
    def test_get_neighbor_based_recommendations_second_degree(self, mock_db):
        """Test neighbor-based recommendations with second_degree strategy"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([
            {
                "_id": "satellites/SAT5",
                "identifier": "2025-005A",
                "name": "Test Sat 5",
                "country": "USA",
                "orbital_band": "LEO",
                "relevance_score": 2,
                "recommendation_type": "second_degree"
            }
        ]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = get_neighbor_based_recommendations(
            "satellites/SAT1",
            strategy="second_degree",
            limit=5
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["recommendation_type"], "second_degree")
    
    @patch('database.graph_analytics.db')
    def test_get_neighbor_based_recommendations_common_neighbors(self, mock_db):
        """Test neighbor-based recommendations with common_neighbors strategy"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([
            {
                "_id": "satellites/SAT6",
                "identifier": "2025-006A",
                "name": "Test Sat 6",
                "country": "USA",
                "orbital_band": "LEO",
                "relevance_score": 5,
                "recommendation_type": "common_neighbors"
            }
        ]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = get_neighbor_based_recommendations(
            "satellites/SAT1",
            strategy="common_neighbors",
            limit=10
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["recommendation_type"], "common_neighbors")
        self.assertEqual(result[0]["relevance_score"], 5)
    
    @patch('database.graph_analytics.db')
    def test_get_neighbor_based_recommendations_invalid_strategy(self, mock_db):
        """Test neighbor-based recommendations with invalid strategy"""
        result = get_neighbor_based_recommendations(
            "satellites/SAT1",
            strategy="invalid_strategy",
            limit=10
        )
        
        self.assertEqual(len(result), 0)
    
    @patch('database.graph_analytics.db')
    def test_get_collaborative_filtering_recommendations_basic(self, mock_db):
        """Test collaborative filtering recommendations"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([
            {
                "_id": "satellites/SAT7",
                "identifier": "2025-007A",
                "name": "Test Sat 7",
                "country": "USA",
                "orbital_band": "LEO",
                "status": "Active",
                "relevance_score": 4,
                "common_connections": 4,
                "recommendation_type": "collaborative_filtering"
            },
            {
                "_id": "satellites/SAT8",
                "identifier": "2025-008A",
                "name": "Test Sat 8",
                "country": "China",
                "orbital_band": "MEO",
                "status": "Active",
                "relevance_score": 3,
                "common_connections": 3,
                "recommendation_type": "collaborative_filtering"
            }
        ]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = get_collaborative_filtering_recommendations(
            "satellites/SAT1",
            limit=2
        )
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["recommendation_type"], "collaborative_filtering")
        self.assertEqual(result[0]["common_connections"], 4)
        self.assertGreaterEqual(result[0]["relevance_score"], result[1]["relevance_score"])
    
    @patch('database.graph_analytics.db')
    def test_get_collaborative_filtering_recommendations_with_min_connections(self, mock_db):
        """Test collaborative filtering with minimum common connections"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([
            {
                "_id": "satellites/SAT9",
                "identifier": "2025-009A",
                "name": "Test Sat 9",
                "country": "USA",
                "orbital_band": "LEO",
                "status": "Active",
                "relevance_score": 5,
                "common_connections": 5,
                "recommendation_type": "collaborative_filtering"
            }
        ]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = get_collaborative_filtering_recommendations(
            "satellites/SAT1",
            min_common_connections=5,
            limit=10
        )
        
        self.assertEqual(len(result), 1)
        self.assertGreaterEqual(result[0]["common_connections"], 5)
        call_args = mock_db.aql.execute.call_args
        bind_vars = call_args[1]['bind_vars']
        self.assertEqual(bind_vars['min_common_connections'], 5)
    
    @patch('database.graph_analytics.db')
    def test_get_collaborative_filtering_recommendations_with_edge_types(self, mock_db):
        """Test collaborative filtering with specific edge types"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = get_collaborative_filtering_recommendations(
            "satellites/SAT1",
            edge_types=["constellation_membership"],
            limit=10
        )
        
        call_args = mock_db.aql.execute.call_args
        query = call_args[0][0]
        self.assertIn("constellation_membership", query)
    
    @patch('database.graph_analytics.db')
    def test_get_collaborative_filtering_recommendations_empty_result(self, mock_db):
        """Test collaborative filtering when no recommendations exist"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = get_collaborative_filtering_recommendations(
            "satellites/SAT_ISOLATED",
            limit=10
        )
        
        self.assertEqual(len(result), 0)
    
    @patch('database.graph_analytics.db')
    def test_recommendations_sorted_by_relevance(self, mock_db):
        """Test that recommendations are sorted by relevance score"""
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = Mock(return_value=iter([
            {
                "_id": "satellites/SAT10",
                "identifier": "2025-010A",
                "name": "High Relevance",
                "country": "USA",
                "orbital_band": "LEO",
                "status": "Active",
                "relevance_score": 10,
                "common_connections": 10,
                "recommendation_type": "collaborative_filtering"
            },
            {
                "_id": "satellites/SAT11",
                "identifier": "2025-011A",
                "name": "Medium Relevance",
                "country": "USA",
                "orbital_band": "LEO",
                "status": "Active",
                "relevance_score": 5,
                "common_connections": 5,
                "recommendation_type": "collaborative_filtering"
            },
            {
                "_id": "satellites/SAT12",
                "identifier": "2025-012A",
                "name": "Low Relevance",
                "country": "USA",
                "orbital_band": "LEO",
                "status": "Active",
                "relevance_score": 2,
                "common_connections": 2,
                "recommendation_type": "collaborative_filtering"
            }
        ]))
        mock_db.aql.execute.return_value = mock_cursor
        
        result = get_collaborative_filtering_recommendations(
            "satellites/SAT1",
            limit=10
        )
        
        self.assertEqual(len(result), 3)
        for i in range(len(result) - 1):
            self.assertGreaterEqual(
                result[i]["relevance_score"],
                result[i + 1]["relevance_score"],
                "Results should be sorted by relevance score in descending order"
            )


if __name__ == '__main__':
    unittest.main()
