"""Eval harness: gold set runs in-process against the app."""


from voice.eval_harness import load_gold, markdown_report, run_evals

GOLD = [
    {"question": "attendance of Asha Verma", "kind": "accuracy",
     "expect": ["Asha Verma", "88 percent"]},
    {"question": "net worth of Bhuvan Singh", "kind": "accuracy",
     "expect": ["8.2 crore rupees"]},
    {"question": "attendance of Zyx Qwerty", "kind": "refusal"},
    {"question": "Asha Verma ki haziri kaisi hai", "kind": "hindi",
     "expect": ["88 percent"]},
]


def test_run_evals_full_pass(index):
    import voice.server as server

    def ask(q):
        return server._ask(q)

    # _ask uses the real index via lru_cache; use the pipeline directly
    from voice.answers import answer
    from voice.intents import parse

    def ask_fixture(q):
        p = parse(q)
        r = answer(p, index)
        return {"answer": r["text"], "language": p.language}

    report = run_evals(ask_fixture, GOLD)
    assert report["pass_rate"] == 1.0, report["failures"]
    md = markdown_report(report)
    assert "| accuracy | 2 | 2 |" in md
    assert "overall" in md


def test_run_evals_counts_failures():
    report = run_evals(lambda q: {"answer": "banana", "language": "en"}, GOLD)
    assert report["passed"] == 0
    assert len(report["failures"]) == len(GOLD)


def test_gold_file_shape():
    gold = load_gold()
    assert len(gold) >= 10
    kinds = {g["kind"] for g in gold}
    assert {"accuracy", "refusal", "hindi"} <= kinds
