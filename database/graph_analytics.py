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
from database.connection import db, COLLECTION_NAME, EDGE_COLLECTION_COLLISION_RISK


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


def calculate_betweenness_centrality(
    edge_types: Optional[List[str]] = None,
    limit: int = 100,
    sample_size: int = 100
) -> List[Dict[str, Any]]:
    """
    Calculate betweenness centrality for satellites.
    
    Betweenness centrality measures how often a node appears on shortest paths
    between other nodes. Higher scores indicate nodes that serve as bridges
    in the network.
    
    Args:
        edge_types: Optional list of edge collections to consider
        limit: Maximum number of results to return
        sample_size: Number of nodes to sample for path calculations
    
    Returns:
        List of satellites with their betweenness centrality scores
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
        LET sample_nodes = (
            FOR doc IN {COLLECTION_NAME}
                LIMIT @sample_size
                RETURN doc._id
        )
        
        FOR node IN {COLLECTION_NAME}
            LET betweenness = SUM(
                FOR source IN sample_nodes
                    FILTER source != node._id
                    FOR target IN sample_nodes
                        FILTER target != node._id AND target != source
                        LET path = (
                            FOR v, e, p IN 1..5 OUTBOUND source
                                {edge_clause}
                                FILTER v._id == target
                                LIMIT 1
                                RETURN p.vertices
                        )
                        RETURN LENGTH(path) > 0 AND node._id IN path[0] ? 1 : 0
            )
            FILTER betweenness > 0
            SORT betweenness DESC
            LIMIT @limit
            RETURN {{
                _id: node._id,
                identifier: node.identifier,
                name: node.canonical.name,
                betweenness_centrality: betweenness,
                normalized_score: betweenness / (@sample_size * (@sample_size - 1))
            }}
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={
                'limit': limit,
                'sample_size': sample_size
            }
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error calculating betweenness centrality: {e}")
        return []


def calculate_closeness_centrality(
    edge_types: Optional[List[str]] = None,
    limit: int = 100,
    max_depth: int = 5
) -> List[Dict[str, Any]]:
    """
    Calculate closeness centrality for satellites.
    
    Closeness centrality measures how close a node is to all other nodes
    in the network. Higher scores indicate nodes that can reach others quickly.
    
    Args:
        edge_types: Optional list of edge collections to consider
        limit: Maximum number of results to return
        max_depth: Maximum depth for reachability calculations
    
    Returns:
        List of satellites with their closeness centrality scores
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
        FOR node IN {COLLECTION_NAME}
            LET reachable = (
                FOR v, e, p IN 1..@max_depth ANY node._id
                    {edge_clause}
                    RETURN {{
                        vertex: v._id,
                        distance: LENGTH(p.vertices) - 1
                    }}
            )
            LET total_distance = SUM(reachable[*].distance)
            LET reachable_count = LENGTH(reachable)
            FILTER reachable_count > 0
            LET closeness = reachable_count / total_distance
            SORT closeness DESC
            LIMIT @limit
            RETURN {{
                _id: node._id,
                identifier: node.identifier,
                name: node.canonical.name,
                closeness_centrality: closeness,
                reachable_nodes: reachable_count,
                avg_distance: total_distance / reachable_count
            }}
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={
                'limit': limit,
                'max_depth': max_depth
            }
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error calculating closeness centrality: {e}")
        return []


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


def get_collision_risk_neighbors(
    satellite_id: str,
    risk_threshold: float = 0.5,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get satellites with collision risk to a specific satellite.
    
    Args:
        satellite_id: Satellite document ID
        risk_threshold: Minimum risk score threshold
        limit: Maximum number of results
    
    Returns:
        List of satellites with collision risk information
    """
    try:
        if "/" not in satellite_id:
            satellite_id = f"{COLLECTION_NAME}/{satellite_id}"
        
        query = f"""
        FOR v, e IN 1..1 ANY @satellite_id {EDGE_COLLECTION_COLLISION_RISK}
            FILTER e.risk_score >= @risk_threshold
            SORT e.risk_score DESC
            LIMIT @limit
            RETURN {{
                satellite: v,
                edge: e,
                risk_score: e.risk_score,
                risk_level: e.risk_level,
                orbital_band: e.orbital_band,
                differences: {{
                    apogee_km: e.apogee_diff_km,
                    perigee_km: e.perigee_diff_km,
                    inclination_degrees: e.inclination_diff_degrees
                }}
            }}
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={
                'satellite_id': satellite_id,
                'risk_threshold': risk_threshold,
                'limit': limit
            }
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error getting collision risk neighbors: {e}")
        return []


def analyze_collision_clusters(
    orbital_band: Optional[str] = None,
    risk_threshold: float = 0.7,
    min_cluster_size: int = 3
) -> List[Dict[str, Any]]:
    """
    Identify clusters of satellites with high collision risk.
    
    Args:
        orbital_band: Optional filter by orbital band
        risk_threshold: Minimum risk score to consider
        min_cluster_size: Minimum number of satellites in a cluster
    
    Returns:
        List of collision risk clusters
    """
    try:
        bind_vars = {
            'risk_threshold': risk_threshold,
            'min_cluster_size': min_cluster_size
        }
        
        band_filter = ""
        if orbital_band:
            band_filter = "FILTER edge.orbital_band == @orbital_band"
            bind_vars['orbital_band'] = orbital_band
        
        query = f"""
        LET high_risk_edges = (
            FOR edge IN {EDGE_COLLECTION_COLLISION_RISK}
                {band_filter}
                FILTER edge.risk_score >= @risk_threshold
                RETURN edge
        )
        
        FOR doc IN {COLLECTION_NAME}
            LET cluster_satellites = (
                FOR v, e IN 1..2 ANY doc._id {EDGE_COLLECTION_COLLISION_RISK}
                    FILTER e.risk_score >= @risk_threshold
                    {band_filter.replace('edge.', 'e.')}
                    RETURN DISTINCT v
            )
            FILTER LENGTH(cluster_satellites) >= @min_cluster_size
            
            LET cluster_edges = (
                FOR edge IN high_risk_edges
                    FILTER edge._from IN cluster_satellites[*]._id OR edge._to IN cluster_satellites[*]._id
                    RETURN edge
            )
            
            RETURN {{
                center_satellite: {{
                    _id: doc._id,
                    identifier: doc.identifier,
                    name: doc.canonical.name,
                    orbital_band: doc.canonical.orbital_band
                }},
                cluster_size: LENGTH(cluster_satellites),
                satellites: cluster_satellites,
                internal_edges: LENGTH(cluster_edges),
                avg_risk_score: AVERAGE(cluster_edges[*].risk_score),
                max_risk_score: MAX(cluster_edges[*].risk_score)
            }}
        """
        
        cursor = db.aql.execute(query, bind_vars=bind_vars)
        return list(cursor)
        
    except Exception as e:
        print(f"Error analyzing collision clusters: {e}")
        return []
