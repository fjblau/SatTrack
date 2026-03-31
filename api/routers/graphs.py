from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from datetime import datetime, timezone
import hashlib
import json

import database.connection as db_conn
from database import (
    COLLECTION_NAME,
    COLLECTION_REG_DOCS,
    EDGE_COLLECTION_CONSTELLATION,
    EDGE_COLLECTION_REGISTRATION,
    EDGE_COLLECTION_PROXIMITY,
    GRAPH_NAME,
    find_satellite
)
from database.graph_analytics import (
    find_shortest_path,
    find_all_paths,
    calculate_degree_centrality,
    calculate_betweenness_centrality,
    calculate_closeness_centrality,
    get_collision_risk_neighbors,
    analyze_collision_clusters,
    find_cross_constellation_proximity,
    find_country_cooperation_network,
    find_function_based_clusters,
    detect_communities,
    get_graph_snapshot_by_date,
    calculate_graph_evolution_timeline,
    get_temporal_network_metrics,
    get_similar_satellites,
    get_neighbor_based_recommendations,
    get_collaborative_filtering_recommendations
)
from database.observation_graph_ops import (
    get_source_reliability_network,
    get_temporal_chain,
    get_anomaly_correlation_network,
    get_observation_graph_stats,
    populate_all_observation_edges,
)
from api.services.cache_service import get_cache
from api.services import collision_service, lineage_service

router = APIRouter(prefix="/v2/graphs", tags=["graphs"])


def _resolve_satellite_doc_id(input_id: str) -> Optional[str]:
    """
    Resolve a user-supplied satellite identifier to a full ArangoDB document ID.

    Accepts:
    - Bare NORAD numbers: "39634"
    - NORAD-prefixed: "NORAD-39634"
    - Full document IDs: "satellites/NORAD-39634"
    - International designators, registration numbers, or identifiers

    Returns the full document ID (e.g. "satellites/NORAD-39634") or None.
    """
    stripped = input_id.strip()

    if stripped.startswith("satellites/"):
        key = stripped[len("satellites/"):]
    else:
        key = stripped

    doc = (
        find_satellite(identifier=key)
        or find_satellite(identifier=f"NORAD-{key}")
        or find_satellite(international_designator=key)
        or find_satellite(registration_number=key)
    )

    if doc:
        return doc["_id"]

    # Try resolving as a bare NORAD catalog number
    if key.isdigit():
        import database as db_module
        if db_module.db:
            cursor = db_module.db.aql.execute(
                "FOR s IN satellites FILTER s.canonical.norad_cat_id == @norad LIMIT 1 RETURN s",
                bind_vars={"norad": int(key)},
            )
            sat = next(cursor, None)
            if sat:
                return sat["_id"]

    return None


# Optimized cache configurations based on query patterns and update frequencies
# Path queries: frequently requested, relatively stable - increased capacity
path_cache = get_cache("path_queries", ttl=3600, max_size=2000)

# Centrality: expensive to compute, moderately stable - reduced TTL for freshness
centrality_cache = get_cache("centrality_queries", ttl=43200, max_size=500)

# Community detection: expensive, fairly stable - keep long TTL
community_cache = get_cache("community_queries", ttl=43200, max_size=300)

# Evolution: very stable temporal data - long TTL, small cache
evolution_cache = get_cache("evolution_queries", ttl=86400, max_size=150)

# Recommendations: moderately expensive, should be fresh - shorter TTL
recommendation_cache = get_cache("recommendation_queries", ttl=3600, max_size=750)

# Collision risks: expensive to compute, moderately dynamic - new cache
collision_cache = get_cache("collision_queries", ttl=7200, max_size=400)

# Cross-domain queries: complex multi-edge traversals - new cache
cross_domain_cache = get_cache("cross_domain_queries", ttl=14400, max_size=300)


@router.get("/constellation/{constellation_name}")
def get_constellation_graph(
    constellation_name: str,
    limit: Optional[int] = Query(default=None, description="Limit number of satellites returned")
):
    """
    Get constellation membership graph for a specific constellation.
    
    Returns nodes (satellites) and edges (constellation membership) in graph format.
    Uses star topology where all satellites connect to a constellation hub.
    """
    query = f"""
    LET hub = FIRST(
        FOR edge IN {EDGE_COLLECTION_CONSTELLATION}
            FILTER edge.constellation_name == @constellation_name
            LIMIT 1
            RETURN edge._to
    )
    
    LET members = (
        FOR v, e IN 1..1 INBOUND hub
        {EDGE_COLLECTION_CONSTELLATION}
        FILTER e.constellation_name == @constellation_name
        FILTER v != null
        {f"LIMIT {limit}" if limit else ""}
        RETURN {{
            id: v._id,
            key: v._key,
            identifier: v.identifier,
            name: v.canonical.name,
            country: v.canonical.country_of_origin,
            orbital_band: v.canonical.orbital_band,
            status: v.canonical.status,
            launch_date: v.canonical.date_of_launch,
            is_hub: false
        }}
    )
    
    LET hub_doc = hub ? DOCUMENT(hub) : null
    
    LET hub_node = hub_doc ? {{
        id: hub_doc._id,
        key: hub_doc._key,
        identifier: hub_doc.identifier,
        name: hub_doc.canonical.name,
        country: hub_doc.canonical.country_of_origin,
        orbital_band: hub_doc.canonical.orbital_band,
        status: hub_doc.canonical.status,
        launch_date: hub_doc.canonical.date_of_launch,
        is_hub: true
    }} : null
    
    LET edges = (
        FOR v IN members
            RETURN {{
                id: CONCAT(v.id, "_to_hub"),
                source: v.id,
                target: hub,
                constellation: @constellation_name,
                relationship: "member_to_hub"
            }}
    )
    
    RETURN {{
        constellation: @constellation_name,
        hub: hub_node,
        nodes: hub_node ? APPEND(members, [hub_node]) : members,
        edges: edges,
        stats: {{
            total_satellites: hub_node ? LENGTH(members) + 1 : LENGTH(members),
            members: LENGTH(members),
            has_hub: hub_node != null
        }}
    }}
    """
    
    cursor = db_conn.db.aql.execute(
        query,
        bind_vars={'constellation_name': constellation_name}
    )
    
    results = list(cursor)
    
    if results and results[0]['nodes']:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "constellation": constellation_name,
                "hub": None,
                "nodes": [],
                "edges": [],
                "stats": {
                    "total_satellites": 0,
                    "members": 0,
                    "has_hub": False
                }
            },
            "message": f"No satellites found for constellation '{constellation_name}'",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/satellite/{satellite_id}/neighborhood")
def get_satellite_neighborhood(
    satellite_id: str,
    depth: int = Query(default=2, ge=1, le=3, description="Traversal depth (1-3 hops)"),
    limit: int = Query(default=100, ge=1, le=500, description="Maximum total nodes to return"),
    edge_types: Optional[List[str]] = Query(
        default=None,
        description="Edge types to traverse (orbital_proximity, constellation_membership, registration_links)"
    )
):
    """
    Get the local neighborhood graph around a satellite.
    
    Returns all satellites within N hops of the source satellite, where N is the depth parameter.
    Useful for exploring local network structure and finding related satellites.
    
    Parameters:
        satellite_id: Source satellite identifier (e.g., "NORAD-44714")
        depth: Number of hops to traverse (1-3, default: 2)
        limit: Maximum total nodes to return (1-500, default: 100)
        edge_types: Optional list of edge collections to traverse
    
    Returns:
        Network graph with nodes and edges representing the satellite's neighborhood.
    
    Example:
        GET /v2/graphs/satellite/NORAD-44714/neighborhood?depth=2&limit=100
    """
    try:
        # Build full document ID
        full_id = f"{COLLECTION_NAME}/{satellite_id}"
        
        # Determine edge collections
        if edge_types:
            edge_collections = []
            mapping = {
                'orbital_proximity': EDGE_COLLECTION_PROXIMITY,
                'constellation_membership': EDGE_COLLECTION_CONSTELLATION,
                'registration_links': EDGE_COLLECTION_REGISTRATION
            }
            for et in edge_types:
                if et in mapping:
                    edge_collections.append(mapping[et])
        else:
            # Default: use all edge types
            edge_collections = [
                EDGE_COLLECTION_PROXIMITY,
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION
            ]
        
        edge_clause = ", ".join(edge_collections)
        
        query = f"""
        LET source = DOCUMENT(@source_id)
        
        LET neighbors = (
            FOR v, e, p IN 1..@depth ANY @source_id {edge_clause}
                OPTIONS {{uniqueVertices: "global", bfs: true}}
                FILTER v != null
                LIMIT @limit
                RETURN {{
                    vertex: v,
                    edge: e,
                    path_length: LENGTH(p.edges)
                }}
        )
        
        LET nodes = APPEND(
            [{{
                id: source._id,
                key: source._key,
                type: "satellite",
                identifier: source.identifier,
                name: source.canonical.name,
                country: source.canonical.country_of_origin,
                orbital_band: source.canonical.orbital_band,
                status: source.canonical.status,
                launch_date: source.canonical.date_of_launch,
                constellation: source.canonical.constellation,
                is_source: true,
                distance: 0
            }}],
            (
                FOR n IN neighbors
                    LET is_reg_doc = STARTS_WITH(n.vertex._id, "registration_documents/")
                    RETURN is_reg_doc ? {{
                        id: n.vertex._id,
                        key: n.vertex._key,
                        type: "registration_document",
                        name: n.vertex.document_title,
                        url: n.vertex.url,
                        is_source: false,
                        distance: n.path_length
                    }} : {{
                        id: n.vertex._id,
                        key: n.vertex._key,
                        type: "satellite",
                        identifier: n.vertex.identifier,
                        name: n.vertex.canonical.name,
                        country: n.vertex.canonical.country_of_origin,
                        orbital_band: n.vertex.canonical.orbital_band,
                        status: n.vertex.canonical.status,
                        launch_date: n.vertex.canonical.date_of_launch,
                        constellation: n.vertex.canonical.constellation,
                        is_source: false,
                        distance: n.path_length
                    }}
            )
        )
        
        LET edges = (
            FOR n IN neighbors
                RETURN {{
                    id: n.edge._id,
                    source: n.edge._from,
                    target: n.edge._to,
                    type: SPLIT(n.edge._id, "/")[0],
                    constellation: n.edge.constellation_name,
                    proximity_score: n.edge.proximity_score,
                    apogee_diff_km: n.edge.apogee_diff_km,
                    perigee_diff_km: n.edge.perigee_diff_km,
                    inclination_diff_degrees: n.edge.inclination_diff_degrees
                }}
        )
        
        RETURN {{
            source_satellite: {{
                id: source._id,
                identifier: source.identifier,
                name: source.canonical.name
            }},
            nodes: nodes,
            edges: edges,
            stats: {{
                total_nodes: LENGTH(nodes),
                total_edges: LENGTH(edges),
                depth: @depth,
                edge_types_used: @edge_types
            }}
        }}
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={
                'source_id': full_id,
                'depth': depth,
                'limit': limit,
                'edge_types': edge_types or ['all']
            }
        )
        
        results = list(cursor)
        
        if results and results[0]['nodes']:
            return {
                "data": results[0],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Satellite '{satellite_id}' not found or has no neighbors"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving neighborhood: {str(e)}"
        )


@router.get("/observations/neighborhood")
def get_observations_neighborhood(
    satellite_id: str = Query(..., description="Satellite identifier (NORAD ID, ID, etc.)"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum observations to return")
):
    """
    Get the observations neighborhood graph for a satellite.
    
    Returns a graph structure containing the satellite, its observations, and the sources of those observations.
    Compatible with GraphViewer.jsx.
    """
    try:
        # Resolve satellite document ID
        full_id = _resolve_satellite_doc_id(satellite_id)
        if not full_id:
            raise HTTPException(
                status_code=404,
                detail=f"Satellite '{satellite_id}' not found"
            )

        query = """
        LET sat = DOCUMENT(@source_id)
        FILTER sat != null

        LET observations = (
            FOR obs IN observations
            FILTER obs.norad_id == sat.canonical.norad_cat_id
            SORT obs.observation_epoch DESC
            LIMIT @limit
            RETURN obs
        )

        LET source_nodes = (
            FOR obs IN observations
            COLLECT source_name = obs.source
            RETURN {
                id: CONCAT('source/', MD5(source_name)),
                name: source_name,
                type: 'source',
                node_role: 'source',
                background_color: '#e67e22'
            }
        )

        LET observation_nodes = (
            FOR obs IN observations
            RETURN {
                id: obs._id,
                key: obs._key,
                type: 'observation',
                name: obs.observation_epoch,
                epoch: obs.observation_epoch,
                health_score: obs.derived_health_score,
                source: obs.source,
                background_color: '#3498db'
            }
        )

        LET satellite_node = {
            id: sat._id,
            key: sat._key,
            type: 'satellite',
            name: sat.canonical.name,
            identifier: sat.identifier,
            norad_id: sat.canonical.norad_cat_id,
            is_source: true,
            background_color: '#2ecc71'
        }

        LET edges = APPEND(
            (FOR obs IN observations
                RETURN {
                    id: CONCAT('edge/sat_obs/', obs._key),
                    source: sat._id,
                    target: obs._id,
                    type: 'observed_by',
                    relationship_type: 'observation'
                }),
            (FOR obs IN observations
                RETURN {
                    id: CONCAT('edge/obs_src/', obs._key),
                    source: obs._id,
                    target: CONCAT('source/', MD5(obs.source)),
                    type: 'reported_by',
                    relationship_type: 'reporting'
                })
        )

        RETURN {
            source_satellite: {
                id: sat._id,
                identifier: sat.identifier,
                name: sat.canonical.name
            },
            nodes: APPEND(APPEND(observation_nodes, source_nodes), [satellite_node]),
            edges: edges,
            stats: {
                total_nodes: LENGTH(observation_nodes) + LENGTH(source_nodes) + 1,
                total_edges: LENGTH(edges),
                observation_count: LENGTH(observation_nodes),
                source_count: LENGTH(source_nodes)
            }
        }
        """

        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={
                'source_id': full_id,
                'limit': limit
            }
        )

        results = list(cursor)

        if results and results[0]['nodes']:
            return {
                "data": results[0],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            return {
                "data": {
                    "nodes": [],
                    "edges": [],
                    "stats": {
                        "total_nodes": 0,
                        "total_edges": 0,
                        "observation_count": 0,
                        "source_count": 0
                    }
                },
                "message": f"No observations found for satellite '{satellite_id}'",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving observations neighborhood: {str(e)}"
        )


@router.get("/observations/source-network")
def get_observation_source_network(
    min_observations: int = Query(default=5, ge=1, description="Minimum observations for a source-satellite link"),
    limit: int = Query(default=100, ge=1, le=500, description="Maximum links to return"),
):
    """Source reliability network: sources connected to satellites, weighted by observation count and avg health."""
    try:
        data = get_source_reliability_network(min_observations=min_observations, limit=limit)
        return {
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error building source network: {str(e)}")


@router.get("/observations/temporal-chain")
def get_observation_temporal_chain(
    norad_id: int = Query(..., description="NORAD ID of the satellite"),
    limit: int = Query(default=50, ge=1, le=500, description="Maximum edges to return"),
):
    """Temporal observation chain for a satellite — sequential observations linked over time."""
    try:
        data = get_temporal_chain(norad_id=norad_id, limit=limit)
        return {
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error building temporal chain: {str(e)}")


@router.get("/observations/anomaly-correlation")
def get_observation_anomaly_correlation(
    limit: int = Query(default=100, ge=1, le=500, description="Maximum edges to return"),
):
    """Anomaly co-occurrence network — satellites linked by simultaneous anomalies."""
    try:
        data = get_anomaly_correlation_network(limit=limit)
        return {
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error building anomaly correlation network: {str(e)}")


@router.get("/observations/graph-stats")
def get_obs_graph_stats():
    """Return counts for all observation graph edge collections."""
    try:
        stats = get_observation_graph_stats()
        return {
            "data": stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving observation graph stats: {str(e)}")


@router.post("/observations/populate-edges")
def populate_observation_edges_endpoint(
    time_window_hours: int = Query(default=24, ge=1, le=168, description="Time window for anomaly correlation (hours)"),
    request: object = None,
):
    """Populate all observation edge collections (admin only). Run this after bulk importing observations."""
    try:
        results = populate_all_observation_edges(time_window_hours=time_window_hours)
        return {
            "data": results,
            "message": "Observation edges populated successfully",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error populating observation edges: {str(e)}")


@router.get("/registration-document/{doc_key}")
def get_registration_document_graph(
    doc_key: str,
    limit: Optional[int] = Query(default=None, description="Limit number of satellites returned")
):
    """
    Get satellites linked to a specific registration document.
    
    Returns nodes (satellites + registration document) and edges in graph format.
    """
    doc_id = f"{COLLECTION_REG_DOCS}/{doc_key}"
    
    limit_clause = f"LIMIT {limit}" if limit else ""
    
    query = f"""
    LET reg_doc = DOCUMENT(@doc_id)
    
    LET satellites = reg_doc ? (
        FOR v, e IN 1..1 INBOUND @doc_id
        {EDGE_COLLECTION_REGISTRATION}
        FILTER v != null
        {limit_clause}
        RETURN {{
            id: v._id,
            key: v._key,
            identifier: v.identifier,
            name: v.canonical.name,
            country: v.canonical.country_of_origin,
            orbital_band: v.canonical.orbital_band,
            status: v.canonical.status,
            registration_number: v.canonical.registration_number
        }}
    ) : []
    
    LET reg_doc_node = reg_doc ? {{
        id: reg_doc._id,
        key: reg_doc._key,
        url: reg_doc.url,
        satellite_count: reg_doc.satellite_count,
        countries: reg_doc.countries,
        type: "registration_document"
    }} : null
    
    LET edges = (
        FOR sat IN satellites
            RETURN {{
                id: CONCAT(sat.id, "_to_", reg_doc._id),
                source: sat.id,
                target: reg_doc._id,
                relationship: "registered_in"
            }}
    )
    
    RETURN {{
        registration_document: reg_doc_node,
        nodes: reg_doc_node ? APPEND(satellites, [reg_doc_node]) : satellites,
        edges: edges,
        stats: {{
            total_nodes: reg_doc_node ? LENGTH(satellites) + 1 : LENGTH(satellites),
            satellites: LENGTH(satellites),
            has_document: reg_doc_node != null
        }}
    }}
    """
    
    cursor = db_conn.db.aql.execute(
        query,
        bind_vars={'doc_id': doc_id}
    )
    
    results = list(cursor)
    
    if results and results[0]['registration_document']:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "registration_document": None,
                "nodes": [],
                "edges": [],
                "stats": {
                    "total_nodes": 0,
                    "satellites": 0,
                    "has_document": False
                }
            },
            "message": f"Registration document not found: {doc_key}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/stats")
def get_graph_stats():
    """
    Get overall graph statistics including node and edge counts.
    """
    query = f"""
    LET satellite_count = LENGTH({COLLECTION_NAME})
    LET reg_doc_count = LENGTH({COLLECTION_REG_DOCS})
    LET constellation_edges = LENGTH({EDGE_COLLECTION_CONSTELLATION})
    LET registration_edges = LENGTH({EDGE_COLLECTION_REGISTRATION})
    LET proximity_edges = LENGTH({EDGE_COLLECTION_PROXIMITY})
    
    LET constellations = (
        FOR edge IN {EDGE_COLLECTION_CONSTELLATION}
            COLLECT constellation = edge.constellation_name WITH COUNT INTO count
            SORT count DESC
            RETURN {{
                name: constellation,
                member_count: count
            }}
    )
    
    LET top_reg_docs = (
        FOR doc IN {COLLECTION_REG_DOCS}
            SORT doc.satellite_count DESC
            LIMIT 10
            RETURN {{
                key: doc._key,
                url: doc.url,
                satellite_count: doc.satellite_count,
                countries: doc.countries
            }}
    )
    
    LET proximity_by_band = (
        FOR edge IN {EDGE_COLLECTION_PROXIMITY}
            COLLECT band = edge.orbital_band WITH COUNT INTO count
            SORT count DESC
            RETURN {{
                orbital_band: band,
                edge_count: count
            }}
    )
    
    LET launches_by_year = (
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.canonical.date_of_launch != null
            LET year = TO_NUMBER(SUBSTRING(doc.canonical.date_of_launch, 0, 4))
            COLLECT launch_year = year WITH COUNT INTO sat_count
            SORT launch_year DESC
            LIMIT 10
            RETURN {{
                year: launch_year,
                satellite_count: sat_count
            }}
    )
    
    RETURN {{
        nodes: {{
            satellites: satellite_count,
            registration_documents: reg_doc_count,
            total: satellite_count + reg_doc_count
        }},
        edges: {{
            constellation_membership: constellation_edges,
            registration_links: registration_edges,
            orbital_proximity: proximity_edges,
            total: constellation_edges + registration_edges + proximity_edges
        }},
        constellations: constellations,
        top_registration_documents: top_reg_docs,
        proximity_by_orbital_band: proximity_by_band,
        recent_launch_years: launches_by_year,
        graph_name: '{GRAPH_NAME}',
        collections: {{
            satellites: '{COLLECTION_NAME}',
            registration_documents: '{COLLECTION_REG_DOCS}',
            constellation_edges: '{EDGE_COLLECTION_CONSTELLATION}',
            registration_edges: '{EDGE_COLLECTION_REGISTRATION}',
            proximity_edges: '{EDGE_COLLECTION_PROXIMITY}'
        }}
    }}
    """
    
    cursor = db_conn.db.aql.execute(query)
    results = list(cursor)
    
    return {
        "data": results[0] if results else {},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }



@router.get("/orbital-proximity/{orbital_band}")
def get_orbital_proximity_graph(
    orbital_band: str,
    limit: Optional[int] = Query(default=50, description="Limit number of satellites returned")
):
    """
    Get orbital proximity graph for a specific orbital band.
    
    Returns satellites and their proximity relationships (satellites with similar orbits).
    """
    query = f"""
    LET proximity_edges = (
        FOR edge IN {EDGE_COLLECTION_PROXIMITY}
            FILTER edge.orbital_band == @orbital_band
            LIMIT @limit
            RETURN edge
    )
    
    LET satellite_ids = UNIQUE(FLATTEN(
        FOR edge IN proximity_edges
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
                inclination_degrees: sat.canonical.orbit.inclination_degrees,
                congestion_risk: sat.canonical.congestion_risk
            }}
    )
    
    LET edges = (
        FOR edge IN proximity_edges
            RETURN {{
                id: edge._key,
                source: edge._from,
                target: edge._to,
                proximity_score: edge.proximity_score,
                apogee_diff_km: edge.apogee_diff_km,
                perigee_diff_km: edge.perigee_diff_km,
                inclination_diff_degrees: edge.inclination_diff_degrees
            }}
    )
    
    LET total_proximity_edges = LENGTH(
        FOR edge IN {EDGE_COLLECTION_PROXIMITY}
            FILTER edge.orbital_band == @orbital_band
            RETURN 1
    )
    
    RETURN {{
        orbital_band: @orbital_band,
        nodes: satellites,
        edges: edges,
        stats: {{
            total_satellites: LENGTH(satellites),
            total_proximity_edges: total_proximity_edges,
            edges_shown: LENGTH(edges)
        }}
    }}
    """
    
    cursor = db_conn.db.aql.execute(
        query,
        bind_vars={'orbital_band': orbital_band, 'limit': limit}
    )
    
    results = list(cursor)
    
    if results and results[0]['nodes']:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "orbital_band": orbital_band,
                "nodes": [],
                "edges": [],
                "stats": {
                    "total_satellites": 0,
                    "total_proximity_edges": 0,
                    "edges_shown": 0
                }
            },
            "message": f"No proximity data found for orbital band '{orbital_band}'",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/timeline/filter-options")
def get_timeline_filter_options():
    """
    Get available filter options for timeline view (countries and orbital bands).
    """
    
    query = f"""
    LET countries = (
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.canonical.country != null
            COLLECT country = doc.canonical.country WITH COUNT INTO count
            FILTER count >= 10
            SORT country ASC
            RETURN country
    )
    
    LET orbital_bands = (
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.canonical.orbital_band != null
            COLLECT band = doc.canonical.orbital_band WITH COUNT INTO count
            FILTER count >= 10
            SORT band ASC
            RETURN band
    )
    
    RETURN {{
        countries: countries,
        orbital_bands: orbital_bands
    }}
    """
    
    cursor = db_conn.db.aql.execute(query)
    results = list(cursor)
    
    if results:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "countries": [],
                "orbital_bands": []
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/timeline/yearly")
def get_yearly_launch_data_filtered(
    country: Optional[str] = Query(default=None, description="Filter by country"),
    orbital_band: Optional[str] = Query(default=None, description="Filter by orbital band")
):
    """
    Get yearly launch data with optional filters.
    Returns satellite counts grouped by year.
    """
    
    filters = []
    bind_vars = {}
    
    if country:
        filters.append("doc.canonical.country == @country")
        bind_vars['country'] = country
    
    if orbital_band:
        filters.append("doc.canonical.orbital_band == @orbital_band")
        bind_vars['orbital_band'] = orbital_band
    
    filter_clause = " AND ".join(filters) if filters else "true"
    
    query = f"""
    FOR doc IN {COLLECTION_NAME}
        FILTER doc.canonical.date_of_launch != null
        FILTER {filter_clause}
        LET launch_year = TO_NUMBER(SUBSTRING(doc.canonical.date_of_launch, 0, 4))
        FILTER launch_year != null AND launch_year >= 1957
        COLLECT year = launch_year WITH COUNT INTO sat_count
        SORT year ASC
        RETURN {{
            year: year,
            satellite_count: sat_count
        }}
    """
    
    cursor = db_conn.db.aql.execute(query, bind_vars=bind_vars)
    results = list(cursor)
    
    return {
        "data": {
            "recent_launch_years": results
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/launch-timeline/monthly/{year}")
def get_monthly_launch_data(
    year: int,
    country: Optional[str] = Query(default=None, description="Filter by country"),
    orbital_band: Optional[str] = Query(default=None, description="Filter by orbital band")
):
    """
    Get monthly launch data for a specific year with optional filters.
    Returns satellite counts grouped by month.
    """
    
    filters = []
    bind_vars = {'year': year}
    
    if country:
        filters.append("doc.canonical.country == @country")
        bind_vars['country'] = country
    
    if orbital_band:
        filters.append("doc.canonical.orbital_band == @orbital_band")
        bind_vars['orbital_band'] = orbital_band
    
    filter_clause = " AND ".join(filters) if filters else "true"
    
    query = f"""
    FOR doc IN {COLLECTION_NAME}
        FILTER doc.canonical.date_of_launch != null
        FILTER {filter_clause}
        LET launch_year = TO_NUMBER(SUBSTRING(doc.canonical.date_of_launch, 0, 4))
        FILTER launch_year == @year
        LET launch_month = TO_NUMBER(SUBSTRING(doc.canonical.date_of_launch, 5, 2))
        COLLECT month = launch_month WITH COUNT INTO sat_count
        SORT month ASC
        RETURN {{
            month: month,
            satellite_count: sat_count
        }}
    """
    
    cursor = db_conn.db.aql.execute(query, bind_vars=bind_vars)
    results = list(cursor)
    
    return {
        "data": {
            "year": year,
            "monthly_data": results,
            "total_satellites": sum(r['satellite_count'] for r in results)
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/launch-timeline/breakdown/{year}")
def get_launch_timeline_breakdown(
    year: int,
    country: Optional[str] = Query(default=None, description="Filter by country"),
    orbital_band: Optional[str] = Query(default=None, description="Filter by orbital band")
):
    """
    Get breakdown statistics for a specific year including:
    - Orbital band distribution
    - Country distribution  
    - Constellation distribution
    """
    
    filters = []
    bind_vars = {'year': year}
    
    if country:
        filters.append("sat.canonical.country == @country")
        bind_vars['country'] = country
    
    if orbital_band:
        filters.append("sat.canonical.orbital_band == @orbital_band")
        bind_vars['orbital_band'] = orbital_band
    
    filter_clause = " AND ".join(filters) if filters else "true"
    
    query = f"""
    LET year_satellites = (
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.canonical.date_of_launch != null
            LET sat_year = TO_NUMBER(SUBSTRING(doc.canonical.date_of_launch, 0, 4))
            FILTER sat_year == @year
            RETURN doc
    )
    
    LET filtered_satellites = (
        FOR sat IN year_satellites
            FILTER {filter_clause}
            RETURN sat
    )
    
    LET by_orbital_band = (
        FOR sat IN filtered_satellites
            COLLECT band = sat.canonical.orbital_band WITH COUNT INTO band_count
            SORT band_count DESC
            RETURN {{orbital_band: band, count: band_count}}
    )
    
    LET by_country = (
        FOR sat IN filtered_satellites
            COLLECT country = sat.canonical.country WITH COUNT INTO country_count
            SORT country_count DESC
            LIMIT 10
            RETURN {{country: country, count: country_count}}
    )
    
    LET by_constellation = (
        FOR sat IN filtered_satellites
            FILTER sat.canonical.constellation != null
            COLLECT constellation = sat.canonical.constellation WITH COUNT INTO const_count
            SORT const_count DESC
            LIMIT 10
            RETURN {{constellation: constellation, count: const_count}}
    )
    
    RETURN {{
        year: @year,
        total_satellites: LENGTH(filtered_satellites),
        by_orbital_band: by_orbital_band,
        by_country: by_country,
        by_constellation: by_constellation
    }}
    """
    
    cursor = db_conn.db.aql.execute(query, bind_vars=bind_vars)
    results = list(cursor)
    
    if results:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "year": year,
                "total_satellites": 0,
                "by_orbital_band": [],
                "by_country": [],
                "by_constellation": []
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/launch-timeline/breakdown/monthly/{year}/{month}")
def get_monthly_launch_breakdown(
    year: int,
    month: int,
    country: Optional[str] = Query(default=None, description="Filter by country"),
    orbital_band: Optional[str] = Query(default=None, description="Filter by orbital band")
):
    """
    Get breakdown statistics for a specific month including:
    - Orbital band distribution
    - Country distribution  
    - Constellation distribution
    """
    
    filters = []
    bind_vars = {'year': year, 'month': month}
    
    if country:
        filters.append("sat.canonical.country == @country")
        bind_vars['country'] = country
    
    if orbital_band:
        filters.append("sat.canonical.orbital_band == @orbital_band")
        bind_vars['orbital_band'] = orbital_band
    
    filter_clause = " AND ".join(filters) if filters else "true"
    
    query = f"""
    LET month_satellites = (
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.canonical.date_of_launch != null
            LET sat_year = TO_NUMBER(SUBSTRING(doc.canonical.date_of_launch, 0, 4))
            LET sat_month = TO_NUMBER(SUBSTRING(doc.canonical.date_of_launch, 5, 2))
            FILTER sat_year == @year AND sat_month == @month
            RETURN doc
    )
    
    LET filtered_satellites = (
        FOR sat IN month_satellites
            FILTER {filter_clause}
            RETURN sat
    )
    
    LET by_orbital_band = (
        FOR sat IN filtered_satellites
            COLLECT band = sat.canonical.orbital_band WITH COUNT INTO band_count
            SORT band_count DESC
            RETURN {{orbital_band: band, count: band_count}}
    )
    
    LET by_country = (
        FOR sat IN filtered_satellites
            COLLECT country = sat.canonical.country WITH COUNT INTO country_count
            SORT country_count DESC
            LIMIT 10
            RETURN {{country: country, count: country_count}}
    )
    
    LET by_constellation = (
        FOR sat IN filtered_satellites
            FILTER sat.canonical.constellation != null
            COLLECT constellation = sat.canonical.constellation WITH COUNT INTO const_count
            SORT const_count DESC
            LIMIT 10
            RETURN {{constellation: constellation, count: const_count}}
    )
    
    RETURN {{
        year: @year,
        month: @month,
        total_satellites: LENGTH(filtered_satellites),
        by_orbital_band: by_orbital_band,
        by_country: by_country,
        by_constellation: by_constellation
    }}
    """
    
    cursor = db_conn.db.aql.execute(query, bind_vars=bind_vars)
    results = list(cursor)
    
    if results:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "year": year,
                "month": month,
                "total_satellites": 0,
                "by_orbital_band": [],
                "by_country": [],
                "by_constellation": []
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/launch-timeline/{time_period}")
def get_launch_timeline_graph(
    time_period: str,
    limit: Optional[int] = Query(default=50, description="Limit number of satellites returned")
):
    """
    Get launch timeline graph for a specific time period.
    
    Returns satellites grouped by launch time period (year, decade, era).
    Time periods can be specific years (e.g., "2024") or ranges (e.g., "2020-2024").
    """
    
    start_year = None
    end_year = None
    
    if '-' in time_period:
        try:
            parts = time_period.split('-')
            start_year = int(parts[0])
            end_year = int(parts[1])
        except (ValueError, IndexError):
            raise HTTPException(status_code=400, detail=f"Invalid time period format: {time_period}")
    else:
        try:
            start_year = int(time_period)
            end_year = start_year
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid time period format: {time_period}")
    
    query = f"""
    LET satellites_in_period = (
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.canonical.date_of_launch != null
            LET year = TO_NUMBER(SUBSTRING(doc.canonical.date_of_launch, 0, 4))
            FILTER year >= @start_year AND year <= @end_year
            LIMIT @limit
            RETURN {{
                _key: doc._key,
                _id: doc._id,
                identifier: doc.identifier,
                name: doc.canonical.name,
                launch_date: doc.canonical.date_of_launch,
                launch_year: year,
                country: doc.canonical.country,
                constellation: doc.canonical.constellation,
                orbital_band: doc.canonical.orbital_band,
                congestion_risk: doc.canonical.congestion_risk
            }}
    )
    
    LET year_groups = (
        FOR sat IN satellites_in_period
            COLLECT year = sat.launch_year INTO year_sats
            RETURN {{
                year: year,
                satellite_count: LENGTH(year_sats),
                satellites: year_sats[*].sat
            }}
    )
    
    LET total_in_period = LENGTH(
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.canonical.date_of_launch != null
            LET year = TO_NUMBER(SUBSTRING(doc.canonical.date_of_launch, 0, 4))
            FILTER year >= @start_year AND year <= @end_year
            RETURN 1
    )
    
    RETURN {{
        time_period: @time_period,
        start_year: @start_year,
        end_year: @end_year,
        year_groups: year_groups,
        nodes: satellites_in_period,
        stats: {{
            total_in_period: total_in_period,
            satellites_shown: LENGTH(satellites_in_period),
            years_covered: LENGTH(year_groups)
        }}
    }}
    """
    
    cursor = db_conn.db.aql.execute(
        query,
        bind_vars={
            'time_period': time_period,
            'start_year': start_year,
            'end_year': end_year,
            'limit': limit
        }
    )
    
    results = list(cursor)
    
    if results and results[0]['nodes']:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "time_period": time_period,
                "start_year": start_year,
                "end_year": end_year,
                "year_groups": [],
                "nodes": [],
                "stats": {
                    "total_in_period": 0,
                    "satellites_shown": 0,
                    "years_covered": 0
                }
            },
            "message": f"No satellites found for time period '{time_period}'",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/function-similarity")
def get_function_similarity_graph(
    functions: Optional[str] = Query(default=None, description="Comma-separated function categories"),
    orbital_bands: Optional[str] = Query(default=None, description="Comma-separated orbital bands"),
    countries: Optional[str] = Query(default=None, description="Comma-separated countries"),
    top_n: Optional[int] = Query(default=15, description="Number of top clusters to return"),
    view_mode: Optional[str] = Query(default="aggregate", description="View mode: 'aggregate' or 'detailed'"),
    cluster_id: Optional[str] = Query(default=None, description="Specific cluster ID for detailed view")
):
    """
    Get function similarity graph with multi-dimensional clustering.
    
    Returns clusters grouped by (function_category, orbital_band) with real edges only.
    Clusters are ranked by edge count and filtered to show only meaningful connections.
    
    Query Parameters:
    - functions: Filter by function categories (e.g., "Communications,Navigation")
    - orbital_bands: Filter by orbital bands (e.g., "LEO-Polar,MEO")
    - countries: Filter by countries (e.g., "USA,China")
    - top_n: Number of top clusters to return (default: 15)
    - view_mode: 'aggregate' (cluster-level view) or 'detailed' (satellite-level view)
    - cluster_id: Specific cluster to show in detailed view (e.g., "Communications-LEO-Polar")
    
    Function Categories:
    - Communications: satellites for telecommunications
    - Earth Observation: remote sensing, earth resources
    - Scientific Research: space/atmosphere investigation
    - Navigation: GPS, GLONASS, positioning
    - Military-Defense: defense, military assignments
    - Space Station: ISS, Mir supply and operations
    - Technology-Testing: tech demonstration, experimental
    """
    
    # Parse filter parameters
    function_filter = [f.strip() for f in functions.split(",")] if functions else None
    orbital_band_filter = [ob.strip() for ob in orbital_bands.split(",")] if orbital_bands else None
    country_filter = [c.strip() for c in countries.split(",")] if countries else None
    
    # Route to aggregate or detailed view
    if view_mode == "aggregate":
        return _get_function_similarity_aggregate(function_filter, orbital_band_filter, country_filter, top_n)
    elif view_mode == "detailed" and cluster_id:
        return _get_function_similarity_detailed_cluster(cluster_id, function_filter, orbital_band_filter, country_filter)
    else:
        # Default to current behavior for backward compatibility
        return _get_function_similarity_detailed_all(function_filter, orbital_band_filter, country_filter, top_n)


def _get_function_similarity_aggregate(
    function_filter: Optional[List[str]],
    orbital_band_filter: Optional[List[str]],
    country_filter: Optional[List[str]],
    top_n: int
) -> dict:
    """Return aggregate cluster-level view of function similarity."""
    
    query = f"""
    LET satellites_with_function = (
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.canonical.function != null
            FILTER doc.canonical.orbital_band != null
            LET func_lower = LOWER(doc.canonical.function)
            LET category = (
                func_lower LIKE '%communicat%' OR func_lower LIKE '%telecom%' ? 'Communications' :
                func_lower LIKE '%earth%' OR func_lower LIKE '%observation%' OR func_lower LIKE '%remote sens%' OR func_lower LIKE '%resources%' ? 'Earth Observation' :
                func_lower LIKE '%investigation%' OR func_lower LIKE '%scientific%' OR func_lower LIKE '%atmosphere%' OR func_lower LIKE '%space%' ? 'Scientific Research' :
                func_lower LIKE '%navigation%' OR func_lower LIKE '%glonass%' OR func_lower LIKE '%gps%' OR func_lower LIKE '%position%' ? 'Navigation' :
                func_lower LIKE '%defense%' OR func_lower LIKE '%defence%' OR func_lower LIKE '%military%' ? 'Military-Defense' :
                func_lower LIKE '%station%' OR func_lower LIKE '%mir%' OR func_lower LIKE '%iss%' OR func_lower LIKE '%delivery%' ? 'Space Station' :
                func_lower LIKE '%technolog%' OR func_lower LIKE '%experiment%' OR func_lower LIKE '%test%' OR func_lower LIKE '%demonstration%' ? 'Technology-Testing' :
                'Other'
            )
            FILTER @function_filter == null OR category IN @function_filter
            FILTER @orbital_band_filter == null OR doc.canonical.orbital_band IN @orbital_band_filter
            FILTER @country_filter == null OR doc.canonical.country IN @country_filter
            RETURN {{
                _id: doc._id,
                function_category: category,
                country: doc.canonical.country,
                orbital_band: doc.canonical.orbital_band,
                congestion_risk: doc.canonical.congestion_risk,
                constellation: doc.canonical.constellation
            }}
    )
    
    LET clusters_with_metadata = (
        FOR sat IN satellites_with_function
            COLLECT 
                function_cat = sat.function_category,
                orbital_band = sat.orbital_band
            INTO cluster_sats
            LET satellite_ids = cluster_sats[*].sat._id
            LET satellite_count = LENGTH(satellite_ids)
            
            LET constellation_edges = (
                FOR edge IN {EDGE_COLLECTION_CONSTELLATION}
                    FILTER edge._from IN satellite_ids AND edge._to IN satellite_ids
                    RETURN edge
            )
            
            LET proximity_edges = (
                FOR edge IN {EDGE_COLLECTION_PROXIMITY}
                    FILTER edge._from IN satellite_ids AND edge._to IN satellite_ids
                    RETURN edge
            )
            
            LET all_edges = UNION(constellation_edges, proximity_edges)
            LET edge_count = LENGTH(all_edges)
            
            FILTER satellite_count >= 5 AND edge_count >= 10
            
            LET countries = (
                FOR sat IN cluster_sats
                    COLLECT country = sat.sat.country WITH COUNT INTO count
                    SORT count DESC
                    LIMIT 5
                    RETURN {{country: country, count: count}}
            )
            
            LET constellations = (
                FOR sat IN cluster_sats
                    FILTER sat.sat.constellation != null
                    COLLECT constellation = sat.sat.constellation WITH COUNT INTO count
                    SORT count DESC
                    LIMIT 5
                    RETURN {{constellation: constellation, count: count}}
            )
            
            LET congestion_risks = (
                FOR sat IN cluster_sats
                    FILTER sat.sat.congestion_risk != null
                    COLLECT risk = sat.sat.congestion_risk WITH COUNT INTO count
                    RETURN {{risk: risk, count: count}}
            )
            
            LET avg_congestion = (
                LENGTH(congestion_risks) > 0 ? (
                    LENGTH(FOR r IN congestion_risks FILTER r.risk == "critical" RETURN 1) > 0 ? "critical" :
                    LENGTH(FOR r IN congestion_risks FILTER r.risk == "high" RETURN 1) > 0 ? "high" :
                    LENGTH(FOR r IN congestion_risks FILTER r.risk == "medium" RETURN 1) > 0 ? "medium" :
                    "low"
                ) : "unknown"
            )
            
            RETURN {{
                cluster_id: CONCAT(function_cat, '-', orbital_band),
                function: function_cat,
                orbital_band: orbital_band,
                satellite_count: satellite_count,
                edge_count: edge_count,
                density: edge_count / (satellite_count * (satellite_count - 1) / 2),
                satellite_ids: satellite_ids,
                top_countries: countries[*].country,
                top_constellations: constellations[*].constellation,
                avg_congestion_risk: avg_congestion
            }}
    )
    
    LET top_clusters = (
        FOR cluster IN clusters_with_metadata
            SORT cluster.edge_count DESC
            LIMIT @top_n
            RETURN cluster
    )
    
    LET inter_cluster_edges = (
        FOR cluster1 IN top_clusters
            FOR cluster2 IN top_clusters
                FILTER cluster1.cluster_id < cluster2.cluster_id
                
                LET constellation_connections = LENGTH(
                    FOR edge IN {EDGE_COLLECTION_CONSTELLATION}
                        FILTER (edge._from IN cluster1.satellite_ids AND edge._to IN cluster2.satellite_ids) OR
                               (edge._from IN cluster2.satellite_ids AND edge._to IN cluster1.satellite_ids)
                        RETURN edge
                )
                
                LET proximity_connections = LENGTH(
                    FOR edge IN {EDGE_COLLECTION_PROXIMITY}
                        FILTER (edge._from IN cluster1.satellite_ids AND edge._to IN cluster2.satellite_ids) OR
                               (edge._from IN cluster2.satellite_ids AND edge._to IN cluster1.satellite_ids)
                        RETURN edge
                )
                
                LET proximity_edges_detail = (
                    FOR edge IN {EDGE_COLLECTION_PROXIMITY}
                        FILTER (edge._from IN cluster1.satellite_ids AND edge._to IN cluster2.satellite_ids) OR
                               (edge._from IN cluster2.satellite_ids AND edge._to IN cluster1.satellite_ids)
                        RETURN edge.proximity_score
                )
                
                LET total_connections = constellation_connections + proximity_connections
                FILTER total_connections > 0
                
                LET avg_proximity = LENGTH(proximity_edges_detail) > 0 ? AVERAGE(proximity_edges_detail) : null
                
                RETURN {{
                    id: CONCAT(cluster1.cluster_id, '_to_', cluster2.cluster_id),
                    source: cluster1.cluster_id,
                    target: cluster2.cluster_id,
                    connection_count: total_connections,
                    constellation_edges: constellation_connections,
                    proximity_edges: proximity_connections,
                    avg_proximity_score: avg_proximity
                }}
    )
    
    LET cluster_nodes = (
        FOR cluster IN top_clusters
            RETURN {{
                id: cluster.cluster_id,
                type: "cluster",
                function: cluster.function,
                orbital_band: cluster.orbital_band,
                satellite_count: cluster.satellite_count,
                edge_count: cluster.edge_count,
                density: cluster.density,
                top_countries: cluster.top_countries,
                top_constellations: cluster.top_constellations,
                avg_congestion_risk: cluster.avg_congestion_risk
            }}
    )
    
    RETURN {{
        nodes: cluster_nodes,
        edges: inter_cluster_edges,
        stats: {{
            total_satellites: LENGTH(satellites_with_function),
            cluster_count: LENGTH(top_clusters),
            inter_cluster_edges: LENGTH(inter_cluster_edges)
        }}
    }}
    """
    
    bind_vars = {
        'function_filter': function_filter,
        'orbital_band_filter': orbital_band_filter,
        'country_filter': country_filter,
        'top_n': top_n
    }
    
    cursor = db_conn.db.aql.execute(query, bind_vars=bind_vars)
    results = list(cursor)
    
    if results:
        return {
            "data": results[0],
            "view_mode": "aggregate",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "nodes": [],
                "edges": [],
                "stats": {"total_satellites": 0, "cluster_count": 0, "inter_cluster_edges": 0}
            },
            "view_mode": "aggregate",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def _get_function_similarity_detailed_cluster(
    cluster_id: str,
    function_filter: Optional[List[str]],
    orbital_band_filter: Optional[List[str]],
    country_filter: Optional[List[str]]
) -> dict:
    """Return detailed satellite-level view for a specific cluster."""
    
    parts = cluster_id.split('-', 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid cluster_id format. Expected 'Function-OrbitalBand'")
    
    target_function = parts[0]
    target_orbital_band = parts[1]
    
    query = f"""
    LET satellites_in_cluster = (
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.canonical.function != null
            FILTER doc.canonical.orbital_band != null
            LET func_lower = LOWER(doc.canonical.function)
            LET category = (
                func_lower LIKE '%communicat%' OR func_lower LIKE '%telecom%' ? 'Communications' :
                func_lower LIKE '%earth%' OR func_lower LIKE '%observation%' OR func_lower LIKE '%remote sens%' OR func_lower LIKE '%resources%' ? 'Earth Observation' :
                func_lower LIKE '%investigation%' OR func_lower LIKE '%scientific%' OR func_lower LIKE '%atmosphere%' OR func_lower LIKE '%space%' ? 'Scientific Research' :
                func_lower LIKE '%navigation%' OR func_lower LIKE '%glonass%' OR func_lower LIKE '%gps%' OR func_lower LIKE '%position%' ? 'Navigation' :
                func_lower LIKE '%defense%' OR func_lower LIKE '%defence%' OR func_lower LIKE '%military%' ? 'Military-Defense' :
                func_lower LIKE '%station%' OR func_lower LIKE '%mir%' OR func_lower LIKE '%iss%' OR func_lower LIKE '%delivery%' ? 'Space Station' :
                func_lower LIKE '%technolog%' OR func_lower LIKE '%experiment%' OR func_lower LIKE '%test%' OR func_lower LIKE '%demonstration%' ? 'Technology-Testing' :
                'Other'
            )
            FILTER category == @target_function
            FILTER doc.canonical.orbital_band == @target_orbital_band
            FILTER @function_filter == null OR category IN @function_filter
            FILTER @orbital_band_filter == null OR doc.canonical.orbital_band IN @orbital_band_filter
            FILTER @country_filter == null OR doc.canonical.country IN @country_filter
            RETURN {{
                _id: doc._id,
                _key: doc._key,
                identifier: doc.identifier,
                name: doc.canonical.name,
                function: doc.canonical.function,
                function_category: category,
                country: doc.canonical.country,
                launch_date: doc.canonical.date_of_launch,
                orbital_band: doc.canonical.orbital_band,
                congestion_risk: doc.canonical.congestion_risk,
                cluster_id: @cluster_id
            }}
    )
    
    LET satellite_ids = satellites_in_cluster[*]._id
    
    LET constellation_edges = (
        FOR edge IN {EDGE_COLLECTION_CONSTELLATION}
            FILTER edge._from IN satellite_ids AND edge._to IN satellite_ids
            RETURN {{
                id: edge._key,
                source: edge._from,
                target: edge._to,
                relationship_type: 'constellation_membership',
                constellation_name: edge.constellation_name
            }}
    )
    
    LET proximity_edges = (
        FOR edge IN {EDGE_COLLECTION_PROXIMITY}
            FILTER edge._from IN satellite_ids AND edge._to IN satellite_ids
            LIMIT 500
            RETURN {{
                id: edge._key,
                source: edge._from,
                target: edge._to,
                relationship_type: 'orbital_proximity',
                proximity_score: edge.proximity_score,
                orbital_band: edge.orbital_band
            }}
    )
    
    LET edges = UNION(constellation_edges, proximity_edges)
    
    RETURN {{
        cluster_id: @cluster_id,
        nodes: satellites_in_cluster,
        edges: edges,
        stats: {{
            satellite_count: LENGTH(satellites_in_cluster),
            edge_count: LENGTH(edges)
        }}
    }}
    """
    
    bind_vars = {
        'cluster_id': cluster_id,
        'target_function': target_function,
        'target_orbital_band': target_orbital_band,
        'function_filter': function_filter,
        'orbital_band_filter': orbital_band_filter,
        'country_filter': country_filter
    }
    
    cursor = db_conn.db.aql.execute(query, bind_vars=bind_vars)
    results = list(cursor)
    
    if results and results[0]['nodes']:
        return {
            "data": results[0],
            "view_mode": "detailed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "cluster_id": cluster_id,
                "nodes": [],
                "edges": [],
                "stats": {"satellite_count": 0, "edge_count": 0}
            },
            "view_mode": "detailed",
            "message": f"No satellites found in cluster '{cluster_id}'",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def _get_function_similarity_detailed_all(
    function_filter: Optional[List[str]],
    orbital_band_filter: Optional[List[str]],
    country_filter: Optional[List[str]],
    top_n: int
) -> dict:
    """Return detailed satellite-level view for all top clusters (legacy behavior)."""
    
    query = f"""
    LET satellites_with_function = (
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.canonical.function != null
            FILTER doc.canonical.orbital_band != null
            LET func_lower = LOWER(doc.canonical.function)
            LET category = (
                func_lower LIKE '%communicat%' OR func_lower LIKE '%telecom%' ? 'Communications' :
                func_lower LIKE '%earth%' OR func_lower LIKE '%observation%' OR func_lower LIKE '%remote sens%' OR func_lower LIKE '%resources%' ? 'Earth Observation' :
                func_lower LIKE '%investigation%' OR func_lower LIKE '%scientific%' OR func_lower LIKE '%atmosphere%' OR func_lower LIKE '%space%' ? 'Scientific Research' :
                func_lower LIKE '%navigation%' OR func_lower LIKE '%glonass%' OR func_lower LIKE '%gps%' OR func_lower LIKE '%position%' ? 'Navigation' :
                func_lower LIKE '%defense%' OR func_lower LIKE '%defence%' OR func_lower LIKE '%military%' ? 'Military-Defense' :
                func_lower LIKE '%station%' OR func_lower LIKE '%mir%' OR func_lower LIKE '%iss%' OR func_lower LIKE '%delivery%' ? 'Space Station' :
                func_lower LIKE '%technolog%' OR func_lower LIKE '%experiment%' OR func_lower LIKE '%test%' OR func_lower LIKE '%demonstration%' ? 'Technology-Testing' :
                'Other'
            )
            FILTER @function_filter == null OR category IN @function_filter
            FILTER @orbital_band_filter == null OR doc.canonical.orbital_band IN @orbital_band_filter
            FILTER @country_filter == null OR doc.canonical.country IN @country_filter
            RETURN {{
                _id: doc._id,
                _key: doc._key,
                identifier: doc.identifier,
                name: doc.canonical.name,
                function: doc.canonical.function,
                function_category: category,
                country: doc.canonical.country,
                launch_date: doc.canonical.date_of_launch,
                orbital_band: doc.canonical.orbital_band,
                congestion_risk: doc.canonical.congestion_risk
            }}
    )
    
    LET clusters_with_edges = (
        FOR sat IN satellites_with_function
            COLLECT 
                function_cat = sat.function_category,
                orbital_band = sat.orbital_band
            INTO cluster_sats
            LET satellite_ids = cluster_sats[*].sat._id
            LET satellite_count = LENGTH(satellite_ids)
            
            LET constellation_edges = (
                FOR edge IN {EDGE_COLLECTION_CONSTELLATION}
                    FILTER edge._from IN satellite_ids AND edge._to IN satellite_ids
                    RETURN edge
            )
            
            LET proximity_edges = (
                FOR edge IN {EDGE_COLLECTION_PROXIMITY}
                    FILTER edge._from IN satellite_ids AND edge._to IN satellite_ids
                    RETURN edge
            )
            
            LET all_edges = UNION(constellation_edges, proximity_edges)
            LET edge_count = LENGTH(all_edges)
            
            FILTER satellite_count >= 5 AND edge_count >= 10
            
            RETURN {{
                cluster_id: CONCAT(function_cat, '-', orbital_band),
                function: function_cat,
                orbital_band: orbital_band,
                satellite_count: satellite_count,
                edge_count: edge_count,
                density: edge_count / (satellite_count * (satellite_count - 1) / 2),
                satellite_ids: satellite_ids,
                edges: all_edges
            }}
    )
    
    LET top_clusters = (
        FOR cluster IN clusters_with_edges
            SORT cluster.edge_count DESC
            LIMIT @top_n
            RETURN cluster
    )
    
    LET selected_satellite_ids = FLATTEN(top_clusters[*].satellite_ids)
    
    LET selected_satellites = (
        FOR sat IN satellites_with_function
            FILTER sat._id IN selected_satellite_ids
            LET cluster_id = CONCAT(sat.function_category, '-', sat.orbital_band)
            RETURN MERGE(sat, {{ cluster_id: cluster_id }})
    )
    
    LET selected_edges = FLATTEN(
        FOR cluster IN top_clusters
            FOR edge IN cluster.edges
                RETURN {{
                    id: edge._key,
                    source: edge._from,
                    target: edge._to,
                    relationship_type: edge.constellation_name != null ? 'constellation_membership' : 'orbital_proximity',
                    constellation_name: edge.constellation_name,
                    proximity_score: edge.proximity_score,
                    orbital_band: edge.orbital_band
                }}
    )
    
    LET cluster_metadata = (
        FOR cluster IN top_clusters
            RETURN {{
                cluster_id: cluster.cluster_id,
                function: cluster.function,
                orbital_band: cluster.orbital_band,
                satellite_count: cluster.satellite_count,
                edge_count: cluster.edge_count,
                density: cluster.density
            }}
    )
    
    RETURN {{
        clusters: cluster_metadata,
        nodes: selected_satellites,
        edges: selected_edges,
        stats: {{
            total_satellites: LENGTH(satellites_with_function),
            cluster_count: LENGTH(top_clusters),
            nodes_shown: LENGTH(selected_satellites),
            edges_shown: LENGTH(selected_edges)
        }}
    }}
    """
    
    bind_vars = {
        'function_filter': function_filter,
        'orbital_band_filter': orbital_band_filter,
        'country_filter': country_filter,
        'top_n': top_n
    }
    
    cursor = db_conn.db.aql.execute(query, bind_vars=bind_vars)
    results = list(cursor)
    
    if results:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "clusters": [],
                "nodes": [],
                "edges": [],
                "stats": {
                    "total_satellites": 0,
                    "cluster_count": 0,
                    "nodes_shown": 0,
                    "edges_shown": 0
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/function-similarity/category/{category}")
def get_function_category_graph(
    category: str,
    limit: Optional[int] = Query(default=100, description="Limit number of satellites")
):
    """
    Get satellites for a specific function category.
    """
    
    query = f"""
    LET satellites_with_function = (
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.canonical.function != null
            LET func_lower = LOWER(doc.canonical.function)
            LET detected_category = (
                func_lower LIKE '%communicat%' OR func_lower LIKE '%telecom%' ? 'Communications' :
                func_lower LIKE '%earth%' OR func_lower LIKE '%observation%' OR func_lower LIKE '%remote sens%' OR func_lower LIKE '%resources%' ? 'Earth Observation' :
                func_lower LIKE '%investigation%' OR func_lower LIKE '%scientific%' OR func_lower LIKE '%atmosphere%' OR func_lower LIKE '%space%' ? 'Scientific Research' :
                func_lower LIKE '%navigation%' OR func_lower LIKE '%glonass%' OR func_lower LIKE '%gps%' OR func_lower LIKE '%position%' ? 'Navigation' :
                func_lower LIKE '%defense%' OR func_lower LIKE '%defence%' OR func_lower LIKE '%military%' ? 'Military-Defense' :
                func_lower LIKE '%station%' OR func_lower LIKE '%mir%' OR func_lower LIKE '%iss%' OR func_lower LIKE '%delivery%' ? 'Space Station' :
                func_lower LIKE '%technolog%' OR func_lower LIKE '%experiment%' OR func_lower LIKE '%test%' OR func_lower LIKE '%demonstration%' ? 'Technology-Testing' :
                'Other'
            )
            FILTER detected_category == @category
            LIMIT @limit
            RETURN {{
                _id: doc._id,
                _key: doc._key,
                identifier: doc.identifier,
                name: doc.canonical.name,
                function: doc.canonical.function,
                function_category: detected_category,
                country: doc.canonical.country,
                launch_date: doc.canonical.date_of_launch,
                orbital_band: doc.canonical.orbital_band,
                congestion_risk: doc.canonical.congestion_risk,
                norad_cat_id: doc.canonical.norad_cat_id
            }}
    )
    
    LET satellite_ids = satellites_with_function[*]._id
    
    LET constellation_edges = (
        FOR edge IN {EDGE_COLLECTION_CONSTELLATION}
            FILTER edge._from IN satellite_ids AND edge._to IN satellite_ids
            RETURN {{
                id: edge._key,
                source: edge._from,
                target: edge._to,
                relationship_type: 'constellation_membership',
                constellation_name: edge.constellation_name
            }}
    )
    
    LET registration_edges = (
        FOR edge IN {EDGE_COLLECTION_REGISTRATION}
            FILTER (edge._from IN satellite_ids OR edge._to IN satellite_ids)
            RETURN {{
                id: edge._key,
                source: edge._from,
                target: edge._to,
                relationship_type: 'registration_link',
                registration_document: edge.registration_document
            }}
    )
    
    LET proximity_edges = (
        FOR edge IN {EDGE_COLLECTION_PROXIMITY}
            FILTER edge._from IN satellite_ids AND edge._to IN satellite_ids
            LIMIT 300
            RETURN {{
                id: edge._key,
                source: edge._from,
                target: edge._to,
                relationship_type: 'orbital_proximity',
                proximity_score: edge.proximity_score,
                orbital_band: edge.orbital_band
            }}
    )
    
    LET edges = UNION(constellation_edges, registration_edges, proximity_edges)
    
    RETURN {{
        category: @category,
        nodes: satellites_with_function,
        edges: edges,
        stats: {{
            satellites_shown: LENGTH(satellites_with_function),
            edges_shown: LENGTH(edges)
        }}
    }}
    """
    
    cursor = db_conn.db.aql.execute(query, bind_vars={'category': category, 'limit': limit})
    results = list(cursor)
    
    if results:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "category": category,
                "nodes": [],
                "edges": [],
                "stats": {
                    "satellites_shown": 0,
                    "edges_shown": 0
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/country-relations")
def get_country_relations_graph(
    min_satellites: Optional[int] = Query(default=50, description="Minimum satellites per country"),
    limit_countries: Optional[int] = Query(default=10, description="Limit number of countries")
):
    """
    Get country relations graph showing international cooperation and shared interests.
    
    Relationships are based on:
    - Shared registration documents (direct collaboration)
    - Satellites in similar orbital bands (coordination)
    """
    
    query = f"""
    LET countries_with_sats = (
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.canonical.country != null
            COLLECT c = doc.canonical.country WITH COUNT INTO count
            FILTER count >= @min_satellites
            SORT count DESC
            LIMIT @limit_countries
            RETURN {{
                country: c,
                satellite_count: count
            }}
    )
    
    LET country_names = countries_with_sats[*].country
    
    LET by_orbital_band = (
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.canonical.country IN country_names
            FILTER doc.canonical.orbital_band != null
            COLLECT country_name = doc.canonical.country, band = doc.canonical.orbital_band WITH COUNT INTO count
            RETURN {{
                country: country_name,
                orbital_band: band,
                count: count
            }}
    )
    
    LET orbital_edges = (
        FOR b1 IN by_orbital_band
            FOR b2 IN by_orbital_band
                FILTER b1.country < b2.country
                FILTER b1.orbital_band == b2.orbital_band
                FILTER b1.count + b2.count >= 10
                RETURN {{
                    country1: b1.country,
                    country2: b2.country,
                    orbital_band: b1.orbital_band,
                    shared_count: b1.count + b2.count
                }}
    )
    
    LET by_registration_doc = (
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.canonical.country IN country_names
            FILTER doc.canonical.registration_document != null
            COLLECT country_name = doc.canonical.country, reg_doc = doc.canonical.registration_document WITH COUNT INTO count
            RETURN {{
                country: country_name,
                reg_doc: reg_doc,
                count: count
            }}
    )
    
    LET collab_edges = (
        FOR r1 IN by_registration_doc
            FOR r2 IN by_registration_doc
                FILTER r1.country < r2.country
                FILTER r1.reg_doc == r2.reg_doc
                RETURN {{
                    country1: r1.country,
                    country2: r2.country,
                    collaboration_count: r1.count + r2.count
                }}
    )
    
    LET edges = UNION_DISTINCT(
        (FOR edge IN orbital_edges
            RETURN {{
                id: CONCAT(edge.country1, '_', edge.country2, '_', edge.orbital_band),
                source: edge.country1,
                target: edge.country2,
                relationship_type: 'shared_orbital_band',
                orbital_band: edge.orbital_band,
                strength: edge.shared_count,
                weight: edge.shared_count
            }}),
        (FOR edge IN collab_edges
            RETURN {{
                id: CONCAT(edge.country1, '_', edge.country2, '_collab'),
                source: edge.country1,
                target: edge.country2,
                relationship_type: 'collaboration',
                strength: edge.collaboration_count * 10,
                weight: edge.collaboration_count * 10
            }})
    )
    
    RETURN {{
        nodes: countries_with_sats,
        edges: edges,
        stats: {{
            countries_shown: LENGTH(countries_with_sats),
            relationships_found: LENGTH(edges)
        }}
    }}
    """
    
    cursor = db_conn.db.aql.execute(
        query,
        bind_vars={'min_satellites': min_satellites, 'limit_countries': limit_countries}
    )
    results = list(cursor)
    
    if results:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "nodes": [],
                "edges": [],
                "stats": {
                    "countries_shown": 0,
                    "relationships_found": 0
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/paths/{from_id}/{to_id}")
def get_path_between_satellites(
    from_id: str,
    to_id: str,
    max_depth: Optional[int] = Query(default=10, description="Maximum traversal depth", ge=1, le=20),
    edge_types: Optional[List[str]] = Query(default=None, description="Edge collection names to traverse"),
    algorithm: Optional[str] = Query(default="shortest", description="Path finding algorithm: 'shortest' or 'all'")
):
    """
    Find paths between two satellites in the graph.
    
    Args:
        from_id: Source satellite ID (e.g., '2025-206B' or 'satellites/2025-206B')
        to_id: Target satellite ID
        max_depth: Maximum number of hops to search (1-20)
        edge_types: Optional list of edge collections to traverse
        algorithm: 'shortest' for single shortest path, 'all' for all paths up to max_depth
    
    Returns:
        Path information including vertices, edges, and distance
    """
    if not from_id or not to_id:
        raise HTTPException(status_code=400, detail="Both from_id and to_id are required")

    from_doc_id = _resolve_satellite_doc_id(from_id)
    if from_doc_id is None:
        raise HTTPException(
            status_code=404,
            detail=f"Satellite not found: '{from_id}'. Accepted formats: bare NORAD number (39634), NORAD-39634, or full identifier."
        )

    to_doc_id = _resolve_satellite_doc_id(to_id)
    if to_doc_id is None:
        raise HTTPException(
            status_code=404,
            detail=f"Satellite not found: '{to_id}'. Accepted formats: bare NORAD number (39634), NORAD-39634, or full identifier."
        )
    
    cache_key = hashlib.md5(
        json.dumps({
            "from": from_doc_id,
            "to": to_doc_id,
            "max_depth": max_depth,
            "edge_types": sorted(edge_types) if edge_types else None,
            "algorithm": algorithm
        }, sort_keys=True).encode()
    ).hexdigest()
    
    cached_result = path_cache.get(cache_key)
    if cached_result is not None:
        return {
            "data": cached_result,
            "cached": True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    try:
        if algorithm == "shortest":
            result = find_shortest_path(
                from_id=from_doc_id,
                to_id=to_doc_id,
                edge_types=edge_types,
                max_depth=max_depth
            )
            
            if result is None:
                response_data = {
                    "from_id": from_doc_id,
                    "to_id": to_doc_id,
                    "path_found": False,
                    "message": f"No path found between {from_id} and {to_id} within {max_depth} hops"
                }
            else:
                response_data = {
                    "from_id": from_doc_id,
                    "to_id": to_doc_id,
                    "path_found": True,
                    "path": result,
                    "algorithm": "shortest"
                }
        
        elif algorithm == "all":
            paths = find_all_paths(
                from_id=from_doc_id,
                to_id=to_doc_id,
                edge_types=edge_types,
                max_depth=max_depth,
                limit=10
            )
            
            response_data = {
                "from_id": from_doc_id,
                "to_id": to_doc_id,
                "path_found": len(paths) > 0,
                "paths": paths,
                "path_count": len(paths),
                "algorithm": "all"
            }
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid algorithm: {algorithm}. Use 'shortest' or 'all'"
            )
        
        path_cache.set(cache_key, response_data)
        
        return {
            "data": response_data,
            "cached": False,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        if "document not found" in str(e).lower():
            raise HTTPException(
                status_code=404,
                detail=f"One or both satellites not found: {from_id}, {to_id}"
            )
        raise HTTPException(status_code=500, detail=f"Error finding path: {str(e)}")


@router.get("/paths/cache/stats")
def get_path_cache_stats():
    """
    Get statistics about the path query cache.
    
    Returns cache hit rate, size, and other performance metrics.
    """
    stats = path_cache.get_stats()
    return {
        "data": stats,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/analytics/centrality")
def get_centrality_analysis(
    metric: str = Query(
        default="degree",
        description="Centrality metric: 'degree', 'betweenness', or 'closeness'"
    ),
    edge_types: Optional[List[str]] = Query(
        default=None,
        description="Edge collection names to consider"
    ),
    limit: int = Query(
        default=50,
        description="Maximum number of results to return",
        ge=1,
        le=200
    ),
    sample_size: Optional[int] = Query(
        default=100,
        description="Sample size for betweenness calculation (betweenness only)",
        ge=10,
        le=500
    ),
    max_depth: Optional[int] = Query(
        default=5,
        description="Maximum depth for closeness calculation (closeness only)",
        ge=1,
        le=10
    )
):
    """
    Calculate centrality metrics for satellites in the graph.
    
    Centrality metrics identify the most important nodes in the network:
    
    - **degree**: Number of direct connections (fast, good for identifying hubs)
    - **betweenness**: How often a node appears on shortest paths (identifies bridges)
    - **closeness**: How close a node is to all others (identifies nodes with quick access)
    
    Args:
        metric: Centrality metric to calculate
        edge_types: Optional list of edge collections to consider
        limit: Maximum number of results (1-200)
        sample_size: Sample size for betweenness (10-500, betweenness only)
        max_depth: Maximum depth for closeness (1-10, closeness only)
    
    Returns:
        List of satellites with their centrality scores, sorted by score descending
    """
    if metric not in ["degree", "betweenness", "closeness"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric: {metric}. Use 'degree', 'betweenness', or 'closeness'"
        )
    
    cache_key = hashlib.md5(
        json.dumps({
            "metric": metric,
            "edge_types": sorted(edge_types) if edge_types else None,
            "limit": limit,
            "sample_size": sample_size if metric == "betweenness" else None,
            "max_depth": max_depth if metric == "closeness" else None
        }, sort_keys=True).encode()
    ).hexdigest()
    
    cached_result = centrality_cache.get(cache_key)
    if cached_result is not None:
        return {
            "data": cached_result,
            "cached": True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    try:
        if metric == "degree":
            results = calculate_degree_centrality(
                edge_types=edge_types,
                limit=limit
            )
        elif metric == "betweenness":
            results = calculate_betweenness_centrality(
                edge_types=edge_types,
                limit=limit,
                sample_size=sample_size
            )
        elif metric == "closeness":
            results = calculate_closeness_centrality(
                edge_types=edge_types,
                limit=limit,
                max_depth=max_depth
            )
        
        response_data = {
            "metric": metric,
            "satellites": results,
            "count": len(results),
            "parameters": {
                "edge_types": edge_types,
                "limit": limit
            }
        }
        
        if metric == "betweenness":
            response_data["parameters"]["sample_size"] = sample_size
        elif metric == "closeness":
            response_data["parameters"]["max_depth"] = max_depth
        
        centrality_cache.set(cache_key, response_data)
        
        return {
            "data": response_data,
            "cached": False,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating {metric} centrality: {str(e)}"
        )


@router.get("/analytics/centrality/cache/stats")
def get_centrality_cache_stats():
    """
    Get statistics about the centrality query cache.
    
    Returns cache hit rate, size, and other performance metrics.
    """
    stats = centrality_cache.get_stats()
    return {
        "data": stats,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/collision-risks")
def get_collision_risks(
    risk_threshold: Optional[float] = Query(
        default=0.5,
        description="Minimum risk score threshold (0-1)",
        ge=0.0,
        le=1.0
    ),
    orbital_band: Optional[str] = Query(
        default=None,
        description="Filter by orbital band (LEO, MEO, GEO, etc.)"
    ),
    risk_level: Optional[str] = Query(
        default=None,
        description="Filter by risk level (high, medium, low)"
    ),
    limit: int = Query(
        default=100,
        description="Maximum number of edges to return",
        ge=1,
        le=500
    )
):
    """
    Get collision risk edges with filtering.
    
    Returns collision risk relationships between satellites based on:
    - Orbital proximity (apogee, perigee, inclination)
    - Risk scoring (0-1, higher = higher collision risk)
    - Orbital band (LEO, MEO, GEO)
    
    Args:
        risk_threshold: Minimum risk score (0-1)
        orbital_band: Filter by orbital band
        risk_level: Filter by risk level (high, medium, low)
        limit: Maximum number of edges (1-500)
    
    Returns:
        List of collision risk edges with satellite information
    """
    if risk_level and risk_level not in ["high", "medium", "low"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid risk_level: {risk_level}. Use 'high', 'medium', or 'low'"
        )
    
    try:
        results = collision_service.get_collision_risks(
            risk_threshold=risk_threshold,
            orbital_band=orbital_band,
            risk_level=risk_level,
            limit=limit
        )
        
        return {
            "data": {
                "edges": results,
                "count": len(results),
                "parameters": {
                    "risk_threshold": risk_threshold,
                    "orbital_band": orbital_band,
                    "risk_level": risk_level,
                    "limit": limit
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying collision risks: {str(e)}"
        )


@router.get("/collision-risks/{satellite_id}")
def get_collision_risks_for_satellite(
    satellite_id: str,
    risk_threshold: Optional[float] = Query(
        default=0.5,
        description="Minimum risk score threshold (0-1)",
        ge=0.0,
        le=1.0
    ),
    limit: int = Query(
        default=50,
        description="Maximum number of results",
        ge=1,
        le=200
    )
):
    """
    Get collision risks for a specific satellite.
    
    Args:
        satellite_id: Satellite identifier (e.g., "2025-206B" or "satellites/2025-206B")
        risk_threshold: Minimum risk score
        limit: Maximum number of results (1-200)
    
    Returns:
        List of satellites with collision risk to the specified satellite
    """
    try:
        results = collision_service.get_collision_risks_for_satellite(
            satellite_id=satellite_id,
            risk_threshold=risk_threshold,
            limit=limit
        )
        
        return {
            "data": {
                "satellite_id": satellite_id,
                "collision_risks": results,
                "count": len(results),
                "parameters": {
                    "risk_threshold": risk_threshold,
                    "limit": limit
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying collision risks for satellite: {str(e)}"
        )


@router.get("/collision-risks/network/graph")
def get_collision_risk_network(
    orbital_band: Optional[str] = Query(
        default=None,
        description="Filter by orbital band"
    ),
    risk_threshold: float = Query(
        default=0.5,
        description="Minimum risk score threshold (0-1)",
        ge=0.0,
        le=1.0
    ),
    limit: int = Query(
        default=100,
        description="Maximum number of edges",
        ge=1,
        le=500
    )
):
    """
    Get collision risk network as nodes and edges for visualization.
    
    Args:
        orbital_band: Optional filter by orbital band
        risk_threshold: Minimum risk score (0-1)
        limit: Maximum number of edges (1-500)
    
    Returns:
        Graph data with nodes (satellites) and edges (collision risks)
    """
    try:
        result = collision_service.get_collision_risk_network(
            orbital_band=orbital_band,
            risk_threshold=risk_threshold,
            limit=limit
        )
        
        return {
            "data": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error building collision risk network: {str(e)}"
        )


@router.get("/collision-risks/statistics")
def get_collision_risk_statistics(
    orbital_band: Optional[str] = Query(
        default=None,
        description="Filter by orbital band"
    )
):
    """
    Get statistics about collision risks in the database.
    
    Args:
        orbital_band: Optional filter by orbital band
    
    Returns:
        Statistics including edge counts, risk levels, and orbital band distribution
    """
    try:
        stats = collision_service.get_collision_risk_statistics(
            orbital_band=orbital_band
        )
        
        return {
            "data": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating collision risk statistics: {str(e)}"
        )


@router.get("/collision-risks/clusters")
def get_collision_clusters(
    orbital_band: Optional[str] = Query(
        default=None,
        description="Filter by orbital band"
    ),
    risk_threshold: float = Query(
        default=0.7,
        description="Minimum risk score for cluster membership (0-1)",
        ge=0.0,
        le=1.0
    ),
    min_cluster_size: int = Query(
        default=3,
        description="Minimum number of satellites in a cluster",
        ge=2,
        le=50
    )
):
    """
    Identify clusters of satellites with high collision risk.
    
    Clusters represent groups of satellites that have multiple high-risk
    collision relationships with each other.
    
    Args:
        orbital_band: Optional filter by orbital band
        risk_threshold: Minimum risk score for cluster edges (0-1)
        min_cluster_size: Minimum satellites per cluster (2-50)
    
    Returns:
        List of collision risk clusters with member satellites
    """
    try:
        results = analyze_collision_clusters(
            orbital_band=orbital_band,
            risk_threshold=risk_threshold,
            min_cluster_size=min_cluster_size
        )
        
        return {
            "data": {
                "clusters": results,
                "count": len(results),
                "parameters": {
                    "orbital_band": orbital_band,
                    "risk_threshold": risk_threshold,
                    "min_cluster_size": min_cluster_size
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing collision clusters: {str(e)}"
        )


@router.get("/cross-constellation-proximity")
def get_cross_constellation_proximity(
    limit: int = Query(
        default=100,
        description="Maximum number of satellite pairs to return",
        ge=1,
        le=500
    ),
    proximity_threshold: float = Query(
        default=0.7,
        description="Minimum proximity score threshold (0-1)",
        ge=0.0,
        le=1.0
    )
):
    """
    Find satellites from different constellations that are in orbital proximity.
    
    This demonstrates multi-dimensional graph queries by combining:
    - Constellation membership relationships
    - Orbital proximity relationships
    
    Returns satellites that belong to different constellations but are
    in close orbital proximity, highlighting potential collision risks
    between different constellation systems.
    
    Args:
        limit: Maximum number of satellite pairs (1-500)
        proximity_threshold: Minimum proximity score (0-1)
    
    Returns:
        Graph data with nodes (satellites) and edges (cross-constellation proximity)
        including statistics on constellation pairs
    """
    try:
        result = find_cross_constellation_proximity(
            limit=limit,
            proximity_threshold=proximity_threshold
        )
        
        if not result:
            return {
                "data": {
                    "nodes": [],
                    "edges": [],
                    "stats": {
                        "total_satellites": 0,
                        "total_proximity_pairs": 0,
                        "constellation_pairs": 0,
                        "top_constellation_pairs": []
                    }
                },
                "message": "No cross-constellation proximity relationships found",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        return {
            "data": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error finding cross-constellation proximity: {str(e)}"
        )


@router.get("/country-cooperation-network")
def get_country_cooperation_network(
    limit: int = Query(
        default=50,
        description="Maximum number of country pairs to return",
        ge=1,
        le=200
    ),
    min_shared_satellites: int = Query(
        default=2,
        description="Minimum number of shared satellites/connections",
        ge=1,
        le=20
    )
):
    """
    Find countries that cooperate through multiple relationship types.
    
    This demonstrates multi-dimensional graph analysis by combining:
    - Shared registration documents
    - Satellites in orbital proximity
    - Constellation membership patterns
    
    Returns country pairs that show cooperation through shared registration
    documents and/or satellites in close orbital proximity, revealing
    international space collaboration patterns.
    
    Args:
        limit: Maximum number of country pairs (1-200)
        min_shared_satellites: Minimum shared satellites/connections (1-20)
    
    Returns:
        Graph data with nodes (countries) and edges (cooperation relationships)
        including cooperation scores and types
    """
    try:
        result = find_country_cooperation_network(
            limit=limit,
            min_shared_satellites=min_shared_satellites
        )
        
        if not result:
            return {
                "data": {
                    "nodes": [],
                    "edges": [],
                    "stats": {
                        "total_countries": 0,
                        "total_cooperation_pairs": 0,
                        "avg_cooperation_score": 0,
                        "max_cooperation_score": 0
                    }
                },
                "message": "No country cooperation relationships found",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        return {
            "data": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error finding country cooperation network: {str(e)}"
        )


@router.get("/function-clusters")
def get_function_based_clusters(
    orbital_band: Optional[str] = Query(
        default=None,
        description="Filter by orbital band (e.g., 'LEO', 'MEO', 'GEO')"
    ),
    limit: int = Query(
        default=20,
        description="Maximum number of clusters to return",
        ge=1,
        le=100
    ),
    min_cluster_size: int = Query(
        default=3,
        description="Minimum number of satellites in a cluster",
        ge=2,
        le=50
    )
):
    """
    Find satellite clusters based on shared function, orbital band, and proximity.
    
    This demonstrates multi-dimensional clustering by combining:
    - Similar satellite functions (communication, Earth observation, etc.)
    - Same orbital band
    - Orbital proximity relationships
    
    Returns clusters of satellites that share the same function and orbital band,
    and have proximity relationships with each other, revealing functional
    satellite groupings and potential congestion zones.
    
    Args:
        orbital_band: Optional orbital band filter
        limit: Maximum number of clusters (1-100)
        min_cluster_size: Minimum satellites per cluster (2-50)
    
    Returns:
        Graph data with nodes (satellites), edges (proximity), and cluster metadata
        including density metrics and multi-country collaboration
    """
    try:
        result = find_function_based_clusters(
            orbital_band=orbital_band,
            limit=limit,
            min_cluster_size=min_cluster_size
        )
        
        if not result:
            return {
                "data": {
                    "nodes": [],
                    "edges": [],
                    "clusters": [],
                    "stats": {
                        "total_clusters": 0,
                        "total_satellites": 0,
                        "total_proximity_edges": 0,
                        "avg_cluster_size": 0,
                        "avg_density": 0
                    }
                },
                "message": "No function-based clusters found",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        return {
            "data": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error finding function-based clusters: {str(e)}"
        )


@router.get("/lineage/{satellite_id}")
def get_satellite_lineage_tree(
    satellite_id: str,
    direction: str = Query(
        default="both",
        description="Traversal direction: 'ancestors', 'descendants', or 'both'"
    ),
    max_depth: int = Query(
        default=5,
        description="Maximum traversal depth",
        ge=1,
        le=10
    )
):
    """
    Get satellite lineage tree showing family relationships.
    
    Returns ancestors (predecessors) and/or descendants (successors) of a satellite
    within the same family lineage (e.g., GPS-IIA → GPS-III, Iridium → Iridium Next).
    
    Args:
        satellite_id: Satellite identifier or document key
        direction: 'ancestors', 'descendants', or 'both'
        max_depth: Maximum traversal depth (1-10)
    
    Returns:
        Root satellite with ancestors/descendants and generation information
    """
    try:
        if direction not in ["ancestors", "descendants", "both"]:
            raise HTTPException(
                status_code=400,
                detail="direction must be 'ancestors', 'descendants', or 'both'"
            )
        
        result = lineage_service.get_satellite_lineage(
            satellite_id=satellite_id,
            direction=direction,
            max_depth=max_depth
        )
        
        if "error" in result and result["root"] is None:
            raise HTTPException(
                status_code=404,
                detail=result["error"]
            )
        
        return {
            "data": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving satellite lineage: {str(e)}"
        )


@router.get("/lineage/family/{family_name}")
def get_family_tree(
    family_name: str,
    limit: int = Query(
        default=100,
        description="Maximum number of satellites to return",
        ge=1,
        le=500
    )
):
    """
    Get complete family tree for a satellite family.
    
    Returns all satellites and their relationships within a specific family
    (e.g., GPS, IRIDIUM, GLONASS, STARLINK).
    
    Args:
        family_name: Family name (e.g., 'GPS', 'IRIDIUM', 'STARLINK')
        limit: Maximum number of satellites (1-500)
    
    Returns:
        Graph data with nodes (satellites) and edges (lineage relationships)
        organized by family generations
    """
    try:
        result = lineage_service.get_satellite_family_tree(
            family_name=family_name,
            limit=limit
        )
        
        if not result.get("nodes"):
            return {
                "data": result,
                "message": f"No satellites found for family '{family_name}'",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        return {
            "data": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving family tree: {str(e)}"
        )


@router.get("/lineage/statistics")
def get_lineage_statistics_endpoint():
    """
    Get statistics about satellite lineage relationships.
    
    Returns summary statistics including:
    - Total lineage edges
    - Family counts
    - Generation gap distribution
    
    Returns:
        Statistics dictionary with counts and distributions
    """
    try:
        stats = lineage_service.get_lineage_statistics()
        
        return {
            "data": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving lineage statistics: {str(e)}"
        )


@router.get("/communities")
def get_communities(
    algorithm: str = Query(
        default="label_propagation",
        description="Community detection algorithm: 'connected_components' or 'label_propagation'"
    ),
    min_size: int = Query(
        default=2,
        description="Minimum community size",
        ge=2,
        le=100
    ),
    edge_types: Optional[List[str]] = Query(
        default=None,
        description="Optional list of edge types to consider"
    )
):
    """
    Detect communities in the satellite network.
    
    Communities are groups of satellites that are more densely connected to each
    other than to the rest of the network. This endpoint supports multiple
    detection algorithms:
    
    - **label_propagation**: Fast iterative algorithm where nodes adopt the most
      common label among their neighbors. Good for large graphs and detecting
      overlapping community structures.
    
    - **connected_components**: Finds isolated clusters of connected satellites.
      Useful for identifying completely separate network segments.
    
    Args:
        algorithm: Detection algorithm to use
        min_size: Minimum number of satellites in a community
        edge_types: Optional list of edge collections to consider
    
    Returns:
        List of detected communities with members, statistics, and characteristics.
        Results are cached for 12 hours to improve performance.
    
    Example:
        GET /v2/graphs/communities?algorithm=label_propagation&min_size=5
    """
    try:
        cache_key = f"{algorithm}:{min_size}:{','.join(edge_types) if edge_types else 'all'}"
        
        cached_result = community_cache.get(cache_key)
        if cached_result is not None:
            return {
                "data": cached_result,
                "cached": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        valid_algorithms = ["connected_components", "label_propagation"]
        if algorithm not in valid_algorithms:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid algorithm. Must be one of: {', '.join(valid_algorithms)}"
            )
        
        communities = detect_communities(
            algorithm=algorithm,
            edge_types=edge_types,
            min_community_size=min_size
        )
        
        result = {
            "communities": communities,
            "algorithm": algorithm,
            "stats": {
                "total_communities": len(communities),
                "total_satellites": sum(c.get("size", 0) for c in communities),
                "min_community_size": min_size,
                "edge_types": edge_types or ["all"]
            }
        }
        
        community_cache.set(cache_key, result)
        
        return {
            "data": result,
            "cached": False,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error detecting communities: {str(e)}"
        )


@router.get("/evolution/timeline")
def get_graph_evolution_timeline(
    start_date: Optional[str] = Query(default="1957", description="Start date (YYYY or YYYY-MM or YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY or YYYY-MM or YYYY-MM-DD)"),
    granularity: str = Query(default="year", description="Time granularity (year, month, quarter)"),
    edge_types: Optional[List[str]] = Query(default=None, description="Optional list of edge types to include")
):
    """
    Get graph evolution timeline showing how the network grows over time.
    
    Parameters:
        start_date: Start date for timeline (default: 1957, first satellite)
        end_date: End date for timeline (default: current year)
        granularity: Time granularity - 'year', 'month', or 'quarter'
        edge_types: Optional list of edge collections to consider
    
    Returns:
        Timeline data with node counts, edge counts, density, and growth metrics.
        Results are cached for 24 hours to improve performance.
    
    Example:
        GET /v2/graphs/evolution/timeline?start_date=2000&end_date=2024&granularity=year
    """
    try:
        if end_date is None:
            end_date = str(datetime.now().year)
        
        cache_key = f"{start_date}:{end_date}:{granularity}:{','.join(edge_types) if edge_types else 'all'}"
        
        cached_result = evolution_cache.get(cache_key)
        if cached_result is not None:
            return {
                "data": cached_result,
                "cached": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        valid_granularities = ["year", "month", "quarter"]
        if granularity not in valid_granularities:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid granularity. Must be one of: {', '.join(valid_granularities)}"
            )
        
        if granularity == "year":
            start_formatted = f"{start_date}-01-01" if len(start_date) == 4 else start_date
            end_formatted = f"{end_date}-12-31" if len(end_date) == 4 else end_date
        elif granularity == "month":
            start_formatted = f"{start_date}-01" if len(start_date) == 4 else start_date
            end_formatted = f"{end_date}-12" if len(end_date) == 4 else end_date
        else:
            start_formatted = start_date
            end_formatted = end_date
        
        timeline = calculate_graph_evolution_timeline(
            start_date=start_formatted,
            end_date=end_formatted,
            granularity=granularity,
            edge_types=edge_types
        )
        
        if not timeline:
            result = {
                "timeline": [],
                "parameters": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "granularity": granularity,
                    "edge_types": edge_types or ["all"]
                },
                "stats": {
                    "total_periods": 0,
                    "total_growth": {
                        "nodes": 0,
                        "edges": 0
                    },
                    "final_state": {
                        "node_count": 0,
                        "edge_count": 0,
                        "density": 0
                    }
                }
            }
        else:
            final_snapshot = timeline[-1]
            initial_snapshot = timeline[0]
            
            result = {
                "timeline": timeline,
                "parameters": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "granularity": granularity,
                    "edge_types": edge_types or ["all"]
                },
                "stats": {
                    "total_periods": len(timeline),
                    "total_growth": {
                        "nodes": final_snapshot['node_count'] - initial_snapshot['node_count'],
                        "edges": final_snapshot['edge_count'] - initial_snapshot['edge_count']
                    },
                    "final_state": {
                        "node_count": final_snapshot['node_count'],
                        "edge_count": final_snapshot['edge_count'],
                        "density": final_snapshot['density'],
                        "avg_degree": final_snapshot['avg_degree']
                    },
                    "peak_growth_period": max(timeline, key=lambda x: x.get('node_growth', 0))['period'],
                    "avg_density": sum(t['density'] for t in timeline) / len(timeline)
                }
            }
        
        evolution_cache.set(cache_key, result)
        
        return {
            "data": result,
            "cached": False,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating graph evolution timeline: {str(e)}"
        )


@router.get("/evolution/snapshot/{date}")
def get_graph_snapshot(
    date: str,
    edge_types: Optional[List[str]] = Query(default=None, description="Optional list of edge types to include")
):
    """
    Get graph snapshot at a specific date.
    
    Parameters:
        date: Target date (YYYY or YYYY-MM or YYYY-MM-DD)
        edge_types: Optional list of edge collections to consider
    
    Returns:
        Snapshot data with node count, edge count, density, and other metrics.
    
    Example:
        GET /v2/graphs/evolution/snapshot/2020-01
    """
    try:
        snapshot = get_graph_snapshot_by_date(
            target_date=date,
            edge_types=edge_types
        )
        
        return {
            "data": snapshot,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting graph snapshot: {str(e)}"
        )


@router.get("/recommendations/{satellite_id}")
def get_satellite_recommendations(
    satellite_id: str,
    strategy: str = Query(
        default="collaborative_filtering",
        description="Recommendation strategy: 'collaborative_filtering', 'similar_neighbors', 'second_degree', 'common_neighbors', or 'similarity'"
    ),
    edge_types: Optional[List[str]] = Query(
        default=None,
        description="Optional list of edge types to consider"
    ),
    limit: int = Query(default=10, ge=1, le=100, description="Maximum number of recommendations"),
    min_similarity: float = Query(default=0.1, ge=0.0, le=1.0, description="Minimum similarity threshold (for similarity strategy)"),
    min_common_connections: int = Query(default=2, ge=1, description="Minimum common connections (for collaborative filtering)")
):
    """
    Get satellite recommendations based on graph structure.
    
    Provides different recommendation strategies:
    
    - **collaborative_filtering**: Satellites that share many connections but aren't directly connected
      (like "users who liked X also liked Y")
    
    - **similar_neighbors**: Satellites connected to other satellites similar to this one
    
    - **second_degree**: Satellites at distance 2 (friends of friends)
    
    - **common_neighbors**: Satellites with most common neighbors
    
    - **similarity**: Satellites most similar based on Jaccard similarity of neighbor sets
    
    Parameters:
        satellite_id: Reference satellite ID (e.g., "2025-001A")
        strategy: Recommendation strategy to use
        edge_types: Optional list of edge collections to consider
        limit: Maximum number of recommendations (1-100)
        min_similarity: Minimum similarity threshold for similarity strategy (0-1)
        min_common_connections: Minimum common connections for collaborative filtering
    
    Returns:
        Recommended satellites with relevance scores and recommendation metadata.
    
    Example:
        GET /v2/graphs/recommendations/2025-001A?strategy=collaborative_filtering&limit=10
    """
    try:
        cache_key = hashlib.md5(
            json.dumps({
                "satellite_id": satellite_id,
                "strategy": strategy,
                "edge_types": edge_types or [],
                "limit": limit,
                "min_similarity": min_similarity,
                "min_common_connections": min_common_connections
            }, sort_keys=True).encode()
        ).hexdigest()
        
        cached_result = recommendation_cache.get(cache_key)
        if cached_result is not None:
            return {
                "data": cached_result,
                "cached": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        full_id = f"{COLLECTION_NAME}/{satellite_id}"
        
        valid_strategies = [
            "collaborative_filtering",
            "similar_neighbors",
            "second_degree",
            "common_neighbors",
            "similarity"
        ]
        
        if strategy not in valid_strategies:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid strategy. Must be one of: {', '.join(valid_strategies)}"
            )
        
        if strategy == "collaborative_filtering":
            recommendations = get_collaborative_filtering_recommendations(
                satellite_id=full_id,
                edge_types=edge_types,
                limit=limit,
                min_common_connections=min_common_connections
            )
        elif strategy == "similarity":
            recommendations = get_similar_satellites(
                satellite_id=full_id,
                edge_types=edge_types,
                limit=limit,
                min_similarity=min_similarity
            )
        else:
            recommendations = get_neighbor_based_recommendations(
                satellite_id=full_id,
                edge_types=edge_types,
                limit=limit,
                strategy=strategy
            )
        
        result = {
            "satellite_id": satellite_id,
            "strategy": strategy,
            "recommendations": recommendations,
            "count": len(recommendations),
            "parameters": {
                "strategy": strategy,
                "edge_types": edge_types or ["all"],
                "limit": limit,
                "min_similarity": min_similarity if strategy == "similarity" else None,
                "min_common_connections": min_common_connections if strategy == "collaborative_filtering" else None
            }
        }
        
        recommendation_cache.set(cache_key, result)
        
        return {
            "data": result,
            "cached": False,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error getting recommendations: {str(e)}"
        )


@router.get("/registration-documents-analytics")
def get_registration_documents_analytics(
    sort_by: Optional[str] = Query(default="satellite_count", description="Field to sort by (url, satellite_count, created_at)"),
    sort_order: Optional[str] = Query(default="DESC", description="Sort order (ASC or DESC)"),
    search: Optional[str] = Query(default=None, description="Filter URLs containing search term")
):
    """
    Get comprehensive analytics for all registration documents.
    
    Returns all registration documents with statistics including:
    - Complete list of documents with URL, satellite count, countries, and creation date
    - Summary statistics: total documents, total satellites, averages, top country
    
    Parameters:
        sort_by: Field to sort by (url, satellite_count, created_at) - default: satellite_count
        sort_order: Sort order (ASC or DESC) - default: DESC
        search: Optional search term to filter URLs
    
    Returns:
        Analytics data with documents array and summary statistics
    
    Example:
        GET /v2/graphs/registration-documents-analytics?sort_by=satellite_count&sort_order=DESC
        GET /v2/graphs/registration-documents-analytics?search=ST/SG
    """
    # Validate sort_by parameter
    valid_sort_fields = ["url", "satellite_count", "created_at"]
    if sort_by not in valid_sort_fields:
        sort_by = "satellite_count"
    
    # Validate sort_order parameter
    sort_order = sort_order.upper()
    if sort_order not in ["ASC", "DESC"]:
        sort_order = "DESC"
    
    query = f"""
    LET all_docs = (
        FOR doc IN {COLLECTION_REG_DOCS}
            FILTER @search == null OR CONTAINS(LOWER(doc.url), LOWER(@search))
            SORT doc[@sort_by] @sort_order
            RETURN {{
                key: doc._key,
                url: doc.url,
                satellite_count: doc.satellite_count,
                countries: doc.countries,
                created_at: doc.created_at
            }}
    )
    
    LET stats = {{
        total_documents: LENGTH(all_docs),
        total_satellites: SUM(all_docs[*].satellite_count),
        avg_satellites_per_doc: AVG(all_docs[*].satellite_count),
        top_country: FIRST(
            FOR doc IN all_docs
                FOR country IN doc.countries
                    COLLECT c = country WITH COUNT INTO cnt
                    SORT cnt DESC
                    LIMIT 1
                    RETURN c
        )
    }}
    
    RETURN {{
        documents: all_docs,
        stats: stats
    }}
    """
    
    cursor = db_conn.db.aql.execute(
        query,
        bind_vars={
            'search': search,
            'sort_by': sort_by,
            'sort_order': sort_order
        }
    )
    
    results = list(cursor)
    
    if results and len(results) > 0:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "documents": [],
                "stats": {
                    "total_documents": 0,
                    "total_satellites": 0,
                    "avg_satellites_per_doc": 0,
                    "top_country": None
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/cache/stats/all")
def get_all_cache_stats():
    """
    Get comprehensive statistics for all graph query caches.
    
    Returns cache hit rates, sizes, and performance metrics for monitoring.
    """
    all_caches = {
        "path_queries": path_cache.get_stats(),
        "centrality_queries": centrality_cache.get_stats(),
        "community_queries": community_cache.get_stats(),
        "evolution_queries": evolution_cache.get_stats(),
        "recommendation_queries": recommendation_cache.get_stats(),
        "collision_queries": collision_cache.get_stats(),
        "cross_domain_queries": cross_domain_cache.get_stats()
    }
    
    total_hits = sum(cache["hits"] for cache in all_caches.values())
    total_misses = sum(cache["misses"] for cache in all_caches.values())
    total_requests = total_hits + total_misses
    overall_hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0.0
    
    return {
        "data": {
            "caches": all_caches,
            "overall": {
                "total_hits": total_hits,
                "total_misses": total_misses,
                "total_requests": total_requests,
                "hit_rate": f"{overall_hit_rate:.2f}%",
                "total_cache_size": sum(cache["size"] for cache in all_caches.values()),
                "total_evictions": sum(cache["evictions"] for cache in all_caches.values())
            }
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.post("/cache/clear/{cache_name}")
def clear_cache(cache_name: str):
    """
    Clear a specific cache by name.
    
    Args:
        cache_name: Name of cache to clear (path_queries, centrality_queries, etc.)
    
    Returns:
        Confirmation message
    """
    cache_map = {
        "path_queries": path_cache,
        "centrality_queries": centrality_cache,
        "community_queries": community_cache,
        "evolution_queries": evolution_cache,
        "recommendation_queries": recommendation_cache,
        "collision_queries": collision_cache,
        "cross_domain_queries": cross_domain_cache
    }
    
    if cache_name not in cache_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cache name. Valid options: {', '.join(cache_map.keys())}"
        )
    
    cache = cache_map[cache_name]
    cache.clear()
    
    return {
        "message": f"Cache '{cache_name}' cleared successfully",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.post("/cache/clear/all")
def clear_all_caches():
    """
    Clear all graph query caches.
    
    Returns:
        Confirmation message with count of cleared caches
    """
    caches = [
        path_cache,
        centrality_cache,
        community_cache,
        evolution_cache,
        recommendation_cache,
        collision_cache,
        cross_domain_cache
    ]
    
    for cache in caches:
        cache.clear()
    
    return {
        "message": f"All {len(caches)} caches cleared successfully",
        "caches_cleared": [
            "path_queries",
            "centrality_queries",
            "community_queries",
            "evolution_queries",
            "recommendation_queries",
            "collision_queries",
            "cross_domain_queries"
        ],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
