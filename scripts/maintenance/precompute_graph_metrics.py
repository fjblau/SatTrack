#!/usr/bin/env python3
"""
Background job for pre-computing expensive graph metrics.

This script computes and caches expensive graph analytics that are frequently requested:
- Centrality metrics (degree, betweenness, closeness)
- Community detection results
- Global graph statistics
- Collision risk clusters

Run this script periodically (e.g., daily via cron) to keep cached metrics fresh.
"""
import sys
import os
import logging
import time
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from database.graph_analytics import (
    calculate_degree_centrality,
    calculate_betweenness_centrality,
    calculate_closeness_centrality,
    detect_communities,
    analyze_collision_clusters
)
from api.services.cache_service import get_cache
import database.connection as db_conn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/precompute_graph_metrics.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MetricPrecomputer:
    """Precompute and cache expensive graph metrics."""
    
    def __init__(self):
        self.centrality_cache = get_cache("centrality_queries", ttl=43200, max_size=500)
        self.community_cache = get_cache("community_queries", ttl=43200, max_size=300)
        self.collision_cache = get_cache("collision_queries", ttl=7200, max_size=400)
        self.stats = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "metrics_computed": [],
            "total_time": 0,
            "errors": []
        }
    
    def precompute_degree_centrality(self):
        """Precompute degree centrality for all edge types."""
        logger.info("Computing degree centrality...")
        start_time = time.time()
        
        try:
            # Default (all edge types)
            results = calculate_degree_centrality(limit=100)
            cache_key = "degree_all_100"
            self.centrality_cache.set(cache_key, {
                "metric": "degree",
                "satellites": results,
                "count": len(results),
                "parameters": {"edge_types": None, "limit": 100}
            })
            
            elapsed = time.time() - start_time
            self.stats["metrics_computed"].append({
                "metric": "degree_centrality",
                "time": elapsed,
                "results": len(results)
            })
            logger.info(f"Degree centrality computed in {elapsed:.2f}s ({len(results)} results)")
            
        except Exception as e:
            logger.error(f"Error computing degree centrality: {e}")
            self.stats["errors"].append(f"degree_centrality: {str(e)}")
    
    def precompute_betweenness_centrality(self):
        """Precompute betweenness centrality (expensive operation)."""
        logger.info("Computing betweenness centrality (this may take a while)...")
        start_time = time.time()
        
        try:
            # Use smaller sample size for background job to balance accuracy vs speed
            results = calculate_betweenness_centrality(
                limit=50,
                sample_size=50
            )
            cache_key = "betweenness_all_50_50"
            self.centrality_cache.set(cache_key, {
                "metric": "betweenness",
                "satellites": results,
                "count": len(results),
                "parameters": {
                    "edge_types": None,
                    "limit": 50,
                    "sample_size": 50
                }
            })
            
            elapsed = time.time() - start_time
            self.stats["metrics_computed"].append({
                "metric": "betweenness_centrality",
                "time": elapsed,
                "results": len(results)
            })
            logger.info(f"Betweenness centrality computed in {elapsed:.2f}s ({len(results)} results)")
            
        except Exception as e:
            logger.error(f"Error computing betweenness centrality: {e}")
            self.stats["errors"].append(f"betweenness_centrality: {str(e)}")
    
    def precompute_closeness_centrality(self):
        """Precompute closeness centrality."""
        logger.info("Computing closeness centrality...")
        start_time = time.time()
        
        try:
            results = calculate_closeness_centrality(
                limit=50,
                max_depth=5
            )
            cache_key = "closeness_all_50_5"
            self.centrality_cache.set(cache_key, {
                "metric": "closeness",
                "satellites": results,
                "count": len(results),
                "parameters": {
                    "edge_types": None,
                    "limit": 50,
                    "max_depth": 5
                }
            })
            
            elapsed = time.time() - start_time
            self.stats["metrics_computed"].append({
                "metric": "closeness_centrality",
                "time": elapsed,
                "results": len(results)
            })
            logger.info(f"Closeness centrality computed in {elapsed:.2f}s ({len(results)} results)")
            
        except Exception as e:
            logger.error(f"Error computing closeness centrality: {e}")
            self.stats["errors"].append(f"closeness_centrality: {str(e)}")
    
    def precompute_communities(self):
        """Precompute community detection."""
        logger.info("Computing communities...")
        start_time = time.time()
        
        try:
            results = detect_communities(
                algorithm="label_propagation",
                min_community_size=5
            )
            cache_key = "communities_label_propagation_5"
            self.community_cache.set(cache_key, {
                "algorithm": "label_propagation",
                "communities": results,
                "count": len(results),
                "parameters": {
                    "algorithm": "label_propagation",
                    "min_community_size": 5
                }
            })
            
            elapsed = time.time() - start_time
            self.stats["metrics_computed"].append({
                "metric": "communities",
                "time": elapsed,
                "results": len(results)
            })
            logger.info(f"Communities computed in {elapsed:.2f}s ({len(results)} results)")
            
        except Exception as e:
            logger.error(f"Error computing communities: {e}")
            self.stats["errors"].append(f"communities: {str(e)}")
    
    def precompute_collision_clusters(self):
        """Precompute collision risk clusters for different orbital bands."""
        logger.info("Computing collision risk clusters...")
        
        orbital_bands = ["LEO", "MEO", "GEO"]
        
        for band in orbital_bands:
            start_time = time.time()
            
            try:
                results = analyze_collision_clusters(
                    orbital_band=band,
                    risk_threshold=0.7,
                    min_cluster_size=3
                )
                cache_key = f"collision_clusters_{band}_0.7_3"
                self.collision_cache.set(cache_key, {
                    "clusters": results,
                    "count": len(results),
                    "parameters": {
                        "orbital_band": band,
                        "risk_threshold": 0.7,
                        "min_cluster_size": 3
                    }
                })
                
                elapsed = time.time() - start_time
                self.stats["metrics_computed"].append({
                    "metric": f"collision_clusters_{band}",
                    "time": elapsed,
                    "results": len(results)
                })
                logger.info(
                    f"Collision clusters for {band} computed in {elapsed:.2f}s "
                    f"({len(results)} results)"
                )
                
            except Exception as e:
                logger.error(f"Error computing collision clusters for {band}: {e}")
                self.stats["errors"].append(f"collision_clusters_{band}: {str(e)}")
    
    def run(self):
        """Run all precomputation tasks."""
        logger.info("=" * 60)
        logger.info("Starting graph metrics precomputation")
        logger.info("=" * 60)
        
        overall_start = time.time()
        
        # Run computations in order of importance/frequency
        self.precompute_degree_centrality()
        self.precompute_communities()
        self.precompute_collision_clusters()
        
        # Skip expensive operations if running frequently
        # Uncomment these for less frequent (e.g., daily) runs
        # self.precompute_betweenness_centrality()
        # self.precompute_closeness_centrality()
        
        self.stats["total_time"] = time.time() - overall_start
        self.stats["completed_at"] = datetime.now(timezone.utc).isoformat()
        
        logger.info("=" * 60)
        logger.info("Precomputation completed")
        logger.info(f"Total time: {self.stats['total_time']:.2f}s")
        logger.info(f"Metrics computed: {len(self.stats['metrics_computed'])}")
        logger.info(f"Errors: {len(self.stats['errors'])}")
        logger.info("=" * 60)
        
        return self.stats


def main():
    """Main entry point."""
    try:
        # Verify database connection
        if not db_conn.db:
            logger.error("Failed to connect to database")
            sys.exit(1)
        
        precomputer = MetricPrecomputer()
        stats = precomputer.run()
        
        # Print summary
        print("\n" + "=" * 60)
        print("PRECOMPUTATION SUMMARY")
        print("=" * 60)
        print(f"Started: {stats['started_at']}")
        print(f"Completed: {stats['completed_at']}")
        print(f"Total time: {stats['total_time']:.2f}s")
        print(f"\nMetrics computed: {len(stats['metrics_computed'])}")
        for metric in stats['metrics_computed']:
            print(f"  - {metric['metric']}: {metric['time']:.2f}s ({metric['results']} results)")
        
        if stats['errors']:
            print(f"\nErrors encountered: {len(stats['errors'])}")
            for error in stats['errors']:
                print(f"  - {error}")
        
        print("=" * 60)
        
        sys.exit(0 if not stats['errors'] else 1)
    
    except Exception as e:
        logger.error(f"Fatal error in precomputation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
