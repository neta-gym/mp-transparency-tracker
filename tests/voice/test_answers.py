from voice.answers import answer
from voice.intents import parse


def ask(index, q):
    return answer(parse(q), index)


def test_attendance_en(index):
    r = ask(index, "attendance of Asha Verma")
    assert "88 percent" in r["text"]
    assert "Asha Verma" in r["text"]
    assert r["mps"] == ["asha-verma"]


def test_attendance_hi(index):
    r = ask(index, "Asha Verma ki haziri kaisi hai?")
    assert "88 percent" in r["text"]
    assert "sansaad" in r["text"] or "haziri" in r["text"]


def test_attendance_missing_data(index):
    r = ask(index, "attendance of Chitra Rao")
    assert "reliable" in r["text"]


def test_funds_indian_units(index):
    r = ask(index, "How much money did Asha Verma spend?")
    assert "10.0 crore" in r["text"]
    assert "7.5 crore" in r["text"]
    assert "75 percent" in r["text"]


def test_criminal_zero(index):
    r = ask(index, "criminal cases Asha Verma")
    assert "no criminal cases" in r["text"]


def test_criminal_nonzero(index):
    r = ask(index, "criminal cases Bhuvan Singh")
    assert "3 criminal cases" in r["text"]
    assert "1" in r["text"]  # serious count present


def test_assets(index):
    r = ask(index, "net worth of Bhuvan Singh")
    assert "8.2 crore" in r["text"]


def test_score_with_rank(index):
    r = ask(index, "report card of Asha Verma")
    assert "81.5" in r["text"]
    assert "rank number 1" in r["text"]


def test_compare_correct_winner(index):
    r = ask(index, "Compare Asha Verma vs Bhuvan Singh")
    assert "Asha Verma leads 81.5 to 33.0" in r["text"]


def test_state_best(index):
    r = ask(index, "best MPs in Test Pradesh")
    assert "Asha Verma" in r["text"]
    assert "81.5" in r["text"]


def test_state_worst(index):
    r = ask(index, "worst MP in Other State")
    assert "Chitra Rao" in r["text"]


def test_unknown_mp(index):
    r = ask(index, "attendance of Zzz Nobody")
    assert "couldn't find" in r["text"]


def test_unknown_name_gets_retry_prompt(index):
    r = ask(index, "flibberty gibbet")
    assert "couldn't find an MP" in r["text"]


def test_fallback_names_capabilities(index):
    r = ask(index, "what is the mp")  # all filler words, nothing to look up
    assert "attendance" in r["text"]  # fallback explains what it can do


def test_every_answer_points_at_site(index):
    for q in ["attendance of Asha Verma", "net worth of Bhuvan Singh",
              "report card of Asha Verma", "Compare Asha Verma vs Bhuvan Singh",
              "best MPs in Test Pradesh"]:
        assert "neta-gym.github.io" in ask(index, q)["text"]
