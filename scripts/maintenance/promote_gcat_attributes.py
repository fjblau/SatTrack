#!/usr/bin/env python3
"""
Promote GCAT source attributes to canonical fields.

Many satellites imported from GCAT have rich data in sources.gcat.* but sparse
canonical sections (only name, launch_date, object_type). This script promotes
the available GCAT data to canonical fields, enabling search/filter features
and downstream graph analytics to work correctly.

Based on the Austrian PRETTY satellite (2023-155H) as the reference for a
well-populated canonical record.

USAGE:
    python promote_gcat_attributes.py [--dry-run] [--yes]

OPTIONS:
    --dry-run   Preview changes without writing to database
    --yes       Skip confirmation prompt
    -v          Verbose: print each updated document identifier
"""

import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from database import connect_arangodb
from database.utils.normalization import CountryNormalizer
import database.connection as db_conn

EARTH_RADIUS_KM = 6378.137

GCAT_STATUS_MAP = {
    "O":   "in orbit",
    "AO":  "in orbit",
    "AR":  "in orbit",
    "OX":  "in orbit",
    "ATT": "in orbit",
    "N":   "in orbit",
    "TFR": "in orbit",
    "REL": "in orbit",
    "R":   "decayed",
    "R?":  "decayed",
    "D":   "decayed",
    "DK":  "decayed",
    "C":   "decayed",
    "L":   "decayed",
    "DSO": "heliocentric",
    "DSA": "heliocentric",
    "E":   "heliocentric",
    "GRP": "in disposal/graveyard orbit",
}


def normalize_gcat_object_type(raw: str) -> str:
    if not raw:
        return "UNKNOWN"
    known = {"PAYLOAD", "DEBRIS", "ROCKET BODY", "UNKNOWN"}
    if raw.strip().upper() in known:
        return raw.strip().upper()
    first = raw.strip()[0].upper()
    if first in ("P", "S"):
        return "PAYLOAD"
    if first == "D":
        return "DEBRIS"
    if first in ("C", "R"):
        return "ROCKET BODY"
    return "UNKNOWN"


def classify_orbital_band(apogee_km, perigee_km, inclination_deg) -> str:
    if apogee_km is None or perigee_km is None:
        return None
    avg = (apogee_km + perigee_km) / 2.0
    diff = abs(apogee_km - perigee_km)

    if diff > 10000 or avg > 35986:
        return "HEO"
    if 35586 <= avg <= 35986:
        if inclination_deg is not None and abs(inclination_deg) >= 5:
            return "GEO-Inclined"
        return "GEO"
    if avg >= 2000:
        return "MEO"
    if inclination_deg is None:
        return "LEO-Inclined"
    inc = abs(inclination_deg)
    if 80 <= inc <= 100:
        return "LEO-Polar"
    if inc > 100:
        return "LEO-Retrograde"
    if inc <= 10:
        return "LEO-Equatorial"
    return "LEO-Inclined"


def run(dry_run: bool, yes: bool, verbose: bool):
    if not connect_arangodb():
        print("Failed to connect to ArangoDB")
        return False

    db = db_conn.db
    col = db_conn.COLLECTION_NAME
    ts = datetime.now(timezone.utc).isoformat()
    country_normalizer = CountryNormalizer()

    total_query = """
    RETURN COUNT(
        FOR doc IN @@col
            FILTER LENGTH(doc.metadata.sources_available) == 1
               AND doc.metadata.sources_available[0] == "gcat"
            RETURN 1
    )
    """
    total = list(db.aql.execute(total_query, bind_vars={"@col": col}))[0]
    print(f"\n=== Promote GCAT Attributes to Canonical ===")
    print(f"Found {total:,} gcat-only documents to process")

    if total == 0:
        print("Nothing to do.")
        return True

    sample_query = """
    FOR doc IN @@col
        FILTER LENGTH(doc.metadata.sources_available) == 1
           AND doc.metadata.sources_available[0] == "gcat"
        LIMIT 5
        RETURN {
            id: doc.identifier,
            current_canonical: doc.canonical,
            gcat: doc.sources.gcat
        }
    """
    samples = list(db.aql.execute(sample_query, bind_vars={"@col": col}))
    print("\nSample documents (before promotion):")
    for s in samples:
        gcat = s["gcat"] or {}
        country_raw = gcat.get("country_of_origin")
        country_norm = country_normalizer.normalize(country_raw)
        obj_type = normalize_gcat_object_type(gcat.get("object_type", ""))
        status_raw = gcat.get("status", "")
        status_mapped = GCAT_STATUS_MAP.get(status_raw)
        apogee = gcat.get("apogee_km")
        perigee = gcat.get("perigee_km")
        inc = gcat.get("inclination_degrees")
        band = classify_orbital_band(apogee, perigee, inc)
        print(f"  {s['id']}:")
        print(f"    country: {country_raw!r} → {country_norm!r}")
        print(f"    status:  {status_raw!r} → {status_mapped!r}")
        print(f"    object_type: {gcat.get('object_type')!r} → {obj_type!r}")
        print(f"    orbit: apogee={apogee}, perigee={perigee}, inc={inc} → band={band!r}")
        print(f"    norad_cat_id: {gcat.get('norad_cat_id')}, intl_des: {gcat.get('international_designator')!r}")

    if dry_run:
        print(f"\n[DRY-RUN] Would promote attributes for {total:,} documents. No changes made.")
        return True

    if not yes:
        resp = input(f"\nProceed with promoting GCAT attributes for {total:,} documents? (y/N): ").strip().lower()
        if resp not in ("y", "yes"):
            print("Cancelled.")
            return False

    print(f"\nUpdating {total:,} documents...")

    update_query = """
    FOR doc IN @@col
        FILTER LENGTH(doc.metadata.sources_available) == 1
           AND doc.metadata.sources_available[0] == "gcat"

        LET g = doc.sources.gcat

        LET raw_type = g.object_type
        LET obj_type = (
            raw_type == "PAYLOAD"      ? "PAYLOAD"      :
            raw_type == "DEBRIS"       ? "DEBRIS"       :
            raw_type == "ROCKET BODY"  ? "ROCKET BODY"  :
            raw_type == "UNKNOWN"      ? "UNKNOWN"      :
            raw_type != null ? (
                LEFT(raw_type, 1) == "P" ? "PAYLOAD"      :
                LEFT(raw_type, 1) == "S" ? "PAYLOAD"      :
                LEFT(raw_type, 1) == "D" ? "DEBRIS"       :
                LEFT(raw_type, 1) == "R" ? "ROCKET BODY"  :
                LEFT(raw_type, 1) == "C" ? "ROCKET BODY"  :
                "UNKNOWN"
            ) : null
        )

        LET status_raw = g.status
        LET status_mapped = (
            status_raw == "O"   ? "in orbit" :
            status_raw == "AO"  ? "in orbit" :
            status_raw == "AR"  ? "in orbit" :
            status_raw == "OX"  ? "in orbit" :
            status_raw == "ATT" ? "in orbit" :
            status_raw == "N"   ? "in orbit" :
            status_raw == "TFR" ? "in orbit" :
            status_raw == "REL" ? "in orbit" :
            status_raw == "R"   ? "decayed"  :
            status_raw == "R?"  ? "decayed"  :
            status_raw == "D"   ? "decayed"  :
            status_raw == "DK"  ? "decayed"  :
            status_raw == "C"   ? "decayed"  :
            status_raw == "L"   ? "decayed"  :
            status_raw == "DSO" ? "heliocentric" :
            status_raw == "DSA" ? "heliocentric" :
            status_raw == "E"   ? "heliocentric" :
            status_raw == "GRP" ? "in disposal/graveyard orbit" :
            null
        )

        LET apogee  = g.apogee_km
        LET perigee = g.perigee_km
        LET inc     = g.inclination_degrees
        LET avg_alt = (apogee != null AND perigee != null) ? (apogee + perigee) / 2.0 : null
        LET diff    = (apogee != null AND perigee != null) ? ABS(apogee - perigee)    : null

        LET band = (
            avg_alt == null ? null :
            (diff > 10000 OR avg_alt > 35986) ? "HEO" :
            (avg_alt >= 35586 AND avg_alt <= 35986) ? (
                (inc != null AND ABS(inc) >= 5) ? "GEO-Inclined" : "GEO"
            ) :
            avg_alt >= 2000 ? "MEO" :
            inc == null     ? "LEO-Inclined" :
            (ABS(inc) >= 80 AND ABS(inc) <= 100) ? "LEO-Polar"      :
            ABS(inc) > 100                        ? "LEO-Retrograde" :
            ABS(inc) <= 10                        ? "LEO-Equatorial" :
            "LEO-Inclined"
        )

        LET new_canonical = MERGE(doc.canonical, {
            norad_cat_id:             doc.canonical.norad_cat_id             != null ? doc.canonical.norad_cat_id             : g.norad_cat_id,
            international_designator: doc.canonical.international_designator != null ? doc.canonical.international_designator : g.international_designator,
            country_of_origin:        doc.canonical.country_of_origin        != null ? doc.canonical.country_of_origin        : g.country_of_origin,
            date_of_launch:           doc.canonical.date_of_launch           != null ? doc.canonical.date_of_launch           : g.date_of_launch,
            launch_date:              doc.canonical.launch_date              != null ? doc.canonical.launch_date              : g.launch_date,
            object_type:              doc.canonical.object_type              != null ? doc.canonical.object_type              : obj_type,
            status:                   doc.canonical.status                   != null ? doc.canonical.status                   : status_mapped,
            orbital_band:             doc.canonical.orbital_band             != null ? doc.canonical.orbital_band             : band,
            date_of_decay_or_change:  doc.canonical.date_of_decay_or_change  != null ? doc.canonical.date_of_decay_or_change  : g.decay_date,
            object_name:              doc.canonical.object_name              != null ? doc.canonical.object_name              : g.name,
            orbit: MERGE(doc.canonical.orbit || {}, {
                apogee_km:           (doc.canonical.orbit.apogee_km           != null) ? doc.canonical.orbit.apogee_km           : apogee,
                perigee_km:          (doc.canonical.orbit.perigee_km          != null) ? doc.canonical.orbit.perigee_km          : perigee,
                inclination_degrees: (doc.canonical.orbit.inclination_degrees != null) ? doc.canonical.orbit.inclination_degrees : inc
            }),
            updated_at: @ts
        })

        LET transformations = [
            g.norad_cat_id             != null ? { timestamp: @ts, source_field: "sources.gcat.norad_cat_id",             target_field: "canonical.norad_cat_id",             value: g.norad_cat_id,             promoted_by: "promote_gcat_attributes" } : null,
            g.international_designator != null ? { timestamp: @ts, source_field: "sources.gcat.international_designator", target_field: "canonical.international_designator", value: g.international_designator, promoted_by: "promote_gcat_attributes" } : null,
            g.country_of_origin        != null ? { timestamp: @ts, source_field: "sources.gcat.country_of_origin",        target_field: "canonical.country_of_origin",        value: g.country_of_origin,        promoted_by: "promote_gcat_attributes" } : null,
            g.date_of_launch           != null ? { timestamp: @ts, source_field: "sources.gcat.date_of_launch",           target_field: "canonical.date_of_launch",           value: g.date_of_launch,           promoted_by: "promote_gcat_attributes" } : null,
            obj_type                   != null ? { timestamp: @ts, source_field: "sources.gcat.object_type",              target_field: "canonical.object_type",              value: obj_type,                   promoted_by: "promote_gcat_attributes", reason: "Normalized from raw GCAT type code" } : null,
            status_mapped              != null ? { timestamp: @ts, source_field: "sources.gcat.status",                   target_field: "canonical.status",                   value: status_mapped,              promoted_by: "promote_gcat_attributes", reason: CONCAT("Mapped from GCAT status: ", status_raw) } : null,
            band                       != null ? { timestamp: @ts, source_field: "sources.gcat.apogee_km+perigee_km+inclination_degrees", target_field: "canonical.orbital_band", value: band, promoted_by: "promote_gcat_attributes", reason: "Derived from orbital parameters" } : null,
            apogee                     != null ? { timestamp: @ts, source_field: "sources.gcat.apogee_km",               target_field: "canonical.orbit.apogee_km",           value: apogee,                     promoted_by: "promote_gcat_attributes" } : null,
            perigee                    != null ? { timestamp: @ts, source_field: "sources.gcat.perigee_km",              target_field: "canonical.orbit.perigee_km",          value: perigee,                    promoted_by: "promote_gcat_attributes" } : null,
            inc                        != null ? { timestamp: @ts, source_field: "sources.gcat.inclination_degrees",     target_field: "canonical.orbit.inclination_degrees", value: inc,                        promoted_by: "promote_gcat_attributes" } : null,
            g.decay_date               != null ? { timestamp: @ts, source_field: "sources.gcat.decay_date",              target_field: "canonical.date_of_decay_or_change",  value: g.decay_date,               promoted_by: "promote_gcat_attributes" } : null
        ]

        UPDATE doc WITH {
            canonical: new_canonical,
            metadata: MERGE(doc.metadata, {
                transformations: APPEND(
                    doc.metadata.transformations || [],
                    transformations[* FILTER CURRENT != null]
                ),
                last_updated_at: @ts
            })
        } IN @@col

        COLLECT WITH COUNT INTO updated
        RETURN updated
    """

    cursor = db.aql.execute(
        update_query,
        bind_vars={"@col": col, "ts": ts},
        max_runtime=600,
    )
    updated = list(cursor)[0]
    print(f"✓ Promoted attributes for {updated:,} satellites")

    verify_query = """
    LET gcat_only = (
        FOR doc IN @@col
            FILTER LENGTH(doc.metadata.sources_available) == 1
               AND doc.metadata.sources_available[0] == "gcat"
            RETURN doc
    )
    RETURN {
        total: LENGTH(gcat_only),
        has_country:      LENGTH(gcat_only[* FILTER CURRENT.canonical.country_of_origin != null]),
        has_object_type:  LENGTH(gcat_only[* FILTER CURRENT.canonical.object_type != null]),
        has_status:       LENGTH(gcat_only[* FILTER CURRENT.canonical.status != null]),
        has_orbital_band: LENGTH(gcat_only[* FILTER CURRENT.canonical.orbital_band != null]),
        has_orbit:        LENGTH(gcat_only[* FILTER CURRENT.canonical.orbit.apogee_km != null])
    }
    """
    stats = list(db.aql.execute(verify_query, bind_vars={"@col": col}))[0]
    total_docs = stats["total"]
    print(f"\n✓ Verification (out of {total_docs:,} gcat-only docs):")
    print(f"  country_of_origin : {stats['has_country']:,}")
    print(f"  object_type       : {stats['has_object_type']:,}")
    print(f"  status            : {stats['has_status']:,}")
    print(f"  orbital_band      : {stats['has_orbital_band']:,}")
    print(f"  orbit.apogee_km   : {stats['has_orbit']:,}")

    return True


def main():
    parser = argparse.ArgumentParser(description="Promote GCAT source attributes to canonical fields")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing to database")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()
    success = run(dry_run=args.dry_run, yes=args.yes, verbose=args.verbose)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
