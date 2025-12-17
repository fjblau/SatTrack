#!/usr/bin/env python3
"""
Test script for safety features in promote_attributes.py
"""

import sys
from promote_attributes import (
    validate_field_path,
    check_target_field_conflicts,
    normalize_field_path
)


def test_validate_field_path():
    """Test field path validation"""
    print("Testing field path validation...")
    
    # Valid paths
    valid_paths = [
        "kaggle.orbital_band",
        "canonical.country_of_origin",
        "sources.kaggle.orbital_band",
        "a.b.c.d.e"
    ]
    
    for path in valid_paths:
        assert validate_field_path(path), f"Expected {path} to be valid"
        print(f"  ✓ Valid: {path}")
    
    # Invalid paths (should print error messages but we'll capture them)
    invalid_paths = [
        "",  # Empty
        "field with spaces",  # Spaces
        "field$name",  # Dollar sign
        "field..name",  # Consecutive dots
        ".field.name",  # Leading dot
        "field.name.",  # Trailing dot
        "field\tname",  # Tab
    ]
    
    for path in invalid_paths:
        result = validate_field_path(path)
        if not result:
            print(f"  ✓ Invalid (as expected): '{path}'")
        else:
            print(f"  ✗ ERROR: {path} should be invalid but passed")
            sys.exit(1)
    
    print("\n✓ All field path validation tests passed\n")


def test_normalize_field_path():
    """Test field path normalization"""
    print("Testing field path normalization...")
    
    test_cases = [
        ("kaggle.orbital_band", "sources.kaggle.orbital_band"),
        ("sources.kaggle.orbital_band", "sources.kaggle.orbital_band"),
        ("canonical.orbital_band", "canonical.orbital_band"),
        ("unoosa.country", "sources.unoosa.country"),
        ("celestrak.tle_line1", "sources.celestrak.tle_line1"),
        ("spacetrack.launch_date", "sources.spacetrack.launch_date"),
        ("custom.field", "custom.field"),  # Unknown prefix remains unchanged
    ]
    
    for input_path, expected_output in test_cases:
        result = normalize_field_path(input_path)
        if result == expected_output:
            print(f"  ✓ {input_path} → {result}")
        else:
            print(f"  ✗ ERROR: Expected {expected_output}, got {result}")
            sys.exit(1)
    
    print("\n✓ All normalization tests passed\n")


def test_check_target_field_conflicts():
    """Test target field conflict detection"""
    print("Testing target field conflict detection...")
    
    # This requires a MongoDB connection, so we'll do a quick check
    from db import connect_mongodb, disconnect_mongodb, get_satellites_collection
    
    if not connect_mongodb():
        print("  ⚠ Skipping conflict detection test (no MongoDB connection)")
        return
    
    try:
        collection = get_satellites_collection()
        
        # Test with a field that likely exists
        query = {"sources.kaggle": {"$exists": True}}
        conflicts = check_target_field_conflicts(
            collection,
            query,
            "canonical.country_of_origin",
            limit=5
        )
        
        print(f"  Found {conflicts['total_conflicts']} documents with existing canonical.country_of_origin")
        if conflicts['sample_conflicts']:
            print(f"  Sample IDs: {conflicts['sample_conflicts'][:3]}")
        
        # Test with a field that doesn't exist
        conflicts2 = check_target_field_conflicts(
            collection,
            query,
            "canonical.nonexistent_field_xyz",
            limit=5
        )
        
        assert conflicts2['total_conflicts'] == 0, "Expected 0 conflicts for non-existent field"
        print(f"  ✓ No conflicts for non-existent field")
        
        print("\n✓ Conflict detection tests passed\n")
        
    finally:
        disconnect_mongodb()


def main():
    """Run all safety feature tests"""
    print("=" * 60)
    print("Safety Features Test Suite")
    print("=" * 60)
    print()
    
    test_validate_field_path()
    test_normalize_field_path()
    test_check_target_field_conflicts()
    
    print("=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
