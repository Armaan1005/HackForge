"""Axon API entrypoint (shared). /api -> engine (Part A), /api/ai -> genai (Part B).

Run from backend/:  uvicorn main:app --reload --port 8000
"""

import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from engine.router import install_error_handlers
from engine.router import router as engine_router

app = FastAPI(title="Axon")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
install_error_handlers(app)
app.include_router(engine_router)  # /api/...

try:
    from genai.router import router as genai_router  # pyright: ignore[reportMissingImports]  # Part B
except ImportError:
    logging.getLogger("axon").warning("genai.router not found; serving engine endpoints only")
else:
    app.include_router(genai_router)  # /api/ai/...
