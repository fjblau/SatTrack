from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from api.services.gmat_service import run_smoke_test, is_available as gmat_is_available, check_data_files, find_egm96
import api.services.discos_service as _discos_svc
import database.demo_config as _demo_config_db
import io
import os
import re
import shutil
import subprocess
import tempfile
import uuid
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path

_BACKUPS_ROOT = Path(__file__).parent.parent.parent / "backups"

router = APIRouter(prefix="/v2/admin", tags=["admin"])

SCRIPT_CATALOGUE = [
    {
        "id": "enrich_launch_data",
        "name": "Enrich Launch Data",
        "description": "Enriches satellite documents with launch dates and country data",
        "category": "maintenance",
        "path": "scripts/maintenance/enrich_launch_data.py",
    },
    {
        "id": "promote_kaggle_orbital",
        "name": "Promote Kaggle Orbital",
        "description": "Promotes Kaggle orbital parameters to canonical satellite fields",
        "category": "maintenance",
        "path": "scripts/maintenance/promote_kaggle_orbital.py",
    },
    {
        "id": "promote_attributes",
        "name": "Promote Attributes",
        "description": "Promote attributes across satellite records",
        "category": "maintenance",
        "path": "scripts/maintenance/promote_attributes.py",
    },
    {
        "id": "promote_launch_site",
        "name": "Promote Launch Site",
        "description": "Promote launch site data to canonical fields",
        "category": "maintenance",
        "path": "scripts/maintenance/promote_launch_site.py",
    },
    {
        "id": "populate_collision_risks",
        "name": "Populate Collision Risks",
        "description": "Compute and populate collision risk edges",
        "category": "population",
        "path": "scripts/population/populate_collision_risks.py",
    },
    {
        "id": "populate_constellation_network",
        "name": "Populate Constellation Network",
        "description": "Build constellation membership graph",
        "category": "population",
        "path": "scripts/population/populate_constellation_network.py",
    },
    {
        "id": "populate_orbital_proximity",
        "name": "Populate Orbital Proximity",
        "description": "Populate orbital proximity edges",
        "category": "population",
        "path": "scripts/population/populate_orbital_proximity.py",
    },
    {
        "id": "populate_registration_network",
        "name": "Populate Registration Network",
        "description": "Build registration linkage graph",
        "category": "population",
        "path": "scripts/population/populate_registration_network.py",
    },
    {
        "id": "populate_satellite_lineage",
        "name": "Populate Satellite Lineage",
        "description": "Compute satellite lineage relationships",
        "category": "population",
        "path": "scripts/population/populate_satellite_lineage.py",
    },
    {
        "id": "enrich_registration_doc_links",
        "name": "Enrich Registration Document Links",
        "description": "Scrapes UNOOSA pages to resolve and store English document links for all registration documents",
        "category": "maintenance",
        "path": "scripts/maintenance/enrich_registration_doc_links.py",
    },
    {
        "id": "export_observations",
        "name": "Export Observations",
        "description": "Exports all observation documents, source vertices, and graph edges (satellite, source, temporal, correlation) to timestamped JSONL backup files.",
        "category": "maintenance",
        "path": "scripts/maintenance/export_observations.py",
    },
    {
        "id": "clear_observations",
        "name": "Clear Observations",
        "description": "Wipes all observation documents, source vertices, and graph edges (satellite, source, temporal, correlation) from the database. Run after exporting a backup.",
        "category": "maintenance",
        "path": "scripts/maintenance/clear_observations.py",
    },
    {
        "id": "import_kestrel_proxy_v2",
        "name": "Import Kestrel Proxy v2 Observations",
        "description": "Imports Kestrel Proxy Observational Data v2 records (source: kestrel_proxy_v2) for 11 satellites across a 180-day window. Enables observations tracking and creates graph edges. Upload the .xlsx file before running.",
        "category": "import",
        "path": "scripts/import/import_kestrel_proxy_v2.py",
        "requires_file": True,
        "file_arg": "--file",
        "accepted_extensions": [".xlsx"],
    },
    {
        "id": "populate_observation_edges",
        "name": "Populate Observation Edges",
        "description": "Rebuilds all four observation graph edge collections (satellite, source, temporal, anomaly-correlation) from the current observation documents. Run this after importing new observation data.",
        "category": "population",
        "path": "scripts/population/populate_observation_edges.py",
    },
    {
        "id": "migrate_collection_rename",
        "name": "Migrate: Rename satellites → objects",
        "description": "Renames the ArangoDB 'satellites' collection to 'objects', recreates indexes, and ensures the satellite_relationships graph points at the objects collection.",
        "category": "migration",
        "path": "scripts/migration/migrate_collection_rename.py",
        "order_hint": 1,
        "depends_on": [],
        "estimated_duration": "2-5 minutes",
        "reversibility": "irreversible (backup required)",
    },
    {
        "id": "migrate_rewrite_edge_vertex_ids",
        "name": "Migrate: Rewrite edge vertex IDs (satellites → objects)",
        "description": "Rewrites stale 'satellites/<key>' _from/_to fields in all edge collections to 'objects/<key>'. Fixes graph queries broken by the collection rename. Deletes and re-inserts affected edges atomically per document.",
        "category": "migration",
        "path": "scripts/migration/migrate_rewrite_edge_vertex_ids.py",
        "order_hint": 2,
        "depends_on": ["migrate_collection_rename"],
        "estimated_duration": "5-30 minutes",
        "reversibility": "irreversible (backup recommended)",
    },
    {
        "id": "migrate_create_new_indexes",
        "name": "Migrate: Create new indexes",
        "description": "Creates hash indexes on canonical.object_class, identifier_aliases.norad, and identifier_aliases.cospar.",
        "category": "migration",
        "path": "scripts/migration/migrate_create_new_indexes.py",
        "order_hint": 3,
        "depends_on": ["migrate_collection_rename"],
        "estimated_duration": "1-3 minutes",
        "reversibility": "reversible",
    },
    {
        "id": "migrate_classify_objects",
        "name": "Migrate: Classify objects (add object_class)",
        "description": "Adds canonical.object_class to every object document by mapping from canonical.object_type (ALL CAPS source values supported). object_type is kept as a deprecated field.",
        "category": "migration",
        "path": "scripts/migration/migrate_classify_objects.py",
        "args": ["--yes"],
        "order_hint": 4,
        "depends_on": ["migrate_collection_rename"],
        "estimated_duration": "5-15 minutes",
        "reversibility": "reversible (object_type preserved)",
    },
    {
        "id": "migrate_backfill_aliases",
        "name": "Migrate: Backfill identifier_aliases",
        "description": "Adds top-level identifier_aliases field {norad, cospar} to every object document, backfilled from canonical fields.",
        "category": "migration",
        "path": "scripts/migration/migrate_backfill_aliases.py",
        "args": ["--yes"],
        "order_hint": 5,
        "depends_on": ["migrate_collection_rename"],
        "estimated_duration": "5-15 minutes",
        "reversibility": "reversible",
    },
    {
        "id": "migrate_rebuild_aql_rag",
        "name": "Migrate: Rebuild AQL/RAG context",
        "description": "Updates _SCHEMA_CONTEXT_BASE in aql_agent_service.py to reference objects/object_class/identifier_aliases, and rebuilds the ChromaDB index for the /v2/ask assistant.",
        "category": "migration",
        "path": "scripts/migration/migrate_rebuild_aql_rag.py",
        "order_hint": 6,
        "depends_on": ["migrate_collection_rename"],
        "estimated_duration": "1-5 minutes",
        "reversibility": "reversible",
    },
    {
        "id": "migrate_verify_object_model",
        "name": "Migrate: Verify object model",
        "description": "Runs post-migration verification: checks collection exists, spot-checks object_class values, identifier_aliases presence, and index availability.",
        "category": "migration",
        "path": "scripts/migration/migrate_verify_object_model.py",
        "order_hint": 7,
        "depends_on": ["migrate_classify_objects", "migrate_backfill_aliases", "migrate_create_new_indexes"],
        "estimated_duration": "< 1 minute",
        "reversibility": "read-only",
    },
    {
        "id": "migrate_split_fragment_counts",
        "name": "Migrate: Split fragment count fields",
        "description": "Renames canonical.fragment_count → canonical.fragment_count_kessler on all fragmentation_events documents. Adds fragment_count_discos and fragment_count_estimated (null). Idempotent — safe to re-run.",
        "category": "migration",
        "path": "scripts/migration/migrate_split_fragment_counts.py",
        "args": ["--yes"],
        "order_hint": 8,
        "depends_on": ["ingest_discos_fragmentations"],
        "estimated_duration": "< 1 minute",
        "reversibility": "irreversible (backup recommended)",
    },
    {
        "id": "remove_insurance_mock_objects",
        "name": "Remove Insurance Mock Objects",
        "description": (
            "Removes stub satellite objects (INS-SAT-*) that were incorrectly inserted into the objects "
            "catalog by an earlier version of the insurance seed script. Those stubs duplicated NORAD IDs "
            "already present in the real catalog. Run this once to clean up, then re-run "
            "'Seed Insurance Demo Data' to rebind insurance data to the correct catalog objects. "
            "Supports --dry-run mode; safe to re-run."
        ),
        "category": "maintenance",
        "path": "scripts/maintenance/remove_insurance_mock_objects.py",
    },
    {
        "id": "seed_insurance_demo",
        "name": "Seed Insurance Demo Data",
        "description": (
            "Populates all insurance overlay collections (parties, policies, insured_interests, "
            "loss_events, claims, risk_scores, anomaly_predictions, shells, kestrels, kestrel_tasks, "
            "coverage_windows) and their graph edges with realistic demo data. "
            "Idempotent — safe to re-run; clears and rebuilds the insurance demo state from scratch. "
            "Requires the objects collection to exist. Run this before using the Insurance Overlay screens."
        ),
        "category": "population",
        "path": "scripts/population/seed_insurance_demo.py",
    },
    {
        "id": "ingest_discos_entities",
        "name": "Ingest DISCOS Entities",
        "description": "Ingests ESA DISCOS entity records (operators, countries) into the entities vertex collection. Run first in the DISCOS ingestion sequence.",
        "category": "population",
        "path": "scripts/population/ingest_discos_entities.py",
        "order_hint": 10,
        "depends_on": [],
        "estimated_duration": "5-15 minutes",
        "reversibility": "reversible (truncate entities collection)",
    },
    {
        "id": "ingest_discos_launch_sites",
        "name": "Ingest DISCOS Launch Sites",
        "description": "Ingests ESA DISCOS launch site records into the launch_sites vertex collection.",
        "category": "population",
        "path": "scripts/population/ingest_discos_launch_sites.py",
        "order_hint": 11,
        "depends_on": ["ingest_discos_entities"],
        "estimated_duration": "2-5 minutes",
        "reversibility": "reversible",
    },
    {
        "id": "ingest_discos_launch_vehicles",
        "name": "Ingest DISCOS Launch Vehicles",
        "description": "Ingests ESA DISCOS launch vehicle records into the launch_vehicles vertex collection.",
        "category": "population",
        "path": "scripts/population/ingest_discos_launch_vehicles.py",
        "order_hint": 12,
        "depends_on": ["ingest_discos_entities"],
        "estimated_duration": "2-5 minutes",
        "reversibility": "reversible",
    },
    {
        "id": "ingest_discos_launches",
        "name": "Ingest DISCOS Launch Events",
        "description": "Ingests ESA DISCOS launch event records into the launch_events vertex collection.",
        "category": "population",
        "path": "scripts/population/ingest_discos_launches.py",
        "order_hint": 13,
        "depends_on": ["ingest_discos_launch_sites", "ingest_discos_launch_vehicles"],
        "estimated_duration": "5-15 minutes",
        "reversibility": "reversible",
    },
    {
        "id": "ingest_discos_objects",
        "name": "Ingest DISCOS Objects (bulk sampling)",
        "description": "Bulk-ingests a sample of ESA DISCOS space object records for development and general catalog presence. Joins to existing objects via cosparId/satno; unmatched entries receive a surrogate key DISCOS-<discosId>. This script is NOT the primary mechanism for fragment ingestion — fragments are ingested lazily by ingest_discos_attributions. For comprehensive operational payload ingestion a separate active-payload-tuned script is planned for a future spec.",
        "category": "population",
        "path": "scripts/population/ingest_discos_objects.py",
        "order_hint": 14,
        "depends_on": ["ingest_discos_launches"],
        "estimated_duration": "30-90 minutes",
        "reversibility": "reversible (DISCOS source envelope removed from object documents)",
    },
    {
        "id": "ingest_discos_fragmentations",
        "name": "Ingest DISCOS Fragmentation Events",
        "description": "Ingests ESA DISCOS fragmentation event records into the fragmentation_events vertex collection.",
        "category": "population",
        "path": "scripts/population/ingest_discos_fragmentations.py",
        "order_hint": 15,
        "depends_on": ["ingest_discos_objects"],
        "estimated_duration": "5-20 minutes",
        "reversibility": "reversible",
    },
    {
        "id": "ingest_discos_attributions",
        "name": "Ingest DISCOS Attributions",
        "description": "Self-completing fragment ingestion: for each fragmentation event, fetches full fragment object payloads from DISCOS, ensures every fragment exists in the objects collection (creating surrogate records as needed), then creates caused_by edges. Running this script for an event guarantees complete fragment provenance in the graph. ingest_discos_objects is no longer a hard prerequisite — fragments are ingested lazily here. May run for several hours on a full catalog depending on rate budget.",
        "category": "population",
        "path": "scripts/population/ingest_discos_attributions.py",
        "order_hint": 16,
        "depends_on": ["ingest_discos_fragmentations"],
        "estimated_duration": "2-8 hours",
        "reversibility": "reversible (truncate caused_by edge collection; fragment object records can be removed if created as surrogates)",
    },
    {
        "id": "promote_discos_event_types",
        "name": "Promote DISCOS Event Types",
        "description": "Promotes DISCOS event type classifications to canonical fields on fragmentation_events documents.",
        "category": "maintenance",
        "path": "scripts/maintenance/promote_discos_event_types.py",
        "order_hint": 20,
        "depends_on": ["ingest_discos_fragmentations"],
        "estimated_duration": "1-5 minutes",
        "reversibility": "reversible",
    },
    {
        "id": "promote_discos_object_attributes",
        "name": "Promote DISCOS Object Attributes",
        "description": "Promotes DISCOS-sourced attributes (mass, RCS, shape) to canonical fields on object documents.",
        "category": "maintenance",
        "path": "scripts/maintenance/promote_discos_object_attributes.py",
        "order_hint": 21,
        "depends_on": ["ingest_discos_objects"],
        "estimated_duration": "5-30 minutes",
        "reversibility": "reversible",
    },
    {
        "id": "promote_discos_object_class",
        "name": "Promote DISCOS Object Class",
        "description": "Promotes DISCOS object type classification to canonical.object_class on object documents.",
        "category": "maintenance",
        "path": "scripts/maintenance/promote_discos_object_class.py",
        "order_hint": 22,
        "depends_on": ["ingest_discos_objects"],
        "estimated_duration": "5-20 minutes",
        "reversibility": "reversible",
    },
    {
        "id": "promote_discos_launches",
        "name": "Promote DISCOS Launches",
        "description": "Creates launched_by, launched_via, and launched_from edges between objects, entities, vehicles, and sites.",
        "category": "maintenance",
        "path": "scripts/maintenance/promote_discos_launches.py",
        "order_hint": 23,
        "depends_on": ["ingest_discos_objects", "ingest_discos_launches"],
        "estimated_duration": "10-30 minutes",
        "reversibility": "reversible (truncate launched_by, launched_via, launched_from edge collections)",
    },
    {
        "id": "promote_discos_attributions",
        "name": "Promote DISCOS Attributions",
        "description": "Promotes attribution metadata and confidence scores onto fragmented_from edges.",
        "category": "maintenance",
        "path": "scripts/maintenance/promote_discos_attributions.py",
        "order_hint": 24,
        "depends_on": ["ingest_discos_attributions"],
        "estimated_duration": "5-20 minutes",
        "reversibility": "reversible",
    },
    {
        "id": "promote_discos_fragmentations",
        "name": "Promote DISCOS Fragmentations",
        "description": "Promotes fragmentation event metadata (epoch, altitude, casualty risk) to canonical fields.",
        "category": "maintenance",
        "path": "scripts/maintenance/promote_discos_fragmentations.py",
        "order_hint": 25,
        "depends_on": ["ingest_discos_fragmentations"],
        "estimated_duration": "1-5 minutes",
        "reversibility": "reversible",
    },
    {
        "id": "fix_tle_norad_mismatch",
        "name": "Fix TLE NORAD Mismatch",
        "description": "Finds objects where the stored TLE's NORAD (from line1) does not match canonical.norad_cat_id and clears the bad TLE. Safe to re-run; supports --dry-run.",
        "category": "maintenance",
        "path": "scripts/maintenance/fix_tle_norad_mismatch.py",
        "order_hint": 26,
        "depends_on": [],
        "estimated_duration": "< 1 minute",
        "reversibility": "reversible (TLE re-fetched on next page load)",
    },
    {
        "id": "promote_gcat_parent_edges",
        "name": "Promote GCAT Parent Edges",
        "description": "Promotes sources.gcat.parent to canonical.parent_gcat_id and creates fragmented_from edges so parent objects appear in the Object Provenance graph. Safe to re-run; supports --dry-run.",
        "category": "maintenance",
        "path": "scripts/maintenance/promote_gcat_parent_edges.py",
        "order_hint": 27,
        "depends_on": ["promote_gcat_attributes"],
        "estimated_duration": "1-5 minutes",
        "reversibility": "reversible",
    },
    {
        "id": "promote_debris_class",
        "name": "Promote Debris Object Class",
        "description": (
            "Promotes 'Unknown' debris objects to specific fragmentation classes "
            "('Rocket Fragmentation Debris' or 'Payload Fragmentation Debris') using two passes: "
            "(1) DISCOS source envelope — objects whose sources.discos.object_class identifies them as rocket or payload debris; "
            "(2) fragmented_from graph edges — objects whose parent object is a Rocket Body or Payload. "
            "Only touches objects still classified as 'Unknown'. Idempotent — safe to re-run."
        ),
        "category": "maintenance",
        "path": "scripts/maintenance/promote_debris_class.py",
        "args": ["--yes"],
        "order_hint": 28,
        "depends_on": ["migrate_classify_objects", "promote_discos_object_class"],
        "estimated_duration": "5-20 minutes",
        "reversibility": "reversible",
    },
    {
        "id": "verify_discos_provenance_e2e",
        "name": "Verify DISCOS Provenance E2E",
        "description": "End-to-end verification of the DISCOS provenance graph: checks collection counts, spot-checks provenance chains, validates edge integrity.",
        "category": "migration",
        "path": "scripts/verification/verify_discos_provenance_e2e.py",
        "order_hint": 30,
        "depends_on": ["promote_discos_launches", "promote_discos_attributions", "promote_discos_fragmentations"],
        "estimated_duration": "2-5 minutes",
        "reversibility": "read-only",
    },
]

_CATALOGUE_BY_ID = {s["id"]: s for s in SCRIPT_CATALOGUE}

_runs: dict[str, dict] = {}
_runs_lock = threading.Lock()

_uploaded_files: dict[str, str] = {}
_uploaded_files_lock = threading.Lock()

_BACKUP_DIR_PATTERN = re.compile(r"^BACKUP_DIR:\s*(.+)$", re.MULTILINE)


def _stream_output(run_id: str, proc: subprocess.Popen) -> None:
    for line in proc.stdout:
        with _runs_lock:
            _runs[run_id]["output"] += line
    proc.wait()
    with _runs_lock:
        status = "success" if proc.returncode == 0 else "error"
        _runs[run_id]["status"] = status
        _runs[run_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
        if status == "success":
            m = _BACKUP_DIR_PATTERN.search(_runs[run_id]["output"])
            if m:
                _runs[run_id]["backup_dir"] = m.group(1).strip()


@router.get("/gmat-status")
def gmat_status():
    gmat_home = os.environ.get("GMAT_HOME", "")
    binary_candidates = [
        os.path.join(gmat_home, "bin", "GmatConsole-R2022a"),
        os.path.join(gmat_home, "bin", "GmatConsole"),
        os.path.join(gmat_home, "bin", "GMAT-R2022a"),
        os.path.join(gmat_home, "bin", "GMAT"),
        shutil.which("GmatConsole-R2022a") or "",
        shutil.which("GMAT-R2022a") or "",
    ]
    binary_path = next((p for p in binary_candidates if p and os.path.isfile(p)), None)

    gmat_dir_exists = bool(gmat_home and os.path.isdir(gmat_home))
    bin_dir_contents: list[str] = []
    if gmat_home and os.path.isdir(os.path.join(gmat_home, "bin")):
        bin_dir_contents = os.listdir(os.path.join(gmat_home, "bin"))

    version_output = None
    if binary_path:
        try:
            result = subprocess.run(
                [binary_path, "--version"],
                capture_output=True, text=True, timeout=10
            )
            version_output = (result.stdout + result.stderr).strip()[:200]
        except Exception as exc:
            version_output = f"error: {exc}"

    missing_data_files = check_data_files()
    egm96_actual_path = find_egm96()

    smoke = None
    if binary_path and os.access(binary_path, os.X_OK):
        smoke = run_smoke_test()

    overall_status = "not_installed"
    if binary_path:
        if smoke and smoke["ok"]:
            overall_status = "ready"
        elif smoke:
            overall_status = "installed_but_broken"
        else:
            overall_status = "installed"

    return {
        "gmat_home": gmat_home or None,
        "gmat_home_exists": gmat_dir_exists,
        "bin_dir_contents": bin_dir_contents,
        "binary_found": binary_path or None,
        "binary_executable": bool(binary_path and os.access(binary_path, os.X_OK)),
        "version_output": version_output,
        "missing_data_files": missing_data_files,
        "egm96_path": egm96_actual_path,
        "smoke_test": smoke,
        "status": overall_status,
    }


@router.get("/discos-status")
def discos_status():
    token_configured = bool(_discos_svc.config.external.DISCOS_API_TOKEN)
    base_url = _discos_svc.config.external.DISCOS_BASE_URL

    check_result = None
    if token_configured:
        check_result = _discos_svc.health_check()

    if not token_configured:
        overall_status = "not_configured"
    elif check_result and check_result.get("status") == "ready":
        overall_status = "ready"
    else:
        overall_status = "error"

    return {
        "token_configured": token_configured,
        "base_url": base_url,
        "health_check": check_result,
        "status": overall_status,
    }


@router.get("/demo-config")
def get_demo_config():
    config = _demo_config_db.get_demo_config()
    return {"config": config}


class DemoConfigBody(BaseModel):
    config: dict


@router.put("/demo-config")
def save_demo_config(body: DemoConfigBody):
    ok = _demo_config_db.save_demo_config(body.config)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save demo config")
    return {"ok": True}


@router.get("/scripts")
def list_scripts():
    return {
        "scripts": [
            {
                "id": s["id"],
                "name": s["name"],
                "description": s["description"],
                "category": s["category"],
                "requires_file": s.get("requires_file", False),
                "accepted_extensions": s.get("accepted_extensions", []),
                "order_hint": s.get("order_hint"),
                "depends_on": s.get("depends_on", []),
                "estimated_duration": s.get("estimated_duration"),
                "reversibility": s.get("reversibility"),
            }
            for s in SCRIPT_CATALOGUE
        ]
    }


@router.post("/scripts/{script_id}/upload")
async def upload_script_file(script_id: str, file: UploadFile = File(...)):
    script = _CATALOGUE_BY_ID.get(script_id)
    if not script:
        raise HTTPException(status_code=404, detail=f"Script '{script_id}' not found")
    if not script.get("requires_file"):
        raise HTTPException(status_code=400, detail=f"Script '{script_id}' does not accept file uploads")

    accepted = script.get("accepted_extensions", [])
    if accepted:
        _, ext = os.path.splitext(file.filename or "")
        if ext.lower() not in accepted:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{ext}'. Accepted: {', '.join(accepted)}"
            )

    suffix = os.path.splitext(file.filename or "upload")[1] or ".bin"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        contents = await file.read()
        tmp.write(contents)
        tmp.flush()
    finally:
        tmp.close()

    with _uploaded_files_lock:
        _uploaded_files[script_id] = tmp.name

    return {"script_id": script_id, "filename": file.filename, "size": len(contents)}


@router.post("/scripts/{script_id}/run")
def run_script(script_id: str):
    script = _CATALOGUE_BY_ID.get(script_id)
    if not script:
        raise HTTPException(status_code=404, detail=f"Script '{script_id}' not found")

    cmd = ["python", script["path"]] + script.get("args", [])

    if script.get("requires_file"):
        with _uploaded_files_lock:
            uploaded_path = _uploaded_files.get(script_id)
        if not uploaded_path or not os.path.isfile(uploaded_path):
            raise HTTPException(
                status_code=400,
                detail="This script requires a file to be uploaded first. Use the upload button."
            )
        file_arg = script.get("file_arg", "--file")
        cmd += [file_arg, uploaded_path]

    run_id = str(uuid.uuid4())
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    with _runs_lock:
        _runs[run_id] = {
            "run_id": run_id,
            "script_id": script_id,
            "status": "running",
            "output": "",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
        }

    t = threading.Thread(target=_stream_output, args=(run_id, proc), daemon=True)
    t.start()

    return {"run_id": run_id}


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    with _runs_lock:
        run = _runs.get(run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        return {
            "run_id": run["run_id"],
            "script_id": run["script_id"],
            "status": run["status"],
            "output": run["output"],
            "started_at": run["started_at"],
            "finished_at": run["finished_at"],
            "backup_dir": run.get("backup_dir"),
        }


@router.get("/runs/{run_id}/download")
def download_run_backup(run_id: str):
    with _runs_lock:
        run = _runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    backup_dir = run.get("backup_dir")
    if not backup_dir or not os.path.isdir(backup_dir):
        raise HTTPException(status_code=404, detail="No backup directory found for this run")

    dir_name = os.path.basename(backup_dir.rstrip("/"))
    zip_filename = f"{dir_name}.zip"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(backup_dir):
            fpath = os.path.join(backup_dir, fname)
            if os.path.isfile(fpath):
                zf.write(fpath, arcname=fname)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )


@router.get("/backups")
def list_backups():
    if not _BACKUPS_ROOT.is_dir():
        return {"backups": []}
    entries = []
    for d in sorted(_BACKUPS_ROOT.iterdir(), reverse=True):
        if d.is_dir():
            try:
                meta_file = d / "metadata.json"
                meta = None
                if meta_file.exists():
                    import json as _json
                    meta = _json.loads(meta_file.read_text())
                entries.append({
                    "name": d.name,
                    "path": str(d),
                    "total_documents": meta.get("total_documents") if meta else None,
                    "exported_at": meta.get("exported_at") if meta else None,
                    "collections": meta.get("collections") if meta else None,
                })
            except Exception:
                entries.append({"name": d.name, "path": str(d)})
    return {"backups": entries}


@router.get("/backups/{dir_name}/download")
def download_backup_by_name(dir_name: str):
    if ".." in dir_name or "/" in dir_name or "\\" in dir_name:
        raise HTTPException(status_code=400, detail="Invalid backup name")
    backup_dir = _BACKUPS_ROOT / dir_name
    if not backup_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Backup '{dir_name}' not found on server")

    zip_filename = f"{dir_name}.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fpath in backup_dir.iterdir():
            if fpath.is_file():
                zf.write(fpath, arcname=fpath.name)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )


class MergeObjectsRequest(BaseModel):
    primary_key: str
    secondary_key: str
    operator: str = "admin"
    reason: str = ""
    dry_run: bool = False


@router.post("/merge-objects")
def merge_objects_endpoint(body: MergeObjectsRequest):
    """
    Merge a secondary object document into a primary.
    All edges referencing the secondary are rewritten to the primary.
    The secondary document is retired (marked as merged) but not deleted.
    Requires operator identity for audit trail.
    """
    from database.merge_operations import merge_objects
    try:
        audit = merge_objects(
            primary_key=body.primary_key,
            secondary_key=body.secondary_key,
            operator=body.operator,
            reason=body.reason,
            dry_run=body.dry_run,
        )
        return audit
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Merge failed: {exc}")
