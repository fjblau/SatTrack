#!/usr/bin/env python3
"""
Test script for field promotion logic
"""

from db import (
    connect_mongodb,
    disconnect_mongodb,
    get_satellites_collection,
    get_nested_field,
    set_nested_field,
    record_transformation
)
from promote_attributes import promote_document
import json


def test_promote_single_document():
    """Test promoting a field in a single document"""
    print("=" * 60)
    print("TEST: Promote single document")
    print("=" * 60)
    
    if not connect_mongodb():
        print("ERROR: Failed to connect to MongoDB")
        return False
    
    try:
        collection = get_satellites_collection()
        
        doc = collection.find_one({
            "sources.kaggle.orbital_band": {"$exists": True, "$ne": None}
        })
        
        if not doc:
            print("ERROR: No document found with kaggle.orbital_band")
            return False
        
        doc_id = doc["_id"]
        identifier = doc.get("identifier", "unknown")
        
        print(f"\nDocument: {identifier} ({doc_id})")
        
        original_value = get_nested_field(doc, "sources.kaggle.orbital_band")
        print(f"Source value (sources.kaggle.orbital_band): {original_value}")
        
        original_canonical = get_nested_field(doc, "canonical.orbital_band")
        print(f"Current canonical value: {original_canonical}")
        
        original_transformations = get_nested_field(doc, "metadata.transformations") or []
        print(f"Existing transformations: {len(original_transformations)}")
        
        result = promote_document(
            doc,
            "sources.kaggle.orbital_band",
            "canonical.orbital_band",
            reason="Test promotion",
            verbose=True
        )
        
        if not result["success"]:
            print(f"ERROR: Promotion failed - {result.get('error')}")
            return False
        
        new_canonical = get_nested_field(doc, "canonical.orbital_band")
        print(f"\nNew canonical value: {new_canonical}")
        
        new_transformations = get_nested_field(doc, "metadata.transformations") or []
        print(f"New transformations count: {len(new_transformations)}")
        
        if new_canonical != original_value:
            print(f"ERROR: Canonical value doesn't match source ({new_canonical} != {original_value})")
            return False
        
        if len(new_transformations) != len(original_transformations) + 1:
            print(f"ERROR: Transformation not recorded (expected {len(original_transformations) + 1}, got {len(new_transformations)})")
            return False
        
        latest_transformation = new_transformations[-1]
        print(f"\nLatest transformation:")
        print(f"  Source: {latest_transformation.get('source_field')}")
        print(f"  Target: {latest_transformation.get('target_field')}")
        print(f"  Value: {latest_transformation.get('value')}")
        print(f"  Reason: {latest_transformation.get('reason')}")
        print(f"  Timestamp: {latest_transformation.get('timestamp')}")
        
        if latest_transformation.get("source_field") != "sources.kaggle.orbital_band":
            print("ERROR: Transformation source_field incorrect")
            return False
        
        if latest_transformation.get("target_field") != "canonical.orbital_band":
            print("ERROR: Transformation target_field incorrect")
            return False
        
        if latest_transformation.get("value") != original_value:
            print("ERROR: Transformation value incorrect")
            return False
        
        if latest_transformation.get("reason") != "Test promotion":
            print("ERROR: Transformation reason incorrect")
            return False
        
        print("\n✓ TEST PASSED: Document promotion works correctly")
        print("  - Canonical field updated")
        print("  - Transformation history recorded")
        print("  - All fields match expected values")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        disconnect_mongodb()


if __name__ == "__main__":
    import sys
    success = test_promote_single_document()
    sys.exit(0 if success else 1)
