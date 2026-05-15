#!/usr/bin/env python3
"""
Migrate: Nest flat observation fields into their correct sub-objects.

The kestrel_proxy_v2 importer originally stored several sensor-group fields
at the top level of each observation document instead of nested under their
schema sub-objects.  This migration finds all observations with any of those
flat fields and moves them into the correct structure:

  Flat field               → Nested path
  ─────────────────────────────────────────────────────────────────────
  roll_deg                 → attitude.roll_deg
  pitch_deg                → attitude.pitch_deg
  yaw_deg                  → attitude.yaw_deg
  stability_flag           → attitude.stability_flag
  reflectivity_index       → material_signature.reflectivity_index
  inferred_material        → material_signature.inferred_material
  material_confidence      → material_signature.material_confidence
  range_km                 → proximity_state.range_km
  relative_velocity_ms     → proximity_state.relative_velocity_ms
  delta_v_residual_ms      → maneuver_indicator.delta_v_residual_ms
  maneuver_confidence      → maneuver_indicator.maneuver_confidence
  maneuver_flag            → maneuver_indicator.maneuver_flag
  perigee_drift_km_per_day → orbital_decay_indicator.perigee_drift_km_per_day
  estimated_perigee_km     → orbital_decay_indicator.estimated_perigee_km

Existing values already present inside a sub-object are preserved; the flat
field value is merged in (the flat field wins on collision so re-runs are safe).
The flat top-level fields are removed after nesting.

Idempotent — documents that have already been migrated (no flat fields present)
are skipped by the FILTER clause.

USAGE:
    python scripts/migration/migrate_nest_observation_fields.py [--dry-run] [--yes]
"""
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import database.connection as db_conn
import database as db_module
from database.connection import COLLECTION_OBSERVATIONS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_FLAT_FIELDS = [
    "roll_deg", "pitch_deg", "yaw_deg", "stability_flag",
    "reflectivity_index", "inferred_material", "material_confidence",
    "range_km", "relative_velocity_ms",
    "delta_v_residual_ms", "maneuver_confidence", "maneuver_flag",
    "perigee_drift_km_per_day", "estimated_perigee_km",
]

_FILTER_CLAUSE = " OR ".join(f"obs.{f} != null" for f in _FLAT_FIELDS)

_COUNT_QUERY = f"""
RETURN COUNT(
    FOR obs IN @@col
        FILTER {_FILTER_CLAUSE}
        RETURN 1
)
"""

_MIGRATE_QUERY = f"""
FOR obs IN @@col
    FILTER {_FILTER_CLAUSE}

    LET new_attitude = MERGE(
        obs.attitude || {{}},
        obs.roll_deg        != null ? {{roll_deg:        obs.roll_deg}}        : {{}},
        obs.pitch_deg       != null ? {{pitch_deg:       obs.pitch_deg}}       : {{}},
        obs.yaw_deg         != null ? {{yaw_deg:         obs.yaw_deg}}         : {{}},
        obs.stability_flag  != null ? {{stability_flag:  obs.stability_flag}}  : {{}}
    )

    LET new_material_signature = MERGE(
        obs.material_signature || {{}},
        obs.reflectivity_index  != null ? {{reflectivity_index:  obs.reflectivity_index}}  : {{}},
        obs.inferred_material   != null ? {{inferred_material:   obs.inferred_material}}   : {{}},
        obs.material_confidence != null ? {{material_confidence: obs.material_confidence}} : {{}}
    )

    LET new_proximity_state = MERGE(
        obs.proximity_state || {{}},
        obs.range_km             != null ? {{range_km:             obs.range_km}}             : {{}},
        obs.relative_velocity_ms != null ? {{relative_velocity_ms: obs.relative_velocity_ms}} : {{}}
    )

    LET new_maneuver_indicator = MERGE(
        obs.maneuver_indicator || {{}},
        obs.delta_v_residual_ms != null ? {{delta_v_residual_ms: obs.delta_v_residual_ms}} : {{}},
        obs.maneuver_confidence != null ? {{maneuver_confidence: obs.maneuver_confidence}} : {{}},
        obs.maneuver_flag       != null ? {{maneuver_flag:       obs.maneuver_flag}}       : {{}}
    )

    LET new_orbital_decay_indicator = MERGE(
        obs.orbital_decay_indicator || {{}},
        obs.perigee_drift_km_per_day != null ? {{perigee_drift_km_per_day: obs.perigee_drift_km_per_day}} : {{}},
        obs.estimated_perigee_km     != null ? {{estimated_perigee_km:     obs.estimated_perigee_km}}     : {{}}
    )

    LET cleaned = UNSET(obs,
        "roll_deg", "pitch_deg", "yaw_deg", "stability_flag",
        "reflectivity_index", "inferred_material", "material_confidence",
        "range_km", "relative_velocity_ms",
        "delta_v_residual_ms", "maneuver_confidence", "maneuver_flag",
        "perigee_drift_km_per_day", "estimated_perigee_km"
    )

    LET updated = MERGE(
        cleaned,
        LENGTH(new_attitude)                > 0 ? {{attitude:                new_attitude}}                : {{}},
        LENGTH(new_material_signature)      > 0 ? {{material_signature:      new_material_signature}}      : {{}},
        LENGTH(new_proximity_state)         > 0 ? {{proximity_state:         new_proximity_state}}         : {{}},
        LENGTH(new_maneuver_indicator)      > 0 ? {{maneuver_indicator:      new_maneuver_indicator}}      : {{}},
        LENGTH(new_orbital_decay_indicator) > 0 ? {{orbital_decay_indicator: new_orbital_decay_indicator}} : {{}}
    )

    REPLACE obs WITH updated IN @@col
    COLLECT WITH COUNT INTO migrated
    RETURN migrated
"""


def run(dry_run: bool = False, yes: bool = False) -> bool:
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        return False

    db = db_module.db

    bind = {"@col": COLLECTION_OBSERVATIONS}

    count_cursor = db.aql.execute(_COUNT_QUERY, bind_vars=bind)
    affected = list(count_cursor)[0] or 0

    logger.info(f"Observation documents with flat (un-nested) sensor fields: {affected}")

    if affected == 0:
        logger.info("Nothing to migrate — all documents already use nested sub-objects.")
        return True

    if dry_run:
        logger.info(f"[DRY RUN] Would migrate {affected} documents. No changes made.")
        return True

    if yes:
        logger.info(f"Migrating {affected} documents (--yes flag set).")
    else:
        try:
            response = input(
                f"\nMigrate {affected} observation documents? "
                f"(moves flat sensor fields into nested sub-objects) (y/N): "
            ).strip().lower()
        except EOFError:
            logger.error("stdin is not interactive. Re-run with --yes to skip this prompt.")
            return False
        if response not in ("y", "yes"):
            logger.info("Cancelled.")
            return False

    cursor = db.aql.execute(_MIGRATE_QUERY, bind_vars=bind)
    migrated = list(cursor)[0] or 0
    logger.info(f"Migrated {migrated} documents.")

    remaining_cursor = db.aql.execute(_COUNT_QUERY, bind_vars=bind)
    remaining = list(remaining_cursor)[0] or 0
    if remaining > 0:
        logger.warning(f"{remaining} documents still have flat fields — investigate.")
        return False

    logger.info("Migration complete. All observations use nested sensor sub-objects.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate flat observation fields into nested sub-objects"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()
    success = run(dry_run=args.dry_run, yes=args.yes)
    sys.exit(0 if success else 1)
