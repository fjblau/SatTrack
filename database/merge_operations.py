"""
Object merge utility — supersedes scripts/maintenance/merge_duplicates.py.

Merges a secondary object document into a primary, rewriting all incoming
and outgoing edges, recording a full audit trail, and marking the secondary
as merged.  Can be called directly as a Python import or via the admin HTTP
endpoint POST /v2/admin/merge-objects.

Alias conflict policy: aliases from both documents are merged; if the same
alias key has different values, the primary's value wins and the conflict is
logged in the audit record.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import database.connection as db_conn
from database.connection import COLLECTION_NAME


_EDGE_COLLECTIONS = [
    "constellation_membership",
    "registration_links",
    "orbital_proximity",
    "collision_risk_edges",
    "satellite_lineage",
    "observation_satellite_edges",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_doc(key: str) -> Optional[Dict[str, Any]]:
    aql = """
    FOR doc IN @@collection
        FILTER doc._key == @key OR doc.identifier == @key
        LIMIT 1
        RETURN doc
    """
    cursor = db_conn.db.aql.execute(
        aql,
        bind_vars={"@collection": COLLECTION_NAME, "key": key},
    )
    results = list(cursor)
    return results[0] if results else None


def _rewrite_edges(old_id: str, new_id: str, edge_collection: str) -> int:
    """Rewrite all edges in edge_collection that reference old_id to new_id."""
    count = 0
    for field in ("_from", "_to"):
        aql = f"""
        FOR edge IN {edge_collection}
            FILTER edge.{field} == @old_id
            UPDATE edge WITH {{ {field}: @new_id }} IN {edge_collection}
            COLLECT WITH COUNT INTO c
            RETURN c
        """
        try:
            cursor = db_conn.db.aql.execute(
                aql,
                bind_vars={"old_id": old_id, "new_id": new_id},
            )
            result = list(cursor)
            count += result[0] if result else 0
        except Exception:
            pass
    return count


def merge_objects(
    primary_key: str,
    secondary_key: str,
    operator: str = "system",
    reason: str = "",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Merge secondary object into primary.

    Args:
        primary_key: _key or identifier of the document to keep
        secondary_key: _key or identifier of the document to merge in and retire
        operator: Identity of the operator performing the merge (for audit)
        reason: Human-readable reason for the merge
        dry_run: If True, validate and return plan but make no changes

    Returns:
        Audit record describing what was (or would be) done
    """
    primary = _get_doc(primary_key)
    if primary is None:
        raise ValueError(f"Primary document not found: {primary_key}")

    secondary = _get_doc(secondary_key)
    if secondary is None:
        raise ValueError(f"Secondary document not found: {secondary_key}")

    if primary["_id"] == secondary["_id"]:
        raise ValueError("Primary and secondary documents are the same")

    primary_id = primary["_id"]
    secondary_id = secondary["_id"]
    ts = _now()

    primary_aliases: Dict[str, Any] = primary.get("identifier_aliases") or {}
    secondary_aliases: Dict[str, Any] = secondary.get("identifier_aliases") or {}

    merged_aliases = dict(secondary_aliases)
    merged_aliases.update(primary_aliases)

    alias_conflicts: List[Dict[str, Any]] = []
    for k, sv in secondary_aliases.items():
        pv = primary_aliases.get(k)
        if pv is not None and pv != sv:
            alias_conflicts.append({"key": k, "primary_value": pv, "secondary_value": sv, "resolution": "primary_wins"})

    edge_rewrites: Dict[str, int] = {}
    if not dry_run:
        for ecol in _EDGE_COLLECTIONS:
            try:
                count = _rewrite_edges(secondary_id, primary_id, ecol)
                if count:
                    edge_rewrites[ecol] = count
            except Exception:
                pass

        primary_canonical = primary.get("canonical", {})
        secondary_canonical = secondary.get("canonical", {})
        merged_canonical = dict(secondary_canonical)
        merged_canonical.update(primary_canonical)

        primary_sources = primary.get("sources", {})
        secondary_sources = secondary.get("sources", {})
        merged_sources = dict(secondary_sources)
        merged_sources.update(primary_sources)

        merge_record = {
            "timestamp": ts,
            "source_field": "merge_objects",
            "target_field": "merge_objects",
            "value": {
                "merged_from": secondary_id,
                "operator": operator,
                "reason": reason,
            },
            "promoted_by": "merge_operations",
        }

        existing_transformations = primary.get("metadata", {}).get("transformations") or []

        update_aql = """
        UPDATE @key WITH {
            canonical: @canonical,
            sources: @sources,
            identifier_aliases: @aliases,
            metadata: MERGE(DOCUMENT(@@collection, @key).metadata || {}, {
                transformations: APPEND(@transformations, [@merge_record]),
                last_updated_at: @ts,
                merged_from: APPEND(
                    DOCUMENT(@@collection, @key).metadata.merged_from || [],
                    [@secondary_id]
                )
            })
        } IN @@collection
        """
        db_conn.db.aql.execute(
            update_aql,
            bind_vars={
                "@collection": COLLECTION_NAME,
                "key": primary["_key"],
                "canonical": merged_canonical,
                "sources": merged_sources,
                "aliases": merged_aliases,
                "transformations": existing_transformations,
                "merge_record": merge_record,
                "ts": ts,
                "secondary_id": secondary_id,
            },
        )

        retire_aql = """
        UPDATE @key WITH {
            _merged_into: @primary_id,
            _retired_at: @ts,
            _retired_by: @operator,
            metadata: MERGE(DOCUMENT(@@collection, @key).metadata || {}, {
                merged_into: @primary_id,
                retired_at: @ts,
                retired_by: @operator,
                last_updated_at: @ts
            })
        } IN @@collection
        """
        db_conn.db.aql.execute(
            retire_aql,
            bind_vars={
                "@collection": COLLECTION_NAME,
                "key": secondary["_key"],
                "primary_id": primary_id,
                "ts": ts,
                "operator": operator,
            },
        )

    audit = {
        "dry_run": dry_run,
        "timestamp": ts,
        "operator": operator,
        "reason": reason,
        "primary_id": primary_id,
        "secondary_id": secondary_id,
        "alias_conflicts": alias_conflicts,
        "merged_aliases": merged_aliases if dry_run else {},
        "edge_rewrites": edge_rewrites,
        "status": "dry_run" if dry_run else "completed",
    }
    return audit
