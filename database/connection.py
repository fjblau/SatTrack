from arango import ArangoClient
import os
import sys

ARANGO_HOST = os.getenv("ARANGO_HOST", "http://localhost:8529")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "kessler_dev_password")
DB_NAME = "kessler"
COLLECTION_NAME = "objects"

GRAPH_NAME = "satellite_relationships"
EDGE_COLLECTION_CONSTELLATION = "constellation_membership"
EDGE_COLLECTION_REGISTRATION = "registration_links"
EDGE_COLLECTION_PROXIMITY = "orbital_proximity"
EDGE_COLLECTION_COLLISION_RISK = "collision_risk_edges"
EDGE_COLLECTION_SATELLITE_LINEAGE = "satellite_lineage"
COLLECTION_REG_DOCS = "registration_documents"
COLLECTION_OBSERVATIONS = "observations"
COLLECTION_OBSERVATION_SOURCES = "observation_sources"
COLLECTION_EPHEMERIS = "ephemeris_envelopes"
COLLECTION_MANEUVER_PLANS = "kestrel_maneuver_plans"
COLLECTION_TLE_HISTORY = "tle_history"
COLLECTION_TLE_HISTORY_COVERAGE = "tle_history_coverage"

OBSERVATION_GRAPH_NAME = "observation_relationships"
EDGE_COLLECTION_OBS_SATELLITE = "observation_satellite_edges"
EDGE_COLLECTION_OBS_SOURCE = "observation_source_edges"
EDGE_COLLECTION_OBS_CORRELATION = "observation_correlation_edges"
EDGE_COLLECTION_OBS_TEMPORAL = "observation_temporal_edges"

PROVENANCE_GRAPH_NAME = "provenance_relationships"
COLLECTION_FRAGMENTATION_EVENTS = "fragmentation_events"

INSURANCE_GRAPH_NAME = "insurance"
COLLECTION_PARTIES = "parties"
COLLECTION_POLICIES = "policies"
COLLECTION_INSURED_INTERESTS = "insured_interests"
COLLECTION_LOSS_EVENTS = "loss_events"
COLLECTION_CLAIMS = "claims"
COLLECTION_RISK_SCORES = "risk_scores"
COLLECTION_ANOMALY_PREDICTIONS = "anomaly_predictions"
COLLECTION_SHELLS = "shells"
COLLECTION_KESTRELS = "kestrels"
COLLECTION_KESTREL_TASKS = "kestrel_tasks"
COLLECTION_COVERAGE_WINDOWS = "coverage_windows"

EDGE_INSURANCE_POLICY_COVERS_SAT = "policy_covers_satellite"
EDGE_INSURANCE_POLICY_HAS_INTEREST = "policy_has_interest"
EDGE_INSURANCE_INTEREST_HELD_BY = "interest_held_by"
EDGE_INSURANCE_CLAIM_ARISES_FROM = "claim_arises_from"
EDGE_INSURANCE_LOSS_EVENT_INVOLVES = "loss_event_involves"
EDGE_INSURANCE_SAT_IN_SHELL = "satellite_in_shell"
EDGE_INSURANCE_RISK_SCORE_FOR = "risk_score_for"
EDGE_INSURANCE_PREDICTION_FOR = "prediction_for"
EDGE_INSURANCE_KESTREL_OBSERVED = "kestrel_observed"
EDGE_INSURANCE_KESTREL_CAN_SEE = "kestrel_can_see"
EDGE_INSURANCE_TASK_TARGETS = "task_targets"
EDGE_INSURANCE_EVENT_WITNESSED_BY = "event_witnessed_by"
COLLECTION_LAUNCH_EVENTS = "launch_events"
COLLECTION_LAUNCH_VEHICLES = "launch_vehicles"
COLLECTION_LAUNCH_SITES = "launch_sites"
COLLECTION_ENTITIES = "entities"
EDGE_COLLECTION_FRAGMENTED_FROM = "fragmented_from"
EDGE_COLLECTION_CAUSED_BY = "caused_by"
EDGE_COLLECTION_LAUNCHED_BY = "launched_by"
EDGE_COLLECTION_LAUNCHED_VIA = "launched_via"
EDGE_COLLECTION_LAUNCHED_FROM = "launched_from"

# Customer Tasks overlay
COLLECTION_CUSTOMER_TASKS        = "customer_tasks"
COLLECTION_CUSTOMER_TASK_TRANS   = "customer_task_transitions"
COLLECTION_TASK_DELIVERABLES     = "task_deliverables"
COLLECTION_TASK_SLA_ALERTS       = "task_sla_alerts"

EDGE_TASK_REQUESTED_BY           = "task_requested_by"
EDGE_TASK_TARGETS_OBJECT         = "task_targets_object"
EDGE_TASK_RELATES_TO_POLICY      = "task_relates_to_policy"
EDGE_TASK_RELATES_TO_LOSS_EVENT  = "task_relates_to_loss_event"
EDGE_TASK_PRODUCED_DELIVERABLE   = "task_produced_deliverable"

client = None
db = None
satellites_collection = None
objects_collection = None


def connect_arangodb():
    """Initialize ArangoDB connection"""
    global client, db, satellites_collection
    try:
        client = ArangoClient(hosts=ARANGO_HOST)
        
        sys_db = client.db('_system', username=ARANGO_USER, password=ARANGO_PASSWORD)
        
        if not sys_db.has_database(DB_NAME):
            sys_db.create_database(DB_NAME)
        
        db = client.db(DB_NAME, username=ARANGO_USER, password=ARANGO_PASSWORD)
        
        if not db.has_collection(COLLECTION_NAME):
            satellites_collection = db.create_collection(COLLECTION_NAME)
        else:
            satellites_collection = db.collection(COLLECTION_NAME)
        
        satellites_collection.add_persistent_index(fields=['canonical.international_designator'], unique=False)
        satellites_collection.add_persistent_index(fields=['canonical.registration_number'], unique=False)
        satellites_collection.add_persistent_index(fields=['identifier'], unique=True)

        # Ensure observations collection exists
        if not db.has_collection(COLLECTION_OBSERVATIONS):
            db.create_collection(COLLECTION_OBSERVATIONS)
        obs_col = db.collection(COLLECTION_OBSERVATIONS)
        obs_col.add_persistent_index(fields=['norad_id'], unique=False)
        obs_col.add_persistent_index(fields=['source'], unique=False)
        obs_col.add_persistent_index(fields=['observation_epoch'], unique=False)

        # Ensure observation_sources vertex collection exists
        if not db.has_collection(COLLECTION_OBSERVATION_SOURCES):
            db.create_collection(COLLECTION_OBSERVATION_SOURCES)

        # Ensure ephemeris_envelopes collection exists
        if not db.has_collection(COLLECTION_EPHEMERIS):
            db.create_collection(COLLECTION_EPHEMERIS)
        eph_col = db.collection(COLLECTION_EPHEMERIS)
        eph_col.add_persistent_index(fields=['norad_id'], unique=False)
        eph_col.add_persistent_index(fields=['generated_at'], unique=False)
        eph_col.add_persistent_index(fields=['valid_from'], unique=False)
        eph_col.add_persistent_index(fields=['valid_until'], unique=False)

        # Ensure kestrel_maneuver_plans collection exists
        if not db.has_collection(COLLECTION_MANEUVER_PLANS):
            db.create_collection(COLLECTION_MANEUVER_PLANS)
        mpln_col = db.collection(COLLECTION_MANEUVER_PLANS)
        mpln_col.add_persistent_index(fields=['kestrel_norad_id'], unique=False)
        mpln_col.add_persistent_index(fields=['target_norad_id'], unique=False)
        mpln_col.add_persistent_index(fields=['created_at'], unique=False)

        if not db.has_collection(COLLECTION_TLE_HISTORY):
            db.create_collection(COLLECTION_TLE_HISTORY)
        th_col = db.collection(COLLECTION_TLE_HISTORY)
        th_col.add_persistent_index(fields=['norad_id'], unique=False)
        th_col.add_persistent_index(fields=['tle_epoch'], unique=False)
        th_col.add_persistent_index(fields=['norad_id', 'tle_epoch'], unique=False)

        if not db.has_collection(COLLECTION_TLE_HISTORY_COVERAGE):
            db.create_collection(COLLECTION_TLE_HISTORY_COVERAGE)

        # Ensure observation edge collections exist
        obs_edge_collections = [
            EDGE_COLLECTION_OBS_SATELLITE,
            EDGE_COLLECTION_OBS_SOURCE,
            EDGE_COLLECTION_OBS_CORRELATION,
            EDGE_COLLECTION_OBS_TEMPORAL,
        ]
        for edge_col_name in obs_edge_collections:
            if not db.has_collection(edge_col_name):
                db.create_collection(edge_col_name, edge=True)

        # Ensure satellite_relationships graph exists (pointing at objects collection)
        if not db.has_graph(GRAPH_NAME):
            satellite_edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY,
                EDGE_COLLECTION_COLLISION_RISK,
                EDGE_COLLECTION_SATELLITE_LINEAGE,
            ]
            for ecol in satellite_edge_collections:
                if not db.has_collection(ecol):
                    db.create_collection(ecol, edge=True)
            db.create_graph(
                GRAPH_NAME,
                edge_definitions=[
                    {
                        "edge_collection": EDGE_COLLECTION_CONSTELLATION,
                        "from_vertex_collections": [COLLECTION_NAME],
                        "to_vertex_collections": [COLLECTION_NAME],
                    },
                    {
                        "edge_collection": EDGE_COLLECTION_REGISTRATION,
                        "from_vertex_collections": [COLLECTION_NAME],
                        "to_vertex_collections": [COLLECTION_REG_DOCS],
                    },
                    {
                        "edge_collection": EDGE_COLLECTION_PROXIMITY,
                        "from_vertex_collections": [COLLECTION_NAME],
                        "to_vertex_collections": [COLLECTION_NAME],
                    },
                    {
                        "edge_collection": EDGE_COLLECTION_COLLISION_RISK,
                        "from_vertex_collections": [COLLECTION_NAME],
                        "to_vertex_collections": [COLLECTION_NAME],
                    },
                    {
                        "edge_collection": EDGE_COLLECTION_SATELLITE_LINEAGE,
                        "from_vertex_collections": [COLLECTION_NAME],
                        "to_vertex_collections": [COLLECTION_NAME],
                    },
                ],
            )

        # Ensure observation graph exists
        if not db.has_graph(OBSERVATION_GRAPH_NAME):
            db.create_graph(
                OBSERVATION_GRAPH_NAME,
                edge_definitions=[
                    {
                        "edge_collection": EDGE_COLLECTION_OBS_SATELLITE,
                        "from_vertex_collections": [COLLECTION_OBSERVATIONS],
                        "to_vertex_collections": [COLLECTION_NAME],
                    },
                    {
                        "edge_collection": EDGE_COLLECTION_OBS_SOURCE,
                        "from_vertex_collections": [COLLECTION_OBSERVATIONS],
                        "to_vertex_collections": [COLLECTION_OBSERVATION_SOURCES],
                    },
                    {
                        "edge_collection": EDGE_COLLECTION_OBS_CORRELATION,
                        "from_vertex_collections": [COLLECTION_OBSERVATIONS],
                        "to_vertex_collections": [COLLECTION_OBSERVATIONS],
                    },
                    {
                        "edge_collection": EDGE_COLLECTION_OBS_TEMPORAL,
                        "from_vertex_collections": [COLLECTION_OBSERVATIONS],
                        "to_vertex_collections": [COLLECTION_OBSERVATIONS],
                    },
                ],
            )

        # Ensure provenance vertex collections exist
        provenance_vertex_collections = [
            COLLECTION_FRAGMENTATION_EVENTS,
            COLLECTION_LAUNCH_EVENTS,
            COLLECTION_LAUNCH_VEHICLES,
            COLLECTION_LAUNCH_SITES,
            COLLECTION_ENTITIES,
        ]
        for vcol_name in provenance_vertex_collections:
            if not db.has_collection(vcol_name):
                db.create_collection(vcol_name)

        # Ensure provenance edge collections exist
        provenance_edge_collections = [
            EDGE_COLLECTION_FRAGMENTED_FROM,
            EDGE_COLLECTION_CAUSED_BY,
            EDGE_COLLECTION_LAUNCHED_BY,
            EDGE_COLLECTION_LAUNCHED_VIA,
            EDGE_COLLECTION_LAUNCHED_FROM,
        ]
        for ecol_name in provenance_edge_collections:
            if not db.has_collection(ecol_name):
                db.create_collection(ecol_name, edge=True)

        # Ensure provenance_relationships named graph exists
        if not db.has_graph(PROVENANCE_GRAPH_NAME):
            db.create_graph(
                PROVENANCE_GRAPH_NAME,
                edge_definitions=[
                    {
                        "edge_collection": EDGE_COLLECTION_FRAGMENTED_FROM,
                        "from_vertex_collections": [COLLECTION_NAME],
                        "to_vertex_collections": [COLLECTION_NAME],
                    },
                    {
                        "edge_collection": EDGE_COLLECTION_CAUSED_BY,
                        "from_vertex_collections": [COLLECTION_NAME],
                        "to_vertex_collections": [COLLECTION_FRAGMENTATION_EVENTS],
                    },
                    {
                        "edge_collection": EDGE_COLLECTION_LAUNCHED_BY,
                        "from_vertex_collections": [COLLECTION_NAME],
                        "to_vertex_collections": [COLLECTION_ENTITIES],
                    },
                    {
                        "edge_collection": EDGE_COLLECTION_LAUNCHED_VIA,
                        "from_vertex_collections": [COLLECTION_NAME],
                        "to_vertex_collections": [COLLECTION_LAUNCH_VEHICLES],
                    },
                    {
                        "edge_collection": EDGE_COLLECTION_LAUNCHED_FROM,
                        "from_vertex_collections": [COLLECTION_NAME],
                        "to_vertex_collections": [COLLECTION_LAUNCH_SITES],
                    },
                ],
            )

        insurance_vertex_collections = [
            COLLECTION_PARTIES,
            COLLECTION_POLICIES,
            COLLECTION_INSURED_INTERESTS,
            COLLECTION_LOSS_EVENTS,
            COLLECTION_CLAIMS,
            COLLECTION_RISK_SCORES,
            COLLECTION_ANOMALY_PREDICTIONS,
            COLLECTION_SHELLS,
            COLLECTION_KESTRELS,
            COLLECTION_KESTREL_TASKS,
            COLLECTION_COVERAGE_WINDOWS,
        ]
        for vcol_name in insurance_vertex_collections:
            if not db.has_collection(vcol_name):
                db.create_collection(vcol_name)

        insurance_edge_collections = [
            EDGE_INSURANCE_POLICY_COVERS_SAT,
            EDGE_INSURANCE_POLICY_HAS_INTEREST,
            EDGE_INSURANCE_INTEREST_HELD_BY,
            EDGE_INSURANCE_CLAIM_ARISES_FROM,
            EDGE_INSURANCE_LOSS_EVENT_INVOLVES,
            EDGE_INSURANCE_SAT_IN_SHELL,
            EDGE_INSURANCE_RISK_SCORE_FOR,
            EDGE_INSURANCE_PREDICTION_FOR,
            EDGE_INSURANCE_KESTREL_OBSERVED,
            EDGE_INSURANCE_KESTREL_CAN_SEE,
            EDGE_INSURANCE_TASK_TARGETS,
            EDGE_INSURANCE_EVENT_WITNESSED_BY,
        ]
        for ecol_name in insurance_edge_collections:
            if not db.has_collection(ecol_name):
                db.create_collection(ecol_name, edge=True)

        if not db.has_graph(INSURANCE_GRAPH_NAME):
            db.create_graph(
                INSURANCE_GRAPH_NAME,
                edge_definitions=[
                    {
                        "edge_collection": EDGE_INSURANCE_POLICY_COVERS_SAT,
                        "from_vertex_collections": [COLLECTION_POLICIES],
                        "to_vertex_collections": [COLLECTION_NAME],
                    },
                    {
                        "edge_collection": EDGE_INSURANCE_POLICY_HAS_INTEREST,
                        "from_vertex_collections": [COLLECTION_POLICIES],
                        "to_vertex_collections": [COLLECTION_INSURED_INTERESTS],
                    },
                    {
                        "edge_collection": EDGE_INSURANCE_INTEREST_HELD_BY,
                        "from_vertex_collections": [COLLECTION_INSURED_INTERESTS],
                        "to_vertex_collections": [COLLECTION_PARTIES],
                    },
                    {
                        "edge_collection": EDGE_INSURANCE_CLAIM_ARISES_FROM,
                        "from_vertex_collections": [COLLECTION_CLAIMS],
                        "to_vertex_collections": [COLLECTION_LOSS_EVENTS],
                    },
                    {
                        "edge_collection": EDGE_INSURANCE_LOSS_EVENT_INVOLVES,
                        "from_vertex_collections": [COLLECTION_LOSS_EVENTS],
                        "to_vertex_collections": [COLLECTION_NAME],
                    },
                    {
                        "edge_collection": EDGE_INSURANCE_SAT_IN_SHELL,
                        "from_vertex_collections": [COLLECTION_NAME],
                        "to_vertex_collections": [COLLECTION_SHELLS],
                    },
                    {
                        "edge_collection": EDGE_INSURANCE_RISK_SCORE_FOR,
                        "from_vertex_collections": [COLLECTION_RISK_SCORES],
                        "to_vertex_collections": [COLLECTION_NAME],
                    },
                    {
                        "edge_collection": EDGE_INSURANCE_PREDICTION_FOR,
                        "from_vertex_collections": [COLLECTION_ANOMALY_PREDICTIONS],
                        "to_vertex_collections": [COLLECTION_NAME],
                    },
                    {
                        "edge_collection": EDGE_INSURANCE_KESTREL_OBSERVED,
                        "from_vertex_collections": [COLLECTION_KESTRELS],
                        "to_vertex_collections": [COLLECTION_OBSERVATIONS],
                    },
                    {
                        "edge_collection": EDGE_INSURANCE_KESTREL_CAN_SEE,
                        "from_vertex_collections": [COLLECTION_KESTRELS],
                        "to_vertex_collections": [COLLECTION_NAME],
                    },
                    {
                        "edge_collection": EDGE_INSURANCE_TASK_TARGETS,
                        "from_vertex_collections": [COLLECTION_KESTREL_TASKS],
                        "to_vertex_collections": [COLLECTION_NAME],
                    },
                    {
                        "edge_collection": EDGE_INSURANCE_EVENT_WITNESSED_BY,
                        "from_vertex_collections": [COLLECTION_LOSS_EVENTS],
                        "to_vertex_collections": [COLLECTION_KESTRELS],
                    },
                ],
            )

        pkg = sys.modules.get('database')
        if pkg is not None:
            pkg.db = db
            pkg.satellites_collection = satellites_collection
            pkg.objects_collection = satellites_collection

        print(f"Connected to ArangoDB: {DB_NAME}.{COLLECTION_NAME}")
        return True
    except Exception as e:
        print(f"Failed to connect to ArangoDB: {e}")
        return False


def connect_mongodb():
    """Initialize ArangoDB connection (kept name for backward compatibility)"""
    return connect_arangodb()


def disconnect_arangodb():
    """Close ArangoDB connection"""
    global client
    if client:
        client.close()


def disconnect_mongodb():
    """Close ArangoDB connection (kept name for backward compatibility)"""
    disconnect_arangodb()


def get_objects_collection():
    """Get objects collection (lazy initialization)"""
    global satellites_collection
    if satellites_collection is None:
        connect_arangodb()
    return satellites_collection


def get_satellites_collection():
    """Get objects collection (deprecated alias for get_objects_collection)"""
    return get_objects_collection()
