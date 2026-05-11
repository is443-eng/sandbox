# Thin FastAPI entrypoint for uvicorn / Posit Connect: ``uvicorn app:app`` from 10_data_management/.
from agent_backend.api import app

__all__ = ["app"]
