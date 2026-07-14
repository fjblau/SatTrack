#!/usr/bin/env python3
"""
Fast bulk GCAT import using ArangoDB batch operations.

Strategy:
  1. Load all existing NORAD IDs + intl designators from DB in two queries
  2. Parse entire gcat_satcat.tsv in memory, classify each record as new/existing
  3. Bulk-insert all new records via collection.import_bulk()
  4. Batch-update existing records via AQL in chunks of CHUNK_SIZE

This avoids the N+1 query problem of the original import script.

USAGE:
    python import_gcat_bulk.py [tsv_path] [cutoff_date] [--dry-run]
    python import_gcat_bulk.py gcat_satcat.tsv 1957-01-01
"""

import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import database.connection as db_conn
from database import connect_arangodb, get_satellites_collection

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

CHUNK_SIZE = 500


def normalize_string(value):
    if value is None or value == "":
        return None
    s = str(value).strip()
    return None if s.lower() in ("nan", "n/a", "none", "", "-") else s


def convert_int(value):
    if value is None or value == "":
        return None
    try:
        s = str(value).strip()
        return None if s.lower() in ("nan", "n/a", "none", "-") else int(s)
    except (ValueError, TypeError):
        return None


def convert_float(value):
    if value is None or value == "":
        return None
    try:
        s = str(value).strip()
        if s.lower() in ("nan", "n/a", "none", "-"):
            return None
        f = float(s)
        import math
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (ValueError, TypeError):
        return None


def parse_gcat_date(date_str):
    if not date_str or date_str.strip() == "-":
        return None
    try:
        s = " ".join(date_str.strip().split())
        return datetime.strptime(s, "%Y %b %d").strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return None


def is_after_date(launch_date, cutoff_date):
    if not launch_date or not cutoff_date:
        return False
    try:
        return datetime.strptime(launch_date, "%Y-%m-%d") > datetime.strptime(cutoff_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return False


def normalize_gcat_object_type(gcat_type):
    if not gcat_type:
        return "UNKNOWN"
    t = gcat_type.strip()
    if not t or t == "-":
        return "UNKNOWN"
    b = t[0].upper()
    if b in ("P", "S"):
        return "PAYLOAD"
    if b == "D":
        return "DEBRIS"
    if b in ("C", "R"):
        return "ROCKET BODY"
    return "UNKNOWN"


def safe_key(identifier):
    return (identifier
            .replace("/", "_").replace(":", "_").replace(".", "_")
            .replace("*", "_STAR_").replace(" ", "_")
            .replace("(", "_").replace(")", "_"))


def parse_tsv(tsv_path, cutoff_date):
    records = []
    skipped_old = 0
    skipped_invalid = 0

    with open(tsv_path, "r", encoding="utf-8") as f:
        for row_num, line in enumerate(f, start=1):
            if row_num <= 2:
                continue
            try:
                fields = line.rstrip("\n").split("\t")
                if len(fields) < 42:
                    skipped_invalid += 1
                    continue

                jcat       = normalize_string(fields[0])
                satcat     = normalize_string(fields[1])
                launch_tag = normalize_string(fields[2])
                piece      = normalize_string(fields[3])
                obj_type   = normalize_string(fields[4])
                name       = normalize_string(fields[5])
                plname     = normalize_string(fields[6])
                ldate      = normalize_string(fields[7])
                parent     = normalize_string(fields[8])
                sdate      = normalize_string(fields[9])
                primary    = normalize_string(fields[10])
                ddate      = normalize_string(fields[11])
                status     = normalize_string(fields[12])
                dest       = normalize_string(fields[13])
                owner      = normalize_string(fields[14])
                state      = normalize_string(fields[15])
                manufacturer = normalize_string(fields[16])
                bus        = normalize_string(fields[17])
                motor      = normalize_string(fields[18])
                mass       = convert_float(fields[19])
                perigee    = convert_float(fields[33])
                apogee     = convert_float(fields[35])
                inclination = convert_float(fields[37])

                norad_id    = convert_int(satcat)
                launch_date = parse_gcat_date(ldate)
                canonical_object_type = normalize_gcat_object_type(obj_type)

                if cutoff_date and not is_after_date(launch_date, cutoff_date):
                    skipped_old += 1
                    continue

                gcat_data = {k: v for k, v in {
                    "jcat": jcat,
                    "norad_cat_id": norad_id,
                    "international_designator": launch_tag,
                    "piece": piece,
                    "object_type": canonical_object_type,
                    "gcat_type_raw": obj_type,
                    "name": name or plname,
                    "payload_name": plname,
                    "date_of_launch": launch_date,
                    "launch_date": launch_date,
                    "parent": parent,
                    "separation_date": parse_gcat_date(sdate),
                    "primary": primary,
                    "decay_date": parse_gcat_date(ddate),
                    "status": status,
                    "destination": dest,
                    "owner": owner,
                    "country_of_origin": state,
                    "manufacturer": manufacturer,
                    "bus": bus,
                    "motor": motor,
                    "mass_kg": mass,
                    "perigee_km": perigee,
                    "apogee_km": apogee,
                    "inclination_degrees": inclination,
                }.items() if v is not None}

                records.append({
                    "jcat": jcat,
                    "norad_id": norad_id,
                    "intl_designator": launch_tag,
                    "launch_date": launch_date,
                    "canonical_object_type": canonical_object_type,
                    "name": name or plname,
                    "gcat_data": gcat_data,
                })
            except Exception as e:
                skipped_invalid += 1

    return records, skipped_old, skipped_invalid


def fetch_existing_ids(db, collection_name):
    """Return sets of (norad_ids, intl_designators) already in the DB."""
    norad_set = set()
    intl_set  = set()

    cursor = db.aql.execute("""
        FOR doc IN @@col
            RETURN {
                norad: doc.canonical.norad_cat_id,
                intl:  doc.canonical.international_designator,
                key:   doc._key
            }
    """, bind_vars={"@col": collection_name}, batch_size=5000)

    key_to_norad = {}
    key_to_intl  = {}
    for row in cursor:
        if row["norad"] is not None:
            norad_set.add(int(row["norad"]))
        if row["intl"]:
            intl_set.add(row["intl"])

    return norad_set, intl_set


def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def import_gcat_bulk(tsv_path, cutoff_date="1957-01-01", dry_run=False):
    print(f"Parsing {tsv_path}...")
    records, skipped_old, skipped_invalid = parse_tsv(tsv_path, cutoff_date)
    print(f"  Parsed {len(records):,} records  |  skipped_old={skipped_old:,}  skipped_invalid={skipped_invalid:,}")

    if dry_run:
        print("[DRY-RUN] Would write to database. Exiting.")
        return True

    if not connect_arangodb():
        print("Failed to connect to ArangoDB")
        return False

    db         = db_conn.db
    col_name   = db_conn.COLLECTION_NAME
    collection = get_satellites_collection()
    timestamp  = datetime.now(timezone.utc).isoformat()

    print("Fetching existing IDs from DB...")
    existing_norad, existing_intl = fetch_existing_ids(db, col_name)
    print(f"  DB has {len(existing_norad):,} NORAD IDs, {len(existing_intl):,} intl designators")

    new_docs      = []
    update_keys   = []  # list of (norad_id, intl_designator, gcat_data, canonical_object_type, launch_date)

    for r in records:
        norad = r["norad_id"]
        intl  = r["intl_designator"]
        if (norad and norad in existing_norad) or (intl and intl in existing_intl):
            update_keys.append(r)
        else:
            identifier = (f"GCAT-{r['jcat']}" if r["jcat"]
                          else f"NORAD-{norad}" if norad
                          else f"INTL-{intl}")
            new_docs.append({
                "_key": safe_key(identifier),
                "identifier": identifier,
                "canonical": {
                    "name": r["name"] or identifier,
                    "launch_date": r["launch_date"],
                    "object_type": r["canonical_object_type"],
                    "updated_at": timestamp,
                },
                "sources": {"gcat": {**r["gcat_data"], "updated_at": timestamp}},
                "metadata": {
                    "created_at": timestamp,
                    "last_updated_at": timestamp,
                    "sources_available": ["gcat"],
                    "source_priority": ["unoosa", "spacetrack", "celestrak", "tleapi", "kaggle"],
                },
            })

    print(f"\nPlan:  {len(new_docs):,} new inserts  |  {len(update_keys):,} source enrichments")

    # ── Bulk insert new records ──────────────────────────────────────────────
    inserted = 0
    errors   = 0
    if new_docs:
        print(f"\nBulk inserting {len(new_docs):,} new records in chunks of {CHUNK_SIZE}...")
        for i, batch in enumerate(chunk(new_docs, CHUNK_SIZE)):
            result = collection.import_bulk(batch, on_duplicate="ignore")
            inserted += result.get("created", 0)
            errors   += result.get("errors", 0)
            if (i + 1) % 20 == 0:
                print(f"  Inserted {inserted:,} / {len(new_docs):,}...")
        print(f"  ✓ Inserted {inserted:,}  errors={errors:,}")

    # ── Batch update existing records ────────────────────────────────────────
    updated = 0
    if update_keys:
        print(f"\nEnriching {len(update_keys):,} existing records in chunks of {CHUNK_SIZE}...")
        for i, batch in enumerate(chunk(update_keys, CHUNK_SIZE)):
            aql = """
            FOR row IN @batch
                FOR doc IN @@col
                    FILTER (row.norad_id != null AND doc.canonical.norad_cat_id == row.norad_id)
                        OR (row.intl_designator != null AND doc.canonical.international_designator == row.intl_designator)
                    LIMIT 1

                    LET fill_object_type = (doc.canonical.object_type == null AND row.canonical_object_type != null)
                        ? row.canonical_object_type : null
                    LET fill_launch_date = (doc.canonical.launch_date == null AND row.launch_date != null)
                        ? row.launch_date : null

                    UPDATE doc WITH {
                        sources: MERGE(doc.sources, {
                            gcat: MERGE(row.gcat_data, { updated_at: @ts })
                        }),
                        canonical: MERGE(doc.canonical,
                            MERGE(
                                fill_object_type != null ? { object_type: fill_object_type } : {},
                                fill_launch_date != null ? { launch_date: fill_launch_date } : {}
                            )
                        ),
                        metadata: MERGE(doc.metadata, {
                            sources_available: UNIQUE(APPEND(doc.metadata.sources_available || [], ["gcat"])),
                            last_updated_at: @ts
                        })
                    } IN @@col
            """
            batch_payload = [
                {
                    "norad_id": r["norad_id"],
                    "intl_designator": r["intl_designator"],
                    "canonical_object_type": r["canonical_object_type"],
                    "launch_date": r["launch_date"],
                    "gcat_data": r["gcat_data"],
                }
                for r in batch
            ]
            db.aql.execute(aql, bind_vars={
                "@col": col_name,
                "batch": batch_payload,
                "ts": timestamp,
            })
            updated += len(batch)
            if (i + 1) % 10 == 0:
                print(f"  Enriched {updated:,} / {len(update_keys):,}...")

        print(f"  ✓ Enriched {updated:,} existing records")

    # ── Summary ──────────────────────────────────────────────────────────────
    total = collection.count()
    print(f"\n✓ Import complete!")
    print(f"  New records inserted : {inserted:,}")
    print(f"  Existing records enriched: {updated:,}")
    print(f"  Skipped (before cutoff) : {skipped_old:,}")
    print(f"  Skipped (invalid)       : {skipped_invalid:,}")
    print(f"  Total satellites in DB  : {total:,}")
    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Bulk GCAT import into ArangoDB")
    parser.add_argument("--file", dest="file_flag", default=None, help="Path to gcat_satcat.tsv (alternative to positional arg)")
    parser.add_argument("tsv_positional", nargs="?", default=None, help="Path to gcat_satcat.tsv")
    parser.add_argument("cutoff_positional", nargs="?", default=None, help="Cutoff date (YYYY-MM-DD)")
    parser.add_argument("--cutoff-date", dest="cutoff_flag", default=None)
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    tsv_path    = args.file_flag or args.tsv_positional or "gcat_satcat.tsv"
    cutoff_date = args.cutoff_flag or args.cutoff_positional or "1957-01-01"
    dry_run     = args.dry_run

    success = import_gcat_bulk(tsv_path, cutoff_date, dry_run)
    sys.exit(0 if success else 1)
