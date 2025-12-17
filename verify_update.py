#!/usr/bin/env python3
"""
Verify that the document was updated correctly in MongoDB
"""

from db import connect_mongodb, disconnect_mongodb, get_satellites_collection
import json


def verify_update():
    """Verify the document was updated correctly"""
    if not connect_mongodb():
        print("ERROR: Failed to connect to MongoDB")
        return False
    
    try:
        collection = get_satellites_collection()
        
        doc = collection.find_one({"identifier": "2025-206B"})
        
        if not doc:
            print("ERROR: Document not found")
            return False
        
        print(f"Document: {doc.get('identifier')}")
        print(f"\nCanonical orbital_band: {doc.get('canonical', {}).get('orbital_band')}")
        print(f"Source orbital_band: {doc.get('sources', {}).get('kaggle', {}).get('orbital_band')}")
        
        transformations = doc.get('metadata', {}).get('transformations', [])
        print(f"\nTransformations: {len(transformations)}")
        
        if transformations:
            for i, t in enumerate(transformations, 1):
                print(f"\nTransformation {i}:")
                print(f"  Source: {t.get('source_field')}")
                print(f"  Target: {t.get('target_field')}")
                print(f"  Value: {t.get('value')}")
                print(f"  Timestamp: {t.get('timestamp')}")
                if t.get('reason'):
                    print(f"  Reason: {t.get('reason')}")
        
        canonical_value = doc.get('canonical', {}).get('orbital_band')
        source_value = doc.get('sources', {}).get('kaggle', {}).get('orbital_band')
        
        if canonical_value != source_value:
            print(f"\n✗ ERROR: Canonical value ({canonical_value}) doesn't match source ({source_value})")
            return False
        
        if not transformations:
            print("\n✗ ERROR: No transformations recorded")
            return False
        
        latest = transformations[-1]
        if latest.get('source_field') != 'sources.kaggle.orbital_band':
            print(f"\n✗ ERROR: Latest transformation source incorrect: {latest.get('source_field')}")
            return False
        
        if latest.get('target_field') != 'canonical.orbital_band':
            print(f"\n✗ ERROR: Latest transformation target incorrect: {latest.get('target_field')}")
            return False
        
        print("\n✓ VERIFICATION PASSED")
        print("  - Canonical field matches source field")
        print("  - Transformation history is recorded")
        return True
        
    finally:
        disconnect_mongodb()


if __name__ == "__main__":
    import sys
    success = verify_update()
    sys.exit(0 if success else 1)
