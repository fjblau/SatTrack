#!/usr/bin/env python3
"""
Standalone test for helper functions (without MongoDB imports)
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any


def get_nested_field(obj: Dict[str, Any], path: str) -> Any:
    keys = path.split(".")
    current = obj
    
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    
    return current


def set_nested_field(obj: Dict[str, Any], path: str, value: Any) -> bool:
    keys = path.split(".")
    current = obj
    
    for i, key in enumerate(keys[:-1]):
        if key not in current:
            current[key] = {}
        elif not isinstance(current[key], dict):
            return False
        current = current[key]
    
    current[keys[-1]] = value
    return True


def record_transformation(
    doc: Dict[str, Any],
    source_field: str,
    target_field: str,
    value: Any,
    reason: Optional[str] = None
) -> None:
    if "metadata" not in doc:
        doc["metadata"] = {}
    
    if "transformations" not in doc["metadata"]:
        doc["metadata"]["transformations"] = []
    
    transformation = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_field": source_field,
        "target_field": target_field,
        "value": value,
        "promoted_by": "manual_script"
    }
    
    if reason:
        transformation["reason"] = reason
    
    doc["metadata"]["transformations"].append(transformation)


def test_get_nested_field():
    print("Testing get_nested_field...")
    
    test_doc = {
        "sources": {
            "kaggle": {
                "orbital_band": "LEO",
                "name": "ISS"
            }
        },
        "canonical": {
            "orbit": {
                "apogee_km": 420
            }
        }
    }
    
    assert get_nested_field(test_doc, "sources.kaggle.orbital_band") == "LEO"
    assert get_nested_field(test_doc, "canonical.orbit.apogee_km") == 420
    assert get_nested_field(test_doc, "sources.nonexistent.field") is None
    assert get_nested_field(test_doc, "sources.kaggle.missing") is None
    assert get_nested_field({}, "a.b.c") is None
    assert get_nested_field({"a": "string"}, "a.b") is None
    
    print("✓ get_nested_field tests passed")


def test_set_nested_field():
    print("Testing set_nested_field...")
    
    doc1 = {}
    assert set_nested_field(doc1, "a.b.c", 1) == True
    assert doc1 == {"a": {"b": {"c": 1}}}
    
    doc2 = {"canonical": {}}
    assert set_nested_field(doc2, "canonical.orbital_band", "LEO") == True
    assert doc2["canonical"]["orbital_band"] == "LEO"
    
    doc3 = {"canonical": {"orbit": {}}}
    assert set_nested_field(doc3, "canonical.orbit.apogee_km", 420) == True
    assert doc3["canonical"]["orbit"]["apogee_km"] == 420
    
    doc4 = {"a": "string"}
    assert set_nested_field(doc4, "a.b.c", 1) == False
    
    doc5 = {}
    set_nested_field(doc5, "x", 10)
    assert doc5 == {"x": 10}
    
    print("✓ set_nested_field tests passed")


def test_record_transformation():
    print("Testing record_transformation...")
    
    doc1 = {}
    record_transformation(doc1, "sources.kaggle.orbital_band", "canonical.orbital_band", "LEO")
    
    assert "metadata" in doc1
    assert "transformations" in doc1["metadata"]
    assert len(doc1["metadata"]["transformations"]) == 1
    
    trans = doc1["metadata"]["transformations"][0]
    assert trans["source_field"] == "sources.kaggle.orbital_band"
    assert trans["target_field"] == "canonical.orbital_band"
    assert trans["value"] == "LEO"
    assert trans["promoted_by"] == "manual_script"
    assert "timestamp" in trans
    
    doc2 = {"metadata": {}}
    record_transformation(doc2, "a.b", "c.d", 123, reason="Testing")
    assert len(doc2["metadata"]["transformations"]) == 1
    assert doc2["metadata"]["transformations"][0]["reason"] == "Testing"
    
    record_transformation(doc2, "x.y", "z.w", 456)
    assert len(doc2["metadata"]["transformations"]) == 2
    
    print("✓ record_transformation tests passed")


def test_edge_cases():
    print("Testing edge cases...")
    
    assert get_nested_field({"a": None}, "a.b") is None
    
    doc = {"a": {"b": ""}}
    assert get_nested_field(doc, "a.b") == ""
    
    doc = {"a": {"b": 0}}
    assert get_nested_field(doc, "a.b") == 0
    
    doc = {"a": {"b": False}}
    assert get_nested_field(doc, "a.b") == False
    
    doc = {}
    set_nested_field(doc, "a.b", None)
    assert get_nested_field(doc, "a.b") is None
    
    print("✓ Edge case tests passed")


if __name__ == "__main__":
    try:
        test_get_nested_field()
        test_set_nested_field()
        test_record_transformation()
        test_edge_cases()
        print("\n✅ All tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise
