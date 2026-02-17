#!/usr/bin/env python3
"""
Verify Railway production database after deployment.
Run this after importing data to Railway to ensure everything is correct.
"""
import os
import sys
from arango import ArangoClient

RAILWAY_HOST = os.getenv("RAILWAY_HOST", "https://arangodb-production-d6fb.up.railway.app:443")
RAILWAY_PASSWORD = os.getenv("RAILWAY_PASSWORD")
DB_NAME = "kessler"

def verify_railway():
    """Verify Railway production database integrity."""
    
    if not RAILWAY_PASSWORD:
        print("❌ Error: RAILWAY_PASSWORD environment variable not set")
        return False
    
    try:
        client = ArangoClient(hosts=RAILWAY_HOST)
        db = client.db(DB_NAME, username='root', password=RAILWAY_PASSWORD)
        
        print("="*70)
        print("RAILWAY PRODUCTION DATABASE VERIFICATION")
        print("="*70)
        print()
        
        all_checks_passed = True
        
        # Check 1: Total satellites
        total = db.collection('satellites').count()
        print(f"✓ Total satellites: {total:,}")
        
        # Check 2: Missing canonical.name
        query = '''
        FOR sat IN satellites
            FILTER sat.canonical.name == null OR sat.canonical.name == ""
            COLLECT WITH COUNT INTO count
            RETURN count
        '''
        result = list(db.aql.execute(query))
        missing_name = result[0] if result else 0
        
        if missing_name > 0:
            print(f"❌ FAIL: {missing_name} satellites with missing canonical.name")
            all_checks_passed = False
        else:
            print("✓ All satellites have canonical.name")
        
        # Check 3: PRETTY satellite integrity
        query = '''
        FOR sat IN satellites
            FILTER sat.canonical.norad_cat_id == 58023
            RETURN {
                _key: sat._key,
                name: sat.canonical.name,
                launch_date: sat.canonical.launch_date,
                canonical_source_priority: sat.canonical.source_priority
            }
        '''
        result = list(db.aql.execute(query))
        
        if result:
            pretty = result[0]
            errors = []
            
            if pretty['_key'] != '2023-155H':
                errors.append(f"_key changed to {pretty['_key']}")
            if pretty['name'] != 'PRETTY':
                errors.append(f"name changed to {pretty['name']}")
            if pretty['launch_date'] != '2023-10-09':
                errors.append(f"launch_date changed to {pretty['launch_date']}")
            if 'gcat' in pretty.get('canonical_source_priority', []):
                errors.append('gcat in canonical.source_priority')
            if 'satnogs' in pretty.get('canonical_source_priority', []):
                errors.append('satnogs in canonical.source_priority')
            
            if errors:
                print("❌ PRETTY SATELLITE CORRUPTED:")
                for err in errors:
                    print(f"   - {err}")
                all_checks_passed = False
            else:
                print("✓ PRETTY satellite verified correct")
        else:
            print("❌ FAIL: PRETTY satellite not found")
            all_checks_passed = False
        
        # Check 4: Most recent launch
        query = '''
        FOR sat IN satellites
            FILTER sat.canonical.launch_date != null
            SORT sat.canonical.launch_date DESC
            LIMIT 5
            RETURN {
                launch: sat.canonical.launch_date,
                name: sat.canonical.name
            }
        '''
        result = list(db.aql.execute(query))
        
        if result:
            print(f"\n✓ Most recent launches:")
            for sat in result[:5]:
                print(f"   {sat['launch']}: {sat['name']}")
            
            most_recent = result[0]['launch']
            if most_recent >= '2026-01-01':
                print(f"\n✓ Most recent launch is current: {most_recent}")
            else:
                print(f"\n⚠️  Most recent launch is old: {most_recent}")
        
        # Check 5: Broken edges
        query = '''
        FOR edge IN orbital_proximity
            LET from_exists = DOCUMENT(edge._from)
            LET to_exists = DOCUMENT(edge._to)
            FILTER from_exists == null OR to_exists == null
            LIMIT 1
            RETURN 1
        '''
        result = list(db.aql.execute(query))
        
        if result:
            print("\n❌ FAIL: Broken edges found in orbital_proximity")
            print("   Run: python3 scripts/maintenance/clean_broken_edges.py")
            all_checks_passed = False
        else:
            print("\n✓ No broken edges in orbital_proximity")
        
        # Check 6: Data source coverage
        print("\n✓ Data source coverage:")
        for source in ['gcat', 'kaggle', 'satnogs', 'unoosa', 'spacetrack']:
            query = f'''
            FOR sat IN satellites
                FILTER sat.sources.{source} != null
                COLLECT WITH COUNT INTO count
                RETURN count
            '''
            result = list(db.aql.execute(query))
            count = result[0] if result else 0
            print(f"   {source}: {count:,} satellites")
        
        print()
        print("="*70)
        
        if all_checks_passed:
            print("✅ ALL CHECKS PASSED - PRODUCTION VERIFIED")
            print("="*70)
            return True
        else:
            print("❌ VERIFICATION FAILED - DO NOT USE PRODUCTION")
            print("="*70)
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = verify_railway()
    sys.exit(0 if success else 1)
