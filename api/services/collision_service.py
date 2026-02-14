"""
Collision risk analysis service.

Provides functions for analyzing collision risks between satellites,
including risk scoring, filtering, and network analysis.
"""
from typing import List, Dict, Any, Optional
import database.connection as db_conn
from database.connection import COLLECTION_NAME, EDGE_COLLECTION_COLLISION_RISK


def calculate_collision_risk_score(
    apogee_diff_km: float,
    perigee_diff_km: float,
    inclination_diff_degrees: float
) -> float:
    """
    Calculate collision risk score based on orbital parameter proximity.
    
    Args:
        apogee_diff_km: Difference in apogee (km)
        perigee_diff_km: Difference in perigee (km)
        inclination_diff_degrees: Difference in inclination (degrees)
    
    Returns:
        Risk score (0-1 range, higher = higher risk)
    """
    APOGEE_THRESHOLD = 20.0
    PERIGEE_THRESHOLD = 20.0
    INCLINATION_THRESHOLD = 2.0
    
    apogee_score = max(0, 1 - (apogee_diff_km / APOGEE_THRESHOLD))
    perigee_score = max(0, 1 - (perigee_diff_km / PERIGEE_THRESHOLD))
    inclination_score = max(0, 1 - (inclination_diff_degrees / INCLINATION_THRESHOLD))
    
    risk_score = (apogee_score + perigee_score + inclination_score) / 3
    
    return round(risk_score, 4)


def get_collision_risks(
    risk_threshold: Optional[float] = None,
    orbital_band: Optional[str] = None,
    risk_level: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Query collision risk edges with filtering.
    
    Args:
        risk_threshold: Minimum risk score threshold (0-1)
        orbital_band: Filter by orbital band (LEO, MEO, GEO, etc.)
        risk_level: Filter by risk level (high, medium, low)
        limit: Maximum number of edges to return
    
    Returns:
        List of collision risk edges with satellite information
    """
    try:
        filters = []
        bind_vars = {'limit': limit}
        
        if risk_threshold is not None:
            filters.append("edge.risk_score >= @risk_threshold")
            bind_vars['risk_threshold'] = risk_threshold
        
        if orbital_band:
            filters.append("edge.orbital_band == @orbital_band")
            bind_vars['orbital_band'] = orbital_band
        
        if risk_level:
            filters.append("edge.risk_level == @risk_level")
            bind_vars['risk_level'] = risk_level
        
        filter_clause = " AND ".join(filters) if filters else "true"
        
        query = f"""
        FOR edge IN {EDGE_COLLECTION_COLLISION_RISK}
            FILTER {filter_clause}
            SORT edge.risk_score DESC
            LIMIT @limit
            
            LET from_sat = DOCUMENT(edge._from)
            LET to_sat = DOCUMENT(edge._to)
            
            RETURN {{
                edge_id: edge._key,
                from: {{
                    _id: from_sat._id,
                    identifier: from_sat.identifier,
                    name: from_sat.canonical.name,
                    orbital_band: from_sat.canonical.orbital_band
                }},
                to: {{
                    _id: to_sat._id,
                    identifier: to_sat.identifier,
                    name: to_sat.canonical.name,
                    orbital_band: to_sat.canonical.orbital_band
                }},
                risk_score: edge.risk_score,
                risk_level: edge.risk_level,
                orbital_band: edge.orbital_band,
                differences: {{
                    apogee_km: edge.apogee_diff_km,
                    perigee_km: edge.perigee_diff_km,
                    inclination_degrees: edge.inclination_diff_degrees
                }}
            }}
        """
        
        cursor = db_conn.db.aql.execute(query, bind_vars=bind_vars)
        return list(cursor)
        
    except Exception as e:
        print(f"Error querying collision risks: {e}")
        return []


def get_collision_risks_for_satellite(
    satellite_id: str,
    risk_threshold: Optional[float] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get collision risk edges for a specific satellite.
    
    Args:
        satellite_id: Satellite document ID (e.g., "satellites/2025-206B" or "2025-206B")
        risk_threshold: Minimum risk score threshold
        limit: Maximum number of edges to return
    
    Returns:
        List of collision risk edges involving this satellite
    """
    try:
        if "/" not in satellite_id:
            satellite_id = f"{COLLECTION_NAME}/{satellite_id}"
        
        bind_vars = {
            'satellite_id': satellite_id,
            'limit': limit
        }
        
        risk_filter = ""
        if risk_threshold is not None:
            risk_filter = "FILTER edge.risk_score >= @risk_threshold"
            bind_vars['risk_threshold'] = risk_threshold
        
        query = f"""
        FOR edge IN {EDGE_COLLECTION_COLLISION_RISK}
            FILTER edge._from == @satellite_id OR edge._to == @satellite_id
            {risk_filter}
            SORT edge.risk_score DESC
            LIMIT @limit
            
            LET from_sat = DOCUMENT(edge._from)
            LET to_sat = DOCUMENT(edge._to)
            LET other_sat = edge._from == @satellite_id ? to_sat : from_sat
            
            RETURN {{
                edge_id: edge._key,
                other_satellite: {{
                    _id: other_sat._id,
                    identifier: other_sat.identifier,
                    name: other_sat.canonical.name,
                    orbital_band: other_sat.canonical.orbital_band
                }},
                risk_score: edge.risk_score,
                risk_level: edge.risk_level,
                orbital_band: edge.orbital_band,
                differences: {{
                    apogee_km: edge.apogee_diff_km,
                    perigee_km: edge.perigee_diff_km,
                    inclination_degrees: edge.inclination_diff_degrees
                }}
            }}
        """
        
        cursor = db_conn.db.aql.execute(query, bind_vars=bind_vars)
        return list(cursor)
        
    except Exception as e:
        print(f"Error querying collision risks for satellite: {e}")
        return []


def get_collision_risk_network(
    orbital_band: Optional[str] = None,
    risk_threshold: float = 0.5,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get collision risk network as nodes and edges for visualization.
    
    Args:
        orbital_band: Filter by orbital band
        risk_threshold: Minimum risk score
        limit: Maximum number of edges
    
    Returns:
        Dictionary with nodes and edges for graph visualization
    """
    try:
        bind_vars = {
            'risk_threshold': risk_threshold,
            'limit': limit
        }
        
        band_filter = ""
        if orbital_band:
            band_filter = "FILTER edge.orbital_band == @orbital_band"
            bind_vars['orbital_band'] = orbital_band
        
        query = f"""
        LET edges = (
            FOR edge IN {EDGE_COLLECTION_COLLISION_RISK}
                {band_filter}
                FILTER edge.risk_score >= @risk_threshold
                SORT edge.risk_score DESC
                LIMIT @limit
                RETURN edge
        )
        
        LET satellite_ids = UNIQUE(FLATTEN(
            FOR edge IN edges
                RETURN [edge._from, edge._to]
        ))
        
        LET satellites = (
            FOR sat_id IN satellite_ids
                LET sat = DOCUMENT(sat_id)
                RETURN {{
                    id: sat._id,
                    key: sat._key,
                    identifier: sat.identifier,
                    name: sat.canonical.name,
                    orbital_band: sat.canonical.orbital_band,
                    apogee_km: sat.canonical.orbit.apogee_km,
                    perigee_km: sat.canonical.orbit.perigee_km,
                    inclination_degrees: sat.canonical.orbit.inclination_degrees
                }}
        )
        
        LET formatted_edges = (
            FOR edge IN edges
                RETURN {{
                    id: edge._key,
                    source: edge._from,
                    target: edge._to,
                    risk_score: edge.risk_score,
                    risk_level: edge.risk_level,
                    apogee_diff_km: edge.apogee_diff_km,
                    perigee_diff_km: edge.perigee_diff_km,
                    inclination_diff_degrees: edge.inclination_diff_degrees
                }}
        )
        
        RETURN {{
            nodes: satellites,
            edges: formatted_edges,
            stats: {{
                total_satellites: LENGTH(satellites),
                total_edges: LENGTH(formatted_edges),
                risk_threshold: @risk_threshold,
                orbital_band: {f'@orbital_band' if orbital_band else 'null'}
            }}
        }}
        """
        
        cursor = db_conn.db.aql.execute(query, bind_vars=bind_vars)
        results = list(cursor)
        return results[0] if results else {
            "nodes": [],
            "edges": [],
            "stats": {
                "total_satellites": 0,
                "total_edges": 0,
                "risk_threshold": risk_threshold,
                "orbital_band": orbital_band
            }
        }
        
    except Exception as e:
        print(f"Error building collision risk network: {e}")
        return {
            "nodes": [],
            "edges": [],
            "stats": {
                "total_satellites": 0,
                "total_edges": 0,
                "risk_threshold": risk_threshold,
                "orbital_band": orbital_band
            },
            "error": str(e)
        }


def get_collision_risk_statistics(
    orbital_band: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get statistics about collision risks in the database.
    
    Args:
        orbital_band: Optional filter by orbital band
    
    Returns:
        Dictionary with collision risk statistics
    """
    try:
        bind_vars = {}
        band_filter = ""
        
        if orbital_band:
            band_filter = "FILTER edge.orbital_band == @orbital_band"
            bind_vars['orbital_band'] = orbital_band
        
        query = f"""
        LET edges = (
            FOR edge IN {EDGE_COLLECTION_COLLISION_RISK}
                {band_filter}
                RETURN edge
        )
        
        LET risk_level_counts = (
            FOR edge IN edges
                COLLECT level = edge.risk_level WITH COUNT INTO count
                RETURN {{level: level, count: count}}
        )
        
        LET band_counts = (
            FOR edge IN edges
                COLLECT band = edge.orbital_band WITH COUNT INTO count
                SORT count DESC
                RETURN {{orbital_band: band, edge_count: count}}
        )
        
        LET avg_risk = AVERAGE(edges[*].risk_score)
        LET max_risk = MAX(edges[*].risk_score)
        LET min_risk = MIN(edges[*].risk_score)
        
        RETURN {{
            total_edges: LENGTH(edges),
            risk_levels: risk_level_counts,
            orbital_bands: band_counts,
            risk_score_stats: {{
                average: avg_risk,
                maximum: max_risk,
                minimum: min_risk
            }}
        }}
        """
        
        cursor = db_conn.db.aql.execute(query, bind_vars=bind_vars)
        results = list(cursor)
        return results[0] if results else {}
        
    except Exception as e:
        print(f"Error calculating collision risk statistics: {e}")
        return {}
