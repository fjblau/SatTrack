#!/usr/bin/env python3
"""
Migrate: Rebuild AQL agent context and ChromaDB RAG index.

1. Verifies that _SCHEMA_CONTEXT_BASE in aql_agent_service.py references
   'objects' (not 'satellites') — the code update is done in Spec 1's code
   changes, this script just validates and reports.
2. Rebuilds the ChromaDB vector index used by the /v2/ask general assistant
   by calling index_service.build_index() with a fresh (cleared) store.

USAGE:
    python migrate_rebuild_aql_rag.py
"""

import sys
import os
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def check_aql_agent_schema():
    from api.services.aql_agent_service import _SCHEMA_CONTEXT_BASE
    uses_objects = "FOR s IN objects" in _SCHEMA_CONTEXT_BASE or "objects/" in _SCHEMA_CONTEXT_BASE
    uses_satellites = "FOR s IN satellites" in _SCHEMA_CONTEXT_BASE or '"satellites/"' in _SCHEMA_CONTEXT_BASE
    print("=== AQL Agent Schema Check ===")
    print(f"  References 'objects':    {uses_objects}")
    print(f"  References 'satellites': {uses_satellites}")
    if uses_satellites:
        print("  WARNING: _SCHEMA_CONTEXT_BASE still references 'satellites'. Check code changes.")
        return False
    if uses_objects:
        print("  OK: _SCHEMA_CONTEXT_BASE references 'objects'.")
    return True


def rebuild_chromadb_index():
    from config import config
    print("\n=== Rebuilding ChromaDB RAG Index ===")

    if not config.agent.OPENAI_API_KEY:
        print("OPENAI_API_KEY not set. Skipping ChromaDB rebuild.")
        return True

    persist_path = config.agent.VECTOR_STORE_PATH
    if os.path.exists(persist_path):
        print(f"Clearing existing vector store at: {persist_path}")
        shutil.rmtree(persist_path)

    from api.services.index_service import build_index
    build_index()
    print("ChromaDB index rebuilt.")
    return True


def run():
    schema_ok = check_aql_agent_schema()
    index_ok = rebuild_chromadb_index()
    return schema_ok and index_ok


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
