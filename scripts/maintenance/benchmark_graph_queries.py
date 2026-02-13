#!/usr/bin/env python3
"""
Benchmark script for graph query performance.

Tests key graph operations and reports timing metrics to evaluate optimization effectiveness.
"""
import sys
import os
import time
import statistics
from typing import List, Dict, Any
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from database.graph_analytics import (
    calculate_degree_centrality,
    calculate_betweenness_centrality,
    calculate_closeness_centrality,
    find_shortest_path,
    detect_communities,
    analyze_collision_clusters
)
import database.connection as db_conn
from database.connection import COLLECTION_NAME


class GraphBenchmark:
    """Benchmark graph query performance."""
    
    def __init__(self, num_runs: int = 3):
        self.num_runs = num_runs
        self.results = []
    
    def _run_benchmark(
        self,
        name: str,
        func,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run a benchmark multiple times and collect statistics.
        
        Args:
            name: Name of the benchmark
            func: Function to benchmark
            *args, **kwargs: Arguments to pass to function
        
        Returns:
            Dictionary with benchmark results
        """
        print(f"\n{'='*60}")
        print(f"Benchmarking: {name}")
        print(f"{'='*60}")
        
        times = []
        result_sizes = []
        
        for i in range(self.num_runs):
            print(f"Run {i+1}/{self.num_runs}...", end=" ", flush=True)
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                
                times.append(elapsed)
                
                if isinstance(result, list):
                    result_sizes.append(len(result))
                elif isinstance(result, dict):
                    result_sizes.append(len(result))
                else:
                    result_sizes.append(0)
                
                print(f"{elapsed:.3f}s ✓")
            
            except Exception as e:
                elapsed = time.time() - start_time
                times.append(elapsed)
                result_sizes.append(0)
                print(f"{elapsed:.3f}s ✗ Error: {str(e)}")
        
        # Calculate statistics
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        stddev = statistics.stdev(times) if len(times) > 1 else 0
        avg_size = statistics.mean(result_sizes) if result_sizes else 0
        
        result = {
            "name": name,
            "runs": self.num_runs,
            "times": times,
            "avg_time": avg_time,
            "min_time": min_time,
            "max_time": max_time,
            "stddev": stddev,
            "avg_result_size": avg_size
        }
        
        print(f"\nResults:")
        print(f"  Average time: {avg_time:.3f}s")
        print(f"  Min time: {min_time:.3f}s")
        print(f"  Max time: {max_time:.3f}s")
        print(f"  Std dev: {stddev:.3f}s")
        print(f"  Avg result size: {avg_size:.0f}")
        
        self.results.append(result)
        return result
    
    def benchmark_degree_centrality(self):
        """Benchmark degree centrality calculation."""
        self._run_benchmark(
            "Degree Centrality (limit=100)",
            calculate_degree_centrality,
            limit=100
        )
    
    def benchmark_betweenness_centrality(self):
        """Benchmark betweenness centrality calculation."""
        self._run_benchmark(
            "Betweenness Centrality (limit=50, sample=50)",
            calculate_betweenness_centrality,
            limit=50,
            sample_size=50
        )
    
    def benchmark_closeness_centrality(self):
        """Benchmark closeness centrality calculation."""
        self._run_benchmark(
            "Closeness Centrality (limit=50, depth=5)",
            calculate_closeness_centrality,
            limit=50,
            max_depth=5
        )
    
    def benchmark_path_finding(self):
        """Benchmark path finding between random satellites."""
        # Get some sample satellite IDs
        query = f"""
        FOR doc IN {COLLECTION_NAME}
            LIMIT 10
            RETURN doc._id
        """
        cursor = db_conn.db.aql.execute(query)
        satellite_ids = list(cursor)
        
        if len(satellite_ids) >= 2:
            self._run_benchmark(
                f"Shortest Path Finding ({satellite_ids[0]} -> {satellite_ids[1]})",
                find_shortest_path,
                from_id=satellite_ids[0],
                to_id=satellite_ids[1],
                max_depth=10
            )
    
    def benchmark_community_detection(self):
        """Benchmark community detection."""
        self._run_benchmark(
            "Community Detection (label_propagation, min_size=5)",
            detect_communities,
            algorithm="label_propagation",
            min_community_size=5
        )
    
    def benchmark_collision_clusters(self):
        """Benchmark collision cluster analysis."""
        self._run_benchmark(
            "Collision Risk Clusters (LEO, threshold=0.7)",
            analyze_collision_clusters,
            orbital_band="LEO",
            risk_threshold=0.7,
            min_cluster_size=3
        )
    
    def run_all(self):
        """Run all benchmarks."""
        print("\n" + "="*60)
        print("GRAPH QUERY PERFORMANCE BENCHMARK")
        print(f"Started: {datetime.now().isoformat()}")
        print(f"Number of runs per benchmark: {self.num_runs}")
        print("="*60)
        
        overall_start = time.time()
        
        # Run benchmarks
        self.benchmark_degree_centrality()
        self.benchmark_path_finding()
        self.benchmark_community_detection()
        self.benchmark_collision_clusters()
        
        # Optional: expensive benchmarks
        # Uncomment to include betweenness and closeness
        # self.benchmark_betweenness_centrality()
        # self.benchmark_closeness_centrality()
        
        total_time = time.time() - overall_start
        
        # Print summary
        self._print_summary(total_time)
    
    def _print_summary(self, total_time: float):
        """Print benchmark summary."""
        print("\n" + "="*60)
        print("BENCHMARK SUMMARY")
        print("="*60)
        
        print(f"\nTotal benchmark time: {total_time:.2f}s")
        print(f"Benchmarks run: {len(self.results)}")
        
        print("\n" + "-"*60)
        print(f"{'Benchmark':<45} {'Avg Time':<15}")
        print("-"*60)
        
        for result in self.results:
            name = result['name']
            if len(name) > 44:
                name = name[:41] + "..."
            print(f"{name:<45} {result['avg_time']:>8.3f}s")
        
        print("-"*60)
        
        # Identify slowest queries
        slowest = sorted(
            self.results,
            key=lambda x: x['avg_time'],
            reverse=True
        )[:3]
        
        print("\nSlowest queries:")
        for i, result in enumerate(slowest, 1):
            print(f"  {i}. {result['name']}: {result['avg_time']:.3f}s")
        
        # Performance ratings
        print("\nPerformance ratings:")
        for result in self.results:
            avg = result['avg_time']
            if avg < 1.0:
                rating = "Excellent ⚡"
            elif avg < 3.0:
                rating = "Good ✓"
            elif avg < 10.0:
                rating = "Acceptable ⚠"
            else:
                rating = "Needs optimization ⚠⚠"
            
            print(f"  {result['name']}: {rating}")
        
        print("\n" + "="*60)
        print(f"Completed: {datetime.now().isoformat()}")
        print("="*60)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Benchmark graph query performance"
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs per benchmark (default: 3)"
    )
    args = parser.parse_args()
    
    try:
        # Verify database connection
        if not db_conn.db:
            print("ERROR: Failed to connect to database")
            sys.exit(1)
        
        benchmark = GraphBenchmark(num_runs=args.runs)
        benchmark.run_all()
        
        sys.exit(0)
    
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
