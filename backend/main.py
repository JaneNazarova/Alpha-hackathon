"""ASGI entry point. Application setup lives in backend.app."""

from backend.app.application import create_app

app = create_app()
