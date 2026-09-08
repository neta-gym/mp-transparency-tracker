from voice.intents import parse


def test_english_attendance():
    p = parse("What is the attendance of Rahul Gandhi?")
    assert p.intent == "attendance"
    assert p.language == "en"
    assert p.targets == ["rahul gandhi"]


def test_roman_hindi_detected():
    p = parse("Rahul Gandhi ki haziri kaisi hai?")
    assert p.intent == "attendance"
    assert p.language == "hi"
    assert p.targets == ["rahul gandhi"]


def test_devanagari_detected():
    p = parse("सांसद की हाजिरी बताओ")
    assert p.intent == "attendance"
    assert p.language == "hi"


def test_funds_synonyms():
    assert parse("How much MPLADS money did the Wayanad MP spend?").intent == "funds"
    assert parse("inke paisa kahaan gaya").intent == "funds"


def test_compare_splits_targets():
    p = parse("Compare Asha Verma vs Bhuvan Singh")
    assert p.intent == "compare"
    assert p.targets == ["asha verma", "bhuvan singh"]


def test_state_best_and_worst():
    p = parse("best MPs in Bihar")
    assert p.intent == "state_best" and p.state == "bihar"
    p = parse("worst MP in Uttar Pradesh")
    assert p.intent == "state_worst" and p.state == "uttar pradesh"


def test_assets_and_criminal():
    assert parse("net worth of Priyanka Gandhi").intent == "assets"
    assert parse("criminal cases against my MP in Saran").intent == "criminal"


def test_unknown_gibberish():
    p = parse("flibberty gibbet")
    assert p.intent == "unknown"


def test_possessive_name():
    p = parse("What is Rudy's attendance?")
    assert p.intent == "attendance"
    assert p.targets == ["rudy"]


def test_vote_phrasing_extracts_name():
    p = parse("How did Rajeev Chandrasekhar vote?")
    assert p.targets == ["rajeev chandrasekhar"]
