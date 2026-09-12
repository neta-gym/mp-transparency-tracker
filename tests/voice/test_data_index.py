def test_loads_all_mps(index):
    stats = index.stats()
    assert stats["mps_indexed"] == 4
    assert stats["states"] == 2
    assert stats["with_scores"] == 4


def test_find_by_exact_name(index):
    rec = index.find("Asha Verma")
    assert rec is not None and rec.slug == "asha-verma"


def test_find_by_constituency(index):
    rec = index.find("Sitapur")
    assert rec is not None and rec.name == "Bhuvan Singh"


def test_find_case_and_punctuation_insensitive(index):
    rec = index.find("asha verma!!")
    assert rec is not None and rec.slug == "asha-verma"


def test_find_fuzzy_typo(index):
    rec = index.find("Chittra Rao")
    assert rec is not None and rec.slug == "chitra-rao"


def test_find_unknown_returns_none(index):
    assert index.find("Zzz Nonexistent") is None


def test_rank_attached_from_leaderboard(index):
    rec = index.find("Asha Verma")
    assert rec.national_rank == 1
    assert rec.composite_score == 81.5


def test_state_leaders_and_laggards(index):
    leaders = index.state_leaders("Test Pradesh")
    assert [r.name for r in leaders] == ["Asha Verma", "Bhuvan Singh"]
    laggards = index.state_laggards("test pradesh")
    assert laggards[0].name == "Bhuvan Singh"


def test_skips_validated_duplicates(data_dir):
    import json
    dup = data_dir / "test-pradesh" / "raw" / "asha-verma_validated.json"
    dup.write_text(json.dumps({"mp": {"name": "Asha Verma"}}))
    from voice.data_index import MPDataIndex
    idx = MPDataIndex(data_dir)
    assert idx.stats()["mps_indexed"] == 4


def test_find_devanagari_name(index):
    rec = index.find("आशा वर्मा")
    assert rec is not None and rec.slug == "asha-verma"


def test_find_devanagari_constituency(index):
    rec = index.find("सीतापुर")
    assert rec is not None and rec.slug == "bhuvan-singh"
