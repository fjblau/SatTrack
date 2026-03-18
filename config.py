import os
from typing import List

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
    
    COLLECTION_SATELLITES: str = "satellites"
    COLLECTION_REG_DOCS: str = "registration_documents"
    
    GRAPH_NAME: str = "satellite_relationships"
    EDGE_COLLECTION_CONSTELLATION: str = "constellation_membership"
    EDGE_COLLECTION_REGISTRATION: str = "registration_links"
    EDGE_COLLECTION_PROXIMITY: str = "orbital_proximity"


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
    SPACETRACK_USERNAME: str = os.getenv("SPACETRACK_USERNAME", "")
    SPACETRACK_PASSWORD: str = os.getenv("SPACETRACK_PASSWORD", "")
    
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "5"))


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
    USERNAME: str = os.getenv("APP_USERNAME", "admin")
    PASSWORD: str = os.getenv("APP_PASSWORD", "")

    def __init__(self):
        import logging
        if not self.PASSWORD:
            logging.getLogger(__name__).warning(
                "APP_PASSWORD is not set. Authentication will reject all login attempts."
            )


class Config:
    """Main configuration class"""
    database = DatabaseConfig()
    cache = CacheConfig()
    api = APIConfig()
    external = ExternalServicesConfig()
    orbital = OrbitalConstants()
    auth = AuthConfig()


config = Config()
