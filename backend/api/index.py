"""api/index.py — Vercel serverless entry point.

Adds the backend/ directory to sys.path and re-exports the FastAPI ASGI app so Vercel's
@vercel/python runtime can serve it. Locally the app runs directly via `uvicorn app:app`;
on Vercel it is routed here by vercel.json.

The Angular SPA is built and served separately as static files (see vercel.json), so on Vercel
app.py's StaticFiles mount stays inactive — the dist/ folder is not bundled into the function,
so `_DIST.is_dir()` is False and this entry only serves the /api routes.
"""
import sys
from pathlib import Path

_backend = str(Path(__file__).resolve().parent.parent)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from app import app  # noqa: F401, E402 — Vercel detects the ASGI app via this import
