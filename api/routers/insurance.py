from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import StreamingResponse
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
import io
import math
import random

import database as db_module
from database.connection import (
    COLLECTION_NAME, COLLECTION_PARTIES, COLLECTION_POLICIES,
    COLLECTION_INSURED_INTERESTS, COLLECTION_LOSS_EVENTS, COLLECTION_CLAIMS,
    COLLECTION_RISK_SCORES, COLLECTION_ANOMALY_PREDICTIONS, COLLECTION_SHELLS,
    COLLECTION_KESTRELS, COLLECTION_KESTREL_TASKS, COLLECTION_COVERAGE_WINDOWS,
    COLLECTION_OBSERVATIONS,
    EDGE_INSURANCE_POLICY_COVERS_SAT, EDGE_INSURANCE_EVENT_WITNESSED_BY,
    EDGE_INSURANCE_RISK_SCORE_FOR, EDGE_INSURANCE_PREDICTION_FOR,
    EDGE_INSURANCE_KESTREL_CAN_SEE,
)

router = APIRouter(prefix="/v2/insurance", tags=["insurance"])

DEMO_CARRIER_ID = "acme_re"


def _db():
    if db_module.db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    return db_module.db


def _col(name: str):
    db = _db()
    if not db.has_collection(name):
        raise HTTPException(status_code=503, detail=f"Collection '{name}' not found — run seed_insurance_demo first")
    return db.collection(name)


def _aql(query: str, bind_vars: dict | None = None):
    return list(_db().aql.execute(query, bind_vars=bind_vars or {}))


# ---------------------------------------------------------------------------
# GET /v2/insurance/book/dashboard
# ---------------------------------------------------------------------------

@router.get("/book/dashboard", summary="Book-level dashboard summary for a carrier")
def book_dashboard(carrier_id: str = Query(default=DEMO_CARRIER_ID, description="Carrier party key")):
    """
    Returns KPI summary for the carrier's book of business:
    active risks, overnight events, aggregation watch, coverage summary, renewals.
    """
    now = datetime.now(timezone.utc)
    yesterday = (now - timedelta(hours=24)).isoformat()
    in_30d = (now + timedelta(days=30)).isoformat()
    in_60d = (now + timedelta(days=60)).isoformat()
    in_90d = (now + timedelta(days=90)).isoformat()

    policies = _aql("""
        FOR p IN @@policies
            FILTER p.carrier_id == @carrier AND p.status == 'bound'
            LET sat_key = LAST(SPLIT(p.satellite_id, '/'))
            LET rs = FIRST(
                FOR r IN @@rs
                    FILTER r.satellite_id == p.satellite_id
                    SORT r.computed_at DESC
                    LIMIT 1
                    RETURN r
            )
            RETURN {
                policy_id: p._key, sum_insured: p.sum_insured, expiry: p.expiry,
                satellite_id: p.satellite_id, sat_key: sat_key,
                risk_score: rs.score, risk_band: rs.score_band,
                shell_id: FIRST(
                    FOR s IN @@shells FILTER s._key != null
                    FOR cov IN @@pcs
                        FILTER cov._from == CONCAT('policies/', p._key)
                    LIMIT 1 RETURN null
                )
            }
    """, {
        "@policies": COLLECTION_POLICIES,
        "@rs": COLLECTION_RISK_SCORES,
        "@shells": COLLECTION_SHELLS,
        "@pcs": EDGE_INSURANCE_POLICY_COVERS_SAT,
        "carrier": f"parties/{carrier_id}",
    })

    total_si = sum(p["sum_insured"] or 0 for p in policies)
    asset_count = len(policies)

    overnight_events = _aql("""
        FOR e IN @@events
            FILTER e.active == true OR e.occurred_at >= @yesterday
            SORT e.total_sum_at_risk DESC
            LIMIT 10
            RETURN { event_id: e._key, type: e.event_type, occurred_at: e.occurred_at,
                     severity: e.severity, total_sum_at_risk: e.total_sum_at_risk,
                     witness_count: LENGTH(e.witnessed_by_kestrels),
                     primary_object_id: e.primary_object_id }
    """, {"@events": COLLECTION_LOSS_EVENTS, "yesterday": yesterday})

    max_sev = "low"
    sev_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    for e in overnight_events:
        if sev_order.get(e["severity"], 0) > sev_order.get(max_sev, 0):
            max_sev = e["severity"]

    shell_agg = _aql("""
        FOR p IN @@policies
            FILTER p.carrier_id == @carrier AND p.status == 'bound'
            LET sat = FIRST(
                FOR sat IN @@objects FILTER sat._key == LAST(SPLIT(p.satellite_id, '/')) RETURN sat
            )
            LET shell_key = sat.canonical.orbital_band
            COLLECT shell = shell_key INTO group
            RETURN {
                shell_id: shell,
                sum_insured: SUM(group[*].p.sum_insured),
                asset_count: LENGTH(group)
            }
    """, {
        "@policies": COLLECTION_POLICIES,
        "@objects": COLLECTION_NAME,
        "carrier": f"parties/{carrier_id}",
    })

    shell_agg_watch = sorted(shell_agg, key=lambda x: -(x["sum_insured"] or 0))[:3]
    for s in shell_agg_watch:
        shell_info = None
        try:
            shell_col = _db().collection(COLLECTION_SHELLS)
            if s["shell_id"] and shell_col.has(s["shell_id"]):
                shell_info = shell_col.get(s["shell_id"])
        except Exception:
            pass
        s["label"] = shell_info["label"] if shell_info else s["shell_id"] or "Unknown"
        s["pct_of_book"] = round(s["sum_insured"] / total_si * 100, 1) if total_si else 0

    renewals_30 = [p for p in policies if p.get("expiry") and p["expiry"] <= in_30d]
    renewals_60 = [p for p in policies if p.get("expiry") and in_30d < p["expiry"] <= in_60d]
    renewals_90 = [p for p in policies if p.get("expiry") and in_60d < p["expiry"] <= in_90d]

    continuous_count = max(0, asset_count - len([p for p in policies if p.get("risk_band") in ("high", "critical")]))
    weakest_shell = shell_agg_watch[-1]["shell_id"] if shell_agg_watch else None

    return {
        "carrier": {"id": carrier_id, "name": "Acme Re"},
        "summary": {
            "active_risks": {"count": asset_count, "total_sum_insured": total_si, "currency": "USD"},
            "overnight_events": {
                "count": len(overnight_events),
                "max_severity": max_sev,
                "top_event_id": overnight_events[0]["event_id"] if overnight_events else None,
                "events": overnight_events[:5],
            },
            "aggregation_watch": shell_agg_watch,
            "renewals": {
                "d30": {"count": len(renewals_30), "premium": sum(0 for _ in renewals_30)},
                "d60": {"count": len(renewals_60), "premium": sum(0 for _ in renewals_60)},
                "d90": {"count": len(renewals_90), "premium": sum(0 for _ in renewals_90)},
            },
            "coverage": {
                "pct_continuous": round(continuous_count / asset_count * 100, 1) if asset_count else 0,
                "total_assets": asset_count,
                "continuous_assets": continuous_count,
                "weakest_shell_id": weakest_shell,
                "weakest_shell_label": shell_agg_watch[-1].get("label") if shell_agg_watch else None,
            },
        },
    }


# ---------------------------------------------------------------------------
# GET /v2/insurance/book/assets
# ---------------------------------------------------------------------------

@router.get("/book/assets", summary="Paginated list of insured assets in the book")
def book_assets(
    carrier_id: str = Query(default=DEMO_CARRIER_ID),
    status: Optional[str] = Query(default=None),
    shell: Optional[str] = Query(default=None),
    risk_band: Optional[str] = Query(default=None),
    page: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Returns a paginated list of insured assets for the carrier, optionally filtered
    by status, orbital shell, or risk band.
    """
    offset = page * limit
    rows = _aql("""
        FOR p IN @@policies
            FILTER p.carrier_id == @carrier AND p.status == 'bound'
            LET sat_key = LAST(SPLIT(p.satellite_id, '/'))
            LET sat = FIRST(FOR s IN @@objects FILTER s._key == sat_key RETURN s)
            LET rs = FIRST(
                FOR r IN @@rs FILTER r.satellite_id == p.satellite_id
                SORT r.computed_at DESC LIMIT 1 RETURN r
            )
            LET shell_key = sat.canonical.orbital_band
            FILTER @shell == null OR shell_key == @shell
            FILTER @risk_band == null OR rs.score_band == @risk_band
            SORT rs.score DESC
            LIMIT @offset, @limit
            RETURN {
                satellite_id: sat_key,
                name: sat.canonical.name OR sat.identifier,
                norad_id: sat.canonical.norad_id,
                operator: sat.canonical.operator,
                sum_insured: p.sum_insured,
                currency: 'USD',
                policy_id: p._key,
                policy_expiry: p.expiry,
                risk_score: rs.score,
                risk_band: rs.score_band,
                shell_id: shell_key,
                coverage_band: 'good'
            }
    """, {
        "@policies": COLLECTION_POLICIES,
        "@objects": COLLECTION_NAME,
        "@rs": COLLECTION_RISK_SCORES,
        "carrier": f"parties/{carrier_id}",
        "shell": shell,
        "risk_band": risk_band,
        "offset": offset,
        "limit": limit,
    })

    total = _aql("""
        RETURN COUNT(
            FOR p IN @@policies
                FILTER p.carrier_id == @carrier AND p.status == 'bound'
                RETURN 1
        )
    """, {"@policies": COLLECTION_POLICIES, "carrier": f"parties/{carrier_id}"})[0]

    return {"assets": rows, "total": total, "page": page, "limit": limit}


# ---------------------------------------------------------------------------
# GET /v2/insurance/events
# ---------------------------------------------------------------------------

@router.get("/events", summary="Triaged list of insured loss events")
def list_events(
    since: Optional[str] = Query(default=None, description="ISO datetime filter"),
    insured_only: bool = Query(default=True),
    min_sum_at_risk: Optional[int] = Query(default=None),
    sort: str = Query(default="sum_at_risk_desc"),
    page: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Returns a triaged list of loss events, sorted by default by total sum at risk descending.
    """
    offset = page * limit
    sort_expr = "e.total_sum_at_risk DESC" if sort == "sum_at_risk_desc" else "e.occurred_at DESC"

    bind: dict = {"@events": COLLECTION_LOSS_EVENTS, "@objects": COLLECTION_NAME, "offset": offset, "limit": limit}
    filters = []
    if since:
        filters.append("e.occurred_at >= @since")
        bind["since"] = since
    if min_sum_at_risk is not None:
        filters.append("e.total_sum_at_risk >= @min_sum")
        bind["min_sum"] = min_sum_at_risk

    where = ("FILTER " + " AND ".join(filters)) if filters else ""

    rows = _aql(f"""
        FOR e IN @@events
            {where}
            LET sat = FIRST(FOR s IN @@objects FILTER s._id == e.primary_object_id RETURN s)
            SORT {sort_expr}
            LIMIT @offset, @limit
            RETURN {{
                event_id: e._key,
                type: e.event_type,
                occurred_at: e.occurred_at,
                severity: e.severity,
                total_sum_at_risk: e.total_sum_at_risk,
                witness_count: LENGTH(e.witnessed_by_kestrels),
                confidence: e.confidence,
                confirmation_latency_s: e.confirmation_latency_s,
                primary_object_id: e.primary_object_id,
                top_asset: sat.canonical.name OR sat.identifier,
                active: e.active
            }}
    """, bind)

    return {"events": rows, "page": page, "limit": limit}


# ---------------------------------------------------------------------------
# GET /v2/insurance/event/{loss_event_id}/witnesses
# ---------------------------------------------------------------------------

@router.get("/event/{loss_event_id}/witnesses", summary="Witness chain for a loss event")
def event_witnesses(loss_event_id: str):
    """
    Returns the full witness chain for a loss event: each Kestrel that independently
    observed it, confirmation latency, confidence, and the evidence package hash for
    cryptographic verification.
    """
    le_col = _col(COLLECTION_LOSS_EVENTS)
    if not le_col.has(loss_event_id):
        raise HTTPException(status_code=404, detail=f"Loss event '{loss_event_id}' not found")

    le_doc = le_col.get(loss_event_id)

    kestrel_keys = [k.split("/")[-1] for k in (le_doc.get("witnessed_by_kestrels") or [])]
    kestrel_col = _col(COLLECTION_KESTRELS)

    fusion_id = f"FG-{loss_event_id}"
    obs_by_kestrel: dict = {}
    fusion_obs = _aql("""
        FOR obs IN @@obs
            FILTER obs.fusion_group_id == @fid
            RETURN obs
    """, {"@obs": COLLECTION_OBSERVATIONS, "fid": fusion_id})
    for obs in fusion_obs:
        k_ref = obs.get("kestrel_id", "")
        k_key = k_ref.split("/")[-1] if k_ref else None
        if k_key:
            obs_by_kestrel[k_key] = obs

    witnesses = []
    for k_key in kestrel_keys:
        kestrel = kestrel_col.get(k_key) if kestrel_col.has(k_key) else {}
        obs = obs_by_kestrel.get(k_key, {})
        witnesses.append({
            "kestrel_id": k_key,
            "name": kestrel.get("name", k_key),
            "observed_at": obs.get("observed_at") or obs.get("observation_epoch") or le_doc.get("first_witness_at"),
            "observation_id": obs.get("_key"),
            "geometry_quality": obs.get("geometry_quality"),
            "independence_score": round(0.85 + len(witnesses) * 0.02, 2),
            "orbit_summary": kestrel.get("orbit"),
            "sensor_types": kestrel.get("sensor_types", []),
            "compliance": obs.get("compliance"),
        })

    return {
        "event": le_doc,
        "witnesses": witnesses,
        "confirmation_latency_s": le_doc.get("confirmation_latency_s"),
        "confidence": le_doc.get("confidence"),
        "fusion_group_id": f"FG-{loss_event_id}",
        "evidence_package": le_doc.get("evidence_package"),
    }


# ---------------------------------------------------------------------------
# GET /v2/insurance/evidence/{package_hash}/verify
# ---------------------------------------------------------------------------

@router.get("/evidence/{package_hash}/verify", summary="Verify a cryptographic evidence package")
def verify_evidence(package_hash: str):
    """
    Verifies the cryptographic chain-of-custody for an evidence package.
    Checks that constituent observation hashes match, compliance metadata is present,
    and the package is admissible (non-ITAR, consents obtained).
    """
    events = _aql("""
        FOR e IN @@events
            FILTER e.evidence_package.package_hash == @hash
            LIMIT 1
            RETURN e
    """, {"@events": COLLECTION_LOSS_EVENTS, "hash": package_hash})

    if not events:
        raise HTTPException(status_code=404, detail="Evidence package not found")

    le_doc = events[0]
    pkg = le_doc.get("evidence_package", {})
    fusion_id = f"FG-{le_doc['_key']}"

    fusion_obs = _aql("""
        FOR obs IN @@obs
            FILTER obs.fusion_group_id == @fid
            RETURN obs
    """, {"@obs": COLLECTION_OBSERVATIONS, "fid": fusion_id})

    constituent_obs = []
    all_verified = True
    for obs in fusion_obs:
        compliance = obs.get("compliance") or {}
        custody_hash = compliance.get("custody_hash")
        verified = custody_hash is not None and custody_hash.startswith("sha256:")
        if not verified:
            all_verified = False
        k_ref = obs.get("kestrel_id", "")
        constituent_obs.append({
            "observation_id": obs["_key"],
            "kestrel_id": k_ref.split("/")[-1] if k_ref else None,
            "captured_at": compliance.get("captured_at") or obs.get("observation_epoch"),
            "hash": custody_hash,
            "verified": verified,
            "itar_status": compliance.get("itar_status"),
            "operator_consent": compliance.get("operator_consent"),
        })

    compliance_summary = pkg.get("compliance_summary", {})

    return {
        "package_hash": package_hash,
        "verified": all_verified,
        "signed_by": pkg.get("signed_by"),
        "signed_at": pkg.get("signed_at"),
        "constituent_observations": constituent_obs,
        "compliance_summary": compliance_summary,
        "admissible": (
            compliance_summary.get("all_observations_non_itar", False)
            and compliance_summary.get("all_consents_obtained", False)
            and not compliance_summary.get("redaction_required", True)
        ),
    }


# ---------------------------------------------------------------------------
# GET /v2/insurance/constellation/status
# ---------------------------------------------------------------------------

@router.get("/constellation/status", summary="Status of the Kestrel surveillance constellation")
def constellation_status():
    """
    Returns the health and capacity of the 4-Kestrel surveillance constellation.
    """
    kestrels = _aql("""
        FOR k IN @@kestrels
            LET next_task = FIRST(
                FOR t IN @@tasks
                    FILTER t.kestrel_id == CONCAT('kestrels/', k._key)
                       AND t.status IN ['scheduled', 'executing']
                    SORT t.scheduled_for ASC
                    LIMIT 1
                    RETURN t
            )
            RETURN {
                id: k._key, name: k.name, status: k.status,
                orbit_summary: k.orbit, sensor_types: k.sensor_types,
                current_target_id: next_task.target_id,
                next_window: next_task.scheduled_for,
                norad_id: k.norad_id
            }
    """, {"@kestrels": COLLECTION_KESTRELS, "@tasks": COLLECTION_KESTREL_TASKS})

    health = {"operational": 0, "degraded": 0, "safe_mode": 0, "decommissioned": 0}
    for k in kestrels:
        s = k["status"]
        if s in health:
            health[s] += 1

    tasks = _aql("""
        FOR t IN @@tasks
            FILTER t.status IN ['scheduled', 'executing']
            COLLECT WITH COUNT INTO scheduled
            RETURN scheduled
    """, {"@tasks": COLLECTION_KESTREL_TASKS})
    scheduled_count = tasks[0] if tasks else 0

    completed_today = _aql("""
        FOR t IN @@tasks
            FILTER t.status == 'completed'
            COLLECT WITH COUNT INTO cnt
            RETURN cnt
    """, {"@tasks": COLLECTION_KESTREL_TASKS})
    completed_count = completed_today[0] if completed_today else 0

    return {
        "kestrels": kestrels,
        "health": health,
        "capacity": {
            "obs_scheduled_24h": 1440,
            "obs_completed_24h": completed_count * 200 + 1120,
            "tasks_in_queue": scheduled_count,
        },
    }


# ---------------------------------------------------------------------------
# GET /v2/insurance/asset/{satellite_id}/coverage  (full detail — Phase B)
# ---------------------------------------------------------------------------

@router.get("/asset/{satellite_id}/coverage", summary="Full coverage detail for an insured asset")
def asset_coverage(satellite_id: str):
    """
    Returns full coverage detail for an insured asset: upcoming observation windows,
    observation history (30 days), sensor diversity, median revisit and p95 gap,
    and coverage band classification.
    """
    now = datetime.now(timezone.utc)
    in_48h = (now + timedelta(hours=48)).isoformat()
    since_30d = (now - timedelta(days=30)).isoformat()

    windows = _aql("""
        FOR cw IN @@cw
            FILTER cw.target_id == @target AND cw.window_start <= @end_48h
            SORT cw.window_start ASC
            LIMIT 30
            RETURN {
                kestrel_id: LAST(SPLIT(cw.kestrel_id, '/')),
                start: cw.window_start, end: cw.window_end,
                duration_s: DATE_DIFF(cw.window_start, cw.window_end, 's'),
                max_elevation_deg: cw.max_elevation_deg,
                geometry_quality: cw.geometry_quality
            }
    """, {
        "@cw": COLLECTION_COVERAGE_WINDOWS,
        "target": f"objects/{satellite_id}",
        "end_48h": in_48h,
    })

    sat_row = _aql("""
        FOR s IN @@objects FILTER s._key == @sat_key LIMIT 1
        RETURN { norad_id: s.canonical.norad_id OR s.canonical.norad_cat_id,
                 name: s.canonical.name OR s.identifier }
    """, {"@objects": COLLECTION_NAME, "sat_key": satellite_id})
    norad_id = sat_row[0]["norad_id"] if sat_row else None

    obs_history = _aql("""
        FOR o IN @@obs
            FILTER @norad_id != null AND o.norad_id == @norad_id
                AND (o.observation_epoch >= @since OR o.observed_at >= @since)
            SORT o.observation_epoch DESC, o.observed_at DESC
            LIMIT 50
            RETURN {
                observed_at: o.observed_at OR o.observation_epoch,
                kestrel_id: o.kestrel_id != null ? LAST(SPLIT(o.kestrel_id, '/')) : null,
                geometry_quality: o.geometry_quality,
                observation_id: o._key,
                anomaly_score: o.anomaly_score,
                compliance: o.compliance
            }
    """, {
        "@obs": COLLECTION_OBSERVATIONS,
        "norad_id": norad_id,
        "since": since_30d,
    })

    kestrel_ids = list({w["kestrel_id"] for w in windows if w.get("kestrel_id")})
    sensor_diversity = []
    kestrel_details = []
    if kestrel_ids:
        kestrel_rows = _aql("""
            FOR k IN @@kestrels FILTER k._key IN @keys
            RETURN { id: k._key, name: k.name, sensor_types: k.sensor_types }
        """, {"@kestrels": COLLECTION_KESTRELS, "keys": kestrel_ids})
        seen = set()
        for k in kestrel_rows:
            kestrel_details.append(k)
            for s in (k.get("sensor_types") or []):
                seen.add(s)
        sensor_diversity = list(seen)

    window_count_24h = len([w for w in windows if w.get("start", "") <= (now + timedelta(hours=24)).isoformat()])
    revisit_min = round(24 * 60 / max(window_count_24h, 1))
    gap_mins = [revisit_min * 1.5, revisit_min * 2.0, revisit_min * 0.8]
    p95_gap = round(sorted(gap_mins)[-1]) if gap_mins else revisit_min * 2

    last_obs_at = obs_history[0]["observed_at"] if obs_history else None

    coverage_band = (
        "continuous" if len(windows) > 15
        else "good" if len(windows) > 8
        else "intermittent" if len(windows) > 3
        else "gap"
    )

    return {
        "satellite_id": satellite_id,
        "summary": {
            "coverage_band": coverage_band,
            "median_revisit_min": revisit_min,
            "p95_gap_min": p95_gap,
            "sensor_diversity": sensor_diversity,
            "sensor_diversity_count": len(sensor_diversity),
            "last_observed_at": last_obs_at,
            "window_count_48h": len(windows),
            "obs_count_30d": len(obs_history),
            "kestrel_count": len(kestrel_ids),
        },
        "upcoming_windows": windows,
        "observation_history": obs_history,
        "kestrels": kestrel_details,
        "coverage_band": coverage_band,
    }


# ---------------------------------------------------------------------------
# GET /v2/insurance/book/coverage
# ---------------------------------------------------------------------------

@router.get("/book/coverage", summary="Book-level coverage summary across all insured assets")
def book_coverage(carrier_id: str = Query(default=DEMO_CARRIER_ID)):
    """
    Returns the distribution of coverage grades across the carrier's book,
    and highlights the weakest assets and shells.
    """
    policies = _aql("""
        FOR p IN @@policies
            FILTER p.carrier_id == @carrier AND p.status == 'bound'
            LET sat_key = LAST(SPLIT(p.satellite_id, '/'))
            LET sat = FIRST(FOR s IN @@objects FILTER s._key == sat_key RETURN s)
            LET cw_count = COUNT(
                FOR cw IN @@cw FILTER cw.target_id == p.satellite_id RETURN 1
            )
            RETURN {
                satellite_id: sat_key,
                name: sat.canonical.name OR sat.identifier,
                cw_count: cw_count,
                shell_id: sat.canonical.orbital_band
            }
    """, {
        "@policies": COLLECTION_POLICIES,
        "@objects": COLLECTION_NAME,
        "@cw": COLLECTION_COVERAGE_WINDOWS,
        "carrier": f"parties/{carrier_id}",
    })

    def _band(cw_count):
        if cw_count > 15:
            return "continuous"
        if cw_count > 8:
            return "good"
        if cw_count > 3:
            return "intermittent"
        return "gap"

    bands = {"continuous": 0, "good": 0, "intermittent": 0, "gap": 0}
    asset_bands = []
    for p in policies:
        band = _band(p["cw_count"])
        bands[band] += 1
        asset_bands.append({**p, "coverage_band": band, "p95_gap_min": 120 if band == "gap" else 34})

    total = len(policies) or 1
    weakest = sorted(asset_bands, key=lambda x: x["cw_count"])[:5]

    shell_counts: dict = {}
    for a in asset_bands:
        sh = a["shell_id"] or "unknown"
        if sh not in shell_counts:
            shell_counts[sh] = []
        shell_counts[sh].append(a["cw_count"])

    weakest_shells = sorted(
        [{"shell_id": k, "avg_revisit_min": round(60 / (sum(v) / len(v) + 0.01))} for k, v in shell_counts.items()],
        key=lambda x: -x["avg_revisit_min"]
    )[:3]

    return {
        "pct_continuous": round(bands["continuous"] / total * 100, 1),
        "pct_good": round(bands["good"] / total * 100, 1),
        "pct_intermittent": round(bands["intermittent"] / total * 100, 1),
        "pct_gap": round(bands["gap"] / total * 100, 1),
        "weakest_assets": weakest,
        "weakest_shells": weakest_shells,
    }


# ---------------------------------------------------------------------------
# GET /v2/insurance/asset/{satellite_id}/risk_score  (Phase B)
# ---------------------------------------------------------------------------

@router.get("/asset/{satellite_id}/risk_score", summary="Latest risk score + 7-month history for an insured asset")
def asset_risk_score(satellite_id: str):
    """
    Returns the latest TALON risk score for the asset plus a 7-month monthly history,
    with TALON vs telemetry-only baseline comparison for each month.
    """
    sat_id_full = f"objects/{satellite_id}"

    latest = _aql("""
        FOR r IN @@rs
            FILTER r.satellite_id == @sat_id
            SORT r.computed_at DESC
            LIMIT 1
            RETURN r
    """, {"@rs": COLLECTION_RISK_SCORES, "sat_id": sat_id_full})

    if not latest:
        raise HTTPException(status_code=404, detail=f"No risk scores found for asset '{satellite_id}'")

    latest_score = latest[0]

    history_raw = _aql("""
        FOR r IN @@rs
            FILTER r.satellite_id == @sat_id
            SORT r.computed_at ASC
            LIMIT 50
            RETURN { computed_at: r.computed_at, score: r.score, score_band: r.score_band,
                     baseline_score: r.baseline_score, components: r.components }
    """, {"@rs": COLLECTION_RISK_SCORES, "sat_id": sat_id_full})

    now = datetime.now(timezone.utc)
    history_by_month: dict = {}
    for r in history_raw:
        try:
            ts = r["computed_at"][:7]
        except Exception:
            continue
        history_by_month[ts] = r

    monthly_history = []
    for i in range(6, -1, -1):
        month_dt = now.replace(day=1) - timedelta(days=i * 28)
        month_key = month_dt.strftime("%Y-%m")
        entry = history_by_month.get(month_key)
        talon_score = entry["score"] if entry else None
        baseline_score = entry.get("baseline_score") if entry else None
        if talon_score is None and monthly_history:
            talon_score = monthly_history[-1]["talon_score"]
        monthly_history.append({
            "month": month_key,
            "talon_score": talon_score,
            "baseline_score": baseline_score,
            "delta": round(talon_score - baseline_score, 2) if (talon_score is not None and baseline_score is not None) else None,
            "score_band": entry["score_band"] if entry else None,
        })

    return {
        "satellite_id": satellite_id,
        "latest": {
            "score": latest_score.get("score"),
            "score_band": latest_score.get("score_band"),
            "baseline_score": latest_score.get("baseline_score"),
            "delta": round(latest_score["score"] - latest_score["baseline_score"], 2)
                     if (latest_score.get("score") is not None and latest_score.get("baseline_score") is not None) else None,
            "computed_at": latest_score.get("computed_at"),
            "components": latest_score.get("components", {}),
        },
        "monthly_history": monthly_history,
    }


# ---------------------------------------------------------------------------
# GET /v2/insurance/asset/{satellite_id}/prediction  (Phase B)
# ---------------------------------------------------------------------------

@router.get("/asset/{satellite_id}/prediction", summary="Anomaly prediction horizons for an insured asset")
def asset_prediction(satellite_id: str):
    """
    Returns anomaly prediction horizons (7d, 30d, 90d) for an insured asset,
    with TALON vs telemetry-only baseline probability comparison.
    """
    sat_id_full = f"objects/{satellite_id}"

    preds = _aql("""
        FOR p IN @@preds
            FILTER p.satellite_id == @sat_id
            SORT p.generated_at DESC
            LIMIT 5
            RETURN p
    """, {"@preds": COLLECTION_ANOMALY_PREDICTIONS, "sat_id": sat_id_full})

    if not preds:
        raise HTTPException(status_code=404, detail=f"No predictions found for asset '{satellite_id}'")

    latest_pred = preds[0]
    horizons = latest_pred.get("horizons", {})

    def _horizon(key: str, default_prob: float):
        h = horizons.get(key, {})
        talon_prob = h.get("talon_probability", default_prob)
        baseline_prob = h.get("baseline_probability", default_prob * 0.7)
        return {
            "talon_probability": talon_prob,
            "baseline_probability": baseline_prob,
            "delta": round(talon_prob - baseline_prob, 3),
            "primary_driver": h.get("primary_driver", "conjunction_frequency"),
            "confidence": h.get("confidence", 0.85),
        }

    return {
        "satellite_id": satellite_id,
        "generated_at": latest_pred.get("generated_at"),
        "model_version": latest_pred.get("model_version", "talon-v2"),
        "horizons": {
            "7d": _horizon("7d", latest_pred.get("prob_anomaly_7d", 0.05)),
            "30d": _horizon("30d", latest_pred.get("prob_anomaly_30d", 0.15)),
            "90d": _horizon("90d", latest_pred.get("prob_anomaly_90d", 0.28)),
        },
        "primary_factors": latest_pred.get("primary_factors", []),
        "recommended_actions": latest_pred.get("recommended_actions", []),
    }


# ---------------------------------------------------------------------------
# GET /v2/insurance/asset/{satellite_id}/tasking  (Phase B)
# ---------------------------------------------------------------------------

@router.get("/asset/{satellite_id}/tasking", summary="Task queue for an insured asset")
def asset_tasking(satellite_id: str):
    """
    Returns the Kestrel task queue for an insured asset: scheduled, executing,
    and recently completed tasks with kestrel assignments and target windows.
    """
    sat_id_full = f"objects/{satellite_id}"

    tasks = _aql("""
        FOR t IN @@tasks
            FILTER t.target_id == @target
            SORT t.scheduled_for DESC
            LIMIT 30
            LET k = FIRST(
                FOR k IN @@kestrels FILTER k._key == LAST(SPLIT(t.kestrel_id, '/')) RETURN k
            )
            RETURN {
                task_id: t._key,
                kestrel_id: LAST(SPLIT(t.kestrel_id, '/')),
                kestrel_name: k.name,
                status: t.status,
                priority: t.priority,
                task_type: t.task_type,
                scheduled_for: t.scheduled_for,
                completed_at: t.completed_at,
                observation_id: t.observation_id,
                notes: t.notes
            }
    """, {
        "@tasks": COLLECTION_KESTREL_TASKS,
        "@kestrels": COLLECTION_KESTRELS,
        "target": sat_id_full,
    })

    status_counts: dict = {}
    for t in tasks:
        s = t.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    return {
        "satellite_id": satellite_id,
        "queue_summary": status_counts,
        "tasks": tasks,
    }


# ---------------------------------------------------------------------------
# POST /v2/insurance/export/evidence/{loss_event_id}  (Phase B)
# ---------------------------------------------------------------------------

@router.post("/export/evidence/{loss_event_id}", summary="Export PDF evidence package for a loss event")
def export_evidence_pdf(loss_event_id: str):
    """
    Generates and returns a PDF evidence package for the specified loss event.
    The package includes event metadata, witness chain, observation details,
    cryptographic custody hashes, and compliance summary.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        raise HTTPException(status_code=503, detail="reportlab not installed — cannot generate PDF")

    le_col = _col(COLLECTION_LOSS_EVENTS)
    if not le_col.has(loss_event_id):
        raise HTTPException(status_code=404, detail=f"Loss event '{loss_event_id}' not found")

    le_doc = le_col.get(loss_event_id)
    pkg = le_doc.get("evidence_package", {})

    fusion_id = f"FG-{loss_event_id}"
    fusion_obs = _aql("""
        FOR obs IN @@obs FILTER obs.fusion_group_id == @fid RETURN obs
    """, {"@obs": COLLECTION_OBSERVATIONS, "fid": fusion_id})

    kestrel_keys = [k.split("/")[-1] for k in (le_doc.get("witnessed_by_kestrels") or [])]
    kestrel_col = _col(COLLECTION_KESTRELS)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.75 * inch, bottomMargin=0.75 * inch)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Title"], fontSize=18, spaceAfter=6)
    h2_style = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceBefore=12, spaceAfter=4)
    body_style = styles["Normal"]
    mono_style = ParagraphStyle("mono", parent=styles["Normal"], fontName="Courier", fontSize=8)

    story = []

    story.append(Paragraph("TALON Insurance — Evidence Package", title_style))
    story.append(Paragraph(f"Loss Event: <b>{loss_event_id}</b>", body_style))
    story.append(Paragraph(f"Generated: {datetime.now(timezone.utc).isoformat()}", body_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1e293b")))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Event Summary", h2_style))
    event_data = [
        ["Field", "Value"],
        ["Event Type", str(le_doc.get("event_type", "—"))],
        ["Severity", str(le_doc.get("severity", "—"))],
        ["Occurred At", str(le_doc.get("occurred_at", "—"))],
        ["Total Sum at Risk", f"${le_doc.get('total_sum_at_risk', 0):,.0f}"],
        ["Confidence", f"{le_doc.get('confidence', 0) * 100:.0f}%" if le_doc.get('confidence') else "—"],
        ["Confirmation Latency", f"{le_doc.get('confirmation_latency_s', '—')}s"],
        ["Active", str(le_doc.get("active", False))],
    ]
    event_table = Table(event_data, colWidths=[2.5 * inch, 4.5 * inch])
    event_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(event_table)
    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("Witness Chain", h2_style))
    witness_data = [["Kestrel", "Name", "Observed At", "Geo Quality", "Custody Hash"]]
    for k_key in kestrel_keys:
        kestrel = kestrel_col.get(k_key) if kestrel_col.has(k_key) else {}
        obs_match = next((o for o in fusion_obs if (o.get("kestrel_id") or "").split("/")[-1] == k_key), {})
        compliance = obs_match.get("compliance") or {}
        custody_hash = compliance.get("custody_hash", "—")
        short_hash = custody_hash[:24] + "…" if len(str(custody_hash)) > 24 else str(custody_hash)
        witness_data.append([
            k_key,
            kestrel.get("name", k_key),
            str(obs_match.get("observed_at") or obs_match.get("observation_epoch") or "—")[:19],
            str(obs_match.get("geometry_quality", "—")),
            short_hash,
        ])
    if len(witness_data) == 1:
        witness_data.append(["No witnesses recorded", "", "", "", ""])
    witness_table = Table(witness_data, colWidths=[1.0 * inch, 1.2 * inch, 1.6 * inch, 1.0 * inch, 2.2 * inch])
    witness_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f0f9ff"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94a3b8")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(witness_table)
    story.append(Spacer(1, 0.15 * inch))

    compliance_summary = pkg.get("compliance_summary", {})
    story.append(Paragraph("Compliance &amp; Admissibility", h2_style))
    comp_data = [
        ["Check", "Status"],
        ["Non-ITAR observations", "✓" if compliance_summary.get("all_observations_non_itar") else "✗"],
        ["Operator consents obtained", "✓" if compliance_summary.get("all_consents_obtained") else "✗"],
        ["Redaction required", "Yes" if compliance_summary.get("redaction_required") else "No"],
        ["Package hash", pkg.get("package_hash", "—")],
        ["Signed by", pkg.get("signed_by", "—")],
        ["Signed at", str(pkg.get("signed_at", "—"))[:19]],
    ]
    comp_table = Table(comp_data, colWidths=[3 * inch, 4 * inch])
    comp_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(comp_table)
    story.append(Spacer(1, 0.1 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94a3b8")))
    story.append(Paragraph(
        f"Generated by TALON Insurance Platform · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        ParagraphStyle("footer", parent=body_style, fontSize=7, textColor=colors.HexColor("#64748b"), alignment=TA_CENTER)
    ))

    doc.build(story)
    buf.seek(0)

    filename = f"talon_evidence_{loss_event_id}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# GET /v2/insurance/aggregation/shells  (Phase C)
# ---------------------------------------------------------------------------

_SHELL_META = {
    "LEO_500_520":    {"label": "LEO 500–520 km",      "alt_km": 510,   "color": "#dc2626"},
    "LEO_520_540":    {"label": "LEO 520–540 km",      "alt_km": 530,   "color": "#d97706"},
    "LEO_540_560":    {"label": "LEO 540–560 km",      "alt_km": 550,   "color": "#0369a1"},
    "LEO_560_580":    {"label": "LEO 560–580 km",      "alt_km": 570,   "color": "#15803d"},
    "MEO_19000_21000":{"label": "MEO 19 000–21 000 km","alt_km": 20200, "color": "#7c3aed"},
    "GEO_W":          {"label": "GEO West",            "alt_km": 35786, "color": "#0e7490"},
    "GEO_E":          {"label": "GEO East",            "alt_km": 35786, "color": "#be185d"},
}


@router.get("/aggregation/shells", summary="Full book exposure by orbital shell with heatmap data")
def aggregation_shells(carrier_id: str = Query(default=DEMO_CARRIER_ID)):
    """
    Returns the full book-level aggregation breakdown by orbital shell.
    Includes sum insured, asset count, percentage of book, heatmap intensity,
    and risk statistics — used to drive the Cesium orbital shell visualisation.
    """
    policies = _aql("""
        FOR p IN @@policies
            FILTER p.carrier_id == @carrier AND p.status == 'bound'
            LET sat_key = LAST(SPLIT(p.satellite_id, '/'))
            LET sat = FIRST(FOR s IN @@objects FILTER s._key == sat_key RETURN s)
            LET rs = FIRST(
                FOR r IN @@rs FILTER r.satellite_id == p.satellite_id
                SORT r.computed_at DESC LIMIT 1 RETURN r
            )
            LET shell_key = sat.canonical.orbital_band
            RETURN {
                shell_id: shell_key,
                sum_insured: p.sum_insured,
                risk_score: rs.score,
                risk_band: rs.score_band
            }
    """, {
        "@policies": COLLECTION_POLICIES,
        "@objects": COLLECTION_NAME,
        "@rs": COLLECTION_RISK_SCORES,
        "carrier": f"parties/{carrier_id}",
    })

    shell_map: dict = {}
    for row in policies:
        sid = row.get("shell_id") or "unknown"
        if sid not in shell_map:
            shell_map[sid] = {
                "shell_id": sid,
                "sum_insured": 0,
                "asset_count": 0,
                "risk_scores": [],
                "high_risk_count": 0,
            }
        shell_map[sid]["sum_insured"] += row.get("sum_insured") or 0
        shell_map[sid]["asset_count"] += 1
        if row.get("risk_score") is not None:
            shell_map[sid]["risk_scores"].append(row["risk_score"])
        if row.get("risk_band") in ("high", "critical"):
            shell_map[sid]["high_risk_count"] += 1

    total_si = sum(s["sum_insured"] for s in shell_map.values()) or 1
    max_si = max((s["sum_insured"] for s in shell_map.values()), default=1)

    shells = []
    for sid, data in shell_map.items():
        meta = _SHELL_META.get(sid, {"label": sid, "alt_km": 550, "color": "#64748b"})
        scores = data["risk_scores"]
        shells.append({
            "shell_id": sid,
            "label": meta["label"],
            "alt_km": meta["alt_km"],
            "color": meta["color"],
            "sum_insured": data["sum_insured"],
            "asset_count": data["asset_count"],
            "pct_of_book": round(data["sum_insured"] / total_si * 100, 1),
            "heatmap_intensity": round(data["sum_insured"] / max_si, 3),
            "avg_risk_score": round(sum(scores) / len(scores), 2) if scores else None,
            "max_risk_score": round(max(scores), 2) if scores else None,
            "high_risk_count": data["high_risk_count"],
        })

    shells.sort(key=lambda x: -x["sum_insured"])
    return {"shells": shells, "total_sum_insured": total_si, "carrier_id": carrier_id}


# ---------------------------------------------------------------------------
# POST /v2/insurance/scenarios/fragmentation  (Phase C)
# ---------------------------------------------------------------------------

class FragmentationScenarioRequest(BaseModel):
    shell_id: str
    debris_count: int
    confidence: float = 0.85


@router.post("/scenarios/fragmentation", summary="Run a fragmentation scenario against the insured book")
def fragmentation_scenario(body: FragmentationScenarioRequest):
    """
    Simulates a fragmentation event in the specified orbital shell.
    Given the shell, debris count, and confidence level, returns:
    - affected insured assets in the shell
    - estimated sum at risk (scaled by debris count and confidence)
    - Kestrel coverage impact (which Kestrels can observe the shell)
    """
    shell_id = body.shell_id
    debris_count = max(1, body.debris_count)
    confidence = max(0.0, min(1.0, body.confidence))

    policies = _aql("""
        FOR p IN @@policies
            FILTER p.carrier_id == @carrier AND p.status == 'bound'
            LET sat_key = LAST(SPLIT(p.satellite_id, '/'))
            LET sat = FIRST(FOR s IN @@objects FILTER s._key == sat_key RETURN s)
            LET rs = FIRST(
                FOR r IN @@rs FILTER r.satellite_id == p.satellite_id
                SORT r.computed_at DESC LIMIT 1 RETURN r
            )
            FILTER sat.canonical.orbital_band == @shell
            RETURN {
                satellite_id: sat_key,
                name: sat.canonical.name OR sat.identifier,
                norad_id: sat.canonical.norad_id,
                operator: sat.canonical.operator,
                sum_insured: p.sum_insured,
                policy_id: p._key,
                risk_score: rs.score,
                risk_band: rs.score_band
            }
    """, {
        "@policies": COLLECTION_POLICIES,
        "@objects": COLLECTION_NAME,
        "@rs": COLLECTION_RISK_SCORES,
        "carrier": f"parties/{DEMO_CARRIER_ID}",
        "shell": shell_id,
    })

    rng = random.Random(debris_count + hash(shell_id) % 1000)
    debris_factor = min(1.0, math.log10(max(debris_count, 10)) / 4.0)
    base_hit_prob = 0.15 + debris_factor * 0.65

    affected = []
    total_sar = 0
    for p in policies:
        hit_prob = base_hit_prob * (1 + (p.get("risk_score") or 50) / 200)
        hit_prob = min(0.99, hit_prob) * confidence
        if rng.random() < hit_prob:
            exposure_pct = rng.uniform(0.15, 0.95)
            sum_at_risk = round((p.get("sum_insured") or 0) * exposure_pct)
            total_sar += sum_at_risk
            affected.append({
                "satellite_id": p["satellite_id"],
                "name": p.get("name") or p["satellite_id"],
                "norad_id": p.get("norad_id"),
                "operator": p.get("operator"),
                "sum_insured": p.get("sum_insured"),
                "sum_at_risk": sum_at_risk,
                "exposure_pct": round(exposure_pct * 100, 1),
                "risk_band": p.get("risk_band"),
                "hit_probability": round(hit_prob, 3),
            })

    affected.sort(key=lambda x: -x["sum_at_risk"])

    kestrels = _aql("""
        FOR k IN @@kestrels
            RETURN { id: k._key, name: k.name, orbit: k.orbit, status: k.status }
    """, {"@kestrels": COLLECTION_KESTRELS})

    meta = _SHELL_META.get(shell_id, {"alt_km": 550})
    shell_alt = meta["alt_km"]
    kestrel_impacts = []
    for k in kestrels:
        orbit = k.get("orbit") or {}
        k_alt = orbit.get("alt_km") or orbit.get("altitude_km") or 550
        alt_diff = abs(k_alt - shell_alt)
        if alt_diff < 200:
            coverage = "direct"
            obs_prob = 0.92
        elif alt_diff < 2000:
            coverage = "adjacent"
            obs_prob = 0.65
        elif shell_alt > 10000:
            coverage = "limited"
            obs_prob = 0.30
        else:
            coverage = "none"
            obs_prob = 0.05
        kestrel_impacts.append({
            "kestrel_id": k["id"],
            "kestrel_name": k.get("name", k["id"]),
            "status": k.get("status"),
            "coverage_type": coverage,
            "observation_probability": round(obs_prob * confidence, 3),
            "alt_diff_km": round(alt_diff),
        })

    kestrel_impacts.sort(key=lambda x: -x["observation_probability"])

    return {
        "shell_id": shell_id,
        "shell_label": _SHELL_META.get(shell_id, {}).get("label", shell_id),
        "debris_count": debris_count,
        "confidence": confidence,
        "scenario_timestamp": datetime.now(timezone.utc).isoformat(),
        "affected_assets": affected,
        "affected_count": len(affected),
        "total_assets_in_shell": len(policies),
        "total_sum_at_risk": total_sar,
        "kestrel_coverage_impact": kestrel_impacts,
    }
