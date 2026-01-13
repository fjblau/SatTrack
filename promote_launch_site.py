#!/usr/bin/env python3
"""
Promote launch_site from Space-Track source to canonical fields.
This script adds launch site data to canonical.launch_site.
"""
import sys
from datetime import datetime, timezone
import db as db_module

def promote_launch_site(dry_run=False):
    """Promote Space-Track launch_site to canonical.launch_site"""
    
    if not db_module.connect_mongodb():
        print("Failed to connect to ArangoDB")
        return False
    
    # Access db after connection is established
    db = db_module.db
    COLLECTION_NAME = db_module.COLLECTION_NAME
    
    try:
        # Count satellites with launch_site in spacetrack source
        count_query = """
        FOR doc IN @@collection
            FILTER doc.sources.spacetrack.launch_site != null
            COLLECT WITH COUNT INTO count
            RETURN count
        """
        
        cursor = db.aql.execute(
            count_query,
            bind_vars={'@collection': COLLECTION_NAME}
        )
        total_count = list(cursor)[0]
        
        print(f"\n=== Launch Site Promotion ===")
        print(f"Found {total_count:,} satellites with Space-Track launch_site data")
        
        if total_count == 0:
            print("No satellites to process.")
            return True
        
        # Sample a few to show what will be promoted
        sample_query = """
        FOR doc IN @@collection
            FILTER doc.sources.spacetrack.launch_site != null
            LIMIT 5
            RETURN {
                identifier: doc.identifier,
                launch_site: doc.sources.spacetrack.launch_site,
                current_canonical: doc.canonical.launch_site
            }
        """
        
        cursor = db.aql.execute(
            sample_query,
            bind_vars={'@collection': COLLECTION_NAME}
        )
        samples = list(cursor)
        
        print("\nSample documents:")
        for s in samples:
            print(f"  {s['identifier']}: '{s['launch_site']}' (current: {s.get('current_canonical', 'None')})")
        
        if dry_run:
            print(f"\n[DRY-RUN] Would promote launch_site for {total_count:,} satellites")
            return True
        
        # Confirm
        response = input(f"\nProceed with promoting launch_site for {total_count:,} satellites? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("Operation cancelled")
            return False
        
        # Perform the promotion using AQL UPDATE
        update_query = """
        FOR doc IN @@collection
            FILTER doc.sources.spacetrack.launch_site != null
            
            LET transformation = {
                timestamp: @timestamp,
                source_field: "sources.spacetrack.launch_site",
                target_field: "canonical.launch_site",
                value: doc.sources.spacetrack.launch_site,
                promoted_by: "promote_launch_site_script"
            }
            
            UPDATE doc WITH {
                canonical: MERGE(doc.canonical, {
                    launch_site: doc.sources.spacetrack.launch_site
                }),
                metadata: MERGE(doc.metadata, {
                    transformations: APPEND(
                        doc.metadata.transformations || [],
                        transformation
                    ),
                    last_updated_at: @timestamp
                })
            } IN @@collection
            
            COLLECT WITH COUNT INTO updated
            RETURN updated
        """
        
        timestamp = datetime.now(timezone.utc).isoformat()
        
        print(f"\nUpdating {total_count:,} documents...")
        cursor = db.aql.execute(
            update_query,
            bind_vars={
                '@collection': COLLECTION_NAME,
                'timestamp': timestamp
            }
        )
        
        updated = list(cursor)[0]
        
        print(f"✓ Successfully promoted launch_site for {updated:,} satellites")
        
        # Verify
        verify_query = """
        FOR doc IN @@collection
            FILTER doc.canonical.launch_site != null
            COLLECT WITH COUNT INTO count
            RETURN count
        """
        
        cursor = db.aql.execute(
            verify_query,
            bind_vars={'@collection': COLLECTION_NAME}
        )
        verified = list(cursor)[0]
        
        print(f"✓ Verification: {verified:,} satellites now have canonical.launch_site")
        
        return True
        
    except Exception as e:
        print(f"Error during promotion: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db_module.disconnect_mongodb()

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    success = promote_launch_site(dry_run=dry_run)
    sys.exit(0 if success else 1)
