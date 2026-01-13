#!/usr/bin/env python3
"""
Verify constellation membership network with graph traversal queries.
"""
import sys
import db as db_module

def verify_constellation_network():
    """Verify constellation membership network"""
    
    print("=" * 60)
    print("Constellation Membership Network Verification")
    print("=" * 60)
    
    if not db_module.connect_mongodb():
        print("❌ Failed to connect to ArangoDB")
        return False
    
    db = db_module.db
    all_passed = True
    
    print("\n" + "=" * 60)
    print("Test 1: Verify Edge Count")
    print("=" * 60)
    
    edges_count = db.collection(db_module.EDGE_COLLECTION_CONSTELLATION).count()
    
    print(f"Constellation membership edges: {edges_count:,}")
    
    if edges_count == 0:
        print("❌ No constellation edges found")
        all_passed = False
    else:
        print(f"✓ {edges_count:,} constellation membership edges created")
    
    print("\n" + "=" * 60)
    print("Test 2: Verify Edge Counts by Constellation")
    print("=" * 60)
    
    query = """
    FOR e IN @@edge_collection
        COLLECT constellation = e.constellation_name WITH COUNT INTO count
        SORT count DESC
        RETURN {
            constellation: constellation,
            edge_count: count
        }
    """
    
    cursor = db.aql.execute(
        query,
        bind_vars={'@edge_collection': db_module.EDGE_COLLECTION_CONSTELLATION}
    )
    edge_counts = list(cursor)
    
    if edge_counts:
        print("✓ Edge counts by constellation:")
        for item in edge_counts:
            print(f"  {item['constellation']}: {item['edge_count']:,} edges")
    else:
        print("❌ Failed to count edges by constellation")
        all_passed = False
    
    print("\n" + "=" * 60)
    print("Test 3: Find All Starlink Gen 1 Satellites via Hub")
    print("=" * 60)
    
    query = """
    FOR edge IN @@edge_collection
        FILTER edge.constellation_name == "Starlink Gen 1"
        LIMIT 1
        RETURN edge._to
    """
    
    cursor = db.aql.execute(
        query,
        bind_vars={'@edge_collection': db_module.EDGE_COLLECTION_CONSTELLATION}
    )
    hub_results = list(cursor)
    
    if hub_results:
        hub_id = hub_results[0]
        print(f"✓ Found Starlink Gen 1 hub: {hub_id}")
        
        query = """
        FOR v, e, p IN 1..1 INBOUND @hub_id
        @@edge_collection
        LIMIT 10
        RETURN {
            identifier: v.identifier,
            name: v.canonical.name
        }
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={
                'hub_id': hub_id,
                '@edge_collection': db_module.EDGE_COLLECTION_CONSTELLATION
            }
        )
        starlink_sats = list(cursor)
        
        if starlink_sats:
            print(f"✓ Found {len(starlink_sats)} Starlink satellites via hub traversal")
            print(f"\nSample satellites:")
            for sat in starlink_sats[:5]:
                print(f"  - {sat['identifier']}: {sat['name']}")
        else:
            print("❌ No Starlink satellites found via hub")
            all_passed = False
    else:
        print("❌ Failed to find Starlink hub")
        all_passed = False
    
    print("\n" + "=" * 60)
    print("Test 4: Find All OneWeb Satellites via Hub")
    print("=" * 60)
    
    query = """
    FOR edge IN @@edge_collection
        FILTER edge.constellation_name == "OneWeb"
        LIMIT 1
        RETURN edge._to
    """
    
    cursor = db.aql.execute(
        query,
        bind_vars={'@edge_collection': db_module.EDGE_COLLECTION_CONSTELLATION}
    )
    hub_results = list(cursor)
    
    if hub_results:
        hub_id = hub_results[0]
        print(f"✓ Found OneWeb hub: {hub_id}")
        
        query = """
        FOR v, e, p IN 1..1 INBOUND @hub_id
        @@edge_collection
        RETURN 1
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={
                'hub_id': hub_id,
                '@edge_collection': db_module.EDGE_COLLECTION_CONSTELLATION
            }
        )
        oneweb_count = len(list(cursor))
        
        print(f"✓ Found {oneweb_count:,} OneWeb satellites via hub traversal")
    else:
        print("❌ Failed to find OneWeb hub")
        all_passed = False
    
    print("\n" + "=" * 60)
    print("Test 5: Named Graph Traversal")
    print("=" * 60)
    
    if hub_results:
        query = f"""
        FOR v, e, p IN 1..1 INBOUND @hub_id
        GRAPH '{db_module.GRAPH_NAME}'
        FILTER e.constellation_name == "OneWeb"
        LIMIT 5
        RETURN v.identifier
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={'hub_id': hub_id}
        )
        results = list(cursor)
        
        if results:
            print(f"✓ Named graph traversal successful")
            print(f"  Found {len(results)} OneWeb satellites via named graph")
        else:
            print("❌ Named graph traversal failed")
            all_passed = False
    
    print("\n" + "=" * 60)
    print("Test 6: Count Total Constellation Members")
    print("=" * 60)
    
    query = """
    FOR const_name IN ["Starlink Gen 1", "OneWeb", "Glonass", "Beidou", "Galileo", "Other"]
        LET hub = FIRST(
            FOR edge IN @@edge_collection
                FILTER edge.constellation_name == const_name
                LIMIT 1
                RETURN edge._to
        )
        LET member_count = LENGTH(
            FOR v IN 1..1 INBOUND hub
            @@edge_collection
            RETURN 1
        )
        RETURN {
            constellation: const_name,
            member_count: member_count
        }
    """
    
    cursor = db.aql.execute(
        query,
        bind_vars={'@edge_collection': db_module.EDGE_COLLECTION_CONSTELLATION}
    )
    member_counts = list(cursor)
    
    if member_counts:
        print("✓ Constellation member counts:")
        for item in member_counts:
            total = item['member_count'] + 1
            print(f"  {item['constellation']}: {total:,} total ({item['member_count']:,} members + 1 hub)")
    else:
        print("❌ Failed to count constellation members")
        all_passed = False
    
    print("\n" + "=" * 60)
    print("Verification Summary")
    print("=" * 60)
    
    if all_passed:
        print("✓ All verification tests passed!")
        print("\nConstellation network statistics:")
        print(f"  - {edges_count:,} constellation membership edges")
        print(f"  - 6 constellation hubs (Starlink Gen 1, OneWeb, Glonass, Beidou, Galileo, Other)")
        print(f"  - Star topology: All satellites → hub for efficient querying")
        print(f"\nGraph is ready for constellation visualization!")
    else:
        print("❌ Some verification tests failed")
    
    db_module.disconnect_mongodb()
    return all_passed

if __name__ == "__main__":
    success = verify_constellation_network()
    sys.exit(0 if success else 1)
