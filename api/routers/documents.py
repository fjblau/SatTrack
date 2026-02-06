from fastapi import APIRouter
from typing import Dict
import time

from api.services.document_service import fetch_english_doc_link, extract_document_metadata
from api.services.cache_service import CacheService

router = APIRouter(prefix="/api/documents", tags=["documents"])

doc_link_cache = CacheService(name="doc_links", ttl=3600, max_size=1000)
doc_metadata_cache = CacheService(name="doc_metadata", ttl=3600, max_size=500)


@router.get("/resolve")
def resolve_document_link(path: str) -> Dict:
    """
    Resolve a registry document path to the actual accessible document link.
    Handles the common issue where registry paths point to Russian pages
    with English links hidden.
    """
    if not path:
        return {"error": "No path provided", "original_path": path}
    
    cache_key = f"doc_{path}"
    
    cached_link = doc_link_cache.get(cache_key)
    if cached_link is not None:
        return {
            "original_path": path,
            "original_url": f"https://www.unoosa.org{path}",
            "english_link": cached_link,
            "found": cached_link is not None,
            "cached": True
        }
    
    english_link = fetch_english_doc_link(path)
    
    doc_link_cache.set(cache_key, english_link)
    
    return {
        "original_path": path,
        "original_url": f"https://www.unoosa.org{path}",
        "english_link": english_link,
        "found": english_link is not None,
        "cached": False
    }


@router.get("/metadata")
def get_document_metadata(url: str) -> Dict:
    """
    Extract and return metadata from a registration document PDF.
    Caches results to avoid repeated PDF processing.
    """
    if not url:
        return {"error": "No URL provided"}
    
    cache_key = url
    
    cached_result = doc_metadata_cache.get(cache_key)
    if cached_result is not None:
        cached_result['cached'] = True
        return cached_result
    
    metadata = extract_document_metadata(url)
    
    result = {
        "url": url,
        "metadata": metadata,
        "found": metadata is not None,
        "cached": False
    }
    
    doc_metadata_cache.set(cache_key, result)
    
    return result
