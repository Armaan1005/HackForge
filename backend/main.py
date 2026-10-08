"""Axon API entrypoint (shared). /api -> engine (Part A), /api/ai -> genai (Part B).

Run from backend/:  uvicorn main:app --port 8000   (or `npm run dev` in frontend/ to run both)
"""

import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from engine.router import install_error_handlers  # noqa: E402
from engine.router import router as engine_router  # noqa: E402

log = logging.getLogger("axon")


class _QuietPolling(logging.Filter):
    """Hide the UI's 8-second /api/ai/status polling so the Gemini trace stays readable."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "/api/ai/status" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(_QuietPolling())

app = FastAPI(title="Axon")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
install_error_handlers(app)
app.include_router(engine_router)  # /api/...

try:
    from genai.router import lifespan as genai_lifespan, router as genai_router  # Part B
except ImportError:
    log.warning("genai.router not found; serving engine endpoints only")
else:
    app.include_router(genai_router)  # /api/ai/...
    app.router.lifespan_context = genai_lifespan
