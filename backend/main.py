"""
ASGI entry when running ``uvicorn main:app`` from the ``backend/`` directory.

Application lives under ``app/``; this module re-exports ``app`` for compatibility.
"""

from app.main import app

__all__ = ["app"]
