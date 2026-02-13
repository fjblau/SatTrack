from typing import Optional, Dict, List, Any
from database.connection import db, GRAPH_NAME


def create_edge_collection(edge_collection_name: str) -> bool:
    """
    Create an edge collection if it doesn't exist.
    
    Args:
        edge_collection_name: Name of the edge collection to create
    
    Returns:
        True if created or already exists, False on error
    """
    try:
        from database.connection import db as current_db
        if current_db is None:
            print(f"Database not connected. Call connect_arangodb() first.")
            return False
        
        if not current_db.has_collection(edge_collection_name):
            current_db.create_collection(edge_collection_name, edge=True)
            print(f"Created edge collection: {edge_collection_name}")
        else:
            print(f"Edge collection already exists: {edge_collection_name}")
        return True
    except Exception as e:
        print(f"Failed to create edge collection {edge_collection_name}: {e}")
        return False


def create_document_collection(collection_name: str) -> bool:
    """
    Create a document collection if it doesn't exist.
    
    Args:
        collection_name: Name of the document collection to create
    
    Returns:
        True if created or already exists, False on error
    """
    try:
        if not db.has_collection(collection_name):
            db.create_collection(collection_name, edge=False)
            print(f"Created document collection: {collection_name}")
        else:
            print(f"Document collection already exists: {collection_name}")
        return True
    except Exception as e:
        print(f"Failed to create document collection {collection_name}: {e}")
        return False


def create_graph(
    graph_name: str,
    edge_definitions: List[Dict[str, Any]]
) -> bool:
    """
    Create a named graph in ArangoDB.
    
    Args:
        graph_name: Name of the graph to create
        edge_definitions: List of edge definitions with structure:
            [{
                "edge_collection": "edge_collection_name",
                "from_vertex_collections": ["collection1"],
                "to_vertex_collections": ["collection2"]
            }]
    
    Returns:
        True if created or already exists, False on error
    """
    try:
        if db.has_graph(graph_name):
            print(f"Graph already exists: {graph_name}")
            return True
        
        db.create_graph(
            name=graph_name,
            edge_definitions=edge_definitions
        )
        print(f"Created graph: {graph_name}")
        return True
    except Exception as e:
        print(f"Failed to create graph {graph_name}: {e}")
        return False


def get_edge_collection(edge_collection_name: str):
    """
    Get an edge collection.
    
    Args:
        edge_collection_name: Name of the edge collection
    
    Returns:
        Edge collection object or None
    """
    try:
        if db.has_collection(edge_collection_name):
            return db.collection(edge_collection_name)
        else:
            print(f"Edge collection not found: {edge_collection_name}")
            return None
    except Exception as e:
        print(f"Failed to get edge collection {edge_collection_name}: {e}")
        return None


def insert_edge(
    edge_collection_name: str,
    from_id: str,
    to_id: str,
    properties: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Insert an edge into an edge collection.
    
    Args:
        edge_collection_name: Name of the edge collection
        from_id: Full document ID of source vertex (e.g., "satellites/2025-206B")
        to_id: Full document ID of target vertex
        properties: Optional edge properties
    
    Returns:
        True if successful, False otherwise
    """
    try:
        edge_collection = get_edge_collection(edge_collection_name)
        if not edge_collection:
            return False
        
        edge_doc = {
            "_from": from_id,
            "_to": to_id,
            **(properties or {})
        }
        
        edge_collection.insert(edge_doc)
        return True
    except Exception as e:
        print(f"Failed to insert edge: {e}")
        return False


def bulk_insert_edges(
    edge_collection_name: str,
    edges: List[Dict[str, Any]]
) -> Dict[str, int]:
    """
    Bulk insert edges into an edge collection.
    
    Args:
        edge_collection_name: Name of the edge collection
        edges: List of edge documents with _from, _to, and optional properties
    
    Returns:
        Dictionary with 'inserted' and 'errors' counts
    """
    try:
        edge_collection = get_edge_collection(edge_collection_name)
        if not edge_collection:
            return {"inserted": 0, "errors": len(edges)}
        
        results = edge_collection.insert_many(edges, return_new=False)
        
        inserted = sum(1 for r in results if not isinstance(r, Exception))
        errors = sum(1 for r in results if isinstance(r, Exception))
        
        return {"inserted": inserted, "errors": errors}
    except Exception as e:
        print(f"Failed to bulk insert edges: {e}")
        return {"inserted": 0, "errors": len(edges)}


def clear_edge_collection(edge_collection_name: str) -> bool:
    """
    Clear all edges from an edge collection.
    
    Args:
        edge_collection_name: Name of the edge collection to clear
    
    Returns:
        True if successful, False otherwise
    """
    try:
        edge_collection = get_edge_collection(edge_collection_name)
        if not edge_collection:
            return False
        
        edge_collection.truncate()
        print(f"Cleared edge collection: {edge_collection_name}")
        return True
    except Exception as e:
        print(f"Failed to clear edge collection {edge_collection_name}: {e}")
        return False


def get_graph():
    """
    Get the satellite_relationships graph.
    
    Returns:
        Graph object or None
    """
    try:
        if db.has_graph(GRAPH_NAME):
            return db.graph(GRAPH_NAME)
        else:
            print(f"Graph not found: {GRAPH_NAME}")
            return None
    except Exception as e:
        print(f"Failed to get graph {GRAPH_NAME}: {e}")
        return None


def add_edge_indexes(edge_collection_name: str) -> bool:
    """
    Add standard indexes to an edge collection for better traversal performance.
    
    Note: ArangoDB automatically creates a combined edge index on ['_from', '_to']
    when an edge collection is created. This function verifies the index exists.
    
    Args:
        edge_collection_name: Name of the edge collection
    
    Returns:
        True if successful, False otherwise
    """
    try:
        from database.connection import db as current_db
        if current_db is None:
            print(f"Database not connected. Call connect_arangodb() first.")
            return False
        
        if not current_db.has_collection(edge_collection_name):
            print(f"❌ Collection not found: {edge_collection_name}")
            return False
        
        edge_collection = current_db.collection(edge_collection_name)
        existing_indexes = edge_collection.indexes()
        
        edge_index_exists = any(
            idx.get('type') == 'edge' for idx in existing_indexes
        )
        
        if edge_index_exists:
            print(f"✓ Edge index exists on {edge_collection_name} (_from, _to)")
        else:
            print(f"⚠ No edge index found on {edge_collection_name}")
        
        return True
    except Exception as e:
        print(f"Failed to check indexes on {edge_collection_name}: {e}")
        return False
