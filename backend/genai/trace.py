"""Terminal trace of every Gemini call, in the style of the Prism (SAP Hackfest) AI Core trace.

AI_TRACE=on (default) prints clipped prompts and responses, AI_TRACE=full prints them untruncated,
AI_TRACE=off silences it. Secrets are never printed: only prompts, responses and metadata.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass

TRACE = os.environ.get("AI_TRACE", "on").strip().lower()

# Box-drawing characters and ANSI colours must survive Windows consoles and piped output.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, ValueError):
    pass
if os.name == "nt":
    os.system("")  # enables ANSI escape processing in classic Windows consoles

C = {"dim": "\x1b[2m", "cyan": "\x1b[36m", "green": "\x1b[32m", "red": "\x1b[31m", "yellow": "\x1b[33m",
     "magenta": "\x1b[35m", "bold": "\x1b[1m", "reset": "\x1b[0m"}
_n = 0


def _out(line: str) -> None:
    print(line, flush=True)


def clip(s: object, n: int) -> str:
    s = str(s if s is not None else "")
    return s if TRACE == "full" or len(s) <= n else f"{s[:n]} … (+{len(s) - n} chars)"


def pretty(s: str) -> str:
    try:
        return json.dumps(json.loads(s), indent=2, ensure_ascii=False)
    except (ValueError, TypeError):
        return s


def indent(s: str) -> str:
    return "\n".join("│   " + line for line in s.splitlines())


@dataclass
class Span:
    n: int
    agent: str
    t0: float


def start(agent: str, model: str, system: str, prompt: str, images: int = 0, priority: str = "live") -> Span | None:
    global _n
    if TRACE == "off":
        return None
    _n += 1
    extra = f" · {images} image{'s' if images != 1 else ''}" if images else ""
    _out(f"\n{C['cyan']}{C['bold']}┌─ AI call #{_n} · {agent} agent{C['reset']} {C['dim']}({model} · {priority} priority{extra}){C['reset']}")
    if system:
        _out(f"{C['dim']}│ SYSTEM:{C['reset']} {clip(' '.join(system.split()), 300)}")
    _out(f"{C['dim']}│ USER →{C['reset']}\n{indent(clip(pretty(prompt), 1500))}")
    return Span(_n, agent, time.monotonic())


def end(span: Span | None, content: str, usage=None, model: str | None = None) -> None:
    if not span:
        return
    ms = int((time.monotonic() - span.t0) * 1000)
    tokens = ""
    if usage is not None:
        tin, tout = getattr(usage, "prompt_token_count", None), getattr(usage, "candidates_token_count", None)
        if tin is not None:
            tokens = f" · {tin} in / {tout} out tokens"
    by = f" · answered by {model}" if model else ""
    _out(f"{C['green']}│ RESPONSE ←{C['reset']} {C['dim']}{ms} ms{tokens}{by}{C['reset']}")
    _out(indent(clip(pretty(content), 2500)))
    _out(f"{C['green']}└─ #{span.n} done{C['reset']}")


def retry(span: Span | None, attempt: int, total: int, err: Exception) -> None:
    if span:
        _out(f"{C['yellow']}│ retry {attempt}/{total} after: {type(err).__name__}: {clip(err, 200)}{C['reset']}")


def switch(span: Span | None, old: str, new: str, err: Exception) -> None:
    if not span:
        return
    code = getattr(err, "code", "?")
    why = "overloaded" if code == 503 else "free-tier quota used up" if code == 429 else f"error {code}"
    nxt = f"trying {new}" if new != old else f"waiting, then retrying {new}"
    _out(f"{C['yellow']}│ {old}: {why} ({code}) → {nxt}{C['reset']}")


def fail(span: Span | None, err: Exception) -> None:
    if span:
        ms = int((time.monotonic() - span.t0) * 1000)
        _out(f"{C['red']}└─ #{span.n} FAILED after {ms} ms: {type(err).__name__}: {clip(err, 300)}{C['reset']} {C['dim']}(falling back to template){C['reset']}")


def cache_hit(agent: str) -> None:
    if TRACE != "off":
        _out(f"{C['dim']}○ {agent} · cache hit (no Gemini call){C['reset']}")


def skipped(agent: str, reason: str) -> None:
    if TRACE != "off":
        _out(f"{C['dim']}○ {agent} · template ({reason}){C['reset']}")


def retrieval(agent: str, rules: list[dict]) -> None:
    if TRACE != "off":
        _out(f"{C['magenta']}◆ Retrieval · {agent}: {', '.join(r['id'] for r in rules)}{C['reset']}")


def verifier(agent: str, kept: int, dropped: list[dict]) -> None:
    if TRACE == "off":
        return
    colour = C["yellow"] if dropped else C["magenta"]
    _out(f"{colour}◆ Citation check · {agent}: {kept} kept, {len(dropped)} struck{C['reset']}")
    for d in dropped:
        _out(f"{C['yellow']}  ✗ \"{clip(d.get('point', ''), 140)}\" {C['dim']}({d.get('reason')}){C['reset']}")
