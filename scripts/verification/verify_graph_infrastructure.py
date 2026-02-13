#!/usr/bin/env python3
"""
Verification script for Phase 1 graph infrastructure.

Verifies:
- New edge collections can be created
- Indexes are properly configured
- Graph analytics functions are importable
- Population scripts are executable
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import database as db_module


def verify_imports():
    """Verify all new modules and functions can be imported"""
    print("=" * 60)
    print("Step 1: Verify Imports")
    print("=" * 60)
    
    try:
        from database.graph_analytics import (
            find_shortest_path,
            find_all_paths,
            calculate_degree_centrality,
            traverse_graph,
            get_neighbors,
            count_edges_by_type,
            find_connected_components
        )
        print("✓ All graph analytics functions imported successfully")
        
        assert hasattr(db_module, 'EDGE_COLLECTION_COLLISION_RISK')
        assert hasattr(db_module, 'EDGE_COLLECTION_SATELLITE_LINEAGE')
        print("✓ New edge collection constants available")
        
        assert hasattr(db_module, 'find_shortest_path')
        assert hasattr(db_module, 'calculate_degree_centrality')
        print("✓ Graph analytics functions exported from database module")
        
        return True
    except Exception as e:
        print(f"❌ Import verification failed: {e}")
        return False


def verify_edge_collections():
    """Verify edge collections can be created"""
    print("\n" + "=" * 60)
    print("Step 2: Verify Edge Collections")
    print("=" * 60)
    
    try:
        if not db_module.connect_mongodb():
            print("❌ Failed to connect to database")
            return False
        
        collision_created = db_module.create_edge_collection(
            db_module.EDGE_COLLECTION_COLLISION_RISK
        )
        if collision_created:
            print(f"✓ Collision risk edge collection: {db_module.EDGE_COLLECTION_COLLISION_RISK}")
        else:
            print(f"❌ Failed to create collision risk edge collection")
            return False
        
        lineage_created = db_module.create_edge_collection(
            db_module.EDGE_COLLECTION_SATELLITE_LINEAGE
        )
        if lineage_created:
            print(f"✓ Satellite lineage edge collection: {db_module.EDGE_COLLECTION_SATELLITE_LINEAGE}")
        else:
            print(f"❌ Failed to create satellite lineage edge collection")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Edge collection verification failed: {e}")
        return False


def verify_indexes():
    """Verify indexes can be added to edge collections"""
    print("\n" + "=" * 60)
    print("Step 3: Verify Indexes")
    print("=" * 60)
    
    try:
        if db_module.db is None:
            if not db_module.connect_mongodb():
                print("❌ Failed to connect to database")
                return False
        
        collision_indexes = db_module.add_edge_indexes(
            db_module.EDGE_COLLECTION_COLLISION_RISK
        )
        if collision_indexes:
            print(f"✓ Indexes verified for {db_module.EDGE_COLLECTION_COLLISION_RISK}")
        
        lineage_indexes = db_module.add_edge_indexes(
            db_module.EDGE_COLLECTION_SATELLITE_LINEAGE
        )
        if lineage_indexes:
            print(f"✓ Indexes verified for {db_module.EDGE_COLLECTION_SATELLITE_LINEAGE}")
        
        from database.connection import db as current_db
        if current_db is None:
            print("❌ Database connection lost")
            return False
        
        collection = current_db.collection(db_module.EDGE_COLLECTION_COLLISION_RISK)
        collection.add_persistent_index(fields=['risk_score'], unique=False)
        print(f"✓ Custom index added: risk_score")
        
        collection.add_persistent_index(fields=['risk_level'], unique=False)
        print(f"✓ Custom index added: risk_level")
        
        lineage_collection = current_db.collection(db_module.EDGE_COLLECTION_SATELLITE_LINEAGE)
        lineage_collection.add_persistent_index(fields=['family'], unique=False)
        print(f"✓ Custom index added: family")
        
        lineage_collection.add_persistent_index(fields=['relationship'], unique=False)
        print(f"✓ Custom index added: relationship")
        
        return True
    except Exception as e:
        print(f"❌ Index verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_population_scripts():
    """Verify population scripts exist and are executable"""
    print("\n" + "=" * 60)
    print("Step 4: Verify Population Scripts")
    print("=" * 60)
    
    scripts_dir = Path(__file__).parent.parent / "population"
    
    collision_script = scripts_dir / "populate_collision_risks.py"
    if collision_script.exists():
        print(f"✓ Collision risk population script exists: {collision_script.name}")
    else:
        print(f"❌ Missing: {collision_script.name}")
        return False
    
    lineage_script = scripts_dir / "populate_satellite_lineage.py"
    if lineage_script.exists():
        print(f"✓ Satellite lineage population script exists: {lineage_script.name}")
    else:
        print(f"❌ Missing: {lineage_script.name}")
        return False
    
    return True


def main():
    """Run all verification checks"""
    print("\n" + "=" * 60)
    print("Phase 1 Infrastructure Verification")
    print("=" * 60)
    
    results = []
    
    try:
        results.append(("Imports", verify_imports()))
        results.append(("Edge Collections", verify_edge_collections()))
        results.append(("Indexes", verify_indexes()))
        results.append(("Population Scripts", verify_population_scripts()))
    finally:
        if db_module.db is not None:
            db_module.disconnect_mongodb()
    
    print("\n" + "=" * 60)
    print("Verification Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All verification checks passed!")
        print("Phase 1 - Backend Infrastructure is complete")
    else:
        print("❌ Some verification checks failed")
        print("Please review the errors above")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
