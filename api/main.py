from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager
import os
import threading

from database import connect_mongodb, disconnect_mongodb
import mqtt_scheduler

from api.routers import satellites, metadata, graphs, documents, tle, mqtt, admin, observations, auth, agent, docs, ephemeris, kestrel, objects, provenance, insurance, tle_history, customer_tasks, analytics, public_api
from api.middleware.auth import AuthMiddleware
from api.services import index_service, agent_service, aql_agent_service, kestrel_agent_service
from api.services.tle_service import warm_tle_cache

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not connect_mongodb():
        raise RuntimeError("Failed to connect to ArangoDB. ArangoDB is required.")
    
    is_serverless = os.getenv("VERCEL", "0") == "1"
    
    if not is_serverless:
        mqtt_scheduler.initialize_scheduler()
        mqtt_scheduler.load_and_schedule_all_configs()

    index_service.build_index()
    agent_service.initialize_agent()
    aql_agent_service.initialize_aql_agent()
    kestrel_agent_service.initialize_kestrel_agent()
    threading.Thread(target=warm_tle_cache, daemon=True, name="tle-cache-warmup").start()
    
    yield
    
    if not is_serverless:
        mqtt_scheduler.shutdown_scheduler()
    disconnect_mongodb()


_OPENAPI_TAGS = [
    {
        "name": "auth",
        "description": "Authentication endpoints. Obtain and revoke session tokens.",
    },
    {
        "name": "satellites",
        "description": "Search and retrieve satellite records with canonical orbital data and source provenance.",
    },
    {
        "name": "objects",
        "description": "Space-object lookup by NORAD ID, COSPAR/international designator, or alias.",
    },
    {
        "name": "metadata",
        "description": "Enumerate filter values (countries, statuses, orbital bands, object types, etc.).",
    },
    {
        "name": "tle",
        "description": "Two-Line Element (TLE) retrieval, persistence, SGP4 orbit propagation, and rate-limit-safe historical TLE archive.",
    },
    {
        "name": "ephemeris",
        "description": "High-fidelity ephemeris generation, storage, and retrieval (SGP4 and GMAT).",
    },
    {
        "name": "graphs",
        "description": "Graph analytics: shortest paths, centrality, collision clusters, constellation networks, observation graphs, and temporal snapshots.",
    },
    {
        "name": "observations",
        "description": "Ingest, query, and export satellite observation records.",
    },
    {
        "name": "provenance",
        "description": "Provenance graph: data-source lineage, confidence scores, and DISCOS-derived object genealogy.",
    },
    {
        "name": "kestrel",
        "description": "Rendezvous and proximity-operations (RPO) scenario planning powered by GMAT maneuver execution.",
    },
    {
        "name": "agent",
        "description": "LLM-powered assistants: RAG Q&A over project docs, natural-language AQL query generation, and Kestrel mission advisor.",
    },
    {
        "name": "mqtt",
        "description": "Manage MQTT broker configurations and scheduled satellite telemetry publishing.",
    },
    {
        "name": "documents",
        "description": "Resolve and parse UNOOSA registration document links and PDF metadata.",
    },
    {
        "name": "insurance",
        "description": "Insurance overlay: book dashboard, insured asset detail, loss events, witness chain, evidence verification, coverage, and constellation status.",
    },
    {
        "name": "customer_tasks",
        "description": "Customer Tasks overlay: contracted observation tasks, lifecycle management, SLA alerts, and overlay queries against existing observations.",
    },
    {
        "name": "analytics",
        "description": "ML-powered RSO analytics: health scoring, anomaly detection, maneuver detection, re-entry estimation, similarity search, and precomputed batch summaries.",
    },
    {
        "name": "admin",
        "description": "Administrative operations: data import scripts, DISCOS enrichment, database backups, and GMAT smoke tests.",
    },
    {
        "name": "docs",
        "description": "Human-readable HTML documentation pages served from project Markdown files.",
    },
]

app = FastAPI(
    lifespan=lifespan,
    title="Talon API",
    description=(
        "REST API for the Talon space-object registry and analytics platform. "
        "Provides satellite search, orbital propagation, graph analytics, observation ingestion, "
        "provenance tracking, rendezvous planning, and AI-assisted query capabilities.\n\n"
        "**Authentication**: Most endpoints require a Bearer token obtained via `POST /v2/auth/login`. "
        "Pass the token in the `Authorization: Bearer <token>` header."
    ),
    version="2.0.0",
    openapi_tags=_OPENAPI_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthMiddleware)

app.include_router(auth.router)
app.include_router(satellites.router)
app.include_router(metadata.router)
app.include_router(graphs.router)
app.include_router(documents.router)
app.include_router(tle.router)
app.include_router(mqtt.router)
app.include_router(mqtt.cron_router)
app.include_router(admin.router)
app.include_router(observations.router)
app.include_router(agent.router)
app.include_router(docs.router)
app.include_router(ephemeris.router)
app.include_router(kestrel.router)
app.include_router(objects.router)
app.include_router(provenance.router)
app.include_router(insurance.router)
app.include_router(customer_tasks.router)
app.include_router(tle_history.router)
app.include_router(analytics.router)
app.include_router(public_api.router)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        tags=_OPENAPI_TAGS,
        routes=app.routes,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
    }
    for path in schema.get("paths", {}).values():
        for operation in path.values():
            operation.setdefault("security", [{"BearerAuth": []}])
    schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi
