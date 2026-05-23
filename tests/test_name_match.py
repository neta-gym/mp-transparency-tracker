"""Tests for shared name matching utilities."""

from tracker.utils.name_match import normalize_name, normalize_state, name_matches


class TestNormalizeName:
    def test_lowercase(self):
        assert normalize_name("Manoj Tiwari") == "manoj tiwari"

    def test_strip_shri(self):
        assert normalize_name("Shri Manoj Tiwari") == "manoj tiwari"

    def test_strip_smt(self):
        assert normalize_name("Smt. Bansuri Swaraj") == "bansuri swaraj"

    def test_strip_dr(self):
        assert normalize_name("Dr. Harsh Vardhan") == "harsh vardhan"

    def test_strip_multiple_titles(self):
        assert normalize_name("Dr. Shri Ram Kumar") == "ram kumar"

    def test_remove_punctuation(self):
        assert normalize_name("N.D. Gupta") == "nd gupta"

    def test_collapse_whitespace(self):
        assert normalize_name("  Manoj   Tiwari  ") == "manoj tiwari"

    def test_empty_string(self):
        assert normalize_name("") == ""


class TestNormalizeState:
    def test_basic(self):
        assert normalize_state("Delhi") == "delhi"

    def test_nct_alias(self):
        assert normalize_state("NCT of Delhi") == "delhi"

    def test_nct_alias_caseinsensitive(self):
        assert normalize_state("nct of delhi") == "delhi"

    def test_national_capital(self):
        assert normalize_state("National Capital Territory of Delhi") == "delhi"

    def test_jk_ampersand(self):
        assert normalize_state("Jammu & Kashmir") == "jammu and kashmir"

    def test_plain_state(self):
        assert normalize_state("  Uttar Pradesh  ") == "uttar pradesh"

    def test_unknown_passes_through(self):
        assert normalize_state("Maharashtra") == "maharashtra"

    def test_andaman_alias(self):
        assert normalize_state("Andaman & Nicobar Islands") == "andaman and nicobar islands"


class TestNameMatches:
    def test_exact_match(self):
        assert name_matches("Manoj Tiwari", "Manoj Tiwari")

    def test_case_insensitive(self):
        assert name_matches("manoj tiwari", "MANOJ TIWARI")

    def test_with_title(self):
        assert name_matches("Shri Manoj Tiwari", "Manoj Tiwari")

    def test_partial_overlap_two_tokens(self):
        assert name_matches("Harsh Malhotra", "Shri Harsh Malhotra")

    def test_no_match(self):
        assert not name_matches("Bansuri Swaraj", "Manoj Tiwari")

    def test_single_token_exact(self):
        # Single token names — should match if tokens are equal
        assert name_matches("Kumar", "Kumar")

    def test_single_token_no_match(self):
        assert not name_matches("Kumar", "Singh")

    def test_high_threshold(self):
        # With high threshold, partial overlap may not match
        assert not name_matches("A B C D", "A B E F", min_confidence=0.9)

    def test_default_threshold(self):
        # 2 out of 3 tokens overlap = 66% > 60%
        assert name_matches("Ram Kumar Singh", "Ram Kumar Verma", min_confidence=0.6)

    def test_empty_strings(self):
        assert not name_matches("", "Manoj Tiwari")
        assert not name_matches("Manoj Tiwari", "")
