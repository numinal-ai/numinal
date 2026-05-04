"""Controlled vocabularies from numinal data card specification §3.

Every term in this module is sourced from the spec's controlled vocabulary
tables. The source reference is documented alongside each term set. Custom
terms (prefixed with 'custom:') are allowed but produce validation warnings
per spec §2.3 rule 2.
"""

# ---------------------------------------------------------------------------
# §3.1 Organisation types (gov:consumerType)
# ---------------------------------------------------------------------------

# UK public sector — Source: UK Cabinet Office Public Bodies Handbook Part 1
UK_PUBLIC_SECTOR_TYPES: set[str] = {
    "uk-ministerial-dept",
    "uk-non-ministerial-dept",
    "uk-executive-agency",
    "uk-executive-ndpb",
    "uk-advisory-ndpb",
    "uk-public-corporation",
    "uk-nhs-trust",
    "uk-local-authority",
    "uk-devolved-govt",
    "uk-combined-authority",
}

# UK private sector — Source: Companies House / Companies Act 2006
UK_PRIVATE_SECTOR_TYPES: set[str] = {
    "uk-ltd-company",
    "uk-plc",
    "uk-llp",
    "uk-sole-trader",
    "uk-startup",  # numinal-defined per spec
    "uk-sme",      # Companies Act 2006 s.465 as amended by SI 2024/1303
}

# UK academic and research — Source: OfS, SFC, CTER, DfE, HESA
UK_ACADEMIC_TYPES: set[str] = {
    "uk-university",
    "uk-research-institute",
    "uk-further-education",
    "uk-research-council",
}

# UK third sector
UK_THIRD_SECTOR_TYPES: set[str] = {
    "uk-charity",
    "uk-social-enterprise",
    "uk-cic",
}

# International
INTERNATIONAL_TYPES: set[str] = {
    "eu-registered-entity",
    "international-entity",
    "international-university",
    "international-research-org",
}

# Individual
INDIVIDUAL_TYPES: set[str] = {
    "individual-researcher",
}

# Combined set for validation
CONSUMER_TYPES: set[str] = (
    UK_PUBLIC_SECTOR_TYPES
    | UK_PRIVATE_SECTOR_TYPES
    | UK_ACADEMIC_TYPES
    | UK_THIRD_SECTOR_TYPES
    | INTERNATIONAL_TYPES
    | INDIVIDUAL_TYPES
)


# ---------------------------------------------------------------------------
# §3.2 Data use purposes (gov:purpose)
# ---------------------------------------------------------------------------

# Purposes sourced from GA4GH DUO
DUO_PURPOSES: dict[str, str] = {
    "general-research":            "DUO:0000042",
    "health-biomedical-research":  "DUO:0000006",
    "disease-specific-research":   "DUO:0000007",
    "not-for-profit-non-commercial": "DUO:0000018",
}

# numinal-defined purposes (no DUO equivalent)
NUMINAL_PURPOSES: set[str] = {
    "model-training",
    "model-fine-tuning",
    "model-evaluation",
    "model-validation",
    "benchmarking",
    "bias-auditing",
    "safety-testing",
    "red-teaming",
    "reproducibility",
    "dataset-enrichment",
    "synthetic-data-generation",
    "transfer-learning",
    "data-curation",
    "competition-entry",
    "teaching",
    "product-development",
    "clinical-decision-support",
    "public-service-delivery",
    "policy-development",
    "meta-analysis",
    "environmental-monitoring",
    "materials-discovery",
    "simulation-training",
    "infrastructure-monitoring",
}

PURPOSES: set[str] = set(DUO_PURPOSES.keys()) | NUMINAL_PURPOSES

# Purpose modifiers sourced from DUO
DUO_PURPOSE_MODIFIERS: dict[str, str] = {
    "geographic-restriction":    "DUO:0000022",
    "institution-specific":      "DUO:0000028",
    "time-limited":              "DUO:0000025",
    "project-specific":          "DUO:0000027",
    "collaboration-required":    "DUO:0000020",
    "ethics-approval-required":  "DUO:0000021",
    "publication-required":      "DUO:0000019",
    "publication-moratorium":    "DUO:0000024",
    "return-to-database":        "DUO:0000029",
    "user-specific":             "DUO:0000026",
}

PURPOSE_MODIFIERS: set[str] = set(DUO_PURPOSE_MODIFIERS.keys())


# ---------------------------------------------------------------------------
# §3.3 EU AI Act high-risk domains (gov:highRiskDomain)
# ---------------------------------------------------------------------------

# Source: EU AI Act Annex III, Regulation (EU) 2024/1689
HIGH_RISK_DOMAINS: dict[str, str] = {
    "biometrics":             "§1",
    "critical-infrastructure": "§2",
    "education-vocational":   "§3",
    "employment-workers":     "§4",
    "essential-services":     "§5",
    "law-enforcement":        "§6",
    "migration-border":       "§7",
    "justice-democracy":      "§8",
    "not-high-risk":          "Consumer declares use outside Annex III",
}


# ---------------------------------------------------------------------------
# §3.4 UK Government security classifications
# ---------------------------------------------------------------------------

# Source: UK Government Security Classifications Policy (GSCP), Cabinet Office
DATA_CLASSIFICATIONS: set[str] = {
    "official",
    "official-sensitive",
    "secret",
    "top-secret",
    "unclassified",  # numinal convenience term for non-government datasets
}


# ---------------------------------------------------------------------------
# Additional constrained value sets used in the schema
# ---------------------------------------------------------------------------

GOVERNANCE_MODELS: set[str] = {"open", "controlled", "restricted"}

LICENSE_GOVERNANCE_RELATIONSHIPS: set[str] = {
    "license-only",
    "governance-supersedes",
    "complementary",
    "license-with-conditions",
}

ACCESS_SCOPE_TYPES: set[str] = {"full", "partial", "sample"}

ACCESS_METHODS: set[str] = {
    "bulk-download",
    "api-query",
    "streaming",
    "federated-query",
    "secure-enclave",
}

RETENTION_TYPES: set[str] = {"fixed", "rolling"}

DELETION_METHODS: set[str] = {
    "cryptographic-erasure",
    "standard-deletion",
    "verified-deletion",
}

SUBPROCESSOR_SHARING: set[str] = {
    "prohibited",
    "permitted-with-notification",
    "permitted-with-approval",
}

CITATION_FORMATS: set[str] = {"bibtex", "apa", "vancouver", "custom"}

PREREQUISITE_TYPES: set[str] = {"agreement", "approval", "certification"}

VERIFICATION_METHODS: set[str] = {
    "digital-signature",
    "document-upload",
    "manual-review",
    "api-check",
}

AUDIT_FREQUENCIES: set[str] = {"annual", "biannual", "on-request"}

DATASET_ROLES: set[str] = {"training", "validation", "testing"}

BIAS_SEVERITIES: set[str] = {"high", "medium", "low"}

MITIGATION_STATUSES: set[str] = {
    "mitigated",
    "partially-mitigated",
    "documented",
    "not-assessed",
}

FUNDING_TRACKS: set[str] = {"non-commercial", "commercial"}

REPORTING_FREQUENCIES: set[str] = {"quarterly", "biannual", "annual"}


def is_custom_term(term: str) -> bool:
    """Check if a term uses the custom: extension prefix (spec §2.3 rule 2)."""
    return term.startswith("custom:")


def validate_term(term: str, vocabulary: set[str], field_name: str) -> tuple[bool, str | None]:
    """Validate a term against a vocabulary.

    Returns (valid, warning_or_error).
    Custom-prefixed terms are valid but produce a warning.
    """
    if term in vocabulary:
        return True, None
    if is_custom_term(term):
        return True, f"Custom term '{term}' in {field_name} — not in canonical vocabulary"
    return False, f"Invalid term '{term}' in {field_name}. Valid: {sorted(vocabulary)}"
