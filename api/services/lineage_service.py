"""
Satellite lineage tracking service.

Provides functions for detecting and analyzing satellite family relationships
based on naming patterns, manufacturers, and technological generations.
"""
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from database.connection import db, COLLECTION_NAME, EDGE_COLLECTION_SATELLITE_LINEAGE


SATELLITE_FAMILIES = {
    "GPS": {
        "pattern": r"(?i)gps[\s\-]*(i{1,3}[a-z]?|block\s*[ivx]+)",
        "generations": {
            "I": 1,
            "II": 2,
            "IIA": 3,
            "IIR": 4,
            "IIR-M": 5,
            "IIF": 6,
            "III": 7
        }
    },
    "IRIDIUM": {
        "pattern": r"(?i)iridium[\s\-]*(\d+|next)",
        "generations": {
            "original": 1,
            "next": 2
        }
    },
    "GLONASS": {
        "pattern": r"(?i)glonass[\s\-]*(m|k)?",
        "generations": {
            "": 1,
            "M": 2,
            "K": 3
        }
    },
    "STARLINK": {
        "pattern": r"(?i)starlink[\s\-]*(v?\d+(\.\d+)?)?",
        "generations": {}
    },
    "ONEWEB": {
        "pattern": r"(?i)oneweb[\s\-]*(\d+)?",
        "generations": {}
    },
    "GALILEO": {
        "pattern": r"(?i)galileo[\s\-]*(\d+|foc|iov)?",
        "generations": {
            "IOV": 1,
            "FOC": 2
        }
    },
    "COSMOS": {
        "pattern": r"(?i)cosmos[\s\-]*(\d+)",
        "generations": {}
    },
    "BEIDOU": {
        "pattern": r"(?i)beidou[\s\-]*(g?\d+)?",
        "generations": {}
    }
}


def detect_satellite_family(name: str) -> Optional[Tuple[str, Optional[str], Optional[int]]]:
    """
    Detect satellite family, variant, and generation from name.
    
    Args:
        name: Satellite name
    
    Returns:
        Tuple of (family_name, variant, generation) or None if no match
    """
    if not name:
        return None
    
    for family_name, family_info in SATELLITE_FAMILIES.items():
        pattern = family_info["pattern"]
        match = re.search(pattern, name)
        
        if match:
            variant = match.group(1) if match.groups() else None
            generation = None
            
            if variant and family_info.get("generations"):
                variant_upper = variant.upper().strip()
                generation = family_info["generations"].get(variant_upper)
            
            return (family_name, variant, generation)
    
    return None


def extract_numeric_series(name: str) -> Optional[int]:
    """
    Extract numeric series from satellite name (e.g., "IRIDIUM 21" -> 21).
    
    Args:
        name: Satellite name
    
    Returns:
        Numeric identifier or None
    """
    match = re.search(r'\b(\d+)\b', name)
    return int(match.group(1)) if match else None


def calculate_lineage_similarity(
    sat1_name: str,
    sat2_name: str,
    sat1_manufacturer: Optional[str] = None,
    sat2_manufacturer: Optional[str] = None
) -> float:
    """
    Calculate similarity score between two satellites for lineage detection.
    
    Args:
        sat1_name: First satellite name
        sat2_name: Second satellite name
        sat1_manufacturer: First satellite manufacturer
        sat2_manufacturer: Second satellite manufacturer
    
    Returns:
        Similarity score (0-1, higher means more likely to be related)
    """
    if not sat1_name or not sat2_name:
        return 0.0
    
    score = 0.0
    
    family1 = detect_satellite_family(sat1_name)
    family2 = detect_satellite_family(sat2_name)
    
    if family1 and family2:
        if family1[0] == family2[0]:
            score += 0.7
            
            if family1[2] is not None and family2[2] is not None:
                gen_diff = abs(family1[2] - family2[2])
                score += 0.2 * (1.0 / (1.0 + gen_diff))
    
    if sat1_manufacturer and sat2_manufacturer:
        if sat1_manufacturer.lower().strip() == sat2_manufacturer.lower().strip():
            score += 0.1
    
    return min(score, 1.0)


def detect_lineage_relationships(satellites: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detect lineage relationships among a list of satellites.
    
    Args:
        satellites: List of satellite documents with name and manufacturer
    
    Returns:
        List of edge documents representing lineage relationships
    """
    edges = []
    
    satellites_by_family = {}
    for sat in satellites:
        name = sat.get("name", "")
        family_info = detect_satellite_family(name)
        
        if family_info:
            family_name = family_info[0]
            if family_name not in satellites_by_family:
                satellites_by_family[family_name] = []
            satellites_by_family[family_name].append({
                "sat": sat,
                "family_info": family_info
            })
    
    for family_name, family_sats in satellites_by_family.items():
        family_sats_with_gen = [
            fs for fs in family_sats
            if fs["family_info"][2] is not None
        ]
        
        if len(family_sats_with_gen) >= 2:
            family_sats_with_gen.sort(key=lambda x: x["family_info"][2])
            
            for i in range(len(family_sats_with_gen) - 1):
                current = family_sats_with_gen[i]
                next_sat = family_sats_with_gen[i + 1]
                
                edges.append({
                    "_from": current["sat"]["_id"],
                    "_to": next_sat["sat"]["_id"],
                    "relationship_type": "successor",
                    "family_name": family_name,
                    "generation_from": current["family_info"][2],
                    "generation_to": next_sat["family_info"][2],
                    "generation_gap": next_sat["family_info"][2] - current["family_info"][2]
                })
    
    return edges


def get_satellite_lineage(
    satellite_id: str,
    direction: str = "both",
    max_depth: int = 5
) -> Dict[str, Any]:
    """
    Get lineage tree for a satellite (ancestors and/or descendants).
    
    Args:
        satellite_id: Satellite document ID (e.g., "satellites/2025-001A" or "2025-001A")
        direction: "ancestors", "descendants", or "both"
        max_depth: Maximum traversal depth
    
    Returns:
        Dictionary with lineage tree information
    """
    try:
        if "/" not in satellite_id:
            satellite_id = f"{COLLECTION_NAME}/{satellite_id}"
        
        root_sat = db.aql.execute(
            f"RETURN DOCUMENT(@id)",
            bind_vars={"id": satellite_id}
        )
        root_list = list(root_sat)
        
        if not root_list or not root_list[0]:
            return {
                "root": None,
                "ancestors": [],
                "descendants": [],
                "error": "Satellite not found"
            }
        
        root = root_list[0]
        
        ancestors = []
        descendants = []
        
        if direction in ["ancestors", "both"]:
            ancestors = _traverse_lineage(satellite_id, "INBOUND", max_depth)
        
        if direction in ["descendants", "both"]:
            descendants = _traverse_lineage(satellite_id, "OUTBOUND", max_depth)
        
        family_info = detect_satellite_family(root.get("canonical", {}).get("name", ""))
        
        return {
            "root": {
                "_id": root["_id"],
                "identifier": root.get("identifier"),
                "name": root.get("canonical", {}).get("name"),
                "family": family_info[0] if family_info else None,
                "generation": family_info[2] if family_info else None
            },
            "ancestors": ancestors,
            "descendants": descendants,
            "stats": {
                "total_ancestors": len(ancestors),
                "total_descendants": len(descendants),
                "max_depth": max_depth,
                "direction": direction
            }
        }
        
    except Exception as e:
        print(f"Error getting satellite lineage: {e}")
        return {
            "root": None,
            "ancestors": [],
            "descendants": [],
            "error": str(e)
        }


def _traverse_lineage(
    start_id: str,
    direction: str,
    max_depth: int
) -> List[Dict[str, Any]]:
    """
    Internal function to traverse lineage in a specific direction.
    
    Args:
        start_id: Starting satellite ID
        direction: "INBOUND" or "OUTBOUND"
        max_depth: Maximum traversal depth
    
    Returns:
        List of related satellites with edge information
    """
    try:
        query = f"""
        FOR v, e, p IN 1..@max_depth {direction} @start_id
            {EDGE_COLLECTION_SATELLITE_LINEAGE}
            RETURN {{
                satellite: {{
                    _id: v._id,
                    identifier: v.identifier,
                    name: v.canonical.name,
                    manufacturer: v.canonical.manufacturer,
                    launch_date: v.canonical.date_of_launch
                }},
                edge: {{
                    relationship_type: e.relationship_type,
                    family_name: e.family_name,
                    generation_from: e.generation_from,
                    generation_to: e.generation_to,
                    generation_gap: e.generation_gap
                }},
                depth: LENGTH(p.vertices) - 1
            }}
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={
                "start_id": start_id,
                "max_depth": max_depth
            }
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error traversing lineage: {e}")
        return []


def get_lineage_statistics() -> Dict[str, Any]:
    """
    Get statistics about satellite lineage relationships.
    
    Returns:
        Dictionary with lineage statistics
    """
    try:
        query = f"""
        LET edges = (
            FOR edge IN {EDGE_COLLECTION_SATELLITE_LINEAGE}
                RETURN edge
        )
        
        LET family_counts = (
            FOR edge IN edges
                COLLECT family = edge.family_name WITH COUNT INTO count
                SORT count DESC
                RETURN {{family: family, edge_count: count}}
        )
        
        LET generation_gaps = (
            FOR edge IN edges
                COLLECT gap = edge.generation_gap WITH COUNT INTO count
                SORT gap
                RETURN {{generation_gap: gap, count: count}}
        )
        
        LET avg_gap = AVERAGE(edges[*].generation_gap)
        LET max_gap = MAX(edges[*].generation_gap)
        
        RETURN {{
            total_edges: LENGTH(edges),
            families: family_counts,
            generation_gap_distribution: generation_gaps,
            gap_stats: {{
                average: avg_gap,
                maximum: max_gap
            }}
        }}
        """
        
        cursor = db.aql.execute(query)
        results = list(cursor)
        return results[0] if results else {}
        
    except Exception as e:
        print(f"Error calculating lineage statistics: {e}")
        return {}


def get_satellite_family_tree(family_name: str, limit: int = 100) -> Dict[str, Any]:
    """
    Get complete family tree for a satellite family.
    
    Args:
        family_name: Family name (e.g., "GPS", "IRIDIUM")
        limit: Maximum number of nodes
    
    Returns:
        Dictionary with nodes and edges for family tree visualization
    """
    try:
        query = f"""
        LET family_edges = (
            FOR edge IN {EDGE_COLLECTION_SATELLITE_LINEAGE}
                FILTER edge.family_name == @family_name
                RETURN edge
        )
        
        LET satellite_ids = UNIQUE(FLATTEN(
            FOR edge IN family_edges
                RETURN [edge._from, edge._to]
        ))
        
        LET satellites = (
            FOR sat_id IN satellite_ids
                LIMIT @limit
                LET sat = DOCUMENT(sat_id)
                RETURN {{
                    id: sat._id,
                    key: sat._key,
                    identifier: sat.identifier,
                    name: sat.canonical.name,
                    manufacturer: sat.canonical.manufacturer,
                    launch_date: sat.canonical.date_of_launch,
                    orbital_band: sat.canonical.orbital_band
                }}
        )
        
        LET formatted_edges = (
            FOR edge IN family_edges
                RETURN {{
                    id: edge._key,
                    source: edge._from,
                    target: edge._to,
                    relationship_type: edge.relationship_type,
                    generation_from: edge.generation_from,
                    generation_to: edge.generation_to,
                    generation_gap: edge.generation_gap
                }}
        )
        
        RETURN {{
            family_name: @family_name,
            nodes: satellites,
            edges: formatted_edges,
            stats: {{
                total_satellites: LENGTH(satellites),
                total_edges: LENGTH(formatted_edges)
            }}
        }}
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={
                "family_name": family_name.upper(),
                "limit": limit
            }
        )
        
        results = list(cursor)
        return results[0] if results else {
            "family_name": family_name,
            "nodes": [],
            "edges": [],
            "stats": {"total_satellites": 0, "total_edges": 0}
        }
        
    except Exception as e:
        print(f"Error building family tree: {e}")
        return {
            "family_name": family_name,
            "nodes": [],
            "edges": [],
            "stats": {"total_satellites": 0, "total_edges": 0},
            "error": str(e)
        }
