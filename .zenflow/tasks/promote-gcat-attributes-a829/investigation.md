# Investigation: Promote GCAT Attributes to Canonical Fields

## Bug Summary

Many recently imported GCAT satellite records (those created by `scripts/import/import_gcat_bulk.py`) have their data stored only in `sources.gcat.*` but are missing key canonical fields that other features depend on. This breaks search/filter functionality and other downstream features that read from `canonical.*`.

## Root Cause Analysis

The import script `import_gcat_bulk.py` creates new documents with a minimal canonical section:
```json
"canonical": {
  "name": "<satellite name>",
  "launch_date": "<YYYY-MM-DD>",
  "object_type": "<PAYLOAD|DEBRIS|ROCKET BODY>",
  "updated_at": "<timestamp>"
}
```

The `update_canonical()` function in `database/transformations.py` explicitly excludes `gcat` from the `approved_sources` list (`["unoosa", "spacetrack", "celestrak", "tleapi", "kaggle"]`), so gcat data is never automatically promoted. This was intentional for conservative data governance, but leaves gcat-only records with sparse canonical data.

## Affected Components

- **10 gcat-only documents** (confirmed in DB) — these have `metadata.sources_available == ["gcat"]` and are missing all canonical fields except `name`, `launch_date`, and `object_type`
- **1,555 documents with gcat source** that are missing some canonical attributes  
- All features that filter/sort on canonical fields: `search_satellites()`, orbital proximity computation, constellation network, collision risk detection

## The Reference: Austrian PRETTY Satellite (`2023-155H`)

A well-populated canonical record looks like:
```json
"canonical": {
  "name": "PRETTY",
  "norad_cat_id": 58023,
  "international_designator": "2023-155H",
  "country_of_origin": "Austria",
  "country": "Austria",
  "date_of_launch": "2023-10-09",
  "launch_date": "2023-10-09",
  "object_type": "PAYLOAD",
  "status": "in orbit",
  "orbital_band": "LEO-Polar",
  "congestion_risk": "HIGH",
  "orbit": {
    "apogee_km": 507,
    "perigee_km": 505,
    "inclination_degrees": 97.59,
    "period_minutes": 94.75
  }
}
```

## Available GCAT Data

GCAT-only documents have these fields in `sources.gcat.*`:
| GCAT field | Available | Target canonical field |
|---|---|---|
| `norad_cat_id` | 7/10 docs | `canonical.norad_cat_id` |
| `international_designator` | 10/10 | `canonical.international_designator` |
| `country_of_origin` | 10/10 | `canonical.country_of_origin` + `canonical.country` (normalized) |
| `status` | 10/10 | `canonical.status` (mapped) |
| `object_type` (raw GCAT code) | 10/10 | `canonical.object_type` (normalized) |
| `apogee_km` | 10/10 | `canonical.orbit.apogee_km` |
| `perigee_km` | 10/10 | `canonical.orbit.perigee_km` |
| `inclination_degrees` | 10/10 | `canonical.orbit.inclination_degrees` |
| `date_of_launch` | 10/10 | `canonical.date_of_launch` |
| `decay_date` | partial | `canonical.date_of_decay_or_change` |
| `name` / `payload_name` | 10/10 | `canonical.name` (already set, use as fallback) |

Additionally, `canonical.orbital_band` can be derived from orbit parameters + inclination.

## GCAT Status Code Mapping

Observed GCAT status values: `['AO', 'AR', 'DSO', 'GRP', 'O', 'R']`

Mapping to canonical status values (matching existing canonical values):
| GCAT | Canonical |
|---|---|
| `O` | `in orbit` |
| `AO` | `in orbit` |
| `AR` | `in orbit` |
| `R` | `decayed` |
| `DSO` | `heliocentric` |
| `GRP` | `in disposal/graveyard orbit` |

## Object Type Normalization

GCAT `object_type` field in `sources.gcat` contains raw GCAT type codes (e.g., `P      O m`, `R2--D`, `C  A`). These need re-normalization using the first character:
- First char `P` or `S` → `PAYLOAD`
- First char `D` → `DEBRIS`
- First char `C` or `R` → `ROCKET BODY`
- otherwise → `UNKNOWN`

## Orbital Band Derivation

Existing canonical orbital bands: `GEO`, `GEO-Inclined`, `HEO`, `LEO-Equatorial`, `LEO-Inclined`, `LEO-Polar`, `LEO-Retrograde`, `MEO`

Algorithm based on `orbital_service.classify_orbital_band()` + inclination:
1. If `|apogee - perigee| > 10000` → `HEO`
2. Else if average altitude >= 35786 km → `HEO`
3. Else if 35586 <= avg altitude <= 35986 → `GEO` (if inclination < 5°) or `GEO-Inclined`
4. Else if avg altitude >= 2000 → `MEO`
5. Else (LEO): classify by inclination:
   - 80° ≤ inclination ≤ 100° → `LEO-Polar`
   - inclination > 100° → `LEO-Retrograde`
   - inclination ≤ 10° → `LEO-Equatorial`
   - otherwise → `LEO-Inclined`

## Proposed Solution

Create a new script: `scripts/maintenance/promote_gcat_attributes.py`

The script will:
1. Connect to ArangoDB
2. Target documents where `metadata.sources_available` contains only `"gcat"` (or optionally all docs with `sources.gcat` and missing canonical fields)
3. For each document, promote from `sources.gcat.*` to `canonical.*` using mappings above
4. Normalize country codes using `CountryNormalizer`
5. Map GCAT status codes to canonical status values
6. Re-normalize `object_type` from raw GCAT code
7. Derive `orbital_band` from orbit parameters + inclination
8. Record each transformation in `metadata.transformations`
9. Support `--dry-run` mode (show what would be changed)
10. Support `--all` flag to also process non-gcat-only docs with missing canonical fields
11. Batch updates using AQL UPDATE for efficiency

### Script Design Pattern
Follow the pattern of `promote_kaggle_orbital.py`:
- Show count of documents to process
- Show sample of what will change
- Confirm before proceeding (unless `--yes` flag)
- Batch AQL UPDATE
- Verify after completion

## Edge Cases

- `object_type` in `sources.gcat` may be raw GCAT code (e.g., `P      O m`) → normalize
- `country_of_origin` may be ISO code (e.g., `US`, `CN`) → normalize using `CountryNormalizer`
- Some fields may be `None` → skip
- Documents with existing canonical values should not be overwritten (use `MERGE` with null checks)
- `DSO` status (Deep Space Object) maps to `heliocentric` — but orbits could be truly deep space (not heliocentric), so this is a best-effort approximation

## Implementation Notes

- File: `scripts/maintenance/promote_gcat_attributes.py`
- Use `database.connect_arangodb()` and AQL queries
- Use `database.utils.normalization.CountryNormalizer` for country normalization
- Use AQL batch UPDATE (not Python-loop-based) for performance
- Keep transformation history with `metadata.transformations` array entries
