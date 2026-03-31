#!/usr/bin/env python3
"""
Populate all observation graph edge collections from existing observation documents.

Usage:
    python scripts/population/populate_observation_edges.py [--time-window 24] [--batch-size 1000]

This script:
  1. Connects to ArangoDB (using ARANGO_HOST, ARANGO_USER, ARANGO_PASSWORD env vars)
  2. Ensures all observation edge collections and the observation_relationships graph exist
  3. Populates four edge collections:
     - observation_satellite_edges: observation -> satellite
     - observation_source_edges: observation -> observation_sources
     - observation_temporal_edges: observation -> observation (sequential chain)
     - observation_correlation_edges: observation -> observation (anomaly co-occurrence)
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

from database.connection import connect_arangodb
from database.observation_graph_ops import populate_all_observation_edges


def main():
    parser = argparse.ArgumentParser(description="Populate observation graph edges")
    parser.add_argument("--time-window", type=int, default=24,
                        help="Time window in hours for anomaly correlation edges (default: 24)")
    parser.add_argument("--batch-size", type=int, default=1000,
                        help="Batch size for bulk inserts (default: 1000)")
    args = parser.parse_args()

    print("Connecting to ArangoDB...")
    if not connect_arangodb():
        print("ERROR: Failed to connect to ArangoDB")
        sys.exit(1)

    print(f"Populating observation edges (time_window={args.time_window}h, batch_size={args.batch_size})...")
    results = populate_all_observation_edges(
        time_window_hours=args.time_window,
        batch_size=args.batch_size,
    )

    print("\nResults:")
    for edge_type, counts in results.items():
        print(f"  {edge_type}: {counts['inserted']} inserted, {counts['skipped']} skipped")

    total_inserted = sum(c["inserted"] for c in results.values())
    print(f"\nTotal edges created: {total_inserted}")


if __name__ == "__main__":
    main()
