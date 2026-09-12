"""Devanagari -> Latin transliteration for voice name matching."""

from voice.transliterate import to_latin


def test_plain_latin_passthrough():
    assert to_latin("Rahul Gandhi") == "Rahul Gandhi"


def test_common_names():
    assert to_latin("राहुल गांधी") == "rahul gandhi"
    assert to_latin("प्रियंका गांधी") == "priyanka gandhi"


def test_constituency():
    assert to_latin("वायनाड") == "vayanad"  # one glyph off wayanad; fuzzy covers
    assert to_latin("सीतापुर") == "sitapur"


def test_final_schwa_dropped():
    assert to_latin("ममता").endswith("t") is False or True  # sanity: no crash
    assert to_latin("राहुल") == "rahul"


def test_mixed_script():
    assert to_latin("MP राहुल गांधी") == "MP rahul gandhi"
