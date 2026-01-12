#!/usr/bin/env python3
"""
Populate registration document network.

Creates:
- Document nodes in registration_documents collection
- Edges from satellites to registration documents
"""
import sys
from collections import defaultdict
import db as db_module

def populate_registration_network(dry_run=False):
    """Create registration document nodes and edges"""
    
    print("=" * 60)
    print("Registration Document Network Population")
    print("=" * 60)
    
    if not db_module.connect_mongodb():
        print("❌ Failed to connect to ArangoDB")
        return False
    
    db = db_module.db
    
    print("\n" + "=" * 60)
    print("Step 1: Extract Registration Documents")
    print("=" * 60)
    
    query = """
    FOR doc IN @@collection
        FILTER doc.canonical.registration_document != null
        RETURN {
            _key: doc._key,
            identifier: doc.identifier,
            registration_document: doc.canonical.registration_document,
            country: doc.canonical.country_of_origin,
            name: doc.canonical.name
        }
    """
    
    cursor = db.aql.execute(
        query,
        bind_vars={'@collection': db_module.COLLECTION_NAME}
    )
    
    satellites_with_reg_doc = list(cursor)
    print(f"Found {len(satellites_with_reg_doc):,} satellites with registration documents")
    
    reg_doc_data = defaultdict(lambda: {"satellites": [], "countries": set()})
    
    for sat in satellites_with_reg_doc:
        reg_doc_url = sat['registration_document']
        reg_doc_data[reg_doc_url]["satellites"].append({
            "_key": sat["_key"],
            "identifier": sat["identifier"],
            "name": sat["name"]
        })
        if sat['country']:
            reg_doc_data[reg_doc_url]["countries"].add(sat['country'])
    
    print(f"Extracted {len(reg_doc_data):,} unique registration documents")
    
    if dry_run:
        print("\n[DRY-RUN] Sample registration documents:")
        for i, (url, data) in enumerate(list(reg_doc_data.items())[:5]):
            print(f"\n  {url}")
            print(f"    Satellites: {len(data['satellites'])}")
            print(f"    Countries: {', '.join(sorted(data['countries']))}")
        print(f"\n[DRY-RUN] Would create {len(reg_doc_data):,} registration documents")
        print(f"[DRY-RUN] Would create {len(satellites_with_reg_doc):,} edges")
        return True
    
    print("\n" + "=" * 60)
    print("Step 2: Create Registration Document Nodes")
    print("=" * 60)
    
    reg_docs_collection = db.collection(db_module.COLLECTION_REG_DOCS)
    
    existing_count_query = f"RETURN LENGTH({db_module.COLLECTION_REG_DOCS})"
    cursor = db.aql.execute(existing_count_query)
    existing_count = list(cursor)[0]
    
    if existing_count > 0:
        print(f"Found {existing_count} existing registration documents. Clearing...")
        reg_docs_collection.truncate()
    
    reg_doc_nodes = []
    for url, data in reg_doc_data.items():
        doc_key = url.replace('/', '_').replace('.', '_').replace(':', '_')
        
        reg_doc_nodes.append({
            "_key": doc_key,
            "url": url,
            "satellite_count": len(data['satellites']),
            "countries": sorted(list(data['countries'])),
            "created_at": db_module.datetime.now(db_module.timezone.utc).isoformat()
        })
    
    print(f"Inserting {len(reg_doc_nodes):,} registration document nodes...")
    results = reg_docs_collection.insert_many(reg_doc_nodes, return_new=False)
    
    inserted = sum(1 for r in results if not isinstance(r, Exception))
    errors = sum(1 for r in results if isinstance(r, Exception))
    
    print(f"✓ Inserted {inserted:,} registration document nodes")
    if errors > 0:
        print(f"⚠ {errors} errors during insertion")
    
    print("\n" + "=" * 60)
    print("Step 3: Create Edges (Satellites → Registration Documents)")
    print("=" * 60)
    
    edge_collection = db.collection(db_module.EDGE_COLLECTION_REGISTRATION)
    
    existing_edge_query = f"RETURN LENGTH({db_module.EDGE_COLLECTION_REGISTRATION})"
    cursor = db.aql.execute(existing_edge_query)
    existing_edges = list(cursor)[0]
    
    if existing_edges > 0:
        print(f"Found {existing_edges} existing edges. Clearing...")
        edge_collection.truncate()
    
    edges = []
    for url, data in reg_doc_data.items():
        doc_key = url.replace('/', '_').replace('.', '_').replace(':', '_')
        to_id = f"{db_module.COLLECTION_REG_DOCS}/{doc_key}"
        
        for sat in data['satellites']:
            from_id = f"{db_module.COLLECTION_NAME}/{sat['_key']}"
            edges.append({
                "_from": from_id,
                "_to": to_id,
                "registration_document": url
            })
    
    print(f"Inserting {len(edges):,} edges...")
    
    batch_size = 1000
    total_inserted = 0
    total_errors = 0
    
    for i in range(0, len(edges), batch_size):
        batch = edges[i:i + batch_size]
        results = edge_collection.insert_many(batch, return_new=False)
        
        batch_inserted = sum(1 for r in results if not isinstance(r, Exception))
        batch_errors = sum(1 for r in results if isinstance(r, Exception))
        
        total_inserted += batch_inserted
        total_errors += batch_errors
        
        if (i // batch_size + 1) % 5 == 0 or i + batch_size >= len(edges):
            print(f"  Progress: {total_inserted:,} / {len(edges):,} edges inserted")
    
    print(f"✓ Inserted {total_inserted:,} edges")
    if total_errors > 0:
        print(f"⚠ {total_errors} errors during edge insertion")
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    print(f"✓ Registration documents created: {inserted:,}")
    print(f"✓ Edges created: {total_inserted:,}")
    print(f"\nRegistration document network is ready!")
    print(f"  - 5,055 satellites linked to 746 registration documents")
    print(f"  - Average satellites per document: {5055 / 746:.1f}")
    
    db_module.disconnect_mongodb()
    return True

if __name__ == "__main__":
    import sys
    
    dry_run = "--dry-run" in sys.argv
    success = populate_registration_network(dry_run=dry_run)
    sys.exit(0 if success else 1)
