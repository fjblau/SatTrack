import os
from typing import List, Literal

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class DatabaseConfig:
    """ArangoDB database configuration"""
    HOST: str = os.getenv("ARANGO_HOST", "http://localhost:8529")
    USER: str = os.getenv("ARANGO_USER", "root")
    PASSWORD: str = os.getenv("ARANGO_PASSWORD", "kessler_dev_password")
    DB_NAME: str = "kessler"
    
    COLLECTION_OBJECTS: str = "objects"
    COLLECTION_SATELLITES: str = "objects"
    COLLECTION_REG_DOCS: str = "registration_documents"
    
    COLLECTION_OBSERVATIONS: str = "observations"
    COLLECTION_OBSERVATION_SOURCES: str = "observation_sources"

    GRAPH_NAME: str = "satellite_relationships"
    EDGE_COLLECTION_CONSTELLATION: str = "constellation_membership"
    EDGE_COLLECTION_REGISTRATION: str = "registration_links"
    EDGE_COLLECTION_PROXIMITY: str = "orbital_proximity"

    OBSERVATION_GRAPH_NAME: str = "observation_relationships"
    EDGE_COLLECTION_OBS_SATELLITE: str = "observation_satellite_edges"
    EDGE_COLLECTION_OBS_SOURCE: str = "observation_source_edges"
    EDGE_COLLECTION_OBS_CORRELATION: str = "observation_correlation_edges"
    EDGE_COLLECTION_OBS_TEMPORAL: str = "observation_temporal_edges"


class CacheConfig:
    """Caching configuration"""
    TLE_CACHE_TTL: int = int(os.getenv("TLE_CACHE_TTL", "3600"))
    DOCUMENT_CACHE_TTL: int = int(os.getenv("DOCUMENT_CACHE_TTL", "3600"))
    MAX_CACHE_SIZE: int = int(os.getenv("MAX_CACHE_SIZE", "1000"))
    ENABLE_CACHE_STATS: bool = os.getenv("ENABLE_CACHE_STATS", "true").lower() == "true"


class APIConfig:
    """API server configuration"""
    HOST: str = os.getenv("API_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("API_PORT", "8000"))
    
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    
    IS_SERVERLESS: bool = os.getenv("VERCEL", "0") == "1"
    
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


class ExternalServicesConfig:
    """External service URLs"""
    CELESTRAK_BASE_URL: str = "https://celestrak.org/NORAD/elements"
    CELESTRAK_TLE_FILES: List[str] = [
        "stations.txt",
        "resource.txt",
        "sarsat.txt",
        "dmc.txt",
        "weather.txt",
        "geo.txt",
        "iss.txt",
    ]
    
    UN_DOCS_BASE_URL: str = "https://documents.un.org"
    
    SPACETRACK_BASE_URL: str = "https://www.space-track.org"
    SPACETRACK_USERNAME: str = os.getenv("SPACETRACK_USERNAME") or os.getenv("SPACE_TRACK_USER", "")
    SPACETRACK_PASSWORD: str = os.getenv("SPACETRACK_PASSWORD") or os.getenv("SPACE_TRACK_PASS", "")
    
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "5"))

    DISCOS_BASE_URL: str = os.getenv("DISCOS_BASE_URL", "https://discosweb.esoc.esa.int/api")
    DISCOS_API_TOKEN: str = os.getenv("DISCOS_API_TOKEN", "")
    DISCOS_CACHE_TTL: int = int(os.getenv("DISCOS_CACHE_TTL", "86400"))
    DISCOS_REQUEST_TIMEOUT: int = int(os.getenv("DISCOS_REQUEST_TIMEOUT", "30"))


class OrbitalConstants:
    """Physical constants for orbital calculations"""
    GM: float = 398600.4418
    
    # WGS84 ellipsoid model constants (recommended for accurate geodetic calculations)
    WGS84_EQUATORIAL_RADIUS_KM: float = 6378.137
    WGS84_POLAR_RADIUS_KM: float = 6356.752
    WGS84_FLATTENING: float = 1.0 / 298.257223563
    
    # Mean Earth radius (deprecated - use WGS84 constants for geodetic calculations)
    # Kept for backward compatibility with orbital parameter calculations (apogee/perigee)
    EARTH_RADIUS_KM: float = 6371.0


class AuthConfig:
    """Authentication configuration"""

    def valid_users(self) -> dict[str, str]:
        username = os.getenv("APP_USERNAME", "admin")
        password = os.getenv("APP_PASSWORD", "")
        shantanu_username = os.getenv("SHANTANU_USERNAME", "shantanu")
        shantanu_password = os.getenv("SHANTANU_PASSWORD", "")

        import logging
        if not password:
            logging.getLogger(__name__).warning(
                "APP_PASSWORD is not set. Authentication will reject all non-demo login attempts."
            )

        users = {}
        if username and password:
            users[username] = password
        if shantanu_username and shantanu_password:
            users[shantanu_username] = shantanu_password
        return users


class AgentConfig:
    """LangGraph agent configuration"""
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    MODEL: str = os.getenv("AGENT_MODEL", "gpt-4o-mini")
    VECTOR_STORE_PATH: str = os.getenv("AGENT_VECTOR_STORE_PATH", ".chroma")
    EMBEDDING_MODEL: str = os.getenv("AGENT_EMBEDDING_MODEL", "text-embedding-3-small")
    RAG_CHUNK_SIZE: int = int(os.getenv("AGENT_RAG_CHUNK_SIZE", "1000"))
    RAG_CHUNK_OVERLAP: int = int(os.getenv("AGENT_RAG_CHUNK_OVERLAP", "200"))
    RAG_TOP_K: int = int(os.getenv("AGENT_RAG_TOP_K", "5"))
    INDEX_SOURCES: List[str] = [
        "ARCHITECTURE.md",
        "DEVELOPER_GUIDE.md",
        "API_DOCUMENTATION.md",
        "README.md",
        "docs/GRAPH_RELATIONSHIPS.md",
        "docs/LANGGRAPH_AGENT_ARCHITECTURE.md",
        "docs/MULTI_SOURCE_DATA_ARCHITECTURE.md",
        "docs/DATA_IMPORT_COMMANDS.md",
        "docs/CELESTRAK_IMPORT.md",
        "docs/OBSERVATIONS_IMPORT_API.md",
    ]

    VERSION: str = os.getenv("AQL_AGENT_VERSION", "v2")
    LOG_PATH: str = os.getenv("AQL_AGENT_LOG_PATH", "/var/log/talon/aql_agent.jsonl")
    LOG_TO_FILE: bool = os.getenv("AQL_AGENT_LOG_TO_FILE", "true").lower() == "true"
    LOG_TO_STDOUT: bool = os.getenv("AQL_AGENT_LOG_TO_STDOUT", "true").lower() == "true"
    MAX_AGENT_ITERATIONS: int = int(os.getenv("AQL_AGENT_MAX_ITERATIONS", "8"))
    MAX_EXECUTION_RETRIES: int = int(os.getenv("AQL_AGENT_MAX_EXEC_RETRIES", "2"))
    DEFAULT_MAX_RUNTIME_S: int = int(os.getenv("AQL_AGENT_DEFAULT_RUNTIME_S", "15"))
    GRAPH_MAX_RUNTIME_S: int = int(os.getenv("AQL_AGENT_GRAPH_RUNTIME_S", "30"))
    SCHEMA_CACHE_TTL_S: int = int(os.getenv("AQL_AGENT_SCHEMA_CACHE_TTL_S", "300"))
    DESCRIBE_INCLUDE_INDEXES: bool = os.getenv("AQL_AGENT_DESCRIBE_INCLUDE_INDEXES", "false").lower() == "true"
    RESULT_REFLECTION_ENABLED: bool = os.getenv("AQL_AGENT_RESULT_REFLECTION_ENABLED", "true").lower() == "true"
    EMPTY_RESULT_REPAIR_ENABLED: bool = os.getenv("AQL_AGENT_EMPTY_RESULT_REPAIR_ENABLED", "true").lower() == "true"
    HEURISTICS_PATH: str = os.getenv("AQL_AGENT_HEURISTICS_PATH", "aql_agent/heuristics.yaml")
    HISTORY_ENABLED: bool = os.getenv("AQL_AGENT_HISTORY_ENABLED", "true").lower() == "true"
    HISTORY_RETAIN_COUNT: int = int(os.getenv("AQL_AGENT_HISTORY_RETAIN_COUNT", "200"))
    HISTORY_RETAIN_DAYS: int = int(os.getenv("AQL_AGENT_HISTORY_RETAIN_DAYS", "30"))


class Config:
    """Main configuration class"""
    database = DatabaseConfig()
    cache = CacheConfig()
    api = APIConfig()
    external = ExternalServicesConfig()
    orbital = OrbitalConstants()
    auth = AuthConfig()
    agent = AgentConfig()


config = Config()
