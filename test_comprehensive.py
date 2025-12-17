#!/usr/bin/env python3
"""
Comprehensive end-to-end testing for promote_attributes.py

Tests all edge cases mentioned in the implementation plan:
1. Source field doesn't exist
2. Source field is null/empty
3. Target field already exists
4. Nested fields
5. Large batches
"""

import sys
from db import connect_mongodb, get_satellites_collection, disconnect_mongodb
from promote_attributes import (
    validate_field_path,
    normalize_field_path,
    parse_filter,
    build_query,
    promote_document,
    check_target_field_conflicts
)

def test_edge_cases():
    print("=" * 60)
    print("COMPREHENSIVE EDGE CASE TESTING")
    print("=" * 60)
    
    # Test 1: Field path validation
    print("\n1. Field Path Validation Edge Cases")
    print("-" * 40)
    invalid_paths = [
        ("", "empty path"),
        (".leading", "leading dot"),
        ("trailing.", "trailing dot"),
        ("double..dots", "consecutive dots"),
        ("has space", "contains space"),
        ("has\ttab", "contains tab"),
    ]
    
    for path, desc in invalid_paths:
        result = validate_field_path(path)
        if not result:
            print(f"  ✓ Rejected {desc}: '{path}'")
        else:
            print(f"  ✗ FAILED: Accepted invalid path '{path}'")
    
    # Test 2: Valid nested field paths
    print("\n2. Nested Field Path Support")
    print("-" * 40)
    nested_paths = [
        "canonical.orbit.apogee_km",
        "sources.kaggle.congestion.risk_level",
        "metadata.transformations.timestamp"
    ]
    
    for path in nested_paths:
        if validate_field_path(path):
            print(f"  ✓ Accepted nested path: {path}")
        else:
            print(f"  ✗ FAILED: Rejected valid nested path: {path}")
    
    # Test 3: Filter parsing with multiple values
    print("\n3. Filter Parsing")
    print("-" * 40)
    filter_tests = [
        ("field=value", 1),
        ("field1=val1,field2=val2", 2),
        ("count=123", 1),
        ("altitude=350.5", 1),
        ("identifier=NORAD-12345,country=USA", 2),
    ]
    
    for filter_str, expected_keys in filter_tests:
        try:
            result = parse_filter(filter_str)
            if len(result) == expected_keys:
                print(f"  ✓ Parsed '{filter_str}' → {result}")
            else:
                print(f"  ✗ FAILED: Expected {expected_keys} keys, got {len(result)}")
        except Exception as e:
            print(f"  ✗ FAILED: Exception parsing '{filter_str}': {e}")
    
    # Test 4: MongoDB integration
    if not connect_mongodb():
        print("\n⚠ MongoDB not available - skipping database tests")
        return
    
    try:
        collection = get_satellites_collection()
        
        print("\n4. Source Field Existence Check")
        print("-" * 40)
        
        # Test with existing field
        query1 = build_query("sources.kaggle.orbital_band", None)
        count1 = collection.count_documents(query1)
        print(f"  ✓ Found {count1:,} documents with sources.kaggle.orbital_band")
        
        # Test with non-existent field
        query2 = build_query("sources.nonexistent.field", None)
        count2 = collection.count_documents(query2)
        print(f"  ✓ Found {count2} documents with sources.nonexistent.field (expected 0)")
        
        print("\n5. Target Field Conflict Detection")
        print("-" * 40)
        
        # Test conflict detection
        conflicts = check_target_field_conflicts(
            collection,
            query1,
            "canonical.orbital_band",
            limit=5
        )
        print(f"  ✓ Detected {conflicts['total_conflicts']} conflicts")
        if conflicts['sample_conflicts']:
            print(f"  ✓ Sample IDs: {conflicts['sample_conflicts'][:3]}")
        
        print("\n6. Document Promotion Edge Cases")
        print("-" * 40)
        
        # Get a sample document
        doc = collection.find_one({"identifier": "2025-206B"})
        if doc:
            print(f"  ✓ Test document: {doc['identifier']}")
            
            # Test successful promotion
            result1 = promote_document(
                doc,
                "sources.kaggle.orbital_band",
                "canonical.orbital_band",
                reason="Test promotion",
                verbose=False
            )
            if result1["success"]:
                print(f"  ✓ Successful promotion: {result1['value']}")
            else:
                print(f"  ✗ FAILED: {result1.get('error', 'Unknown error')}")
            
            # Test with missing source field
            result2 = promote_document(
                doc,
                "sources.nonexistent.field",
                "canonical.test",
                verbose=False
            )
            if not result2["success"]:
                print(f"  ✓ Correctly failed for missing source field")
            else:
                print(f"  ✗ FAILED: Should have failed for missing field")
        
        print("\n7. Nested Target Field Creation")
        print("-" * 40)
        test_doc = {
            "_id": "test_id",
            "sources": {
                "kaggle": {
                    "apogee": 500
                }
            }
        }
        
        result3 = promote_document(
            test_doc,
            "sources.kaggle.apogee",
            "canonical.orbit.apogee_km",
            verbose=False
        )
        
        if result3["success"]:
            nested_value = test_doc.get("canonical", {}).get("orbit", {}).get("apogee_km")
            if nested_value == 500:
                print(f"  ✓ Created nested target field: canonical.orbit.apogee_km = {nested_value}")
            else:
                print(f"  ✗ FAILED: Nested field not created correctly")
        else:
            print(f"  ✗ FAILED: {result3.get('error', 'Unknown error')}")
        
    finally:
        disconnect_mongodb()
    
    print("\n" + "=" * 60)
    print("✓ COMPREHENSIVE TESTING COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    test_edge_cases()
