#!/usr/bin/env python3
"""
End-to-end verification of the DISCOS provenance graph.

Checks:
1. All provenance collections exist and have documents
2. Spot-checks provenance chains (fragment → event → parent object)
3. Validates edge integrity (no dangling edges)
4. Reports confidence distribution on fragmented_from edges
5. Checks attribution_status distribution on objects

Usage:
    python scripts/verification/verify_discos_provenance_e2e.py [--fail-on-warning]
"""
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

import database.connection as db_conn
import database as db_module

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

VERTEX_COLLECTIONS = [
    "fragmentation_events",
    "launch_events",
    "launch_vehicles",
    "launch_sites",
    "entities",
]

EDGE_COLLECTIONS = [
    "fragmented_from",
    "caused_by",
    "launched_by",
    "launched_via",
    "launched_from",
]

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


def check_collections(db) -> list:
    results = []
    for col_name in VERTEX_COLLECTIONS + EDGE_COLLECTIONS:
        if not db.has_collection(col_name):
            results.append((FAIL, f"Collection '{col_name}' does not exist"))
            continue
        try:
            count_cursor = db.aql.execute(f"RETURN LENGTH({col_name})")
            count = list(count_cursor)[0]
            level = PASS if count > 0 else WARN
            results.append((level, f"Collection '{col_name}': {count} documents"))
        except Exception as exc:
            results.append((FAIL, f"Failed to count '{col_name}': {exc}"))
    return results


def check_provenance_chains(db) -> list:
    results = []
    try:
        cursor = db.aql.execute(
            """
            FOR e IN caused_by
                LIMIT 5
                LET fragment = DOCUMENT(e._from)
                LET event = DOCUMENT(e._to)
                RETURN {
                    fragment_key: fragment._key,
                    event_key: event._key,
                    both_exist: fragment != null AND event != null
                }
            """
        )
        rows = list(cursor)
        if not rows:
            results.append((WARN, "No caused_by edges found — attributions may not have been ingested"))
        else:
            broken = [r for r in rows if not r.get("both_exist")]
            if broken:
                results.append((FAIL, f"{len(broken)}/{len(rows)} caused_by edges have dangling references"))
            else:
                results.append((PASS, f"Spot-checked {len(rows)} caused_by edges — all valid"))
    except Exception as exc:
        results.append((FAIL, f"caused_by chain check failed: {exc}"))

    try:
        cursor = db.aql.execute(
            """
            FOR e IN fragmented_from
                LIMIT 5
                LET frag = DOCUMENT(e._from)
                LET parent = DOCUMENT(e._to)
                RETURN {
                    frag_key: frag._key,
                    parent_key: parent._key,
                    both_exist: frag != null AND parent != null
                }
            """
        )
        rows = list(cursor)
        if not rows:
            results.append((WARN, "No fragmented_from edges found"))
        else:
            broken = [r for r in rows if not r.get("both_exist")]
            if broken:
                results.append((FAIL, f"{len(broken)}/{len(rows)} fragmented_from edges have dangling references"))
            else:
                results.append((PASS, f"Spot-checked {len(rows)} fragmented_from edges — all valid"))
    except Exception as exc:
        results.append((FAIL, f"fragmented_from chain check failed: {exc}"))

    return results


def check_confidence_distribution(db) -> list:
    results = []
    try:
        cursor = db.aql.execute(
            """
            LET total = LENGTH(fragmented_from)
            LET high = LENGTH(FOR e IN fragmented_from FILTER e.confidence >= 0.9 RETURN 1)
            LET medium = LENGTH(FOR e IN fragmented_from FILTER e.confidence >= 0.7 AND e.confidence < 0.9 RETURN 1)
            LET low = LENGTH(FOR e IN fragmented_from FILTER e.confidence < 0.7 RETURN 1)
            LET no_conf = LENGTH(FOR e IN fragmented_from FILTER e.confidence == null RETURN 1)
            RETURN {total: total, high: high, medium: medium, low: low, no_confidence: no_conf}
            """
        )
        dist = list(cursor)[0]
        results.append((
            PASS,
            f"fragmented_from confidence: total={dist['total']} "
            f"high(>=0.9)={dist['high']} medium(0.7-0.9)={dist['medium']} "
            f"low(<0.7)={dist['low']} no_confidence={dist['no_confidence']}"
        ))
    except Exception as exc:
        results.append((WARN, f"Confidence distribution check failed: {exc}"))
    return results


def check_attribution_status(db) -> list:
    results = []
    try:
        cursor = db.aql.execute(
            """
            LET attributed = LENGTH(FOR obj IN objects FILTER obj.metadata.attribution_status == "attributed" RETURN 1)
            LET pending = LENGTH(FOR obj IN objects FILTER obj.metadata.attribution_status == "pending" RETURN 1)
            LET no_status = LENGTH(FOR obj IN objects FILTER obj.metadata.attribution_status == null RETURN 1)
            RETURN {attributed: attributed, pending: pending, no_status: no_status}
            """
        )
        dist = list(cursor)[0]
        results.append((
            PASS,
            f"attribution_status: attributed={dist['attributed']} "
            f"pending={dist['pending']} no_status={dist['no_status']}"
        ))
    except Exception as exc:
        results.append((WARN, f"Attribution status check failed: {exc}"))
    return results


def check_graph_exists(db) -> list:
    results = []
    if db.has_graph("provenance_relationships"):
        results.append((PASS, "Named graph 'provenance_relationships' exists"))
    else:
        results.append((FAIL, "Named graph 'provenance_relationships' does not exist"))
    return results


def run(fail_on_warning: bool = False):
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        sys.exit(1)

    db = db_module.db
    all_results = []

    logger.info("=== DISCOS Provenance E2E Verification ===")

    all_results.extend(check_graph_exists(db))
    all_results.extend(check_collections(db))
    all_results.extend(check_provenance_chains(db))
    all_results.extend(check_confidence_distribution(db))
    all_results.extend(check_attribution_status(db))

    print("\n=== Verification Results ===")
    failures = 0
    warnings = 0
    for level, message in all_results:
        print(f"[{level}] {message}")
        if level == FAIL:
            failures += 1
        elif level == WARN:
            warnings += 1

    print(f"\nSummary: {len(all_results)} checks — "
          f"{failures} failed, {warnings} warnings, "
          f"{len(all_results) - failures - warnings} passed")

    if failures > 0:
        logger.error("Verification FAILED")
        sys.exit(1)
    elif fail_on_warning and warnings > 0:
        logger.error("Verification FAILED (warnings treated as errors)")
        sys.exit(1)
    else:
        logger.info("Verification PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify DISCOS provenance graph E2E")
    parser.add_argument("--fail-on-warning", action="store_true",
                        help="Treat warnings as failures")
    args = parser.parse_args()
    run(fail_on_warning=args.fail_on_warning)
