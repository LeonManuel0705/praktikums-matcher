from datetime import date

import pytest

from backend.app.dateparse import overlap_ratio, parse_window
from backend.app.geo import distance_between, geocode, is_remote, normalize
from backend.app.scoring import extract_keywords, infer_categories, score_offer
from backend.app.search.base import extract_json_payload, normalize_offer, valid_url

BASE_PROFILE = {
    "interests": ["ai_tech"],
    "location": "Potsdam",
    "radius_km": 30,
    "start_date": "2027-03-01",
    "end_date": "2027-03-26",
    "compensation": "paid",
    "free_text": "möchte was mit LLMs machen",
}

BASE_OFFER = {
    "title": "Praktikum Machine Learning",
    "company": "Parloa",
    "city": "Berlin-Mitte",
    "compensation_kind": "paid",
    "compensation_text": "1.200 EUR/Monat",
    "description": "Arbeit an Sprachmodellen und LLM-Pipelines.",
    "url": "https://example.com/job/1",
    "start_date_hint": "ab März 2027",
    "categories": ["ai_tech"],
}


def offer(**overrides):
    return {**BASE_OFFER, **overrides}


def profile(**overrides):
    return {**BASE_PROFILE, **overrides}


class TestGeo:
    def test_normalize_strips_umlauts_and_noise(self):
        assert normalize("Berlin-Neukölln, Deutschland") == "berlin neukoelln"

    def test_known_distances(self):
        assert 25 < distance_between("Potsdam", "Berlin-Mitte") < 30
        assert 8 < distance_between("Werder (Havel)", "Potsdam-Babelsberg") < 13

    def test_unknown_place_has_no_coordinates(self):
        assert geocode("Kuala Lumpur") is None
        assert distance_between("Potsdam", "Kuala Lumpur") is None

    def test_district_resolves_via_token_overlap(self):
        assert geocode("Berlin (10627), Wilmersdorfer Str. 60, Charlottenburg") is not None

    @pytest.mark.parametrize("value", ["Remote", "Homeoffice", "bundesweit"])
    def test_remote_detection(self, value):
        assert is_remote(value)

    def test_city_is_not_remote(self):
        assert not is_remote("Potsdam")


class TestDateParsing:
    def test_month_range_keeps_first_month(self):
        window = parse_window("Februar bis April 2027")
        assert window.start == date(2027, 2, 1)
        assert window.end == date(2027, 4, 30)

    def test_season_spans_three_months(self):
        window = parse_window("Winter 2026")
        assert window.start == date(2026, 12, 1)
        assert window.end == date(2027, 2, 28)

    def test_rolling_hint(self):
        assert parse_window("ab sofort").rolling

    def test_duration_extends_start(self):
        window = parse_window("ab 01.03.2027 für 3 Monate")
        assert window.duration_days == 90
        assert window.end == date(2027, 5, 30)

    def test_missing_information_is_neutral(self):
        score, reason = overlap_ratio(date(2027, 3, 1), date(2027, 3, 26), parse_window(""))
        assert score == 0.5
        assert "nicht angegeben" in reason

    def test_non_overlapping_window_scores_zero(self):
        score, _ = overlap_ratio(date(2027, 3, 1), date(2027, 3, 26), parse_window("Juli 2027"))
        assert score == 0.0

    def test_reversed_desired_range_is_tolerated(self):
        score, _ = overlap_ratio(date(2027, 3, 26), date(2027, 3, 1), parse_window("März 2027"))
        assert score == 1.0


class TestScoring:
    def test_perfect_match_scores_high(self):
        assert score_offer(profile(), offer()).score >= 90

    def test_mismatch_scores_low(self):
        result = score_offer(profile(), offer(
            city="München", compensation_kind="unpaid", compensation_text="",
            categories=["business"], title="Praktikum Marketing",
            description="Social Media Content.", start_date_hint="Sommer 2027"))
        assert result.score <= 15

    def test_distance_beyond_radius_lowers_location(self):
        near = score_offer(profile(), offer(city="Potsdam"))
        far = score_offer(profile(), offer(city="Frankfurt (Oder)"))
        assert near.score > far.score

    def test_criteria_weights_sum_to_one(self):
        criteria = score_offer(profile(), offer()).criteria
        assert sum(c.weight for c in criteria) == pytest.approx(1.0)

    def test_every_criterion_has_a_reason(self):
        for criterion in score_offer(profile(), offer()).criteria:
            assert criterion.detail.strip()

    def test_free_text_keywords_are_reported(self):
        assert "llms" in score_offer(profile(), offer()).matched_keywords

    def test_missing_keywords_reduce_interest(self):
        with_hit = score_offer(profile(), offer())
        without = score_offer(profile(), offer(description="Allgemeine Büroarbeit.", title="Praktikum Informatik"))
        assert with_hit.criteria[0].score > without.criteria[0].score

    def test_unpaid_is_zero_when_paid_required(self):
        result = score_offer(profile(), offer(compensation_kind="unpaid"))
        assert result.criteria[2].score == 0.0

    def test_compensation_irrelevant_when_any(self):
        result = score_offer(profile(compensation="any"), offer(compensation_kind="unpaid"))
        assert result.criteria[2].score == 1.0

    def test_unknown_compensation_is_neutral(self):
        result = score_offer(profile(), offer(compensation_kind="unknown", compensation_text=""))
        assert result.criteria[2].score == 0.5

    def test_profile_without_dates_is_neutral_on_timeframe(self):
        result = score_offer(profile(start_date=None, end_date=None), offer())
        assert result.criteria[3].score == 0.5

    def test_score_stays_within_bounds(self):
        for city in ("Potsdam", "Berlin", "München", "Nirgendwo"):
            assert 0 <= score_offer(profile(), offer(city=city)).score <= 100

    def test_keyword_extraction_drops_stopwords(self):
        assert extract_keywords("ich möchte gerne etwas mit LLMs machen") == ["llms"]

    def test_categories_are_inferred_when_missing(self):
        assert "ai_tech" in infer_categories(offer(categories=[]))


class TestOfferNormalization:
    def test_offer_without_url_is_rejected(self):
        assert normalize_offer({"title": "X", "company": "Y", "url": "kein-link"}) is None

    def test_javascript_url_is_rejected(self):
        assert not valid_url("javascript:alert(1)")

    def test_unknown_category_is_dropped(self):
        result = normalize_offer({**BASE_OFFER, "categories": ["ai_tech", "unsinn"]})
        assert result["categories"] == ["ai_tech"]

    def test_invalid_compensation_falls_back(self):
        result = normalize_offer({**BASE_OFFER, "compensation_kind": "vielleicht"})
        assert result["compensation_kind"] == "unknown"

    def test_source_defaults_to_host(self):
        result = normalize_offer({**BASE_OFFER, "source": ""})
        assert result["source"] == "example.com"

    def test_whitespace_is_collapsed(self):
        result = normalize_offer({**BASE_OFFER, "title": "  Praktikum \n\n  ML  "})
        assert result["title"] == "Praktikum ML"


class TestPayloadExtraction:
    def test_plain_array(self):
        assert len(extract_json_payload('[{"title": "A"}]')) == 1

    def test_fenced_block(self):
        assert len(extract_json_payload('Hier:\n```json\n[{"title": "A"}]\n```\nFertig')) == 1

    def test_wrapped_in_object(self):
        assert len(extract_json_payload('{"offers": [{"title": "A"}, {"title": "B"}]}')) == 2

    def test_prose_around_array(self):
        assert len(extract_json_payload('Ich habe gefunden: [{"title": "A"}] das war alles')) == 1

    def test_garbage_yields_nothing(self):
        assert extract_json_payload("keine Daten gefunden") == []

    def test_empty_input(self):
        assert extract_json_payload("") == []


class TestStreamedOfferLines:
    def test_single_line_is_parsed(self):
        from backend.app.search.base import parse_offer_lines
        line = 'OFFER: {"title":"Praktikum ML","company":"Parloa","city":"Berlin","url":"https://x.de/1"}'
        assert parse_offer_lines(line)[0]["company"] == "Parloa"

    def test_several_lines_among_prose(self):
        from backend.app.search.base import parse_offer_lines
        text = (
            'Ich habe die Seite geoeffnet.\n'
            'OFFER: {"title":"A","company":"Firma1","city":"Berlin","url":"https://x.de/1"}\n'
            'Weiter geht es.\n'
            'OFFER: {"title":"B","company":"Firma2","city":"Potsdam","url":"https://x.de/2"}\n'
            'FERTIG'
        )
        assert [o["company"] for o in parse_offer_lines(text)] == ["Firma1", "Firma2"]

    def test_broken_json_is_skipped(self):
        from backend.app.search.base import parse_offer_lines
        text = 'OFFER: {"title": kaputt}\nOFFER: {"title":"B","company":"F","city":"Berlin","url":"https://x.de/2"}'
        assert len(parse_offer_lines(text)) == 1

    def test_offer_without_url_is_skipped(self):
        from backend.app.search.base import parse_offer_lines
        assert parse_offer_lines('OFFER: {"title":"A","company":"F","city":"Berlin"}') == []

    def test_prose_without_offers(self):
        from backend.app.search.base import parse_offer_lines
        assert parse_offer_lines("Ich habe leider nichts gefunden.") == []


class TestTimeframeCalibration:
    def test_explicit_window_beats_rolling(self):
        from datetime import date
        from backend.app.dateparse import overlap_ratio, parse_window
        explicit, _ = overlap_ratio(date(2027, 3, 1), date(2027, 3, 26), parse_window("März 2027"))
        rolling, _ = overlap_ratio(date(2027, 3, 1), date(2027, 3, 26), parse_window("ab sofort"))
        assert explicit > rolling

    def test_rolling_still_beats_missing_information(self):
        from datetime import date
        from backend.app.dateparse import overlap_ratio, parse_window
        rolling, _ = overlap_ratio(date(2027, 3, 1), date(2027, 3, 26), parse_window("ab sofort"))
        unknown, _ = overlap_ratio(date(2027, 3, 1), date(2027, 3, 26), parse_window(""))
        assert rolling > unknown

    def test_rolling_beats_non_overlapping(self):
        from datetime import date
        from backend.app.dateparse import overlap_ratio, parse_window
        rolling, _ = overlap_ratio(date(2027, 3, 1), date(2027, 3, 26), parse_window("ab sofort"))
        missed, _ = overlap_ratio(date(2027, 3, 1), date(2027, 3, 26), parse_window("Juli 2027"))
        assert rolling > missed
