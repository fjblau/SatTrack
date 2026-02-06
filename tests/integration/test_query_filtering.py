#!/usr/bin/env python3
"""
Test script for document query and filtering functionality.
"""

import sys
from promote_attributes import (
    parse_filter,
    build_query,
    normalize_field_path
)


def test_parse_filter():
    """Test filter parsing with various inputs"""
    print("Testing parse_filter()...")
    
    # Test simple filter
    result = parse_filter("identifier=NORAD-25544")
    assert result == {"identifier": "NORAD-25544"}, f"Expected {{'identifier': 'NORAD-25544'}}, got {result}"
    print("✓ Simple string filter")
    
    # Test numeric filter
    result = parse_filter("count=123")
    assert result == {"count": 123}, f"Expected {{'count': 123}}, got {result}"
    print("✓ Numeric filter")
    
    # Test float filter
    result = parse_filter("altitude=350.5")
    assert result == {"altitude": 350.5}, f"Expected {{'altitude': 350.5}}, got {result}"
    print("✓ Float filter")
    
    # Test multiple filters
    result = parse_filter("canonical.country_of_origin=USA,canonical.launch_year=2020")
    assert result == {"canonical.country_of_origin": "USA", "canonical.launch_year": 2020}, \
        f"Expected multiple filters, got {result}"
    print("✓ Multiple filters")
    
    # Test empty filter
    result = parse_filter("")
    assert result == {}, f"Expected empty dict, got {result}"
    print("✓ Empty filter")
    
    # Test filter with spaces
    result = parse_filter("  field  =  value  ")
    assert result == {"field": "value"}, f"Expected {{'field': 'value'}}, got {result}"
    print("✓ Filter with spaces")
    
    # Test invalid filter (should raise ValueError)
    try:
        parse_filter("invalid_no_equals")
        assert False, "Should have raised ValueError"
    except ValueError:
        print("✓ Invalid filter raises ValueError")
    
    print("All parse_filter tests passed!\n")


def test_build_query():
    """Test query building"""
    print("Testing build_query()...")
    
    # Test without filter
    result = build_query("sources.kaggle.orbital_band")
    expected = {
        "sources.kaggle.orbital_band": {"$exists": True, "$ne": None}
    }
    assert result == expected, f"Expected {expected}, got {result}"
    print("✓ Query without filter")
    
    # Test with filter
    result = build_query("sources.kaggle.orbital_band", "identifier=NORAD-25544")
    expected = {
        "identifier": "NORAD-25544",
        "sources.kaggle.orbital_band": {"$exists": True, "$ne": None}
    }
    assert result == expected, f"Expected {expected}, got {result}"
    print("✓ Query with filter")
    
    # Test with multiple filters
    result = build_query("sources.kaggle.orbital_band", "canonical.country=USA,canonical.year=2020")
    expected = {
        "canonical.country": "USA",
        "canonical.year": 2020,
        "sources.kaggle.orbital_band": {"$exists": True, "$ne": None}
    }
    assert result == expected, f"Expected {expected}, got {result}"
    print("✓ Query with multiple filters")
    
    print("All build_query tests passed!\n")


def test_normalize_field_path():
    """Test field path normalization"""
    print("Testing normalize_field_path()...")
    
    # Test source field
    result = normalize_field_path("kaggle.orbital_band")
    assert result == "sources.kaggle.orbital_band", f"Expected 'sources.kaggle.orbital_band', got {result}"
    print("✓ Source field normalization")
    
    # Test already normalized source field
    result = normalize_field_path("sources.kaggle.orbital_band")
    assert result == "sources.kaggle.orbital_band", f"Expected 'sources.kaggle.orbital_band', got {result}"
    print("✓ Already normalized source field")
    
    # Test canonical field
    result = normalize_field_path("canonical.orbital_band")
    assert result == "canonical.orbital_band", f"Expected 'canonical.orbital_band', got {result}"
    print("✓ Canonical field normalization")
    
    # Test other known sources
    result = normalize_field_path("unoosa.name")
    assert result == "sources.unoosa.name", f"Expected 'sources.unoosa.name', got {result}"
    print("✓ UNOOSA field normalization")
    
    result = normalize_field_path("celestrak.tle")
    assert result == "sources.celestrak.tle", f"Expected 'sources.celestrak.tle', got {result}"
    print("✓ CelesTrak field normalization")
    
    result = normalize_field_path("spacetrack.data")
    assert result == "sources.spacetrack.data", f"Expected 'sources.spacetrack.data', got {result}"
    print("✓ Space-Track field normalization")
    
    # Test arbitrary field (no normalization)
    result = normalize_field_path("identifier")
    assert result == "identifier", f"Expected 'identifier', got {result}"
    print("✓ Arbitrary field (no normalization)")
    
    print("All normalize_field_path tests passed!\n")


if __name__ == "__main__":
    try:
        test_parse_filter()
        test_build_query()
        test_normalize_field_path()
        print("=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
