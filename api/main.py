from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from database import connect_mongodb, disconnect_mongodb
import mqtt_scheduler

from api.routers import satellites, metadata, graphs, documents, tle, mqtt, admin, observations, auth, agent, docs
from api.middleware.auth import AuthMiddleware
from api.services import index_service, agent_service, aql_agent_service

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
    
    yield
    
    if not is_serverless:
        mqtt_scheduler.shutdown_scheduler()
    disconnect_mongodb()


app = FastAPI(lifespan=lifespan)

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
app.include_router(admin.router)
app.include_router(observations.router)
app.include_router(agent.router)
app.include_router(docs.router)
