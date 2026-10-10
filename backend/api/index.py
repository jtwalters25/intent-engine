"""Vercel Python entry point.

Exposes the FastAPI ASGI app so Vercel's Python runtime can serve the backend
(legacy `/rank`, V4 `/v4/*`, and Discover `/discover/*`). `backend/vercel.json`
rewrites every path to this function; FastAPI does its own routing.
"""

from intent_engine.api import app  # noqa: F401  (ASGI app served by Vercel)
