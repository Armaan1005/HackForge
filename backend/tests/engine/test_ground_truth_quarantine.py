"""Only engine/trust.py and engine/twin/ may read ground truth (spec ground rule 2).
engine/generate/ writes it (and never reads it back)."""

from pathlib import Path

ENGINE = Path(__file__).resolve().parents[2] / "engine"


def allowed(path: Path) -> bool:
    rel = path.relative_to(ENGINE).as_posix()
    return rel == "trust.py" or rel.startswith("twin/") or rel.startswith("generate/")


def test_generator_never_reads_ground_truth():
    for p in sorted((ENGINE / "generate").rglob("*.py")):
        text = p.read_text(encoding="utf-8")
        assert "read_csv" not in text or "ground_truth" not in text, p.name


def test_no_ground_truth_outside_trust_and_twin():
    offenders = [
        p.relative_to(ENGINE).as_posix()
        for p in sorted(ENGINE.rglob("*.py"))
        if not allowed(p) and "ground_truth" in p.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"ground truth referenced outside trust.py/twin/: {offenders}"
