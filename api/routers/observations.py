from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator, model_validator, ConfigDict
from typing import Optional
from datetime import datetime
import csv
import io
import json as json_module

import database as db_module
from database.connection import COLLECTION_OBSERVATIONS
from database.observation_graph_ops import create_edges_for_observation

router = APIRouter(tags=["observations"])

ALLOWED_SORT_FIELDS = {
    'norad_id', 'observation_epoch', 'pass_id', 'frame_index', 'observation_mode',
    'sensors_active', 'illumination', 'source', 'object_name', 'object_type',
    'origin_country', 'estimated_mass_kg', 'spin_rate_rpm', 'derived_health_score',
    'attitude.roll_deg', 'attitude.pitch_deg', 'attitude.yaw_deg', 'attitude.stability_flag',
    'thermal.surface_temp_K', 'thermal.temp_variance_30d', 'thermal.anomaly_flag',
    'material_signature.reflectivity_index', 'material_signature.inferred_material',
    'material_signature.material_confidence',
    'proximity_state.range_km', 'proximity_state.relative_velocity_ms',
    'maneuver_indicator.delta_v_residual_ms', 'maneuver_indicator.maneuver_confidence',
    'maneuver_indicator.maneuver_flag',
    'orbital_decay_indicator.perigee_drift_km_per_day', 'orbital_decay_indicator.estimated_perigee_km',
}


def get_observations_collection():
    db = db_module.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    if not db.has_collection(COLLECTION_OBSERVATIONS):
        raise HTTPException(status_code=503, detail="Observations collection not found")
    return db.collection(COLLECTION_OBSERVATIONS)


class ThermalData(BaseModel):
    model_config = ConfigDict(extra='allow')
    anomaly_flag: Optional[bool] = None


class ObservationInput(BaseModel):
    model_config = ConfigDict(extra='allow')

    norad_id: int
    observation_epoch: str
    source: str
    object_name: Optional[str] = None
    object_type: Optional[str] = None
    origin_country: Optional[str] = None
    derived_health_score: Optional[float] = None
    estimated_mass_kg: Optional[float] = None
    spin_rate_rpm: Optional[float] = None
    thermal: Optional[ThermalData] = None

    @field_validator('norad_id')
    @classmethod
    def norad_id_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('norad_id must be a positive integer')
        return v

    @field_validator('observation_epoch')
    @classmethod
    def valid_iso_epoch(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError('observation_epoch must be a valid ISO 8601 datetime string')
        return v

    @field_validator('source')
    @classmethod
    def source_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('source must not be empty')
        return v.strip()

    @field_validator('estimated_mass_kg')
    @classmethod
    def mass_non_negative(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError('estimated_mass_kg must be non-negative')
        return v

    @field_validator('spin_rate_rpm')
    @classmethod
    def spin_non_negative(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError('spin_rate_rpm must be non-negative')
        return v

    @field_validator('derived_health_score')
    @classmethod
    def health_score_range(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 100.0):
            raise ValueError('derived_health_score must be between 0 and 100')
        return v


class ObservationImportRequest(BaseModel):
    observations: list[ObservationInput]

    @model_validator(mode='after')
    def list_not_empty(self) -> 'ObservationImportRequest':
        if not self.observations:
            raise ValueError('observations list must not be empty')
        return self


@router.post("/v2/observations/import")
def import_observations(body: ObservationImportRequest):
    db = db_module.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if not db.has_collection(COLLECTION_OBSERVATIONS):
        raise HTTPException(status_code=503, detail="Observations collection not found")

    observations = body.observations

    norad_ids = list({obs.norad_id for obs in observations})
    allowed_cursor = db.aql.execute(
        """
        FOR sat IN satellites
            FILTER sat.canonical.norad_cat_id IN @norad_ids
            FILTER sat.canonical.observations_enabled == true
            RETURN sat.canonical.norad_cat_id
        """,
        bind_vars={"norad_ids": norad_ids}
    )
    allowed_set = set(list(allowed_cursor))

    dedup_keys = [(obs.norad_id, obs.observation_epoch, obs.source) for obs in observations]
    dedup_norad_ids = [k[0] for k in dedup_keys]
    dedup_epochs = [k[1] for k in dedup_keys]
    dedup_sources = [k[2] for k in dedup_keys]
    existing_cursor = db.aql.execute(
        """
        FOR obs IN observations
            FILTER obs.norad_id IN @norad_ids
            FILTER obs.observation_epoch IN @epochs
            FILTER obs.source IN @sources
            RETURN {norad_id: obs.norad_id, observation_epoch: obs.observation_epoch, source: obs.source}
        """,
        bind_vars={
            "norad_ids": dedup_norad_ids,
            "epochs": dedup_epochs,
            "sources": dedup_sources,
        }
    )
    existing_set = {
        (r["norad_id"], r["observation_epoch"], r["source"])
        for r in list(existing_cursor)
    }

    inserted = 0
    skipped_duplicates = 0
    skipped_not_allowed = 0
    errors = []

    for obs in observations:
        key = (obs.norad_id, obs.observation_epoch, obs.source)

        if obs.norad_id not in allowed_set:
            skipped_not_allowed += 1
            errors.append({
                "norad_id": obs.norad_id,
                "observation_epoch": obs.observation_epoch,
                "source": obs.source,
                "error": "norad_id not in allowed tracking list",
            })
            continue

        if key in existing_set:
            skipped_duplicates += 1
            continue

        doc = obs.model_dump(exclude_none=True)
        if doc.get("thermal") is not None:
            doc["thermal"] = obs.thermal.model_dump(exclude_none=True)

        try:
            result = db.collection(COLLECTION_OBSERVATIONS).insert(doc, return_new=True)
            existing_set.add(key)
            inserted += 1
            # Create graph edges for the new observation
            try:
                create_edges_for_observation(result["new"])
            except Exception:
                pass  # edge creation is best-effort; don't fail the import
        except Exception as e:
            errors.append({
                "norad_id": obs.norad_id,
                "observation_epoch": obs.observation_epoch,
                "source": obs.source,
                "error": str(e),
            })

    return {
        "inserted": inserted,
        "skipped_duplicates": skipped_duplicates,
        "skipped_not_allowed": skipped_not_allowed,
        "errors": errors,
        "total_submitted": len(observations),
    }


@router.get("/v2/observations/allowed-objects")
def get_allowed_objects():
    db = db_module.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    cursor = db.aql.execute(
        """
        FOR sat IN satellites
            FILTER sat.canonical.observations_enabled == true
            RETURN {
                norad_id: sat.canonical.norad_cat_id,
                name: sat.canonical.name
            }
        """
    )
    results = list(cursor)
    return {"data": results, "total": len(results)}


@router.put("/v2/observations/allowed-objects/{norad_id}")
def enable_observations_for_object(norad_id: int):
    db = db_module.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    cursor = db.aql.execute(
        """
        FOR sat IN satellites
            FILTER sat.canonical.norad_cat_id == @norad_id
            LIMIT 1
            RETURN sat._key
        """,
        bind_vars={"norad_id": norad_id}
    )
    keys = list(cursor)
    if not keys:
        raise HTTPException(status_code=404, detail=f"Satellite with norad_id {norad_id} not found")

    db.aql.execute(
        """
        FOR sat IN satellites
            FILTER sat.canonical.norad_cat_id == @norad_id
            UPDATE sat WITH {canonical: MERGE(sat.canonical, {observations_enabled: true})} IN satellites
        """,
        bind_vars={"norad_id": norad_id}
    )
    return {"norad_id": norad_id, "observations_enabled": True}


@router.delete("/v2/observations/allowed-objects/{norad_id}")
def disable_observations_for_object(norad_id: int):
    db = db_module.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    cursor = db.aql.execute(
        """
        FOR sat IN satellites
            FILTER sat.canonical.norad_cat_id == @norad_id
            LIMIT 1
            RETURN sat._key
        """,
        bind_vars={"norad_id": norad_id}
    )
    keys = list(cursor)
    if not keys:
        raise HTTPException(status_code=404, detail=f"Satellite with norad_id {norad_id} not found")

    db.aql.execute(
        """
        FOR sat IN satellites
            FILTER sat.canonical.norad_cat_id == @norad_id
            UPDATE sat WITH {canonical: MERGE(sat.canonical, {observations_enabled: false})} IN satellites
        """,
        bind_vars={"norad_id": norad_id}
    )
    return {"norad_id": norad_id, "observations_enabled": False}


@router.get("/v2/observations/filter-options")
def get_observation_filter_options():
    db = db_module.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    cursor = db.aql.execute("""
    RETURN {
        sources: (FOR obs IN observations COLLECT s = obs.source INTO g FILTER s != null SORT s RETURN s),
        object_types: (FOR obs IN observations COLLECT t = obs.object_type INTO g FILTER t != null SORT t RETURN t),
        origin_countries: (FOR obs IN observations COLLECT c = obs.origin_country INTO g FILTER c != null SORT c RETURN c)
    }
    """)
    result = next(iter(list(cursor)), {"sources": [], "object_types": [], "origin_countries": []})
    return result


@router.get("/v2/observations")
def get_all_observations(
    source: Optional[str] = None,
    object_type: Optional[str] = None,
    origin_country: Optional[str] = None,
    search: Optional[str] = None,
    has_anomaly: Optional[bool] = None,
    health_score_min: Optional[float] = None,
    health_score_max: Optional[float] = None,
    epoch_from: Optional[str] = None,
    epoch_to: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = 'observation_epoch',
    sort_order: str = 'DESC',
):
    db = db_module.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = 'observation_epoch'
    sort_order = 'ASC' if sort_order.upper() == 'ASC' else 'DESC'

    filter_clauses = []
    bind_vars = {'skip': skip, 'limit': limit}

    if search:
        filter_clauses.append('CONTAINS(LOWER(obs.object_name), LOWER(@search))')
        bind_vars['search'] = search
    if source:
        filter_clauses.append('obs.source == @source')
        bind_vars['source'] = source
    if object_type:
        filter_clauses.append('obs.object_type == @object_type')
        bind_vars['object_type'] = object_type
    if origin_country:
        filter_clauses.append('CONTAINS(LOWER(obs.origin_country), LOWER(@origin_country))')
        bind_vars['origin_country'] = origin_country
    if has_anomaly:
        filter_clauses.append('obs.thermal.anomaly_flag == true')
    if health_score_min is not None:
        filter_clauses.append('obs.derived_health_score >= @health_score_min')
        bind_vars['health_score_min'] = health_score_min
    if health_score_max is not None:
        filter_clauses.append('obs.derived_health_score <= @health_score_max')
        bind_vars['health_score_max'] = health_score_max
    if epoch_from:
        filter_clauses.append('obs.observation_epoch >= @epoch_from')
        bind_vars['epoch_from'] = epoch_from
    if epoch_to:
        filter_clauses.append('obs.observation_epoch <= @epoch_to')
        bind_vars['epoch_to'] = epoch_to

    filter_str = '\n'.join(f'    FILTER {clause}' for clause in filter_clauses)

    query = f"""
    FOR obs IN observations
    {filter_str}
    SORT obs.{sort_by} {sort_order}
    LIMIT @skip, @limit
    RETURN obs
    """

    count_query = f"""
    FOR obs IN observations
    {filter_str}
    COLLECT WITH COUNT INTO total
    RETURN total
    """

    cursor = db.aql.execute(query, bind_vars=bind_vars)
    results = list(cursor)

    count_bind_vars = {k: v for k, v in bind_vars.items() if k not in ('skip', 'limit')}
    count_cursor = db.aql.execute(count_query, bind_vars=count_bind_vars)
    total = next(iter(list(count_cursor)), 0)

    return {
        "data": results,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


class AqlQueryRequest(BaseModel):
    query: str
    bind_vars: Optional[dict] = None
    format: Optional[str] = None  # "json", "csv", or None (default JSON response)


@router.get("/v2/observations/analytics/health-over-time")
def get_health_over_time(granularity: Optional[str] = "daily"):
    db = db_module.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if granularity == "weekly":
        # Group by year and week (calculated using day of year)
        date_expression = "CONCAT(LEFT(obs.observation_epoch, 4), '-W', TO_STRING(FLOOR((DATE_DAYOFYEAR(obs.observation_epoch) - 1) / 7) + 1))"
    else:
        # Default to daily
        date_expression = "LEFT(obs.observation_epoch, 10)"

    cursor = db.aql.execute(
        f"""
        FOR obs IN observations
            FILTER obs.observation_epoch != null AND obs.derived_health_score != null
            LET period = {date_expression}
            COLLECT date = period AGGREGATE average_health_score = AVERAGE(obs.derived_health_score)
            SORT date ASC
            RETURN {{ date, average_health_score }}
        """
    )
    return list(cursor)


@router.get("/v2/observations/analytics/anomaly-distribution")
def get_anomaly_distribution(by: Optional[str] = None):
    db = db_module.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if by in ['source', 'object_type']:
        query = f"""
        FOR obs IN observations
            FILTER obs.thermal.anomaly_flag == true
            COLLECT group = obs.{by} WITH COUNT INTO count
            FILTER group != null
            SORT count DESC
            RETURN {{ label: group, value: count }}
        """
    else:
        query = """
        FOR obs IN observations
            COLLECT has_anomaly = (obs.thermal.anomaly_flag == true) WITH COUNT INTO count
            RETURN { label: has_anomaly ? "Anomaly" : "Normal", value: count }
        """

    cursor = db.aql.execute(query)
    return list(cursor)


@router.get("/v2/observations/analytics/source-distribution")
def get_source_distribution():
    db = db_module.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    cursor = db.aql.execute(
        """
        FOR obs IN observations
            COLLECT source = obs.source WITH COUNT INTO count
            FILTER source != null
            SORT count DESC
            RETURN { label: source, value: count }
        """
    )
    return list(cursor)


@router.post("/v2/observations/aql")
def execute_custom_aql(request: AqlQueryRequest, fast_request: Request):
    db = db_module.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    # Security: restrict AQL execution to administrators
    from api.routers.auth import _demo_token_store
    auth_header = fast_request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):]
        if token in _demo_token_store:
            raise HTTPException(status_code=403, detail="AQL execution is restricted to administrators")

    try:
        cursor = db.aql.execute(request.query, bind_vars=request.bind_vars or {})
        results = list(cursor)

        # Export as downloadable CSV
        if request.format == "csv":
            return _results_to_csv_response(results)

        # Export as downloadable JSON file
        if request.format == "json_file":
            content = json_module.dumps(results, indent=2, default=str)
            return StreamingResponse(
                io.BytesIO(content.encode()),
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=aql_export.json"},
            )

        return {
            "data": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/v2/observations/{norad_id}")
def get_observations(norad_id: int, limit: Optional[int] = 100, offset: Optional[int] = 0):
    db = db_module.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    cursor = db.aql.execute(
        """
        FOR obs IN observations
        FILTER obs.norad_id == @norad_id
        SORT obs.observation_epoch DESC
        LIMIT @offset, @limit
        RETURN obs
        """,
        bind_vars={"norad_id": norad_id, "offset": offset, "limit": limit}
    )
    results = list(cursor)

    count_cursor = db.aql.execute(
        "FOR obs IN observations FILTER obs.norad_id == @norad_id COLLECT WITH COUNT INTO total RETURN total",
        bind_vars={"norad_id": norad_id}
    )
    total = next(iter(list(count_cursor)), 0)

    return {
        "data": results,
        "total": total,
        "norad_id": norad_id,
        "limit": limit,
        "offset": offset
    }


def _results_to_csv_response(results):
    """Convert AQL query results to a downloadable CSV StreamingResponse."""
    if not results:
        output = io.StringIO()
        output.write("")
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=aql_export.csv"},
        )

    # Flatten nested dicts for CSV columns
    def flatten(obj, parent_key=""):
        items = {}
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_key = f"{parent_key}.{k}" if parent_key else k
                if isinstance(v, dict):
                    items.update(flatten(v, new_key))
                elif isinstance(v, (list, tuple)):
                    items[new_key] = json_module.dumps(v, default=str)
                else:
                    items[new_key] = v
        else:
            items[parent_key or "value"] = obj
        return items

    flat_rows = [flatten(r) for r in results]
    all_keys = []
    seen = set()
    for row in flat_rows:
        for k in row:
            if k not in seen:
                all_keys.append(k)
                seen.add(k)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=all_keys, extrasaction="ignore")
    writer.writeheader()
    for row in flat_rows:
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=aql_export.csv"},
    )
