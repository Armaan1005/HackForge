"""Axon API entrypoint. Shared file: mounts Part A (engine, /api) and Part B (genai, /api/ai).

Each router import is guarded so either part can run before the other exists.
"""
import logging

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

log = logging.getLogger("axon")

app = FastAPI(title="Axon", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    from engine.router import router as engine_router  # Part A

    app.include_router(engine_router)
except ImportError as e:
    log.warning("engine router not available yet: %s", e)

try:
    from genai.router import lifespan as genai_lifespan, router as genai_router  # Part B

    app.include_router(genai_router)
    app.router.lifespan_context = genai_lifespan
except ImportError as e:
    log.warning("genai router not available yet: %s", e)
