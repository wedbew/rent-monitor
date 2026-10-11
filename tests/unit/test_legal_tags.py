from rm_core.legal import GDPR_CATEGORIES, LEGAL_AREAS, LegalTag, tag_names


def test_areas_and_categories_partition_all_tags() -> None:
    assert set(LegalTag) == LEGAL_AREAS | GDPR_CATEGORIES
    assert not LEGAL_AREAS & GDPR_CATEGORIES


def test_tag_names_match_rule_grammar() -> None:
    assert tag_names(LegalTag.scraping, LegalTag.url_analysis) == ["scraping", "url-analysis"]
