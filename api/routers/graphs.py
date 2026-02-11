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
    GRAPH_NAME
)
from database.graph_analytics import (
    find_shortest_path,
    find_all_paths,
    calculate_degree_centrality,
    calculate_betweenness_centrality,
    calculate_closeness_centrality
)
from api.services.cache_service import get_cache

router = APIRouter(prefix="/v2/graphs", tags=["graphs"])

path_cache = get_cache("path_queries", ttl=3600, max_size=1000)
centrality_cache = get_cache("centrality_queries", ttl=86400, max_size=500)


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
        {f"LIMIT {limit}" if limit else ""}
        RETURN {{
            id: v._id,
            key: v._key,
            identifier: v.identifier,
            name: v.canonical.name,
            country: v.canonical.country_of_origin,
            orbital_band: v.canonical.orbital_band,
            status: v.canonical.status,
            launch_date: v.canonical.date_of_launch
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
            FILTER doc.canonical.launch_date != null
            LET year = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 0, 4))
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
        FILTER doc.canonical.launch_date != null
        FILTER {filter_clause}
        LET launch_year = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 0, 4))
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
        FILTER doc.canonical.launch_date != null
        FILTER {filter_clause}
        LET launch_year = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 0, 4))
        FILTER launch_year == @year
        LET launch_month = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 5, 2))
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
            FILTER doc.canonical.launch_date != null
            LET sat_year = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 0, 4))
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
            FILTER doc.canonical.launch_date != null
            LET sat_year = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 0, 4))
            LET sat_month = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 5, 2))
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
            FILTER doc.canonical.launch_date != null
            LET year = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 0, 4))
            FILTER year >= @start_year AND year <= @end_year
            LIMIT @limit
            RETURN {{
                _key: doc._key,
                _id: doc._id,
                identifier: doc.identifier,
                name: doc.canonical.name,
                launch_date: doc.canonical.launch_date,
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
            FILTER doc.canonical.launch_date != null
            LET year = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 0, 4))
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
def get_function_similarity_graph(limit: Optional[int] = Query(default=100, description="Limit satellites per category")):
    """
    Get function similarity graph showing satellites grouped by function categories.
    
    Categories are derived from function keywords:
    - Communications: satellites for telecommunications
    - Earth Observation: remote sensing, earth resources
    - Scientific Research: space/atmosphere investigation
    - Navigation: GPS, GLONASS, positioning
    - Military-Defense: defense, military assignments
    - Space Station: ISS, Mir supply and operations
    - Technology-Testing: tech demonstration, experimental
    """
    
    query = f"""
    LET satellites_with_function = (
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.canonical.function != null
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
            RETURN {{
                _id: doc._id,
                _key: doc._key,
                identifier: doc.identifier,
                name: doc.canonical.name,
                function: doc.canonical.function,
                function_category: category,
                country: doc.canonical.country,
                launch_date: doc.canonical.launch_date,
                orbital_band: doc.canonical.orbital_band,
                congestion_risk: doc.canonical.congestion_risk
            }}
    )
    
    LET category_stats = (
        FOR sat IN satellites_with_function
            COLLECT category = sat.function_category WITH COUNT INTO count
            SORT count DESC
            RETURN {{
                category: category,
                satellite_count: count
            }}
    )
    
    LET limited_satellites = (
        FOR sat IN satellites_with_function
            COLLECT category = sat.function_category INTO category_sats
            LET limited_sats = SLICE(category_sats[*].sat, 0, @limit)
            FOR s IN limited_sats
                RETURN s
    )
    
    LET satellite_ids = limited_satellites[*]._id
    
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
    
    LET edges = UNION(constellation_edges, registration_edges, proximity_edges)
    
    RETURN {{
        nodes: limited_satellites,
        edges: edges,
        categories: category_stats,
        stats: {{
            total_with_function: LENGTH(satellites_with_function),
            nodes_shown: LENGTH(limited_satellites),
            edges_shown: LENGTH(edges),
            categories_count: LENGTH(category_stats)
        }}
    }}
    """
    
    cursor = db_conn.db.aql.execute(query, bind_vars={'limit': limit})
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
                "categories": [],
                "stats": {
                    "total_with_function": 0,
                    "nodes_shown": 0,
                    "edges_shown": 0,
                    "categories_count": 0
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
                launch_date: doc.canonical.launch_date,
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
    
    from_doc_id = from_id if from_id.startswith("satellites/") else f"satellites/{from_id}"
    to_doc_id = to_id if to_id.startswith("satellites/") else f"satellites/{to_id}"
    
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
