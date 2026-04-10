import os
import logging
from pathlib import Path
from typing import Optional

from config import config

logger = logging.getLogger(__name__)

_retriever = None


def _load_documents() -> list:
    from langchain_core.documents import Document

    docs = []
    repo_root = Path(__file__).resolve().parents[2]

    for rel_path in config.agent.INDEX_SOURCES:
        full_path = repo_root / rel_path
        if not full_path.exists():
            logger.warning(f"Index source not found, skipping: {full_path}")
            continue
        try:
            text = full_path.read_text(encoding="utf-8")
            docs.append(Document(page_content=text, metadata={"source": rel_path}))
            logger.debug(f"Loaded index source: {rel_path}")
        except Exception as exc:
            logger.warning(f"Failed to read {rel_path}: {exc}")

    return docs


def _split_documents(docs: list) -> list:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.agent.RAG_CHUNK_SIZE,
        chunk_overlap=config.agent.RAG_CHUNK_OVERLAP,
    )
    return splitter.split_documents(docs)


def build_index() -> None:
    global _retriever

    if not config.agent.OPENAI_API_KEY:
        logger.warning(
            "OPENAI_API_KEY is not set — /v2/ask endpoint will be unavailable."
        )
        return

    try:
        from langchain_openai import OpenAIEmbeddings
        from langchain_chroma import Chroma

        embeddings = OpenAIEmbeddings(
            model=config.agent.EMBEDDING_MODEL,
            api_key=config.agent.OPENAI_API_KEY,
        )

        persist_path = config.agent.VECTOR_STORE_PATH

        if os.path.exists(persist_path) and os.listdir(persist_path):
            logger.info(f"Loading existing vector store from {persist_path}")
            store = Chroma(
                persist_directory=persist_path,
                embedding_function=embeddings,
                collection_name="kessler_docs",
            )
        else:
            logger.info("Building vector store index from source documents...")
            raw_docs = _load_documents()
            if not raw_docs:
                logger.warning("No documents found to index.")
                return
            chunks = _split_documents(raw_docs)
            store = Chroma.from_documents(
                documents=chunks,
                embedding=embeddings,
                persist_directory=persist_path,
                collection_name="kessler_docs",
            )
            logger.info(f"Indexed {len(chunks)} chunks into vector store at {persist_path}")

        _retriever = store.as_retriever(search_kwargs={"k": config.agent.RAG_TOP_K})
        logger.info("RAG retriever is ready.")

    except Exception as exc:
        logger.error(f"Failed to build vector store index: {exc}", exc_info=True)


def get_retriever():
    return _retriever


def is_ready() -> bool:
    return _retriever is not None
