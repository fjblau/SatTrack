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
        "description": "Complete REST API reference for all Talon endpoints.",
    },
    "architecture": {
        "title": "Architecture",
        "file": "ARCHITECTURE.md",
        "description": "System architecture overview, module dependencies, and data flow.",
    },
    "deployment-vercel": {
        "title": "Vercel Deployment",
        "file": "README.vercel.md",
        "description": "Step-by-step guide to deploying Talon on Vercel.",
    },
    "deployment-fly": {
        "title": "Fly.io / ArangoDB Setup",
        "file": "fly-arangodb-setup.md",
        "description": "Guide to deploying ArangoDB on Fly.io.",
    },
}

_CSS = """
*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; height: 100%; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif;
  font-size: 15px;
  line-height: 1.75;
  color: #1e2a38;
  background: #f7f9fc;
}
.doc-topbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: #fff;
  border-bottom: 1px solid #dee2e6;
  padding: 0.75rem 2.5rem;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.doc-topbar-title {
  font-size: 1rem;
  font-weight: 600;
  color: #2c3e50;
  flex: 1;
}
.back-link {
  font-size: 0.85rem;
  color: #6c757d;
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 0.3rem;
  white-space: nowrap;
}
.back-link:hover { color: #3498db; }
.doc-body {
  padding: 2.5rem 2.5rem 4rem;
  max-width: 100%;
}
h1 {
  font-size: 2rem;
  color: #1a1a2e;
  border-bottom: 3px solid #3498db;
  padding-bottom: 0.5rem;
  margin-top: 0;
  margin-bottom: 1.5rem;
}
h2 {
  font-size: 1.4rem;
  color: #1a1a2e;
  border-bottom: 1px solid #dee2e6;
  padding-bottom: 0.3rem;
  margin-top: 2.5rem;
  margin-bottom: 1rem;
}
h3 { font-size: 1.1rem; color: #2c3e50; margin-top: 1.75rem; margin-bottom: 0.6rem; }
h4 { font-size: 0.95rem; color: #495057; margin-top: 1.25rem; margin-bottom: 0.4rem; font-weight: 600; }
a { color: #3498db; text-decoration: none; }
a:hover { text-decoration: underline; color: #2178b5; }
p { margin: 0 0 0.85rem 0; }
code {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 0.85em;
  background: #eef2f7;
  padding: 0.2em 0.45em;
  border-radius: 4px;
  color: #c0392b;
  border: 1px solid #dce4ef;
}
pre {
  background: #f0f4f8;
  border: 1px solid #d0dae8;
  color: #2c3e50;
  padding: 1.25rem 1.5rem;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 0.85rem;
  line-height: 1.6;
  margin: 1rem 0 1.5rem;
}
pre code {
  background: none;
  color: inherit;
  padding: 0;
  border-radius: 0;
  border: none;
  font-size: inherit;
}
.doc-table-wrap {
  width: 100%;
  overflow-x: auto;
  margin: 1.25rem 0 1.75rem;
  border-radius: 8px;
  border: 1px solid #d0dae8;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
  background: #fff;
}
thead tr { background: #1e3a5f; }
th {
  padding: 0.7rem 1rem;
  text-align: left;
  font-weight: 600;
  color: #fff;
  white-space: nowrap;
  border-right: 1px solid rgba(255,255,255,0.15);
}
th:last-child { border-right: none; }
tbody tr { border-bottom: 1px solid #e8edf4; transition: background 0.1s; }
tbody tr:last-child { border-bottom: none; }
tbody tr:hover { background: #f0f6ff; }
td {
  padding: 0.65rem 1rem;
  vertical-align: top;
  border-right: 1px solid #e8edf4;
  color: #2c3e50;
}
td:last-child { border-right: none; }
tbody tr:nth-child(even) td { background: #f7fafd; }
tbody tr:nth-child(even):hover td { background: #f0f6ff; }
blockquote {
  border-left: 4px solid #3498db;
  margin: 1.25rem 0;
  padding: 0.75rem 1.25rem;
  background: #f0f7ff;
  color: #2c3e50;
  border-radius: 0 8px 8px 0;
}
blockquote p:last-child { margin-bottom: 0; }
hr { border: none; border-top: 1px solid #dee2e6; margin: 2.5rem 0; }
ul, ol { padding-left: 1.6rem; margin: 0.5rem 0 1rem; }
li { margin: 0.3rem 0; }
li > ul, li > ol { margin: 0.2rem 0; }
.vendor-links {
  background: linear-gradient(135deg, #f0f7ff 0%, #e8f4ff 100%);
  border: 1px solid #90caf9;
  border-radius: 10px;
  padding: 1.25rem 1.5rem;
  margin: 0 0 2rem;
}
.vendor-links h4 { margin-top: 0; margin-bottom: 0.6rem; color: #1565c0; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.05em; }
.vendor-links ul { margin: 0; padding-left: 1.25rem; }
.vendor-links li { margin: 0.2rem 0; font-size: 0.875rem; }
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
        vendor_section = f'<div class="vendor-links"><h4>External Resources</h4><ul>{items}</ul></div>'

    wrapped_body = _wrap_tables(body_html)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Talon</title>
  <style>{_CSS}</style>
</head>
<body>
  <div class="doc-topbar">
    <a class="back-link" href="javascript:history.back()">&#8592; Back</a>
    <span class="doc-topbar-title">{title}</span>
  </div>
  <div class="doc-body">
    {vendor_section}
    {wrapped_body}
  </div>
</body>
</html>"""


def _wrap_tables(html: str) -> str:
    import re
    return re.sub(r'(<table[\s>])', r'<div class="doc-table-wrap">\1', html).replace('</table>', '</table></div>')


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
    body = f"<h1>Talon Documentation</h1><ul>{items}</ul>"
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
