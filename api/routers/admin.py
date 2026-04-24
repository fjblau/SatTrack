from fastapi import APIRouter, HTTPException, UploadFile, File
from api.services.gmat_service import run_smoke_test, is_available as gmat_is_available, check_data_files, find_egm96
import os
import shutil
import subprocess
import tempfile
import uuid
import threading
from datetime import datetime, timezone

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
        "id": "export_and_clear_observations",
        "name": "Export & Clear Observations",
        "description": "Exports all observation documents, source vertices, and graph edges (satellite, source, temporal, correlation) to timestamped JSONL backup files, then wipes those collections. Run this before re-importing observation data.",
        "category": "maintenance",
        "path": "scripts/maintenance/export_and_clear_observations.py",
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
]

_CATALOGUE_BY_ID = {s["id"]: s for s in SCRIPT_CATALOGUE}

_runs: dict[str, dict] = {}
_runs_lock = threading.Lock()

_uploaded_files: dict[str, str] = {}
_uploaded_files_lock = threading.Lock()


def _stream_output(run_id: str, proc: subprocess.Popen) -> None:
    for line in proc.stdout:
        with _runs_lock:
            _runs[run_id]["output"] += line
    proc.wait()
    with _runs_lock:
        _runs[run_id]["status"] = "success" if proc.returncode == 0 else "error"
        _runs[run_id]["finished_at"] = datetime.now(timezone.utc).isoformat()


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

    cmd = ["python", script["path"]]

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
        }
