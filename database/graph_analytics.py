"""
Graph analytics module for advanced graph traversal and analysis.

This module provides helper functions for:
- Path finding (shortest path, all paths)
- Centrality calculations
- Community detection
- Graph traversal utilities
- Multi-edge type queries
"""
from typing import Optional, Dict, List, Any, Set
from database.connection import db, COLLECTION_NAME


def find_shortest_path(
    from_id: str,
    to_id: str,
    edge_types: Optional[List[str]] = None,
    max_depth: int = 10
) -> Optional[Dict[str, Any]]:
    """
    Find the shortest path between two satellites.
    
    Args:
        from_id: Source satellite document ID (e.g., "satellites/2025-206B")
        to_id: Target satellite document ID
        edge_types: Optional list of edge collection names to traverse
        max_depth: Maximum traversal depth
    
    Returns:
        Dictionary containing path information or None if no path found:
        {
            "vertices": [...],  # List of vertex documents
            "edges": [...],     # List of edge documents
            "distance": int     # Number of hops
        }
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join([f"'{edge}'" for edge in edge_collections])
        
        query = f"""
        FOR v, e IN 1..@max_depth OUTBOUND @from_id
            {edge_clause}
            FILTER v._id == @to_id
            LIMIT 1
            RETURN {{
                vertices: [v],
                edges: [e],
                distance: LENGTH([v])
            }}
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={
                'from_id': from_id,
                'to_id': to_id,
                'max_depth': max_depth
            }
        )
        
        results = list(cursor)
        return results[0] if results else None
        
    except Exception as e:
        print(f"Error finding shortest path: {e}")
        return None


def find_all_paths(
    from_id: str,
    to_id: str,
    edge_types: Optional[List[str]] = None,
    max_depth: int = 5,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Find all paths between two satellites up to max_depth.
    
    Args:
        from_id: Source satellite document ID
        to_id: Target satellite document ID
        edge_types: Optional list of edge collection names to traverse
        max_depth: Maximum traversal depth
        limit: Maximum number of paths to return
    
    Returns:
        List of path dictionaries
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join([f"'{edge}'" for edge in edge_collections])
        
        query = f"""
        FOR v, e, p IN 1..@max_depth OUTBOUND @from_id
            {edge_clause}
            FILTER v._id == @to_id
            LIMIT @limit
            RETURN {{
                vertices: p.vertices,
                edges: p.edges,
                distance: LENGTH(p.vertices) - 1
            }}
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={
                'from_id': from_id,
                'to_id': to_id,
                'max_depth': max_depth,
                'limit': limit
            }
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error finding all paths: {e}")
        return []


def calculate_degree_centrality(
    edge_types: Optional[List[str]] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Calculate degree centrality for satellites.
    
    Args:
        edge_types: Optional list of edge collections to consider
        limit: Maximum number of results to return
    
    Returns:
        List of satellites with their degree centrality scores
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join([f"'{edge}'" for edge in edge_collections])
        
        query = f"""
        FOR doc IN {COLLECTION_NAME}
            LET outbound_count = LENGTH(
                FOR v IN 1..1 OUTBOUND doc._id {edge_clause}
                RETURN v
            )
            LET inbound_count = LENGTH(
                FOR v IN 1..1 INBOUND doc._id {edge_clause}
                RETURN v
            )
            LET degree = outbound_count + inbound_count
            FILTER degree > 0
            SORT degree DESC
            LIMIT @limit
            RETURN {{
                _id: doc._id,
                identifier: doc.identifier,
                name: doc.canonical.name,
                degree: degree,
                inbound: inbound_count,
                outbound: outbound_count
            }}
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={'limit': limit}
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error calculating degree centrality: {e}")
        return []


def traverse_graph(
    start_id: str,
    edge_types: Optional[List[str]] = None,
    direction: str = 'OUTBOUND',
    min_depth: int = 1,
    max_depth: int = 3,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Generic graph traversal function.
    
    Args:
        start_id: Starting vertex document ID
        edge_types: Optional list of edge collections to traverse
        direction: Traversal direction ('OUTBOUND', 'INBOUND', 'ANY')
        min_depth: Minimum traversal depth
        max_depth: Maximum traversal depth
        limit: Optional limit on results
    
    Returns:
        List of reached vertices with path information
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join([f"'{edge}'" for edge in edge_collections])
        
        limit_clause = f"LIMIT {limit}" if limit else ""
        
        query = f"""
        FOR v, e, p IN @min_depth..@max_depth {direction} @start_id
            {edge_clause}
            {limit_clause}
            RETURN {{
                vertex: v,
                edge: e,
                path: p,
                depth: LENGTH(p.vertices) - 1
            }}
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={
                'start_id': start_id,
                'min_depth': min_depth,
                'max_depth': max_depth
            }
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error traversing graph: {e}")
        return []


def get_neighbors(
    vertex_id: str,
    edge_types: Optional[List[str]] = None,
    direction: str = 'ANY'
) -> List[Dict[str, Any]]:
    """
    Get direct neighbors of a vertex.
    
    Args:
        vertex_id: Vertex document ID
        edge_types: Optional list of edge collections
        direction: Traversal direction ('OUTBOUND', 'INBOUND', 'ANY')
    
    Returns:
        List of neighbor vertices with edge information
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join([f"'{edge}'" for edge in edge_collections])
        
        query = f"""
        FOR v, e IN 1..1 {direction} @vertex_id
            {edge_clause}
            RETURN {{
                vertex: v,
                edge: e,
                edge_type: PARSE_IDENTIFIER(e).collection
            }}
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={'vertex_id': vertex_id}
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error getting neighbors: {e}")
        return []


def count_edges_by_type(vertex_id: str) -> Dict[str, int]:
    """
    Count edges by type for a given vertex.
    
    Args:
        vertex_id: Vertex document ID
    
    Returns:
        Dictionary mapping edge collection names to counts
    """
    try:
        from database.connection import (
            EDGE_COLLECTION_CONSTELLATION,
            EDGE_COLLECTION_REGISTRATION,
            EDGE_COLLECTION_PROXIMITY
        )
        
        edge_collections = [
            EDGE_COLLECTION_CONSTELLATION,
            EDGE_COLLECTION_REGISTRATION,
            EDGE_COLLECTION_PROXIMITY
        ]
        
        counts = {}
        for edge_collection in edge_collections:
            query = f"""
            LET outbound = LENGTH(
                FOR v IN 1..1 OUTBOUND @vertex_id {edge_collection}
                RETURN v
            )
            LET inbound = LENGTH(
                FOR v IN 1..1 INBOUND @vertex_id {edge_collection}
                RETURN v
            )
            RETURN {{
                outbound: outbound,
                inbound: inbound,
                total: outbound + inbound
            }}
            """
            
            cursor = db.aql.execute(
                query,
                bind_vars={'vertex_id': vertex_id}
            )
            
            result = list(cursor)[0]
            counts[edge_collection] = result
        
        return counts
        
    except Exception as e:
        print(f"Error counting edges by type: {e}")
        return {}


def find_connected_components(
    edge_types: Optional[List[str]] = None,
    min_component_size: int = 2
) -> List[Dict[str, Any]]:
    """
    Find connected components in the graph.
    
    Args:
        edge_types: Optional list of edge collections
        min_component_size: Minimum size for a component to be included
    
    Returns:
        List of components with their members
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join([f"'{edge}'" for edge in edge_collections])
        
        query = f"""
        FOR doc IN {COLLECTION_NAME}
            LET component = (
                FOR v IN 0..100 ANY doc._id {edge_clause}
                RETURN DISTINCT v._id
            )
            FILTER LENGTH(component) >= @min_size
            COLLECT components = component
            RETURN {{
                size: LENGTH(components),
                members: components
            }}
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={'min_size': min_component_size}
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error finding connected components: {e}")
        return []
