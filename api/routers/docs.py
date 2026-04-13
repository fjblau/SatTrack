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
*, *::before, *::after { box-sizing: border-box; }
html { font-size: 15px; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  line-height: 1.75;
  color: #1a1a2e;
  background: #f7f8fc;
  margin: 0;
  padding: 0;
}
.page-wrap {
  display: flex;
  min-height: 100vh;
}
.sidebar {
  width: 260px;
  flex-shrink: 0;
  background: #1a1a2e;
  color: #c8cfe8;
  padding: 2rem 1.25rem;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
}
.sidebar-title {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #7b8abf;
  margin: 0 0 1rem;
}
.sidebar a {
  display: block;
  color: #c8cfe8;
  text-decoration: none;
  font-size: 0.82rem;
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  margin-bottom: 0.15rem;
}
.sidebar a:hover { background: rgba(255,255,255,0.08); color: #fff; }
.sidebar .back-link {
  color: #7b8abf;
  font-size: 0.78rem;
  margin-bottom: 1.5rem;
}
.sidebar .back-link:hover { color: #c8cfe8; }
.sidebar .vendor-title {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #7b8abf;
  margin: 1.5rem 0 0.5rem;
}
.content {
  flex: 1;
  min-width: 0;
  padding: 2.5rem 3rem 4rem;
  background: #fff;
}
h1 {
  font-size: 1.9rem;
  color: #1a1a2e;
  border-bottom: 3px solid #3498db;
  padding-bottom: 0.5rem;
  margin-top: 0;
  margin-bottom: 1.5rem;
}
h2 {
  font-size: 1.3rem;
  color: #1a1a2e;
  border-bottom: 1px solid #e0e4ef;
  padding-bottom: 0.3rem;
  margin-top: 2.5rem;
  margin-bottom: 1rem;
}
h3 { font-size: 1.05rem; color: #2c3e50; margin-top: 1.75rem; margin-bottom: 0.5rem; }
h4 { font-size: 0.95rem; color: #495057; margin-top: 1.25rem; margin-bottom: 0.4rem; }
a { color: #3498db; text-decoration: none; }
a:hover { text-decoration: underline; }
p { margin: 0 0 1rem; }
code {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 0.875em;
  background: #eef0f8;
  padding: 0.15em 0.45em;
  border-radius: 4px;
  color: #c0392b;
}
pre {
  background: #1e2235;
  color: #cdd6f4;
  padding: 1.25rem 1.5rem;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 0.83rem;
  line-height: 1.6;
  margin: 1rem 0 1.5rem;
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
  margin: 1rem 0 1.5rem;
  font-size: 0.88rem;
}
th {
  background: #eef0f8;
  border: 1px solid #d0d5e8;
  padding: 0.55rem 0.85rem;
  text-align: left;
  font-weight: 600;
  color: #2c3e50;
}
td {
  border: 1px solid #d0d5e8;
  padding: 0.5rem 0.85rem;
  vertical-align: top;
}
tr:nth-child(even) td { background: #f7f8fc; }
blockquote {
  border-left: 4px solid #3498db;
  margin: 1rem 0;
  padding: 0.6rem 1rem;
  background: #f0f7ff;
  color: #2c3e50;
  border-radius: 0 6px 6px 0;
}
blockquote p:last-child { margin: 0; }
hr { border: none; border-top: 1px solid #e0e4ef; margin: 2rem 0; }
ul, ol { padding-left: 1.5rem; margin: 0 0 1rem; }
li { margin: 0.3rem 0; }
@media (max-width: 768px) {
  .sidebar { display: none; }
  .content { padding: 1.5rem; }
}
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
    vendor_links = "".join(
        f'<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>'
        for label, url in vendor
    )
    vendor_section = ""
    if vendor_links:
        vendor_section = f'<p class="vendor-title">Official Docs</p>{vendor_links}'

    all_docs_links = "".join(
        f'<a href="/v2/docs/{n}"{"style=\"font-weight:600;color:#fff\"" if n == name else ""}>{m["title"]}</a>'
        for n, m in _DOCS.items()
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Kessler</title>
  <style>{_CSS}</style>
</head>
<body>
<div class="page-wrap">
  <nav class="sidebar">
    <a class="back-link" href="javascript:history.back()">← Back to App</a>
    <p class="sidebar-title">Documentation</p>
    {all_docs_links}
    {vendor_section}
  </nav>
  <main class="content">
    {body_html}
  </main>
</div>
</body>
</html>"""


def _md_to_html(text: str) -> str:
    if MARKDOWN_AVAILABLE:
        return md_lib.markdown(
            text,
            extensions=["fenced_code", "tables", "toc"],
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
