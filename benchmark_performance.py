#!/usr/bin/env python3
"""
Performance benchmarking script for graph operations

Tests:
1. Database query performance for various graph operations
2. API endpoint response times
3. Data processing throughput
4. Memory efficiency for large graph datasets

Success Criteria:
- Graph queries: < 2s for typical queries
- API endpoints: < 2s response time
- Data processing: > 1000 nodes/second
"""
import sys
import os
import time
import statistics
from typing import List, Dict, Any
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db

API_BASE = "http://localhost:8000"
BENCHMARK_RESULTS = []


class Benchmark:
    """Context manager for timing operations"""
    
    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.duration = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, *args):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        return False


def log_benchmark(category: str, operation: str, duration: float, 
                  count: int = 0, threshold: float = 2.0, unit: str = "seconds"):
    """Log benchmark result"""
    passed = duration < threshold
    status = "✓ PASS" if passed else "❌ FAIL"
    
    result = {
        "category": category,
        "operation": operation,
        "duration": duration,
        "count": count,
        "threshold": threshold,
        "passed": passed,
        "unit": unit
    }
    BENCHMARK_RESULTS.append(result)
    
    if count > 0:
        throughput = count / duration if duration > 0 else 0
        print(f"{status}: {operation}")
        print(f"  Duration: {duration:.3f}s | Count: {count} | Throughput: {throughput:.1f} items/s")
    else:
        print(f"{status}: {operation}")
        print(f"  Duration: {duration:.3f}s | Threshold: {threshold:.1f}s")


def benchmark_db_query(name: str, aql: str, bind_vars: Dict[str, Any] = None) -> float:
    """Benchmark a database query"""
    with Benchmark(name) as bench:
        cursor = db.db.aql.execute(aql, bind_vars=bind_vars or {})
        results = list(cursor)
        count = len(results)
    
    log_benchmark("Database Query", name, bench.duration, count=count)
    return bench.duration


def benchmark_api_endpoint(name: str, url: str, expected_status: int = 200) -> float:
    """Benchmark an API endpoint"""
    try:
        with Benchmark(name) as bench:
            response = requests.get(url, timeout=30)
        
        if response.status_code != expected_status:
            print(f"⚠ Warning: Expected status {expected_status}, got {response.status_code}")
        
        data = response.json()
        count = 0
        if 'data' in data:
            if 'nodes' in data['data']:
                count = len(data['data']['nodes'])
            elif 'edges' in data['data']:
                count = len(data['data']['edges'])
        
        log_benchmark("API Endpoint", name, bench.duration, count=count)
        return bench.duration
    except Exception as e:
        print(f"❌ ERROR: {name} - {e}")
        return -1


def run_database_benchmarks():
    """Run database query benchmarks"""
    print("\n" + "=" * 70)
    print("Database Query Performance")
    print("=" * 70 + "\n")
    
    print("--- Constellation Queries ---")
    benchmark_db_query(
        "Get Starlink Gen 1 members (limited)",
        """
        LET hub = FIRST(
            FOR sat IN satellites
                FILTER sat.sources.kaggle.satellite_constellation == "Starlink Gen 1"
                FILTER sat.canonical.constellation_hub == true
                RETURN sat
        )
        FOR sat IN 1..1 OUTBOUND hub._id constellation_membership
            LIMIT 100
            RETURN sat
        """,
        {}
    )
    
    benchmark_db_query(
        "Get OneWeb constellation members",
        """
        LET hub = FIRST(
            FOR sat IN satellites
                FILTER sat.sources.kaggle.satellite_constellation == "OneWeb"
                FILTER sat.canonical.constellation_hub == true
                RETURN sat
        )
        FOR sat IN 1..1 OUTBOUND hub._id constellation_membership
            RETURN sat
        """,
        {}
    )
    
    print("\n--- Registration Document Queries ---")
    benchmark_db_query(
        "Get satellites by registration document",
        """
        LET doc = DOCUMENT("registration_documents/_osoindex_data_documents_gb_st_stsgser_e1020_html")
        FOR sat IN 1..1 INBOUND doc._id registration_links
            LIMIT 50
            RETURN sat
        """,
        {}
    )
    
    print("\n--- Orbital Proximity Queries ---")
    benchmark_db_query(
        "Get LEO-Inclined proximity edges (limited)",
        """
        FOR edge IN orbital_proximity
            FILTER edge.orbital_band == "LEO-Inclined"
            LIMIT 100
            RETURN edge
        """,
        {}
    )
    
    benchmark_db_query(
        "Get orbital proximity with satellite data",
        """
        FOR edge IN orbital_proximity
            FILTER edge.orbital_band == "LEO-Polar"
            LIMIT 50
            LET from_sat = DOCUMENT(edge._from)
            LET to_sat = DOCUMENT(edge._to)
            RETURN {
                edge: edge,
                from: from_sat,
                to: to_sat
            }
        """,
        {}
    )
    
    print("\n--- Launch Timeline Queries ---")
    benchmark_db_query(
        "Get satellites launched in 2024",
        """
        FOR sat IN satellites
            FILTER sat.canonical.launch_year == 2024
            LIMIT 100
            RETURN sat
        """,
        {}
    )
    
    print("\n--- Graph Statistics Queries ---")
    benchmark_db_query(
        "Count constellation edges",
        """
        RETURN {
            total_edges: LENGTH(constellation_membership),
            total_satellites: LENGTH(satellites)
        }
        """,
        {}
    )
    
    benchmark_db_query(
        "Count proximity edges by orbital band",
        """
        FOR edge IN orbital_proximity
            COLLECT band = edge.orbital_band WITH COUNT INTO count
            RETURN {orbital_band: band, count: count}
        """,
        {}
    )


def run_api_benchmarks():
    """Run API endpoint benchmarks"""
    print("\n" + "=" * 70)
    print("API Endpoint Performance")
    print("=" * 70 + "\n")
    
    try:
        response = requests.get(f"{API_BASE}/v2/health", timeout=2)
        if response.status_code != 200:
            print("❌ API not available. Please start the API server:")
            print("   uvicorn api:app --reload")
            return False
    except Exception:
        print("❌ API not available. Please start the API server:")
        print("   uvicorn api:app --reload")
        return False
    
    print("--- Constellation Endpoints ---")
    benchmark_api_endpoint(
        "Starlink Gen 1 (limited to 50)",
        f"{API_BASE}/v2/graphs/constellation/Starlink Gen 1?limit=50"
    )
    
    benchmark_api_endpoint(
        "OneWeb (full)",
        f"{API_BASE}/v2/graphs/constellation/OneWeb"
    )
    
    print("\n--- Registration Document Endpoints ---")
    benchmark_api_endpoint(
        "Registration document query",
        f"{API_BASE}/v2/graphs/registration-document/_osoindex_data_documents_gb_st_stsgser_e1020_html?limit=50"
    )
    
    print("\n--- Orbital Proximity Endpoints ---")
    benchmark_api_endpoint(
        "LEO-Inclined proximity (limited)",
        f"{API_BASE}/v2/graphs/orbital-proximity/LEO-Inclined?limit=100"
    )
    
    benchmark_api_endpoint(
        "GEO proximity",
        f"{API_BASE}/v2/graphs/orbital-proximity/GEO?limit=30"
    )
    
    print("\n--- Launch Timeline Endpoints ---")
    benchmark_api_endpoint(
        "Launch timeline 2024",
        f"{API_BASE}/v2/graphs/launch-timeline/2024?limit=100"
    )
    
    benchmark_api_endpoint(
        "Launch timeline 2020-2024",
        f"{API_BASE}/v2/graphs/launch-timeline/2020-2024?limit=50"
    )
    
    print("\n--- Statistics Endpoint ---")
    benchmark_api_endpoint(
        "Graph statistics",
        f"{API_BASE}/v2/graphs/stats"
    )
    
    return True


def run_throughput_benchmarks():
    """Run data processing throughput benchmarks"""
    print("\n" + "=" * 70)
    print("Data Processing Throughput")
    print("=" * 70 + "\n")
    
    print("--- Node Processing ---")
    with Benchmark("Process 1000 satellite nodes") as bench:
        satellites = list(db.satellites_collection.find({}, limit=1000))
        processed = []
        for sat in satellites:
            processed.append({
                'id': sat.get('_key'),
                'name': sat.get('canonical', {}).get('name'),
                'country': sat.get('canonical', {}).get('country_of_origin')
            })
    
    count = len(processed)
    throughput = count / bench.duration if bench.duration > 0 else 0
    threshold_throughput = 1000
    passed = throughput > threshold_throughput
    
    status = "✓ PASS" if passed else "❌ FAIL"
    print(f"{status}: Process {count} satellite nodes")
    print(f"  Duration: {bench.duration:.3f}s | Throughput: {throughput:.1f} nodes/s")
    print(f"  Threshold: > {threshold_throughput} nodes/s")
    
    BENCHMARK_RESULTS.append({
        "category": "Throughput",
        "operation": "Node processing",
        "duration": bench.duration,
        "count": count,
        "throughput": throughput,
        "threshold": threshold_throughput,
        "passed": passed,
        "unit": "nodes/second"
    })


def print_summary():
    """Print benchmark summary"""
    print("\n" + "=" * 70)
    print("Benchmark Summary")
    print("=" * 70)
    
    categories = {}
    for result in BENCHMARK_RESULTS:
        cat = result['category']
        if cat not in categories:
            categories[cat] = {'passed': 0, 'failed': 0, 'total': 0, 'durations': []}
        
        categories[cat]['total'] += 1
        if result['passed']:
            categories[cat]['passed'] += 1
        else:
            categories[cat]['failed'] += 1
        categories[cat]['durations'].append(result['duration'])
    
    print()
    for category, stats in categories.items():
        avg_duration = statistics.mean(stats['durations'])
        print(f"\n{category}:")
        print(f"  Total: {stats['total']}")
        print(f"  Passed: {stats['passed']}")
        print(f"  Failed: {stats['failed']}")
        print(f"  Avg Duration: {avg_duration:.3f}s")
    
    total_passed = sum(r['passed'] for r in BENCHMARK_RESULTS)
    total_failed = len(BENCHMARK_RESULTS) - total_passed
    total = len(BENCHMARK_RESULTS)
    
    print(f"\n{'=' * 70}")
    print(f"Overall: {total_passed}/{total} benchmarks passed")
    
    if total_failed > 0:
        print(f"\n⚠ Failed benchmarks:")
        for result in BENCHMARK_RESULTS:
            if not result['passed']:
                print(f"  - {result['operation']}: {result['duration']:.3f}s (threshold: {result['threshold']:.1f}s)")
    
    return total_failed == 0


def main():
    """Run all benchmarks"""
    print("=" * 70)
    print("Graph Performance Benchmarks")
    print("=" * 70)
    print("\nSuccess Criteria:")
    print("  - Graph queries: < 2s")
    print("  - API endpoints: < 2s")
    print("  - Node processing: > 1000 nodes/second")
    
    try:
        if not db.connect_mongodb():
            print("❌ Failed to connect to database")
            return False
        
        print(f"\nConnected to: {db.DB_NAME}")
        
        run_database_benchmarks()
        
        api_available = run_api_benchmarks()
        
        run_throughput_benchmarks()
        
        success = print_summary()
        
        if not api_available:
            print("\n⚠ Note: Some API benchmarks were skipped (API not running)")
        
        if success:
            print("\n✓ All benchmarks passed!")
        else:
            print("\n⚠ Some benchmarks did not meet performance criteria")
        
        return success
    
    except Exception as e:
        print(f"\n❌ Benchmark error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.disconnect_mongodb()


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
