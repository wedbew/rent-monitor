"""Runtime registry for LEGAL[...] / GDPR[...] tags (.agent/rules/legal-tags.md).

Names here must match the source-comment tags exactly. A tag means "needs legal attention",
not a legal verdict. Add a new area here and in the rule file in the same PR.
"""

from enum import StrEnum


class LegalTag(StrEnum):
    # LEGAL[...] areas
    scraping = "scraping"
    url_analysis = "url-analysis"
    images = "images"
    third_party_data = "third-party-data"
    republication = "republication"
    tax_invoice = "tax-invoice"
    # GDPR[...] categories
    personal_data = "personal-data"
    processor = "processor"
    retention = "retention"
    erasure = "erasure"
    consent = "consent"


LEGAL_AREAS = frozenset(
    {
        LegalTag.scraping,
        LegalTag.url_analysis,
        LegalTag.images,
        LegalTag.third_party_data,
        LegalTag.republication,
        LegalTag.tax_invoice,
    }
)
GDPR_CATEGORIES = frozenset(set(LegalTag) - LEGAL_AREAS)


def tag_names(*tags: LegalTag) -> list[str]:
    """Values for structlog `legal_tags=` and `audit_event.payload["legal_tags"]` (ids and names only)."""
    return [t.value for t in tags]
