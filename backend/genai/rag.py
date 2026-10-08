"""Retrieval over the Axon rulebook (payer rules POL-* + law summaries LAW-*), for the agents.

Plain BM25, no AI calls: deterministic, instant, and every retrieved rule becomes citable
evidence for that case only (the Citation Verifier rejects rule IDs that weren't retrieved).
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache

from .config import REPO_DIR

RULEBOOK = REPO_DIR / "data" / "reference" / "rulebook.json"
_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "of", "to", "and", "or", "in", "on", "for", "is", "are", "be", "by", "with", "as", "at", "it", "this",
         "that", "its", "not", "from", "one", "same", "only", "more", "than", "case", "claim", "claims", "provider", "providers"}


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


@lru_cache(maxsize=1)
def _index() -> tuple[list[dict], list[Counter], dict[str, float], float]:
    entries = json.loads(RULEBOOK.read_text(encoding="utf-8"))["entries"]
    docs = [Counter(_tokens(f"{e['title']} {e['tags']} {e['tags']} {e['text']}")) for e in entries]
    n = len(docs)
    df = Counter(t for d in docs for t in d)
    idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
    avg = sum(sum(d.values()) for d in docs) / max(n, 1)
    return entries, docs, idf, avg


def search(query: str, k: int = 5, kind: str | None = None) -> list[dict]:
    entries, docs, idf, avg = _index()
    q = _tokens(query)
    scored = []
    for e, d in zip(entries, docs):
        if kind and e["kind"] != kind:
            continue
        length = sum(d.values())
        s = sum(idf.get(t, 0) * d[t] * 2.2 / (d[t] + 1.2 * (0.25 + 0.75 * length / avg)) for t in q if t in d)
        if s > 0:
            scored.append((s, e))
    scored.sort(key=lambda x: -x[0])
    return [{**e, "score": round(s, 2)} for s, e in scored[:k]]


def case_query(case: dict) -> str:
    """What the case is about, in words the rulebook uses."""
    parts = [case.get("pattern", "").replace("_", " "), case.get("title", "")]
    for e in case.get("evidence", []):
        parts += [e.get("name", ""), e.get("method", "").replace(".", " ").replace("_", " ")]
    parts += [m.get("doc_type", "").replace("_", " ") + " missing documentation" for m in case.get("missing_documents", [])]
    if (case.get("payment_clock") or {}).get("hold_recommended"):
        parts.append("hold payment pending release")
    return " ".join(parts)


def for_case(case: dict, rules: int = 6, laws: int = 3) -> list[dict]:
    """Rules + laws relevant to this case, plus the always-on human-review rule."""
    q = case_query(case)
    hits = search(q, rules, "payer_rule") + search(q, laws, "law")
    have = {h["id"] for h in hits}
    # always-on: AI is advisory (POL-033); the insurer fraud-monitoring framework (LAW-001) applies to every SIU case
    hits += [e for e in _index()[0] if e["id"] in {"POL-033", "LAW-001"} - have]
    return hits


def as_evidence(rules: list[dict]) -> list[dict]:
    """Rulebook entries shaped so the verifier and prompts can treat them like evidence items."""
    return [{"evidence_id": r["id"], "type": "rulebook", "kind": r["kind"], "name": r["title"], "description": r["text"],
             "source": r["source"], "verify": r.get("verify", False)} for r in rules]


def rule_refs(arguments: list[dict], case: dict) -> list[dict]:
    """Retrieved rules for the UI: which ones the agents actually cited, then the rest."""
    cited = {i for a in arguments for i in a.get("evidence_ids", [])}
    out = [{"id": r["id"], "kind": r["kind"], "title": r["title"], "text": r["text"], "source": r["source"],
            "verify": r.get("verify", False), "cited": r["id"] in cited} for r in for_case(case)]
    return sorted(out, key=lambda r: not r["cited"])
