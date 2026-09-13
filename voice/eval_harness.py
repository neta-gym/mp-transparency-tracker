"""Reliability eval harness - the "show how you know it works" layer.

A fixed gold set of questions with expected answers (evals/gold.json) is
run against the live answer pipeline. Three scored behaviors:

  accuracy  - the answer names the right MP and states the right numbers
  refusal   - out-of-data questions get an honest "not available", never
              an invented number
  hindi     - Hindi questions (romanized and Devanagari) get Hindi answers

Results are a dict + a markdown table for the reliability brief. The same
runner drives the pytest suite (in-process) and the public /evals report
(against the deployed service), so what we test is what we ship.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLD_PATH = REPO_ROOT / "evals" / "gold.json"

REFUSAL_MARKERS = ("don't have", "not available", "no reliable",
                   "couldn't find", "didn't catch",
                   "available nahin", "nahin mila", "samajh nahin")


def load_gold(path: Path | str = GOLD_PATH) -> list[dict]:
    return json.loads(Path(path).read_text())


def _check(case: dict, answer_text: str, language: str) -> tuple[bool, str]:
    low = answer_text.lower()
    kind = case.get("kind", "accuracy")
    if kind == "refusal":
        ok = any(m in low for m in REFUSAL_MARKERS)
        return ok, "expected an honest not-available answer"
    missing = [s for s in case.get("expect", []) if s.lower() not in low]
    if missing:
        return False, f"missing expected: {missing}"
    if kind == "hindi":
        # Hindi answers are romanized Hindi or Devanagari; English template
        # markers must not dominate. Language detector on the QUESTION is the
        # contract: hi question -> answer uses the Hindi templates.
        if language != "hi":
            return False, f"question language detected as {language}, expected hi"
        en_markers = ("has attended", "declared total assets", "has asked")
        if any(m in low for m in en_markers):
            return False, "answer used the English template for a Hindi question"
    return True, ""


def run_evals(ask_fn, gold: list[dict] | None = None) -> dict:
    """ask_fn(question) -> {"answer": str, "language": str, ...}"""
    gold = gold if gold is not None else load_gold()
    started = time.time()
    results = []
    for case in gold:
        try:
            resp = ask_fn(case["question"])
            ok, why = _check(case, resp.get("answer", ""), resp.get("language", ""))
        except Exception as exc:  # an exception is a reliability failure too
            ok, why, resp = False, f"exception: {exc}", {}
        results.append({"question": case["question"], "kind": case.get("kind", "accuracy"),
                        "ok": ok, "why": why, "answer": resp.get("answer", "")[:200]})
    by_kind: dict[str, dict] = {}
    for r in results:
        k = by_kind.setdefault(r["kind"], {"total": 0, "passed": 0})
        k["total"] += 1
        k["passed"] += 1 if r["ok"] else 0
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "by_kind": by_kind,
        "duration_s": round(time.time() - started, 2),
        "failures": [r for r in results if not r["ok"]],
    }


def markdown_report(report: dict) -> str:
    lines = [
        "| Behavior | Passed | Total | Rate |",
        "|---|---|---|---|",
    ]
    for kind, k in sorted(report["by_kind"].items()):
        rate = f"{100.0 * k['passed'] / k['total']:.0f}%" if k["total"] else "-"
        lines.append(f"| {kind} | {k['passed']} | {k['total']} | {rate} |")
    lines.append(f"| **overall** | **{report['passed']}** | **{report['total']}** "
                 f"| **{100.0 * report['pass_rate']:.0f}%** |")
    if report["failures"]:
        lines.append("")
        lines.append("Failures:")
        for f in report["failures"]:
            lines.append(f"- [{f['kind']}] {f['question']}: {f['why']}")
    return "\n".join(lines)
