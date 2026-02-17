#!/usr/bin/env python3
"""
Comprehensive verification of local database after multi-source import.
Checks data integrity, coverage, and quality from GCAT, Kaggle, SatNOGS, and UNOOSA sources.
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import database.connection as db_conn
from database import connect_arangodb, COLLECTION_NAME


def print_header(title):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def check_total_count():
    """Check total record count"""
    print_header("Total Record Count")
    count = db_conn.satellites_collection.count()
    print(f"Total satellites in database: {count:,}")
    return count


def check_multi_source_coverage():
    """Check coverage by data source"""
    print_header("Multi-Source Coverage")
    
    sources = ['gcat', 'kaggle', 'satnogs', 'unoosa']
    results = {}
    
    for source in sources:
        query = f'''
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.sources.{source} != null
            COLLECT WITH COUNT INTO length
            RETURN length
        '''
        result = list(db_conn.db.aql.execute(query))
        count = result[0] if result else 0
        results[source] = count
        print(f"Records with {source.upper():8s} data: {count:,}")
    
    return results


def check_recent_launches():
    """Check for recent launches after 2025-09-13"""
    print_header("Recent Launches (after 2025-09-13)")
    
    query = f'''
    FOR doc IN {COLLECTION_NAME}
        FILTER doc.canonical.date_of_launch >= "2025-09-14"
        SORT doc.canonical.date_of_launch DESC
        LIMIT 25
        RETURN {{
            name: doc.canonical.name,
            launch_date: doc.canonical.date_of_launch,
            norad_id: doc.canonical.norad_cat_id,
            country: doc.canonical.country_of_origin,
            sources: ATTRIBUTES(doc.sources)
        }}
    '''
    
    recent = list(db_conn.db.aql.execute(query))
    
    if recent:
        print(f"\nFound {len(recent)} recent launches (showing first 25):")
        for sat in recent:
            sources_str = ', '.join(sat['sources'])
            norad_str = f"NORAD: {sat['norad_id']}" if sat['norad_id'] else "No NORAD"
            print(f"  {sat['launch_date']}: {sat['name'][:50]:50s} ({norad_str}) - Sources: [{sources_str}]")
    else:
        print("⚠️  WARNING: No recent launches found after 2025-09-13!")
    
    return recent


def find_most_recent_launch():
    """Find the most recent launch date in database"""
    print_header("Most Recent Launch Date")
    
    query = f'''
    FOR doc IN {COLLECTION_NAME}
        FILTER doc.canonical.date_of_launch != null
        SORT doc.canonical.date_of_launch DESC
        LIMIT 1
        RETURN {{
            name: doc.canonical.name,
            launch_date: doc.canonical.date_of_launch,
            norad_id: doc.canonical.norad_cat_id,
            sources: ATTRIBUTES(doc.sources)
        }}
    '''
    
    result = list(db_conn.db.aql.execute(query))
    if result:
        sat = result[0]
        sources_str = ', '.join(sat['sources'])
        print(f"Most recent launch: {sat['launch_date']}")
        print(f"  Satellite: {sat['name']}")
        print(f"  NORAD ID: {sat['norad_id']}")
        print(f"  Sources: [{sources_str}]")
        return sat
    else:
        print("⚠️  No launch dates found in database!")
        return None


def check_duplicates():
    """Check for duplicate NORAD IDs"""
    print_header("Duplicate Detection")
    
    query = f'''
    FOR doc IN {COLLECTION_NAME}
        FILTER doc.canonical.norad_cat_id != null
        COLLECT norad = doc.canonical.norad_cat_id WITH COUNT INTO count
        FILTER count > 1
        SORT count DESC
        LIMIT 10
        RETURN {{norad_id: norad, count: count}}
    '''
    
    duplicates = list(db_conn.db.aql.execute(query))
    
    if duplicates:
        print(f"⚠️  WARNING: Found {len(duplicates)} duplicate NORAD IDs:")
        for dup in duplicates:
            print(f"  NORAD {dup['norad_id']}: {dup['count']} records")
    else:
        print("✓ No duplicate NORAD IDs found")
    
    return duplicates


def check_kaggle_enrichment():
    """Check Kaggle orbital analytics enrichment"""
    print_header("Kaggle Orbital Analytics")
    
    # Check for orbital band distribution
    query = f'''
    FOR doc IN {COLLECTION_NAME}
        FILTER doc.sources.kaggle.orbital_band != null
        COLLECT band = doc.sources.kaggle.orbital_band WITH COUNT INTO count
        SORT count DESC
        RETURN {{band: band, count: count}}
    '''
    
    bands = list(db_conn.db.aql.execute(query))
    
    if bands:
        print("\nOrbital Band Distribution:")
        for band in bands:
            print(f"  {band['band']:20s}: {band['count']:,} satellites")
    else:
        print("⚠️  No Kaggle orbital band data found")
    
    # Check for congestion risk
    query = f'''
    FOR doc IN {COLLECTION_NAME}
        FILTER doc.sources.kaggle.congestion_risk != null
        COLLECT risk = doc.sources.kaggle.congestion_risk WITH COUNT INTO count
        SORT count DESC
        RETURN {{risk: risk, count: count}}
    '''
    
    risks = list(db_conn.db.aql.execute(query))
    
    if risks:
        print("\nCongestion Risk Distribution:")
        for risk in risks:
            print(f"  {risk['risk']:20s}: {risk['count']:,} satellites")
    
    return bands, risks


def check_satnogs_status():
    """Check SatNOGS operational status"""
    print_header("SatNOGS Operational Status")
    
    query = f'''
    FOR doc IN {COLLECTION_NAME}
        FILTER doc.sources.satnogs.status != null
        COLLECT status = doc.sources.satnogs.status WITH COUNT INTO count
        SORT count DESC
        RETURN {{status: status, count: count}}
    '''
    
    statuses = list(db_conn.db.aql.execute(query))
    
    if statuses:
        print("\nOperational Status Distribution:")
        for status in statuses:
            print(f"  {status['status']:20s}: {status['count']:,} satellites")
    else:
        print("⚠️  No SatNOGS status data found")
    
    return statuses


def check_specific_launches():
    """Check for specific launches mentioned in the task"""
    print_header("Specific Launch Verification")
    
    # Check for 2025-12-07 launch (mentioned in task)
    query = f'''
    FOR doc IN {COLLECTION_NAME}
        FILTER doc.canonical.date_of_launch == "2025-12-07"
        RETURN {{
            name: doc.canonical.name,
            norad_id: doc.canonical.norad_cat_id,
            sources: ATTRIBUTES(doc.sources)
        }}
    '''
    
    launches_1207 = list(db_conn.db.aql.execute(query))
    
    if launches_1207:
        print(f"✓ Found {len(launches_1207)} satellite(s) launched on 2025-12-07:")
        for sat in launches_1207:
            sources_str = ', '.join(sat['sources'])
            print(f"  {sat['name']} (NORAD: {sat['norad_id']}) - Sources: [{sources_str}]")
    else:
        print("⚠️  WARNING: No satellites found with launch date 2025-12-07")
        print("   (Task mentioned this should be the most recent)")
    
    return launches_1207


def generate_summary():
    """Generate summary statistics"""
    print_header("VERIFICATION SUMMARY")
    
    # Overall health check
    issues = []
    warnings = []
    
    # Check total count
    total = db_conn.satellites_collection.count()
    if total < 5000:
        warnings.append(f"Low record count: {total:,} (expected 15,000+)")
    else:
        print(f"✓ Database size: {total:,} satellites")
    
    # Check GCAT data
    result = list(db_conn.db.aql.execute(f'FOR doc IN {COLLECTION_NAME} FILTER doc.sources.gcat != null COLLECT WITH COUNT INTO length RETURN length'))
    gcat_count = result[0] if result else 0
    if gcat_count < 50:
        warnings.append(f"Low GCAT coverage: {gcat_count} (expected 99+)")
    else:
        print(f"✓ GCAT coverage: {gcat_count:,} satellites")
    
    # Check Kaggle data
    result = list(db_conn.db.aql.execute(f'FOR doc IN {COLLECTION_NAME} FILTER doc.sources.kaggle != null COLLECT WITH COUNT INTO length RETURN length'))
    kaggle_count = result[0] if result else 0
    if kaggle_count < 10000:
        warnings.append(f"Low Kaggle coverage: {kaggle_count:,} (expected 14,623)")
    else:
        print(f"✓ Kaggle coverage: {kaggle_count:,} satellites")
    
    # Check SatNOGS data
    result = list(db_conn.db.aql.execute(f'FOR doc IN {COLLECTION_NAME} FILTER doc.sources.satnogs != null COLLECT WITH COUNT INTO length RETURN length'))
    satnogs_count = result[0] if result else 0
    print(f"✓ SatNOGS coverage: {satnogs_count:,} satellites")
    
    # Check UNOOSA data
    result = list(db_conn.db.aql.execute(f'FOR doc IN {COLLECTION_NAME} FILTER doc.sources.unoosa != null COLLECT WITH COUNT INTO length RETURN length'))
    unoosa_count = result[0] if result else 0
    print(f"✓ UNOOSA coverage: {unoosa_count:,} satellites")
    
    # Check most recent launch
    most_recent_query = f'''
    FOR doc IN {COLLECTION_NAME}
        FILTER doc.canonical.date_of_launch != null
        SORT doc.canonical.date_of_launch DESC
        LIMIT 1
        RETURN doc.canonical.date_of_launch
    '''
    most_recent = list(db_conn.db.aql.execute(most_recent_query))
    if most_recent:
        most_recent_date = most_recent[0]
        print(f"✓ Most recent launch: {most_recent_date}")
        
        if most_recent_date < "2025-12-07":
            warnings.append(f"Most recent launch {most_recent_date} is before 2025-12-07")
    
    # Check for duplicates
    dup_query = f'''
    FOR doc IN {COLLECTION_NAME}
        FILTER doc.canonical.norad_cat_id != null
        COLLECT norad = doc.canonical.norad_cat_id WITH COUNT INTO count
        FILTER count > 1
        COLLECT WITH COUNT INTO dup_count
        RETURN dup_count
    '''
    result = list(db_conn.db.aql.execute(dup_query))
    dup_count = result[0] if result else 0
    if dup_count > 0:
        warnings.append(f"Found {dup_count} duplicate NORAD IDs")
    else:
        print(f"✓ No duplicate NORAD IDs")
    
    # Print warnings and issues
    if warnings:
        print("\n⚠️  WARNINGS:")
        for warning in warnings:
            print(f"  - {warning}")
    
    if issues:
        print("\n❌ ISSUES:")
        for issue in issues:
            print(f"  - {issue}")
    
    if not warnings and not issues:
        print("\n✅ All verification checks passed!")
    
    return {
        'total': total,
        'gcat': gcat_count,
        'kaggle': kaggle_count,
        'satnogs': satnogs_count,
        'unoosa': unoosa_count,
        'most_recent': most_recent[0] if most_recent else None,
        'warnings': warnings,
        'issues': issues
    }


def main():
    """Run all verification checks"""
    print("=" * 80)
    print(" LOCAL DATABASE VERIFICATION")
    print(" Multi-Source Import: GCAT + Kaggle + SatNOGS + UNOOSA")
    print("=" * 80)
    print(f"\nTimestamp: {datetime.now().isoformat()}")
    
    # Connect to database
    if not connect_arangodb():
        print("❌ Failed to connect to ArangoDB")
        return False
    
    try:
        # Run all checks
        check_total_count()
        check_multi_source_coverage()
        find_most_recent_launch()
        check_recent_launches()
        check_specific_launches()
        check_duplicates()
        check_kaggle_enrichment()
        check_satnogs_status()
        summary = generate_summary()
        
        # Determine overall success
        success = len(summary['issues']) == 0
        
        if success:
            print("\n" + "=" * 80)
            print(" ✅ VERIFICATION COMPLETE - ALL CHECKS PASSED")
            print("=" * 80)
        else:
            print("\n" + "=" * 80)
            print(" ⚠️  VERIFICATION COMPLETE - ISSUES FOUND")
            print("=" * 80)
        
        return success
        
    except Exception as e:
        print(f"\n❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
