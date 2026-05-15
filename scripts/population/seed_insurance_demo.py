#!/usr/bin/env python3
"""
Seed demo data for the TALON Insurance Overlay.

Idempotent — safe to run multiple times.  Deletes existing insurance demo
documents (keyed with the INS- namespace) and rebuilds from scratch.

Collections created/populated:
  parties, policies, insured_interests, loss_events, claims,
  risk_scores, anomaly_predictions, shells, kestrels,
  kestrel_tasks, coverage_windows

Edges created/populated:
  policy_covers_satellite, policy_has_interest, interest_held_by,
  claim_arises_from, loss_event_involves, satellite_in_shell,
  risk_score_for, prediction_for, kestrel_observed,
  kestrel_can_see, task_targets, event_witnessed_by
"""
import sys
import hashlib
import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import database as db_module
from database.connection import (
    connect_mongodb, db,
    COLLECTION_NAME,
    COLLECTION_PARTIES, COLLECTION_POLICIES, COLLECTION_INSURED_INTERESTS,
    COLLECTION_LOSS_EVENTS, COLLECTION_CLAIMS, COLLECTION_RISK_SCORES,
    COLLECTION_ANOMALY_PREDICTIONS, COLLECTION_SHELLS, COLLECTION_KESTRELS,
    COLLECTION_KESTREL_TASKS, COLLECTION_COVERAGE_WINDOWS, COLLECTION_OBSERVATIONS,
    EDGE_INSURANCE_POLICY_COVERS_SAT, EDGE_INSURANCE_POLICY_HAS_INTEREST,
    EDGE_INSURANCE_INTEREST_HELD_BY, EDGE_INSURANCE_CLAIM_ARISES_FROM,
    EDGE_INSURANCE_LOSS_EVENT_INVOLVES, EDGE_INSURANCE_SAT_IN_SHELL,
    EDGE_INSURANCE_RISK_SCORE_FOR, EDGE_INSURANCE_PREDICTION_FOR,
    EDGE_INSURANCE_KESTREL_OBSERVED, EDGE_INSURANCE_KESTREL_CAN_SEE,
    EDGE_INSURANCE_TASK_TARGETS, EDGE_INSURANCE_EVENT_WITNESSED_BY,
)

rng = random.Random(42)

NOW = datetime.now(timezone.utc)


def ts_future(hours=0, days=0, minutes=0):
    return (NOW + timedelta(hours=hours, days=days, minutes=minutes)).isoformat()


def ts_past(days=0, hours=0, minutes=0):
    return (NOW - timedelta(days=days, hours=hours, minutes=minutes)).isoformat()


def sha256_stub(data: str) -> str:
    return "sha256:" + hashlib.sha256(data.encode()).hexdigest()


def upsert(col_name: str, doc: dict):
    col = db_module.db.collection(col_name)
    key = doc["_key"]
    if col.has(key):
        col.update(doc)
    else:
        col.insert(doc)


def upsert_edge(col_name: str, doc: dict):
    col = db_module.db.collection(col_name)
    key = doc["_key"]
    if col.has(key):
        col.update(doc)
    else:
        col.insert(doc)


def find_existing_obs_near(norad_id: int, target_iso: str, limit: int = 5) -> list[dict]:
    """Return up to `limit` existing observations for a NORAD ID, sorted nearest to target_iso."""
    cursor = db_module.db.aql.execute("""
        FOR obs IN @@obs
            FILTER obs.norad_id == @norad_id
            SORT ABS(DATE_DIFF(obs.observation_epoch, @target, 's')) ASC
            LIMIT @lim
            RETURN obs
    """, bind_vars={
        "@obs": COLLECTION_OBSERVATIONS,
        "norad_id": norad_id,
        "target": target_iso,
        "lim": limit,
    })
    return list(cursor)


def find_existing_obs_for_asset(norad_id: int, limit: int = 50) -> list[dict]:
    """Return up to `limit` existing observations for a NORAD ID (any time)."""
    cursor = db_module.db.aql.execute("""
        FOR obs IN @@obs
            FILTER obs.norad_id == @norad_id
            SORT obs.observation_epoch DESC
            LIMIT @lim
            RETURN obs
    """, bind_vars={
        "@obs": COLLECTION_OBSERVATIONS,
        "norad_id": norad_id,
        "lim": limit,
    })
    return list(cursor)


def _health_score_for_asset(norad_id: int) -> float | None:
    """Return average derived_health_score (0–1) from observations for a NORAD ID, or None."""
    obs_list = find_existing_obs_for_asset(norad_id, limit=20)
    scores = [
        o.get("derived_health_score")
        for o in obs_list
        if o.get("derived_health_score") is not None
    ]
    if not scores:
        return None
    avg = sum(scores) / len(scores)
    if avg > 1.0:
        avg = avg / 100.0
    return max(0.0, min(1.0, avg))


def find_objects_with_observations(limit: int = 40) -> list[dict]:
    """Return catalog objects that have at least one real (non-synthetic) observation.

    Joins the objects collection against observations by norad_cat_id / norad_id,
    using TO_NUMBER() on both sides to handle int, float, or string storage variants.
    Returns up to `limit` objects with enough metadata to build insurance records.
    """
    cursor = db_module.db.aql.execute("""
        LET observed_norad_ids = (
            FOR obs IN @@obs
                FILTER obs._insurance_synthetic != true
                FILTER obs.norad_id != null
                COLLECT norad_id = TO_NUMBER(obs.norad_id)
                FILTER norad_id > 0
                RETURN norad_id
        )
        FOR obj IN @@objects
            FILTER obj._insurance_mock != true
            FILTER obj.canonical.object_class == "Payload"
            FILTER obj.canonical.status == "in orbit"
            FILTER TO_NUMBER(obj.canonical.norad_cat_id) IN observed_norad_ids
            LIMIT @lim
            RETURN {
                _key:         obj._key,
                norad_id:     TO_NUMBER(obj.canonical.norad_cat_id),
                name:         obj.canonical.name    OR obj.identifier OR obj._key,
                operator:     obj.canonical.operator OR obj.canonical.owner OR "Unknown",
                orbital_band: obj.canonical.orbital_band OR obj.canonical.regime OR "LEO"
            }
    """, bind_vars={
        "@obs": COLLECTION_OBSERVATIONS,
        "@objects": COLLECTION_NAME,
        "lim": limit,
    })
    return [r for r in cursor if r.get("norad_id")]


def _infer_shell_key(orbital_band: str) -> str:
    """Map a canonical orbital_band value to one of the seed shell keys."""
    band = (orbital_band or "").upper()
    if "GEO" in band:
        return rng.choice(["GEO_W", "GEO_E"])
    if "MEO" in band:
        return "MEO_19000_21000"
    return rng.choice(["LEO_500_520", "LEO_520_540", "LEO_540_560"])


def _infer_sum_insured_m(orbital_band: str) -> int:
    """Assign a plausible sum-insured (in $M) based on orbital regime."""
    band = (orbital_band or "").upper()
    if "GEO" in band:
        return rng.randint(200, 400)
    if "MEO" in band:
        return rng.randint(80, 130)
    return rng.randint(40, 200)


def amend_obs(obs_doc: dict, kestrel_key: str, fusion_group_id: str | None = None, geometry_quality: float | None = None):
    """
    Extend an existing observation with insurance fields in-place.
    Only sets fields that are not already present, to avoid clobbering existing data.
    """
    epoch = obs_doc.get("observation_epoch") or obs_doc.get("observed_at") or NOW.isoformat()
    patch: dict = {}
    if "kestrel_id" not in obs_doc:
        patch["kestrel_id"] = f"kestrels/{kestrel_key}"
    if "compliance" not in obs_doc:
        patch["compliance"] = _compliance(kestrel_key, epoch)
    if fusion_group_id and "fusion_group_id" not in obs_doc:
        patch["fusion_group_id"] = fusion_group_id
    if geometry_quality is not None and "geometry_quality" not in obs_doc:
        patch["geometry_quality"] = geometry_quality
    if "observed_at" not in obs_doc:
        patch["observed_at"] = epoch
    if patch:
        patch["_key"] = obs_doc["_key"]
        db_module.db.collection(COLLECTION_OBSERVATIONS).update(patch)
        obs_doc.update(patch)
    return obs_doc


def create_synthetic_obs(norad_id: int, kestrel_key: str, epoch_iso: str,
                          fusion_group_id: str | None = None, geometry_quality: float | None = None) -> dict:
    """Create a minimal synthetic observation when no real one exists for this NORAD ID."""
    import uuid
    obs_key = f"INS-OBS-{norad_id}-{uuid.uuid4().hex[:12]}"
    doc = {
        "_key": obs_key,
        "norad_id": norad_id,
        "observation_epoch": epoch_iso,
        "observed_at": epoch_iso,
        "source": "kestrel_proxy_v2",
        "kestrel_id": f"kestrels/{kestrel_key}",
        "geometry_quality": geometry_quality if geometry_quality is not None else round(rng.uniform(0.55, 0.92), 2),
        "compliance": _compliance(kestrel_key, epoch_iso),
        "_insurance_synthetic": True,
    }
    if fusion_group_id:
        doc["fusion_group_id"] = fusion_group_id
    try:
        db_module.db.collection(COLLECTION_OBSERVATIONS).insert(doc)
    except Exception:
        pass
    return doc


def delete_demo_prefix(col_name: str, prefix: str):
    aql = """
    FOR doc IN @@col
        FILTER STARTS_WITH(doc._key, @prefix)
        REMOVE doc IN @@col
    """
    db_module.db.aql.execute(aql, bind_vars={"@col": col_name, "prefix": prefix})


# ---------------------------------------------------------------------------
# Seed data definitions
# ---------------------------------------------------------------------------

PARTIES = [
    {
        "_key": "acme_re",
        "name": "Acme Re",
        "type": "carrier",
        "lloyd_syndicate_no": "1234",
        "country": "GB",
        "roles": ["carrier", "lead_underwriter"],
        "contact": {"primary_underwriter": "underwriter@acme-re.example"},
    },
    {
        "_key": "axaxl",
        "name": "AXA XL",
        "type": "carrier",
        "lloyd_syndicate_no": "2019",
        "country": "GB",
        "roles": ["carrier"],
        "contact": {"primary_underwriter": "space@axaxl.example"},
    },
    {
        "_key": "allianz",
        "name": "Allianz Global Corporate & Specialty",
        "type": "carrier",
        "lloyd_syndicate_no": "0000",
        "country": "DE",
        "roles": ["carrier"],
        "contact": {"primary_underwriter": "space@agcs.example"},
    },
    {
        "_key": "marsh",
        "name": "Marsh Space Projects",
        "type": "broker",
        "country": "US",
        "roles": ["broker"],
        "contact": {"primary_underwriter": "space@marsh.example"},
    },
    {
        "_key": "mcgill",
        "name": "McGill Space Insurance",
        "type": "broker",
        "country": "CA",
        "roles": ["broker"],
        "contact": {"primary_underwriter": "space@mcgill.example"},
    },
]

OPERATORS = ["SES", "Inmarsat", "Iridium", "OneWeb", "Starlink", "Maxar", "Planet", "Telesat"]

SHELLS = [
    {"_key": "LEO_500_520", "regime": "LEO", "alt_min_km": 500, "alt_max_km": 520, "inclination_band": "all", "label": "LEO 500–520 km"},
    {"_key": "LEO_520_540", "regime": "LEO", "alt_min_km": 520, "alt_max_km": 540, "inclination_band": "all", "label": "LEO 520–540 km"},
    {"_key": "LEO_540_560", "regime": "LEO", "alt_min_km": 540, "alt_max_km": 560, "inclination_band": "all", "label": "LEO 540–560 km"},
    {"_key": "LEO_560_580", "regime": "LEO", "alt_min_km": 560, "alt_max_km": 580, "inclination_band": "all", "label": "LEO 560–580 km"},
    {"_key": "MEO_19000_21000", "regime": "MEO", "alt_min_km": 19000, "alt_max_km": 21000, "inclination_band": "all", "label": "MEO 19000–21000 km"},
    {"_key": "GEO_W", "regime": "GEO", "alt_min_km": 35786, "alt_max_km": 35786, "inclination_band": "all", "label": "GEO West"},
    {"_key": "GEO_E", "regime": "GEO", "alt_min_km": 35786, "alt_max_km": 35786, "inclination_band": "all", "label": "GEO East"},
]

KESTRELS = [
    {"_key": "KSTRL-01", "name": "Kestrel-1", "norad_id": 99001, "status": "operational", "sensor_types": ["optical_visible", "optical_ir"], "fov_deg": 4.5, "limiting_magnitude": 17.5, "orbit": {"regime": "LEO_SSO", "alt_km": 600, "inclination_deg": 97.8, "raan_deg": 0.0}, "tasking_latency_s": 240},
    {"_key": "KSTRL-02", "name": "Kestrel-2", "norad_id": 99002, "status": "operational", "sensor_types": ["optical_visible", "optical_ir"], "fov_deg": 4.5, "limiting_magnitude": 17.5, "orbit": {"regime": "LEO_SSO", "alt_km": 601, "inclination_deg": 97.8, "raan_deg": 90.0}, "tasking_latency_s": 240},
    {"_key": "KSTRL-03", "name": "Kestrel-3", "norad_id": 99003, "status": "operational", "sensor_types": ["optical_visible", "optical_ir", "rf"], "fov_deg": 5.0, "limiting_magnitude": 17.0, "orbit": {"regime": "LEO_SSO", "alt_km": 602, "inclination_deg": 97.8, "raan_deg": 180.0}, "tasking_latency_s": 300},
    {"_key": "KSTRL-04", "name": "Kestrel-4", "norad_id": 99004, "status": "degraded", "sensor_types": ["optical_visible", "optical_ir"], "fov_deg": 4.5, "limiting_magnitude": 16.0, "orbit": {"regime": "LEO_SSO", "alt_km": 603, "inclination_deg": 97.8, "raan_deg": 270.0}, "tasking_latency_s": 480},
]

SHELL_FOR_REGIME = {
    "GEO_W": "GEO_W", "GEO_E": "GEO_E",
    "LEO_500_520": "LEO_500_520", "LEO_520_540": "LEO_520_540",
    "LEO_540_560": "LEO_540_560", "LEO_560_580": "LEO_560_580",
    "MEO_19000_21000": "MEO_19000_21000",
}

CARRIER_WEIGHTS = {"acme_re": 0.40, "axaxl": 0.32, "allianz": 0.28}


def _compliance(kestrel_key: str, captured_at: str, itar: str = "non_itar") -> dict:
    obs_data = f"{kestrel_key}:{captured_at}"
    return {
        "itar_status": itar,
        "export_jurisdiction": "US",
        "nda_scope": None,
        "operator_consent": "obtained",
        "redaction_applied": False,
        "captured_by": f"kestrels/{kestrel_key}",
        "captured_at": captured_at,
        "custody_hash": sha256_stub(obs_data),
    }


def _evidence_package(obs_hashes: list[str], signed_at: str) -> dict:
    return {
        "package_hash": sha256_stub(":".join(obs_hashes) + signed_at),
        "constituent_observation_hashes": obs_hashes,
        "signed_by": "kestrel-ops@talon.example",
        "signed_at": signed_at,
        "signature": sha256_stub("sig:" + signed_at),
        "compliance_summary": {
            "all_observations_non_itar": True,
            "all_consents_obtained": True,
            "redaction_required": False,
        },
    }


def _risk_score(sat_key: str, date_str: str, score: int, factors: dict | None = None) -> dict:
    if factors is None:
        factors = {
            "shell_debris_density": {"value": round(rng.uniform(0.3, 0.9), 2), "weight": 0.30, "delta_30d": round(rng.uniform(-0.05, 0.10), 2)},
            "operator_track_record": {"value": round(rng.uniform(0.3, 0.8), 2), "weight": 0.20, "delta_30d": 0},
            "asset_age_factor": {"value": round(rng.uniform(0.1, 0.6), 2), "weight": 0.15, "delta_30d": round(rng.uniform(0, 0.02), 2)},
            "recent_anomaly_count": {"value": round(rng.uniform(0.1, 0.8), 2), "weight": 0.15, "delta_30d": round(rng.uniform(0, 0.12), 2)},
            "neighbor_maneuver_intensity": {"value": round(rng.uniform(0.2, 0.9), 2), "weight": 0.20, "delta_30d": round(rng.uniform(0, 0.08), 2)},
        }
    band_map = [(20, "low"), (40, "moderate"), (60, "elevated"), (80, "high"), (101, "critical")]
    band = next(b for threshold, b in band_map if score < threshold)
    key = f"RS-{sat_key}-{date_str}"
    return {
        "_key": key,
        "satellite_id": f"objects/{sat_key}",
        "computed_at": f"{date_str}T02:00:00Z",
        "score": score,
        "score_band": band,
        "factors": factors,
        "comparable_event_ids": [],
        "confidence": round(rng.uniform(0.65, 0.92), 2),
    }


def _anomaly_prediction(sat_key: str, date_str: str, p7: float, p30: float, p90: float, baseline_p30: float) -> dict:
    ci = lambda p: {"value": p, "ci_lower": round(max(0, p - rng.uniform(0.01, 0.04)), 3), "ci_upper": round(min(1, p + rng.uniform(0.01, 0.07)), 3)}
    kestrel_count = rng.randint(3, 8)
    return {
        "_key": f"AP-{sat_key}-{date_str}",
        "satellite_id": f"objects/{sat_key}",
        "computed_at": f"{date_str}T02:00:00Z",
        "horizons": {
            "p_anomaly_7d": ci(p7),
            "p_anomaly_30d": ci(p30),
            "p_anomaly_90d": ci(p90),
        },
        "input_sources": {
            "operator_telemetry": {"available": True, "freshness_hours": rng.randint(1, 6), "weight": 0.45},
            "space_based_sensors": {"available": True, "kestrel_count": kestrel_count, "weight": 0.35},
            "environment": {"available": True, "weight": 0.20},
        },
        "telemetry_only_baseline": {
            "p_anomaly_30d": baseline_p30,
            "note": "Comparison baseline using operator telemetry alone.",
        },
        "model_version": "predictor-v0.3",
        "confidence": round(rng.uniform(0.60, 0.85), 2),
    }


def main():
    if not connect_mongodb():
        print("ERROR: Could not connect to ArangoDB")
        sys.exit(1)

    print("=== TALON Insurance Demo Seed ===")
    print("Clearing existing insurance demo data...")

    vertex_cols = [
        COLLECTION_PARTIES, COLLECTION_POLICIES, COLLECTION_INSURED_INTERESTS,
        COLLECTION_LOSS_EVENTS, COLLECTION_CLAIMS, COLLECTION_RISK_SCORES,
        COLLECTION_ANOMALY_PREDICTIONS, COLLECTION_SHELLS, COLLECTION_KESTRELS,
        COLLECTION_KESTREL_TASKS, COLLECTION_COVERAGE_WINDOWS, COLLECTION_OBSERVATIONS,
    ]
    edge_cols = [
        EDGE_INSURANCE_POLICY_COVERS_SAT, EDGE_INSURANCE_POLICY_HAS_INTEREST,
        EDGE_INSURANCE_INTEREST_HELD_BY, EDGE_INSURANCE_CLAIM_ARISES_FROM,
        EDGE_INSURANCE_LOSS_EVENT_INVOLVES, EDGE_INSURANCE_SAT_IN_SHELL,
        EDGE_INSURANCE_RISK_SCORE_FOR, EDGE_INSURANCE_PREDICTION_FOR,
        EDGE_INSURANCE_KESTREL_OBSERVED, EDGE_INSURANCE_KESTREL_CAN_SEE,
        EDGE_INSURANCE_TASK_TARGETS, EDGE_INSURANCE_EVENT_WITNESSED_BY,
    ]

    for col_name in vertex_cols:
        delete_demo_prefix(col_name, "INS-")
        delete_demo_prefix(col_name, "KSTRL-")
        delete_demo_prefix(col_name, "SHL-")
        delete_demo_prefix(col_name, "RS-")
        delete_demo_prefix(col_name, "AP-")
        delete_demo_prefix(col_name, "TSK-")
        delete_demo_prefix(col_name, "CW-")
        delete_demo_prefix(col_name, "OBS-")
        delete_demo_prefix(col_name, "POL-")
        delete_demo_prefix(col_name, "CLM-")
        delete_demo_prefix(col_name, "LE-")
        delete_demo_prefix(col_name, "II-")
        delete_demo_prefix(col_name, "INS-OBS-")

    for ecol in edge_cols:
        try:
            db_module.db.aql.execute(f"FOR doc IN `{ecol}` REMOVE doc IN `{ecol}`")
        except Exception:
            pass

    for party in PARTIES:
        upsert(COLLECTION_PARTIES, party)
    print(f"  Parties: {len(PARTIES)}")

    for shell in SHELLS:
        upsert(COLLECTION_SHELLS, shell)
    print(f"  Shells: {len(SHELLS)}")

    for kestrel in KESTRELS:
        upsert(COLLECTION_KESTRELS, kestrel)
    print(f"  Kestrels: {len(KESTRELS)}")

    print("Discovering catalog objects that have real observations...")
    observed_objects = find_objects_with_observations(limit=40)
    print(f"  Found {len(observed_objects)} objects with observations")

    if not observed_objects:
        print()
        print("WARNING: No catalog objects with real observations found.")
        print("  Import observation data first (e.g. via import_kestrel_proxy_v2.py),")
        print("  then re-run this script.")
        print("=== Seed aborted — no qualifying assets ===")
        return

    insured_assets = []
    for obj in observed_objects:
        shell_key = _infer_shell_key(obj["orbital_band"])
        insured_assets.append({
            "sat_key": obj["_key"],
            "norad_id": int(obj["norad_id"]),
            "name": obj["name"],
            "shell_key": shell_key,
            "operator": obj["operator"],
            "sum_insured_m": _infer_sum_insured_m(obj["orbital_band"]),
        })

    print(f"  Insured assets: {len(insured_assets)}")

    for asset in insured_assets:
        shell_key = SHELL_FOR_REGIME.get(asset["shell_key"], "LEO_540_560")
        edge_key = f"SHL-{asset['sat_key']}-{shell_key}"
        upsert_edge(EDGE_INSURANCE_SAT_IN_SHELL, {
            "_key": edge_key,
            "_from": f"objects/{asset['sat_key']}",
            "_to": f"shells/{shell_key}",
        })
    print(f"  satellite_in_shell edges: {len(insured_assets)}")

    print("Creating policies and syndicate lines...")
    policy_refs = []
    for i, asset in enumerate(insured_assets):
        pol_key = f"POL-2026-{i+1:04d}"
        pol_num = f"AR-SAT-2026-{i+1:04d}"
        inception = (NOW - timedelta(days=rng.randint(30, 365))).strftime("%Y-%m-%d")
        expiry = (NOW + timedelta(days=rng.randint(30, 730))).strftime("%Y-%m-%d")
        premium = int(asset["sum_insured_m"] * rng.uniform(0.025, 0.038) * 1_000_000)
        pol = {
            "_key": pol_key,
            "policy_number": pol_num,
            "carrier_id": "parties/acme_re",
            "broker_id": "parties/marsh" if i % 2 == 0 else "parties/mcgill",
            "lead_underwriter_id": "parties/acme_re",
            "sum_insured": asset["sum_insured_m"] * 1_000_000,
            "currency": "USD",
            "deductible": 5_000_000,
            "perils": ["in_orbit", "third_party_liability"],
            "inception": inception,
            "expiry": expiry,
            "status": "bound",
            "premium": premium,
            "premium_currency": "USD",
            "policy_period_type": "annual_in_orbit",
            "satellite_id": f"objects/{asset['sat_key']}",
        }
        upsert(COLLECTION_POLICIES, pol)
        policy_refs.append({"pol_key": pol_key, "asset": asset, "expiry": expiry, "sum_insured": pol["sum_insured"]})

        upsert_edge(EDGE_INSURANCE_POLICY_COVERS_SAT, {
            "_key": f"PCS-{pol_key}",
            "_from": f"policies/{pol_key}",
            "_to": f"objects/{asset['sat_key']}",
            "attached_at": inception,
        })

        carriers = [("acme_re", 40.0), ("axaxl", 32.0), ("allianz", 28.0)]
        for carrier_key, pct in carriers:
            ii_key = f"II-{pol_key}-{carrier_key}"
            ii = {
                "_key": ii_key,
                "policy_id": f"policies/{pol_key}",
                "party_id": f"parties/{carrier_key}",
                "participation_pct": pct,
                "line_size": int(asset["sum_insured_m"] * 1_000_000 * pct / 100),
                "layer": "primary",
                "role": "lead" if carrier_key == "acme_re" else "follow",
            }
            upsert(COLLECTION_INSURED_INTERESTS, ii)
            upsert_edge(EDGE_INSURANCE_POLICY_HAS_INTEREST, {
                "_key": f"PHI-{pol_key}-{carrier_key}",
                "_from": f"policies/{pol_key}",
                "_to": f"insured_interests/{ii_key}",
            })
            upsert_edge(EDGE_INSURANCE_INTEREST_HELD_BY, {
                "_key": f"IHB-{ii_key}",
                "_from": f"insured_interests/{ii_key}",
                "_to": f"parties/{carrier_key}",
            })

    print(f"  Policies: {len(policy_refs)}, syndicate lines: {len(policy_refs)*3}")

    print("Creating risk scores (6 months history per asset)...")
    rs_count = 0
    for asset in insured_assets:
        sat_key = asset["sat_key"]
        health = _health_score_for_asset(asset["norad_id"])
        if health is not None:
            base_score = max(10, min(90, round((1.0 - health) * 100)))
        else:
            base_score = rng.randint(30, 80)
        for months_ago in range(6, -1, -1):
            date_dt = NOW - timedelta(days=months_ago * 30)
            date_str = date_dt.strftime("%Y-%m-%d")
            drift = rng.randint(-5, 10) if months_ago > 0 else 0
            score = max(10, min(95, base_score + (6 - months_ago) * 2 + drift))
            rs_doc = _risk_score(sat_key, date_str, score)
            upsert(COLLECTION_RISK_SCORES, rs_doc)
            upsert_edge(EDGE_INSURANCE_RISK_SCORE_FOR, {
                "_key": f"RSF-{rs_doc['_key']}",
                "_from": f"risk_scores/{rs_doc['_key']}",
                "_to": f"objects/{sat_key}",
                "is_latest": months_ago == 0,
            })
            rs_count += 1
    print(f"  Risk scores: {rs_count}")

    print("Creating anomaly predictions (7 months history per asset)...")
    ap_count = 0
    for asset in insured_assets:
        sat_key = asset["sat_key"]
        p30_base = rng.uniform(0.05, 0.18)
        for months_ago in range(6, -1, -1):
            date_dt = NOW - timedelta(days=months_ago * 30)
            date_str = date_dt.strftime("%Y-%m-%d")
            p30 = round(min(0.45, p30_base + months_ago * -0.005 + rng.uniform(-0.01, 0.02)), 3)
            p7 = round(p30 * 0.38, 3)
            p90 = round(min(0.60, p30 * 2.3), 3)
            baseline_p30 = round(p30 * rng.uniform(0.65, 0.82), 3)
            ap_doc = _anomaly_prediction(sat_key, date_str, p7, p30, p90, baseline_p30)
            upsert(COLLECTION_ANOMALY_PREDICTIONS, ap_doc)
            upsert_edge(EDGE_INSURANCE_PREDICTION_FOR, {
                "_key": f"PF-{ap_doc['_key']}",
                "_from": f"anomaly_predictions/{ap_doc['_key']}",
                "_to": f"objects/{sat_key}",
                "is_latest": months_ago == 0,
            })
            ap_count += 1
    print(f"  Anomaly predictions: {ap_count}")

    print("Creating loss events (20 historical + 3 overnight active)...")
    headline_asset = insured_assets[0]
    le_docs = []

    event_templates = [
        {"type": "fragmentation", "severity": "high", "days_ago": 1, "confidence": 0.94, "kestrels": ["KSTRL-01", "KSTRL-02", "KSTRL-03"], "latency_s": 187, "asset_idx": 0, "active": True},
        {"type": "conjunction", "severity": "medium", "days_ago": 1, "confidence": 0.87, "kestrels": ["KSTRL-01", "KSTRL-03"], "latency_s": 320, "asset_idx": 1, "active": True},
        {"type": "anomaly", "severity": "low", "days_ago": 0, "confidence": 0.72, "kestrels": ["KSTRL-02"], "latency_s": None, "asset_idx": 3, "active": True},
        {"type": "fragmentation", "severity": "medium", "days_ago": 45, "confidence": 0.91, "kestrels": ["KSTRL-01", "KSTRL-03"], "latency_s": 244, "asset_idx": 5},
        {"type": "conjunction", "severity": "low", "days_ago": 60, "confidence": 0.80, "kestrels": ["KSTRL-03"], "latency_s": 410, "asset_idx": 6},
        {"type": "anomaly", "severity": "medium", "days_ago": 90, "confidence": 0.75, "kestrels": ["KSTRL-02", "KSTRL-04"], "latency_s": 280, "asset_idx": 7},
        {"type": "launch_failure", "severity": "high", "days_ago": 180, "confidence": 0.99, "kestrels": ["KSTRL-03", "KSTRL-01"], "latency_s": 95, "asset_idx": 8},
        {"type": "fragmentation", "severity": "high", "days_ago": 200, "confidence": 0.96, "kestrels": ["KSTRL-01", "KSTRL-03", "KSTRL-02"], "latency_s": 165, "asset_idx": 9},
        {"type": "conjunction", "severity": "medium", "days_ago": 250, "confidence": 0.82, "kestrels": ["KSTRL-02", "KSTRL-04"], "latency_s": 380, "asset_idx": 10},
        {"type": "anomaly", "severity": "low", "days_ago": 300, "confidence": 0.68, "kestrels": ["KSTRL-04"], "latency_s": None, "asset_idx": 11},
        {"type": "conjunction", "severity": "high", "days_ago": 365, "confidence": 0.89, "kestrels": ["KSTRL-01", "KSTRL-03", "KSTRL-02"], "latency_s": 210, "asset_idx": 12},
        {"type": "anomaly", "severity": "medium", "days_ago": 400, "confidence": 0.76, "kestrels": ["KSTRL-01", "KSTRL-02"], "latency_s": 330, "asset_idx": 13},
        {"type": "fragmentation", "severity": "medium", "days_ago": 450, "confidence": 0.88, "kestrels": ["KSTRL-03", "KSTRL-04"], "latency_s": 290, "asset_idx": 14},
        {"type": "conjunction", "severity": "low", "days_ago": 500, "confidence": 0.71, "kestrels": ["KSTRL-02"], "latency_s": 520, "asset_idx": 15},
        {"type": "anomaly", "severity": "low", "days_ago": 550, "confidence": 0.64, "kestrels": ["KSTRL-04"], "latency_s": None, "asset_idx": 16},
        {"type": "fragmentation", "severity": "high", "days_ago": 600, "confidence": 0.97, "kestrels": ["KSTRL-01", "KSTRL-02", "KSTRL-03", "KSTRL-04"], "latency_s": 142, "asset_idx": 17},
        {"type": "conjunction", "severity": "medium", "days_ago": 700, "confidence": 0.85, "kestrels": ["KSTRL-01", "KSTRL-02"], "latency_s": 395, "asset_idx": 18},
        {"type": "anomaly", "severity": "medium", "days_ago": 800, "confidence": 0.78, "kestrels": ["KSTRL-02", "KSTRL-04"], "latency_s": 270, "asset_idx": 19},
        {"type": "fragmentation", "severity": "low", "days_ago": 900, "confidence": 0.82, "kestrels": ["KSTRL-01"], "latency_s": 480, "asset_idx": 20},
        {"type": "conjunction", "severity": "low", "days_ago": 1000, "confidence": 0.69, "kestrels": ["KSTRL-03"], "latency_s": 610, "asset_idx": 21},
        {"type": "anomaly", "severity": "high", "days_ago": 1100, "confidence": 0.93, "kestrels": ["KSTRL-03", "KSTRL-04", "KSTRL-01"], "latency_s": 188, "asset_idx": 22},
        {"type": "fragmentation", "severity": "medium", "days_ago": 1200, "confidence": 0.86, "kestrels": ["KSTRL-01", "KSTRL-03"], "latency_s": 222, "asset_idx": 23},
        {"type": "conjunction", "severity": "high", "days_ago": 1500, "confidence": 0.90, "kestrels": ["KSTRL-01", "KSTRL-03", "KSTRL-02"], "latency_s": 198, "asset_idx": 24},
    ]

    for i, tmpl in enumerate(event_templates):
        le_key = f"LE-2026-{i+1:03d}"
        asset_idx = min(tmpl["asset_idx"], len(insured_assets) - 1)
        asset = insured_assets[asset_idx]
        sat_key = asset["sat_key"]
        occurred = ts_past(days=tmpl["days_ago"], hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
        witness_keys = tmpl["kestrels"]
        le_doc = {
            "_key": le_key,
            "event_type": tmpl["type"],
            "occurred_at": occurred,
            "primary_object_id": f"objects/{sat_key}",
            "severity": tmpl["severity"],
            "evidence_refs": [],
            "estimated_debris_count": rng.randint(20, 300) if tmpl["type"] == "fragmentation" else None,
            "shell_id": f"shells/{SHELL_FOR_REGIME.get(asset['shell_key'], 'LEO_540_560')}",
            "witnessed_by_kestrels": [f"kestrels/{k}" for k in witness_keys],
            "first_witness_at": occurred,
            "confirmation_latency_s": tmpl["latency_s"],
            "confidence": tmpl["confidence"],
            "total_sum_at_risk": int(asset["sum_insured_m"] * 1_000_000 * rng.uniform(0.3, 1.0)),
            "active": tmpl.get("active", False),
            "evidence_package": {},
        }
        upsert(COLLECTION_LOSS_EVENTS, le_doc)
        le_docs.append(le_doc)

        upsert_edge(EDGE_INSURANCE_LOSS_EVENT_INVOLVES, {
            "_key": f"LEI-{le_key}-primary",
            "_from": f"loss_events/{le_key}",
            "_to": f"objects/{sat_key}",
            "role": "primary",
        })
        for k_key in witness_keys:
            upsert_edge(EDGE_INSURANCE_EVENT_WITNESSED_BY, {
                "_key": f"EWB-{le_key}-{k_key}",
                "_from": f"loss_events/{le_key}",
                "_to": f"kestrels/{k_key}",
                "witnessed_at": occurred,
                "independence_score": round(rng.uniform(0.7, 1.0), 2),
            })

        witness_obs_ids = []
        witness_obs_hashes = []
        fusion_id = f"FG-{le_key}"
        existing_for_event = find_existing_obs_near(asset["norad_id"], occurred, limit=max(len(witness_keys) * 2, 6))
        for j, k_key in enumerate(witness_keys):
            if not existing_for_event:
                break
            geom = round(rng.uniform(0.55, 0.92), 2)
            obs_doc = existing_for_event.pop(0)
            obs_doc = amend_obs(obs_doc, k_key, fusion_group_id=fusion_id, geometry_quality=geom)
            obs_id = obs_doc["_key"]
            witness_obs_ids.append(f"observations/{obs_id}")
            epoch = obs_doc.get("observation_epoch") or obs_doc.get("observed_at") or occurred
            custody = obs_doc.get("compliance", {}).get("custody_hash") or sha256_stub(f"{obs_id}:{epoch}")
            witness_obs_hashes.append(custody)
            upsert_edge(EDGE_INSURANCE_KESTREL_OBSERVED, {
                "_key": f"KO-{le_key}-{k_key}",
                "_from": f"kestrels/{k_key}",
                "_to": f"observations/{obs_id}",
            })

        evidence_pkg = _evidence_package(witness_obs_hashes, occurred)
        le_doc["evidence_refs"] = witness_obs_ids
        le_doc["evidence_package"] = evidence_pkg
        db_module.db.collection(COLLECTION_LOSS_EVENTS).update({"_key": le_key, "evidence_refs": witness_obs_ids, "evidence_package": evidence_pkg})

    print(f"  Loss events: {len(le_docs)} ({sum(1 for e in le_docs if e.get('active'))} active)")

    print("Creating claims for high-severity events...")
    clm_count = 0
    for le_doc in le_docs:
        if le_doc["severity"] in ("high", "medium") and not le_doc.get("active"):
            for pol_ref in policy_refs:
                if pol_ref["asset"]["sat_key"] == le_doc["primary_object_id"].split("/")[-1]:
                    clm_key = f"CLM-{le_doc['_key']}"
                    clm = {
                        "_key": clm_key,
                        "claim_number": f"AR-{clm_key}",
                        "policy_id": f"policies/{pol_ref['pol_key']}",
                        "loss_event_id": f"loss_events/{le_doc['_key']}",
                        "status": rng.choice(["reserved", "paid", "closed"]),
                        "notified_date": (NOW - timedelta(days=rng.randint(1, 30))).strftime("%Y-%m-%d"),
                        "reserve": int(pol_ref["sum_insured"] * rng.uniform(0.3, 0.9)),
                        "paid": 0,
                        "currency": "USD",
                    }
                    upsert(COLLECTION_CLAIMS, clm)
                    upsert_edge(EDGE_INSURANCE_CLAIM_ARISES_FROM, {
                        "_key": f"CAF-{clm_key}",
                        "_from": f"claims/{clm_key}",
                        "_to": f"loss_events/{le_doc['_key']}",
                    })
                    clm_count += 1
                    break
    print(f"  Claims: {clm_count}")

    print("Creating coverage windows (24h per insured asset) and amending existing observations...")
    cw_count = 0
    obs_amended = 0
    kestrel_keys = [k["_key"] for k in KESTRELS if k["status"] == "operational"]
    for asset in insured_assets:
        sat_key = asset["sat_key"]
        for hour in range(24):
            window_start_dt = NOW + timedelta(hours=hour)
            for k_key in rng.sample(kestrel_keys, min(rng.randint(1, 3), len(kestrel_keys))):
                window_start = window_start_dt.isoformat()
                window_end = (window_start_dt + timedelta(minutes=rng.randint(8, 18))).isoformat()
                cw_key = f"CW-{k_key}-{sat_key[:12]}-{hour:02d}"
                upsert(COLLECTION_COVERAGE_WINDOWS, {
                    "_key": cw_key,
                    "kestrel_id": f"kestrels/{k_key}",
                    "target_id": f"objects/{sat_key}",
                    "window_start": window_start,
                    "window_end": window_end,
                    "max_elevation_deg": round(rng.uniform(15, 75), 1),
                    "geometry_quality": round(rng.uniform(0.45, 0.95), 2),
                    "computed_at": NOW.isoformat(),
                })
                upsert_edge(EDGE_INSURANCE_KESTREL_CAN_SEE, {
                    "_key": f"KCS-{k_key}-{sat_key[:12]}",
                    "_from": f"kestrels/{k_key}",
                    "_to": f"objects/{sat_key}",
                    "next_window": window_start,
                    "median_revisit_min": rng.randint(8, 22),
                })
                cw_count += 1

        existing_obs = find_existing_obs_for_asset(asset["norad_id"], limit=50)
        for obs_doc in existing_obs:
            k_key = rng.choice(kestrel_keys)
            amend_obs(obs_doc, k_key)
            upsert_edge(EDGE_INSURANCE_KESTREL_OBSERVED, {
                "_key": f"KO-COV-{obs_doc['_key'][:24]}",
                "_from": f"kestrels/{k_key}",
                "_to": f"observations/{obs_doc['_key']}",
            })
            obs_amended += 1

    print(f"  Coverage windows: {cw_count}")
    print(f"  Observations amended with insurance fields: {obs_amended}")

    print("Creating kestrel task queue...")
    def _asset_key(idx):
        return insured_assets[min(idx, len(insured_assets) - 1)]["sat_key"]

    tasks = [
        {"_key": "TSK-2026-001", "kestrel_id": "kestrels/KSTRL-03", "target_id": f"objects/{_asset_key(0)}", "task_type": "priority_observation", "requested_by": "user/underwriter-001", "requested_at": ts_past(hours=3), "scheduled_for": ts_past(hours=2, minutes=55), "executed_at": ts_past(hours=2, minutes=54), "status": "completed", "result_observation_ids": le_docs[0].get("evidence_refs", [])[:1] if le_docs else [], "trigger_event_id": "loss_events/LE-2026-001"},
        {"_key": "TSK-2026-002", "kestrel_id": "kestrels/KSTRL-02", "target_id": f"objects/{_asset_key(1)}", "task_type": "priority_observation", "requested_by": "user/underwriter-001", "requested_at": ts_past(hours=2), "scheduled_for": ts_past(hours=1, minutes=55), "executed_at": ts_past(hours=1, minutes=54), "status": "completed", "result_observation_ids": [], "trigger_event_id": "loss_events/LE-2026-002"},
        {"_key": "TSK-2026-003", "kestrel_id": "kestrels/KSTRL-03", "target_id": f"objects/{_asset_key(2)}", "task_type": "priority_observation", "requested_by": "user/underwriter-002", "requested_at": ts_past(hours=1), "scheduled_for": ts_past(minutes=55), "executed_at": ts_past(minutes=50), "status": "completed", "result_observation_ids": [], "trigger_event_id": None},
        {"_key": "TSK-2026-004", "kestrel_id": "kestrels/KSTRL-03", "target_id": f"objects/{_asset_key(3)}", "task_type": "scheduled_pass", "requested_by": "system", "requested_at": ts_past(minutes=30), "scheduled_for": ts_future(minutes=10), "executed_at": None, "status": "scheduled", "result_observation_ids": [], "trigger_event_id": None},
        {"_key": "TSK-2026-005", "kestrel_id": "kestrels/KSTRL-01", "target_id": f"objects/{_asset_key(4)}", "task_type": "renewal_survey", "requested_by": "user/underwriter-001", "requested_at": ts_past(minutes=10), "scheduled_for": ts_future(minutes=5), "executed_at": None, "status": "executing", "result_observation_ids": [], "trigger_event_id": None},
    ]
    for task in tasks:
        upsert(COLLECTION_KESTREL_TASKS, task)
        upsert_edge(EDGE_INSURANCE_TASK_TARGETS, {
            "_key": f"TT-{task['_key']}",
            "_from": f"kestrel_tasks/{task['_key']}",
            "_to": task["target_id"],
        })
    print(f"  Kestrel tasks: {len(tasks)}")

    print()
    print("=== Seed complete ===")
    print(f"  {len(insured_assets)} insured assets across {len(SHELLS)} shells")
    print(f"  {len(KESTRELS)} Kestrels (3 operational, 1 degraded)")
    print(f"  {len(le_docs)} loss events ({sum(1 for e in le_docs if e.get('active'))} active overnight)")
    print("  Risk scores + anomaly predictions: 7 months history per asset")
    print("  Coverage windows: 24h forward-looking per asset")


if __name__ == "__main__":
    main()
