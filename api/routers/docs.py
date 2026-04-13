import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

try:
    import markdown as md_lib
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

router = APIRouter(prefix="/v2/docs", tags=["docs"])


def _find_root() -> Path:
    here = Path(__file__).resolve().parent
    candidates = [
        Path(os.getcwd()),
        here,
        here.parent,
        here.parent.parent,
        here.parent.parent.parent,
        Path("/app"),
        Path("/var/task"),
    ]
    for candidate in candidates:
        if (candidate / "API_DOCUMENTATION.md").exists():
            return candidate
    return Path(os.getcwd())


_ROOT = _find_root()

_DOCS = {
    "api": {
        "title": "API Documentation",
        "file": "API_DOCUMENTATION.md",
        "description": "Complete REST API reference for all Kessler endpoints.",
    },
    "architecture": {
        "title": "Architecture",
        "file": "ARCHITECTURE.md",
        "description": "System architecture overview, module dependencies, and data flow.",
    },
    "deployment-vercel": {
        "title": "Vercel Deployment",
        "file": "README.vercel.md",
        "description": "Step-by-step guide to deploying Kessler on Vercel.",
    },
    "deployment-fly": {
        "title": "Fly.io / ArangoDB Setup",
        "file": "fly-arangodb-setup.md",
        "description": "Guide to deploying ArangoDB on Fly.io.",
    },
}

_CSS = """
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif;
  font-size: 15px;
  line-height: 1.7;
  color: #212529;
  max-width: 960px;
  margin: 0 auto;
  padding: 2rem 1.5rem 4rem;
  background: #fff;
}
h1 { font-size: 2rem; color: #1a1a2e; border-bottom: 2px solid #3498db; padding-bottom: 0.4rem; margin-top: 0; }
h2 { font-size: 1.45rem; color: #1a1a2e; border-bottom: 1px solid #dee2e6; padding-bottom: 0.25rem; margin-top: 2.5rem; }
h3 { font-size: 1.15rem; color: #2c3e50; margin-top: 2rem; }
h4 { font-size: 1rem; color: #495057; margin-top: 1.5rem; }
a { color: #3498db; text-decoration: none; }
a:hover { text-decoration: underline; }
code {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 0.875em;
  background: #f1f3f5;
  padding: 0.15em 0.4em;
  border-radius: 4px;
  color: #c0392b;
}
pre {
  background: #1e1e2e;
  color: #cdd6f4;
  padding: 1.25rem 1.5rem;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 0.85rem;
  line-height: 1.55;
  margin: 1rem 0;
}
pre code {
  background: none;
  color: inherit;
  padding: 0;
  border-radius: 0;
  font-size: inherit;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1.25rem 0;
  font-size: 0.9rem;
}
th {
  background: #f1f3f5;
  border: 1px solid #dee2e6;
  padding: 0.6rem 0.85rem;
  text-align: left;
  font-weight: 600;
  color: #495057;
}
td {
  border: 1px solid #dee2e6;
  padding: 0.55rem 0.85rem;
  vertical-align: top;
}
tr:nth-child(even) td { background: #f8f9fa; }
blockquote {
  border-left: 4px solid #3498db;
  margin: 1rem 0;
  padding: 0.5rem 1rem;
  background: #f0f7ff;
  color: #2c3e50;
  border-radius: 0 6px 6px 0;
}
hr { border: none; border-top: 1px solid #dee2e6; margin: 2rem 0; }
ul, ol { padding-left: 1.5rem; }
li { margin: 0.25rem 0; }
.back-link {
  display: inline-block;
  margin-bottom: 1.5rem;
  font-size: 0.85rem;
  color: #6c757d;
}
.back-link:hover { color: #3498db; }
.vendor-links {
  background: #f0f7ff;
  border: 1px solid #90caf9;
  border-radius: 8px;
  padding: 1rem 1.25rem;
  margin: 2rem 0;
}
.vendor-links h4 { margin-top: 0; color: #1565c0; }
.vendor-links ul { margin: 0; }
"""

_VENDOR_LINKS = {
    "api": [
        ("FastAPI Documentation", "https://fastapi.tiangolo.com/"),
        ("ArangoDB AQL Reference", "https://www.arangodb.com/docs/stable/aql/"),
        ("CelesTrak TLE Data", "https://celestrak.org/SOCRATES/"),
        ("UNOOSA Online Index", "https://www.unoosa.org/oosa/en/spaceobjectregister/index.html"),
    ],
    "architecture": [
        ("ArangoDB Documentation", "https://www.arangodb.com/docs/stable/"),
        ("FastAPI Documentation", "https://fastapi.tiangolo.com/"),
        ("LangGraph Documentation", "https://langchain-ai.github.io/langgraph/"),
        ("ChromaDB Documentation", "https://docs.trychroma.com/"),
        ("CelesTrak", "https://celestrak.org/"),
        ("Space-Track.org", "https://www.space-track.org/"),
    ],
    "deployment-vercel": [
        ("Vercel Documentation", "https://vercel.com/docs"),
        ("ArangoDB Cloud (ArangoGraph)", "https://cloud.arangodb.com/"),
        ("Vercel Cron Jobs", "https://vercel.com/docs/cron-jobs"),
    ],
    "deployment-fly": [
        ("Fly.io Documentation", "https://fly.io/docs/"),
        ("ArangoDB Docker Hub", "https://hub.docker.com/_/arangodb"),
        ("flyctl CLI Reference", "https://fly.io/docs/flyctl/"),
    ],
}


def _build_html(name: str, title: str, body_html: str) -> str:
    vendor = _VENDOR_LINKS.get(name, [])
    vendor_section = ""
    if vendor:
        items = "".join(f'<li><a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a></li>' for label, url in vendor)
        vendor_section = f'<div class="vendor-links"><h4>Official Vendor Documentation</h4><ul>{items}</ul></div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Kessler</title>
  <style>{_CSS}</style>
</head>
<body>
  <a class="back-link" href="javascript:history.back()">← Back</a>
  {vendor_section}
  {body_html}
</body>
</html>"""


def _md_to_html(text: str) -> str:
    if MARKDOWN_AVAILABLE:
        return md_lib.markdown(
            text,
            extensions=["fenced_code", "tables", "toc", "nl2br", "codehilite"],
            extension_configs={
                "codehilite": {"noclasses": True, "guess_lang": False},
            },
        )
    escaped = (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )
    return f"<pre>{escaped}</pre>"


@router.get("", response_class=HTMLResponse, include_in_schema=False)
def list_docs():
    items = "".join(
        f'<li><a href="/v2/docs/{name}">{meta["title"]}</a> — {meta["description"]}</li>'
        for name, meta in _DOCS.items()
    )
    body = f"<h1>Kessler Documentation</h1><ul>{items}</ul>"
    return HTMLResponse(_build_html("index", "Documentation", body))


@router.get("/{name}", response_class=HTMLResponse, include_in_schema=False)
def get_doc(name: str):
    meta = _DOCS.get(name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Document '{name}' not found.")
    path = _ROOT / meta["file"]
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {meta['file']}")
    raw = path.read_text(encoding="utf-8")
    body_html = _md_to_html(raw)
    return HTMLResponse(_build_html(name, meta["title"], body_html))
